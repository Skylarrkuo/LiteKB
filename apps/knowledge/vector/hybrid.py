import json
from pathlib import Path

from common.db.sql_execute import select_list
from common.utils.ts_vecto_util import to_query
from knowledge.models import Termbase
from knowledge.vector.fusion import candidate_window, fuse_candidates


CANDIDATE_SQL = (Path(__file__).resolve().parents[1] / "sql" / "rrf_candidates.sql").read_text(encoding="utf-8")


def paragraph_candidates(knowledge_id, question, query_vector, top_k, documents=None,
                         excluded_documents=None, excluded_paragraphs=None):
    terms = list(Termbase.objects.filter(knowledge_id=knowledge_id).values_list("content", flat=True))
    vector = json.dumps([float(value) for value in query_vector], allow_nan=False)
    window = candidate_window(top_k)
    return select_list(CANDIDATE_SQL, [knowledge_id, len(query_vector), documents,
                                       excluded_documents or [], excluded_paragraphs or [],
                                       to_query(question, user_words=terms),
                                       len(query_vector), vector, window, window, vector])


def ranked_paragraphs(vectors_by_knowledge, question, top_k, min_score, documents=None,
                      excluded_documents=None, excluded_paragraphs=None):
    candidates = []
    for kid, vector in vectors_by_knowledge.items():
        candidates.extend(paragraph_candidates(kid, question, vector, top_k, documents,
                                               excluded_documents, excluded_paragraphs))
    return fuse_candidates(candidates, top_k, min_score)
