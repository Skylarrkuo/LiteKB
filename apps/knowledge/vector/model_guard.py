from collections import defaultdict
from contextvars import ContextVar

from django.db import transaction

from knowledge.models import Document, Knowledge


_index_model = ContextVar("knowledge_index_model", default=None)


def run_for_model(model_id, document_ids, callback):
    """Discard stale queued work and resubmit if the model changed during inference."""
    ids = set(document_ids)
    if not ids:
        return
    model_id = str(model_id)

    def current():
        return list(Document.objects.filter(pk__in=ids).values_list("pk", "knowledge_id", "knowledge__embedding_model_id"))

    def rebuild(documents):
        from litekb_api.knowledge_service import index_documents

        by_knowledge = defaultdict(list)
        for doc_id, kb_id, latest_id in documents:
            if latest_id:
                by_knowledge[kb_id].append(doc_id)
        if by_knowledge:
            with transaction.atomic():
                for kb in Knowledge.objects.select_for_update().filter(pk__in=by_knowledge).order_by("pk"):
                    index_documents(kb, by_knowledge[kb.pk])

    documents = current()
    if not documents:
        return
    if any(str(row[2]) != model_id for row in documents):
        rebuild(documents)
        return
    token = _index_model.set(model_id)
    try:
        return callback()
    finally:
        _index_model.reset(token)
        rebuild(row for row in current() if str(row[2]) != model_id)


def writable_knowledge_ids(ids):
    """Call inside the short vector-write transaction, after model inference has returned."""
    ids = {str(pk) for pk in ids}
    expected = _index_model.get()
    if expected is None:
        return ids
    locked = Knowledge.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    return {str(pk) for pk, model in locked.values_list("pk", "embedding_model_id") if str(model) == expected}
