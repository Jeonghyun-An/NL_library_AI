import pytest

from services.research.explorer import rank_hits


class TestRankHits:
    def _hit(self, book_id, score):
        return {"book_id": book_id, "chunk_id": f"{book_id}-c", "text": "t",
                "page_start": 1, "page_end": 1, "score": score}

    def _meta(self, pub_date, citations):
        return {"title": "t", "pub_date": pub_date, "kci_citations": citations}

    def test_empty_input(self):
        assert rank_hits([], {}, citation_weight=0.2, now_year=2026) == []

    def test_missing_metadata_scores_as_zero_impact(self):
        hits = [self._hit("A", 0.9)]
        ranked = rank_hits(hits, {}, citation_weight=0.2, now_year=2026)
        assert ranked[0]["score"] == pytest.approx(0.9)

    def test_impact_reorders_close_scores(self):
        hits = [self._hit("OLD", 0.81), self._hit("NEW", 0.80)]
        meta = {
            "OLD": self._meta("2002-01", 50),    # 50/25 = 2.0
            "NEW": self._meta("2024-01", 40),    # 40/3  = 13.3
        }
        ranked = rank_hits(hits, meta, citation_weight=0.2, now_year=2026)
        assert ranked[0]["book_id"] == "NEW"

    def test_zero_weight_preserves_rerank_order(self):
        hits = [self._hit("OLD", 0.81), self._hit("NEW", 0.80)]
        meta = {"OLD": self._meta("2002-01", 50), "NEW": self._meta("2024-01", 40)}
        ranked = rank_hits(hits, meta, citation_weight=0.0, now_year=2026)
        assert ranked[0]["book_id"] == "OLD"

    def test_original_hits_are_not_mutated(self):
        hits = [self._hit("A", 0.9)]
        rank_hits(hits, {"A": self._meta("2008-01", 10)}, citation_weight=0.2, now_year=2026)
        assert hits[0]["score"] == pytest.approx(0.9)
