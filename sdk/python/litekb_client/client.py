"""Small synchronous client for the public LiteKB /v1 API."""
import json
import time
from dataclasses import dataclass
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class LiteKBError(Exception):
    def __init__(self, message, *, status=None):
        super().__init__(message)
        self.status = status


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class Event:
    id: int
    kind: str
    data: dict


def _frames(lines):
    fields, data = {}, []
    for line in lines:
        if not line.endswith((b"\n", b"\r")):
            return
        line = line.decode("utf-8").rstrip("\r\n")
        if not line:
            if data:
                try:
                    yield Event(int(fields["id"]), fields["event"], json.loads("\n".join(data)))
                except (KeyError, ValueError) as exc:
                    raise LiteKBError("Invalid SSE event received from LiteKB.") from exc
            fields, data = {}, []
        elif not line.startswith(":"):
            key, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if key == "data":
                data.append(value)
            elif key in ("id", "event"):
                fields[key] = value
    # An incomplete final frame has not been acknowledged and will be replayed.


def _resource(value):
    return quote(str(value), safe="")


class Client:
    def __init__(self, base_url, api_key, *, subject=None, timeout=70):
        base = urlsplit(base_url)
        if base.scheme not in ("http", "https") or not base.netloc or base.query or base.fragment:
            raise ValueError("Provide a LiteKB HTTP(S) base URL.")
        if not api_key or timeout <= 0:
            raise ValueError("A service key and a positive request timeout are required.")
        self._base = base_url.rstrip("/") + "/v1"
        self._headers = {"Authorization": "Bearer " + api_key}
        if subject is not None:
            if not subject.isascii() or not subject.strip() or len(subject) > 160 or not subject.isprintable():
                raise ValueError("Use a stable printable ASCII subject of 1 to 160 characters.")
            self._headers["X-LiteKB-Subject"] = subject
        self._timeout = timeout
        self._opener = build_opener(_NoRedirects())

    def _open(self, path, *, method="GET", body=None, headers=None):
        headers = {**self._headers, "Accept": "application/json", **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(self._base + path, data=data, method=method, headers=headers)
        try:
            return self._opener.open(req, timeout=self._timeout)
        except HTTPError as exc:
            with exc:
                detail = exc.read(4096).decode("utf-8", "replace")
            raise LiteKBError(f"HTTP {exc.code}: {detail}", status=exc.code) from exc

    def _json(self, path, **kwargs):
        with self._open(path, **kwargs) as response:
            return json.load(response)

    def agents(self, *, offset=0, limit=50):
        return self._json(f"/agents?offset={int(offset)}&limit={int(limit)}")

    def create_knowledge_base(self, name, embedding_model_id, *, description=""):
        return self._json("/knowledge-bases", method="POST", body={
            "name": name, "embedding_model_id": str(embedding_model_id), "description": description,
        })

    def add_text(self, kb_id, name, content):
        response = self._json(f"/knowledge-bases/{_resource(kb_id)}/documents", method="POST",
                              body={"name": name, "content": content})
        return response["documents"][0]

    def document(self, kb_id, document_id):
        return self._json(f"/knowledge-bases/{_resource(kb_id)}/documents/{_resource(document_id)}")

    def retrieve(self, knowledge_base_ids, query, *, mode="rrf", top_k=5, **options):
        body = dict(options, knowledge_base_ids=list(knowledge_base_ids), query=query, mode=mode, top_k=top_k)
        return self._json("/retrievals", method="POST", body=body)["hits"]

    def start_run(self, agent_id, message, *, idempotency_key, session_id=None, form_data=None, max_runtime_seconds=None):
        if not idempotency_key:
            raise ValueError("Supply the stable idempotency key of this product request.")
        body = {"message": message}
        for key, value in (("session_id", session_id), ("form_data", form_data), ("max_runtime_seconds", max_runtime_seconds)):
            if value is not None:
                body[key] = value
        return self._json(f"/agents/{_resource(agent_id)}/runs", method="POST", body=body,
                          headers={"Idempotency-Key": idempotency_key})

    def run(self, run_id):
        return self._json(f"/runs/{_resource(run_id)}")

    def cancel(self, run_id):
        return self._json(f"/runs/{_resource(run_id)}/cancel", method="POST", body={})

    def resume(self, run_id, node_data, *, waiting_event_id):
        return self._json(f"/runs/{_resource(run_id)}/resume", method="POST",
                          body={"node_data": node_data, "waiting_event_id": waiting_event_id})

    def events(self, run_id, *, after=0, max_retries=5):
        """Stream committed events after a saved cursor. Retry reads, never replay a mutation."""
        if after < 0 or max_retries < 0:
            raise ValueError("after and max_retries must be nonnegative.")
        cursor, failures = after, 0
        ending = {"succeeded", "failed", "cancelled", "waiting_input"}
        while True:
            try:
                opened_at, initial_cursor = time.monotonic(), cursor
                with self._open(f"/runs/{_resource(run_id)}/events", headers={
                    "Accept": "text/event-stream", "Last-Event-ID": str(cursor),
                }) as response:
                    if response.headers.get_content_type() != "text/event-stream":
                        raise LiteKBError("Expected a text/event-stream response.")
                    for event in _frames(response):
                        if event.id <= cursor:
                            continue
                        if event.id != cursor + 1:
                            raise LiteKBError(f"Gap in run events after {cursor}.")
                        cursor, failures = event.id, 0
                        yield event
                        if event.kind.startswith("run.") and event.kind[4:] in ending:
                            return
                state = self.run(run_id)
                if state["status"] in ending and cursor >= state["event_sequence"]:
                    return
                # Healthy streams also rotate periodically, even for a long, silent node.
                if cursor == initial_cursor and time.monotonic() - opened_at < 1:
                    raise ConnectionError("Run event stream ended prematurely.")
                time.sleep(0.1)
            except (URLError, TimeoutError, ConnectionError, IncompleteRead, LiteKBError) as exc:
                if isinstance(exc, LiteKBError) and exc.status not in (429, 500, 502, 503, 504):
                    raise
                if failures >= max_retries:
                    raise
                time.sleep(min(0.25 * 2**failures, 3))
                failures += 1

    def stream_text(self, run_id, *, after=0):
        """Yield user-visible answer chunks. Use events() to save cursors or render a form."""
        for event in self.events(run_id, after=after):
            if event.kind == "answer.delta" and event.data.get("text"):
                yield event.data["text"]
            elif event.kind == "run.failed":
                state = self.run(run_id)
                raise LiteKBError(f"Run {run_id} failed: {state['error']}")
