from services.research.citations import MarkerResult, bind_markers, build_evidence, evidence_id


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

    def _meta(self, *cnts_ids):
        return {cnts_id: {"title": f"제목 {cnts_id}", "kci_citations": 3} for cnts_id in cnts_ids}

    def test_one_paper_one_evidence(self):
        ev = build_evidence([self._hit("A", "c1", 0.9)], self._meta("A"), chunks_per_evidence=2)
        assert len(ev) == 1
        assert ev[0].cnts_id == "A"
        assert ev[0].id == ""  # 번호는 runner 가 붙인다 — 여기서는 미할당

    def test_chunks_of_same_paper_group_into_one_evidence(self):
        ev = build_evidence(
            [self._hit("A", "c1", 0.9), self._hit("A", "c2", 0.7)],
            self._meta("A"), chunks_per_evidence=2,
        )
        assert len(ev) == 1
        assert len(ev[0].chunks) == 2

    def test_chunks_per_evidence_caps_and_keeps_best(self):
        ev = build_evidence(
            [self._hit("A", "c1", 0.5), self._hit("A", "c2", 0.9),
             self._hit("A", "c3", 0.7)],
            self._meta("A"), chunks_per_evidence=2,
        )
        assert [c.chunk_id for c in ev[0].chunks] == ["c2", "c3"]

    def test_hit_without_metadata_is_dropped(self):
        """카탈로그에 없는 청크는 근거로 쓰지 않는다 — 서지를 못 보여준다."""
        ev = build_evidence([self._hit("GHOST", "c1", 0.9)], {}, chunks_per_evidence=2)
        assert ev == []

    def test_return_order_follows_hit_appearance_order(self):
        """점수가 아니라 hits 등장 순서를 따른다 — sorted() 가 몰래 끼어들면 이 테스트가 잡는다."""
        ev = build_evidence(
            [self._hit("B", "c1", 0.5), self._hit("A", "c2", 0.9)],
            self._meta("A", "B"), chunks_per_evidence=2,
        )
        assert [e.cnts_id for e in ev] == ["B", "A"]

    def test_empty_hits_gives_empty_list(self):
        assert build_evidence([], {}, chunks_per_evidence=2) == []

    def test_chunks_per_evidence_zero_gives_no_chunks(self):
        ev = build_evidence([self._hit("A", "c1", 0.9)], self._meta("A"), chunks_per_evidence=0)
        assert ev[0].chunks == []


class TestBindMarkers:
    def test_valid_marker_is_kept(self):
        res = bind_markers("근거가 있다 [E1].", {"E1"})
        assert "[E1]" in res.text
        assert res.dropped == []

    def test_unknown_marker_is_dropped(self):
        """모델이 없는 근거를 지어내면 칩을 만들지 않는다."""
        res = bind_markers("근거가 있다 [E99].", {"E1"})
        assert "[E99]" not in res.text
        assert res.dropped == ["E99"]

    def test_dropping_does_not_leave_double_space(self):
        res = bind_markers("앞 [E99] 뒤.", {"E1"})
        assert "  " not in res.text

    def test_sentence_without_marker_is_counted(self):
        res = bind_markers("근거 있다 [E1]. 근거 없다.", {"E1"})
        assert res.unmarked == 1

    def test_sentence_whose_only_marker_was_dropped_counts_as_unmarked(self):
        res = bind_markers("지어낸 근거다 [E99].", {"E1"})
        assert res.dropped == ["E99"]
        assert res.unmarked == 1

    def test_empty_text(self):
        assert bind_markers("", {"E1"}) == MarkerResult("", [], [], 0)

    def test_used_ids_are_reported_in_order(self):
        res = bind_markers("가 [E2]. 나 [E1].", {"E1", "E2"})
        assert res.used == ["E2", "E1"]
        assert res.dropped == []
        assert res.unmarked == 0

    def test_trailing_marker_after_period_attributes_to_next_sentence(self):
        """정규화가 없어도 총합(unmarked)은 1로 같다 — 어느 문장이 무근거로
        지목되는지만 바뀐다. 정규화 유무를 가르는 회귀 테스트가 아니다.
        (그 검증은 test_trailing_marker_at_end_of_text_counts_as_marked 가 한다.)
        """
        res = bind_markers("근거 있다. [E1] 다른 말이다.", {"E1"})
        assert res.unmarked == 1  # "다른 말이다." 만 무근거

    def test_trailing_marker_at_end_of_text_counts_as_marked(self):
        """정규화 유무로 실제 값이 갈리는 케이스 — 뒤 문장이 없어 마커를
        당기지 않으면 "근거 있다." 자체가 무근거로 잘못 잡힌다."""
        res = bind_markers("근거 있다. [E1]", {"E1"})
        assert res.unmarked == 0

    def test_consecutive_trailing_markers_all_attribute_to_previous_sentence(self):
        """마커가 여럿 쌓여 있으면(". [E1] [E2]") 전부 앞 문장 근거로 봐야
        한다 — 하나만 당기면 뒤 마커가 다음 문장 소속으로 잘못 잡혀 과소
        계수된다."""
        res = bind_markers("문장이다. [E1] [E2] 다음 문장이다.", {"E1", "E2"})
        assert res.unmarked == 1  # "다음 문장이다." 만 무근거

    def test_trailing_marker_normalization_does_not_change_returned_text(self):
        res = bind_markers("근거 있다. [E1] 다른 말이다.", {"E1"})
        assert res.text == "근거 있다. [E1] 다른 말이다."

    def test_statistic_notation_is_preserved(self):
        """p < .05 같은 사회과학 논문의 선행 0 생략 표기를 훼손하면 안 된다."""
        res = bind_markers("유의수준 p < .05 였다 [E1].", {"E1"})
        assert "p < .05" in res.text

    def test_newline_is_preserved(self):
        res = bind_markers("첫 줄 [E1].\n둘째 줄.", {"E1"})
        assert "\n" in res.text
