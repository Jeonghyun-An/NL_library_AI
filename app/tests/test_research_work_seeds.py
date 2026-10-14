"""services/research_work/seeds.py — 보고서 씨앗 고르기·주제 카드 입력·코퍼스 스냅숏(순수 함수).

보고서는 synthesizer.assemble_report 가 실제로 저장하는 모양을 흉내 낸다 — 절(sections)은 근거가 있는
하위질문만 있고, trail 은 하위질문마다 있다. 그래서 절 순번과 trail 순번이 어긋난다(아래 trail 1 은 근거
0편이라 절이 없다).
"""
import json
from datetime import datetime
from types import SimpleNamespace

from services.research_work.seeds import (
    corpus_of, pick_seeds, seed_evidence, seed_papers, topic_input, used_seed_keys,
)
from services.research_work.shapes import MIN_TOPIC_EVIDENCE, TOPIC_PAPERS_MAX


def _ev(cnts_id: str, title: str, pub_date: str | None) -> dict:
    return {"cnts_id": cnts_id, "chunks": [],
            "meta": {"title": title, "personal_author": "김철수", "pub_date": pub_date,
                     "series_title": "노인복지연구"}}


def _papers(*pairs: tuple[str, str]) -> list[dict]:
    return [{"cnts_id": cnts_id, "summary": "요약", "evidence": [eid]} for cnts_id, eid in pairs]


REPORT = {
    "question": "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
    "range": {"from": "1980", "to": "2017", "n_papers": 144748},
    "sections": [
        {"heading": "노인의 사회적 지지와 우울", "intro": "도입 [E1]",
         "papers": _papers(("P1", "E1"), ("P2", "E2"), ("P3", "E3")),
         "future": [{"text": "독거노인의 지지망을 따로 볼 필요가 있다 [E2]", "evidence": ["E2"]},
                    {"text": "종단 자료로  인과를 확인해야 한다 [E1] [E3]", "evidence": ["E1", "E3"]}]},
        {"heading": "농촌 노인의 우울 위험 요인", "intro": "",
         "papers": _papers(("P4", "E4"), ("P5", "E5")),
         "future": [{"text": "농촌 노인의 우울 선별 도구를 검증할 필요가 있다 [E4]", "evidence": ["E4"]}]},
        {"heading": "노인 우울 중재 프로그램", "intro": "",
         "papers": _papers(("P6", "E6"), ("P1", "E1")),
         "future": [{"text": "중재 효과의 지속 기간을 확인해야 한다 [E6]", "evidence": ["E6"]}]},
        # 향후 과제는 있지만 근거 후보가 1편 — 카드가 근거 2개를 받칠 수 없어 씨앗이 되지 않는다
        {"heading": "노인 우울과 여가", "intro": "",
         "papers": _papers(("P7", "E7")),
         "future": [{"text": "여가 참여의 효과를 볼 필요가 있다 [E7]", "evidence": ["E7"]}]},
    ],
    "evidence": {
        "E1": _ev("P1", "노인의 사회적 지지와 우울의 관계", "2013-05"),
        "E2": _ev("P2", "독거노인의 사회적 관계망", "2015"),
        "E3": _ev("P3", "노인 우울의 종단 연구", None),
        "E4": _ev("P4", "농촌 노인의 우울 요인", "2011"),
        "E5": _ev("P5", "농촌 지역사회 노인 건강", "2009-01"),
        "E6": _ev("P6", "노인 우울 중재 프로그램 효과", "2016"),
        "E7": _ev("P7", "노인의 여가 활동", "2012"),
    },
    "trail": [
        {"subquestion": "노인의 사회적 지지와 우울", "evidence_count": 12, "verdict": "sufficient", "note": "충분하다"},
        {"subquestion": "노인 우울 측정 도구", "evidence_count": 0, "verdict": "insufficient",
         "note": "측정 도구 연구를 찾지 못했다"},
        {"subquestion": "농촌 노인의 우울 위험 요인", "evidence_count": 7, "verdict": "insufficient",
         "note": "농촌 표본 연구가 적다 [E4]"},
        {"subquestion": "노인 우울 중재 프로그램", "evidence_count": 5, "verdict": "sufficient", "note": ""},
        {"subquestion": "노인 우울과 여가", "evidence_count": 1, "verdict": "insufficient", "note": "여가 연구가 적다"},
    ],
}


def _keys(seeds: list[dict]) -> list[str]:
    return [s["key"] for s in seeds]


class TestCorpusOf:
    def test_report_range_and_the_finished_time(self):
        job = SimpleNamespace(report=REPORT, finished_at=datetime(2026, 10, 6, 9, 30))
        assert corpus_of(job) == {"n_papers": 144748, "from": "1980", "to": "2017",
                                  "at": "2026-10-06T09:30:00"}

    def test_unfinished_job_has_no_time(self):
        job = SimpleNamespace(report=REPORT, finished_at=None)
        assert corpus_of(job)["at"] is None

    def test_no_range_means_no_snapshot(self):
        assert corpus_of(SimpleNamespace(report={"sections": []}, finished_at=None)) is None
        assert corpus_of(SimpleNamespace(report=None, finished_at=None)) is None
        assert corpus_of(SimpleNamespace(report={"range": {"from": "1980"}}, finished_at=None)) is None


class TestSeedPapers:
    def test_seed_evidence_first_then_the_section_papers(self):
        assert seed_papers(REPORT, ["E2"], 0) == ["P2", "P1", "P3"]
        assert seed_papers(REPORT, ["E3", "E1"], 0) == ["P3", "P1", "P2"]

    def test_unknown_numbers_and_a_missing_section_add_nothing(self):
        assert seed_papers(REPORT, ["E9", "E4"], None) == ["P4"]
        assert seed_papers(REPORT, [], 9) == []

    def test_papers_without_a_bibliography_are_left_out(self):
        report = {**REPORT, "sections": [{"heading": "h", "papers": _papers(("P1", "E1"), ("X9", "E9"))}]}
        assert seed_papers(report, [], 0) == ["P1"]

    def test_at_most_the_card_paper_limit(self):
        evidence = {f"E{n}": _ev(f"Q{n}", f"논문 {n}", "2010") for n in range(1, 10)}
        section = {"heading": "h", "papers": _papers(*[(f"Q{n}", f"E{n}") for n in range(1, 10)])}
        report = {"sections": [section], "evidence": evidence}
        assert seed_papers(report, ["E9"], 0) == ["Q9", "Q1", "Q2", "Q3", "Q4", "Q5"]
        assert len(seed_papers(report, [], 0)) == TOPIC_PAPERS_MAX


class TestSeedEvidence:
    """향후 과제 씨앗에 보고서가 달았던 근거(cnts_id) — 연구 공백 절이 씨앗 줄에 그 근거의 [E#] 를 붙인다(운영 630e0d65:
    씨앗 문장을 옮긴 첫 문장이 근거 표시 없이 남았다). DB 에 이미 있는 카드의 씨앗도 key 로 풀린다."""

    def test_the_future_evidence_in_order(self):
        seeds = {s["key"]: s for s in pick_seeds(REPORT, limit=None)}
        assert seed_evidence(REPORT, seeds["future:0:1"]) == ["P1", "P3"]
        assert seed_evidence(REPORT, seeds["future:1:0"]) == ["P4"]

    def test_insufficient_and_user_card_seeds_have_none(self):
        seeds = {s["key"]: s for s in pick_seeds(REPORT, limit=None)}
        assert seed_evidence(REPORT, seeds["insufficient:2"]) == []
        assert seed_evidence(REPORT, {}) == []

    def test_a_key_that_no_longer_points_at_that_future_has_none(self):
        # 번호가 범위를 벗어나거나 그 자리의 향후 과제 글이 씨앗 글과 다르면 엉뚱한 근거를 붙이지 않는다
        seed = pick_seeds(REPORT, limit=1)[0]
        assert seed_evidence(REPORT, {**seed, "key": "future:9:0"}) == []
        assert seed_evidence(REPORT, {**seed, "key": "future:0:1"}) == []
        assert seed_evidence(REPORT, {**seed, "key": "future:x:0"}) == []
        assert seed_evidence({}, seed) == [] and seed_evidence(None, seed) == []


class TestPickSeeds:
    def test_one_seed_per_section_before_a_second_from_any(self):
        seeds = pick_seeds(REPORT, limit=None)
        assert _keys(seeds) == ["future:0:0", "future:1:0", "future:2:0", "future:0:1", "insufficient:2"]

    def test_seed_shape(self):
        first, second = pick_seeds(REPORT, limit=2)
        assert first == {
            "key": "future:0:0", "kind": "future", "section_idx": 0, "subq_idx": 0,
            "heading": "노인의 사회적 지지와 우울", "text": "독거노인의 지지망을 따로 볼 필요가 있다",
            "papers": ["P2", "P1", "P3"], "adopted": 12,
        }
        assert (second["section_idx"], second["subq_idx"], second["adopted"]) == (1, 2, 7)

    def test_limit(self):
        assert _keys(pick_seeds(REPORT, limit=4)) == ["future:0:0", "future:1:0", "future:2:0", "future:0:1"]
        assert pick_seeds(REPORT, limit=0) == []

    def test_insufficient_note_joins_its_section_by_the_heading(self):
        # trail 2 는 절 1 이다(근거 0편인 trail 1 은 절이 없다) — 순번이 아니라 소제목으로 잇는다
        (seed,) = [s for s in pick_seeds(REPORT, limit=None) if s["kind"] == "insufficient"]
        assert seed == {
            "key": "insufficient:2", "kind": "insufficient", "section_idx": 1, "subq_idx": 2,
            "heading": "농촌 노인의 우울 위험 요인", "text": "농촌 표본 연구가 적다",
            "papers": ["P4", "P5"], "adopted": 7,
        }

    def test_notes_of_subquestions_without_a_section_are_not_seeds(self):
        assert "insufficient:1" not in _keys(pick_seeds(REPORT, limit=None))

    def test_seeds_that_cannot_hold_two_evidence_chips_are_dropped(self):
        keys = _keys(pick_seeds(REPORT, limit=None))
        assert MIN_TOPIC_EVIDENCE == 2
        assert "future:3:0" not in keys and "insufficient:4" not in keys

    def test_excluded_keys_and_their_text_are_not_picked_again(self):
        report = json.loads(json.dumps(REPORT))
        # 절 2 의 향후 과제가 절 0 의 첫 과제와 같은 글(공백·대소문자만 다름)
        report["sections"][2]["future"].append({"text": "독거노인의  지지망을 따로 볼 필요가 있다", "evidence": []})
        assert "future:2:1" not in _keys(pick_seeds(report, limit=None))
        # 쓴 씨앗은 제 차례를 차지한 채 건너뛴다 — 남은 것은 돌던 순서 그대로(절 2 → 절 0 의 둘째 → …)
        left = pick_seeds(report, limit=None, exclude={"future:0:0", "future:1:0"})
        assert _keys(left) == ["future:2:0", "future:0:1", "insufficient:2"]
        assert _keys(pick_seeds(REPORT, limit=2, exclude={"future:0:0"})) == ["future:1:0", "future:2:0"]

    def test_nothing_left(self):
        used = _keys(pick_seeds(REPORT, limit=None))
        assert pick_seeds(REPORT, limit=2, exclude=used) == []

    def test_reports_without_seeds(self):
        assert pick_seeds({}, limit=4) == []
        assert pick_seeds(None, limit=4) == []
        assert pick_seeds({"sections": [{"heading": "h", "future": [{"text": "  [E1] "}]}]}, limit=4) == []

    def test_seeds_survive_a_jsonb_round_trip(self):
        seeds = pick_seeds(REPORT, limit=None)
        assert json.loads(json.dumps(seeds, ensure_ascii=False)) == seeds


# 운영 d60a5dc1(2026-10-14) 보고서의 꼴 — 종합이 절마다 거의 같은 향후 과제를 썼다. 절 0 과 절 3 은 '유형'과 '형태' 한 낱말만
# 다르고(이어가기가 slot1·slot4 에 둘을 넣어 카드 제목이 똑같이 나왔다), 절 5 는 절 3 과 글자까지 같다. insufficient note 는
# 머리('제공된 근거들은 … 다루고 있지만,')가 같은 틀 문장이라 서로 다른 씨앗으로 남아야 한다
_LIVE_HEADINGS = [f"하위질문 {n}" for n in range(6)]
_LIVE_FUTURES = [
    ["향후 연구에서는 사회적 지지의 구체적인 유형과 노인의 우울 감소 효과 간의 관계를 심층적으로 분석할 필요가 있다 [E1]."],
    ["향후 연구에서는 다양한 사회적 지지 유형(가족, 친구, 지역사회 등)이 노인의 우울에 미치는 영향에 대한 심층적인 분석이 필요하다 [E2]."],
    ["노인의 우울 감소를 위한 프로그램 개발 및 효과 검증 연구가 필요하다 [E1].",
     "다양한 사회경제적 배경을 가진 노인의 우울에 대한 영향 요인을 심층적으로 분석하는 연구가 요구된다 [E2]."],
    ["향후 연구에서는 사회적 지지의 구체적인 형태와 노인의 우울 감소 효과 간의 관계를 심층적으로 분석할 필요가 있다 [E1].",
     "또한, 다양한 사회경제적 배경을 가진 노인의 사회적 관계와 우울 간의 상호 영향을 종단적으로 분석하여 정책적 시사점을 도출해야 한다 [E2]."],
    ["연구 결과의 일반화를 위해서는 여러 노인 집단을 포함하여 연구할 필요성이 있다. [E1]",
     "향후 연구에서는 횡단적 자료가 아닌 종단적 자료를 활용하여 인과관계를 보다 명확하게 규명해야 할 것이다. [E1]",
     "복지 사각지대에 있는 노인들의 스트레스와 우울에 대한 심층적인 연구가 필요하다. [E1]"],
    ["향후 연구에서는 사회적 지지의 구체적인 형태와 노인의 우울 감소 효과 간의 관계를 심층적으로 분석할 필요가 있다 [E1]."],
]
_LIVE_NOTES = {
    0: "제시된 근거들은 노인의 우울과 사회적 지지 간의 관계를 다루고 있지만, 국내 학술 논문에서 이 두 개념이 어떻게 "
       "정의되고 있는지에 대한 직접적인 설명을 담고 있지는 않아서 부족합니다.",
    1: "제공된 근거들은 노인의 우울과 사회적 지지 간의 관계를 다루고 있지만, 구체적으로 어떤 방법 및 기법이 국내 학술 "
       "논문에서 사용되었는지에 대한 상세한 설명은 부족합니다.",
    4: "제공된 근거들은 노인의 우울과 사회적 지지 간의 관계를 다루고 있지만, 연구의 한계점 및 과제에 대한 심층적인 논의는 "
       "부족합니다.",
    5: "제공된 근거들은 노인의 우울과 사회적 지지 간의 관계를 다루고 있지만, 국내 학술 논문의 연구 동향 변화를 '시간의 "
       "흐름에 따른' 구체적인 변화 양상을 보여주지 못하고 있습니다.",
}
LIVE_REPORT = {
    "sections": [{"heading": h, "papers": _papers(("P1", "E1"), ("P2", "E2")),
                  "future": [{"text": t, "evidence": ["E1"]} for t in futures]}
                 for h, futures in zip(_LIVE_HEADINGS, _LIVE_FUTURES)],
    "evidence": {"E1": _ev("P1", "노인의 사회적 지지와 우울", "2013"), "E2": _ev("P2", "노인 우울의 위험 요인", "2015")},
    "trail": [{"subquestion": h, "evidence_count": 5,
               "verdict": "insufficient" if t in _LIVE_NOTES else "sufficient", "note": _LIVE_NOTES.get(t, "")}
              for t, h in enumerate(_LIVE_HEADINGS)],
}


class TestNearSameSeeds:
    def test_seeds_that_differ_by_a_word_are_one_seed(self):
        # 한 낱말('유형'↔'형태')만 다른 향후 과제는 같은 씨앗이다 — 앞 절의 것만 남는다
        report = json.loads(json.dumps(REPORT))
        report["sections"][2]["future"].append(
            {"text": "독거노인의 지원망을 따로 볼 필요가 있다 [E6]", "evidence": ["E6"]})
        assert "future:2:1" not in _keys(pick_seeds(report, limit=None))

    def test_punctuation_and_markers_do_not_make_a_seed_new(self):
        report = json.loads(json.dumps(REPORT))
        report["sections"][2]["future"].append(
            {"text": "독거노인의 지지망을, 따로 볼 필요가 있다. [E6]", "evidence": ["E6"]})
        assert "future:2:1" not in _keys(pick_seeds(report, limit=None))

    def test_a_seed_near_an_excluded_one_is_not_picked_again(self):
        # [다른 방향] — 이미 카드로 쓴 씨앗과 거의 같은 글도 다시 고르지 않는다
        report = json.loads(json.dumps(REPORT))
        report["sections"][2]["future"].append(
            {"text": "독거노인의 지원망을 따로 볼 필요가 있다 [E6]", "evidence": ["E6"]})
        left = pick_seeds(report, limit=None, exclude={"future:0:0"})
        assert "future:2:1" not in _keys(left)
        assert _keys(left) == ["future:1:0", "future:2:0", "future:0:1", "insufficient:2"]

    def test_live_report_gives_four_different_slots(self):
        # 운영 d60a5dc1 — 고치기 전에는 [future:0:0, 1:0, 2:0, 3:0] 이라 slot1·slot4 카드 제목이 같았다
        assert _keys(pick_seeds(LIVE_REPORT, limit=4)) == ["future:0:0", "future:1:0", "future:2:0", "future:4:0"]

    def test_live_report_keeps_template_notes_and_different_futures(self):
        # 틀 문장이 같은 insufficient note·서로 다른 향후 과제는 합치지 않는다 — 빠지는 것은 절 0 과 거의 같은 3:0·5:0 뿐
        assert _keys(pick_seeds(LIVE_REPORT, limit=None)) == [
            "future:0:0", "future:1:0", "future:2:0", "future:4:0",
            "insufficient:0", "insufficient:1", "future:2:1", "future:3:1", "future:4:1", "insufficient:5",
            "future:4:2", "insufficient:4",
        ]


class TestTopicInput:
    def test_shape(self):
        seed = pick_seeds(REPORT, limit=1)[0]
        assert topic_input("노인의 우울과 사회적 지지에 관한 연구가 궁금해", seed, REPORT, 12) == {
            "topic_id": 12,
            "question": "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
            "seed": {"heading": "노인의 사회적 지지와 우울", "text": "독거노인의 지지망을 따로 볼 필요가 있다"},
            "papers": [
                {"eid": "E1", "cnts_id": "P2", "title": "독거노인의 사회적 관계망", "year": 2015},
                {"eid": "E2", "cnts_id": "P1", "title": "노인의 사회적 지지와 우울의 관계", "year": 2013},
                {"eid": "E3", "cnts_id": "P3", "title": "노인 우울의 종단 연구", "year": None},
            ],
            "adopted": 12,
            "corpus": {"n_papers": 144748, "from": "1980", "to": "2017"},
            "keywords": [],
            "focus": [],
        }

    def test_topic_input_carries_the_added_keywords_as_focus(self):
        # [이 키워드로 다시 만들기]가 카드를 만들 때보다 더한 키워드를 focus 로 싣는다(운영 630e0d65). 처음 카드·
        # [다른 방향]은 넘기지 않아 빈 목록이다. 넘긴 목록을 복사해 둔다
        seed = pick_seeds(REPORT, limit=1)[0]
        added = ["측정 방법"]
        made = topic_input("q", seed, REPORT, 12, keywords=["노인 우울", "측정 방법"], focus=added)
        assert made["focus"] == added and made["focus"] is not added
        assert topic_input("q", seed, REPORT, 12, keywords=["노인 우울"])["focus"] == []
        assert topic_input("q", seed, REPORT, 12, keywords=["노인 우울"], focus=None)["focus"] == []

    def test_topic_input_carries_the_keywords_or_an_empty_list(self):
        # 06e D23 — 카드를 만들 때 고른 키워드(work.concepts)를 입력에 싣는다. 넘긴 목록을 복사해 둔다
        seed = pick_seeds(REPORT, limit=1)[0]
        picked = ["노인 우울", "사회적 지지"]
        made = topic_input("q", seed, REPORT, 12, keywords=picked)
        assert made["keywords"] == picked and made["keywords"] is not picked
        assert topic_input("q", seed, REPORT, 12, keywords=None)["keywords"] == []

    def test_missing_range_and_counts_are_null(self):
        seed = {"heading": "h", "text": "t", "papers": ["P1", "P2"], "adopted": None}
        report = {k: v for k, v in REPORT.items() if k != "range"}
        made = topic_input("q", seed, report, 1)
        assert made["corpus"] is None and made["adopted"] is None
        assert [p["eid"] for p in made["papers"]] == ["E1", "E2"]

    def test_the_input_survives_a_jsonb_round_trip(self):
        made = topic_input("q", pick_seeds(REPORT, limit=1)[0], REPORT, 3)
        assert json.loads(json.dumps(made, ensure_ascii=False)) == made


class TestUsedSeedKeys:
    def test_from_stored_seeds_and_topic_items(self):
        seeds = pick_seeds(REPORT, limit=2)
        topics = [seeds[0], {"id": 9, "seed": seeds[1]}, {}, {"id": 10, "seed": None}, {"key": ""}]
        assert used_seed_keys(topics) == {"future:0:0", "future:1:0"}

    def test_user_cards_use_no_seed(self):
        assert used_seed_keys([{}, {"seed": {}}]) == set()
