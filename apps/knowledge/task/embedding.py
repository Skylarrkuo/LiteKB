# coding=utf-8

import traceback
from typing import List

from celery_once import QueueOnce
from common.config.embedding_config import ModelManage
from common.event.listener_manage import (
    ListenerManagement,
    UpdateEmbeddingDocumentIdArgs,
    UpdateEmbeddingKnowledgeIdArgs,
    UpdateProblemArgs,
)
from common.utils.logger import maxkb_logger
from django.db import transaction
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from models_provider.models import Model
from models_provider.tools import get_model, get_model_default_params
from ops import celery_app

from knowledge.models import Document, Knowledge, Paragraph, ProblemParagraphMapping, State, TaskType
from knowledge.serializers.common import drop_knowledge_index
from knowledge.vector.model_guard import run_for_model


def paragraph_documents(ids):
    return Paragraph.objects.filter(pk__in=ids).values_list("document_id", flat=True).distinct()


def get_embedding_model(
    model_id,
    exception_handler=lambda e: maxkb_logger.error(
        _("Failed to obtain vector model: {error} {traceback}").format(error=str(e), traceback=traceback.format_exc())
    ),
):
    try:
        model = QuerySet(Model).filter(id=model_id).first()

        default_params = get_model_default_params(model)

        embedding_model = ModelManage.get_model(model_id, lambda _id: get_model(model, **{**default_params}))
    except Exception as e:
        exception_handler(e)
        raise e
    return embedding_model


@celery_app.task(base=QueueOnce, once={"keys": ["paragraph_id"]}, name="celery:embedding_by_paragraph")
def embedding_by_paragraph(paragraph_id, model_id):
    run_for_model(model_id, paragraph_documents([paragraph_id]),
                  lambda: ListenerManagement.embedding_by_paragraph(paragraph_id, get_embedding_model(model_id)))


@celery_app.task(base=QueueOnce, once={"keys": ["paragraph_id_list"]}, name="celery:embedding_by_paragraph_data_list")
def embedding_by_paragraph_data_list(data_list, paragraph_id_list, model_id):
    run_for_model(model_id, paragraph_documents(paragraph_id_list), lambda:
                  ListenerManagement.embedding_by_paragraph_data_list(data_list, paragraph_id_list,
                                                                      get_embedding_model(model_id)))


@celery_app.task(base=QueueOnce, once={"keys": ["paragraph_id_list"]}, name="celery:embedding_by_paragraph_list")
def embedding_by_paragraph_list(paragraph_id_list, model_id):
    run_for_model(model_id, paragraph_documents(paragraph_id_list),
                  lambda: ListenerManagement.embedding_by_paragraph_list(paragraph_id_list, get_embedding_model(model_id)))


@celery_app.task(base=QueueOnce, once={"keys": ["document_id"]}, name="celery:embedding_by_document")
def embedding_by_document(document_id, model_id, state_list=None):
    """
    向量化文档
    @param state_list:
    @param document_id: 文档id
    @param model_id 向量模型
    :return: None
    """

    current_id = Document.objects.filter(pk=document_id).values_list("knowledge__embedding_model_id", flat=True).first()
    if current_id is None:
        return
    if state_list is None or str(current_id) != str(model_id):
        state_list = [
            State.PENDING.value,
            State.STARTED.value,
            State.SUCCESS.value,
            State.FAILURE.value,
            State.REVOKE.value,
            State.REVOKED.value,
            State.IGNORED.value,
        ]

    def exception_handler(e):
        ListenerManagement.update_status(QuerySet(Document).filter(id=document_id), TaskType.EMBEDDING, State.FAILURE)
        maxkb_logger.error(
            _("Failed to obtain vector model: {error} {traceback}").format(
                error=str(e), traceback=traceback.format_exc()
            )
        )

    # A queued task from before a model switch can rebuild the document with its current model.
    model_id = str(current_id)
    run_for_model(model_id, [document_id], lambda: ListenerManagement.embedding_by_document(
        document_id, get_embedding_model(model_id, exception_handler), state_list))


@celery_app.task(name="celery:embedding_by_document_list")
def embedding_by_document_list(document_id_list, model_id):
    """
    向量化文档
    @param document_id_list: 文档id列表
    @param model_id 向量模型
    :return: None
    """
    for document_id in document_id_list:
        embedding_by_document.delay(document_id, model_id)


@celery_app.task(base=QueueOnce, once={"keys": ["knowledge_id"]}, name="celery:embedding_by_knowledge")
def embedding_by_knowledge(knowledge_id, model_id):
    """
    向量化知识库
    @param knowledge_id: 知识库id
    @param model_id 向量模型
    :return: None
    """
    maxkb_logger.info(_("Start--->Vectorized knowledge: {knowledge_id}").format(knowledge_id=knowledge_id))
    try:
        with transaction.atomic():
            knowledge = Knowledge.objects.select_for_update().filter(pk=knowledge_id).first()
            if knowledge is None or str(knowledge.embedding_model_id) != str(model_id):
                return
            ListenerManagement.delete_embedding_by_knowledge(knowledge_id)
            drop_knowledge_index(knowledge_id=knowledge_id)
        document_list = QuerySet(Document).filter(knowledge_id=knowledge_id)
        maxkb_logger.info(
            _("Knowledge documentation: {document_names}").format(
                document_names=", ".join([d.name for d in document_list])
            )
        )
        from litekb_api.index_tasks import dispatch_document_index

        for document in document_list:
            dispatch_document_index(str(document.pk), str(model_id))
    except Exception as e:
        maxkb_logger.error(
            _("Vectorized knowledge: {knowledge_id} error {error} {traceback}").format(
                knowledge_id=knowledge_id, error=str(e), traceback=traceback.format_exc()
            )
        )
    finally:
        maxkb_logger.info(_("End--->Vectorized knowledge: {knowledge_id}").format(knowledge_id=knowledge_id))


def embedding_by_problem(args, model_id):
    """
    向量话问题
    @param args:    问题对象
    @param model_id: 模型id
    @return:
    """
    run_for_model(model_id, [args["document_id"]],
                  lambda: ListenerManagement.embedding_by_problem(args, get_embedding_model(model_id)))


def embedding_by_data_list(args: List, model_id):
    run_for_model(model_id, {row["document_id"] for row in args},
                  lambda: ListenerManagement.embedding_by_data_list(args, get_embedding_model(model_id)))


@celery_app.task(base=QueueOnce, once={"keys": ["document_id"]}, name="celery:tokenize_by_document")
def tokenize_by_document(document_id, state_list):
    ListenerManagement.tokenize_by_document(document_id, state_list)


def delete_embedding_by_document(document_id):
    """
    删除指定文档id的向量
    @param document_id: 文档id
    @return: None
    """

    ListenerManagement.delete_embedding_by_document(document_id)


def delete_embedding_by_document_list(document_id_list: List[str]):
    """
    删除指定文档列表的向量数据
    @param document_id_list: 文档id列表
    @return: None
    """
    ListenerManagement.delete_embedding_by_document_list(document_id_list)


def delete_embedding_by_knowledge(knowledge_id):
    """
    删除指定数据集向量数据
    @param knowledge_id: 数据集id
    @return: None
    """
    ListenerManagement.delete_embedding_by_knowledge(knowledge_id)


def delete_embedding_by_paragraph(paragraph_id):
    """
    删除指定段落的向量数据
    @param paragraph_id: 段落id
    @return: None
    """
    ListenerManagement.delete_embedding_by_paragraph(paragraph_id)


def delete_embedding_by_source(source_id):
    """
    删除指定资源id的向量数据
    @param source_id: 资源id
    @return: None
    """
    ListenerManagement.delete_embedding_by_source(source_id)


def disable_embedding_by_paragraph(paragraph_id):
    """
    禁用某个段落id的向量
    @param paragraph_id: 段落id
    @return: None
    """
    ListenerManagement.disable_embedding_by_paragraph(paragraph_id)


def enable_embedding_by_paragraph(paragraph_id):
    """
    开启某个段落id的向量数据
    @param paragraph_id: 段落id
    @return: None
    """
    ListenerManagement.enable_embedding_by_paragraph(paragraph_id)


def delete_embedding_by_source_ids(source_ids: List[str]):
    """
    删除向量根据source_id_list
    @param source_ids:
    @return:
    """
    ListenerManagement.delete_embedding_by_source_ids(source_ids)


def update_problem_embedding(problem_id: str, problem_content: str, model_id):
    """
    更新问题
    @param problem_id:
    @param problem_content:
    @param model_id:
    @return:
    """
    docs = ProblemParagraphMapping.objects.filter(problem_id=problem_id).values_list("document_id", flat=True)
    run_for_model(model_id, docs, lambda: ListenerManagement.update_problem(
        UpdateProblemArgs(problem_id, problem_content, get_embedding_model(model_id))))


def update_embedding_knowledge_id(paragraph_id_list, target_knowledge_id):
    """
    修改向量数据到指定知识库
    @param paragraph_id_list: 指定段落的向量数据
    @param target_knowledge_id: 知识库id
    @return:
    """

    ListenerManagement.update_embedding_knowledge_id(
        UpdateEmbeddingKnowledgeIdArgs(paragraph_id_list, target_knowledge_id)
    )


def delete_embedding_by_paragraph_ids(paragraph_ids: List[str]):
    """
    删除指定段落列表的向量数据
    @param paragraph_ids: 段落列表
    @return: None
    """
    ListenerManagement.delete_embedding_by_paragraph_ids(paragraph_ids)


def update_embedding_document_id(
    paragraph_id_list, target_document_id, target_knowledge_id, target_embedding_model_id=None
):
    def update(model):
        ListenerManagement.update_embedding_document_id(
            UpdateEmbeddingDocumentIdArgs(paragraph_id_list, target_document_id, target_knowledge_id, model))

    if target_embedding_model_id is None:
        update(None)
    else:
        run_for_model(target_embedding_model_id, [target_document_id],
                      lambda: update(get_embedding_model(target_embedding_model_id)))


def delete_embedding_by_knowledge_id_list(knowledge_id_list):
    ListenerManagement.delete_embedding_by_knowledge_id_list(knowledge_id_list)
