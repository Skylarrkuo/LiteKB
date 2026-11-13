"""Propagate Run ownership across graph threads, nested graphs and model-selected tools."""

import asyncio
import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from threading import Lock
from typing import Callable
from uuid import UUID

_worker = ContextVar("litekb_worker", default=None)
_path = ContextVar("litekb_node_path", default=())
WRITE_NODES = {
    "mcp-node",
    "tool-node",
    "tool-lib-node",
    "knowledge-write-node",
    "image-generate-node",
    "text-to-video-node",
    "image-to-video-node",
    "text-to-speech-node",
}


@dataclass
class RunWorker:
    run_id: UUID
    owner: UUID
    interrupted: Callable[[], bool]
    memory_updates: set = field(default_factory=set)
    lock: Lock = field(default_factory=Lock)


@contextmanager
def worker_scope(run_id, owner, interrupted):
    worker = RunWorker(run_id, owner, interrupted)
    key = _worker.set(worker)
    try:
        yield worker
    finally:
        _worker.reset(key)


def is_interrupted():
    worker = _worker.get()
    return bool(worker and worker.interrupted())


def in_run():
    return _worker.get() is not None


def defer_memory_update(args):
    worker = _worker.get()
    if not worker:
        return False
    with worker.lock:
        worker.memory_updates.add(args)
    return True


@contextmanager
def node_scope(node):
    if _worker.get() is None:
        yield
        return
    mark = _path.set((*_path.get(), node.runtime_node_id))
    try:
        yield
    finally:
        _path.reset(mark)


def fenced_write(method):
    """Serialize local chat/variable commits with cancellation, expiry and subsequent session turns."""

    @wraps(method)
    def write(*args, **kwargs):
        worker = _worker.get()
        if worker is None:
            return method(*args, **kwargs)
        from .run_lease import locked_owner

        with locked_owner(worker.run_id, worker.owner) as run:
            if run and not worker.interrupted():
                return method(*args, **kwargs)

    return write


def admit_effect(kind, identity, arguments=None):
    """Commit a dispatch receipt before entering code that may already have changed an external system."""
    worker = _worker.get()
    if worker is None:
        return
    from django.utils import timezone
    from .run_lease import end_turn, locked_owner, record_event
    from .runs import Run

    path = _path.get()
    raw = json.dumps([path, kind, identity, arguments], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    key = hashlib.sha256(raw.encode()).hexdigest()
    with locked_owner(worker.run_id, worker.owner) as run:
        if run and not worker.interrupted():
            if not run.events.filter(effect_key=key).exists():
                record_event(
                    run,
                    "tool.dispatched",
                    {"execution_path": list(path), "type": kind, "name": identity},
                    effect_key=key,
                )
                return key
            end_turn(run, Run.Status.FAILED, timezone.now(), error="effect_already_dispatched")
    raise RuntimeError("Tool dispatch is closed for this run.")


@contextmanager
def workflow_tool_scope(tool_id, kwargs):
    key = admit_effect("workflow_tool", str(tool_id), kwargs)
    if key is None:
        yield
        return
    mark = _path.set((*_path.get(), key))
    try:
        yield
    except Exception:
        uncertain_effect()
        raise
    finally:
        _path.reset(mark)


def uncertain_effect():
    worker = _worker.get()
    if worker is not None:
        from .run_lease import fail

        fail(worker.run_id, worker.owner, "tool_outcome_unknown")


async def intercept_mcp(request, handler):
    worker = _worker.get()
    if worker is None:
        return await handler(request)
    from asgiref.sync import sync_to_async

    await sync_to_async(admit_effect)("mcp", [request.server_name, request.name], request.args)
    try:
        result = await handler(request)
    except (Exception, asyncio.CancelledError):
        await sync_to_async(uncertain_effect)()
        raise
    if getattr(result, "isError", False):
        await sync_to_async(uncertain_effect)()
    return result
