import asyncio
import json

import httpx
import pytest

from services.research import synthesizer
from services.research.state import Chunk, Evidence, ResearchState, SubQuestion, merge_params
from services.research.synthesizer import (
    PAPERS_PER_SECTION, SynthesisCanceled, assemble_report, build_limitations, build_section,
    synthesize,
)

_DROPPED = "그 절의 근거에 없는 번호"


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
        # 근거를 좀 모은 뒤 죽은 경우 — 근거는 절에 싣되 중단 사실은 알린다
        st = _state()
        st.subquestions[0].failed = True
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        assert any("하위1" in x and "오류로 중단" in x and "1편" in x for x in lims)

    def test_capped_subquestion_is_not_reported_as_missing_evidence(self):
        """근거 상한에 막힌 것을 '근거를 찾지 못했다'로 쓰면 시스템 상한이
        코퍼스 빈틈으로 둔갑한다 — critic 의 note('관련 논문이 없다')도 오보다."""
        st = _state()
        st.subquestions[1].capped = 7
        st.subquestions[1].note = "관련 논문이 없다"
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        line = next(x for x in lims if "하위2" in x)
        assert "근거 상한(60편)" in line and "7편" in line
        assert "근거를 찾지 못했다" not in line and "관련 논문이 없다" not in line

    def test_capped_insufficient_subquestion_mentions_cap(self):
        st = _state()
        st.subquestions[0].verdict = "insufficient"
        st.subquestions[0].capped = 2
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        line = next(x for x in lims if "하위1" in x)
        assert "결론이 약하다" in line and "근거 상한" in line and "2편" in line

    def test_unchecked_subquestion_without_evidence_is_not_counted_twice(self):
        """근거가 0편이면 충분성을 따질 대상이 없다 — '못 찾았다'와 '점검 못 함'을 둘 다 쓰지 않는다."""
        st = _state()
        st.subquestions[1].parse_failed = True
        st.subquestions[1].note = "자동 점검을 완료하지 못했다"
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        assert not any("자동 점검을 완료하지 못한 하위질문" in x for x in lims)
        assert not any("하위2" in x and "자동 점검" in x for x in lims)

    def test_unparsed_markers_are_reported(self):
        lims = build_limitations(_state(), unmarked_total=0, dropped_total=0, unparsed_total=2)
        assert any("해석할 수 없는 인용 표기 2건" in x for x in lims)

    def test_introless_sections_are_reported(self):
        lims = build_limitations(_state(), unmarked_total=0, dropped_total=0,
                                 introless_sections=1)
        assert any("도입 문단을 생성하지 못한 절이 1개" in x for x in lims)

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
        assert any(_DROPPED in x and "1건" in x for x in lims)

    def test_zero_dropped_is_not_reported(self):
        assert not any(_DROPPED in x
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
        assert any(_DROPPED in x and "1건" in x for x in report["limitations"])

    def test_unknown_marker_in_future_is_stripped(self):
        """향후 과제도 마커 인용이다 — 도입만 세면 이쪽이 조용히 빠져나간다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "", "papers": [],
                       "future": [{"text": "과제 [E99]."}]}],
            unmarked_total=0,
        )
        assert "[E99]" not in report["sections"][0]["future"][0]["text"]
        assert any(_DROPPED in x and "1건" in x for x in report["limitations"])

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
        assert any(_DROPPED in x and "2건" in x for x in report["limitations"])

    def test_same_unknown_marker_twice_counts_twice(self):
        """사용자에게 보이는 단위는 본문의 표기 수다 — 서로 다른 번호의 수가 아니다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "가 [E99]. 나 [E99].",
                       "papers": [], "future": []}],
            unmarked_total=0,
        )
        assert any(_DROPPED in x and "2건" in x for x in report["limitations"])

    def test_valid_markers_are_not_reported_as_dropped(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "도입 [E1].",
                       "papers": [{"cnts_id": "A", "summary": "s"}],
                       "future": [{"text": "과제 [E1]."}]}],
            unmarked_total=0,
        )
        assert not any(_DROPPED in x for x in report["limitations"])

    def test_marker_outside_section_evidence_is_dropped(self):
        """모델은 절마다 그 절의 근거만 받는다 — 다른 절의 번호는 본 적 없는 논문이다.

        근거 번호가 E1..En 으로 연속 발급되므로 전역 집합으로 검증하면 지어낸 작은
        번호가 거의 다 통과한다.
        """
        st = _state_three()
        report = assemble_report(
            st,
            sections=[{"heading": "하위2", "intro": "평가 지표가 제안되었다 [E1] [E3].",
                       "papers": [{"cnts_id": "B", "summary": "s"}, {"cnts_id": "C", "summary": "s"}],
                       "future": [{"text": "과제 [E1]."}]}],
            unmarked_total=0,
        )
        sec = report["sections"][0]
        assert "[E1]" not in sec["intro"] and "[E3]" in sec["intro"]
        assert sec["future"][0]["evidence"] == []
        assert any(_DROPPED in x and "2건" in x for x in report["limitations"])

    def test_unparsed_markers_are_counted_across_sections(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "도입 [E1 참조].",
                       "papers": [{"cnts_id": "A", "summary": "s"}],
                       "future": [{"text": "과제 [E1: 표 2]."}]}],
            unmarked_total=0,
        )
        assert any("해석할 수 없는 인용 표기 2건" in x for x in report["limitations"])

    def test_failed_section_papers_are_not_counted_as_unsummarized(self):
        """절 서술이 통째로 실패하면 '서술 못 한 절 1개' 하나로 보고한다 — 요약 N편으로 또 세면 실패가 두 건처럼 보인다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "", "failed": True, "future": [],
                       "papers": [{"cnts_id": "A", "summary": ""}]}],
            unmarked_total=0,
        )
        assert any("서술을 생성하지 못한 절이 1개" in x for x in report["limitations"])
        assert not any("요약을 생성하지 못한 논문" in x for x in report["limitations"])
        assert not any("도입 문단을 생성하지 못한" in x for x in report["limitations"])

    def test_introless_section_is_reported(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "", "future": [],
                       "papers": [{"cnts_id": "A", "summary": "요약"}]}],
            unmarked_total=0,
        )
        assert any("도입 문단을 생성하지 못한 절이 1개" in x for x in report["limitations"])

    def test_section_evidence_chunks_are_carried(self):
        """호버가 그 절에서 매칭된 대목을 띄우려면 절마다 청크 참조가 있어야 한다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "도입 [E1].", "future": [],
                       "papers": [{"cnts_id": "A", "summary": "s"}],
                       "evidence_chunks": {"E1": ["c1"]}}],
            unmarked_total=0,
        )
        assert report["sections"][0]["evidence_chunks"] == {"E1": ["c1"]}

    def test_markers_in_paper_summary_are_stripped(self):
        """요약은 bind_markers 를 안 거친다 — 남기면 지어낸 번호가 검증 없이 나간다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "", "future": [],
                       "papers": [{"cnts_id": "A", "summary": "무엇을 했다 [E1]. 또 했다 [E99]."}]}],
            unmarked_total=0,
        )
        assert report["sections"][0]["papers"][0]["summary"] == "무엇을 했다. 또 했다."

    def test_marker_only_future_item_is_dropped_but_counted(self):
        """마커만 있던 과제는 번호를 지우면 빈 불릿이다 — 싣지 않고, 지운 번호는 한계에 남긴다."""
        st = _state_three()
        report = assemble_report(
            st,
            sections=[{"heading": "하위1", "intro": "도입 [E1].",
                       "papers": [{"cnts_id": "A", "summary": "s"}, {"cnts_id": "B", "summary": "s"}],
                       "future": [{"text": "[E7]"}, {"text": "과제 [E1]."}]}],
            unmarked_total=0,
        )
        assert report["sections"][0]["future"] == [{"text": "과제 [E1].", "evidence": ["E1"]}]
        assert any(_DROPPED in x and "1건" in x for x in report["limitations"])

    def test_citation_only_future_item_is_dropped(self):
        """유효한 번호뿐인 과제도 문장이 없다 — 칩 하나짜리 불릿이 된다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "도입 [E1].",
                       "papers": [{"cnts_id": "A", "summary": "s"}],
                       "future": [{"text": "[E1]"}]}],
            unmarked_total=0,
        )
        assert report["sections"][0]["future"] == []

    def test_citation_only_intro_counts_as_introless(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "[E1]", "future": [],
                       "papers": [{"cnts_id": "A", "summary": "요약"}]}],
            unmarked_total=0,
        )
        assert report["sections"][0]["intro"] == ""
        assert any("도입 문단을 생성하지 못한 절이 1개" in x for x in report["limitations"])

    def test_marker_with_period_summary_is_not_a_summary(self):
        """번호를 걷고 마침표 하나만 남은 요약을 실으면 화면에 '.' 이 요약으로 나간다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "도입 [E1].", "future": [],
                       "papers": [{"cnts_id": "A", "summary": "[E1]."}]}],
            unmarked_total=0,
        )
        assert report["sections"][0]["papers"][0]["summary"] == ""
        assert any("요약을 생성하지 못한 논문 1편" in x for x in report["limitations"])

    def test_marker_only_summary_counts_as_unsummarized(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "", "future": [],
                       "papers": [{"cnts_id": "A", "summary": "[E1]"}]}],
            unmarked_total=0,
        )
        assert any("요약을 생성하지 못한 논문 1편" in x for x in report["limitations"])

    def test_evidence_is_serialized(self):
        report = assemble_report(_state(), sections=[], unmarked_total=0)
        assert report["evidence"]["E1"]["chunks"][0]["page_start"] == 3
        assert report["evidence"]["E1"]["cnts_id"] == "A"

    def test_evidence_chunk_score_is_serialized(self):
        # score 는 화면에 유사도로 나간다 — 프론트는 report 만 받으므로 여기서 빠지면 닿을 길이 없다
        report = assemble_report(_state(), sections=[], unmarked_total=0)
        assert report["evidence"]["E1"]["chunks"][0]["score"] == 0.9

    def test_trail_comes_from_subquestions(self):
        report = assemble_report(_state(), sections=[], unmarked_total=0)
        assert [t["subquestion"] for t in report["trail"]] == ["하위1", "하위2"]

    def test_trail_carries_unchecked_failed_and_capped_flags(self):
        """판정 실패는 verdict=sufficient, 탐색 실패는 pending 으로 남는다 — 플래그 없이는
        탐색 경로 화면이 둘 다 '충분'·'대기 중'으로 그린다."""
        st = _state()
        st.subquestions[0].parse_failed = True
        st.subquestions[1].failed = True
        st.subquestions[1].capped = 4
        trail = assemble_report(st, sections=[], unmarked_total=0)["trail"]
        assert [(t["parse_failed"], t["failed"], t["capped"]) for t in trail] == [
            (True, False, 0), (False, True, 4)]

    def test_corpus_range_is_carried_into_report(self):
        """수록 범위는 고정 문구가 아니라 실행 시점 실측값이다."""
        st = _state()
        st.corpus_range = {"from": "2002", "to": "2026", "n_papers": 72054}
        report = assemble_report(st, sections=[], unmarked_total=0)
        assert report["range"]["n_papers"] == 72054

    def test_missing_corpus_range_is_none(self):
        assert assemble_report(_state(), sections=[], unmarked_total=0)["range"] is None


def _state_three():
    """하위질문 3개, 근거 3편 — 라이브에서 절이 1개만 나온 모양을 재현하는 바탕."""
    st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
    st.subquestions = [
        SubQuestion(idx=0, text="하위1", evidence_ids=["E1", "E2"], verdict="sufficient"),
        SubQuestion(idx=1, text="하위2", evidence_ids=["E2", "E3"], verdict="sufficient"),
        SubQuestion(idx=2, text="하위3", evidence_ids=[], verdict="insufficient"),
    ]
    st.evidence = {
        f"E{i}": Evidence(id=f"E{i}", cnts_id=c, meta={"title": f"논문 {c}"},
                          chunks=[Chunk(f"c{i}", "본문", 1, 1, 0.9)])
        for i, c in ((1, "A"), (2, "B"), (3, "C"))
    }
    return st


class TestBuildSection:
    def test_heading_and_papers_are_structural(self):
        """모델이 논문을 하나만 요약해도 절의 논문 목록은 하위질문의 근거 그대로다."""
        st = _state_three()
        sec = build_section(st, st.subquestions[0],
                            {"intro": "도입 [E1].", "summaries": {"E1": "요약"}, "future": []})
        assert sec["heading"] == "하위1"
        assert [p["cnts_id"] for p in sec["papers"]] == ["A", "B"]
        assert sec["papers"][1]["summary"] == ""

    def test_parse_failure_keeps_paper_list(self):
        st = _state_three()
        sec = build_section(st, st.subquestions[0], None)
        assert sec["intro"] == "" and sec["future"] == []
        assert [p["cnts_id"] for p in sec["papers"]] == ["A", "B"]

    def test_malformed_fields_are_ignored(self):
        st = _state_three()
        sec = build_section(st, st.subquestions[0],
                            {"intro": 3, "summaries": ["x"], "future": "x"})
        assert sec["intro"] == "" and sec["future"] == []
        assert all(p["summary"] == "" for p in sec["papers"])

    def test_papers_are_capped(self):
        st = _state_three()
        ids = [f"E{i}" for i in range(1, 10)]
        for eid in ids:
            st.evidence.setdefault(eid, Evidence(id=eid, cnts_id=eid, meta={}))
        st.subquestions[0].evidence_ids = ids
        assert len(build_section(st, st.subquestions[0], {})["papers"]) == PAPERS_PER_SECTION

    def test_papers_follow_evidence_order(self):
        # runner 가 evidence_ids 를 하위질문 안 순위로 정렬해 둔다 — 절은 그 앞을 자른다
        st = _state_three()
        st.subquestions[0].evidence_ids = ["E2", "E1"]
        sec = build_section(st, st.subquestions[0], {})
        assert [p["cnts_id"] for p in sec["papers"]] == ["B", "A"]

    def test_future_item_with_non_string_text_is_dropped(self):
        """text 가 null 이면 bind_markers 에서 TypeError — 모든 절 호출이 끝난 뒤라 보고서 전체를 잃는다."""
        st = _state_three()
        sec = build_section(st, st.subquestions[0], {"intro": "도입.", "future": [
            {"text": None}, {"text": {"a": 1}}, {"no_text": 1}, {"text": "  "}, 7,
            {"text": "과제 [E1]."}]})
        assert sec["future"] == [{"text": "과제 [E1]."}]

    def test_string_future_items_are_accepted(self):
        st = _state_three()
        sec = build_section(st, st.subquestions[0], {"intro": "도입.", "future": ["과제 [E1]."]})
        assert sec["future"] == [{"text": "과제 [E1]."}]

    def test_list_summary_is_joined_not_repr(self):
        """str(list) 를 쓰면 "['문장1', '문장2']" 가 요약으로 화면에 나간다."""
        st = _state_three()
        sec = build_section(st, st.subquestions[0], {"intro": "도입.", "summaries": {
            "E1": ["SERVQUAL 을 적용했다.", "신뢰성이 가장 낮았다."], "E2": {"x": 1}}})
        assert sec["papers"][0]["summary"] == "SERVQUAL 을 적용했다. 신뢰성이 가장 낮았다."
        assert sec["papers"][1]["summary"] == ""

    def test_template_placeholder_copy_is_not_taken_as_narrative(self):
        """gemma 는 프롬프트 예시를 견본으로 베낀다 — '[E#]' 가 남은 문장은 지시문 원문이다."""
        st = _state_three()
        sec = build_section(st, st.subquestions[0], {
            "intro": "이 하위질문에 대한 연구 흐름을 설명하는 2~4문장. 문장마다 [E#] 를 답니다.",
            "summaries": {"E#": "그 논문이 무엇을 했고"},
            "future": [{"text": "남은 과제 한 문장 [E#]."}]})
        assert sec["intro"] == "" and sec["future"] == []

    def test_section_carries_chunks_matched_in_its_subquestion(self):
        st = _state_three()
        st.evidence["E2"].chunks.append(Chunk("c2b", "하위2 대목", 5, 5, 0.8))
        st.subquestions[1].evidence_chunks = {"E2": ["c2b"], "E3": ["c3"]}
        sec = build_section(st, st.subquestions[1], {})
        assert sec["evidence_chunks"] == {"E2": ["c2b"], "E3": ["c3"]}

    def test_parse_failure_is_marked_failed(self):
        st = _state_three()
        assert build_section(st, st.subquestions[0], None)["failed"] is True
        assert build_section(st, st.subquestions[0], {"intro": "도입."})["failed"] is False


def _timeout() -> httpx.ReadTimeout:
    return httpx.ReadTimeout("timeout")


class TestSynthesize:
    def _patch_chat(self, monkeypatch, replies):
        """replies 항목이 예외면 그 호출에서 던진다 — 전송 오류 대역."""
        calls = []

        async def fake_chat(messages, *, params=None, timeout=None):
            calls.append(messages[1]["content"])
            reply = replies[len(calls) - 1]
            if isinstance(reply, Exception):
                raise reply
            return reply
        monkeypatch.setattr(synthesizer, "chat", fake_chat)
        return calls

    def test_one_section_per_subquestion_with_evidence(self, monkeypatch):
        """2026-09-23 라이브 회귀: 하위질문 3개인데 절이 1개만 나왔다."""
        reply = json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": []})
        calls = self._patch_chat(monkeypatch, [reply, reply])
        report = asyncio.run(synthesize(_state_three()))
        assert [s["heading"] for s in report["sections"]] == ["하위1", "하위2"]
        assert len(calls) == 2                      # 근거 없는 하위3 은 호출하지 않는다
        assert "하위2" in calls[1] and "[E3]" in calls[1] and "[E1]" not in calls[1]

    def test_every_evidence_appears_in_some_section(self, monkeypatch):
        reply = json.dumps({"intro": "도입.", "summaries": {}, "future": []})
        self._patch_chat(monkeypatch, [reply, reply])
        report = asyncio.run(synthesize(_state_three()))
        cited = {e for s in report["sections"] for p in s["papers"] for e in p["evidence"]}
        assert cited == set(report["evidence"])

    def test_missing_summaries_are_reported(self, monkeypatch):
        reply = json.dumps({"intro": "도입.", "summaries": {"E1": "요약"}, "future": []})
        self._patch_chat(monkeypatch, [reply, reply])
        report = asyncio.run(synthesize(_state_three()))
        # 하위1 의 E2, 하위2 의 E2·E3 — 절마다 따로 센다
        assert any("요약을 생성하지 못한 논문 3편" in x for x in report["limitations"])

    def test_partial_parse_failure_is_reported_not_raised(self, monkeypatch):
        good = json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": []})
        self._patch_chat(monkeypatch, [good, "모르겠습니다", "여전히 모르겠습니다"])
        report = asyncio.run(synthesize(_state_three()))
        assert len(report["sections"]) == 2
        assert any("서술을 생성하지 못한 절이 1개" in x for x in report["limitations"])

    def test_total_parse_failure_raises(self, monkeypatch):
        """서술 0줄짜리 보고서를 completed 로 두면 재시도 기회가 사라진다."""
        self._patch_chat(monkeypatch, ["x", "y", "z", "w"])
        with pytest.raises(ValueError):
            asyncio.run(synthesize(_state_three()))

    def test_parse_failure_is_retried_once(self, monkeypatch):
        good = json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": []})
        calls = self._patch_chat(monkeypatch, ["모르겠습니다", good, good])
        report = asyncio.run(synthesize(_state_three()))
        assert len(calls) == 3
        assert not any("서술을 생성하지 못한 절" in x for x in report["limitations"])

    def test_transport_error_is_retried_once(self, monkeypatch):
        """spec §6 '종합 LLM 실패 — 1회 재시도'. 공유 GPU 의 대기로 300초를 넘기는 일이 있다."""
        good = json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": []})
        calls = self._patch_chat(monkeypatch, [_timeout(), good, good])
        report = asyncio.run(synthesize(_state_three()))
        assert len(calls) == 3
        assert report["sections"][0]["intro"] == "도입 [E1]."

    def test_section_failing_twice_does_not_lose_other_sections(self, monkeypatch):
        """절 하나의 전송 오류가 이미 받은 절까지 버리면 잡이 failed 가 되고 재시도가 전부 다시 부른다."""
        good = json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": []})
        self._patch_chat(monkeypatch, [good, _timeout(), _timeout()])
        report = asyncio.run(synthesize(_state_three()))
        assert report["sections"][0]["intro"] == "도입 [E1]."
        assert [p["cnts_id"] for p in report["sections"][1]["papers"]] == ["B", "C"]
        assert any("서술을 생성하지 못한 절이 1개" in x for x in report["limitations"])

    def test_every_section_failing_transport_raises(self, monkeypatch):
        self._patch_chat(monkeypatch, [_timeout()] * 4)
        with pytest.raises(ValueError):
            asyncio.run(synthesize(_state_three()))

    def test_contentless_replies_count_as_failed(self, monkeypatch):
        """키가 다르거나 빈 dict 는 파싱은 되지만 서술이 0줄이다 — 성공으로 세면
        '서술 0줄 completed' 를 막으려던 가드가 뚫린다."""
        self._patch_chat(monkeypatch, ["{}", '{"sections": []}', "{}", "{}"])
        with pytest.raises(ValueError):
            asyncio.run(synthesize(_state_three()))

    def test_marker_only_replies_count_as_failed(self, monkeypatch):
        """마커만 있는 도입·과제는 검증에서 지워지면 서술 0줄이다 — 성공으로 세면
        재시도도 '전부 실패' 가드도 건너뛰고 서술 없는 보고서가 completed 로 남는다."""
        reply = json.dumps({"intro": "[E7]", "summaries": {}, "future": [{"text": "[E1]"}]})
        calls = self._patch_chat(monkeypatch, [reply] * 4)
        with pytest.raises(ValueError):
            asyncio.run(synthesize(_state_three()))
        assert len(calls) == 4                      # 절마다 1회 재시도

    def test_null_future_text_does_not_lose_report(self, monkeypatch):
        reply = json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": [{"text": None}]})
        self._patch_chat(monkeypatch, [reply, reply])
        report = asyncio.run(synthesize(_state_three()))
        assert report["sections"][0]["future"] == []

    def test_failed_subquestion_with_evidence_gets_a_section(self, monkeypatch):
        """재검색·판정 중 예외로 끝난 하위질문도 그 전에 모은 근거는 실재한다 —
        절에서 빼면 근거가 report.evidence 에만 고아로 남는다."""
        st = _state_three()
        st.subquestions[1].failed = True
        reply = json.dumps({"intro": "도입.", "summaries": {}, "future": []})
        self._patch_chat(monkeypatch, [reply, reply])
        report = asyncio.run(synthesize(st))
        assert [s["heading"] for s in report["sections"]] == ["하위1", "하위2"]
        assert any("하위2" in x and "오류로 중단" in x for x in report["limitations"])

    def test_section_prompt_uses_chunk_matched_in_its_subquestion(self, monkeypatch):
        st = _state_three()
        st.evidence["E2"].chunks = [Chunk("c2a", "하위1 대목", 1, 1, 0.9),
                                    Chunk("c2b", "하위2 대목", 2, 2, 0.8)]
        st.subquestions[0].evidence_chunks = {"E1": ["c1"], "E2": ["c2a"]}
        st.subquestions[1].evidence_chunks = {"E2": ["c2b"], "E3": ["c3"]}
        reply = json.dumps({"intro": "도입.", "summaries": {}, "future": []})
        calls = self._patch_chat(monkeypatch, [reply, reply])
        asyncio.run(synthesize(st))
        assert "하위1 대목" in calls[0] and "하위2 대목" not in calls[0]
        assert "하위2 대목" in calls[1] and "하위1 대목" not in calls[1]

    def test_should_stop_cancels_before_any_llm_call(self, monkeypatch):
        calls = self._patch_chat(monkeypatch, [])

        async def stop():
            return True

        with pytest.raises(SynthesisCanceled):
            asyncio.run(synthesize(_state_three(), should_stop=stop))
        assert calls == []

    def test_should_stop_is_checked_before_each_section(self, monkeypatch):
        """취소 후에도 남은 절을 다 부르면 '취소가 GPU 를 비운다'가 거짓이 된다."""
        reply = json.dumps({"intro": "도입.", "summaries": {}, "future": []})
        calls = self._patch_chat(monkeypatch, [reply, reply])
        checks = []

        async def stop():
            checks.append(1)
            return len(checks) > 1

        with pytest.raises(SynthesisCanceled):
            asyncio.run(synthesize(_state_three(), should_stop=stop))
        assert len(calls) == 1


class TestReportChunks:
    """보고서의 근거 청크 — Evidence.chunks 는 매칭된 적 있는 청크의 저장소라 재검색이
    갈아끼운 대목도 남아 있다. 보고서에는 지금 어느 절이 가리키는 대목만, 좋은 순으로 싣는다."""

    def _replaced(self):
        st = _state_three()
        st.evidence["E1"].chunks = [Chunk("P-가", "첫 검색 대목", 1, 1, 0.3),
                                    Chunk("P-재1", "재검색 대목", 2, 2, 0.9)]
        st.subquestions[0].evidence_chunks = {"E1": ["P-재1"], "E2": ["c2"]}
        return st

    def test_chunk_no_section_points_to_is_not_served(self):
        report = assemble_report(self._replaced(), sections=[], unmarked_total=0)
        assert [c["chunk_id"] for c in report["evidence"]["E1"]["chunks"]] == ["P-재1"]

    def test_chunks_of_several_sections_are_best_first(self):
        """chunks[0] 이 약한 대목이면 호버가 첫 장에 그걸 띄운다."""
        st = _state_three()
        st.evidence["E2"].chunks = [Chunk("c2a", "하위1 대목", 1, 1, 0.4),
                                    Chunk("c2b", "하위2 대목", 2, 2, 0.8)]
        st.subquestions[0].evidence_chunks = {"E1": ["c1"], "E2": ["c2a"]}
        st.subquestions[1].evidence_chunks = {"E2": ["c2b"], "E3": ["c3"]}
        report = assemble_report(st, sections=[], unmarked_total=0)
        assert [c["chunk_id"] for c in report["evidence"]["E2"]["chunks"]] == ["c2b", "c2a"]

    def test_evidence_without_mapping_keeps_every_chunk(self):
        """매핑이 없는 옛 스냅샷은 chunks_for 처럼 전부 준다 — 거르면 청크가 0개가 된다."""
        st = self._replaced()
        st.subquestions[0].evidence_chunks = {}
        report = assemble_report(st, sections=[], unmarked_total=0)
        assert [c["chunk_id"] for c in report["evidence"]["E1"]["chunks"]] == ["P-재1", "P-가"]

    def test_section_carries_its_own_chunk_scores(self):
        """한 청크를 두 절이 쓰면 점수도 둘이다 — 절 호버는 자기 하위질문의 점수를 띄운다."""
        st = _state_three()
        st.evidence["E2"].chunks = [Chunk("c2", "공유 대목", 1, 1, 0.95)]
        st.subquestions[0].evidence_chunks = {"E1": ["c1"], "E2": ["c2"]}
        st.subquestions[0].chunk_scores = {"c1": 0.9, "c2": 0.2}
        st.subquestions[1].evidence_chunks = {"E2": ["c2"], "E3": ["c3"]}
        st.subquestions[1].chunk_scores = {"c2": 0.95, "c3": 0.9}

        first = build_section(st, st.subquestions[0], {"intro": "도입 [E1]."})
        second = build_section(st, st.subquestions[1], {"intro": "도입 [E2]."})
        report = assemble_report(st, sections=[first, second], unmarked_total=0)

        assert report["sections"][0]["chunk_scores"] == {"c1": 0.9, "c2": 0.2}
        assert report["sections"][1]["chunk_scores"] == {"c2": 0.95, "c3": 0.9}
