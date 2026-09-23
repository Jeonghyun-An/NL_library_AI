import asyncio
import json

import pytest

from services.research import synthesizer
from services.research.state import Chunk, Evidence, ResearchState, SubQuestion, merge_params
from services.research.synthesizer import (
    PAPERS_PER_SECTION, assemble_report, build_limitations, build_section, synthesize,
)


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

    def test_markers_in_paper_summary_are_stripped(self):
        """요약은 bind_markers 를 안 거친다 — 남기면 지어낸 번호가 검증 없이 나간다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "", "future": [],
                       "papers": [{"cnts_id": "A", "summary": "무엇을 했다 [E1]. 또 했다 [E99]."}]}],
            unmarked_total=0,
        )
        assert report["sections"][0]["papers"][0]["summary"] == "무엇을 했다. 또 했다."

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
                            {"intro": ["x"], "summaries": ["x"], "future": "x"})
        assert sec["intro"] == "" and sec["future"] == []
        assert all(p["summary"] == "" for p in sec["papers"])

    def test_papers_are_capped(self):
        st = _state_three()
        ids = [f"E{i}" for i in range(1, 10)]
        for eid in ids:
            st.evidence.setdefault(eid, Evidence(id=eid, cnts_id=eid, meta={}))
        st.subquestions[0].evidence_ids = ids
        assert len(build_section(st, st.subquestions[0], {})["papers"]) == PAPERS_PER_SECTION


class TestSynthesize:
    def _patch_chat(self, monkeypatch, replies):
        calls = []

        async def fake_chat(messages, *, params=None, timeout=None):
            calls.append(messages[1]["content"])
            return replies[len(calls) - 1]
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
        reply = json.dumps({"intro": "", "summaries": {}, "future": []})
        self._patch_chat(monkeypatch, [reply, reply])
        report = asyncio.run(synthesize(_state_three()))
        cited = {e for s in report["sections"] for p in s["papers"] for e in p["evidence"]}
        assert cited == set(report["evidence"])

    def test_missing_summaries_are_reported(self, monkeypatch):
        reply = json.dumps({"intro": "", "summaries": {"E1": "요약"}, "future": []})
        self._patch_chat(monkeypatch, [reply, reply])
        report = asyncio.run(synthesize(_state_three()))
        # 하위1 의 E2, 하위2 의 E2·E3 — 절마다 따로 센다
        assert any("요약을 생성하지 못한 논문 3편" in x for x in report["limitations"])

    def test_partial_parse_failure_is_reported_not_raised(self, monkeypatch):
        good = json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": []})
        self._patch_chat(monkeypatch, [good, "모르겠습니다"])
        report = asyncio.run(synthesize(_state_three()))
        assert len(report["sections"]) == 2
        assert any("서술을 생성하지 못한 절이 1개" in x for x in report["limitations"])

    def test_total_parse_failure_raises(self, monkeypatch):
        """서술 0줄짜리 보고서를 completed 로 두면 재시도 기회가 사라진다."""
        self._patch_chat(monkeypatch, ["x", "y"])
        with pytest.raises(ValueError):
            asyncio.run(synthesize(_state_three()))
