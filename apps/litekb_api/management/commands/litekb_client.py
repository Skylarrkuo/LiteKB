from argparse import ArgumentTypeError
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_slug
from django.core.exceptions import ValidationError
from django.db import transaction

from application.models import Application
from knowledge.models import Knowledge, KnowledgeFolder, KnowledgeType
from models_provider.models import Model
from users.models import User

from litekb_api.models import Project, ProjectKnowledge, ServiceClient


def identifier(value):
    try:
        return UUID(value)
    except ValueError as exc:
        raise ArgumentTypeError("Expected a UUID") from exc


class Command(BaseCommand):
    help = "Issue or revoke LiteKB project service keys and grant existing workspace resources."

    def add_arguments(self, parser):
        parser.add_argument("project", help="Project slug")
        action = parser.add_mutually_exclusive_group(required=True)
        action.add_argument("--issue", metavar="CLIENT_NAME")
        action.add_argument("--revoke", type=identifier, metavar="CLIENT_ID")
        parser.add_argument("--owner", help="Existing active console username; required for a new project")
        parser.add_argument("--workspace", default="default")
        parser.add_argument("--model", type=identifier, action="append", default=[])
        parser.add_argument("--agent", type=identifier, action="append", default=[])
        parser.add_argument("--knowledge", type=identifier, action="append", default=[])

    @transaction.atomic
    def handle(self, *args, **options):
        slug = options["project"]
        try:
            validate_slug(slug)
        except ValidationError as exc:
            raise CommandError("Invalid project slug") from exc
        if len(slug) > 50:
            raise CommandError("Project slug exceeds 50 characters")
        if options["revoke"]:
            count = ServiceClient.objects.filter(project__slug=slug, id=options["revoke"]).update(is_active=False)
            if not count:
                raise CommandError("Unknown client for this project")
            return "Revoked"
        if not options["issue"].strip() or len(options["issue"]) > 128:
            raise CommandError("Client name must contain 1–128 characters")
        project = Project.objects.select_for_update().filter(slug=slug).first()
        if project is None:
            owner = User.objects.filter(username=options["owner"], is_active=True).first()
            if not owner or not KnowledgeFolder.objects.filter(pk=options["workspace"],
                                                              workspace_id=options["workspace"]).exists():
                raise CommandError("An active --owner and an existing workspace root folder are required")
            project = Project.objects.create(slug=slug, name=slug, owner=owner, workspace_id=options["workspace"])
        elif project.workspace_id != options["workspace"] or (options["owner"] and project.owner.username != options["owner"]):
            raise CommandError("Workspace or owner does not match existing project")
        for key, relation, cls in (("model", project.models, Model), ("agent", project.applications, Application)):
            ids = set(options[key])
            resources = list(cls.objects.filter(pk__in=ids, workspace_id=project.workspace_id))
            if len(resources) != len(ids):
                raise CommandError(f"Unknown {key} in this workspace")
            relation.add(*resources)
        for pk in options["knowledge"]:
            kb = Knowledge.objects.select_for_update().filter(pk=pk, workspace_id=project.workspace_id,
                                                             type=KnowledgeType.BASE).first()
            if kb is None or not project.models.filter(pk=kb.embedding_model_id).exists():
                raise CommandError("Grant the embedding model and an existing basic knowledge base")
            grant, _ = ProjectKnowledge.objects.get_or_create(knowledge=kb, defaults={"project": project})
            if grant.project_id != project.pk:
                raise CommandError("Knowledge base already belongs to another project")
        client, key = ServiceClient.issue(project, options["issue"])
        return f"client_id={client.pk}\nservice_key={key}"
