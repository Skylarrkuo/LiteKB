import unittest

from .fusion import fuse_candidates


def hit(pid, channel, dense, lexical):
    return {"paragraph_id": pid, "branch": channel, "dense_score": dense, "lexical_score": lexical}


class RankFusionTests(unittest.TestCase):
    def test_duplicate_embedding_rows_receive_one_vote_per_branch(self):
        rows = [hit("b", "dense", .8, .2), hit("a", "dense", .9, 0), hit("b", "dense", .7, .1),
                hit("b", "lexical", .8, .2), hit("c", "lexical", .1, .3)]
        ranked = fuse_candidates(rows, 3)
        self.assertEqual([r["paragraph_id"] for r in ranked], ["b", "a", "c"])
        self.assertAlmostEqual(ranked[0]["rank_score"], 2 / 62)
        self.assertEqual(ranked[0]["score"], 1.0)
        self.assertEqual(fuse_candidates(rows[::-1], 3), ranked)
        self.assertEqual(fuse_candidates(rows, 3, min_score=1), [])

    def test_unusable_dense_vector_allows_lexical_vote_and_uses_evidence_threshold(self):
        rows = [hit("invalid", "dense", float("nan"), 0), hit("match", "lexical", float("nan"), .2)]
        self.assertEqual(fuse_candidates(rows, 3), [{"paragraph_id": "match", "rank_score": 1 / 61, "score": .2}])
        self.assertEqual(fuse_candidates(rows, 3, min_score=.2), [])

    def test_global_window_and_uuid_tie_break_do_not_depend_on_knowledge_iteration_order(self):
        rows = [hit(str(i), "dense", 1 - i * .01, 0) for i in range(25)]
        rows.extend([hit("x", "lexical", .99, .1), hit("y", "lexical", .99, .1)])
        ranked = fuse_candidates(rows, 2)
        self.assertEqual([r["paragraph_id"] for r in ranked], ["x", "0"])
        self.assertEqual(ranked, fuse_candidates(rows[::-1], 2))
