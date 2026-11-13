import logging
from pathlib import Path

from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, ValidationError

from knowledge.models import Document, Embedding, File, FileSourceType, Knowledge, KnowledgeType, Paragraph, State
from knowledge.models import Status, TaskType

from .inputs import DocumentCreate, validated
from .models import ProjectKnowledge


logger = logging.getLogger(__name__)


def scoped_knowledge(project):
    return Knowledge.objects.filter(project_grant__project=project, workspace_id=project.workspace_id,
                                    type=KnowledgeType.BASE)


def embedding_model(project, model_id):
    return get_object_or_404(project.models, pk=model_id, workspace_id=project.workspace_id,
                             model_type="EMBEDDING", status="SUCCESS")


def knowledge_data(kb):
    return {
        "id": kb.pk, "name": kb.name, "description": kb.desc, "embedding_model_id": kb.embedding_model_id,
        "file_size_limit": kb.file_size_limit, "file_count_limit": kb.file_count_limit,
        "created_at": kb.create_time, "updated_at": kb.update_time,
    }


def index_state(raw_status):
    try:
        return Status.of(raw_status)[TaskType.EMBEDDING].name.lower()
    except (ValueError, KeyError):
        return "unknown"


def document_data(doc):
    return {
        "id": doc.pk, "knowledge_base_id": doc.knowledge_id, "name": doc.name, "is_active": doc.is_active,
        "character_count": doc.char_length, "index_status": index_state(doc.status), "updated_at": doc.update_time,
        "source_file_id": doc.meta.get("source_file_id"),
        "hit_handling_method": doc.hit_handling_method, "directly_return_similarity": doc.directly_return_similarity,
    }


def paragraph_data(paragraph):
    return {
        "id": paragraph.pk, "document_id": paragraph.document_id, "knowledge_base_id": paragraph.knowledge_id,
        "title": paragraph.title, "content": paragraph.content, "is_active": paragraph.is_active,
        "position": paragraph.position, "index_status": index_state(paragraph.status),
    }


@transaction.atomic
def create_knowledge(project, data):
    model = embedding_model(project, data["embedding_model_id"])
    from knowledge.models import KnowledgeFolder
    from knowledge.serializers.common import update_resource_mapping_by_knowledge
    from system_manage.models import AuthTargetType
    from system_manage.serializers.user_resource_permission import UserResourcePermissionSerializer

    folder = get_object_or_404(KnowledgeFolder, pk=project.workspace_id, workspace_id=project.workspace_id)
    kb = Knowledge.objects.create(
        name=data["name"], desc=data["description"], user_id=project.owner_id, workspace_id=project.workspace_id,
        type=KnowledgeType.BASE, folder=folder, embedding_model=model,
    )
    ProjectKnowledge.objects.create(project=project, knowledge=kb)
    UserResourcePermissionSerializer(data={
        "workspace_id": project.workspace_id, "user_id": str(project.owner_id),
        "auth_target_type": AuthTargetType.KNOWLEDGE.value,
    }).auth_resource(str(kb.pk))
    update_resource_mapping_by_knowledge(str(kb.pk))
    return kb


def update_knowledge(project, kb, data):
    previous_model = kb.embedding_model_id
    if "embedding_model_id" in data:
        kb.embedding_model = embedding_model(project, data.pop("embedding_model_id"))
    for key, value in data.items():
        setattr(kb, "desc" if key == "description" else key, value)
    kb.save()
    if previous_model != kb.embedding_model_id:
        from knowledge.serializers.common import drop_knowledge_index, update_resource_mapping_by_knowledge

        drop_knowledge_index(knowledge_id=kb.pk)
        Embedding.objects.filter(knowledge=kb).delete()
        update_resource_mapping_by_knowledge(str(kb.pk))
        index_documents(kb, Document.objects.filter(knowledge=kb).values_list("pk", flat=True))


def index_documents(kb, doc_ids):
    """Commit rows before dispatch so the worker sees the new document, status and paragraphs."""
    from common.event.listener_manage import ListenerManagement
    from .index_tasks import dispatch_document_index

    doc_ids = list(doc_ids)
    if not doc_ids:
        return
    ListenerManagement.update_status(Document.objects.filter(pk__in=doc_ids, knowledge=kb),
                                     TaskType.EMBEDDING, State.PENDING)
    ListenerManagement.update_status(Paragraph.objects.filter(document_id__in=doc_ids, knowledge=kb),
                                     TaskType.EMBEDDING, State.PENDING)

    for doc_id in doc_ids:
        def dispatch(pk=str(doc_id), model_id=str(kb.embedding_model_id)):
            try:
                dispatch_document_index(pk, model_id)
            except Exception:
                logger.exception("Could not enqueue document %s", pk)
                ListenerManagement.update_status(Document.objects.filter(pk=pk), TaskType.EMBEDDING, State.FAILURE)
                ListenerManagement.update_status(Paragraph.objects.filter(document_id=pk), TaskType.EMBEDDING, State.FAILURE)

        transaction.on_commit(dispatch)


def validate_upload(kb, upload):
    if upload.size > 1024 * 1024 * kb.file_size_limit:
        raise ValidationError({"file": "The upload exceeds this knowledge base's size limit."})
    if Path(upload.name).suffix.lower() not in {".txt", ".md", ".pdf", ".docx", ".csv", ".xlsx", ".xls", ".html"}:
        raise ValidationError({"file": "Unsupported file type."})
    return upload


def previews(kb):
    return File.objects.filter(source_type=FileSourceType.KNOWLEDGE, source_id=str(kb.pk), meta__litekb_preview=True)


def parse_file(project, kb, data):
    upload = validate_upload(kb, data["file"])
    from knowledge.serializers.document import DocumentSerializers

    parsed = DocumentSerializers.Split(data={"workspace_id": project.workspace_id, "knowledge_id": str(kb.pk)}).parse({
        "file": [upload], "limit": data["split_length"],
    })
    if not parsed:
        raise ValidationError({"file": "No documents were found in this file."})
    File.objects.filter(source_type=FileSourceType.KNOWLEDGE, source_id=str(kb.pk),
                        pk__in={row["source_file_id"] for row in parsed}).update(meta={"litekb_preview": True})
    return [validated(DocumentCreate, {
        "name": row["name"], "paragraphs": [{"title": p.get("title") or "", "content": p["content"]}
                                             for p in row["content"] if p.get("content", "").strip()],
        "source_file_id": row["source_file_id"],
    }) for row in parsed]


def store_document(project, kb, data):
    data = dict(data)
    source = None
    if "source_file_id" in data:
        source = get_object_or_404(previews(kb).select_for_update(), pk=data["source_file_id"])
    from knowledge.serializers.document import DocumentSerializers

    if "content" in data:
        from common.utils.split_model import get_split_model

        content = data.pop("content")
        data = validated(DocumentCreate, {**data, "paragraphs": [
            {"title": p.get("title") or "", "content": p["content"]}
            for p in get_split_model(data["name"], limit=4096).parse(content) if p.get("content", "").strip()
        ]})
    objects = DocumentSerializers.Create.get_document_paragraph_model(kb.pk, project.owner_id, data)
    doc = objects["document"]
    for field in ("hit_handling_method", "directly_return_similarity"):
        if field in data:
            setattr(doc, field, data[field])
    if source is not None:
        # A single preview can produce multiple documents. Each must own its own download reference.
        DocumentSerializers.Batch.link_file(source.pk, doc.pk, kb.pk, project.owner_id)
        original = File.objects.get(source_id=str(doc.pk), source_type=FileSourceType.DOCUMENT)
        doc.meta["source_file_id"] = str(original.pk)
    doc.save()
    paragraphs = objects["paragraph_model_list"]
    for position, paragraph in enumerate(paragraphs, 1):
        paragraph.position = position
        paragraph.is_active = data["paragraphs"][position - 1].get("is_active", True)
    Paragraph.objects.bulk_create(paragraphs, batch_size=500)
    if objects["problem_paragraph_object_list"]:
        from knowledge.models import Problem, ProblemParagraphMapping
        from knowledge.serializers.common import ProblemParagraphManage

        problems, links = ProblemParagraphManage(objects["problem_paragraph_object_list"], kb.pk).to_problem_model_list()
        Problem.objects.bulk_create(problems, batch_size=500)
        ProblemParagraphMapping.objects.bulk_create(links, batch_size=500)
    return doc


def store_paragraph(kb, doc, data, paragraph=None):
    from common.chunk import text_to_chunk
    from knowledge.serializers.common import update_document_char_length

    if paragraph is None:
        last = Paragraph.objects.filter(document=doc).aggregate(n=Max("position"))["n"] or 0
        paragraph = Paragraph(document=doc, knowledge=kb, position=last + 1)
    for key in ("title", "content", "is_active"):
        if key in data:
            setattr(paragraph, key, data[key])
    if "content" in data:
        paragraph.chunks = text_to_chunk(data["content"])
    paragraph.save()
    Embedding.objects.filter(knowledge=kb, paragraph=paragraph).delete()
    update_document_char_length(str(doc.pk))
    index_documents(kb, [doc.pk])
    return paragraph


def retrieve_rrf(project, bases, data):
    from django.db.models import F
    from knowledge.serializers.common import get_embedding_model_by_knowledge
    from knowledge.vector.base_vector import normalize_for_embedding
    from knowledge.vector.hybrid import ranked_paragraphs

    vectors = {}
    question = normalize_for_embedding(data["query"])
    for kb in bases:
        if kb.embedding_model_id not in vectors:
            model = get_embedding_model_by_knowledge(kb)
            vectors[kb.embedding_model_id] = model.embed_query(question)
    by_knowledge = {kb.pk: vectors[kb.embedding_model_id] for kb in bases}
    ranked = ranked_paragraphs(by_knowledge, question, data["top_k"], data["min_score"])
    paragraphs = Paragraph.objects.filter(
        knowledge__in=scoped_knowledge(project).filter(pk__in=[kb.pk for kb in bases]),
        document__knowledge_id=F("knowledge_id"), document__is_active=True, is_active=True,
    ).select_related("document").in_bulk(row["paragraph_id"] for row in ranked)
    hits = []
    for row in ranked:
        p = paragraphs.get(row["paragraph_id"])
        if p:
            hits.append({**row, "knowledge_base_id": p.knowledge_id, "document_id": p.document_id,
                         "document_name": p.document.name, "position": p.position, "title": p.title,
                         "content": p.content})
    return hits


def retrieve(project, data):
    ids = set(data["knowledge_base_ids"])
    bases = list(scoped_knowledge(project).filter(id__in=ids).select_related("embedding_model"))
    if len(bases) != len(ids):
        raise NotFound()
    for model_id in {kb.embedding_model_id for kb in bases}:
        embedding_model(project, model_id)
    if data["mode"] == "rrf":
        return retrieve_rrf(project, bases, data)
    from knowledge.serializers.knowledge import KnowledgeSerializer

    hits = []
    for kb in bases:
        rows = KnowledgeSerializer.HitTest(data={
            "workspace_id": project.workspace_id, "knowledge_id": kb.pk, "user_id": project.owner_id,
            "query_text": data["query"], "top_number": data["top_k"], "search_mode": data["mode"],
            "similarity": data["min_score"],
        }).hit_test()
        for row in rows:
            if str(row["knowledge_id"]) == str(kb.pk) and row["is_active"]:
                hits.append({
                    "knowledge_base_id": kb.pk, "document_id": row["document_id"], "document_name": row["document_name"],
                    "paragraph_id": row["id"], "position": row["position"], "title": row["title"],
                    "content": row["content"], "score": row["comprehensive_score"],
                })
    return sorted(hits, key=lambda row: (-row["score"], str(row["paragraph_id"])))[:data["top_k"]]
