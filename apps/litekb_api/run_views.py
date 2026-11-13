import time

from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from common.auth import TokenAuth
from common.auth.authentication import get_is_permissions
from common.constants.permission_constants import RoleConstants
from common.result import result

from .auth import ServiceAPIView
from .inputs import Input
from .pagination import page
from .runs import Run
from .run_lease import current, end_turn, reconcile, record_event, transition
from .run_service import Conflict, TERMINAL, create_run, enqueue
from .run_trace import sse_frame


class RunInput(Input):
    message = serializers.CharField(max_length=10240)
    session_id = serializers.UUIDField(required=False)
    form_data = serializers.DictField(required=False)
    max_runtime_seconds = serializers.IntegerField(default=300, min_value=1, max_value=3600)


class ResumeInput(Input):
    node_data = serializers.DictField()
    waiting_event_id = serializers.IntegerField(min_value=1, required=False)


def subject_for(request):
    value = request.headers.get("X-LiteKB-Subject", "").strip()
    if not value or len(value) > 160:
        raise ValidationError("Supply X-LiteKB-Subject (1–160 characters).")
    return value


def owned_runs(request):
    return Run.objects.filter(
        client=request.auth,
        subject=subject_for(request),
        version__application__in=request.auth.project.applications.all(),
    )


def representation(run, detail=False):
    run = current(run)
    data = {
        "id": str(run.id),
        "agent_id": str(run.version.application_id),
        "version_id": str(run.version_id),
        "client_id": str(run.client_id),
        "subject": run.subject,
        "session_id": str(run.session_id),
        "chat_record_id": str(run.chat_record_id) if run.chat_record_id else None,
        "status": run.status,
        "event_sequence": run.event_sequence,
        "budget": run.budget,
        "cancel_requested": run.cancel_requested,
        "error": run.error,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }
    if detail:
        data.update(
            result=run.result,
            steps=list(
                run.steps.values(
                    "node_id",
                    "node_type",
                    "execution_path",
                    "iteration",
                    "status",
                    "attempt",
                    "elapsed_seconds",
                    "output_ref",
                )
            ),
        )
    return data


class Agents(ServiceAPIView):
    def get(self, request):
        from application.models import ApplicationVersion

        project = request.auth.project
        versions = (
            ApplicationVersion.objects.filter(
                application__in=project.applications.all(),
                workspace_id=project.workspace_id,
                application__workspace_id=project.workspace_id,
            )
            .order_by("application_id", "-create_time", "-pk")
            .distinct("application_id")
        )
        return page(
            request,
            versions,
            lambda v: {"id": v.application_id, "version_id": v.pk, "name": v.application_name, "type": v.type},
        )


class AgentRuns(ServiceAPIView):
    def get(self, request, agent_id):
        get_object_or_404(
            request.auth.project.applications, pk=agent_id, workspace_id=request.auth.project.workspace_id
        )
        runs = owned_runs(request).filter(version__application_id=agent_id).select_related("version")
        if request.query_params.get("session_id"):
            session = serializers.UUIDField().run_validation(request.query_params["session_id"])
            runs = runs.filter(session_id=session)
        return page(request, runs, representation)

    def post(self, request, agent_id):
        params = RunInput(data=request.data)
        params.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key")
        if key is not None and not 1 <= len(key) <= 128:
            raise ValidationError("Invalid Idempotency-Key.")
        run = create_run(request.auth, subject_for(request), agent_id, params.validated_data, key)
        run.refresh_from_db()
        return Response(representation(run), status=202, headers={"Location": f"/v1/runs/{run.pk}"})


class RunDetail(ServiceAPIView):
    def get(self, request, run_id):
        run = get_object_or_404(owned_runs(request).select_related("version"), pk=run_id)
        return Response(representation(run, detail=True))


class CancelRun(ServiceAPIView):
    @transaction.atomic
    def post(self, request, run_id):
        run = get_object_or_404(owned_runs(request).select_for_update(of=("self",)), pk=run_id)
        reconcile(run, timezone.now())
        if run.status in (Run.Status.QUEUED, Run.Status.WAITING):
            transition(run, Run.Status.CANCELLED, cancel_requested=True)
        elif run.status == Run.Status.RUNNING and not run.cancel_requested:
            record_event(run, "run.cancel_requested", {})
            end_turn(run, Run.Status.CANCELLED, timezone.now(), cancel_requested=True)
        return Response(representation(run))


class ResumeRun(ServiceAPIView):
    @transaction.atomic
    def post(self, request, run_id):
        run = get_object_or_404(owned_runs(request).select_for_update(of=("self",)), pk=run_id)
        if run.status != Run.Status.WAITING:
            raise Conflict("This run is not waiting for input.")
        params = ResumeInput(data=request.data)
        params.is_valid(raise_exception=True)
        form = params.validated_data["node_data"]
        waiting_event = params.validated_data.get("waiting_event_id")
        if waiting_event != run.event_sequence and (waiting_event is not None or "node_data" in run.inputs):
            raise Conflict("Supply the current form's waiting_event_id.")
        reference = run.result["resume"]
        run.inputs = {**run.inputs, **reference, "chat_record_id": str(run.chat_record_id), "node_data": form}
        transition(run, Run.Status.QUEUED, inputs=run.inputs, result={})
        transaction.on_commit(lambda: enqueue(run.pk, run.event_sequence))
        return Response(representation(run), status=202)


def stream_events(query, run_id, cursor):
    # Release the HTTP worker periodically. EventSource reconnects using Last-Event-ID.
    until = time.monotonic() + 60
    last_output = time.monotonic()
    delay = 0.1
    while time.monotonic() < until:
        run = query.filter(pk=run_id, client__is_active=True, client__project__owner__is_active=True).first()
        if run is None:
            return
        run = current(run)
        events = list(
            run.events.filter(sequence__gt=cursor, sequence__lte=run.event_sequence).values("sequence", "kind", "data")[
                :200
            ]
        )
        for event in events:
            yield sse_frame(event)
            cursor = event["sequence"]
        if events:
            last_output = time.monotonic()
            delay = 0.1
        if cursor >= run.event_sequence and (run.status in TERMINAL or run.status == Run.Status.WAITING):
            return
        if len(events) == 200:
            continue
        if time.monotonic() - last_output >= 10:
            yield ": heartbeat\n\n"
            last_output = time.monotonic()
        time.sleep(delay)
        delay = min(0.5, delay * 1.5)


class EventStreamRenderer(JSONRenderer):
    # A successful stream bypasses DRF rendering. Negotiated error/metadata
    # responses still contain a JSON document (authentication, cursor validation).
    media_type = "text/event-stream"
    format = "event-stream"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context["response"]["Content-Type"] = "application/json"
        return super().render(data, "application/json", renderer_context)


class RunEvents(ServiceAPIView):
    renderer_classes = [JSONRenderer, EventStreamRenderer]

    def get(self, request, run_id):
        query = owned_runs(request)
        run = current(get_object_or_404(query, pk=run_id))
        cursor = serializers.IntegerField(min_value=0, max_value=run.event_sequence).run_validation(
            request.headers.get("Last-Event-ID", request.query_params.get("after", 0))
        )
        return StreamingHttpResponse(
            stream_events(query, run.pk, cursor),
            content_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )


class AdminRuns(APIView):
    authentication_classes = [TokenAuth]

    def get(self, request, run_id=None):
        if not get_is_permissions(request)(RoleConstants.ADMIN):
            raise PermissionDenied()
        query = Run.objects.select_related("version")
        if run_id:
            run = get_object_or_404(query, pk=run_id)
            data = representation(run, detail=True)
            data["events"] = list(
                reversed(list(run.events.order_by("-sequence").values("sequence", "kind", "data", "created_at")[:200]))
            )
            return result.success(data)
        page = serializers.IntegerField(min_value=1).run_validation(request.query_params.get("page", 1))
        size = serializers.IntegerField(min_value=1, max_value=100).run_validation(
            request.query_params.get("page_size", 20)
        )
        offset = (page - 1) * size
        return result.success(
            {"total": query.count(), "items": [representation(r) for r in query[offset : offset + size]]}
        )
