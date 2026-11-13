from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.response import Response

from knowledge.models import DocumentTag, Embedding, Problem, ProblemParagraphMapping, SourceType, Tag

from .auth import ServiceAPIView
from .inputs import Input, validated
from .knowledge_service import embedding_model, index_documents
from .knowledge_views import document, knowledge, paragraph
from .pagination import page


class Conflict(APIException):
    status_code = 409


class TagInput(Input):
    key = serializers.CharField(max_length=64, trim_whitespace=False)
    value = serializers.CharField(max_length=128, trim_whitespace=False)


class DocumentTagsInput(Input):
    tag_ids = serializers.ListField(child=serializers.UUIDField(), max_length=1000)


class QuestionInput(Input):
    content = serializers.CharField(max_length=256)


def tag_data(tag):
    return {"id": tag.pk, "key": tag.key, "value": tag.value}


class Tags(ServiceAPIView):
    def get(self, request, kb_id):
        kb = knowledge(request, kb_id)
        return page(request, Tag.objects.filter(knowledge=kb).order_by("key", "value", "pk"), tag_data)

    @transaction.atomic
    def post(self, request, kb_id):
        kb = knowledge(request, kb_id, lock=True)
        tag, created = Tag.objects.get_or_create(knowledge=kb, **validated(TagInput, request.data))
        return Response(tag_data(tag), status=201 if created else 200)


class TagItem(ServiceAPIView):
    def get(self, request, kb_id, tag_id):
        return Response(tag_data(get_object_or_404(Tag, pk=tag_id, knowledge=knowledge(request, kb_id))))

    @transaction.atomic
    def patch(self, request, kb_id, tag_id):
        kb = knowledge(request, kb_id, lock=True)
        tag = get_object_or_404(Tag, pk=tag_id, knowledge=kb)
        changes = validated(TagInput, request.data, partial=True)
        if not changes:
            raise ValidationError("Supply a tag key or value.")
        for attr, value in changes.items():
            setattr(tag, attr, value)
        try:
            with transaction.atomic():
                tag.save()
        except IntegrityError as exc:
            raise Conflict("This tag already exists in the knowledge base.") from exc
        return Response(tag_data(tag))

    @transaction.atomic
    def delete(self, request, kb_id, tag_id):
        kb = knowledge(request, kb_id, lock=True)
        tag = get_object_or_404(Tag, pk=tag_id, knowledge=kb)
        DocumentTag.objects.filter(document__knowledge=kb, tag=tag).delete()
        tag.delete()
        return Response(status=204)


class DocumentTags(ServiceAPIView):
    def get(self, request, kb_id, doc_id):
        kb = knowledge(request, kb_id)
        doc = document(kb, doc_id)
        return page(request, Tag.objects.filter(knowledge=kb, documenttag__document=doc).order_by("key", "value"),
                    tag_data)

    @transaction.atomic
    def put(self, request, kb_id, doc_id):
        kb = knowledge(request, kb_id, lock=True)
        doc = document(kb, doc_id)
        ids = set(validated(DocumentTagsInput, request.data)["tag_ids"])
        tags = list(Tag.objects.filter(knowledge=kb, pk__in=ids).order_by("key", "value"))
        if len(tags) != len(ids):
            raise NotFound()
        DocumentTag.objects.filter(document=doc, tag__knowledge=kb).exclude(tag_id__in=ids).delete()
        DocumentTag.objects.bulk_create([DocumentTag(document=doc, tag=tag) for tag in tags], ignore_conflicts=True)
        return Response({"tags": [tag_data(tag) for tag in tags]})


def questions(kb, doc, para):
    return ProblemParagraphMapping.objects.filter(knowledge=kb, document=doc, paragraph=para,
                                                  problem__knowledge=kb).select_related("problem")


def question_data(link):
    return {"id": link.pk, "content": link.problem.content}


def problem_for(kb, content):
    # Historical problem rows can contain duplicate wording.
    return (Problem.objects.filter(knowledge=kb, content=content).order_by("pk").first()
            or Problem.objects.create(knowledge=kb, content=content))


def discard_orphan(kb, problem_id):
    Problem.objects.filter(pk=problem_id, knowledge=kb, problemparagraphmapping__isnull=True).delete()


def invalidate_question(link):
    Embedding.objects.filter(knowledge_id=link.knowledge_id, document_id=link.document_id,
                             paragraph_id=link.paragraph_id, source_type=SourceType.PROBLEM,
                             source_id=str(link.pk)).delete()


class Questions(ServiceAPIView):
    def get(self, request, kb_id, doc_id, paragraph_id):
        kb = knowledge(request, kb_id)
        doc = document(kb, doc_id)
        rows = questions(kb, doc, paragraph(kb, doc, paragraph_id)).order_by("problem__content", "pk")
        return page(request, rows, question_data)

    @transaction.atomic
    def post(self, request, kb_id, doc_id, paragraph_id):
        kb = knowledge(request, kb_id, lock=True)
        doc = document(kb, doc_id)
        para = paragraph(kb, doc, paragraph_id)
        content = validated(QuestionInput, request.data)["content"]
        existing = questions(kb, doc, para).filter(problem__content=content).first()
        if existing:
            return Response(question_data(existing))
        embedding_model(request.auth.project, kb.embedding_model_id)
        link = ProblemParagraphMapping.objects.create(knowledge=kb, document=doc, paragraph=para,
                                                     problem=problem_for(kb, content))
        index_documents(kb, [doc.pk])
        return Response(question_data(link), status=201)


class QuestionItem(ServiceAPIView):
    def resolve(self, request, kb_id, doc_id, paragraph_id, question_id, *, lock=False):
        kb = knowledge(request, kb_id, lock=lock)
        doc = document(kb, doc_id)
        para = paragraph(kb, doc, paragraph_id)
        return kb, doc, para, get_object_or_404(questions(kb, doc, para), pk=question_id)

    def get(self, request, **ids):
        return Response(question_data(self.resolve(request, **ids)[-1]))

    @transaction.atomic
    def patch(self, request, **ids):
        kb, doc, para, link = self.resolve(request, **ids, lock=True)
        content = validated(QuestionInput, request.data)["content"]
        if content == link.problem.content:
            return Response(question_data(link))
        if questions(kb, doc, para).filter(problem__content=content).exists():
            raise Conflict("This question is already linked to the paragraph.")
        embedding_model(request.auth.project, kb.embedding_model_id)
        old_problem_id = link.problem_id
        invalidate_question(link)
        link.problem = problem_for(kb, content)
        link.save(update_fields=["problem", "update_time"])
        discard_orphan(kb, old_problem_id)
        index_documents(kb, [doc.pk])
        return Response(question_data(link))

    @transaction.atomic
    def delete(self, request, **ids):
        kb, doc, para, link = self.resolve(request, **ids, lock=True)
        embedding_model(request.auth.project, kb.embedding_model_id)
        old_problem_id = link.problem_id
        invalidate_question(link)
        link.delete()
        discard_orphan(kb, old_problem_id)
        index_documents(kb, [doc.pk])
        return Response(status=204)
