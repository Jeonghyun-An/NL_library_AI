"""services/research_work/views.py — 연구 어시스턴트 API 응답을 만드는 순수 함수.

입력은 워커가 실제로 저장하는 모양(state_snapshot·report.trail·research_steps.result.rounds)을
그대로 흉내 낸다. 06a 뒤 잡의 회차에는 adopted_papers 가 있고(Task 3), 그 전 잡에는 없다.
"""
import json
import uuid
from types import SimpleNamespace

from services.research_work.views import candidates_from_snapshot, pool_from_job, work_view

X1 = {"cnts_id": "X1", "title": "무관 논문", "personal_author": "박민수", "pub_date": "2015"}
X2 = {"cnts_id": "X2", "title": "다른 뜻 논문", "personal_author": "최", "pub_date": "2012"}
C1_BRIEF = {"cnts_id": "C1", "title": "독서 격차 연구", "personal_author": "김철수",
            "pub_date": "2019-03"}
C2_BRIEF = {"cnts_id": "C2", "title": "학교 도서관", "personal_author": "이영희", "pub_date": "2017"}
C3_BRIEF = {"cnts_id": "C3", "title": "가정 독서 환경", "personal_author": "정", "pub_date": "2011"}

# 하위질문 0 — 06a 뒤 잡(회차마다 adopted_papers). 1회차에 C1 채택·X1 제외, 2회차에 C2 채택.
ROUNDS_0 = [
    {"round": 1, "query": "독서 격차 원인", "found_chunks": 9, "new_papers": 2,
     "verdict": "insufficient", "note": "가정 요인이 부족하다", "next_query": "가정 독서 환경",
     "excluded": 1, "excluded_papers": [X1], "flagged": 0, "flagged_papers": [],
     "adopted_papers": [{**C1_BRIEF, "rank": 1, "new": True}]},
    {"round": 2, "query": "가정 독서 환경", "found_chunks": 7, "new_papers": 1,
     "verdict": "sufficient", "note": "충분하다", "next_query": None,
     "excluded": 0, "excluded_papers": [], "flagged": 0, "flagged_papers": [],
     "adopted_papers": [{"cnts_id": "C1", "rank": 1}, {**C2_BRIEF, "rank": 2, "new": True}]},
]
# 하위질문 1 — 06a 전 잡과 같은 회차(adopted_papers 없음). 1회차에 X2 제외.
ROUNDS_1 = [
    {"round": 1, "query": "독서 격차 영향", "found_chunks": 5, "new_papers": 2,
     "verdict": "insufficient", "note": "영향 연구가 적다", "next_query": None,
     "excluded": 1, "excluded_papers": [X2], "flagged": 0, "flagged_papers": []},
]


def _snapshot() -> dict:
    return {
        "question": "청소년 독서 격차",
        "params": {},
        "corpus_range": {"from": "2002", "to": "2026", "n_papers": 72054},
        "subquestions": [
            {"idx": 0, "text": "독서 격차의 원인", "queries": ["독서 격차 원인", "가정 독서 환경"],
             "evidence_ids": ["E1", "E2"], "verdict": "sufficient", "parse_failed": False,
             "failed": False, "note": "충분하다", "capped": 0, "budget_capped": 0,
             "evidence_chunks": {"E1": ["c1", "c2"], "E2": ["c3"]},
             "chunk_scores": {"c1": 0.91, "c2": 0.7, "c3": 0.65},
             "rounds": ROUNDS_0, "excluded_cnts": ["X1"]},
            {"idx": 1, "text": "독서 격차의 영향", "queries": ["독서 격차 영향"],
             "evidence_ids": ["E3", "E1"], "verdict": "insufficient", "parse_failed": False,
             "failed": False, "note": "영향 연구가 적다", "capped": 0, "budget_capped": 0,
             "evidence_chunks": {"E3": ["c4"], "E1": ["c1"]},
             "chunk_scores": {"c4": 0.8, "c1": 0.5},
             "rounds": ROUNDS_1, "excluded_cnts": ["X2"]},
        ],
        "evidence": {
            "E1": {"cnts_id": "C1", "meta": {**C1_BRIEF, "series_title": "교육학연구"},
                   "chunks": [{"chunk_id": "c1", "text": "가", "page_start": 1, "page_end": 1,
                               "score": 0.91}]},
            "E2": {"cnts_id": "C2", "meta": {**C2_BRIEF, "series_title": None}, "chunks": []},
            "E3": {"cnts_id": "C3", "meta": {**C3_BRIEF, "series_title": "독서연구"}, "chunks": []},
        },
        "evidence_seq": 3,
        "seen_cnts": ["C1", "C2", "C3", "X1", "X2"],
    }


def _steps(rounds_0=ROUNDS_0, rounds_1=ROUNDS_1) -> list[dict]:
    return [
        {"seq": 1, "kind": "search", "subq_idx": 0, "status": "done", "result": {"rounds": rounds_0}},
        {"seq": 2, "kind": "search", "subq_idx": 1, "status": "done", "result": {"rounds": rounds_1}},
    ]


class TestCandidatesFromSnapshot:
    def test_no_snapshot_means_no_candidates(self):
        assert candidates_from_snapshot(None) == []
        assert candidates_from_snapshot({}) == []

    def test_every_adopted_paper_becomes_a_candidate_with_its_stored_path(self):
        assert candidates_from_snapshot(_snapshot()) == [
            {"cnts_id": "C1", "origin": "evidence", "origin_ref": {
                "subq_idx": [0, 1], "rank": {"0": 1, "1": 2},
                "chunks": {"0": ["c1", "c2"], "1": ["c1"]},
                "chunk_scores": {"0": {"c1": 0.91, "c2": 0.7}, "1": {"c1": 0.5}},
                "verdict": {"0": "sufficient", "1": "insufficient"},
                "first_round": {"0": 1}}},
            {"cnts_id": "C2", "origin": "evidence", "origin_ref": {
                "subq_idx": [0], "rank": {"0": 2}, "chunks": {"0": ["c3"]},
                "chunk_scores": {"0": {"c3": 0.65}}, "verdict": {"0": "sufficient"},
                "first_round": {"0": 2}}},
            # 하위질문 1 의 회차에는 adopted_papers 가 없다(06a 전 잡) — 처음 채택된 회차를 비운다
            {"cnts_id": "C3", "origin": "evidence", "origin_ref": {
                "subq_idx": [1], "rank": {"1": 1}, "chunks": {"1": ["c4"]},
                "chunk_scores": {"1": {"c4": 0.8}}, "verdict": {"1": "insufficient"}}},
        ]

    def test_path_survives_a_jsonb_round_trip(self):
        # 하위질문 번호 키를 문자열로 둔다 — 정수 키는 JSONB 에 저장되며 문자열이 되어 읽은 값이 달라진다
        out = candidates_from_snapshot(_snapshot())
        assert json.loads(json.dumps(out)) == out

    def test_evidence_outside_every_subquestion_is_kept_last_without_a_path(self):
        snap = _snapshot()
        snap["evidence"]["E9"] = {"cnts_id": "C9", "meta": {"title": "외톨이"}, "chunks": []}
        assert candidates_from_snapshot(snap)[-1] == {
            "cnts_id": "C9", "origin": "evidence",
            "origin_ref": {"subq_idx": [], "rank": {}, "chunks": {}, "chunk_scores": {},
                           "verdict": {}},
        }

    def test_one_row_per_paper(self):
        # research_reading 의 PK 는 (work_id, cnts_id) — 같은 논문이 두 번 나오면 한 INSERT 안에서 부딪친다
        snap = _snapshot()
        snap["evidence"]["E4"] = {"cnts_id": "C1", "meta": {}, "chunks": []}
        snap["subquestions"][1]["evidence_ids"].append("E4")
        ids = [c["cnts_id"] for c in candidates_from_snapshot(snap)]
        assert ids == ["C1", "C2", "C3"]


class TestPoolFromJob:
    def test_completed_job_lists_every_adopted_paper_from_the_snapshot(self):
        job = SimpleNamespace(state_snapshot=_snapshot(), report={"trail": []})
        pool = pool_from_job(job, _steps())
        assert pool["adopted"] == [
            {**C1_BRIEF, "series_title": "교육학연구", "subq_idx": [0, 1], "rank": 1},
            {**C2_BRIEF, "series_title": None, "subq_idx": [0], "rank": 2},
            {**C3_BRIEF, "series_title": "독서연구", "subq_idx": [1], "rank": 1},
        ]

    def test_paper_in_two_subquestions_takes_its_best_rank(self):
        snap = _snapshot()
        snap["subquestions"][1]["evidence_ids"] = ["E2", "E3", "E1"]
        job = SimpleNamespace(state_snapshot=snap, report=None)
        adopted = pool_from_job(job, [])["adopted"]
        assert [(p["cnts_id"], p["subq_idx"], p["rank"]) for p in adopted] == [
            ("C1", [0, 1], 1), ("C2", [0, 1], 1), ("C3", [1], 2),
        ]

    def test_completed_job_takes_excluded_papers_from_the_trail_with_round_and_note(self):
        trail = [{"subquestion": "독서 격차의 원인", "excluded_papers": [X1]},
                 {"subquestion": "독서 격차의 영향", "excluded_papers": [X2]}]
        job = SimpleNamespace(state_snapshot=_snapshot(), report={"trail": trail})
        assert pool_from_job(job, _steps())["excluded"] == [
            {**X1, "subq_idx": 0, "round": 1, "note": "가정 요인이 부족하다"},
            {**X2, "subq_idx": 1, "round": 1, "note": "영향 연구가 적다"},
        ]

    def test_trail_paper_excluded_in_two_subquestions_takes_its_own_subquestions_round(self):
        # X1 은 하위질문 0 의 1회차와 하위질문 1 의 2회차에서 빠졌다 — 회차는 trail 항목의 하위질문에서 찾는다
        rounds_1 = [*ROUNDS_1, {"round": 2, "query": "독서 격차 결과", "found_chunks": 4,
                                "new_papers": 0, "verdict": "insufficient",
                                "note": "다른 뜻으로 쓴 논문이다", "next_query": None, "excluded": 1,
                                "excluded_papers": [X1], "flagged": 0, "flagged_papers": []}]
        trail = [{"excluded_papers": [X1]}, {"excluded_papers": [X2, X1]}]
        job = SimpleNamespace(state_snapshot=_snapshot(), report={"trail": trail})
        assert pool_from_job(job, _steps(rounds_1=rounds_1))["excluded"] == [
            {**X1, "subq_idx": 0, "round": 1, "note": "가정 요인이 부족하다"},
            {**X2, "subq_idx": 1, "round": 1, "note": "영향 연구가 적다"},
            {**X1, "subq_idx": 1, "round": 2, "note": "다른 뜻으로 쓴 논문이다"},
        ]

    def test_trail_paper_without_a_round_record_keeps_round_and_note_empty(self):
        # 회차 기록이 없는 옛 잡 — trail 의 서지는 그대로 싣는다
        job = SimpleNamespace(state_snapshot=_snapshot(),
                              report={"trail": [{"excluded_papers": [X1]}]})
        assert pool_from_job(job, [])["excluded"] == [
            {**X1, "subq_idx": 0, "round": None, "note": None},
        ]

    def test_running_job_builds_the_pool_from_the_rounds(self):
        job = SimpleNamespace(state_snapshot=None, report=None)
        pool = pool_from_job(job, _steps())
        # 하위질문 0 은 마지막 회차의 adopted_papers 가 지금 채택 목록이다. 서지는 새로 채택된 회차의 값.
        # 하위질문 1 은 06a 전 회차라 채택 목록이 없다
        assert pool["adopted"] == [
            {**C1_BRIEF, "series_title": None, "subq_idx": [0], "rank": 1},
            {**C2_BRIEF, "series_title": None, "subq_idx": [0], "rank": 2},
        ]
        assert pool["excluded"] == [
            {**X1, "subq_idx": 0, "round": 1, "note": "가정 요인이 부족하다"},
            {**X2, "subq_idx": 1, "round": 1, "note": "영향 연구가 적다"},
        ]

    def test_running_job_merges_a_paper_adopted_by_two_subquestions(self):
        # C2 는 하위질문 0 에서 2위, 1 에서 1위 — 가장 앞선 순위를 쓴다
        rounds_1 = [{**ROUNDS_1[0], "adopted_papers": [
            {**C2_BRIEF, "rank": 1, "new": True}, {**C3_BRIEF, "rank": 2, "new": True}]}]
        job = SimpleNamespace(state_snapshot=None, report=None)
        adopted = pool_from_job(job, _steps(rounds_1=rounds_1))["adopted"]
        assert [(p["cnts_id"], p["subq_idx"], p["rank"]) for p in adopted] == [
            ("C1", [0], 1), ("C2", [0, 1], 1), ("C3", [1], 2),
        ]

    def test_retried_search_step_replaces_the_earlier_one(self):
        # 재시도로 같은 하위질문의 탐색 단계가 새로 생기면 뒤(seq 가 큰) 단계가 지금 상태다
        later = [{**ROUNDS_0[0], "excluded_papers": [], "adopted_papers": [
            {**C2_BRIEF, "rank": 1, "new": True}]}]
        steps = [*_steps(), {"seq": 3, "kind": "search", "subq_idx": 0, "status": "running",
                             "result": {"rounds": later}}]
        pool = pool_from_job(SimpleNamespace(state_snapshot=None, report=None), steps)
        assert [p["cnts_id"] for p in pool["adopted"]] == ["C2"]
        assert [p["cnts_id"] for p in pool["excluded"]] == ["X2"]

    def test_nothing_recorded_yet(self):
        job = SimpleNamespace(state_snapshot=None, report=None)
        assert pool_from_job(job, []) == {"adopted": [], "excluded": []}
        steps = [{"seq": 1, "kind": "search", "subq_idx": 0, "status": "running", "result": {}}]
        assert pool_from_job(job, steps) == {"adopted": [], "excluded": []}


def _gen(id, status, **kw):
    return SimpleNamespace(id=id, kind=kw.get("kind", "concepts"), target=kw.get("target"),
                           status=status, model=kw.get("model"), error=kw.get("error"))


class TestWorkView:
    def test_shape(self):
        work = SimpleNamespace(
            id="0b9f6c3e-1d2a-4f5b-8c7d-6e5f4a3b2c1d", phase="topics",
            concepts=["독서 격차", "청소년"], memo="메모", is_example=False, progress={"topics": 0},
        )
        gens = [_gen(7, "queued"), _gen(3, "done", model="qwen3-vl-8b"),
                _gen(5, "failed", error="시간 초과")]
        assert work_view(work, gens, {7: 2}) == {
            "id": "0b9f6c3e-1d2a-4f5b-8c7d-6e5f4a3b2c1d", "phase": "topics",
            "concepts": ["독서 격차", "청소년"], "memo": "메모", "is_example": False,
            "progress": {"topics": 0},
            "generations": [
                {"id": 3, "kind": "concepts", "target": None, "status": "done",
                 "model": "qwen3-vl-8b", "error": None, "position": None},
                {"id": 5, "kind": "concepts", "target": None, "status": "failed",
                 "model": None, "error": "시간 초과", "position": None},
                {"id": 7, "kind": "concepts", "target": None, "status": "queued",
                 "model": None, "error": None, "position": 2},
            ],
        }

    def test_id_is_a_string(self):
        wid = uuid.uuid4()
        work = SimpleNamespace(id=wid, phase="topics", concepts=[], memo=None, is_example=True,
                               progress={})
        view = work_view(work, [], {})
        assert view["id"] == str(wid) and view["is_example"] is True and view["generations"] == []
