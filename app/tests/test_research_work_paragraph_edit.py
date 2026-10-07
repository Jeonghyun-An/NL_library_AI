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

    def test_paragraph_left_empty_is_removed(self):
        assert revalidate(SECTION, [_p("p1", "[E9]", "authored")]) == []
