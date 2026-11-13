import hashlib
import json
import logging
import time
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied

from .runs import Run, RunEvent, RunStep
from .run_lease import current, end_turn, locked_owner, record_event
from .run_trace import record_steps

log = logging.getLogger(__name__)
TERMINAL = {Run.Status.SUCCEEDED, Run.Status.FAILED, Run.Status.CANCELLED}


class Conflict(APIException):
    status_code = 409


def enqueue(run_id, queued_sequence):
    from .tasks import execute_run

    try:
        execute_run.delay(str(run_id), queued_sequence)
    except Exception:
        # Broker reception is ambiguous on disconnect. Re-publish the same queue
        # generation on the recovery scan. Only a database claim starts execution.
        log.exception("Broker publication deferred for LiteKB run %s", run_id)


def replay(client, subject, key, digest):
    existing = Run.objects.filter(client=client, subject=subject, request_key=key).first() if key else None
    if existing and existing.request_hash != digest:
        raise Conflict("Idempotency-Key was already used for a different request.")
    return existing


def create_run(client, subject, agent_id, data, key):
    from application.models import ApplicationVersion

    if not client.project.applications.filter(pk=agent_id, workspace_id=client.project.workspace_id).exists():
        raise NotFound()
    digest = hashlib.sha256(
        json.dumps([str(agent_id), data], sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()
    prior = replay(client, subject, key, digest)
    if prior:
        return current(prior)
    version = (
        ApplicationVersion.objects.filter(application_id=agent_id, workspace_id=client.project.workspace_id)
        .order_by("-create_time", "-pk")
        .first()
    )
    if not version:
        raise Conflict("Publish the agent before starting a run.")
    session_id = data.get("session_id")
    if (
        session_id
        and not Run.objects.filter(
            client=client, subject=subject, session_id=session_id, version__application_id=agent_id
        ).exists()
    ):
        raise NotFound()
    if session_id:
        active = Run.objects.filter(session_id=session_id, status=Run.Status.RUNNING).first()
        if active:
            current(active)
    try:
        with transaction.atomic():
            run = Run.objects.create(
                client=client,
                subject=subject,
                session_id=session_id or uuid.uuid4(),
                version=version,
                inputs={"message": data["message"], "form_data": data.get("form_data", {})},
                budget={"max_runtime_seconds": data.get("max_runtime_seconds", 300)},
                request_key=key,
                request_hash=digest,
            )
            record_event(run, "run.queued", {"status": run.status})
            transaction.on_commit(lambda: enqueue(run.pk, run.event_sequence))
    except IntegrityError:
        prior = replay(client, subject, key, digest)
        if prior:
            return prior
        if (
            session_id
            and Run.objects.filter(
                session_id=session_id, status__in=[Run.Status.QUEUED, Run.Status.RUNNING, Run.Status.WAITING]
            ).exists()
        ):
            raise Conflict("Another turn is active in this session.")
        raise
    return run


def save_event(run_id, token, kind, data):
    with locked_owner(run_id, token) as run:
        if run:
            record_event(run, kind, data)


def resume_pointer(steps, forms):
    waiting = [s["execution_path"] for s in steps if s["status"] == "waiting_input"]
    for pointer in forms:
        leaf = pointer
        while (leaf.get("child_node") or {}).get("runtime_node_id"):
            leaf = leaf["child_node"]
        for path in waiting:
            if path[0] == pointer["runtime_node_id"] and path[-1] == leaf["runtime_node_id"]:
                return pointer, path
    for path in waiting:
        if len(path) == 1:
            return {"runtime_node_id": path[0], "child_node": {}}, path
    return None, None


def finish(run_id, token, record, failed, forms):
    with locked_owner(run_id, token) as run:
        if not run:
            return
        steps = list(record_steps(record))
        previous = {tuple(s.execution_path): s for s in run.steps.order_by("pk")}
        new_steps = []
        sources = {}
        for step in steps:
            failed |= step.pop("unhandled_error")
            for source in step.pop("sources"):
                sources[source["paragraph_id"]] = source
            path = step["execution_path"]
            old = previous.get(tuple(path))
            if (
                old
                and old.status == step["status"]
                and old.output_ref == step["output_ref"]
                and old.elapsed_seconds == step["elapsed_seconds"]
            ):
                continue
            new_steps.append(RunStep(run=run, **step, attempt=old.attempt + 1 if old else 1))
        RunStep.objects.bulk_create(new_steps)
        events = []
        for step in new_steps:
            run.event_sequence += 1
            events.append(
                RunEvent(
                    run=run,
                    sequence=run.event_sequence,
                    kind="step.finished",
                    data={
                        "node_id": step.node_id,
                        "execution_path": step.execution_path,
                        "iteration": step.iteration,
                        "status": step.status,
                        "elapsed_seconds": step.elapsed_seconds,
                        "attempt": step.attempt,
                    },
                )
            )
        RunEvent.objects.bulk_create(events)
        pointer, pending = resume_pointer(steps, forms)
        result = {
            "answer": record.answer_text,
            "sources": list(sources.values()),
            "usage": {"input_tokens": record.message_tokens, "output_tokens": record.answer_tokens},
        }
        if pending:
            result["waiting_step"] = pending
            result["resume"] = pointer
            result["waiting_event_id"] = run.event_sequence + 1
        status = Run.Status.WAITING if pending else Run.Status.SUCCEEDED
        error = ""
        now = timezone.now()
        if failed or now >= run.deadline_at:
            status, error = Run.Status.FAILED, "timeout" if now >= run.deadline_at else "execution_failed"
        end_turn(run, status, now, result=result, error=error, chat_record=record)
        return status


def execute(run, interrupted):
    from application.models import ChatRecord, ChatUserType
    from application.serializers.common import ChatInfo
    from chat.serializers.chat import ChatSerializers

    client = run.client
    granted = client.project.applications.filter(
        pk=run.version.application_id, workspace_id=client.project.workspace_id
    )
    if not client.is_active or not client.project.owner.is_active or not granted.exists():
        raise PermissionDenied()
    user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"litekb/{client.pk}/{run.subject}"))
    source = {"type": "API_CALL", "run_id": str(run.pk)}
    agent_id = str(run.version.application_id)
    info = ChatInfo(str(run.session_id), user_id, ChatUserType.SYSTEM_API_KEY.value, "", source, [], [], agent_id)
    info.pinned_version = run.version
    info.chat_record_list = list(
        reversed(
            list(
                ChatRecord.objects.filter(chat_id=run.session_id, run__status=Run.Status.SUCCEEDED).order_by(
                    "-create_time"
                )[: max(5, run.version.dialogue_number)]
            )
        )
    )
    if run.chat_record_id:
        info.chat_record_list = [item for item in info.chat_record_list if item.pk != run.chat_record_id]
        info.chat_record_list.append(run.chat_record)
    call = ChatSerializers(
        data={
            "chat_id": str(run.session_id),
            "application_id": agent_id,
            "chat_user_id": user_id,
            "chat_user_type": ChatUserType.SYSTEM_API_KEY.value,
            "source": source,
            "ip_address": "",
        },
        context={"run_chat_info": info, "interrupt": interrupted},
    )
    response = call.chat({**run.inputs, "stream": True, "re_chat": False})
    record_id, failed = None, False
    forms = []
    buffer = ""
    last_write = None
    try:
        for chunk in response.streaming_content:
            for line in chunk.decode().splitlines():
                if not line.startswith("data: "):
                    continue
                frame = json.loads(line[6:])
                record_id = frame.get("chat_record_id") or record_id
                if frame.get("requires_input") and frame.get("runtime_node_id"):
                    pointer = {"runtime_node_id": frame["runtime_node_id"], "child_node": frame.get("child_node") or {}}
                    if pointer not in forms:
                        forms.append(pointer)
                failed |= frame.get("node_status") == "ERROR" or frame.get("status") == 500
                buffer += frame.get("content") or ""
                now = time.monotonic()
                if buffer and (
                    last_write is None or len(buffer) >= 512 or now - last_write >= 0.25 or frame.get("is_end")
                ):
                    save_event(run.pk, run.lease_owner, "answer.delta", {"text": buffer})
                    buffer, last_write = "", now
                if frame.get("node_phase") == "started":
                    save_event(
                        run.pk,
                        run.lease_owner,
                        "step.started",
                        {
                            "node_id": frame.get("node_id"),
                            "runtime_node_id": frame.get("real_node_id") or frame.get("runtime_node_id"),
                        },
                    )
    finally:
        response.close()
    if buffer:
        save_event(run.pk, run.lease_owner, "answer.delta", {"text": buffer})
    return ChatRecord.objects.get(pk=record_id, chat_id=run.session_id), failed, forms
