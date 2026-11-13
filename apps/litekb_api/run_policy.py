from contextlib import contextmanager
from contextvars import ContextVar

from rest_framework.exceptions import PermissionDenied


_grants = ContextVar("litekb_run_grants", default=None)


@contextmanager
def project_scope(project):
    grants = {
        "knowledge": frozenset(map(str, project.knowledge_grants.values_list("knowledge_id", flat=True))),
        "application": frozenset(map(str, project.applications.values_list("pk", flat=True))),
        "model": frozenset(map(str, project.models.values_list("pk", flat=True))),
    }
    token = _grants.set(grants)
    try:
        yield
    finally:
        _grants.reset(token)


def filter_ids(kind, values):
    grants = _grants.get()
    if grants is None or kind not in grants:
        return values
    return [value for value in values if str(value) in grants[kind]]


def require_ids(kind, values):
    if len(filter_ids(kind, values)) != len(values):
        raise PermissionDenied("The published agent references a resource outside this project.")


def validate_resources(version):
    if _grants.get() is None:
        return
    from application.serializers.application import get_bound_application_ids, get_bound_knowledge_ids

    config = {
        "work_flow": version.work_flow,
        "knowledge_id_list": version.knowledge_ids,
        "application_ids": version.application_ids,
    }
    require_ids("application", [version.application_id, *get_bound_application_ids(config)])
    require_ids("knowledge", get_bound_knowledge_ids(config))
    if version.model_id:
        require_ids("model", [version.model_id])
