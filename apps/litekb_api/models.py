import hashlib
import secrets
import uuid

from django.db import models


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=128)
    workspace_id = models.CharField(max_length=64, default="default")
    owner = models.ForeignKey("users.User", on_delete=models.PROTECT)
    applications = models.ManyToManyField("application.Application", blank=True)
    models = models.ManyToManyField("models_provider.Model", blank=True)


class ProjectKnowledge(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="knowledge_grants")
    knowledge = models.OneToOneField("knowledge.Knowledge", on_delete=models.CASCADE, related_name="project_grant")


class ServiceClient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="clients")
    name = models.CharField(max_length=128)
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def digest(key):
        return hashlib.sha256(key.encode("ascii")).hexdigest()

    @classmethod
    def issue(cls, project, name):
        key = "lk_" + secrets.token_urlsafe(32)
        return cls.objects.create(project=project, name=name, key_hash=cls.digest(key)), key


from .runs import Run, RunEvent, RunStep  # noqa: E402,F401
