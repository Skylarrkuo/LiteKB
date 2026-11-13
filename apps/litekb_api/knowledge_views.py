from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from knowledge.models import Document, DocumentTag, File, FileSourceType, Paragraph, Tag

from . import inputs
from .auth import ServiceAPIView
from .pagination import page
from .knowledge_service import (
    create_knowledge, document_data, embedding_model, index_documents, knowledge_data, paragraph_data,
    parse_file, previews, retrieve, scoped_knowledge, store_document, store_paragraph, update_knowledge, validate_upload,
)


def knowledge(request, kb_id, lock=False):
    queryset = scoped_knowledge(request.auth.project)
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    return get_object_or_404(queryset, pk=kb_id)


def document(kb, doc_id):
    return get_object_or_404(Document, knowledge=kb, pk=doc_id)


def paragraph(kb, doc, paragraph_id):
    return get_object_or_404(Paragraph, pk=paragraph_id, knowledge=kb, document=doc)


class Models(ServiceAPIView):
    def get(self, request):
        project = request.auth.project
        rows = project.models.filter(workspace_id=project.workspace_id).order_by("name", "id").values(
            "id", "name", "model_type", "model_name", "status"
        )
        return page(request, rows, dict)


class KnowledgeBases(ServiceAPIView):
    def get(self, request):
        return page(request, scoped_knowledge(request.auth.project).order_by("id"), knowledge_data)

    def post(self, request):
        kb = create_knowledge(request.auth.project, inputs.validated(inputs.KnowledgeCreate, request.data))
        return Response(knowledge_data(kb), status=201)


class KnowledgeBase(ServiceAPIView):
    def get(self, request, kb_id):
        return Response(knowledge_data(knowledge(request, kb_id)))

    @transaction.atomic
    def patch(self, request, kb_id):
        kb = knowledge(request, kb_id, lock=True)
        data = inputs.validated(inputs.KnowledgeEdit, request.data)
        update_knowledge(request.auth.project, kb, data)
        return Response(knowledge_data(kb))

    @transaction.atomic
    def delete(self, request, kb_id):
        kb = knowledge(request, kb_id, lock=True)
        from knowledge.serializers.knowledge import KnowledgeSerializer

        DocumentTag.objects.filter(document__knowledge=kb, tag__knowledge=kb).delete()
        Tag.objects.filter(knowledge=kb).delete()
        KnowledgeSerializer.Operate(data={
            "knowledge_id": kb.pk, "workspace_id": kb.workspace_id, "user_id": request.auth.project.owner_id,
        }).delete()
        return Response(status=204)


class Documents(ServiceAPIView):
    def get(self, request, kb_id):
        kb = knowledge(request, kb_id)
        return page(request, Document.objects.filter(knowledge=kb).order_by("id"), document_data)

    @transaction.atomic
    def post(self, request, kb_id):
        kb = knowledge(request, kb_id, lock=True)
        project = request.auth.project
        embedding_model(project, kb.embedding_model_id)
        if request.FILES:
            batches = parse_file(project, kb, inputs.validated(inputs.FileInput, request.data))
        else:
            batches = [inputs.validated(inputs.DocumentCreate, request.data)]
        docs = [store_document(project, kb, data) for data in batches]
        if request.FILES:
            previews(kb).filter(pk__in={data["source_file_id"] for data in batches}).delete()
        index_documents(kb, [doc.pk for doc in docs])
        return Response({"documents": [document_data(row) for row in Document.objects.filter(
            knowledge=kb, id__in=[doc.pk for doc in docs]).order_by("id")]}, status=201)


class DocumentItem(ServiceAPIView):
    def get(self, request, kb_id, doc_id):
        return Response(document_data(document(knowledge(request, kb_id), doc_id)))

    @transaction.atomic
    def patch(self, request, kb_id, doc_id):
        doc = document(knowledge(request, kb_id, lock=True), doc_id)
        data = inputs.validated(inputs.DocumentEdit, request.data)
        for key, value in data.items():
            setattr(doc, key, value)
        doc.save()
        return Response(document_data(doc))

    @transaction.atomic
    def delete(self, request, kb_id, doc_id):
        kb = knowledge(request, kb_id, lock=True)
        doc = document(kb, doc_id)
        from knowledge.serializers.document import DocumentSerializers

        # Old imports may have source_file_id pointing at a shared preview. Delete only this document's files.
        if "source_file_id" in doc.meta:
            doc.meta = {key: value for key, value in doc.meta.items() if key != "source_file_id"}
            doc.save(update_fields=["meta"])
        DocumentSerializers.Operate(data={
            "workspace_id": kb.workspace_id, "knowledge_id": kb.pk, "document_id": doc.pk,
        }).delete()
        return Response(status=204)


class DocumentSource(ServiceAPIView):
    def get(self, request, kb_id, doc_id):
        kb = knowledge(request, kb_id)
        doc = document(kb, doc_id)
        file = File.objects.filter(source_type=FileSourceType.DOCUMENT, source_id=str(doc.pk)).first()
        if file is None:
            file = get_object_or_404(File, pk=doc.meta.get("source_file_id"), source_type=FileSourceType.KNOWLEDGE,
                                     source_id=str(kb.pk))
        response = HttpResponse(file.get_bytes(), content_type="application/octet-stream")
        response["Content-Disposition"] = content_disposition_header(True, file.file_name)
        return response

    @transaction.atomic
    def put(self, request, kb_id, doc_id):
        kb = knowledge(request, kb_id, lock=True)
        doc = document(kb, doc_id)
        upload = validate_upload(kb, inputs.validated(inputs.UploadInput, request.data)["file"])
        file = File(file_name=upload.name, source_type=FileSourceType.DOCUMENT, source_id=str(doc.pk))
        file.save(upload.read())
        File.objects.filter(source_type=FileSourceType.DOCUMENT, source_id=str(doc.pk)).exclude(pk=file.pk).delete()
        doc.meta = {**doc.meta, "source_file_id": str(file.pk), "allow_download": True}
        doc.save(update_fields=["meta", "update_time"])
        return Response(document_data(doc))

    @transaction.atomic
    def delete(self, request, kb_id, doc_id):
        doc = document(knowledge(request, kb_id, lock=True), doc_id)
        File.objects.filter(source_type=FileSourceType.DOCUMENT, source_id=str(doc.pk)).delete()
        doc.meta.pop("source_file_id", None)
        doc.meta["allow_download"] = False
        doc.save(update_fields=["meta", "update_time"])
        return Response(status=204)


class SplitFile(ServiceAPIView):
    @transaction.atomic
    def post(self, request, kb_id):
        kb = knowledge(request, kb_id)
        return Response({"documents": parse_file(request.auth.project, kb, inputs.validated(inputs.FileInput, request.data))},
                        status=201)


class SplitPreview(ServiceAPIView):
    @transaction.atomic
    def delete(self, request, kb_id, file_id):
        kb = knowledge(request, kb_id, lock=True)
        preview = get_object_or_404(previews(kb), pk=file_id)
        if Document.objects.filter(knowledge=kb, meta__source_file_id=str(preview.pk)).exists():
            return Response({"detail": "This source file is referenced by an existing document."}, status=409)
        preview.delete()
        return Response(status=204)


class Reindex(ServiceAPIView):
    @transaction.atomic
    def post(self, request, kb_id, doc_id=None):
        kb = knowledge(request, kb_id, lock=True)
        embedding_model(request.auth.project, kb.embedding_model_id)
        docs = Document.objects.filter(knowledge=kb)
        if doc_id is not None:
            docs = docs.filter(pk=document(kb, doc_id).pk)
        ids = list(docs.values_list("pk", flat=True))
        index_documents(kb, ids)
        return Response({"submitted_documents": len(ids)}, status=202)


class Paragraphs(ServiceAPIView):
    def get(self, request, kb_id, doc_id):
        kb = knowledge(request, kb_id)
        doc = document(kb, doc_id)
        return page(request, Paragraph.objects.filter(knowledge=kb, document=doc).order_by("position", "id"),
                    paragraph_data)

    @transaction.atomic
    def post(self, request, kb_id, doc_id):
        kb = knowledge(request, kb_id, lock=True)
        doc = document(kb, doc_id)
        embedding_model(request.auth.project, kb.embedding_model_id)
        row = store_paragraph(kb, doc, inputs.validated(inputs.ParagraphEdit, request.data))
        row.refresh_from_db()
        return Response(paragraph_data(row), status=201)


class ParagraphItem(ServiceAPIView):
    def get(self, request, kb_id, doc_id, paragraph_id):
        kb = knowledge(request, kb_id)
        return Response(paragraph_data(paragraph(kb, document(kb, doc_id), paragraph_id)))

    @transaction.atomic
    def patch(self, request, kb_id, doc_id, paragraph_id):
        kb = knowledge(request, kb_id, lock=True)
        doc = document(kb, doc_id)
        embedding_model(request.auth.project, kb.embedding_model_id)
        row = paragraph(kb, doc, paragraph_id)
        data = inputs.validated(inputs.ParagraphEdit, request.data, partial=True)
        if not data:
            raise ValidationError("Provide a paragraph field to update.")
        row = store_paragraph(kb, doc, data, row)
        row.refresh_from_db()
        return Response(paragraph_data(row))

    @transaction.atomic
    def delete(self, request, kb_id, doc_id, paragraph_id):
        kb = knowledge(request, kb_id, lock=True)
        doc = document(kb, doc_id)
        row = paragraph(kb, doc, paragraph_id)
        from knowledge.serializers.paragraph import ParagraphSerializers

        ParagraphSerializers.Operate(data={
            "workspace_id": kb.workspace_id, "knowledge_id": kb.pk, "document_id": doc.pk, "paragraph_id": row.pk,
        }).delete(with_valid=True)
        return Response(status=204)


class Retrievals(ServiceAPIView):
    def post(self, request):
        return Response({"hits": retrieve(request.auth.project, inputs.validated(inputs.RetrieveInput, request.data))})
