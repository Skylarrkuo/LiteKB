import io
import json
import unittest
from email.message import Message
from unittest.mock import Mock, patch
from urllib.error import URLError

from litekb_client import Client, LiteKBError


def stream(data):
    body = io.BytesIO(data)
    body.headers = Message()
    body.headers["Content-Type"] = "text/event-stream"
    return body


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.client = Client("http://127.0.0.1:8080", "server-key", subject="user-42")

    def test_half_frame_then_replay_from_last_delivered_event(self):
        partial = b'id: 1\nevent: run.running\ndata: {}\n\nid: 2\nevent: answer.delta\ndata: {"text":"\xe4'
        final = 'id: 2\nevent: answer.delta\ndata: {"text":"好"}\n\nid: 3\nevent: run.succeeded\ndata: {}\n\n'
        responses = [stream(partial), io.BytesIO(b'{"status":"succeeded","event_sequence":3}'), stream(final.encode())]
        with patch.object(self.client._opener, "open", side_effect=responses) as fetch:
            events = list(self.client.events("r"))
        self.assertEqual([e.id for e in events], [1, 2, 3])
        self.assertEqual(events[1].data["text"], "好")
        self.assertEqual(fetch.call_args_list[-1].args[0].get_header("Last-event-id"), "1")

    def test_terminal_cursor_returns_without_duplicate(self):
        responses = [stream(b""), io.BytesIO(b'{"status":"succeeded","event_sequence":9}')]
        with patch.object(self.client._opener, "open", side_effect=responses):
            self.assertEqual(list(self.client.events("r", after=9)), [])

    def test_unrecoverable_stream_gap(self):
        with patch.object(self.client._opener, "open", return_value=stream(b"id: 3\nevent: answer.delta\ndata: {}\n\n")):
            with self.assertRaisesRegex(LiteKBError, "Gap"):
                list(self.client.events("r"))

    def test_read_retry_does_not_apply_to_writes(self):
        retry = Mock(side_effect=[URLError("offline"), stream(b"id: 1\nevent: run.cancelled\ndata: {}\n\n")])
        with patch.object(self.client._opener, "open", retry), patch("litekb_client.client.time.sleep"):
            self.assertEqual([e.kind for e in self.client.events("r")], ["run.cancelled"])
        with patch.object(self.client._opener, "open", side_effect=URLError("offline")) as post:
            with self.assertRaises(URLError):
                self.client.start_run("a", "message", idempotency_key="ticket-42")
            self.assertEqual(post.call_count, 1)

    def test_product_methods_encode_retrieval_and_form_version(self):
        results = [io.BytesIO(b'{"hits":[{"paragraph_id":"p"}]}'), io.BytesIO(b'{"status":"queued"}')]
        with patch.object(self.client._opener, "open", side_effect=results) as fetch:
            self.assertEqual(self.client.retrieve(["k"], "warranty"), [{"paragraph_id": "p"}])
            self.client.resume("r", {"approved": True}, waiting_event_id=7)
        query, submission = (entry.args[0] for entry in fetch.call_args_list)
        self.assertEqual(json.loads(query.data)["mode"], "rrf")
        self.assertEqual(submission.get_header("X-litekb-subject"), "user-42")
        self.assertEqual(json.loads(submission.data), {"node_data": {"approved": True}, "waiting_event_id": 7})
