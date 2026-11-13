from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from application.models import Application, ApplicationFolder, ApplicationVersion
from users.models import User
from .models import Project, Run, ServiceClient
from .run_service import enqueue
from .tasks import execute_run


def node(key, kind, **data):
    return {
        "id": key,
        "type": kind,
        "x": 0,
        "y": 0,
        "properties": {"stepName": key, "config": {"fields": [], "globalFields": []}, "node_data": data},
    }


def edge(source, target, branch=""):
    return {
        "id": source + target,
        "type": "app-edge",
        "sourceNodeId": source,
        "targetNodeId": target,
        "sourceAnchorId": source + ("_" + branch if branch else "") + "_right",
        "targetAnchorId": target + "_left",
    }


def reply(key, text):
    return node(key, "reply-node", reply_type="custom", content=text, is_result=True)


def graph(nodes, edges):
    return {"nodes": [node("base-node", "base-node"), node("start-node", "start-node"), *nodes], "edges": edges}


class RunTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create(username="run-owner", nick_name="Run", password="unused", role="ADMIN")
        folder = ApplicationFolder.objects.create(id="run-test", workspace_id="run-test", name="Tests")
        self.agent = Application.objects.create(
            name="Agent", user=self.owner, folder=folder, workspace_id=folder.pk, type="WORK_FLOW", is_publish=True
        )
        self.project = Project.objects.create(slug="run-test", name="Project", workspace_id=folder.pk, owner=self.owner)
        self.project.applications.add(self.agent)
        self.caller, self.key = ServiceClient.issue(self.project, "product")
        self.http = APIClient()
        self.auth(self.key, "alice")
        self.create_url = f"/v1/agents/{self.agent.pk}/runs"
        # Keep the real workflow worker and database. Dispatch it explicitly between HTTP requests.
        self.dispatch = self.enterContext(patch("litekb_api.run_service.enqueue"))
        self.enterContext(patch("litekb_api.run_views.enqueue", self.dispatch))

    def auth(self, key, subject):
        self.http.credentials(HTTP_AUTHORIZATION="Bearer " + key, HTTP_X_LITEKB_SUBJECT=subject)

    def publish(self, flow):
        return ApplicationVersion.objects.create(
            application=self.agent,
            user=self.owner,
            type="WORK_FLOW",
            workspace_id=self.project.workspace_id,
            application_name="Agent",
            work_flow=flow,
        )

    def start(self, message="hello", **data):
        response = self.http.post(self.create_url, {"message": message, **data}, format="json")
        self.assertEqual(response.status_code, 202, response.content)
        return Run.objects.get(pk=response.json()["id"])

    def work(self, run, expected):
        execute_run.run(str(run.pk))
        run.refresh_from_db()
        self.assertEqual(run.status, expected, (run.error, run.result))

    def test_pinned_version_condition_loop_and_sse_resume(self):
        body = {
            "nodes": [node("loop-start-node", "loop-start-node"), reply("iteration", "repeat")],
            "edges": [edge("loop-start-node", "iteration")],
        }
        branch = node(
            "branch", "condition-node", branch=[{"id": "yes", "type": "IF", "condition": "and", "conditions": []}]
        )
        flow = graph(
            [branch, node("loop", "loop-node", loop_type="NUMBER", number=2, loop_body=body)],
            [edge("start-node", "branch"), edge("branch", "loop", "yes")],
        )
        original = self.publish(flow)
        run = self.start()
        self.publish(graph([reply("new", "different")], [edge("start-node", "new")]))
        self.work(run, Run.Status.SUCCEEDED)
        self.assertEqual(run.version_id, original.pk)
        self.assertEqual(self.http.get("/v1/agents").json()["results"][0]["id"], str(self.agent.pk))
        self.assertEqual(self.http.get(self.create_url, {"session_id": str(run.session_id)}).json()["count"], 1)
        self.assertIn("repeat", run.result["answer"])
        self.assertEqual(set(run.steps.filter(node_id="iteration").values_list("iteration", flat=True)), {0, 1})
        sequences = list(run.events.values_list("sequence", flat=True))
        self.assertEqual(sequences, list(range(1, len(sequences) + 1)))
        self.assertEqual(run.events.filter(kind="step.finished").count(), run.steps.count())
        response = self.http.get(
            f"/v1/runs/{run.pk}/events", HTTP_LAST_EVENT_ID=str(sequences[-2]), HTTP_ACCEPT_ENCODING="gzip"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.has_header("Content-Encoding"))
        body = b"".join(response.streaming_content).decode()
        self.assertEqual(body.count("event: "), 1)
        self.assertIn("event: run.succeeded", body)

    def test_form_resume_keeps_record_and_attempts(self):
        form = node("approval", "form-node", form_field_list=[], form_content_format="{{form}}")
        self.publish(
            graph([form, reply("complete", "approved")], [edge("start-node", "approval"), edge("approval", "complete")])
        )
        run = self.start()
        self.work(run, Run.Status.WAITING)
        record_id = run.chat_record_id
        first_duration = run.budget["used_runtime_seconds"]
        response = self.http.post(f"/v1/runs/{run.pk}/resume", {"node_data": {"ok": True}}, format="json")
        self.assertEqual(response.status_code, 202, response.content)
        self.work(run, Run.Status.SUCCEEDED)
        self.assertEqual(run.chat_record_id, record_id)
        self.assertGreater(run.budget["used_runtime_seconds"], first_duration)
        self.assertIn("approved", run.result["answer"])
        self.assertEqual(
            list(run.steps.filter(node_id="approval").values_list("attempt", "status")),
            [(1, "waiting_input"), (2, "succeeded")],
        )

    def test_simple_agent_uses_published_fallback_and_session_history(self):
        from application.models import ChatRecord

        version = self.publish({})
        version.type = "SIMPLE"
        version.knowledge_setting["no_references_setting"] = {"status": "designated_answer", "value": "FAQ: {question}"}
        version.save()
        first = self.start("one")
        self.work(first, Run.Status.SUCCEEDED)
        self.assertEqual(first.result["answer"], "FAQ: one")
        second = self.start("two", session_id=str(first.session_id))
        self.work(second, Run.Status.SUCCEEDED)
        self.assertEqual(second.result["answer"], "FAQ: two")
        self.assertEqual(ChatRecord.objects.filter(chat_id=first.session_id).count(), 2)

    def test_loop_form_continues_at_waiting_iteration(self):
        form = node("approval", "form-node", form_field_list=[], form_content_format="{{form}}")
        body = {
            "nodes": [node("loop-start-node", "loop-start-node"), form, reply("iteration", "done")],
            "edges": [edge("loop-start-node", "approval"), edge("approval", "iteration")],
        }
        self.publish(
            graph(
                [node("loop", "loop-node", loop_type="NUMBER", number=2, loop_body=body)], [edge("start-node", "loop")]
            )
        )
        run = self.start()
        previous_form = None
        for i in range(2):
            self.work(run, Run.Status.WAITING)
            self.assertIn(i, run.result["waiting_step"])
            if previous_form:
                response = self.http.post(f"/v1/runs/{run.pk}/resume", previous_form, format="json")
                self.assertEqual(response.status_code, 409)
                response = self.http.post(f"/v1/runs/{run.pk}/resume", {"node_data": {}}, format="json")
                self.assertEqual(response.status_code, 409)
            previous_form = {"node_data": {"ok": True}, "waiting_event_id": run.result["waiting_event_id"]}
            self.assertEqual(previous_form["waiting_event_id"], run.event_sequence)
            response = self.http.post(f"/v1/runs/{run.pk}/resume", previous_form, format="json")
            self.assertEqual(response.status_code, 202, response.content)
        self.work(run, Run.Status.SUCCEEDED)
        self.assertEqual(set(run.steps.filter(node_id="iteration").values_list("iteration", flat=True)), {0, 1})

    def test_product_document_to_published_rag_answer(self):
        from knowledge.models import Document, KnowledgeFolder
        from knowledge.task.embedding import embedding_by_document
        from models_provider.models import Model

        workspace = self.project.workspace_id
        KnowledgeFolder.objects.create(id=workspace, name=workspace, workspace_id=workspace)
        embedding = Model.objects.create(
            name="vectors",
            model_type="EMBEDDING",
            model_name="fixture",
            provider="test",
            credential="unused",
            workspace_id=workspace,
        )
        self.project.models.add(embedding)
        kb = self.http.post(
            "/v1/knowledge-bases", {"name": "FAQ", "embedding_model_id": str(embedding.pk)}, format="json"
        )
        self.assertEqual(kb.status_code, 201, kb.content)
        kb_id = kb.json()["id"]
        with patch("litekb_api.index_tasks.embedding_by_document.delay"):
            doc = self.http.post(
                f"/v1/knowledge-bases/{kb_id}/documents",
                {"name": "Support", "content": "A warranty lasts two years."},
                format="json",
            )
        self.assertEqual(doc.status_code, 201, doc.content)
        doc_id = doc.json()["documents"][0]["id"]
        Document.objects.filter(pk=doc_id).update(hit_handling_method="directly_return", directly_return_similarity=0.8)
        vector_model = Mock()
        vector_model.embed_documents.side_effect = lambda texts: [[1.0, 0.0] for _ in texts]
        vector_model.embed_query.return_value = [1.0, 0.0]
        with patch("knowledge.task.embedding.get_embedding_model", return_value=vector_model):
            embedding_by_document.run(doc_id, str(embedding.pk))
        version = self.publish({})
        version.type, version.knowledge_ids = "SIMPLE", [kb_id]
        version.save()
        with patch(
            "application.chat_pipeline.step.search_dataset_step.impl.base_search_dataset_step.get_model",
            return_value=vector_model,
        ):
            run = self.start("How long is the warranty?")
            self.work(run, Run.Status.SUCCEEDED)
        self.assertIn("two years", run.result["answer"])
        (source,) = run.result["sources"]
        self.assertEqual((source["knowledge_base_id"], source["document_id"]), (kb_id, doc_id))
        self.assertEqual(
            self.http.get(
                f"/v1/knowledge-bases/{kb_id}/documents/{doc_id}/paragraphs/" + source["paragraph_id"]
            ).status_code,
            200,
        )

    def test_subagent_scope_and_mcp_output_reference(self):
        child = Application.objects.create(
            name="Child",
            user=self.owner,
            folder=self.agent.folder,
            workspace_id=self.project.workspace_id,
            type="WORK_FLOW",
            is_publish=True,
        )
        mcp = node(
            "lookup",
            "mcp-node",
            mcp_servers='{"local":{"transport":"streamable_http","url":"https://example.com/mcp"}}',
            mcp_server="local",
            mcp_tool="lookup",
            mcp_source="custom",
            mcp_tool_id=None,
            tool_params={},
        )
        answer = node(
            "child-output", "reply-node", reply_type="referencing", fields=["lookup", "result"], is_result=True
        )
        ApplicationVersion.objects.create(
            application=child,
            user=self.owner,
            type="WORK_FLOW",
            application_name="Child",
            workspace_id=self.project.workspace_id,
            work_flow=graph([mcp, answer], [edge("start-node", "lookup"), edge("lookup", "child-output")]),
        )
        embed = node(
            "invoke",
            "application-node",
            application_id=str(child.pk),
            question_reference_address=["start-node", "question"],
            is_result=True,
        )
        self.publish(graph([embed], [edge("start-node", "invoke")]))
        backend_module = "application.flow.step_node.mcp_node.impl.base_mcp_node"
        with patch(backend_module + ".SandboxMCPBackend") as backend:
            transport = AsyncMock(return_value=SimpleNamespace(content=[SimpleNamespace(text="fixture-result")]))
            backend.return_value.call_tool = transport
            denied = self.start()
            self.work(denied, Run.Status.FAILED)
            transport.assert_not_called()
            self.project.applications.add(child)
            allowed = self.start()
            self.work(allowed, Run.Status.SUCCEEDED)
            transport.assert_awaited_once()
            self.assertIn("fixture-result", allowed.result["answer"])
            step = allowed.steps.get(node_id="lookup")
            self.assertIn("chat_record", step.execution_path)
            self.assertNotEqual(step.output_ref["chat_record_id"], str(allowed.chat_record_id))
            transport.side_effect = ValueError("MCP fixture failure")
            broken = self.start()
            self.work(broken, Run.Status.FAILED)
            self.assertEqual(broken.error, "tool_outcome_unknown")
            self.assertEqual(broken.events.filter(kind="tool.dispatched").count(), 1)
            self.work(broken, Run.Status.FAILED)
            self.assertEqual(transport.await_count, 2)

    def test_expired_lease_cannot_repeat_an_external_write_or_commit_results(self):
        from .run_guard import admit_effect, fenced_write, worker_scope
        from .run_lease import claim, maintain_runs, renew
        from .run_service import finish, save_event

        self.publish(graph([reply("done", "ok")], [edge("start-node", "done")]))
        run = self.start()
        owner = claim(run.pk, run.event_sequence).lease_owner
        write = Mock()
        with worker_scope(run.pk, owner, lambda: False):
            admit_effect("node", "issue-refund")
            write()
            Run.objects.filter(pk=run.pk).update(lease_expires_at=timezone.now() - timedelta(seconds=1))
            maintain_runs()
            self.assertFalse(renew(run.pk, owner))
            with self.assertRaises(RuntimeError):
                admit_effect("node", "issue-refund")
                write()
            fenced_write(write)()
        save_event(run.pk, owner, "answer.delta", {"text": "late"})
        finish(run.pk, owner, None, False, [])
        self.work(run, Run.Status.FAILED)
        write.assert_called_once()
        self.assertEqual(run.error, "worker_lost")
        self.assertFalse(run.events.filter(kind="answer.delta").exists())
        self.assertEqual(run.events.filter(kind="run.failed").count(), 1)
        self.assertEqual(self.http.post(f"/v1/runs/{run.pk}/resume", {"node_data": {}}, format="json").status_code, 409)

    def test_blocked_tool_is_fenced_on_cancel_and_timeout(self):
        import time
        from application.models import ChatRecord

        mcp = node(
            "write",
            "mcp-node",
            mcp_servers='{"example":{"transport":"streamable_http","url":"https://example.com/mcp"}}',
            mcp_server="example",
            mcp_tool="write",
            mcp_source="custom",
            mcp_tool_id=None,
            tool_params={},
        )
        self.publish(graph([mcp, reply("after", "late")], [edge("start-node", "write"), edge("write", "after")]))
        for stop in ("cancel", "timeout"):
            entered, release = Event(), Event()

            async def blocking(*args):
                entered.set()
                if not release.wait(15):
                    raise AssertionError("test did not release the tool")
                return SimpleNamespace(content=[SimpleNamespace(text="committed")])

            def worker(pk):
                try:
                    execute_run.run(str(pk))
                finally:
                    connections.close_all()

            with (
                self.subTest(stop=stop),
                patch("application.flow.step_node.mcp_node.impl.base_mcp_node.SandboxMCPBackend") as backend,
                ThreadPoolExecutor(max_workers=1) as executor,
            ):
                backend.return_value.call_tool = AsyncMock(side_effect=blocking)
                run = self.start(max_runtime_seconds=3 if stop == "timeout" else 60)
                url = f"/v1/runs/{run.pk}"
                future = executor.submit(worker, run.pk)
                try:
                    self.assertTrue(entered.wait(10))
                    if stop == "cancel":
                        self.assertEqual(self.http.post(url + "/cancel").json()["status"], "cancelled")
                    else:
                        until = time.monotonic() + 6
                        while time.monotonic() < until:
                            run.refresh_from_db()
                            if run.status == Run.Status.FAILED:
                                break
                            time.sleep(0.05)
                        self.assertEqual(run.error, "timeout")
                        self.assertEqual(run.budget["used_runtime_seconds"], 3)
                    self.assertFalse(future.done())
                    before = self.http.get(url).json()["event_sequence"]
                finally:
                    release.set()
                future.result(timeout=10)
                run.refresh_from_db()
                self.assertEqual(run.event_sequence, before)
                execute_run.run(str(run.pk))
                backend.return_value.call_tool.assert_awaited_once()
                self.assertFalse(ChatRecord.objects.filter(chat_id=run.session_id).exists())

    def test_stale_queue_delivery_and_duplicate_model_tool_admission(self):
        from asgiref.sync import async_to_sync
        from .run_guard import intercept_mcp, worker_scope
        from .run_lease import claim, maintain_runs

        self.publish(graph([reply("done", "ok")], [edge("start-node", "done")]))
        run = self.start()
        Run.objects.filter(pk=run.pk).update(updated_at=timezone.now() - timedelta(minutes=2))
        maintain_runs()
        self.dispatch.assert_called_with(run.pk, run.event_sequence)
        self.assertIsNone(claim(run.pk, run.event_sequence + 100))
        owner = claim(run.pk, run.event_sequence).lease_owner
        call = SimpleNamespace(server_name="store", name="charge", args={"order": "test"})
        transport = AsyncMock(return_value=SimpleNamespace(isError=False))
        with worker_scope(run.pk, owner, lambda: False):
            async_to_sync(intercept_mcp)(call, transport)
            with self.assertRaises(RuntimeError):
                async_to_sync(intercept_mcp)(call, transport)
        transport.assert_awaited_once()
        run.refresh_from_db()
        self.assertEqual(run.error, "effect_already_dispatched")
        import asyncio

        disconnected = self.start()
        token = claim(disconnected.pk, disconnected.event_sequence).lease_owner
        transport = AsyncMock(side_effect=asyncio.CancelledError())
        with worker_scope(disconnected.pk, token, lambda: False):
            with self.assertRaises(asyncio.CancelledError):
                async_to_sync(intercept_mcp)(call, transport)
            with self.assertRaises(RuntimeError):
                async_to_sync(intercept_mcp)(call, transport)
        transport.assert_awaited_once()
        disconnected.refresh_from_db()
        self.assertEqual(disconnected.error, "tool_outcome_unknown")

    def test_nested_workflow_tool_writes_once_per_loop_iteration_across_forms(self):
        from tools.models import Tool, ToolFolder, ToolWorkflowVersion

        workspace = self.project.workspace_id
        folder = ToolFolder.objects.create(id=workspace, name="Tools", workspace_id=workspace)
        tool = Tool.objects.create(
            name="order-tool", tool_type="WORKFLOW", user=self.owner, workspace_id=workspace, folder=folder
        )
        write = node(
            "write",
            "mcp-node",
            mcp_servers='{"orders":{"transport":"streamable_http","url":"https://example.com/mcp"}}',
            mcp_server="orders",
            mcp_tool="submit",
            mcp_source="custom",
            mcp_tool_id=None,
            tool_params={},
        )
        form = node("approve", "form-node", form_field_list=[], form_content_format="{{form}}")
        ToolWorkflowVersion.objects.create(
            tool=tool,
            workspace_id=workspace,
            work_flow={
                "nodes": [
                    node("tool-base-node", "tool-base-node"),
                    node("tool-start-node", "tool-start-node"),
                    write,
                    form,
                    reply("receipt", "saved"),
                ],
                "edges": [edge("tool-start-node", "write"), edge("write", "approve"), edge("approve", "receipt")],
            },
        )
        body = {
            "nodes": [
                node("loop-start-node", "loop-start-node"),
                node("order", "tool-workflow-lib-node", tool_lib_id=str(tool.pk), input_field_list=[], is_result=True),
            ],
            "edges": [edge("loop-start-node", "order")],
        }
        self.publish(
            graph(
                [node("loop", "loop-node", loop_type="NUMBER", number=2, loop_body=body)], [edge("start-node", "loop")]
            )
        )
        run = self.start()
        initial_queue = run.event_sequence
        with patch("application.flow.step_node.mcp_node.impl.base_mcp_node.SandboxMCPBackend") as backend:
            dispatch = AsyncMock(return_value=SimpleNamespace(content=[SimpleNamespace(text="saved")]))
            backend.return_value.call_tool = dispatch
            for i in range(2):
                self.work(run, Run.Status.WAITING)
                self.assertEqual(dispatch.await_count, i + 1)
                response = self.http.post(
                    f"/v1/runs/{run.pk}/resume",
                    {"node_data": {"ok": True}, "waiting_event_id": run.event_sequence},
                    format="json",
                )
                self.assertEqual(response.status_code, 202, response.content)
                execute_run.run(str(run.pk), initial_queue)
                run.refresh_from_db()
                self.assertEqual(run.status, Run.Status.QUEUED)
            self.work(run, Run.Status.SUCCEEDED)
            self.assertEqual(dispatch.await_count, 2)
        receipts = list(run.events.filter(kind="tool.dispatched").values_list("data", flat=True))
        self.assertEqual(len(receipts), 2)
        self.assertNotEqual(receipts[0]["execution_path"], receipts[1]["execution_path"])
        self.assertEqual(set(run.steps.filter(node_id="write").values_list("iteration", flat=True)), {0, 1})

    def test_sse_reconnect_across_database_pages(self):
        from django.db import transaction
        from .run_lease import transition
        from .runs import RunEvent

        self.publish(graph([reply("done", "ok")], [edge("start-node", "done")]))
        run = self.start()
        with transaction.atomic():
            run = Run.objects.select_for_update().get(pk=run.pk)
            RunEvent.objects.bulk_create(
                [RunEvent(run=run, sequence=i, kind="answer.delta", data={"text": str(i)}) for i in range(2, 405)]
            )
            run.event_sequence = 404
            transition(run, Run.Status.SUCCEEDED)
        url = f"/v1/runs/{run.pk}/events"
        stream = self.http.get(url, HTTP_LAST_EVENT_ID="2", HTTP_ACCEPT="text/event-stream")
        self.assertEqual(stream.status_code, 200)
        self.assertEqual(stream["Content-Type"], "text/event-stream")
        invalid = self.http.get(url, {"after": 406}, HTTP_ACCEPT="text/event-stream")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid["Content-Type"], "application/json")
        connection = iter(stream.streaming_content)
        first = next(connection).decode()
        stream.close()
        self.assertTrue(first.startswith("id: 3\n"))
        replay = self.http.get(url, HTTP_LAST_EVENT_ID="3")
        body = b"".join(replay.streaming_content).decode()
        self.assertEqual([int(line[4:]) for line in body.splitlines() if line.startswith("id: ")], list(range(4, 406)))
        self.assertEqual(b"".join(self.http.get(url, {"after": 405}).streaming_content), b"")

    def test_broker_disconnect_between_publish_and_ack(self):
        from .run_lease import maintain_runs

        self.publish(graph([reply("done", "ok")], [edge("start-node", "done")]))
        run = self.start()
        queued_sequence = run.event_sequence
        with patch.object(execute_run, "delay", side_effect=ConnectionError("lost broker ack")):
            enqueue(run.pk, queued_sequence)
        run.refresh_from_db()
        self.assertEqual(run.status, Run.Status.QUEUED)
        Run.objects.filter(pk=run.pk).update(updated_at=timezone.now() - timedelta(minutes=2))
        maintain_runs()
        self.dispatch.assert_called_with(run.pk, queued_sequence)
        for _ in range(2):
            execute_run.run(str(run.pk), queued_sequence)
        run.refresh_from_db()
        self.assertEqual(run.result["answer"], "ok")
        self.assertEqual(run.events.filter(kind="run.running").count(), 1)

    def test_process_killed_after_external_write(self):
        import json
        import os
        from pathlib import Path
        import subprocess
        import sys
        import tempfile
        import time
        from .run_lease import maintain_runs

        self.publish(graph([reply("done", "ok")], [edge("start-node", "done")]))
        run = self.start()
        # Execute a real DB claim and a single observable external write in a killable child.
        child = """
import json, sys
from pathlib import Path
sys.path[:] = json.loads(sys.argv[1])
from django.conf import settings
settings.DATABASES['default']['NAME'] = sys.argv[2]
import django
django.setup()
from litekb_api.run_lease import claim
from litekb_api.run_guard import admit_effect, worker_scope
run = claim(sys.argv[3], int(sys.argv[4]))
with worker_scope(run.pk, run.lease_owner, lambda: False):
    admit_effect('node', 'write-receipt')
    with Path(sys.argv[5]).open('a', encoding='utf-8') as target:
        target.write('sent\\n')
    sys.stdin.readline()
"""
        with tempfile.TemporaryDirectory() as temp:
            receipt = Path(temp, "receipt")
            args = [
                sys.executable,
                "-c",
                child,
                json.dumps(sys.path),
                connections["default"].settings_dict["NAME"],
                str(run.pk),
                str(run.event_sequence),
                str(receipt),
            ]
            with subprocess.Popen(
                args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=os.environ.copy()
            ) as process:
                try:
                    deadline = time.monotonic() + 60
                    while not receipt.exists() and time.monotonic() < deadline and process.poll() is None:
                        time.sleep(0.1)
                finally:
                    process.kill()
                    _, stderr = process.communicate(timeout=10)
                self.assertTrue(receipt.exists(), stderr.decode(errors="replace")[-2000:])
            self.assertTrue(run.events.filter(kind="tool.dispatched").exists())
            Run.objects.filter(pk=run.pk).update(lease_expires_at=timezone.now() - timedelta(seconds=1))
            maintain_runs()
            with patch("litekb_api.tasks.execute") as engine:
                self.work(run, Run.Status.FAILED)
                engine.assert_not_called()
            self.assertEqual(run.error, "worker_lost")
            self.assertEqual(receipt.read_text(encoding="utf-8").splitlines(), ["sent"])

    def test_isolation_idempotency_and_cancellation(self):
        self.publish(graph([reply("done", "ok")], [edge("start-node", "done")]))

        def send(message):
            return self.http.post(self.create_url, {"message": message}, format="json", HTTP_IDEMPOTENCY_KEY="once")

        first = send("hello").json()
        self.assertEqual(send("hello").json()["id"], first["id"])
        self.assertEqual(send("changed").status_code, 409)
        self.assertEqual(self.dispatch.call_count, 1)
        url = "/v1/runs/" + first["id"]
        for _, key, subject in [(None, self.key, "bob"), (*ServiceClient.issue(self.project, "other"), "alice")]:
            self.auth(key, subject)
            self.assertEqual(self.http.get(url).status_code, 404)
            self.assertEqual(self.http.get(url + "/events").status_code, 404)
            self.assertEqual(self.http.post(url + "/cancel").status_code, 404)
            response = self.http.post(
                self.create_url, {"message": "x", "session_id": first["session_id"]}, format="json"
            )
            self.assertEqual(response.status_code, 404)
        self.auth(self.key, "alice")
        self.assertEqual(self.http.post(url + "/cancel").json()["status"], "cancelled")
        self.work(Run.objects.get(pk=first["id"]), Run.Status.CANCELLED)

    def test_exhausted_execution_budget_prevents_another_dispatch_to_engine(self):
        self.publish(graph([reply("done", "ok")], [edge("start-node", "done")]))
        run = self.start(max_runtime_seconds=1)
        Run.objects.filter(pk=run.pk).update(budget={"max_runtime_seconds": 1, "used_runtime_seconds": 1.2})
        with patch("litekb_api.tasks.execute") as engine:
            self.work(run, Run.Status.FAILED)
        engine.assert_not_called()
        self.assertEqual(run.error, "timeout")

    def test_concurrent_idempotent_requests_dispatch_once(self):
        self.publish(graph([reply("done", "ok")], [edge("start-node", "done")]))
        barrier = Barrier(2)

        def submit():
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION="Bearer " + self.key, HTTP_X_LITEKB_SUBJECT="alice")
            try:
                barrier.wait(timeout=10)
                response = client.post(
                    self.create_url, {"message": "once"}, format="json", HTTP_IDEMPOTENCY_KEY="concurrent"
                )
                self.assertEqual(response.status_code, 202, response.content)
                return response.json()["id"]
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            requests = [executor.submit(submit) for _ in range(2)]
            self.assertEqual(requests[0].result(), requests[1].result())
        self.assertEqual(self.dispatch.call_count, 1)

    def test_studio_login_can_read_real_run_and_save_brand(self):
        import secrets
        from common.utils.common import password_encrypt

        password = secrets.token_urlsafe(16)
        self.owner.password = password_encrypt(password)
        self.owner.save(update_fields=["password"])
        self.publish(graph([reply("done", "verified")], [edge("start-node", "done")]))
        run = self.start()
        self.work(run, Run.Status.SUCCEEDED)
        console = APIClient()
        login = console.post(
            "/admin/api/user/login", {"username": self.owner.username, "password": password}, format="json"
        )
        self.assertEqual(login.json()["code"], 200)
        console.credentials(HTTP_AUTHORIZATION="Bearer " + login.json()["data"]["token"])
        detail = console.get(f"/admin/api/litekb/runs/{run.pk}").json()["data"]
        self.assertEqual(detail["result"]["answer"], "verified")
        self.assertEqual(detail["events"][-1]["kind"], "run.succeeded")
        branding = {"name": "QA Studio", "icon": ""}
        self.assertEqual(console.put("/admin/api/branding", branding, format="json").json()["data"], branding)
        self.assertEqual(APIClient().get("/admin/api/branding").json()["data"], branding)
