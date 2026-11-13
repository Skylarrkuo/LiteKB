"""Evaluate labeled paragraph retrieval from saved rankings, PostgreSQL or a LiteKB API."""
import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SQL = ROOT / "apps" / "knowledge" / "sql"
MODES = ("embedding", "keywords", "blend", "rrf")
sys.path.insert(0, str(ROOT / "apps"))


def read_jsonl(name):
    return [json.loads(line) for line in (HERE / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def document_key(doc_id):
    return uuid5(NAMESPACE_URL, "urn:litekb:retrieval-fixture:" + doc_id)


def make_archive(corpus):
    return {"format": "litekb.knowledge.v1", "tags": [], "documents": [
        {"key": str(document_key(d["id"])), "name": d["id"], "is_active": True, "tags": [],
         "paragraphs": [{"title": "", "content": d["text"], "is_active": True, "questions": []}]}
        for d in corpus]}


def latent_vectors(corpus, queries):
    """Fit a 12-component TF-IDF LSA only on the unlabeled passage text."""
    import numpy as np

    def tokens(text):
        terms = []
        for sequence in re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", text.lower()):
            if sequence.isascii():
                terms.append(sequence)
            else:
                terms.extend(sequence)
                terms.extend(sequence[i:i + 2] for i in range(len(sequence) - 1))
        return Counter(terms)

    docs = [tokens(d["text"]) for d in corpus]
    vocab = sorted({term for doc in docs for term in doc})
    idf = np.log((len(docs) + 1) / (1 + np.array([sum(term in doc for doc in docs) for term in vocab]))) + 1

    def matrix(bags):
        features = np.log1p(np.array([[b[term] for term in vocab] for b in bags])) * idf
        return features / np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-12)

    train = matrix(docs)
    _, _, basis = np.linalg.svd(train, full_matrices=False)

    def encode(rows):
        projected = rows @ basis[:12].T
        # A query with no corpus vocabulary is orthogonal to all passages.
        return np.column_stack((projected, np.linalg.norm(projected, axis=1) < 1e-12)).tolist()

    return encode(train), encode(matrix([tokens(q["query"]) for q in queries]))


def postgres_run(corpus, queries, k):
    import psycopg
    from psycopg.rows import dict_row
    from common.utils.ts_vecto_util import to_query, to_ts_vector
    from knowledge.vector.fusion import candidate_window, fuse_candidates

    doc_vectors, query_vectors = latent_vectors(corpus, queries)
    doc_map = {document_key(d["id"]): d["id"] for d in corpus}
    kb = document_key("fixture")
    template = {mode: (SQL / (mode + "_search.sql")).read_text().replace(
        "${keywords_query}" if mode == "keywords" else "${embedding_query}", "WHERE knowledge_id = %s AND is_active")
                for mode in MODES if mode != "rrf"}
    rrf_sql = (SQL / "rrf_candidates.sql").read_text()
    rankings = {}
    with psycopg.connect(os.getenv("LITEKB_BENCH_DSN", ""), cursor_factory=psycopg.ClientCursor,
                         row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL search_path TO pg_temp, public")
        cur.execute("CREATE TEMP TABLE document (id uuid PRIMARY KEY, knowledge_id uuid, is_active boolean)")
        cur.execute("CREATE TEMP TABLE paragraph (id uuid PRIMARY KEY, knowledge_id uuid, document_id uuid, "
                    "is_active boolean)")
        cur.execute("CREATE TEMP TABLE embedding (id uuid PRIMARY KEY, knowledge_id uuid, document_id uuid, "
                    "paragraph_id uuid, is_active boolean, embedding vector, search_vector tsvector)")
        for d, vector in zip(corpus, doc_vectors, strict=True):
            pid = document_key(d["id"])
            cur.execute("INSERT INTO pg_temp.document VALUES (%s,%s,true)", (pid, kb))
            cur.execute("INSERT INTO pg_temp.paragraph VALUES (%s,%s,%s,true)", (pid, kb, pid))
            cur.execute("INSERT INTO pg_temp.embedding VALUES (%s,%s,%s,%s,true,%s,to_tsvector('simple',%s))",
                        (pid, kb, pid, pid, json.dumps(vector), to_ts_vector(d["text"])))
        for q, vector in zip(queries, query_vectors, strict=True):
            size = len(vector)
            value = json.dumps(vector)
            terms = to_query(q["query"])
            dense_params = [size, value, kb, size, size, value, k]
            params = {"embedding": [*dense_params, 0, k], "blend": [*dense_params, terms, 0, k],
                      "keywords": [terms, kb, terms, 0, k]}
            by_mode = {}
            for mode in params:
                cur.execute(template[mode], params[mode])
                by_mode[mode] = [doc_map[r["paragraph_id"]] for r in cur.fetchall()]
            window = candidate_window(k)
            cur.execute(rrf_sql, [kb, size, None, [], [], terms, size, value, window, window, value])
            by_mode["rrf"] = [doc_map[r["paragraph_id"]] for r in fuse_candidates(cur.fetchall(), k)]
            rankings[q["id"]] = by_mode
    return rankings


def api_run(queries, k, base_url, kb):
    import requests

    key = os.environ["LITEKB_SERVICE_KEY"]
    rankings = {}
    for q in queries:
        rankings[q["id"]] = {}
        for mode in MODES:
            payload = {"query": q["query"], "knowledge_base_ids": [kb], "top_k": k, "mode": mode, "min_score": 0}
            response = requests.post(base_url.rstrip("/") + "/v1/retrievals", json=payload,
                                     headers={"Authorization": "Bearer " + key}, timeout=90, allow_redirects=False)
            response.raise_for_status()
            rankings[q["id"]][mode] = [row["document_name"] for row in response.json()["hits"]]
    return rankings


def measures(qrels, docs, k):
    grades = [qrels.get(doc, 0) for doc in docs[:k]]
    rank = next((i for i, grade in enumerate(grades, 1) if grade > 0), None)

    def dcg(order):
        return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(order))

    return (sum(g > 0 for g in grades) / len(qrels), 1.0 / rank if rank else 0.0,
            dcg(grades) / dcg(sorted(qrels.values(), reverse=True)[:k]))


def report(queries, rankings, corpus_ids, k):
    if set(rankings) != {q["id"] for q in queries}:
        raise ValueError("Saved rankings must cover all queries")
    print(f"group        mode         Recall@{k}    MRR@{k}   nDCG@{k}")
    for group in ["all", *dict.fromkeys(q["group"] for q in queries)]:
        subset = [q for q in queries if group == "all" or q["group"] == group]
        for mode in MODES:
            scores = []
            for q in subset:
                found = rankings[q["id"]][mode]
                if set(found) - corpus_ids or len(found) != len(set(found)):
                    raise ValueError(f"Unexpected/duplicate fixture document for {q['id']}: {found}")
                scores.append(measures(q["qrels"], found, k))
            means = [sum(column) / len(subset) for column in zip(*scores)]
            print(f"{group:12s} {mode:11s}" + "".join(f"{v:9.4f}" for v in means))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--postgres", action="store_true", help="Use libpq environment or LITEKB_BENCH_DSN")
    source.add_argument("--api", metavar="BASE_URL", help="Retrieve with the deployed embedding model")
    source.add_argument("--archive", type=Path, help="Write import JSON for the API benchmark")
    source.add_argument("--replay", type=Path, default=HERE / "rankings.json", help="Saved run to score")
    parser.add_argument("--kb", help="Dedicated fixture knowledge base UUID for --api")
    parser.add_argument("--save", type=Path, help="Save ranking lists from a fresh run")
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()
    corpus = read_jsonl("corpus.jsonl")
    queries = read_jsonl("queries.jsonl")
    ids = {d["id"] for d in corpus}
    if (len(ids) != len(corpus) or len({q["id"] for q in queries}) != len(queries)
            or any(not q["qrels"] or set(q["qrels"]) - ids or set(q["qrels"].values()) - {1, 2} for q in queries)):
        parser.error("Invalid corpus or relevance judgments")
    if args.archive:
        args.archive.write_text(json.dumps(make_archive(corpus), ensure_ascii=False), encoding="utf-8")
        return
    if not 1 <= args.k <= 100:
        parser.error("--k must be between 1 and 100")
    if args.postgres:
        rankings = postgres_run(corpus, queries, args.k)
    elif args.api:
        if not args.kb:
            parser.error("--api requires --kb")
        rankings = api_run(queries, args.k, args.api, args.kb)
    else:
        saved = json.loads(args.replay.read_text(encoding="utf-8"))
        if args.k != saved["k"]:
            parser.error("The saved rankings use a different k; run a fresh evaluation")
        rankings = saved["rankings"]
    if args.save:
        args.save.write_text(json.dumps({"k": args.k, "rankings": rankings}, indent=2) + "\n", encoding="utf-8")
    report(queries, rankings, ids, args.k)


if __name__ == "__main__":
    main()
