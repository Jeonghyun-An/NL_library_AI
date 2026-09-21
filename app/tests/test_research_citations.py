from services.research.state import Chunk, Evidence
from services.research.citations import bind_markers, build_evidence, evidence_id


class TestEvidenceId:
    def test_format(self):
        assert evidence_id(0) == "E1"
        assert evidence_id(11) == "E12"


class TestBuildEvidence:
    def _hit(self, cnts_id, chunk_id, score, page=1):
        return {
            "book_id": cnts_id, "chunk_id": chunk_id, "text": f"본문 {chunk_id}",
            "page_start": page, "page_end": page, "score": score,
        }

    def _meta(self, cnts_id):
        return {cnts_id: {"title": f"제목 {cnts_id}", "kci_citations": 3}}

    def test_one_paper_one_evidence(self):
        ev = build_evidence(
            [self._hit("A", "c1", 0.9)], self._meta("A"),
            start_index=0, chunks_per_evidence=2,
        )
        assert list(ev.keys()) == ["E1"]
        assert ev["E1"].cnts_id == "A"

    def test_chunks_of_same_paper_group_into_one_evidence(self):
        ev = build_evidence(
            [self._hit("A", "c1", 0.9), self._hit("A", "c2", 0.7)],
            self._meta("A"), start_index=0, chunks_per_evidence=2,
        )
        assert len(ev) == 1
        assert len(ev["E1"].chunks) == 2

    def test_chunks_per_evidence_caps_and_keeps_best(self):
        ev = build_evidence(
            [self._hit("A", "c1", 0.5), self._hit("A", "c2", 0.9),
             self._hit("A", "c3", 0.7)],
            self._meta("A"), start_index=0, chunks_per_evidence=2,
        )
        assert [c.chunk_id for c in ev["E1"].chunks] == ["c2", "c3"]

    def test_start_index_continues_numbering(self):
        ev = build_evidence(
            [self._hit("B", "c9", 0.8)], self._meta("B"),
            start_index=5, chunks_per_evidence=2,
        )
        assert list(ev.keys()) == ["E6"]

    def test_hit_without_metadata_is_dropped(self):
        """카탈로그에 없는 청크는 근거로 쓰지 않는다 — 서지를 못 보여준다."""
        ev = build_evidence(
            [self._hit("GHOST", "c1", 0.9)], {}, start_index=0, chunks_per_evidence=2,
        )
        assert ev == {}


class TestBindMarkers:
    def test_valid_marker_is_kept(self):
        text, dropped, unmarked = bind_markers("근거가 있다 [E1].", {"E1"})
        assert "[E1]" in text
        assert dropped == []

    def test_unknown_marker_is_dropped(self):
        """모델이 없는 근거를 지어내면 칩을 만들지 않는다."""
        text, dropped, unmarked = bind_markers("근거가 있다 [E99].", {"E1"})
        assert "[E99]" not in text
        assert dropped == ["E99"]

    def test_dropping_does_not_leave_double_space(self):
        text, _, _ = bind_markers("앞 [E99] 뒤.", {"E1"})
        assert "  " not in text

    def test_sentence_without_marker_is_counted(self):
        _, _, unmarked = bind_markers("근거 있다 [E1]. 근거 없다.", {"E1"})
        assert unmarked == 1

    def test_sentence_whose_only_marker_was_dropped_counts_as_unmarked(self):
        _, dropped, unmarked = bind_markers("지어낸 근거다 [E99].", {"E1"})
        assert dropped == ["E99"]
        assert unmarked == 1

    def test_empty_text(self):
        assert bind_markers("", {"E1"}) == ("", [], 0)

    def test_used_ids_are_reported_in_order(self):
        text, dropped, unmarked = bind_markers("가 [E2]. 나 [E1].", {"E1", "E2"})
        assert dropped == []
        assert unmarked == 0
