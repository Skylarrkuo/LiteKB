import uuid

from django.db import models


class Run(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        WAITING = "waiting_input"
        SUCCEEDED = "succeeded"
        FAILED = "failed"
        CANCELLED = "cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey("litekb_api.ServiceClient", on_delete=models.PROTECT)
    subject = models.CharField(max_length=160)
    session_id = models.UUIDField(db_index=True)
    version = models.ForeignKey("application.ApplicationVersion", on_delete=models.CASCADE)
    chat_record = models.ForeignKey("application.ChatRecord", null=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    inputs = models.JSONField(default=dict)
    budget = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    error = models.CharField(max_length=256, blank=True, default="")
    cancel_requested = models.BooleanField(default=False)
    event_sequence = models.PositiveBigIntegerField(default=0)
    lease_owner = models.UUIDField(null=True, editable=False)
    lease_expires_at = models.DateTimeField(null=True, db_index=True)
    active_since = models.DateTimeField(null=True)
    deadline_at = models.DateTimeField(null=True, db_index=True)
    request_key = models.CharField(max_length=128, null=True)
    request_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["client", "subject", "request_key"], name="lk_unique_run_request"),
            models.UniqueConstraint(
                fields=["session_id"],
                condition=models.Q(status__in=["queued", "running", "waiting_input"]),
                name="lk_one_active_turn",
            ),
        ]
        ordering = ["-created_at"]


class RunStep(models.Model):
    run = models.ForeignKey(Run, related_name="steps", on_delete=models.CASCADE)
    node_id = models.TextField()
    node_type = models.CharField(max_length=128)
    execution_path = models.JSONField()
    iteration = models.PositiveIntegerField(null=True)
    status = models.CharField(max_length=20)
    elapsed_seconds = models.FloatField(default=0)
    attempt = models.PositiveIntegerField(default=1)
    output_ref = models.JSONField(default=dict)

    class Meta:
        ordering = ["pk"]


class RunEvent(models.Model):
    run = models.ForeignKey(Run, related_name="events", on_delete=models.CASCADE)
    sequence = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=48)
    effect_key = models.CharField(max_length=64, null=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(fields=["run", "sequence"], name="lk_event_order"),
            models.UniqueConstraint(
                fields=["run", "effect_key"], condition=models.Q(effect_key__isnull=False), name="lk_run_effect_once"
            ),
        ]
