# coding=utf-8
"""
@project: maxkb
@Author：虎
@file： pg_vector.py
@date：2023/10/19 15:28
@desc:
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List

import uuid_utils.compat as uuid
from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.db.models import QuerySet, Value
from langchain_core.embeddings import Embeddings

from common.db.search import generate_sql_by_query_dict
from common.db.sql_execute import select_list
from common.utils.common import get_file_content
from common.utils.ts_vecto_util import to_ts_vector, to_query
from knowledge.models import Embedding, SearchMode, SourceType, Termbase
from knowledge.vector.base_vector import BaseVectorStore, normalize_for_embedding
from knowledge.vector.hybrid import ranked_paragraphs
from knowledge.vector.model_guard import writable_knowledge_ids
from maxkb.conf import PROJECT_DIR


class PGVector(BaseVectorStore):
    def delete_by_source_ids(self, source_ids: List[str], source_type: str):
        if len(source_ids) == 0:
            return
        QuerySet(Embedding).filter(source_id__in=source_ids, source_type=source_type).delete()

    def update_by_source_ids(self, source_ids: List[str], instance: Dict):
        rows = QuerySet(Embedding).filter(source_id__in=source_ids)
        with transaction.atomic():
            allowed = writable_knowledge_ids(rows.values_list("knowledge_id", flat=True).distinct())
            rows.filter(knowledge_id__in=allowed).update(**instance)

    def vector_is_create(self) -> bool:
        # 项目启动默认是创建好的 不需要再创建
        return True

    def vector_create(self):
        return True

    def _save(
        self,
        text,
        source_type: SourceType,
        knowledge_id: str,
        document_id: str,
        paragraph_id: str,
        source_id: str,
        is_active: bool,
        embedding: Embeddings,
    ):
        text = normalize_for_embedding(text)
        text_embedding = [float(x) for x in embedding.embed_query(text)]
        terms = list(
            QuerySet(Termbase)
            .filter(
                knowledge_id=knowledge_id,
            )
            .values_list("content", flat=True)
        )
        embedding = Embedding(
            id=uuid.uuid7(),
            knowledge_id=knowledge_id,
            document_id=document_id,
            is_active=is_active,
            paragraph_id=paragraph_id,
            source_id=source_id,
            embedding=text_embedding,
            source_type=source_type,
            search_vector=SearchVector(Value(to_ts_vector(text, user_words=terms)), config='simple'),
        )
        with transaction.atomic():
            if writable_knowledge_ids([knowledge_id]):
                embedding.save()
        return True

    def _batch_save(self, text_list: List[Dict], embedding: Embeddings, is_the_task_interrupted):
        texts = [normalize_for_embedding(row.get("text")) for row in text_list]
        embeddings = embedding.embed_documents(texts)
        embedding_list = [
            Embedding(
                id=uuid.uuid7(),
                document_id=text_list[index].get("document_id"),
                paragraph_id=text_list[index].get("paragraph_id"),
                knowledge_id=text_list[index].get("knowledge_id"),
                is_active=text_list[index].get("is_active", True),
                source_id=text_list[index].get("source_id"),
                source_type=text_list[index].get("source_type"),
                embedding=[float(x) for x in embeddings[index]],
                search_vector=SearchVector(
                    Value(
                        to_ts_vector(
                            texts[index],
                            user_words=list(
                                QuerySet(Termbase)
                                .filter(knowledge_id=text_list[index]["knowledge_id"])
                                .values_list("content", flat=True)
                            ),
                        )
                    ),
                    config='simple',
                ),
            )
            for index in range(0, len(texts))
        ]
        if not is_the_task_interrupted() and embedding_list:
            with transaction.atomic():
                allowed = writable_knowledge_ids(row.knowledge_id for row in embedding_list)
                QuerySet(Embedding).bulk_create([row for row in embedding_list if str(row.knowledge_id) in allowed])
        return True

    def hit_test(
        self,
        query_text,
        knowledge_id_list: list[str],
        exclude_document_id_list: list[str],
        top_number: int,
        similarity: float,
        search_mode: SearchMode,
        embedding: Embeddings,
    ):
        if knowledge_id_list is None or len(knowledge_id_list) == 0:
            return []
        query_text = normalize_for_embedding(query_text)
        embedding_query = embedding.embed_query(query_text)
        return self.query(query_text, embedding_query, knowledge_id_list, None, exclude_document_id_list,
                          None, True, top_number, similarity, search_mode)

    def query(
        self,
        query_text: str,
        query_embedding: List[float],
        knowledge_id_list: list[str],
        document_id_list: list[str],
        exclude_document_id_list: list[str],
        exclude_paragraph_list: list[str],
        is_active: bool,
        top_n: int,
        similarity: float,
        search_mode: SearchMode,
    ):
        if not knowledge_id_list or (document_id_list is not None and len(document_id_list) == 0):
            return []
        if search_mode == SearchMode.rrf:
            if not is_active:
                return []
            from litekb_api.run_policy import require_ids
            require_ids("knowledge", knowledge_id_list)
            ranked = ranked_paragraphs(dict.fromkeys(knowledge_id_list, query_embedding), query_text,
                                       top_n, similarity, document_id_list, exclude_document_id_list,
                                       exclude_paragraph_list)
            return [{**r, "similarity": r["score"], "comprehensive_score": r["score"]} for r in ranked]
        for search_handle in search_handle_list:
            if search_handle.support(search_mode):
                # Query per knowledge base to leverage per-KB partial HNSW indexes
                # (WHERE knowledge_id = '{k_id}'), which won't be used with knowledge_id__in
                def build_query_set(kid):
                    qs = QuerySet(Embedding).filter(knowledge_id=kid, is_active=is_active)
                    if document_id_list is not None and len(document_id_list) > 0:
                        qs = qs.filter(document_id__in=document_id_list)
                    if exclude_document_id_list is not None and len(exclude_document_id_list) > 0:
                        qs = qs.exclude(document_id__in=exclude_document_id_list)
                    if exclude_paragraph_list is not None and len(exclude_paragraph_list) > 0:
                        qs = qs.exclude(paragraph_id__in=exclude_paragraph_list)
                    return qs
                if len(knowledge_id_list) == 1:
                    query_set = build_query_set(knowledge_id_list[0])
                    return search_handle.handle(
                        query_set, query_text, query_embedding, top_n, similarity, search_mode, knowledge_id_list
                    )
                else:
                    all_results = []
                    for kid in knowledge_id_list:
                        query_set = build_query_set(kid)
                        results = search_handle.handle(
                            query_set, query_text, query_embedding, top_n, similarity, search_mode, knowledge_id_list
                        )
                        all_results.extend(results)
                    all_results.sort(key=lambda x: x.get("similarity", x.get("comprehensive_score", 0)), reverse=True)
                    return all_results[:top_n]

    def update_by_source_id(self, source_id: str, instance: Dict):
        QuerySet(Embedding).filter(source_id=source_id).update(**instance)

    def update_by_paragraph_id(self, paragraph_id: str, instance: Dict):
        QuerySet(Embedding).filter(paragraph_id=paragraph_id).update(**instance)

    def update_by_paragraph_ids(self, paragraph_id: str, instance: Dict):
        QuerySet(Embedding).filter(paragraph_id__in=paragraph_id).update(**instance)

    def delete_by_knowledge_id(self, knowledge_id: str):
        QuerySet(Embedding).filter(knowledge_id=knowledge_id).delete()

    def delete_by_knowledge_id_list(self, knowledge_id_list: List[str]):
        QuerySet(Embedding).filter(knowledge_id__in=knowledge_id_list).delete()

    def delete_by_document_id(self, document_id: str):
        QuerySet(Embedding).filter(document_id=document_id).delete()
        return True

    def delete_by_document_id_list(self, document_id_list: List[str]):
        if len(document_id_list) == 0:
            return True
        return QuerySet(Embedding).filter(document_id__in=document_id_list).delete()

    def delete_by_source_id(self, source_id: str, source_type: str):
        QuerySet(Embedding).filter(source_id=source_id, source_type=source_type).delete()
        return True

    def delete_by_paragraph_id(self, paragraph_id: str):
        QuerySet(Embedding).filter(paragraph_id=paragraph_id).delete()

    def delete_by_paragraph_ids(self, paragraph_ids: List[str]):
        QuerySet(Embedding).filter(paragraph_id__in=paragraph_ids).delete()


class ISearch(ABC):
    @abstractmethod
    def support(self, search_mode: SearchMode):
        pass

    @abstractmethod
    def handle(
        self,
        query_set,
        query_text,
        query_embedding,
        top_number: int,
        similarity: float,
        search_mode: SearchMode,
        knowledge_id_list: list[str] = None,
    ):
        pass


class EmbeddingSearch(ISearch):
    def handle(
        self,
        query_set,
        query_text,
        query_embedding,
        top_number: int,
        similarity: float,
        search_mode: SearchMode,
        knowledge_id_list: list[str] = None,
    ):
        exec_sql, exec_params = generate_sql_by_query_dict(
            {"embedding_query": query_set},
            select_string=get_file_content(
                os.path.join(PROJECT_DIR, "apps", "knowledge", "sql", "embedding_search.sql")
            ),
            with_table_name=True,
        )
        embedding_model = select_list(
            exec_sql, [len(query_embedding), json.dumps(query_embedding), *exec_params, len(query_embedding),
                       len(query_embedding), json.dumps(query_embedding), top_number, similarity, top_number]
        )
        return embedding_model

    def support(self, search_mode: SearchMode):
        return search_mode.value == SearchMode.embedding.value


class KeywordsSearch(ISearch):
    def handle(
        self,
        query_set,
        query_text,
        query_embedding,
        top_number: int,
        similarity: float,
        search_mode: SearchMode,
        knowledge_id_list: list[str] = None,
    ):
        exec_sql, exec_params = generate_sql_by_query_dict(
            {"keywords_query": query_set},
            select_string=get_file_content(
                os.path.join(PROJECT_DIR, "apps", "knowledge", "sql", "keywords_search.sql")
            ),
            with_table_name=True,
        )
        terms = (
            list(QuerySet(Termbase).filter(knowledge_id__in=knowledge_id_list).values_list("content", flat=True))
            if knowledge_id_list
            else None
        )
        embedding_model = select_list(
            exec_sql, [to_query(query_text, user_words=terms), *exec_params, to_query(query_text, user_words=terms), similarity, top_number]
        )
        return embedding_model

    def support(self, search_mode: SearchMode):
        return search_mode.value == SearchMode.keywords.value


class BlendSearch(ISearch):
    def handle(
        self,
        query_set,
        query_text,
        query_embedding,
        top_number: int,
        similarity: float,
        search_mode: SearchMode,
        knowledge_id_list: list[str] = None,
    ):
        exec_sql, exec_params = generate_sql_by_query_dict(
            {"embedding_query": query_set},
            select_string=get_file_content(os.path.join(PROJECT_DIR, "apps", "knowledge", "sql", "blend_search.sql")),
            with_table_name=True,
        )
        terms = (
            list(QuerySet(Termbase).filter(knowledge_id__in=knowledge_id_list).values_list("content", flat=True))
            if knowledge_id_list
            else None
        )
        embedding_model = select_list(
            exec_sql,
            [
                len(query_embedding),
                json.dumps(query_embedding),
                *exec_params,
                len(query_embedding),
                len(query_embedding),
                json.dumps(query_embedding),
                top_number,
                to_query(query_text, user_words=terms),
                similarity,
                top_number,
            ],
        )
        return embedding_model

    def support(self, search_mode: SearchMode):
        return search_mode.value == SearchMode.blend.value


search_handle_list = [EmbeddingSearch(), KeywordsSearch(), BlendSearch()]
