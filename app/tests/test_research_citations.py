from services.research.citations import (
    MarkerResult, bind_markers, build_evidence, chunks_for, evidence_id, link_chunks,
    strip_markers,
)
from services.research.state import Chunk, Evidence, SubQuestion


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


class TestMarkerGrammar:
    """모델은 지시와 달리 묶음·범위·전각 표기를 낸다 — 검증을 우회하면 안 된다."""

    def test_grouped_markers_are_split_and_validated(self):
        res = bind_markers("측정돼 왔다 [E1, E2].", {"E1", "E2"})
        assert res.text == "측정돼 왔다 [E1] [E2]."
        assert res.used == ["E1", "E2"]
        assert res.dropped == []

    def test_invalid_id_inside_group_is_dropped(self):
        """묶음 속 없는 번호가 원문 그대로 실리면 인용 검증이 통째로 뚫린다."""
        res = bind_markers("측정돼 왔다 [E2, E99].", {"E1", "E2"})
        assert res.text == "측정돼 왔다 [E2]."
        assert res.dropped == ["E99"]
        assert res.used == ["E2"]

    def test_group_with_only_invalid_ids_is_removed(self):
        res = bind_markers("지어냈다 [E98,E99].", {"E1"})
        assert res.text == "지어냈다."
        assert res.dropped == ["E98", "E99"]

    def test_range_expands_to_valid_ids(self):
        res = bind_markers("연구가 있다 [E1-E3].", {"E1", "E2", "E3"})
        assert res.text == "연구가 있다 [E1] [E2] [E3]."
        assert res.used == ["E1", "E2", "E3"]

    def test_range_skips_ids_not_given_but_checks_endpoints(self):
        """범위 사이 번호는 모델이 실제로 쓴 번호가 아니다 — 끝점만 없는 번호로 센다."""
        res = bind_markers("연구가 있다 [E3~E9].", {"E3", "E7", "E12"})
        assert res.text == "연구가 있다 [E3] [E7]."
        assert res.dropped == ["E9"]

    def test_full_width_brackets_are_normalized(self):
        res = bind_markers("근거다 ［E1］ 【E2】.", {"E1", "E2"})
        assert res.text == "근거다 [E1] [E2]."
        assert res.used == ["E1", "E2"]

    def test_lowercase_and_zero_padded_ids_are_normalized(self):
        """[E01] 을 'E01' 로 대조하면 맞는 인용이 '없는 번호'로 오보된다."""
        res = bind_markers("근거다 [e1] [E02].", {"E1", "E2"})
        assert res.text == "근거다 [E1] [E2]."
        assert res.dropped == []

    def test_unparseable_marker_is_removed_and_reported(self):
        res = bind_markers("근거다 [E1 참조].", {"E1"})
        assert res.text == "근거다."
        assert res.unparsed == ["[E1 참조]"]
        assert res.dropped == []

    def test_non_citation_brackets_are_preserved(self):
        text = "표를 보면 [표 1] 과 [ICE 2019] 가 있다 [E1]."
        res = bind_markers(text, {"E1"})
        assert res.text == text
        assert res.unparsed == [] and res.dropped == []

    def test_grouped_marker_counts_as_marked_sentence(self):
        res = bind_markers("근거가 있다 [E1, E2]. 없다.", {"E1", "E2"})
        assert res.unmarked == 1

    def test_strip_markers_removes_grouped_and_unparseable(self):
        """요약은 bind_markers 를 안 거친다 — 묶음 표기가 남으면 검증 없이 나간다."""
        assert strip_markers("했다 [E1, E4]. 또 했다 ［E2］ [E3 참조].") == "했다. 또 했다."

    def test_strip_markers_keeps_non_citation_brackets(self):
        assert strip_markers("[표 1] 을 제시했다 [E1].") == "[표 1] 을 제시했다."

    def test_scientific_notation_in_brackets_is_preserved(self):
        """숫자 뒤 지수 표기 e 는 인용 E 가 아니다 — 지우면 수치가 사라지고
        한계에 '해석할 수 없는 인용 표기' 가 거짓으로 실린다."""
        text = "95% CI [1.2e3, 4.5e3] 이다 [E2]."
        res = bind_markers(text, {"E2"})
        assert res.text == text
        assert res.unparsed == [] and res.dropped == []

    def test_exponent_after_digit_is_not_a_citation(self):
        res = bind_markers("[n=2E5] 이다 [E1].", {"E1"})
        assert res.text == "[n=2E5] 이다 [E1]."
        assert res.unparsed == []

    def test_strip_markers_keeps_scientific_notation(self):
        assert strip_markers("표본 [N = 1.5E4] 이다 [E1].") == "표본 [N = 1.5E4] 이다."


class TestChunksFor:
    def _ev(self):
        return Evidence(id="E1", cnts_id="A", meta={}, chunks=[
            Chunk("a1", "가 대목", 1, 1, 0.9), Chunk("b1", "나 대목", 2, 2, 0.8),
        ])

    def test_returns_chunks_matched_in_that_subquestion(self):
        sq = SubQuestion(idx=1, text="나", evidence_chunks={"E1": ["b1"]})
        assert [c.chunk_id for c in chunks_for(self._ev(), sq)] == ["b1"]

    def test_falls_back_to_all_chunks_without_mapping(self):
        """매핑이 없는 옛 스냅샷도 재개할 수 있어야 한다."""
        sq = SubQuestion(idx=0, text="가")
        assert [c.chunk_id for c in chunks_for(self._ev(), sq)] == ["a1", "b1"]


class TestLinkChunks:
    """점수는 청크를 매칭한 하위질문의 검색어로 받은 값이다 — 같은 청크를 다른 하위질문이
    먼저 찾았어도 이 하위질문의 비교·발췌·호버는 자기 점수로 한다."""

    def _chunk(self, chunk_id, score):
        return Chunk(chunk_id, f"대목 {chunk_id}", 1, 1, score)

    def test_shared_chunk_keeps_each_subquestions_score(self):
        ev = Evidence(id="E1", cnts_id="P", meta={})
        a, b = SubQuestion(idx=0, text="A"), SubQuestion(idx=1, text="B")
        link_chunks(ev, a, [self._chunk("P-c1", 0.2)], limit=1)
        link_chunks(ev, b, [self._chunk("P-c1", 0.95)], limit=1)

        assert [(c.chunk_id, c.score) for c in chunks_for(ev, a)] == [("P-c1", 0.2)]
        assert [(c.chunk_id, c.score) for c in chunks_for(ev, b)] == [("P-c1", 0.95)]

    def test_research_compares_with_this_subquestions_score(self):
        """B 가 0.95 로 찾은 대목을 A 의 점수(0.2)로 비교하면 재검색의 0.5 짜리에 밀린다."""
        ev = Evidence(id="E1", cnts_id="P", meta={})
        a, b = SubQuestion(idx=0, text="A"), SubQuestion(idx=1, text="B")
        link_chunks(ev, a, [self._chunk("P-c1", 0.2)], limit=1)
        link_chunks(ev, b, [self._chunk("P-c1", 0.95)], limit=1)
        link_chunks(ev, b, [self._chunk("P-c2", 0.5)], limit=1)

        assert b.evidence_chunks == {"E1": ["P-c1"]}
        assert a.evidence_chunks == {"E1": ["P-c1"]}

    def test_evidence_level_score_is_the_best_match(self):
        """보고서 근거 목록에는 청크 하나에 점수 하나다 — 먼저 찾은 쪽이 아니라 최고값을 싣는다."""
        ev = Evidence(id="E1", cnts_id="P", meta={})
        link_chunks(ev, SubQuestion(idx=0, text="A"), [self._chunk("P-c1", 0.2)], limit=1)
        link_chunks(ev, SubQuestion(idx=1, text="B"), [self._chunk("P-c1", 0.95)], limit=1)

        assert [(c.chunk_id, c.score) for c in ev.chunks] == [("P-c1", 0.95)]

    def test_replaced_chunk_leaves_the_subquestion(self):
        ev = Evidence(id="E1", cnts_id="P", meta={})
        sq = SubQuestion(idx=0, text="가")
        link_chunks(ev, sq, [self._chunk("P-가", 0.3)], limit=1)
        link_chunks(ev, sq, [self._chunk("P-재1", 0.9)], limit=1)

        assert sq.evidence_chunks == {"E1": ["P-재1"]}
        assert sq.chunk_scores == {"P-재1": 0.9}

    def test_chunks_for_without_scores_uses_chunk_score(self):
        """점수 기록이 없는 옛 스냅샷은 Chunk.score 로 되돌아간다."""
        ev = Evidence(id="E1", cnts_id="P", meta={}, chunks=[self._chunk("P-c1", 0.7)])
        sq = SubQuestion(idx=0, text="가", evidence_chunks={"E1": ["P-c1"]})
        assert [c.score for c in chunks_for(ev, sq)] == [0.7]

    def test_chunks_for_does_not_mutate_the_evidence(self):
        ev = Evidence(id="E1", cnts_id="P", meta={})
        a, b = SubQuestion(idx=0, text="A"), SubQuestion(idx=1, text="B")
        link_chunks(ev, a, [self._chunk("P-c1", 0.2)], limit=1)
        link_chunks(ev, b, [self._chunk("P-c1", 0.95)], limit=1)
        chunks_for(ev, a)[0].score = -1.0
        assert ev.chunks[0].score == 0.95
