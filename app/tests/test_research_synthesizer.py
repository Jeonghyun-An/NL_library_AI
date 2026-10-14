import asyncio
import json

import httpx
import pytest

from services.prompts import get_prompt
from services.research import synthesizer
from services.research.llm_json import extract_json
from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, merge_params, restore_state, snapshot_state,
)
from services.research.synthesizer import (
    PAPERS_PER_SECTION, SectionTally, SynthesisCanceled, _topic, assemble_report,
    build_limitations, build_section, finalize_section, section_evidence, synthesize,
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


def _section_of(*cnts_ids):
    """cnts_ids 를 대표 논문으로 싣는 절 — 보고서 evidence 는 절에 실린 근거만 담는다."""
    return {"heading": "h", "intro": "", "future": [],
            "papers": [{"cnts_id": c, "summary": "s"} for c in cnts_ids]}


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
        assert "전체 근거 상한(90편)" in line and "7편" in line
        assert "하위질문당" not in line
        assert "근거를 찾지 못했다" not in line and "관련 논문이 없다" not in line

    def test_capped_insufficient_subquestion_mentions_cap(self):
        st = _state()
        st.subquestions[0].verdict = "insufficient"
        st.subquestions[0].capped = 2
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        line = next(x for x in lims if x.startswith("1절은"))
        assert "'근거 부족'으로 판정했다" in line and "근거 상한" in line and "2편" in line

    def test_budget_capped_insufficient_subquestion_names_the_per_subquestion_cap(self):
        # 몫에 막힌 것을 전체 상한 탓으로 쓰면 max_evidence 를 올리라는 잘못된 신호가 된다
        st = _state()                       # 하위질문 2개 · 기본 90편 → 몫 45편
        st.subquestions[0].verdict = "insufficient"
        st.subquestions[0].budget_capped = 3
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if x.startswith("1절은"))
        assert "(하위질문당 근거 상한(45편)에 닿아 후보 3편을 더 싣지 못했다)" in line
        assert "전체 근거 상한" not in line

    def test_both_caps_are_named_separately(self):
        st = _state()
        st.subquestions[0].verdict = "insufficient"
        st.subquestions[0].budget_capped = 2
        st.subquestions[0].capped = 1
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if x.startswith("1절은"))
        assert ("(하위질문당 근거 상한(45편)에 닿아 후보 2편을, "
                "전체 근거 상한(90편)에 닿아 후보 1편을 더 싣지 못했다)") in line

    def test_subquestion_starved_by_its_share_is_not_reported_as_missing_evidence(self):
        st = _state()
        st.subquestions[1].budget_capped = 4
        st.subquestions[1].note = "관련 논문이 없다"
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "하위2" in x)
        assert line == "'하위2' (은)는 하위질문당 근거 상한(45편)에 닿아 검색된 논문 4편을 싣지 못했다"

    def test_subquestion_emptied_by_exclusion_names_the_exclusion(self):
        """자기점검이 실제 근거를 읽고 모두 뺐다 — '근거를 찾지 못했다'(코퍼스 빈틈)로 쓰면 그 사실이 사라진다."""
        st = _state()
        st.subquestions[1].excluded_cnts = ["B", "C"]
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "하위2" in x)
        assert line == ("'하위2' 에 대해서는 모은 논문 2편이 모두 하위질문과 무관해 근거에서 뺐다"
                        " — 자기점검 메모: “2015년 이후 자료가 없다”")

    def test_emptied_subquestion_still_names_a_cap_that_blocked_more(self):
        # 모두 뺀 것이 먼저다 — 상한은 덧붙인다. 상한 분기로 보내면 critic 이 근거를 읽고 뺀 사실과 note 가 사라진다
        st = _state()
        st.subquestions[1].excluded_cnts = ["B"]
        st.subquestions[1].capped = 3
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "하위2" in x)
        assert line == ("'하위2' 에 대해서는 모은 논문 1편이 모두 하위질문과 무관해 근거에서 뺐다"
                        "(전체 근거 상한(90편)에 닿아 후보 3편을 더 싣지 못했다)"
                        " — 자기점검 메모: “2015년 이후 자료가 없다”")

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


class TestTopic:
    """한계 문장의 주어 조각 — 조사를 받침에 맞춘다. ' 는' 으로 고정하면 받침 있는 말에서 틀린다."""

    @pytest.mark.parametrize(("text", "expected"), [
        ("컴퓨팅 자원 관리", "'컴퓨팅 자원 관리' 는"),
        ("엣지 컴퓨팅의 자원 할당", "'엣지 컴퓨팅의 자원 할당' 은"),
    ])
    def test_particle_follows_the_final_consonant(self, text, expected):
        assert _topic(text) == expected

    @pytest.mark.parametrize("text", ["고성능 컴퓨팅 (HPC)", "클라우드 SLA", "IoT"])
    def test_non_hangul_ending_gets_both_particles(self, text):
        # 'HPC' 는 '는'(에이치피시)이지만 'LAN' 은 '은'(랜)이다 — 읽는 소리는 코드가 모른다
        assert _topic(text) == f"'{text}' (은)는"

    @pytest.mark.parametrize(("text", "expected"), [
        # 운영 연구 d60a5dc1 — 계획이 하위질문을 의문문으로 내면 끝 글자가 '?' 라 한계 줄이 모두 '(은)는' 이었다
        ("국내 학술 논문에서 노인의 우울과 사회적 지지 간의 관계를 측정하기 위해 사용된 방법 및 기법은 무엇인가?",
         "'국내 학술 논문에서 노인의 우울과 사회적 지지 간의 관계를 측정하기 위해 사용된 방법 및 기법은 무엇인가?' 는"),
        ("자원 할당 방법은?", "'자원 할당 방법은?' 은"),
        ("자원 할당의 한계!", "'자원 할당의 한계!' 는"),
        ("자원 할당의 동향.", "'자원 할당의 동향.' 은"),
        ("자원 할당의 과제？ ", "'자원 할당의 과제？ ' 는"),
    ])
    def test_closing_punctuation_is_skipped_before_the_final_consonant(self, text, expected):
        assert _topic(text) == expected

    @pytest.mark.parametrize("text", ["IoT?", "?", "고성능 컴퓨팅 (HPC)?"])
    def test_non_hangul_before_the_punctuation_still_gets_both_particles(self, text):
        assert _topic(text) == f"'{text}' (은)는"

    def test_limitation_sentence_uses_the_matching_particle(self):
        # 부족 줄은 절 번호를 주어로 쓴다 — 하위질문 전문을 주어로 쓰는 중단 줄로 조사를 본다
        st = _state()
        st.subquestions[0].text = "자원 할당"
        st.subquestions[0].failed = True
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "자원 할당" in x)
        assert line.startswith("'자원 할당' 은 탐색이 오류로 중단돼")

    def test_insufficient_line_names_the_verdict_not_the_count(self):
        """운영 d60a5dc1 — 근거 13편인 하위질문에 '근거 13편으로 결론이 약하다'가 붙어 편수 탓으로 읽혔다(같은
        연구에서 5~6편은 충분). 부족 판정은 critic 이 발췌가 핵심 개념을 다루는지로 내린다 — 편수는 신호일 뿐이다
        (research_critique.yaml). 줄은 판정을 적고 까닭은 note 가 말한다. 탐색 경로의 '근거 부족'과 같은 말이다."""
        text = ("국내 학술 논문에서 노인의 우울과 사회적 지지 간의 관계를 측정하기 위해 "
                "사용된 방법 및 기법은 무엇인가?")
        st = _state()
        st.subquestions[0].text = text
        st.subquestions[0].verdict = "insufficient"
        st.subquestions[0].note = "측정 도구를 직접 비교한 논문이 없다"
        st.subquestions[0].evidence_ids = [f"E{i}" for i in range(13)]
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "13편" in x)
        assert line == ("1절은 근거 13편을 모았으나 자기점검에서 '근거 부족'으로 판정했다"
                        " — 자기점검 메모: “측정 도구를 직접 비교한 논문이 없다”")

    def test_about_phrase_keeps_its_fixed_particle(self):
        # '에 대해서는' 은 받침과 무관하다 — 그대로 둔다
        lims = build_limitations(_state(), unmarked_total=0, dropped_total=0)
        assert any(x.startswith("'하위2' 에 대해서는 근거를 찾지 못했다") for x in lims)


class TestInsufficientLineShape:
    """운영 630e0d65 — 하위질문 6개 중 5개가 부족이었고, 줄마다 같은 앞머리('국내 학술 논문에서 다문화가정 아동
    언어 발달…')의 하위질문 전문과 critic note 두 문장을 이어 263~314자가 됐다. 앞은 '-다' 체, 뒤 note 는
    '…부족합니다. 특히 …어렵습니다.'(운영 회차 note 42개 중 38개가 합니다체)라 한 줄에 문체가 섞였다.
    부족 줄의 주어는 보고서의 절 번호로 쓰고(절 제목이 곧 하위질문이다), note 는 첫 문장만 자기점검 메모로
    따옴표 안에 인용한다 — 직접 인용은 원문의 말투를 그대로 둔다."""

    def _line(self, st, prefix):
        return next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if x.startswith(prefix))

    def _insufficient(self, note):
        st = _state()
        st.subquestions[0].verdict = "insufficient"
        st.subquestions[0].note = note
        return st

    def test_section_number_counts_only_subquestions_with_evidence(self):
        """절은 근거 있는 하위질문마다 순서대로 하나씩이다(synthesize) — 앞 하위질문이 0편이면 번호가 당겨진다.
        그때는 하위질문 번호를 함께 적는다 — 보고서 옆 과정 패널과 내려받은 문서의 '부록: 탐색 경로'는 하위질문을
        0편까지 세어 번호 매기므로, '2절' 만 쓰면 그쪽의 '2.'(다른 하위질문, 판정 충분)를 가리키는 것으로 읽힌다."""
        st = _state()
        st.subquestions = [
            SubQuestion(idx=0, text="하위0", evidence_ids=[], verdict="insufficient"),
            SubQuestion(idx=1, text="하위1", evidence_ids=["E1"], verdict="sufficient"),
            SubQuestion(idx=2, text="하위2", evidence_ids=["E1"], verdict="insufficient",
                        note="개념을 다루지 않는다"),
        ]
        line = self._line(st, "2절")
        assert line == ("2절(하위질문 3)은 근거 1편을 모았으나 자기점검에서 '근거 부족'으로 판정했다"
                        " — 자기점검 메모: “개념을 다루지 않는다”")
        assert "하위2" not in line

    def test_section_number_alone_when_it_matches_the_subquestion_number(self):
        # 앞에 0편 하위질문이 없으면 절 번호와 하위질문 번호가 같다 — 뒤에 0편 하위질문이 있어도 덧붙이지 않는다
        st = _state()
        st.subquestions = [
            SubQuestion(idx=0, text="하위0", evidence_ids=["E1"], verdict="sufficient"),
            SubQuestion(idx=1, text="하위1", evidence_ids=["E1"], verdict="insufficient", note="부족하다"),
            SubQuestion(idx=2, text="하위2", evidence_ids=[], verdict="insufficient"),
        ]
        assert self._line(st, "2절").startswith("2절은 근거 1편을 모았으나")

    def test_only_the_first_sentence_of_the_note_is_quoted(self):
        st = self._insufficient("제시된 근거들은 동향을 다루지만 개념에 대한 직접적인 분석은 부족합니다. "
                                "특히, 정의의 변화를 추적하는 논문은 찾기 어렵습니다.")
        assert self._line(st, "1절은").endswith(
            " — 자기점검 메모: “제시된 근거들은 동향을 다루지만 개념에 대한 직접적인 분석은 부족합니다.”")

    @pytest.mark.parametrize("note, first", [
        # 제목 안의 '. ' 는 문장 끝이 아니다(_titled_note 가 번호를 「제목」으로 바꾼다)
        ("「다문화 아동. 언어 발달」은 개념을 다루지 않는다. 특히 정의가 없다.",
         "「다문화 아동. 언어 발달」은 개념을 다루지 않는다."),
        # 숫자 사이 마침표도 문장 끝이 아니다
        ("양적연구 66편(58.4%)만 다룬다. 질적연구는 없다.", "양적연구 66편(58.4%)만 다룬다."),
        # 마침표가 없으면 통째로 싣는다
        ("2015년 이후 자료가 없다", "2015년 이후 자료가 없다"),
        ("  한 문장뿐이다.  ", "한 문장뿐이다."),
    ])
    def test_sentence_boundary(self, note, first):
        assert self._line(self._insufficient(note), "1절은").endswith(f" — 자기점검 메모: “{first}”")

    def test_blank_note_adds_no_memo(self):
        line = self._line(self._insufficient("   "), "1절은")
        assert line == "1절은 근거 1편을 모았으나 자기점검에서 '근거 부족'으로 판정했다"

    def test_note_of_an_unjudged_subquestion_is_left_out(self):
        # 판정을 못 받았을 때의 note 는 '왜'가 아니라 같은 실패의 반복이다 — 집계 줄이 따로 센다
        st = _state()
        st.subquestions[0].failed = True
        st.subquestions[0].parse_failed = True
        st.subquestions[0].note = "판정 JSON 파싱 실패"
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "'하위1'" in x)
        assert "판정 JSON 파싱 실패" not in line and "자기점검 메모" not in line

    def test_failed_and_missing_branches_quote_the_memo_too(self):
        st = _state()
        st.subquestions[0].failed = True
        st.subquestions[0].note = "앞 회차까지는 관련 논문이 있었다. 둘째 문장."
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        assert ("'하위1' (은)는 탐색이 오류로 중단돼 끝까지 확인하지 못했다(중단 전까지 모은 근거 1편으로만 썼다)"
                " — 자기점검 메모: “앞 회차까지는 관련 논문이 있었다.”") in lims
        assert "'하위2' 에 대해서는 근거를 찾지 못했다 — 자기점검 메모: “2015년 이후 자료가 없다”" in lims


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
        report = assemble_report(_state(), sections=[_section_of("A")], unmarked_total=0)
        assert report["evidence"]["E1"]["chunks"][0]["page_start"] == 3
        assert report["evidence"]["E1"]["cnts_id"] == "A"

    def test_evidence_chunk_score_is_serialized(self):
        # score 는 화면에 유사도로 나간다 — 프론트는 report 만 받으므로 여기서 빠지면 닿을 길이 없다
        report = assemble_report(_state(), sections=[_section_of("A")], unmarked_total=0)
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

    def test_trail_carries_excluded_count(self):
        """문서 부록과 옛 잡 타임라인의 '무관 N편 제외' 원천이다."""
        st = _state()
        st.subquestions[0].excluded_cnts = ["X", "Y"]
        trail = assemble_report(st, sections=[], unmarked_total=0)["trail"]
        assert [t["excluded"] for t in trail] == [2, 0]

    def test_trail_carries_the_excluded_papers_in_round_order(self):
        """보고서 '관련성이 낮아 제외한 논문'과 문서 부록의 원천 — 풀에서 지운 논문도 회차 기록의 서지로 남는다."""
        st = _state()
        edge = {"cnts_id": "X", "title": "의료영상 Edge method", "personal_author": "김",
                "pub_date": "2001"}
        mpeg = {"cnts_id": "Y", "title": "MPEG-7 Edge Histogram", "personal_author": None,
                "pub_date": "2003"}
        st.subquestions[0].excluded_cnts = ["X", "Y"]
        st.subquestions[0].rounds = [{"round": 1, "excluded": 1, "excluded_papers": [edge]},
                                     {"round": 2, "excluded": 0, "excluded_papers": []},
                                     {"round": 3, "excluded": 1, "excluded_papers": [mpeg]}]
        trail = assemble_report(st, sections=[], unmarked_total=0)["trail"]
        assert [t["excluded_papers"] for t in trail] == [[edge, mpeg], []]

    def test_trail_carries_the_flagged_count_of_a_job_with_exclusion_off(self):
        """무관 제외를 끈 잡이 무관하다고 본 수 — 켠 잡의 trail.excluded 와 같은 쿼리로 나란히 본다.
        회차 기록의 flagged 는 처음 가리킨 논문만 세므로 더하면 하위질문별 논문 수다."""
        st = _state()
        st.subquestions[0].rounds = [{"round": 1, "excluded": 0, "flagged": 2},
                                     {"round": 2, "excluded": 0, "flagged": 1}]
        trail = assemble_report(st, sections=[], unmarked_total=0)["trail"]
        assert [t["flagged"] for t in trail] == [3, 0]

    def test_resumed_job_with_rounds_recorded_before_the_bibliography_has_no_excluded_papers(self):
        # 보강 전 회차 기록에는 excluded_papers 가 없다 — 그 스냅샷에서 종합만 다시 해도 보고서가 깨지지 않는다
        st = _state()
        st.subquestions[0].rounds = [{"round": 1, "query": "하위1", "found_chunks": 3,
                                      "new_papers": 1, "verdict": "sufficient", "note": "충분하다",
                                      "next_query": None, "excluded": 0}]
        back = restore_state("j1", snapshot_state(st))
        trail = assemble_report(back, sections=[], unmarked_total=0)["trail"]
        assert [t["excluded_papers"] for t in trail] == [[], []]

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
        """gemma 는 프롬프트 예시를 견본으로 베낀다 — '[E#]' 가 남은 문장은 지시문 원문이다.

        손으로 옮긴 골격 문자열은 프롬프트의 골격 설명이 바뀌면 어긋난 채 통과한다 — 렌더한 프롬프트의 JSON 골격을
        그대로 읽어 넣는다(모델이 통째로 베낀 응답과 같은 모양)."""
        st = _state_three()
        system, _, _ = get_prompt("research_synthesize").render(
            question="질문", subquestion="하위1", evidence_block="[E1] 논문 A\n본문", paper_ids="E1, E2")
        skeleton = extract_json(system)
        assert skeleton is not None and set(skeleton) == {"intro", "summaries", "future"}
        assert skeleton["future"][0]["text"]
        sec = build_section(st, st.subquestions[0], skeleton)
        assert sec["intro"] == "" and sec["future"] == []
        # 견본의 키 'E#' 는 어느 논문 번호도 아니다
        assert all(p["summary"] == "" for p in sec["papers"])

    def test_numbered_refs_copied_from_excerpts_are_removed(self):
        """대목 속 남의 번호 인용('[3, 4]')을 옮긴 문장 — 근거 칩처럼 보이지만 어느 근거도 아니다(A/B focus 9ba1 1절).
        도입·요약·향후 과제 모두에서 지우고, 우리 마커 [E#] 는 그대로 둔다."""
        st = _state_three()
        sec = build_section(st, st.subquestions[0], {
            "intro": "우울은 다른 연령에 비해 유발 가능성이 높은 정서반응이다 [3, 4]. "
                     "삶의 질을 심각하게 저하시킨다 [5, 6, 7, 8] [E1]. 5문항으로 구성된 도구이다 [33, 34].",
            "summaries": {"E1": "Hoyl 등[33]의 GDS-5를 사용했다. 삶의 질을 저하시킨다 [8].",
                          "E2": "체계적 문헌고찰을 수행했다 [2]."},
            "future": [{"text": "변화 궤적을 분석하는 추가 연구가 필요하다 [8] [E2]."}, {"text": "[3]"}]})
        assert sec["intro"] == ("우울은 다른 연령에 비해 유발 가능성이 높은 정서반응이다. "
                                "삶의 질을 심각하게 저하시킨다 [E1]. 5문항으로 구성된 도구이다.")
        assert [p["summary"] for p in sec["papers"]] == [
            "Hoyl 등의 GDS-5를 사용했다. 삶의 질을 저하시킨다.", "체계적 문헌고찰을 수행했다."]
        # 번호만 있던 항목은 빈 글이라 싣지 않는다
        assert sec["future"] == [{"text": "변화 궤적을 분석하는 추가 연구가 필요하다 [E2]."}]

    def test_removed_numbered_refs_are_not_reported_as_our_markers(self):
        """지운 남의 번호는 우리 인용 표기가 아니다 — 한계의 '해석할 수 없는 인용 표기'·'없는 번호' 로 세지 않는다.
        근거 칩이 없는 문장은 무표기로 센다(지우기 전에도 [E#] 가 없던 문장이다)."""
        st = _state_three()
        sec = build_section(st, st.subquestions[0], {
            "intro": "정서반응이다 [3, 4]. 저하시킨다 [E1].", "summaries": {"E1": "요약이다.", "E2": "요약이다."},
            "future": []})
        _, tally = finalize_section(st, sec)
        assert tally.unparsed == 0 and tally.dropped == 0
        assert tally.unmarked == 1

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


# 절 응답의 요약 — 어느 절의 논문이든 번호마다 요약이 있다. 요약을 빠뜨린 응답은 그 절을 다시 묻는다
# (_synthesize_section). 절에 없는 번호의 요약은 build_section 이 읽지 않는다
_SUMMARIES = {f"E{i}": "그 논문의 방법과 결과를 요약했다." for i in range(1, 10)}


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
        reply = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
        calls = self._patch_chat(monkeypatch, [reply, reply])
        report = asyncio.run(synthesize(_state_three()))
        assert [s["heading"] for s in report["sections"]] == ["하위1", "하위2"]
        assert len(calls) == 2                      # 근거 없는 하위3 은 호출하지 않는다
        assert "하위2" in calls[1] and "[E3]" in calls[1] and "[E1]" not in calls[1]

    def test_insufficient_line_names_the_section_the_report_shows(self, monkeypatch):
        """한계의 'N절' 은 보고서 화면·내려받은 문서의 'N. 제목' 과 같은 절이어야 한다 — 절을 건너뛰거나 합치게
        바뀌면 번호가 어긋나 엉뚱한 절을 가리킨다. 근거 없는 하위질문이 앞에 있어 하위질문 번호와 다른 경우로 묶는다."""
        reply = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
        self._patch_chat(monkeypatch, [reply, reply])
        st = _state_three()
        st.subquestions = [st.subquestions[2], st.subquestions[0], st.subquestions[1]]
        st.subquestions[2].verdict = "insufficient"
        st.subquestions[2].note = "비교 연구가 없다."
        report = asyncio.run(synthesize(st))
        line = next(x for x in report["limitations"] if "'근거 부족'" in x)
        where = line.split("은 근거", 1)[0]
        k = int(where.split("절", 1)[0])
        assert report["sections"][k - 1]["heading"] == "하위2"
        # 하위질문 번호는 과정 패널·탐색 경로 부록의 번호(근거 0편 하위질문까지 센다)다
        assert where == f"{k}절(하위질문 3)" and st.subquestions[2].text == "하위2"

    def test_every_evidence_appears_in_some_section(self, monkeypatch):
        reply = json.dumps({"intro": "도입.", "summaries": _SUMMARIES, "future": []})
        self._patch_chat(monkeypatch, [reply, reply])
        st = _state_three()
        report = asyncio.run(synthesize(st))
        cited = {e for s in report["sections"] for p in s["papers"] for e in p["evidence"]}
        # 보고서 evidence 는 절에 실린 근거만 담아 절과 늘 같다 — 채택 근거 전체와 비교해야
        # 절에서 빠진 근거가 드러난다.
        assert cited == set(st.evidence)

    def test_missing_summaries_are_reported(self, monkeypatch):
        reply = json.dumps({"intro": "도입.", "summaries": {"E1": "요약"}, "future": []})
        calls = self._patch_chat(monkeypatch, [reply] * 4)
        report = asyncio.run(synthesize(_state_three()))
        assert len(calls) == 4                      # 절마다 한 번 다시 묻고도 빠졌다
        # 하위1 의 E2, 하위2 의 E2·E3 — 절마다 따로 센다
        assert any("요약을 생성하지 못한 논문 3편" in x for x in report["limitations"])
        assert not any("서술을 생성하지 못한 절" in x for x in report["limitations"])

    def test_missing_summary_is_asked_again(self, monkeypatch):
        """summaries 에서 근거 번호 하나를 빠뜨린 응답(A/B focus2 85d2 3절 E11, 48호출 중 1건)은 빈 요약으로 내지
        않고 그 절을 다시 묻는다. 값이 빈 글·마커뿐인 요약도 빠진 것이다(finalize_section 이 요약 없음으로 센다)."""
        partial = json.dumps({"intro": "도입 [E1].", "summaries": {"E1": "첫 논문 요약이다."}, "future": []})
        hollow = json.dumps({"intro": "도입 [E1].", "summaries": {"E1": "첫 논문 요약이다.", "E2": "[E2]"},
                             "future": []})
        full = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
        calls = self._patch_chat(monkeypatch, [partial, full, hollow, full])
        report = asyncio.run(synthesize(_state_three()))
        assert len(calls) == 4
        assert "하위1" in calls[1] and "하위2" in calls[3]
        assert all(p["summary"] for s in report["sections"] for p in s["papers"])
        assert not any("요약을 생성하지 못한" in x for x in report["limitations"])

    def test_reply_missing_fewer_summaries_is_kept_after_the_retry(self, monkeypatch):
        """다시 물어도 빠지면 서술은 버리지 않는다 — 빠진 수가 가장 적은 응답을 싣고, 빠진 논문은 지금처럼 빈 요약으로
        '요약을 생성하지 못한 논문' 한계에 센다. 절을 실패(논문 목록만)로 돌리면 받은 도입·요약까지 잃는다."""
        one_missing = json.dumps({"intro": "첫 응답 도입 [E1].", "summaries": {"E1": "첫 논문 요약이다."},
                                  "future": []})
        both_missing = json.dumps({"intro": "둘째 응답 도입 [E2].", "summaries": {}, "future": []})
        full = json.dumps({"intro": "도입 [E2].", "summaries": _SUMMARIES, "future": []})
        self._patch_chat(monkeypatch, [one_missing, both_missing, full])
        report = asyncio.run(synthesize(_state_three()))
        first = report["sections"][0]
        assert first["intro"] == "첫 응답 도입 [E1]."
        assert [p["summary"] for p in first["papers"]] == ["첫 논문 요약이다.", ""]
        assert any("요약을 생성하지 못한 논문 1편" in x for x in report["limitations"])
        assert not any("서술을 생성하지 못한 절" in x for x in report["limitations"])

    def test_transport_error_on_the_retry_keeps_the_reply_missing_a_summary(self, monkeypatch):
        partial = json.dumps({"intro": "도입 [E1].", "summaries": {"E1": "첫 논문 요약이다."}, "future": []})
        full = json.dumps({"intro": "도입 [E2].", "summaries": _SUMMARIES, "future": []})
        calls = self._patch_chat(monkeypatch, [partial, _timeout(), full])
        report = asyncio.run(synthesize(_state_three()))
        assert "하위1" in calls[1]                   # 다시 물은 것이 끊겼다
        assert report["sections"][0]["intro"] == "도입 [E1]."
        assert any("요약을 생성하지 못한 논문 1편" in x for x in report["limitations"])
        assert not any("서술을 생성하지 못한 절" in x for x in report["limitations"])

    def test_partial_parse_failure_is_reported_not_raised(self, monkeypatch):
        good = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
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
        good = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
        calls = self._patch_chat(monkeypatch, ["모르겠습니다", good, good])
        report = asyncio.run(synthesize(_state_three()))
        assert len(calls) == 3
        assert not any("서술을 생성하지 못한 절" in x for x in report["limitations"])

    def test_transport_error_is_retried_once(self, monkeypatch):
        """spec §6 '종합 LLM 실패 — 1회 재시도'. 공유 GPU 의 대기로 300초를 넘기는 일이 있다."""
        good = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
        calls = self._patch_chat(monkeypatch, [_timeout(), good, good])
        report = asyncio.run(synthesize(_state_three()))
        assert len(calls) == 3
        assert report["sections"][0]["intro"] == "도입 [E1]."

    def test_section_failing_twice_does_not_lose_other_sections(self, monkeypatch):
        """절 하나의 전송 오류가 이미 받은 절까지 버리면 잡이 failed 가 되고 재시도가 전부 다시 부른다."""
        good = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
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
        reply = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": [{"text": None}]})
        self._patch_chat(monkeypatch, [reply, reply])
        report = asyncio.run(synthesize(_state_three()))
        assert report["sections"][0]["future"] == []

    def test_failed_subquestion_with_evidence_gets_a_section(self, monkeypatch):
        """재검색·판정 중 예외로 끝난 하위질문도 그 전에 모은 근거는 실재한다 —
        절에서 빼면 그 근거가 보고서에서 사라진다(report.evidence 는 절에 실린 근거만 담는다)."""
        st = _state_three()
        st.subquestions[1].failed = True
        reply = json.dumps({"intro": "도입.", "summaries": _SUMMARIES, "future": []})
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
        reply = json.dumps({"intro": "도입.", "summaries": _SUMMARIES, "future": []})
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
        reply = json.dumps({"intro": "도입.", "summaries": _SUMMARIES, "future": []})
        calls = self._patch_chat(monkeypatch, [reply, reply])
        checks = []

        async def stop():
            checks.append(1)
            return len(checks) > 1

        with pytest.raises(SynthesisCanceled):
            asyncio.run(synthesize(_state_three(), should_stop=stop))
        assert len(calls) == 1


class TestSynthesizePrompt:
    """절 서술의 문체 — 운영 보고서에서 5절만 '~합니다' 체였다."""

    def _system(self, monkeypatch):
        systems = []

        async def fake_chat(messages, *, params=None, timeout=None):
            systems.append(messages[0]["content"])
            return json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})

        monkeypatch.setattr(synthesizer, "chat", fake_chat)
        asyncio.run(synthesize(_state_three()))
        return systems[0]

    def test_every_field_is_asked_in_plain_written_style(self, monkeypatch):
        system = self._system(monkeypatch)
        assert "'~다'로 끝나는 문어체 평서문" in system
        assert "'~합니다'·'~입니다' 금지" in system
        assert "intro·summaries·future 모두" in system

    def test_json_example_does_not_model_the_polite_style(self, monkeypatch):
        # gemma 는 예시를 견본으로 베낀다(recurring-gotchas 15번) — 예시 값이 '~ㅂ니다'로 끝나면 규칙과 싸운다
        system = self._system(monkeypatch)
        example = system.split("JSON 하나만 출력하세요.", 1)[1].split("summaries 에는", 1)[0]
        assert "니다" not in example


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
        report = assemble_report(self._replaced(), sections=[_section_of("A")], unmarked_total=0)
        assert [c["chunk_id"] for c in report["evidence"]["E1"]["chunks"]] == ["P-재1"]

    def test_chunks_of_several_sections_are_best_first(self):
        """chunks[0] 이 약한 대목이면 호버가 첫 장에 그걸 띄운다."""
        st = _state_three()
        st.evidence["E2"].chunks = [Chunk("c2a", "하위1 대목", 1, 1, 0.4),
                                    Chunk("c2b", "하위2 대목", 2, 2, 0.8)]
        st.subquestions[0].evidence_chunks = {"E1": ["c1"], "E2": ["c2a"]}
        st.subquestions[1].evidence_chunks = {"E2": ["c2b"], "E3": ["c3"]}
        report = assemble_report(st, sections=[_section_of("B")], unmarked_total=0)
        assert [c["chunk_id"] for c in report["evidence"]["E2"]["chunks"]] == ["c2b", "c2a"]

    def test_evidence_without_mapping_keeps_every_chunk(self):
        """매핑이 없는 옛 스냅샷은 chunks_for 처럼 전부 준다 — 거르면 청크가 0개가 된다."""
        st = self._replaced()
        st.subquestions[0].evidence_chunks = {}
        report = assemble_report(st, sections=[_section_of("A")], unmarked_total=0)
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


class TestSectionProgress:
    """절 진행을 콜백으로 알린다 — 워커가 synth 이벤트로 흘리고 종합 단계 result 에도 남긴다."""

    def _record(self, infos: list | None = None):
        seen: list[tuple[int, int, str]] = []

        async def on_section(idx, total, status, info):
            seen.append((idx, total, status))
            if infos is not None:
                infos.append(info)

        return seen, on_section

    def test_each_section_reports_start_and_end(self, monkeypatch):
        reply = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [reply, reply])
        seen, on_section = self._record()
        asyncio.run(synthesize(_state_three(), on_section=on_section))
        # 근거 없는 하위3 은 절이 되지 않는다 — total 은 실제로 쓰는 절 수이고 idx 는 절 순번이다
        assert seen == [(0, 2, "running"), (0, 2, "done"), (1, 2, "running"), (1, 2, "done")]

    def test_section_without_narrative_reports_failed(self, monkeypatch):
        good = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [good, _timeout(), _timeout()])
        seen, on_section = self._record()
        asyncio.run(synthesize(_state_three(), on_section=on_section))
        assert seen[-1] == (1, 2, "failed")

    def test_canceled_section_is_never_reported_finished(self, monkeypatch):
        # 끝났다고 알리지 않는다 — 워커가 종합 단계를 failed 로 닫는다
        TestSynthesize()._patch_chat(monkeypatch, [])
        seen, on_section = self._record()

        async def stop():
            return True

        with pytest.raises(SynthesisCanceled):
            asyncio.run(synthesize(_state_three(), should_stop=stop, on_section=on_section))
        assert seen == [(0, 2, "running")]

    def test_start_carries_the_subquestion_and_every_heading(self, monkeypatch):
        # 절 순번과 하위질문 번호는 다르다 — 근거 없는 하위질문은 절이 되지 않는다
        st = _state_three()
        st.subquestions[0].evidence_ids = []
        reply = json.dumps({"intro": "도입 [E2].", "summaries": _SUMMARIES, "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [reply])
        infos = []
        seen, on_section = self._record(infos)
        asyncio.run(synthesize(st, on_section=on_section))
        assert seen[0] == (0, 1, "running")
        assert infos[0] == {"subq_idx": 1, "heading": "하위2", "headings": ["하위2"]}

    def test_end_carries_the_finalized_section_and_its_evidence(self, monkeypatch):
        reply = json.dumps({"intro": "도입 [E1] [E2].", "summaries": {**_SUMMARIES, "E1": "요약 [E1]."},
                            "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [reply, reply])
        infos = []
        _, on_section = self._record(infos)
        report = asyncio.run(synthesize(_state_three(), on_section=on_section))
        assert "section" not in infos[0] and "evidence" not in infos[0]
        assert infos[1]["subq_idx"] == 0 and infos[1]["headings"] == ["하위1", "하위2"]
        # 초안의 절은 최종본의 절과 같다 — 같은 finalize_section 으로 다듬는다
        assert [infos[1]["section"], infos[3]["section"]] == report["sections"]
        assert set(infos[1]["evidence"]) == {"E1", "E2"}
        assert set(infos[3]["evidence"]) == {"E2", "E3"}
        assert infos[1]["evidence"]["E1"] == report["evidence"]["E1"]

    def test_failed_section_is_carried_with_its_paper_list(self, monkeypatch):
        # 서술을 끝내 받지 못한 절도 초안에 싣는다 — 최종본도 그 절을 논문 목록만으로 싣는다
        good = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [good, _timeout(), _timeout()])
        infos = []
        seen, on_section = self._record(infos)
        report = asyncio.run(synthesize(_state_three(), on_section=on_section))
        assert seen[-1] == (1, 2, "failed")
        sec = infos[-1]["section"]
        assert sec == report["sections"][1]
        assert sec["intro"] == "" and sec["future"] == []
        assert [(p["cnts_id"], p["summary"]) for p in sec["papers"]] == [("B", ""), ("C", "")]
        assert set(infos[-1]["evidence"]) == {"E2", "E3"}


class TestReportEvidence:
    """보고서 evidence 는 절에 실린 근거만 담는다 — 채택 수는 stats 가 센다."""

    def test_evidence_beyond_the_section_papers_is_left_out(self):
        # 절은 하위질문마다 앞 5편만 싣는다 — 나머지까지 실으면 상한을 올릴수록 보고서 JSON 만 분다
        st = _state_three()
        ids = [f"E{i}" for i in range(1, 8)]
        for eid in ids:
            st.evidence.setdefault(eid, Evidence(id=eid, cnts_id=eid, meta={}))
        st.subquestions[0].evidence_ids = ids
        sections = [build_section(st, sq, {"intro": "도입."})
                    for sq in st.subquestions if sq.evidence_ids]
        report = assemble_report(st, sections, unmarked_total=0)
        assert list(report["evidence"]) == ["E1", "E2", "E3", "E4", "E5"]
        assert report["stats"]["evidence_adopted"] == 7

    def test_evidence_of_a_subquestion_without_a_section_is_left_out(self):
        st = _state_three()
        report = assemble_report(st, [build_section(st, st.subquestions[0], {"intro": "도입."})],
                                 unmarked_total=0)
        assert set(report["evidence"]) == {"E1", "E2"}


class TestReportStats:
    """보고서 서론 한 줄("논문 N편을 검토하고 M편을 근거로")의 원천."""

    def test_report_carries_research_stats(self):
        st = _state()
        st.seen_cnts = {"A", "B", "C"}
        st.subquestions[0].queries = ["q1", "q2"]
        st.subquestions[1].excluded_cnts = ["B", "C"]
        st.subquestions[1].rounds = [{"round": 1, "excluded": 2}]
        report = assemble_report(st, sections=[], unmarked_total=0)
        assert report["stats"] == {"papers_reviewed": 3, "evidence_adopted": 1, "rechecks": 1,
                                   "excluded": 2}

    def test_existing_keys_are_kept(self):
        # 키 추가만 한다 — 옛 보고서를 그리는 화면과 교본이 기존 키에 기대고 있다
        report = assemble_report(_state(), sections=[], unmarked_total=0)
        assert set(report) == {
            "question", "range", "sections", "evidence", "trail", "limitations", "stats",
        }


class TestFinalizeSection:
    """assemble_report 의 절 단위 처리를 떼어 낸 함수. 작성 중 초안(절 미리보기)과 최종본이
    이 함수 하나로 다듬은 절을 쓴다 — 둘이 갈리면 초안에서 읽은 글이 완성본에서 바뀐다."""

    def _sections(self):
        return [
            {"heading": "하위1", "intro": "도입 [E1] [E99]. 연결 문장.",
             "papers": [{"cnts_id": "A", "summary": "요약 [E1]."}, {"cnts_id": "B", "summary": ""}],
             "future": [{"text": "과제 [E2]."}, {"text": "[E7]"}],
             "evidence_chunks": {"E1": ["c1"], "E2": ["c2"]},
             "chunk_scores": {"c1": 0.9, "c2": 0.8}},
            {"heading": "하위2", "intro": "", "failed": True, "future": [],
             "papers": [{"cnts_id": "B", "summary": ""}, {"cnts_id": "C", "summary": ""}]},
        ]

    def test_section_equals_the_assembled_report_section(self):
        st = _state_three()
        sections = self._sections()
        report = assemble_report(st, sections, unmarked_total=0)
        assert [finalize_section(st, s)[0] for s in sections] == report["sections"]

    def test_tally_counts_one_section(self):
        # 도입의 [E99]·과제의 [E7] 은 이 절 근거(E1·E2)에 없다 → 삭제 2, "연결 문장." → 무표기 1,
        # 요약이 빈 B → 요약 누락 1
        _, tally = finalize_section(_state_three(), self._sections()[0])
        assert tally == SectionTally(unmarked=1, dropped=2, unsummarized=1)

    def test_failed_section_counts_only_as_failed(self):
        _, tally = finalize_section(_state_three(), self._sections()[1])
        assert tally == SectionTally(failed=1)

    def test_tallies_add_up_to_the_report_limitations(self):
        st = _state_three()
        total = SectionTally()
        for s in self._sections():
            total.add(finalize_section(st, s)[1])
        assert total == SectionTally(unmarked=1, dropped=2, unsummarized=1, failed=1)
        assert assemble_report(st, self._sections(), unmarked_total=0)["limitations"] == (
            build_limitations(st, unmarked_total=1, dropped_total=2, failed_sections=1,
                              unsummarized_total=1))


class TestSectionEvidence:
    """절 미리보기에 싣는 근거 — 그 절이 인용한 근거만, 대목은 그 절이 매칭한 것만."""

    def _state(self):
        st = _state_three()
        st.evidence["E2"].chunks = [Chunk("c2a", "하위1 대목", 1, 1, 0.4),
                                    Chunk("c2b", "하위2 대목", 2, 2, 0.8)]
        st.subquestions[0].evidence_chunks = {"E1": ["c1"], "E2": ["c2a"]}
        st.subquestions[1].evidence_chunks = {"E2": ["c2b"], "E3": ["c3"]}
        return st

    def _finalized(self, st, i):
        return finalize_section(st, build_section(st, st.subquestions[i], {"intro": "도입 [E2]."}))[0]

    def test_only_cited_evidence_is_carried(self):
        st = self._state()
        # 하위1 절의 논문은 E1·E2 다 — E3 은 하위2 절의 근거라 싣지 않는다
        assert set(section_evidence(st, self._finalized(st, 0))) == {"E1", "E2"}

    def test_shape_matches_report_evidence(self):
        st = self._state()
        ev = section_evidence(st, self._finalized(st, 1))["E3"]
        assert ev == {"cnts_id": "C", "meta": {"title": "논문 C"}, "chunks": [
            {"chunk_id": "c3", "text": "본문", "page_start": 1, "page_end": 1, "score": 0.9}]}
        # 손으로 적은 기대값만으로는 보고서 쪽 모양이 바뀌어도 통과한다 — 실제 보고서 출력과도 맞춘다
        # (E3 은 한 절에만 실려 두 쪽의 대목 선택이 같다)
        assert ev == assemble_report(st, [_section_of("C")], unmarked_total=0)["evidence"]["E3"]

    def test_chunks_are_limited_to_the_section(self):
        # 한 논문이 두 절에 실리면 Evidence.chunks 는 합집합이다 — 절 미리보기는 제 대목만 싣는다
        st = self._state()
        first = section_evidence(st, self._finalized(st, 0))["E2"]["chunks"]
        second = section_evidence(st, self._finalized(st, 1))["E2"]["chunks"]
        assert [c["chunk_id"] for c in first] == ["c2a"]
        assert [c["chunk_id"] for c in second] == ["c2b"]

    def test_chunks_are_best_first(self):
        st = self._state()
        st.evidence["E1"].chunks = [Chunk("c1a", "약한 대목", 1, 1, 0.3),
                                    Chunk("c1b", "강한 대목", 2, 2, 0.9)]
        st.subquestions[0].evidence_chunks = {"E1": ["c1a", "c1b"], "E2": ["c2a"]}
        chunks = section_evidence(st, self._finalized(st, 0))["E1"]["chunks"]
        assert [c["chunk_id"] for c in chunks] == ["c1b", "c1a"]

    def test_section_without_chunk_mapping_keeps_every_chunk(self):
        """매핑 없는 절(옛 모양)은 _serialize_evidence 처럼 전부 준다 — 거르면 대목이 0개가 된다."""
        st = self._state()
        sec, _ = finalize_section(st, {"heading": "h", "intro": "도입 [E1].", "future": [],
                                       "papers": [{"cnts_id": "A", "summary": "s"},
                                                  {"cnts_id": "B", "summary": "s"}]})
        assert [c["chunk_id"] for c in section_evidence(st, sec)["E2"]["chunks"]] == ["c2b", "c2a"]

    def test_markers_in_intro_and_future_are_cited_too(self):
        # 칩은 대표 논문만이 아니다 — 도입·향후 과제의 [E#] 도 팝오버를 연다
        st = self._state()
        sec = {"heading": "h", "intro": "도입 [E3].", "papers": [],
               "future": [{"text": "과제 [E2].", "evidence": ["E2"]}], "evidence_chunks": {}}
        assert set(section_evidence(st, sec)) == {"E2", "E3"}


# 운영 630e0d65 의 대목 모양 — 2절에서 박혜성(2014)의 유일한 대목이 남의 연구를 정리한 표의 한 행이었다
_TABLE_ROW = ("정금자, 이영숙 (2013)|만 5세 유아로 실험집단 60명 &amp; 비교집단 60명|사회극놀이를 통한 다문화교육활동이 "
              "유아의 사회적 능력에 미치는 효과를 탐색함|1) 사회적 능력 향상에 긍정적인 효과를 미침.<br>"
              "2) 전 유아를 대상으로 구성, 적용되어야 함.<br>|실험(비교)연구")
_PROSE = "연구 방법에서는 비교와 조사 유형이 주를 이루는 양적 연구 방법이 76%로 편중되었다. 질적 연구는 드물었다."
# 황상심(2009)의 1위 대목 — 참고문헌 꼬리와 다음 쪽 영문 제목·초록 머리가 한 청크라 앞 400자에 서술 문장이 없다
_BIB_TAIL = ("Toronto: University of Toronto press. Vihman, M.\n(1996).\nPhonological development: "
             "The origins of language in the child.\nCambridge, MA: Blackwell.\n"
             "### A Study on Language Characteristics of Children\n\n&lt;Abstract&gt;\n\nThis s")


def _mapped_state(*mappings: dict[str, list[Chunk]]) -> ResearchState:
    """하위질문마다 {근거 번호: 그 하위질문이 매칭한 대목(점수순)} — 근거는 매칭한 대목의 합집합이다."""
    st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
    for idx, mapping in enumerate(mappings):
        sq = SubQuestion(idx=idx, text=f"하위{idx + 1}", evidence_ids=list(mapping), verdict="sufficient")
        for eid, chunks in mapping.items():
            ev = st.evidence.setdefault(eid, Evidence(id=eid, cnts_id=f"P{eid}", meta={"title": f"논문 {eid}"}))
            ev.chunks.extend(c for c in chunks if c.chunk_id not in {x.chunk_id for x in ev.chunks})
            sq.evidence_chunks[eid] = [c.chunk_id for c in chunks]
            sq.chunk_scores.update({c.chunk_id: c.score for c in chunks})
        st.subquestions.append(sq)
    return st


class TestSectionExcerpts:
    """절마다 논문 하나에 대목 하나를 모델에 넘긴다 — 운영 630e0d65 에서 그 하위질문의 1위 대목을 그대로 넘겨,
    같은 대목이 4개 절에 들어가 같은 문장이 되풀이됐고(장 2019 의 '2004년…'), 표 행·참고문헌 꼬리뿐인 대목으로
    남의 연구를 그 논문의 성과처럼 쓰거나 제목만 되풀이한 요약이 나왔다."""

    def _run(self, monkeypatch, st, replies=None):
        reply = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
        n = sum(1 for sq in st.subquestions if sq.evidence_ids)
        calls = TestSynthesize()._patch_chat(monkeypatch, replies or [reply] * n)
        infos = []
        _, on_section = TestSectionProgress()._record(infos)
        report = asyncio.run(synthesize(st, on_section=on_section))
        return calls, report, [i for i in infos if "section" in i]

    def test_table_row_gives_way_to_a_prose_excerpt(self, monkeypatch):
        st = _mapped_state({"E1": [Chunk("t1", _TABLE_ROW, 9, 9, 0.9), Chunk("n1", _PROSE, 2, 2, 0.6)]})
        calls, report, _ = self._run(monkeypatch, st)
        assert "76%로 편중" in calls[0] and "정금자" not in calls[0]
        # 인용칩 팝오버의 첫 대목이 모델이 읽은 대목이다
        assert report["sections"][0]["evidence_chunks"]["E1"] == ["n1", "t1"]

    def test_excerpt_without_a_sentence_is_skipped(self, monkeypatch):
        method = "연령 집단 별 차이 비교를 위해서 t 검정을 실시하였으며, SPSS/Win 15.0 을 사용하였다."
        st = _mapped_state({"E1": [Chunk("b1", _BIB_TAIL, 9, 9, 0.739), Chunk("m1", method, 4, 4, 0.629)]})
        calls, _, _ = self._run(monkeypatch, st)
        assert "t 검정" in calls[0] and "Blackwell" not in calls[0]

    def test_sections_sharing_a_paper_get_its_other_excerpt(self, monkeypatch):
        first = Chunk("c1a", "가 대목에서 음운 발달을 분석하였다.", 1, 1, 0.9)
        second = Chunk("c1b", "나 대목에서 연구 방법을 정리하였다.", 2, 2, 0.8)
        st = _mapped_state({"E1": [first, second]}, {"E1": [first, second]})
        calls, report, _ = self._run(monkeypatch, st)
        assert "가 대목" in calls[0] and "나 대목" not in calls[0]
        assert "나 대목" in calls[1] and "가 대목" not in calls[1]
        assert report["sections"][1]["evidence_chunks"]["E1"] == ["c1b", "c1a"]

    def test_excerpt_of_a_section_without_narrative_is_not_counted_as_shown(self, monkeypatch):
        # 서술을 받지 못한 절의 대목은 보고서에 쓰이지 않았다 — 다음 절이 피할 까닭이 없다
        first = Chunk("c1a", "가 대목에서 음운 발달을 분석하였다.", 1, 1, 0.9)
        second = Chunk("c1b", "나 대목에서 연구 방법을 정리하였다.", 2, 2, 0.8)
        st = _mapped_state({"E1": [first, second]}, {"E1": [first, second]})
        reply = json.dumps({"intro": "도입 [E1].", "summaries": _SUMMARIES, "future": []})
        calls, _, _ = self._run(monkeypatch, st, [_timeout(), _timeout(), reply])
        assert "가 대목" in calls[2]

    def test_paper_with_only_table_excerpts_borrows_its_prose_matched_elsewhere(self, monkeypatch):
        st = _mapped_state({"E1": [Chunk("t1", _TABLE_ROW, 9, 9, 0.548)]},
                           {"E1": [Chunk("n1", _PROSE, 2, 2, 0.637)]})
        # 재검색이 갈아끼워 어느 하위질문도 가리키지 않는 대목은 보고서 근거에 실리지 않는다 — 빌려 오지 않는다
        st.evidence["E1"].chunks.append(Chunk("old", "지난 대목에서 다른 결과를 보고하였다.", 7, 7, 0.99))
        calls, report, drafts = self._run(monkeypatch, st)
        assert "76%로 편중" in calls[0] and "정금자" not in calls[0] and "지난 대목" not in calls[0]
        assert report["sections"][0]["evidence_chunks"]["E1"] == ["n1", "t1"]
        assert {c["chunk_id"] for c in report["evidence"]["E1"]["chunks"]} == {"t1", "n1"}
        assert {c["chunk_id"] for c in drafts[0]["evidence"]["E1"]["chunks"]} == {"t1", "n1"}

    def test_html_escapes_and_line_breaks_are_unfolded(self, monkeypatch):
        text = "검사 도구는 &lt;기초학습기능검사&gt;였다.<br>대상은 232명이었다."
        st = _mapped_state({"E1": [Chunk("c1", text, 1, 1, 0.9)]})
        calls, _, _ = self._run(monkeypatch, st)
        assert "<기초학습기능검사>였다.\n대상은 232명" in calls[0]
        assert "&lt;" not in calls[0] and "<br>" not in calls[0]

    def test_window_whose_only_sentence_ends_are_initials_is_skipped(self, monkeypatch):
        """'완결 문장이 없는 대목' 판정은 대목을 자르는 문장 끝과 같은 기준이다 — 머리글자 'H.'·'J.' 를 문장 끝으로 보면
        그 앞의 영문 서지 조각('This study was …')이 서술로 세어져, 잘린 문장만 있는 대목이 모델에 간다."""
        bib = "This study was cited by Song, H. and Kim, J. in the review of " + "x" * 400
        st = _mapped_state({"E1": [Chunk("b1", bib, 9, 9, 0.9), Chunk("n1", _PROSE, 2, 2, 0.6)]})
        calls, _, _ = self._run(monkeypatch, st)
        assert "76%로 편중" in calls[0] and "Song" not in calls[0]


# 모델이 읽는 대목 창 — 운영 630e0d65 2절 E16 은 400자째에서 '넷 째, …5개의' 로 끊겨, 모델이 잘린 문장을 짐작해
# 잇거나 되풀이 루프에 빠졌다
_DONE = "셋 째, 연구 방법에서는 양적 연구 방법이 76%로서 편중된 양상을 나타내었다. "
_CUT_TAIL = "넷 째, 분석대상논문들을 통해 총 6개의 하위 주제와 5개의 "


class TestExcerptText:
    def _text(self, text: str) -> str:
        return synthesizer.excerpt_text(Chunk("c1", text, 1, 1, 0.9))

    def test_window_is_cut_at_the_last_sentence_end(self):
        text = _DONE * 5 + _CUT_TAIL + "하위 범주를 " * 40 + "도출하였다."
        assert text.index("도출하였다") > synthesizer.EXCERPT_CHARS
        assert self._text(text) == (_DONE * 5).rstrip()

    def test_english_window_is_cut_at_the_last_sentence_end(self):
        done = "This study reviewed the assessment methods used in the researches. "
        text = done * 4 + "The findings suggest that while early researches focused on vocabulary, " * 5
        assert self._text(text) == (done * 4).rstrip()

    def test_sentence_end_too_close_to_the_start_keeps_the_400_char_cut(self):
        # 마지막 문장 끝이 너무 앞이면 남는 글이 거의 없다 — 지금처럼 400자에서 자른다
        text = "짧은 문장이다. " + "가" * 500
        assert self._text(text) == text[:synthesizer.EXCERPT_CHARS]

    def test_window_without_a_sentence_end_keeps_the_400_char_cut(self):
        text = "|번호|성별|연령|\n" * 60
        assert self._text(text) == text[:synthesizer.EXCERPT_CHARS]

    def test_chunk_within_the_window_is_kept_whole(self):
        # 400자를 넘지 않으면 자르지 않는다 — 청크가 끝난 자리다
        text = _DONE * 3 + "끝나지 않은 조각"
        assert self._text(text) == text

    def test_period_at_the_window_edge_is_judged_by_the_next_char(self):
        # 400자째 마침표가 '3.14' 의 소수점이면 문장 끝이 아니다 — '평균은 3.' 에서 자르면 값이 바뀐다
        head = _DONE * 5 + "평균은 "
        text = head + "나" * (synthesizer.EXCERPT_CHARS - 2 - len(head)) + "3.14점이었다. " + "다" * 100
        assert text.index("3.14") + 1 == synthesizer.EXCERPT_CHARS - 1
        assert self._text(text) == (_DONE * 5).rstrip()

    @pytest.mark.parametrize("tail", [
        "#### 3. 연구 방법",                 # 절 번호(운영 d60a5dc1 E1 '#### 3.')
        "- [7] H. Song, A study on",         # 머리글자(운영 d60a5dc1 E11 '- [7] H.')
        "- Ⅳ. 공공도서관 지역",               # 로마 숫자(운영 85d2bc0e E19 '- Ⅳ.')
        "|3.615 (.815)\n\n.125",             # 소수점(운영 9ba10849 E6 '3.615 (.')
        "Journal of Welfare, Vol. 17, pp",   # 서지 약어(운영 9ba10849 E1 'Vol.')
        "(Kim et al. 2019",                  # et al.
    ])
    def test_numbers_initials_and_abbreviations_are_not_sentence_ends(self, tail):
        text = _DONE * 5 + tail + " " + "가" * 400
        assert self._text(text) == (_DONE * 5).rstrip()

    def test_closing_quote_stays_with_its_sentence(self):
        text = _DONE * 4 + "연구자는 “언어 지원이 먼저 필요하다.” " + "가" * 400
        assert self._text(text).endswith("“언어 지원이 먼저 필요하다.”")

    def test_footnote_number_after_the_period_is_left_out(self):
        text = _DONE * 4 + "일반화하기는 어렵다.4)\n\n그러므로 객관적 자료 조사가 " + "가" * 400
        assert self._text(text).endswith("일반화하기는 어렵다.")


def _drafted(intro: str = "", future: tuple[str, ...] = (), summary: str = "요약이다.") -> dict:
    """모델 출력으로 만든 절(build_section 의 모양) — 다듬기(finalize_section) 전이다."""
    return {"heading": "h", "intro": intro, "papers": [{"cnts_id": "A", "summary": summary}],
            "future": [{"text": t} for t in future], "evidence_chunks": {}, "chunk_scores": {},
            "failed": False}


class TestDropRepeats:
    """앞 절과 거의 같은 도입 문장·향후 과제를 지운다 — 운영 630e0d65 에서 '2004년부터 시작되었으며…' 가 1·2·4·5절
    도입 첫 문장으로, '객관적인 자료 조사가 필요하다 [E4]' 가 네 절의 향후 과제로 거의 그대로 되풀이됐다."""

    _FIRST = ("국내 학술 논문에서 다문화가정 아동의 언어 발달에 대한 연구는 2004년부터 시작되었으며, 유아와 아동의 음운, "
              "어휘 발달, 형태론 등을 분석한 경우가 많다 [E1].")
    _AGAIN = ("국내 학술 논문에서 다문화가정 아동의 언어 발달 연구는 2004년부터 시작되었으며, 유아와 아동의 음운, "
              "어휘 발달, 형태론 등을 분석한 경우가 많았다 [E2].")
    _FUTURE = "다문화가정 아동의 언어 능력을 정확히 보여줄 수 있는 객관적인 자료 조사가 필요하다 [E1]."

    def _seen(self, intro: str = _FIRST, future: tuple[str, ...] = (_FUTURE,)) -> list[str]:
        _, seen = synthesizer.drop_repeats(_drafted(intro, future), [])
        return seen

    def test_repeated_intro_sentence_is_dropped(self):
        sec, _ = synthesizer.drop_repeats(_drafted(f"{self._AGAIN} 연구 방법으로는 조사 연구가 가장 많았다 [E3]."),
                                          self._seen())
        assert sec["intro"] == "연구 방법으로는 조사 연구가 가장 많았다 [E3]."

    def test_paraphrase_below_the_threshold_is_kept(self):
        # 바꿔 쓴 일반론(유사도 0.79)은 남긴다 — 같은 문장의 되풀이만 지운다
        earlier = "다문화가정 아동의 언어 발달에 영향을 미치는 다양한 요인들을 종합적으로 고려하는 연구가 필요하다 [E1]."
        later = "다문화가정 아동의 언어 발달에 영향을 미치는 다양한 변인들에 대한 추가적인 연구가 필요하다 [E2]."
        sec, _ = synthesizer.drop_repeats(_drafted("새 도입이다 [E2].", (later,)),
                                          self._seen(future=(earlier,)))
        assert sec["future"] == [{"text": later}]

    def test_repeated_future_item_is_dropped(self):
        again = "다문화가정 아동의 언어 능력을 정확히 보여줄 수 있는 객관적인 자료 조사가 필요하다. [E2]"
        other = "연령별 특성을 세분화하여 분석하는 연구가 필요하다 [E2]."
        sec, _ = synthesizer.drop_repeats(_drafted("새 도입이다 [E2].", (again, other)), self._seen())
        assert sec["future"] == [{"text": other}]

    def test_intro_made_only_of_repeats_is_kept_whole(self):
        # 비우면 '도입 문단을 생성하지 못한 절' 한계 줄이 잘못 붙는다
        sec, _ = synthesizer.drop_repeats(_drafted(self._AGAIN), self._seen())
        assert sec["intro"] == self._AGAIN

    def test_meta_sentence_is_dropped(self):
        sec, _ = synthesizer.drop_repeats(_drafted(
            "본 절에서는 국내 학술 논문에서 연구 대상 집단을 분석하고자 한다 [E3]. 양적 연구 방법이 주로 활용되었다 [E1]."), [])
        assert sec["intro"] == "양적 연구 방법이 주로 활용되었다 [E1]."

    def test_marker_after_the_period_goes_with_the_dropped_sentence(self):
        intro = f"{self._AGAIN.removesuffix(' [E2].')}. [E2] 이러한 연구들은 어머니의 언어 능력을 함께 보고한다. [E3]"
        sec, _ = synthesizer.drop_repeats(_drafted(intro), self._seen())
        assert sec["intro"] == "이러한 연구들은 어머니의 언어 능력을 함께 보고한다. [E3]"

    def test_marker_used_as_the_next_subject_stays_with_it(self):
        # '[E1] 연구는…' 의 마커는 다음 문장의 주어다 — 앞 문장과 함께 지우면 '연구는…' 이 근거 없이 남는다
        intro = f"{self._AGAIN.removesuffix(' [E2].')}. [E2] 연구는 어머니의 한국 거주 기간을 변수로 보았다."
        sec, _ = synthesizer.drop_repeats(_drafted(intro), self._seen())
        assert sec["intro"] == "[E2] 연구는 어머니의 한국 거주 기간을 변수로 보았다."

    def test_paper_summaries_are_left_alone(self):
        sec, _ = synthesizer.drop_repeats(_drafted("새 도입이다 [E2].", summary=self._FIRST), self._seen())
        assert sec["papers"] == [{"cnts_id": "A", "summary": self._FIRST}]

    def test_unchanged_section_keeps_its_text(self):
        intro = "첫 문장이다 [E1].\n둘째 문장이다 [E2]."
        sec, _ = synthesizer.drop_repeats(_drafted(intro, ("과제다 [E1].",)), [])
        assert sec["intro"] == intro and sec["future"] == [{"text": "과제다 [E1]."}]

    @pytest.mark.parametrize("earlier, intro", [
        # 번호 매김 '1.' — '. ' 에서 잘린 조각의 비교 키가 '1' 로 같아 유사도 1.0 이었다
        ("다문화가정 아동의 어휘 발달은 2004년부터 연구되었다 [E1]. 1. 이후 여러 연구가 이어졌다 [E2].",
         "선행 연구는 다음과 같다. 1. 어휘 발달 연구가 있다 [E3]. 2. 문법 발달 연구가 있다 [E5]."),
        # 'vs.' — '가정 vs.' 조각이 앞 절과 같다
        ("가정 vs. 학교 환경의 차이를 본 연구가 많다 [E1].", "가정 vs. 기관 환경을 비교한 연구도 있다 [E3]."),
    ], ids=["numbering", "versus"])
    def test_short_fragments_are_not_repeats(self, earlier, intro):
        # 마침표에서 잘린 짧은 조각은 앞 절에 같은 조각이 있어도 되풀이로 보지 않는다 — 지우면 '2. 문법 …' 만 번호가 남는다
        _, seen = synthesizer.drop_repeats(_drafted(earlier), [])
        sec, _ = synthesizer.drop_repeats(_drafted(intro), seen)
        assert sec["intro"] == intro


class TestSynthesizeDropsRepeats:
    def test_draft_and_report_show_the_same_trimmed_section(self, monkeypatch):
        first = json.dumps({"intro": TestDropRepeats._FIRST, "summaries": _SUMMARIES,
                            "future": [{"text": TestDropRepeats._FUTURE}]})
        second = json.dumps({"intro": f"{TestDropRepeats._AGAIN} 연구 방법으로는 조사 연구가 가장 많았다 [E3].",
                             "summaries": _SUMMARIES,
                             "future": [{"text": TestDropRepeats._FUTURE.replace("[E1]", "[E2]")}]})
        TestSynthesize()._patch_chat(monkeypatch, [first, second])
        infos = []
        _, on_section = TestSectionProgress()._record(infos)
        report = asyncio.run(synthesize(_state_three(), on_section=on_section))
        assert report["sections"][1]["intro"] == "연구 방법으로는 조사 연구가 가장 많았다 [E3]."
        assert report["sections"][1]["future"] == []
        assert infos[3]["section"] == report["sections"][1]

    def test_intro_made_only_of_repeats_is_not_reported_as_missing(self, monkeypatch):
        reply = json.dumps({"intro": TestDropRepeats._FIRST.replace("[E1]", "[E2]"), "summaries": _SUMMARIES, "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [reply, reply])
        report = asyncio.run(synthesize(_state_three()))
        assert report["sections"][1]["intro"]
        assert not any("도입 문단" in x for x in report["limitations"])
