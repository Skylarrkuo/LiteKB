import hashlib
import io
import json
from collections import defaultdict

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.db import transaction
from django.db.models import F, Q
from rest_framework import serializers
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from knowledge.models import Document, DocumentTag, Paragraph, ProblemParagraphMapping, Tag

from .auth import ServiceAPIView
from .inputs import DocumentSettings, Input, validated
from .knowledge_catalog import Conflict, TagInput
from .knowledge_service import embedding_model, index_documents, store_document
from .knowledge_views import knowledge


FORMAT = "litekb.knowledge.v1"
MAX_DOCUMENTS = 200


class ArchiveTooLarge(APIException):
    status_code = 413
    default_detail = "This JSON archive exceeds the configured upload limit."


class ArchiveParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        if limit is not None:
            body = stream.read(limit + 1)
            if len(body) > limit:
                raise ArchiveTooLarge()
            stream = io.BytesIO(body)
        return super().parse(stream, media_type, parser_context)


class ExportPage(Input):
    after = serializers.UUIDField(required=False)
    limit = serializers.IntegerField(default=25, min_value=1, max_value=MAX_DOCUMENTS)


class ArchiveParagraph(Input):
    title = serializers.CharField(max_length=256, allow_blank=True, trim_whitespace=False, default="")
    content = serializers.CharField(max_length=102400, allow_blank=True, trim_whitespace=False)
    is_active = serializers.BooleanField(default=True)
    questions = serializers.ListField(child=serializers.CharField(max_length=256, trim_whitespace=False),
                                      default=list)


class ArchiveDocument(DocumentSettings):
    key = serializers.UUIDField()
    name = serializers.CharField(max_length=150, trim_whitespace=False)
    is_active = serializers.BooleanField(default=True)
    tags = TagInput(many=True, default=list)
    paragraphs = ArchiveParagraph(many=True)


class ArchiveInput(Input):
    format = serializers.ChoiceField(choices=[FORMAT])
    tags = TagInput(many=True, default=list)
    documents = ArchiveDocument(many=True, max_length=MAX_DOCUMENTS)

    def validate(self, data):
        docs = data["documents"]
        if len({doc["key"] for doc in docs}) != len(docs):
            raise ValidationError("Document keys must be unique in a batch.")
        tag_pairs = {(tag["key"], tag["value"]) for tag in data["tags"]}
        for doc in docs:
            if any((tag["key"], tag["value"]) not in tag_pairs for tag in doc["tags"]):
                raise ValidationError("Each document tag must be declared in the archive tags.")
        return data


def portable_documents(kb, docs):
    """Only join rows that agree on their knowledge, document, paragraph and problem."""
    exports = {
        doc.pk: {"key": doc.meta.get("litekb_import_key") or str(doc.pk), "name": doc.name, "is_active": doc.is_active,
                 "hit_handling_method": doc.hit_handling_method, "directly_return_similarity": doc.directly_return_similarity,
                 "tags": [], "paragraphs": []}
        for doc in docs
    }
    for row in DocumentTag.objects.filter(document_id__in=exports, tag__knowledge=kb).order_by(
            "tag__key", "tag__value").values_list("document_id", "tag__key", "tag__value"):
        doc_id, key, value = row
        exports[doc_id]["tags"].append({"key": key, "value": value})
    questions = defaultdict(list)
    for para_id, content in ProblemParagraphMapping.objects.filter(
            knowledge=kb, document_id__in=exports, paragraph__knowledge=kb, paragraph__document_id=F("document_id"),
            problem__knowledge=kb).order_by("problem__content", "pk").values_list("paragraph_id", "problem__content"):
        questions[para_id].append(content)
    rows = Paragraph.objects.filter(knowledge=kb, document_id__in=exports).order_by("document_id", "position", "pk")
    for row in rows.values("id", "document_id", "title", "content", "is_active").iterator(chunk_size=200):
        doc_id = row.pop("document_id")
        row["questions"] = questions[row.pop("id")]
        exports[doc_id]["paragraphs"].append(row)
    return list(exports.values())


def digest(record):
    # Keep the idempotency fingerprint of archives created before document hit settings were exported.
    record = dict(record)
    for key in ("hit_handling_method", "directly_return_similarity"):
        if record.get(key) == Document._meta.get_field(key).get_default():
            record.pop(key, None)
    raw = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ExportContent(ServiceAPIView):
    @transaction.atomic
    def get(self, request, kb_id):
        kb = knowledge(request, kb_id, lock=True)
        page = validated(ExportPage, request.query_params)
        query = Document.objects.filter(knowledge=kb).order_by("pk")
        if "after" in page:
            query = query.filter(pk__gt=page["after"])
        docs = list(query[:page["limit"] + 1])
        result = Response({
            "format": FORMAT, "tags": list(Tag.objects.filter(knowledge=kb).order_by("key", "value").values("key", "value")),
            "documents": portable_documents(kb, docs[:page["limit"]]),
        })
        result["Content-Disposition"] = 'attachment; filename="litekb-knowledge.json"'
        if len(docs) > page["limit"]:
            result["X-Next-After"] = str(docs[page["limit"] - 1].pk)
        return result


class ImportContent(ServiceAPIView):
    parser_classes = [ArchiveParser]

    def handle_exception(self, exc):
        # Some Django/DRF versions validate Content-Length before passing the stream to JSONParser.
        return super().handle_exception(ArchiveTooLarge() if isinstance(exc, RequestDataTooBig) else exc)

    @transaction.atomic
    def post(self, request, kb_id):
        project = request.auth.project
        kb = knowledge(request, kb_id, lock=True)
        archive = validated(ArchiveInput, request.data)
        if archive["documents"]:
            embedding_model(project, kb.embedding_model_id)
        created, skipped = import_content(project, kb, archive)
        return Response({"created_documents": len(created), "skipped_documents": skipped},
                        status=201 if created else 200)


def import_content(project, kb, archive):
    fingerprints = {str(row["key"]): digest(row) for row in archive["documents"]}
    keys = list(fingerprints)
    matches = Document.objects.filter(Q(meta__litekb_import_key__in=keys) | Q(pk__in=keys), knowledge=kb)
    existing = {str(doc.meta.get("litekb_import_key") or doc.pk): doc for doc in matches}
    # Locally authored documents also accept their own exports without creating duplicates.
    originals = [doc for key, doc in existing.items() if doc.meta.get("litekb_import_digest") != fingerprints.get(key)]
    old_digests = {row["key"]: digest(row) for row in portable_documents(kb, originals)}
    by_pair = {(row["key"], row["value"]): row for row in archive["tags"]}
    Tag.objects.bulk_create([Tag(knowledge=kb, **tag) for tag in by_pair.values()], ignore_conflicts=True, batch_size=500)
    tags = {(row.key, row.value): row for row in Tag.objects.filter(knowledge=kb)}
    created = []
    skipped = 0
    for record in archive["documents"]:
        key = str(record["key"])
        fingerprint = fingerprints[key]
        if key in existing:
            if fingerprint not in (existing[key].meta.get("litekb_import_digest"), old_digests.get(key)):
                raise Conflict("A document with this import key has different content.")
            skipped += 1
            continue
        paragraphs = [{**item, "problem_list": [{"content": text} for text in item["questions"]]}
                      for item in record["paragraphs"]]
        settings = {key: record[key] for key in ("hit_handling_method", "directly_return_similarity") if key in record}
        doc = store_document(project, kb, {"name": record["name"], "paragraphs": paragraphs, **settings})
        doc.is_active = record["is_active"]
        doc.meta = {**doc.meta, "litekb_import_key": key, "litekb_import_digest": fingerprint}
        doc.save(update_fields=["meta", "is_active"])
        doc_tags = {(tag["key"], tag["value"]) for tag in record["tags"]}
        DocumentTag.objects.bulk_create([DocumentTag(document=doc, tag=tags[pair]) for pair in doc_tags])
        created.append(doc.pk)
    if created:
        index_documents(kb, created)
    return created, skipped
