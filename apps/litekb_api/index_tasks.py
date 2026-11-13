from celery_once import AlreadyQueued
from ops import celery_app

from knowledge.models import Document
from knowledge.task.embedding import embedding_by_document


def dispatch_document_index(document_id, model_id):
    try:
        embedding_by_document.delay(document_id, model_id)
    except AlreadyQueued:
        # The currently executing task may have read the old paragraph content.
        retry_document_index.apply_async(args=(document_id, model_id), countdown=10)


@celery_app.task(bind=True, name="litekb.retry_document_index", max_retries=None, ignore_result=True)
def retry_document_index(self, document_id, model_id):
    if not Document.objects.filter(pk=document_id, knowledge__embedding_model_id=model_id).exists():
        return
    try:
        embedding_by_document.delay(document_id, model_id)
    except AlreadyQueued as exc:
        raise self.retry(exc=exc, countdown=min(60, 10 * (self.request.retries + 1)))
