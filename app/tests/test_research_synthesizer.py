from services.research.state import Chunk, Evidence, ResearchState, SubQuestion, merge_params
from services.research.synthesizer import assemble_report, build_limitations


def _state():
    st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
    st.subquestions = [
        SubQuestion(idx=0, text="하위1", evidence_ids=["E1"],
                    verdict="sufficient", note="충분하다"),
        SubQuestion(idx=1, text="하위2", evidence_ids=[],
                    verdict="insufficient", note="2015년 이후 자료가 없다"),
    ]
    st.evidence = {
        "E1": Evidence(id="E1", cnts_id="A", meta={"title": "논문 가", "pub_date": "2008-06"},
                       chunks=[Chunk("c1", "본문", 3, 3, 0.9)]),
    }
    return st


class TestBuildLimitations:
    def test_insufficient_subquestion_is_reported(self):
        lims = build_limitations(_state(), unmarked_total=0, dropped_total=0)
        assert any("하위2" in x for x in lims)
        assert any("2015년 이후 자료가 없다" in x for x in lims)

    def test_sufficient_subquestion_is_not_reported(self):
        assert not any("하위1" in x
                       for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))

    def test_no_evidence_subquestion_is_reported(self):
        assert any("근거를 찾지 못했다" in x
                   for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))

    def test_failed_subquestion_is_not_reported_as_missing_evidence(self):
        """탐색이 예외로 죽은 하위질문을 "근거를 찾지 못했다"로 쓰면 안 된다.

        그건 연구 결과처럼 읽히는 시스템 장애다. 코퍼스에 자료가 없는 것과
        우리 쪽이 터진 것은 사용자에게 완전히 다른 정보이고, 이 기능의 값이
        "모른다고 정직하게 말하는 것"인데 장애를 발견으로 포장하면 무너진다.
        """
        st = _state()
        st.subquestions[1].failed = True
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        assert any("하위2" in x and "오류로 확인하지 못했다" in x for x in lims)
        assert not any("하위2" in x and "근거를 찾지 못했다" in x for x in lims)

    def test_failed_subquestion_with_evidence_is_still_reported(self):
        # 근거를 좀 모은 뒤 죽은 경우 — evidence_ids 가 비지 않아도 실패는 실패다
        st = _state()
        st.subquestions[0].failed = True
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        assert any("하위1" in x and "오류로 확인하지 못했다" in x for x in lims)

    def test_healthy_subquestion_is_not_reported_as_failed(self):
        assert not any("오류로 확인하지 못했다" in x
                       for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))

    def test_unmarked_sentences_are_reported(self):
        lims = build_limitations(_state(), unmarked_total=4, dropped_total=0)
        assert any("근거 표기가 없는 서술 4건" in x for x in lims)

    def test_parse_failed_subquestion_is_reported(self):
        """판정 실패는 verdict=sufficient 로 떨어지므로 따로 세지 않으면 사라진다."""
        st = _state()
        st.subquestions[0].parse_failed = True
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        assert any("자동 점검을 완료하지 못한 하위질문이 1건" in x for x in lims)

    def test_no_parse_failure_is_not_reported(self):
        assert not any("자동 점검을 완료하지 못한" in x
                       for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))

    def test_zero_unmarked_is_not_reported(self):
        assert not any("근거 표기가 없는" in x
                       for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))

    def test_single_unmarked_sentence_is_tolerated(self):
        """마커 없는 문장은 연결 문장일 때가 많아 몇 건은 넘긴다.

        없는 번호를 가리킨 표기(dropped)와 한 문장으로 합치면 이 관용이
        사라지거나, 반대로 지어낸 번호가 임계값에 묻힌다.
        """
        assert not any("근거 표기가 없는" in x
                       for x in build_limitations(_state(), unmarked_total=1, dropped_total=0))

    def test_dropped_marker_is_reported_at_one(self):
        """지어낸 근거 번호는 1건부터 보고한다 — 인용 설계가 잡으려는 실패가 이것이다."""
        lims = build_limitations(_state(), unmarked_total=0, dropped_total=1)
        assert any("존재하지 않는 근거 번호" in x and "1건" in x for x in lims)

    def test_zero_dropped_is_not_reported(self):
        assert not any("존재하지 않는 근거 번호" in x
                       for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))


class TestAssembleReport:
    def test_sections_match_subquestions(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "하위1", "intro": "도입 [E1].",
                       "papers": [{"cnts_id": "A", "summary": "요약"}],
                       "future": [{"text": "과제 [E1]."}]}],
            unmarked_total=0,
        )
        assert len(report["sections"]) == 1
        assert report["sections"][0]["papers"][0]["evidence"] == ["E1"]

    def test_paper_bullet_evidence_is_structural(self):
        """대표 논문 요약의 인용은 모델이 고르는 게 아니라 cnts_id 로 정해진다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "", "papers": [{"cnts_id": "A", "summary": "s"}],
                       "future": []}],
            unmarked_total=0,
        )
        assert report["sections"][0]["papers"][0]["evidence"] == ["E1"]

    def test_unknown_marker_in_intro_is_stripped(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "지어냈다 [E99].", "papers": [], "future": []}],
            unmarked_total=0,
        )
        assert "[E99]" not in report["sections"][0]["intro"]
        assert any("존재하지 않는 근거 번호" in x and "1건" in x for x in report["limitations"])

    def test_unknown_marker_in_future_is_stripped(self):
        """향후 과제도 마커 인용이다 — 도입만 세면 이쪽이 조용히 빠져나간다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "", "papers": [],
                       "future": [{"text": "과제 [E99]."}]}],
            unmarked_total=0,
        )
        assert "[E99]" not in report["sections"][0]["future"][0]["text"]
        assert any("존재하지 않는 근거 번호" in x and "1건" in x for x in report["limitations"])

    def test_dropped_markers_accumulate_across_call_sites(self):
        """bind_markers 는 섹션마다 여러 번 불린다 — 한 번의 반환값만 읽으면 과소 계수된다."""
        report = assemble_report(
            _state(),
            sections=[
                {"heading": "h1", "intro": "가 [E98].", "papers": [], "future": []},
                {"heading": "h2", "intro": "", "papers": [],
                 "future": [{"text": "나 [E99]."}]},
            ],
            unmarked_total=0,
        )
        assert any("존재하지 않는 근거 번호" in x and "2건" in x for x in report["limitations"])

    def test_same_unknown_marker_twice_counts_twice(self):
        """사용자에게 보이는 단위는 본문의 표기 수다 — 서로 다른 번호의 수가 아니다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "가 [E99]. 나 [E99].",
                       "papers": [], "future": []}],
            unmarked_total=0,
        )
        assert any("존재하지 않는 근거 번호" in x and "2건" in x for x in report["limitations"])

    def test_valid_markers_are_not_reported_as_dropped(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "도입 [E1].", "papers": [],
                       "future": [{"text": "과제 [E1]."}]}],
            unmarked_total=0,
        )
        assert not any("존재하지 않는 근거 번호" in x for x in report["limitations"])

    def test_evidence_is_serialized(self):
        report = assemble_report(_state(), sections=[], unmarked_total=0)
        assert report["evidence"]["E1"]["chunks"][0]["page_start"] == 3
        assert report["evidence"]["E1"]["cnts_id"] == "A"

    def test_trail_comes_from_subquestions(self):
        report = assemble_report(_state(), sections=[], unmarked_total=0)
        assert [t["subquestion"] for t in report["trail"]] == ["하위1", "하위2"]

    def test_corpus_range_is_carried_into_report(self):
        """수록 범위는 고정 문구가 아니라 실행 시점 실측값이다."""
        st = _state()
        st.corpus_range = {"from": "2002", "to": "2026", "n_papers": 72054}
        report = assemble_report(st, sections=[], unmarked_total=0)
        assert report["range"]["n_papers"] == 72054

    def test_missing_corpus_range_is_none(self):
        assert assemble_report(_state(), sections=[], unmarked_total=0)["range"] is None
