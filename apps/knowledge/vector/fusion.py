"""Paragraph-level reciprocal rank fusion of independent candidate lists."""
from math import isfinite


def candidate_window(top_k):
    return min(top_k * 10, 500)


def fuse_candidates(rows, top_k, min_score=0):
    """Merge all authorized KBs, allowing one vote per paragraph per retriever."""
    branches = {"dense": {}, "lexical": {}}
    evidence = {}
    for row in rows:
        paragraph = row["paragraph_id"]
        dense = float(row["dense_score"])
        lexical = float(row["lexical_score"])
        if not isfinite(lexical):
            continue
        if not isfinite(dense):
            if row["branch"] == "dense":
                continue
            dense = 0.0  # A zero vector cannot vote for cosine, but an exact FTS match still can.
        evidence[paragraph] = max(evidence.get(paragraph, float("-inf")), dense + lexical)
        branch = branches[row["branch"]]
        score = dense if row["branch"] == "dense" else lexical
        branch[paragraph] = max(branch.get(paragraph, float("-inf")), score)

    votes = {}
    for branch in branches.values():
        ranked = sorted(branch, key=lambda pid: (-branch[pid], str(pid)))[:candidate_window(top_k)]
        for rank, pid in enumerate(ranked, 1):
            votes[pid] = votes.get(pid, 0.0) + 1.0 / (60 + rank)
    result = [{"paragraph_id": pid, "rank_score": vote, "score": evidence[pid]}
              for pid, vote in votes.items() if evidence[pid] > min_score]
    return sorted(result, key=lambda row: (-row["rank_score"], -row["score"], str(row["paragraph_id"])))[:top_k]
