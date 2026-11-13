import logging
import threading
import time

from celery.signals import worker_ready, worker_shutdown
from django.db import connections, close_old_connections
from django.utils import timezone
from ops import celery_app

from .index_tasks import retry_document_index  # noqa: F401 (Celery autodiscovery)
from .run_guard import worker_scope
from .run_lease import RENEW_SECONDS, claim, fail, maintain_runs, renew
from .run_policy import project_scope
from .run_service import execute, finish
from .runs import Run

log = logging.getLogger(__name__)


def _keep_lease(run_id, token, deadline, stopped):
    try:
        while not stopped.wait(min(RENEW_SECONDS, max(0, deadline - time.monotonic()))):
            if not renew(run_id, token):
                break
    except Exception:
        log.exception("LiteKB run %s lost its lease connection", run_id)
    finally:
        stopped.set()
        connections.close_all()


@celery_app.task(name="litekb.execute_run", ignore_result=True, acks_late=True, reject_on_worker_lost=True)
def execute_run(run_id, queued_sequence=None):
    run = claim(run_id, queued_sequence)
    if not run:
        return
    token = run.lease_owner
    deadline = time.monotonic() + (run.deadline_at - timezone.now()).total_seconds()
    stopped = threading.Event()

    def interrupted():
        return stopped.is_set() or time.monotonic() >= deadline

    watch = threading.Thread(target=_keep_lease, args=(run.pk, token, deadline, stopped), daemon=True)
    watch.start()
    try:
        with worker_scope(run.pk, token, interrupted) as worker, project_scope(run.client.project):
            record, failed, forms = execute(run, interrupted)
        if stopped.is_set():
            fail(run_id, token, "worker_lost")
        elif finish(run_id, token, record, failed, forms) == Run.Status.SUCCEEDED:
            from application.long_term_memory import extract_long_term_memory

            for args in worker.memory_updates:
                try:
                    extract_long_term_memory.apply_async(args=args, countdown=1)
                except Exception:
                    log.exception("Could not dispatch post-run memory update for %s", run_id)
    except Exception:
        if fail(run_id, token, "execution_failed"):
            log.exception("LiteKB run %s failed", run_id)
    finally:
        stopped.set()
        watch.join(timeout=1)


_shutdown = threading.Event()


def _maintain():
    try:
        while not _shutdown.is_set():
            try:
                close_old_connections()
                maintain_runs()
            except Exception:
                log.exception("LiteKB worker could not reconcile runs")
            _shutdown.wait(10)
    finally:
        connections.close_all()


@worker_ready.connect
def recover_runs_on_start(**kwargs):
    _shutdown.clear()
    threading.Thread(target=_maintain, name="litekb-run-recovery", daemon=True).start()


@worker_shutdown.connect
def stop_run_recovery(**kwargs):
    _shutdown.set()
