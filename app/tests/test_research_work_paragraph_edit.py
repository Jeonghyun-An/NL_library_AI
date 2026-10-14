"""services/research_work/paragraph_edit.py — 절 문단 고치기의 상태 전이·다시 검증(순수, 정함 17)."""
import pytest

from services.research_work.paragraph_edit import merge_paragraphs, revalidate


def _p(pid: str, text: str, state: str, gen_id: int | None = 41) -> dict:
    return {"id": pid, "text": text, "state": state, "cites": ["KCI_A"], "checks": {"dropped": 0}, "gen_id": gen_id}


STORED = [_p("p1", "첫 문단 [E1].", "proposed"), _p("p2", "둘째 문단 [E1].", "accepted"),
          _p("p3", "고친 문단 [E1].", "edited"), _p("p5", "내가 쓴 문단 [E1].", "authored", None)]


def _req(pid: str | None, text: str, state: str = "proposed") -> dict:
    return {"id": pid, "text": text, "state": state}


class TestMerge:
    @pytest.mark.parametrize("pid, expected", [("p1", "edited"), ("p2", "edited"), ("p3", "edited"),
                                               ("p5", "authored")])
    def test_changed_text_becomes_edited_unless_user_written(self, pid, expected):
        (out,) = merge_paragraphs(STORED, [_req(pid, "바뀐 글 [E1].", "accepted")])
        assert (out["id"], out["text"], out["state"]) == (pid, "바뀐 글 [E1].", expected)
        assert out["gen_id"] == next(p["gen_id"] for p in STORED if p["id"] == pid)

    @pytest.mark.parametrize("pid, requested, expected", [
        ("p1", "accepted", "accepted"), ("p2", "proposed", "proposed"), ("p1", "proposed", "proposed"),
        ("p3", "accepted", "edited"), ("p3", "proposed", "edited"), ("p5", "accepted", "authored"),
        ("p1", "edited", "proposed"), ("p2", "authored", "accepted"),
    ])
    def test_same_text_only_toggles_between_proposed_and_accepted(self, pid, requested, expected):
        text = next(p["text"] for p in STORED if p["id"] == pid)
        (out,) = merge_paragraphs(STORED, [_req(pid, text, requested)])
        assert out["state"] == expected

    def test_new_paragraphs_are_user_written_with_the_next_ids(self):
        out = merge_paragraphs(STORED, [_req(None, "새 문단 [E1].", "accepted"), _req("p9", "모르는 id [E1].")])
        assert [(p["id"], p["state"], p["gen_id"]) for p in out] == [("p6", "authored", None), ("p7", "authored", None)]

    def test_order_follows_the_request_and_missing_ones_are_removed(self):
        out = merge_paragraphs(STORED, [_req("p3", "고친 문단 [E1]."), _req("p1", "첫 문단 [E1].")])
        assert [p["id"] for p in out] == ["p3", "p1"]

    def test_first_id_without_stored_paragraphs_is_p1(self):
        assert merge_paragraphs([], [_req(None, "가 [E1].")])[0]["id"] == "p1"

    def test_same_stored_id_twice_is_rejected(self):
        with pytest.raises(ValueError):
            merge_paragraphs(STORED, [_req("p1", "가 [E1]."), _req("p1", "나 [E1].")])


SECTION = {"evidence": {"E1": "KCI_A", "E2": "KCI_B"}, "figures": [{"id": "F1", "label": "논문 수", "value": "2"}]}


class TestRevalidate:
    def test_markers_and_numbers_are_checked_with_the_section_map(self):
        paragraphs = [{**_p("p1", "", "edited"), "text": "고친 글이다 [E2] [E7]. 연구는 [F1]편이고 표본은 300명이다 [F4]."}]

        (out,) = revalidate(SECTION, paragraphs)

        assert out["text"] == "고친 글이다 [E2]. 연구는 [F1]편이고 표본은 300명이다."
        assert out["cites"] == ["KCI_B"]
        assert out["checks"]["dropped"] == 1 and out["checks"]["dropped_f"] == 1
        assert out["checks"]["numbers"] == ["300"]
        assert (out["id"], out["state"], out["gen_id"]) == ("p1", "edited", 41)

    def test_user_text_keeps_figure_sentences_the_generation_check_drops(self):
        # 수치 자리 밖 [F#] 문장 지우기(markers.drop_misplaced_figures)는 생성 글에만 건다 — 사용자가 쓴 글은 그대로 둔다
        text = "연구는 [F1] 이다 [E1]. 논문 수는 [F1]건이다."

        (out,) = revalidate(SECTION, [{**_p("p1", "", "edited"), "text": text}])

        assert out["text"] == text
        assert (out["checks"]["dropped_f"], out["checks"]["unmarked"]) == (0, 1)

    def test_paragraph_left_empty_is_removed(self):
        assert revalidate(SECTION, [_p("p1", "[E9]", "authored")]) == []

    def test_paragraph_with_the_stored_text_keeps_its_stored_checks(self):
        """화면은 늘 절 전체를 보낸다 — 글이 저장된 것과 같은 문단(손대지 않음·상태만 바뀜)은 다시 검사하지 않는다.
        이미 정리된 글을 다시 검사하면 생성 때 센 dropped·dropped_f·softened 가 0 으로 덮인다."""
        generated = {"dropped": 1, "dropped_f": 1, "unmarked": 0, "numbers": [], "softened": 1}
        stored = [{**_p("p1", "첫 문단 [E1].", "proposed"), "checks": generated},
                  {**_p("p2", "둘째 문단 [E1].", "proposed"), "checks": generated},
                  {**_p("p3", "셋째 문단 [E1].", "proposed"), "checks": generated}]
        merged = merge_paragraphs(stored, [_req("p1", "첫 문단 [E1]."), _req("p2", "둘째 문단 [E1].", "accepted"),
                                           _req("p3", "셋째 문단을 고쳤다 [E2] [E7].")])

        out = revalidate({**SECTION, "paragraphs": stored}, merged)

        assert out[0] == stored[0]
        assert out[1] == {**stored[1], "state": "accepted"}
        assert (out[2]["text"], out[2]["state"], out[2]["cites"]) == ("셋째 문단을 고쳤다 [E2].", "edited", ["KCI_B"])
        assert (out[2]["checks"]["dropped"], out[2]["checks"]["dropped_f"], out[2]["checks"]["softened"]) == (1, 0, 0)

    def test_a_user_edited_gap_claim_is_softened_again(self):
        """06e(06b 이월 §7-13) — 사용자가 고친 글도 생성 때와 같은 검사(check_paragraph)를 다시 탄다. 연구 공백 단정을
        써 넣어도 공백 후보 투로 바뀌고 softened 로 센다(spec 의 'paragraph_edit.py:192-209' 는 지금 revalidate)."""
        paragraphs = [{**_p("p1", "", "edited"), "text": "소장 코퍼스를 분석한 결과 관련 연구가 충분하지 않음을 확인했다 [E1]."}]

        (out,) = revalidate(SECTION, paragraphs)

        assert out["text"] == ("소장 코퍼스를 분석한 결과 관련 연구가 충분하지 않은 것으로 보인다"
                               "(소장 코퍼스에서 확인하지 않은 공백 후보) [E1].")
        assert (out["cites"], out["checks"]["softened"]) == (["KCI_A"], 1)
