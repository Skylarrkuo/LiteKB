"""Serialize admission, ownership and the cumulative active-time budget on the Run row."""

import uuid
from contextlib import contextmanager
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .runs import Run, RunEvent

LEASE_SECONDS = 30
RENEW_SECONDS = 5
REDISPATCH_SECONDS = 60


def record_event(run, kind, data, *, effect_key=None):
    """Caller owns the row lock or just inserted the Run in its transaction."""
    run.event_sequence += 1
    run.save(update_fields=["event_sequence", "updated_at"])
    RunEvent.objects.create(run=run, sequence=run.event_sequence, kind=kind, data=data, effect_key=effect_key)


def transition(run, status, **fields):
    run.status = status
    for key, value in fields.items():
        setattr(run, key, value)
    run.save(update_fields=["status", *fields, "updated_at"])
    data = {"status": status}
    if run.error:
        data["error"] = run.error
    record_event(run, "run." + status, data)


def end_turn(run, status, at, **fields):
    budget = dict(run.budget)
    if run.active_since:
        elapsed = max(0, (at - run.active_since).total_seconds())
        budget["used_runtime_seconds"] = min(
            budget["max_runtime_seconds"], budget.get("used_runtime_seconds", 0) + elapsed
        )
    transition(
        run,
        status,
        budget=budget,
        lease_owner=None,
        active_since=None,
        deadline_at=None,
        lease_expires_at=None,
        **fields,
    )


def reconcile(run, now):
    """The caller holds the row lock. A lost worker is never allowed to replay a started turn."""
    if run.status != Run.Status.RUNNING:
        return
    if run.cancel_requested:
        end_turn(run, Run.Status.CANCELLED, now)
    elif not run.lease_owner or not run.lease_expires_at or not run.deadline_at:
        end_turn(run, Run.Status.FAILED, now, error="worker_lost")
    else:
        stopped = min(run.deadline_at, run.lease_expires_at)
        if stopped <= now:
            error = "timeout" if stopped == run.deadline_at else "worker_lost"
            end_turn(run, Run.Status.FAILED, stopped, error=error)


def expired(run, now):
    return run.status == Run.Status.RUNNING and (
        run.cancel_requested
        or not run.lease_owner
        or not run.lease_expires_at
        or run.lease_expires_at <= now
        or not run.deadline_at
        or run.deadline_at <= now
    )


def current(run):
    if expired(run, timezone.now()):
        with transaction.atomic():
            run = Run.objects.select_for_update().get(pk=run.pk)
            reconcile(run, timezone.now())
    return run


@contextmanager
def locked_owner(run_id, token):
    with transaction.atomic():
        run = Run.objects.select_for_update().filter(pk=run_id).first()
        if run:
            reconcile(run, timezone.now())
        yield run if run and run.status == Run.Status.RUNNING and token and run.lease_owner == token else None


def claim(run_id, queued_sequence=None):
    with transaction.atomic():
        run = Run.objects.select_for_update().filter(pk=run_id).first()
        if not run:
            return
        now = timezone.now()
        reconcile(run, now)
        if run.status != Run.Status.QUEUED or (queued_sequence is not None and run.event_sequence != queued_sequence):
            return
        remaining = run.budget["max_runtime_seconds"] - run.budget.get("used_runtime_seconds", 0)
        if remaining <= 0:
            transition(run, Run.Status.FAILED, error="timeout")
            return
        transition(
            run,
            Run.Status.RUNNING,
            active_since=now,
            deadline_at=now + timedelta(seconds=remaining),
            lease_owner=uuid.uuid4(),
            lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
        )
        return run


def renew(run_id, token):
    with locked_owner(run_id, token) as run:
        if run:
            run.lease_expires_at = timezone.now() + timedelta(seconds=LEASE_SECONDS)
            run.save(update_fields=["lease_expires_at"])
            return True
    return False


def fail(run_id, token, error):
    with locked_owner(run_id, token) as run:
        if run:
            end_turn(run, Run.Status.FAILED, timezone.now(), error=error)
            return True
    return False


def maintain_runs():
    from .run_service import enqueue

    now = timezone.now()
    stale = Q(lease_expires_at__lte=now) | Q(deadline_at__lte=now) | Q(lease_owner=None) | Q(cancel_requested=True)
    stale_queued = Q(status=Run.Status.QUEUED, updated_at__lte=now - timedelta(seconds=REDISPATCH_SECONDS))
    with transaction.atomic():
        candidates = Run.objects.filter(Q(status=Run.Status.RUNNING) & stale | stale_queued)
        for run in candidates.order_by("updated_at").select_for_update(skip_locked=True)[:100]:
            if run.status == Run.Status.QUEUED:
                run.save(update_fields=["updated_at"])
                transaction.on_commit(lambda pk=run.pk, seq=run.event_sequence: enqueue(pk, seq))
            else:
                reconcile(run, timezone.now())
