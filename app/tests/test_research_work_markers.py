"""services/research_work/markers.py — [F#]·숫자·단정 표현·문단 검사(순수 함수).

숫자('확인 필요')와 근거 표시 없는 문장 수(unmarked)는 프론트 utils/figureMarkers.ts 가 같은 규칙으로 화면에
그린다. 두 쪽 테스트가 공용 고정 예제 frontend/tests/fixtures/marker_checks.json 을 함께 읽는다 — 한쪽 규칙을
바꾸려면 이 파일을 고쳐야 하고, 그러면 다른 쪽 테스트가 깨진다(test_paper_citation 의 citation_reference.json 과
같은 방식).
"""
import json
import re
from pathlib import Path

import pytest

from services.research_work.markers import (
    CLAIM_REWRITES, FIGURE_MARKER, FigureResult, check_figures, check_paragraph, figure,
    numbers_outside, soften_claims,
)

SHARED_FIXTURE = (
    Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "marker_checks.json"
)
SHARED_CASES = json.loads(SHARED_FIXTURE.read_text(encoding="utf-8"))


def _ids(prefix: str, text: str) -> set[str]:
    return set(re.findall(rf"\[({prefix}\d+)\]", text))


class TestSharedCases:
    def test_fixture_keeps_the_cases_both_sides_must_agree_on(self):
        # 예제를 줄여 대조를 약하게 만들지 못하게 — 빼야 할 이름 숫자·잡아야 할 숫자·마침표 뒤 마커·[F#] 만 있는 문장
        texts = " ".join(c["text"] for c in SHARED_CASES)
        for name in ("COVID-19", "B2B", "5G", "WHO-5", "2017년", "9편"):
            assert name in texts
        assert any({"2017", "9"} <= set(c["numbers"]) for c in SHARED_CASES)
        assert any(re.search(r"[.!?]\s+\[E\d+\]", c["text"]) for c in SHARED_CASES)
        assert any(_ids("F", c["text"]) and not _ids("E", c["text"]) and c["unmarked"] == 1
                   for c in SHARED_CASES)
        # 표준형이 아닌 [F#](묶음·전각·소문자) — 그 안의 번호는 두 쪽 모두 숫자로 세지 않는다
        assert re.search(r"\[F\d+,\s*F\d+\]", texts) and "［F" in texts and "[f" in texts
        assert all(set(c) == {"text", "numbers", "unmarked", "note"} for c in SHARED_CASES)

    @pytest.mark.parametrize("case", SHARED_CASES, ids=[c["note"] for c in SHARED_CASES])
    def test_numbers_and_unmarked_match_the_shared_fixture(self, case):
        text = case["text"]
        e_ids = _ids("E", text)

        _, _, checks = check_paragraph(text, valid_e=e_ids, valid_f=_ids("F", text),
                                       evidence={e: f"C-{e}" for e in e_ids})

        assert numbers_outside(text) == case["numbers"]
        assert (checks["numbers"], checks["unmarked"]) == (case["numbers"], case["unmarked"])


class TestFigures:
    def test_figure_value_is_text(self):
        assert figure("F1", "이 절에 준 논문 수", 6) == {"id": "F1", "label": "이 절에 준 논문 수", "value": "6"}

    def test_marker_pattern(self):
        assert FIGURE_MARKER.findall("[F1] 과 [F12], [E3]") == ["1", "12"]

    def test_unknown_numbers_are_removed_with_the_space_before(self):
        result = check_figures("논문은 [F9] 편이고 범위는 [F01] 과 [F1] 이다. [F3]", {"F1", "F2"})

        assert result == FigureResult("논문은 편이고 범위는 [F1] 과 [F1] 이다.", ["F1"], ["F9", "F3"])

    def test_citation_markers_are_left_alone(self):
        assert check_figures("가족 지지 [E1] [F1].", {"F1"}).text == "가족 지지 [E1] [F1]."

    @pytest.mark.parametrize("text, expected", [
        ("연구는 [F1, F9]편이다.", FigureResult("연구는 [F1]편이다.", ["F1"], ["F9"])),
        ("범위는 [F1-F2] 이다.", FigureResult("범위는 [F1] [F2] 이다.", ["F1", "F2"], [])),
        ("전각 ［F2］ 와 【f1】.", FigureResult("전각 [F2] 와 [F1].", ["F2", "F1"], [])),
        ("소문자 [f1] 과 [F 02].", FigureResult("소문자 [F1] 과 [F2].", ["F1", "F2"], [])),
        ("없는 번호뿐인 묶음 [F7, F9] 은 지운다.", FigureResult("없는 번호뿐인 묶음 은 지운다.", [], ["F7", "F9"])),
    ])
    def test_bundles_ranges_full_width_and_lower_case_follow_the_citation_grammar(self, text, expected):
        # [E#] 의 bind_markers 와 같은 괄호 문법 — 단일 [F#] 만 보면 묶음 속 없는 번호가 검사 없이 저장 글에 남는다
        assert check_figures(text, {"F1", "F2"}) == expected

    def test_unreadable_figure_brackets_are_removed_and_other_brackets_kept(self):
        result = check_figures("범위는 [F1 참조] 이다. 통계는 [F(2, 98) = 4.2] 이고 [표 1] 을 본다.", {"F1"})

        assert result == FigureResult("범위는 이다. 통계는 [F(2, 98) = 4.2] 이고 [표 1] 을 본다.", [], [],
                                      ["[F1 참조]"])


class TestSoftenClaims:
    @pytest.mark.parametrize("text, expected", [
        ("이에 관한 연구가 거의 없다.", "이에 관한 연구를 소장 코퍼스에서 확인하지 못했다."),
        ("선행연구는 전무하다.", "선행연구를 소장 코퍼스에서 확인하지 못했다."),
        ("관련 논의가 전무한 실정이다.", "관련 논의를 소장 코퍼스에서 확인하지 못했다."),
        ("연구는 전혀 없었다.", "연구를 소장 코퍼스에서 확인하지 못했다."),
        ("이 주제는 아직 연구되지 않았다.", "이 주제는 소장 코퍼스에서 확인되지 않았다."),
        ("실증 분석은 전무하다.", "실증 분석은 소장 코퍼스에서 확인되지 않았다."),
        ("본 연구는 최초로 노인을 분석한다.", "본 연구는 소장 코퍼스에서 확인한 범위에서 처음으로 노인을 분석한다."),
        ("최초의 시도다.", "소장 코퍼스에서 확인한 범위에서 첫 시도다."),
    ])
    def test_absolute_claims_become_corpus_bound(self, text, expected):
        softened, n = soften_claims(text)

        assert (softened, n) == (expected, 1)
        assert soften_claims(softened) == (softened, 0)          # 두 번 거쳐도 같다

    @pytest.mark.parametrize("text", ["연구가 많지 않다.", "두 집단의 차이가 없다.", "전무후무한 사례다."])
    def test_other_sentences_are_untouched(self, text):
        assert soften_claims(text) == (text, 0)

    def test_counts_every_rewrite(self):
        _, n = soften_claims("연구가 없다. 최초로 다룬다. 논의되지 않았다.")
        assert n == 3

    def test_rewrites_are_pattern_and_replacement_pairs(self):
        assert CLAIM_REWRITES and all(
            isinstance(p, str) and isinstance(r, str) for p, r in CLAIM_REWRITES)


class TestCheckParagraph:
    EVIDENCE = {"E1": "KCI_A", "E2": "KCI_B", "E3": "KCI_A"}

    def _check(self, text: str):
        return check_paragraph(text, valid_e=set(self.EVIDENCE), valid_f={"F1", "F2"},
                               evidence=self.EVIDENCE)

    def test_cites_follow_first_appearance_without_repeats(self):
        text, cites, checks = self._check("지지는 우울을 낮춘다 [E2]. 가족 지지가 크다 [E3] [E1].")

        assert text == "지지는 우울을 낮춘다 [E2]. 가족 지지가 크다 [E3] [E1]."
        assert cites == ["KCI_B", "KCI_A"]
        assert checks == {"dropped": 0, "dropped_f": 0, "unmarked": 0, "numbers": [], "softened": 0}

    def test_wrong_markers_are_removed_and_counted(self):
        text, cites, checks = self._check("지지가 크다 [E9] [E01]. 범위는 [F7] 이다 [E1 참조]. 논문 [F02] 편 [E2].")

        assert text == "지지가 크다 [E1]. 범위는 이다. 논문 [F2] 편 [E2]."
        assert cites == ["KCI_A", "KCI_B"]
        assert (checks["dropped"], checks["dropped_f"], checks["unmarked"]) == (2, 1, 1)

    def test_non_standard_figure_markers_are_rewritten_and_counted(self):
        text, _, checks = self._check("연구는 [F1, F9]편이다 [E1]. 범위는 ［f2］이고 [F1 참조] 를 본다 [E2].")

        assert text == "연구는 [F1]편이다 [E1]. 범위는 [F2]이고 를 본다 [E2]."
        assert (checks["dropped"], checks["dropped_f"]) == (0, 2)       # 없는 F9 + 못 읽은 [F1 참조]

    def test_claims_are_softened_and_numbers_counted_on_the_final_text(self):
        text, _, checks = self._check("2017년 이후 연구가 없다 [E1].")

        assert text == "2017년 이후 연구를 소장 코퍼스에서 확인하지 못했다 [E1]."
        assert (checks["numbers"], checks["softened"]) == (["2017"], 1)
