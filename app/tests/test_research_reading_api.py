"""test_research_reading_api.py — 읽기 목록(services/research_work/reading_views.py·api/research_reading.py).

앞 절은 응답 모양 순수 함수, 뒤 절은 TestClient 로 라우팅을 거치는 API 다. DB 는 history_sqlite 의 SQLite —
서지(library_catalog)·읽기 목록 행·진행 요약을 실제 SQL 로 읽고 쓴다. 요청이 끝나면 세션을 되돌리므로 핸들러가
직접 커밋한 쓰기만 남는다. redis 는 로컬 venv 에 없다 — 미설치일 때만 더미를 꽂고 publish_work 는 기록용 가짜다.
"""
import ast
import importlib
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from history_sqlite import (
    AsyncSessionOverSync, add_book, add_proposal, add_reading, add_research_job, add_topic, add_work,
    make_engine,
)
from models.research import ResearchJob
from models.research_work import ResearchReading, ResearchWork
from services.research_work.reading_views import (
    book_meta, excluded_candidates, funnel, preselect, reading_item, reading_order, reading_path, reading_view,
    subquestions_of,
)
from services.research_work.shapes import MIN_READING_FOR_OUTLINE, PATH_CHUNK_CHARS, READING_PRESELECT

PLAN = ["독서 격차의 원인", "독서 격차의 영향"]
LONG = "가" * (PATH_CHUNK_CHARS + 50)
X1 = {"cnts_id": "X1", "title": "무관 논문", "personal_author": "박민수", "pub_date": "2015"}
X2 = {"cnts_id": "X2", "title": "다른 뜻 논문", "personal_author": "최", "pub_date": "2012"}
ROUNDS_0 = [
    {"round": 1, "query": "독서 격차 원인", "verdict": "insufficient", "note": "가정 요인이 부족하다",
     "excluded": 1, "excluded_papers": [X1]},
    {"round": 2, "query": "가정 독서 환경", "verdict": "sufficient", "note": "충분하다",
     "excluded": 0, "excluded_papers": []},
]
ROUNDS_1 = [
    {"round": 1, "query": "독서 격차 영향", "verdict": "insufficient", "note": "영향 연구가 적다",
     "excluded": 2, "excluded_papers": [X2, X1]},
]
SNAPSHOT = {
    "question": "청소년 독서 격차",
    "subquestions": [
        {"idx": 0, "text": PLAN[0], "evidence_ids": ["E1", "E2"], "verdict": "sufficient",
         "evidence_chunks": {"E1": ["c1", "c2"], "E2": ["c3"]},
         "chunk_scores": {"c1": 0.91, "c2": 0.7, "c3": 0.65}, "rounds": ROUNDS_0},
        {"idx": 1, "text": PLAN[1], "evidence_ids": ["E1"], "verdict": "insufficient",
         "evidence_chunks": {"E1": ["c1"]}, "chunk_scores": {"c1": 0.5}, "rounds": ROUNDS_1},
    ],
    "evidence": {
        "E1": {"cnts_id": "C1", "meta": {"title": "독서 격차 연구"},
               "chunks": [{"chunk_id": "c1", "text": LONG, "page_start": 3, "page_end": 4, "score": 0.91},
                          {"chunk_id": "c2", "text": "둘째 대목", "page_start": 5, "page_end": 5,
                           "score": 0.7}]},
        "E2": {"cnts_id": "C2", "meta": {"title": "학교 도서관"},
               "chunks": [{"chunk_id": "c3", "text": "학교 대목", "page_start": 0, "page_end": 0,
                           "score": 0.65}]},
    },
}
REPORT = {
    "question": "청소년 독서 격차",
    "stats": {"papers_reviewed": 121, "evidence_adopted": 48, "rechecks": 1, "excluded": 2},
    "trail": [{"subquestion": PLAN[0], "excluded_papers": [X1]},
              {"subquestion": PLAN[1], "excluded_papers": [X2, X1]}],
}
# 이어가기(candidates_from_snapshot)가 C1·C2 에 남기는 들어온 경로 그대로
REF_C1 = {"subq_idx": [0, 1], "rank": {"0": 1, "1": 1}, "chunks": {"0": ["c1", "c2"], "1": ["c1"]},
          "chunk_scores": {"0": {"c1": 0.91, "c2": 0.7}, "1": {"c1": 0.5}},
          "verdict": {"0": "sufficient", "1": "insufficient"}, "first_round": {"0": 1}}
REF_C2 = {"subq_idx": [0], "rank": {"0": 2}, "chunks": {"0": ["c3", "c9"]},
          "chunk_scores": {"0": {"c3": 0.65}}, "verdict": {"0": "sufficient"}}


def _job_ns(**fields) -> SimpleNamespace:
    base = {"plan": PLAN, "state_snapshot": SNAPSHOT, "report": REPORT}
    return SimpleNamespace(**{**base, **fields})


def _path_text(text: str) -> str:
    """대목 하나(글 text)를 단 스냅숏으로 들어온 경로를 그려 그 대목의 글만."""
    snapshot = {"evidence": {"E1": {"cnts_id": "C1", "chunks": [{"chunk_id": "c1", "text": text}]}}}
    ref = {"subq_idx": [0], "rank": {"0": 1}, "chunks": {"0": ["c1"]}}
    return reading_path("evidence", ref, snapshot, PLAN)["subqs"][0]["chunks"][0]["text"]


def _row(cnts_id, **fields) -> SimpleNamespace:
    base = {"cnts_id": cnts_id, "state": "candidate", "origin": "evidence", "origin_ref": {},
            "note": None, "group_label": None, "position": None}
    return SimpleNamespace(**{**base, **fields})


# ── 응답 모양(순수 함수) ──────────────────────────────────────────────


class TestReadingPath:
    def test_evidence_path_lists_each_subquestion_with_its_stored_values(self):
        path = reading_path("evidence", REF_C1, SNAPSHOT, PLAN)
        assert path["revived"] is None and path["user"] is False
        assert [(s["idx"], s["subquestion"], s["rank"], s["verdict"], s["first_round"])
                for s in path["subqs"]] == [
            (0, PLAN[0], 1, "sufficient", 1), (1, PLAN[1], 1, "insufficient", None)]
        assert path["subqs"][0]["chunks"] == [
            {"chunk_id": "c1", "page_start": 3, "page_end": 4, "score": 0.91,
             "text": "가" * PATH_CHUNK_CHARS},
            {"chunk_id": "c2", "page_start": 5, "page_end": 5, "score": 0.7, "text": "둘째 대목"},
        ]
        # 같은 대목이라도 점수는 그 하위질문의 매칭 점수다
        assert path["subqs"][1]["chunks"][0]["score"] == 0.5

    def test_br_tags_become_line_breaks_before_the_cut(self):
        # 운영(2026-10-13, 연구 9ba10849… 의 KCI_FI001594560__0055 — 대목 67개 중 6개): 300자째가 '<br>' 안에 떨어져
        # '|Model 3<br><br>B (S.E.)<' 처럼 태그 조각이 끝에 남았다. 화면(frontend/utils/passageText.ts)은 온전한 <br> 만
        # 줄바꿈으로 바꾸므로 조각이 글자로 보인다 — 자르기 전에 같은 규칙으로 바꾼다
        cut_inside = "가" * (PATH_CHUNK_CHARS - 2) + "<br><br>B (S.E.)<br>|"
        assert cut_inside[:PATH_CHUNK_CHARS].endswith("<b")
        assert _path_text(cut_inside) == "가" * (PATH_CHUNK_CHARS - 2) + "\n\n"
        # 운영 끝 글자 그대로 — 원문으로 자르면 'B (S.E.)<' 에서 끝난다
        live_tail = "가" * (PATH_CHUNK_CHARS - 25) + "|Model 3<br><br>B (S.E.)<br>|0.12|"
        assert live_tail[:PATH_CHUNK_CHARS].endswith("|Model 3<br><br>B (S.E.)<")
        assert _path_text(live_tail) == "가" * (PATH_CHUNK_CHARS - 25) + "|Model 3\n\nB (S.E.)\n|0.12|"
        for raw in (cut_inside, live_tail):
            assert "<" not in _path_text(raw)

    def test_br_tags_do_not_use_up_the_character_limit(self):
        # 표가 많은 대목은 태그 글자(<br> 4자)가 상한을 먹어 실제 글이 줄었다 — 줄바꿈 한 글자로 센다
        cells = "<br>".join(["가" * 10] * 40)
        text = _path_text(cells)
        assert text == "\n".join(["가" * 10] * 40)[:PATH_CHUNK_CHARS]
        assert text.count("가") > cells[:PATH_CHUNK_CHARS].count("가")

    def test_same_rule_as_the_screen(self):
        # passageText 와 같은 글자 — <br>·<br/>·<br />·대소문자, 빈 줄 연속(사이 공백·탭 포함)은 빈 줄 하나
        assert _path_text("가<br>나<br/>다<br />라<BR>마<Br/>바<bR  />사") == "가\n나\n다\n라\n마\n바\n사"
        assert _path_text("요한다.<br><br>한편") == "요한다.\n\n한편"
        assert _path_text("표<br><br><br><br><br><br>|") == "표\n\n|"
        assert _path_text("가\n<br> <br>\n나") == "가\n\n나"
        # <br> 가 아닌 태그 꼴과 통계 글의 '<' 는 글자 그대로 — 잘린 끝의 '<' 라도 지우지 않는다
        assert _path_text("<b>굵게</b> <brx> p < .05") == "<b>굵게</b> <brx> p < .05"
        stat = "가" * (PATH_CHUNK_CHARS - 3) + "p <.05"
        assert _path_text(stat) == "가" * (PATH_CHUNK_CHARS - 3) + "p <"

    def test_chunks_missing_from_the_snapshot_are_left_out(self):
        # c9 는 스냅숏에 글이 없다 — 저장된 값만 쓴다
        path = reading_path("evidence", REF_C2, SNAPSHOT, PLAN)
        assert [c["chunk_id"] for c in path["subqs"][0]["chunks"]] == ["c3"]

    def test_no_snapshot_keeps_the_subquestions_without_chunks(self):
        path = reading_path("evidence", REF_C1, None, PLAN)
        assert [s["chunks"] for s in path["subqs"]] == [[], []]

    def test_revived_path(self):
        path = reading_path("revived", {"subq_idx": 1, "round": 1, "note": "영향 연구가 적다"},
                            SNAPSHOT, PLAN)
        assert path == {"subqs": [], "user": False, "revived": {
            "subq_idx": 1, "subquestion": PLAN[1], "round": 1, "note": "영향 연구가 적다"}}

    def test_user_path(self):
        assert reading_path("user", {}, SNAPSHOT, PLAN) == {"subqs": [], "revived": None, "user": True}

    def test_subquestion_outside_the_plan_is_blank(self):
        path = reading_path("revived", {"subq_idx": 7, "round": None, "note": None}, None, PLAN)
        assert path["revived"] == {"subq_idx": 7, "subquestion": "", "round": None, "note": ""}


class TestReadingItemAndOrder:
    def test_item_shape(self):
        row = _row("C2", state="in", origin_ref=REF_C2, note="메모", group_label="가정", position=3)
        meta = book_meta("C2", None)
        assert reading_item(row, meta, SNAPSHOT, PLAN) == {
            "cnts_id": "C2", "state": "in", "origin": "evidence", "note": "메모",
            "group_label": "가정", "position": 3, "meta": meta,
            "path": reading_path("evidence", REF_C2, SNAPSHOT, PLAN),
        }

    def test_book_meta_falls_back_to_the_id(self):
        assert book_meta("Z9", None) == {"title": "Z9", "personal_author": None, "pub_date": None,
                                         "series_title": None}
        book = SimpleNamespace(title="독서 격차 연구", personal_author="김철수", pub_date="2019",
                               series_title="교육학연구")
        assert book_meta("C1", book) == {"title": "독서 격차 연구", "personal_author": "김철수",
                                         "pub_date": "2019", "series_title": "교육학연구"}

    def test_order_is_position_then_best_rank_then_id(self):
        rows = [_row("C5"), _row("C4", origin_ref={"rank": {"1": 2}}),
                _row("C3", origin_ref={"rank": {"0": 4, "1": 1}}), _row("C2", position=1),
                _row("C1", position=0), _row("R1", origin="revived", origin_ref={"subq_idx": 0})]
        assert [r.cnts_id for r in reading_order(rows)] == ["C1", "C2", "C3", "C4", "C5", "R1"]

    def test_same_best_rank_goes_to_the_higher_chunk_score_then_id(self):
        # 같은 순위면 들어온 경로의 대목 점수(chunk_scores, 하위질문 전부) 중 가장 높은 값이 큰 편이 먼저다(사용자 결정
        # 2026-10-14 — id 가 작은 옛 논문이 먼저 오던 것). 점수가 없는 편은 점수 있는 편 뒤, 그래도 같으면 cnts_id.
        # 사용자가 정한 순서(position)는 그대로 맨 앞이다
        rows = [_row("C1", origin_ref={"rank": {"0": 1}, "chunk_scores": {"0": {"a": 0.4}}}),
                _row("C2", origin_ref={"rank": {"1": 1}, "chunk_scores": {"1": {"b": 0.9, "c": 0.3}}}),
                _row("C3", origin_ref={"rank": {"0": 2, "1": 1}, "chunk_scores": {"0": {"d": 0.95}, "1": {"e": 0.5}}}),
                _row("C4", origin_ref={"rank": {"2": 1}}),
                _row("C0", origin_ref={"rank": {"2": 1}, "chunk_scores": {"2": {}}}),
                _row("C9", origin_ref={"rank": {"2": 1}, "chunk_scores": {"2": {"f": None, "g": True}}}),
                _row("C5", position=0, origin_ref={"rank": {"0": 9}, "chunk_scores": {"0": {"h": 0.1}}}),
                _row("C6", origin_ref={"rank": {"0": 2}, "chunk_scores": {"0": {"i": 0.99}}})]
        assert [r.cnts_id for r in reading_order(rows)] == ["C5", "C3", "C2", "C1", "C0", "C4", "C9", "C6"]

    def test_subquestions_are_the_plan_strings(self):
        assert subquestions_of(_job_ns(plan=[PLAN[0], 3, None, PLAN[1]])) == PLAN
        assert subquestions_of(_job_ns(plan=None)) == []


class TestFunnel:
    def test_counts(self):
        rows = [_row("C1", state="in"), _row("C2", state="candidate"), _row("C3", state="out")]
        assert funnel(REPORT, rows) == {"reviewed": 121, "adopted": 48, "candidates": 2, "picked": 1}

    def test_missing_stats_are_none(self):
        assert funnel({}, []) == {"reviewed": None, "adopted": None, "candidates": 0, "picked": 0}
        assert funnel({"stats": {"papers_reviewed": True}}, [])["reviewed"] is None


def _candidate(cnts_id: str, ranks: dict[str, int], scores: dict[str, dict[str, float]] | None = None) -> dict:
    """candidates_from_snapshot 한 편의 모양 — 순위(와 대목 점수)만 다르게."""
    return {"cnts_id": cnts_id, "origin": "evidence",
            "origin_ref": {"subq_idx": [int(k) for k in ranks], "rank": dict(ranks), "chunks": {},
                           "chunk_scores": dict(scores or {}), "verdict": {}}}


class TestPreselect:
    """이어가기 때 채택 근거 상위 READING_PRESELECT 편을 미리 담는다(사용자 결정 2026-10-13)."""

    def test_the_constant(self):
        # 미리 담은 수만으로 [보고서 만들기](담음 MIN_READING_FOR_OUTLINE 편 이상)를 누를 수 있다
        assert READING_PRESELECT == 8
        assert READING_PRESELECT >= MIN_READING_FOR_OUTLINE

    def test_top_eight_in_reading_order_are_picked_and_the_rest_stay_candidates(self):
        # 하위질문 셋에서 들어온 열 편 — 읽기 목록 순서(하위질문 안 가장 앞선 순위 → cnts_id)로 앞 여덟 편이 담음
        candidates = [
            _candidate("P01", {"0": 1}), _candidate("P02", {"0": 2}), _candidate("P03", {"0": 3}),
            _candidate("P04", {"0": 4}), _candidate("P05", {"1": 1}), _candidate("P06", {"1": 2, "0": 5}),
            _candidate("P07", {"1": 3}), _candidate("P08", {"2": 1}), _candidate("P09", {"2": 2}),
            _candidate("P10", {"2": 3}),
        ]
        rows = preselect(candidates)

        # 넣는 순서는 candidates 그대로, 모양은 candidates_from_snapshot + state
        assert [r["cnts_id"] for r in rows] == [c["cnts_id"] for c in candidates]
        picked = {r["cnts_id"] for r in rows if r["state"] == "in"}
        # 순위 1: P01·P05·P08, 순위 2: P02·P06·P09, 순위 3: P03·P07 (P10 은 순위 3 의 셋째, P04 는 순위 4)
        assert picked == {"P01", "P05", "P08", "P02", "P06", "P09", "P03", "P07"}
        assert {r["cnts_id"]: r["state"] for r in rows if r["cnts_id"] not in picked} == {
            "P04": "candidate", "P10": "candidate"}
        # 같은 순서를 읽기 목록(reading_order)이 그대로 보인다 — 미리 담은 여덟 편이 표의 맨 위 여덟 줄이다
        shown = reading_order([_row(r["cnts_id"], state=r["state"], origin_ref=r["origin_ref"]) for r in rows])
        assert [r.state for r in shown] == ["in"] * READING_PRESELECT + ["candidate"] * 2

    def test_a_tie_at_the_cut_goes_to_the_higher_chunk_score_not_the_older_id(self):
        # 순위 1·2 가 여섯 편, 순위 3 이 네 편 — 남은 두 칸은 순위 3 중 대목 점수가 높은 P10·P09 (옛 키는 id 가 작은
        # P07·P08 을 담았다). 점수가 없는 편(P11)은 점수 있는 편 뒤
        candidates = [
            _candidate("P01", {"0": 1}, {"0": {"a": 0.5}}), _candidate("P02", {"1": 1}), _candidate("P03", {"2": 1}),
            _candidate("P04", {"0": 2}), _candidate("P05", {"1": 2}), _candidate("P06", {"2": 2}),
            _candidate("P07", {"0": 3}, {"0": {"b": 0.41}}), _candidate("P08", {"1": 3}, {"1": {"c": 0.42}}),
            _candidate("P09", {"2": 3}, {"2": {"d": 0.3, "e": 0.8}}), _candidate("P10", {"0": 3, "1": 4},
                                                                                   {"0": {"f": 0.2}, "1": {"g": 0.9}}),
            _candidate("P11", {"3": 3}),
        ]
        rows = preselect(candidates)

        picked = {r["cnts_id"] for r in rows if r["state"] == "in"}
        assert picked == {"P01", "P02", "P03", "P04", "P05", "P06", "P09", "P10"}
        # 표(reading_order)도 같은 키다 — 미리 담은 여덟 편이 맨 위 여덟 줄, 순위 3 은 점수 높은 순
        shown = reading_order([_row(r["cnts_id"], state=r["state"], origin_ref=r["origin_ref"]) for r in rows])
        assert [r.state for r in shown] == ["in"] * READING_PRESELECT + ["candidate"] * 3
        assert [r.cnts_id for r in shown][6:] == ["P10", "P09", "P08", "P07", "P11"]

    def test_preselected_rows_carry_a_mark_in_the_path_and_the_input_is_untouched(self):
        candidates = [_candidate(f"P{n}", {"0": n}) for n in range(1, 11)]
        before = json.loads(json.dumps(candidates))
        rows = preselect(candidates)

        assert candidates == before
        for row, cand in zip(rows, candidates):
            if row["state"] == "in":
                assert row["origin_ref"] == {**cand["origin_ref"], "preselected": True}
            else:
                assert row["origin_ref"] == cand["origin_ref"]
            assert (row["origin"], row["cnts_id"]) == (cand["origin"], cand["cnts_id"])

    def test_fewer_than_eight_are_all_picked(self):
        rows = preselect([_candidate("A", {"0": 2}), _candidate("B", {"0": 1}), _candidate("C", {})])
        assert [(r["cnts_id"], r["state"]) for r in rows] == [("A", "in"), ("B", "in"), ("C", "in")]
        assert preselect([]) == []

    def test_papers_without_a_rank_come_after_ranked_ones(self):
        # 어느 하위질문에도 남지 않은 근거(경로 없이 뒤에 둔 옛 스냅샷) — 순위가 있는 논문이 먼저 담긴다
        candidates = [_candidate(f"N{n}", {}) for n in range(3)] + [_candidate(f"R{n}", {"0": n}) for n in range(1, 8)]
        picked = [r["cnts_id"] for r in preselect(candidates) if r["state"] == "in"]
        assert sorted(picked) == ["N0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"]

    def test_limit(self):
        rows = preselect([_candidate(f"P{n}", {"0": n}) for n in range(1, 4)], limit=1)
        assert [r["state"] for r in rows] == ["in", "candidate", "candidate"]


class TestExcludedCandidates:
    def test_round_and_note_come_from_the_snapshot_rounds(self):
        assert excluded_candidates(_job_ns(), []) == [
            {**X1, "subq_idx": 0, "subquestion": PLAN[0], "round": 1, "note": "가정 요인이 부족하다"},
            {**X2, "subq_idx": 1, "subquestion": PLAN[1], "round": 1, "note": "영향 연구가 적다"},
        ]

    def test_papers_that_already_have_a_row_are_left_out(self):
        assert [c["cnts_id"] for c in excluded_candidates(_job_ns(), [_row("X1", origin="revived")])] == [
            "X2"]

    def test_old_job_without_round_records(self):
        snap = {**SNAPSHOT, "subquestions": [{**sq, "rounds": []} for sq in SNAPSHOT["subquestions"]]}
        out = excluded_candidates(_job_ns(state_snapshot=snap), [])
        assert [(c["cnts_id"], c["round"], c["note"]) for c in out] == [("X1", None, ""), ("X2", None, "")]


class TestReadingView:
    def test_shape(self):
        work = SimpleNamespace(topic_id=12)
        rows = [_row("C2", origin_ref=REF_C2), _row("C1", state="in", origin_ref=REF_C1)]
        books = {"C1": SimpleNamespace(title="독서 격차 연구", personal_author="김철수", pub_date="2019",
                                       series_title=None)}
        view = reading_view(work, _job_ns(), rows, books)
        assert view["topic_id"] == 12 and view["stale"] is False and view["subquestions"] == PLAN
        assert view["funnel"] == {"reviewed": 121, "adopted": 48, "candidates": 2, "picked": 1}
        assert [(i["cnts_id"], i["meta"]["title"]) for i in view["items"]] == [
            ("C1", "독서 격차 연구"), ("C2", "C2")]
        assert [c["cnts_id"] for c in view["excluded"]] == ["X1", "X2"]
        assert json.loads(json.dumps(view)) == view

    def test_preselected_counts_rows_picked_at_continue_whatever_their_state_now(self):
        # 읽기 목록 머리 안내('채택 근거 상위 N편을 미리 담았습니다')의 N — 뺀(out) 행도 미리 담았던 것이다.
        # 이 안내 전에 이어간 연구·되살림·직접 담음 행에는 표시가 없다
        work = SimpleNamespace(topic_id=None)
        rows = [_row("C1", state="in", origin_ref={**REF_C1, "preselected": True}),
                _row("C2", state="out", origin_ref={**REF_C2, "preselected": True}),
                _row("C3", state="in", origin_ref={"rank": {"0": 3}}),
                _row("R1", state="in", origin="revived", origin_ref={"subq_idx": 0})]
        assert reading_view(work, _job_ns(), rows, {})["preselected"] == 2
        assert reading_view(work, _job_ns(), rows[2:], {})["preselected"] == 0

    def test_no_outline_or_the_same_topic_is_not_stale(self):
        work = SimpleNamespace(topic_id=2)
        # 목차가 없으면(계획서 행이 없거나 목차가 비었으면) 배지도 없다
        assert reading_view(work, _job_ns(), [], {})["stale"] is False
        assert reading_view(work, _job_ns(), [], {}, {})["stale"] is False
        # 목차를 만든 주제를 그대로 고른 채면 거짓 — 참이 되는 경우는 API 테스트가 본다
        assert reading_view(work, _job_ns(), [], {}, {"topic": {"id": 2}})["stale"] is False


# ── API ─────────────────────────────────────────────────────────────


def _stub_missing(monkeypatch, name: str, module) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module)


_CACHED = ("api.research_reading", "api.research_work", "services.research.relay")


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """test_research_work_api.py 와 같은 방식 — 더미 redis 에 묶인 relay 가 다른 테스트로 새지 않게."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


class _Api:
    def __init__(self, client, engine, router, events):
        self.client = client
        self.engine = engine
        self.router = router
        self.events = events


@pytest.fixture
def api(monkeypatch):
    for name in ("redis", "redis.asyncio"):
        _stub_missing(monkeypatch, name, MagicMock())
    _forget_on_teardown(monkeypatch, _CACHED)
    router = importlib.import_module("api.research_reading")
    from core.deps import get_db

    events: list[tuple] = []

    async def _publish_work(work_id, kind, payload):
        events.append((str(work_id), kind, payload))

    monkeypatch.setattr(router, "publish_work", _publish_work)
    engine = make_engine()

    async def _db():
        db = AsyncSessionOverSync(engine)
        try:
            yield db
        finally:
            await db.rollback()
            await db.close()

    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[get_db] = _db
    return _Api(TestClient(app), engine, router, events)


def _work_job(engine, *, continued: bool = True, **work) -> uuid.UUID:
    jid = add_research_job(engine, status="completed", stage="synthesized")
    with engine.begin() as conn:
        conn.execute(sa.update(ResearchJob.__table__).where(ResearchJob.__table__.c.id == jid).values(
            question="청소년 독서 격차", plan=PLAN, state_snapshot=SNAPSHOT, report=REPORT,
        ))
    if continued:
        add_work(engine, jid, phase="reading", **work)
        add_reading(engine, jid, "C1", origin_ref=REF_C1)
        add_reading(engine, jid, "C2", origin_ref=REF_C2)
    return jid


def _reading(engine, jid) -> dict:
    table = ResearchReading.__table__
    with engine.connect() as conn:
        rows = conn.execute(sa.select(table).where(table.c.work_id == jid)).mappings().all()
    return {r["cnts_id"]: dict(r) for r in rows}


def _progress(engine, jid) -> dict:
    table = ResearchWork.__table__
    with engine.connect() as conn:
        return conn.execute(sa.select(table.c.progress).where(table.c.id == jid)).scalar_one()


class TestGetReading:
    def test_items_meta_funnel_and_excluded(self, api):
        jid = _work_job(api.engine)
        add_book(api.engine, "C1", title="독서 격차 연구", personal_author="김철수", pub_date="2019",
                 series_title="교육학연구")

        res = api.client.get(f"/api/research/{jid}/reading")

        assert res.status_code == 200
        body = res.json()
        assert body["topic_id"] is None and body["stale"] is False and body["subquestions"] == PLAN
        assert body["funnel"] == {"reviewed": 121, "adopted": 48, "candidates": 2, "picked": 0}
        assert [(i["cnts_id"], i["origin"], i["meta"]) for i in body["items"]] == [
            ("C1", "evidence", {"title": "독서 격차 연구", "personal_author": "김철수",
                                "pub_date": "2019", "series_title": "교육학연구"}),
            ("C2", "evidence", {"title": "C2", "personal_author": None, "pub_date": None,
                                "series_title": None}),
        ]
        assert body["items"][0]["path"]["subqs"][0]["chunks"][0]["text"] == "가" * PATH_CHUNK_CHARS
        assert [c["cnts_id"] for c in body["excluded"]] == ["X1", "X2"]

    def test_picking_another_topic_after_the_outline_marks_the_list_stale(self, api):
        # 목차를 만든 뒤 주제 화면에서 다른 카드를 골랐다 — 계획서뿐 아니라 읽기 목록에도 '다시 맞춤 필요'(spec §5-2)
        jid = _work_job(api.engine)
        card = {"title": "첫 주제", "question": "가는 나인가?"}
        first = add_topic(api.engine, jid, slot=1, card=card)
        second = add_topic(api.engine, jid, slot=2, card={"title": "둘째 주제", "question": "다는 라인가?"},
                           state="picked")
        add_proposal(api.engine, jid, outline={"topic": {"id": first, **card}, "groups": []})
        table = ResearchWork.__table__
        with api.engine.begin() as conn:
            conn.execute(sa.update(table).where(table.c.id == jid).values(topic_id=second))

        body = api.client.get(f"/api/research/{jid}/reading").json()

        assert body["topic_id"] == second and body["stale"] is True

    def test_404_until_continued(self, api):
        jid = _work_job(api.engine, continued=False)
        assert api.client.get(f"/api/research/{jid}/reading").status_code == 404

    def test_bad_id_is_422(self, api):
        assert api.client.get("/api/research/not-a-uuid/reading").status_code == 422


class TestPutReading:
    def test_picking_a_candidate(self, api):
        jid = _work_job(api.engine)

        res = api.client.put(f"/api/research/{jid}/reading/C1", json={"state": "in"})

        assert res.status_code == 200
        assert res.json()["state"] == "in" and res.json()["cnts_id"] == "C1"
        assert _reading(api.engine, jid)["C1"]["state"] == "in"
        assert _progress(api.engine, jid)["reading"] == 1
        (event,) = api.events
        assert event[:2] == (str(jid), "work")
        assert event[2]["phase"] == "reading" and event[2]["progress"]["reading"] == 1

    def test_only_the_sent_fields_change(self, api):
        jid = _work_job(api.engine)
        api.client.put(f"/api/research/{jid}/reading/C1",
                       json={"state": "in", "note": "핵심", "group_label": "가정", "position": 2})

        res = api.client.put(f"/api/research/{jid}/reading/C1", json={"note": "  다시 읽기  "})

        row = _reading(api.engine, jid)["C1"]
        assert (row["state"], row["note"], row["group_label"], row["position"]) == (
            "in", "다시 읽기", "가정", 2)
        assert res.json()["note"] == "다시 읽기"

    def test_null_or_blank_clears_note_and_group(self, api):
        jid = _work_job(api.engine)
        api.client.put(f"/api/research/{jid}/reading/C1", json={"note": "메모", "group_label": "가정"})

        api.client.put(f"/api/research/{jid}/reading/C1", json={"note": None, "group_label": "   "})

        row = _reading(api.engine, jid)["C1"]
        assert (row["note"], row["group_label"]) == (None, None)

    def test_reviving_a_paper_the_critic_dropped(self, api):
        jid = _work_job(api.engine)

        res = api.client.put(f"/api/research/{jid}/reading/X2", json={})

        assert res.status_code == 200
        row = _reading(api.engine, jid)["X2"]
        assert (row["state"], row["origin"]) == ("candidate", "revived")
        assert row["origin_ref"] == {"subq_idx": 1, "round": 1, "note": "영향 연구가 적다"}
        assert res.json()["path"]["revived"] == {"subq_idx": 1, "subquestion": PLAN[1], "round": 1,
                                                 "note": "영향 연구가 적다"}
        assert [c["cnts_id"] for c in api.client.get(f"/api/research/{jid}/reading").json()["excluded"]] == [
            "X1"]

    def test_new_row_takes_the_sent_state(self, api):
        jid = _work_job(api.engine)
        api.client.put(f"/api/research/{jid}/reading/X1", json={"state": "in"})
        assert _reading(api.engine, jid)["X1"]["state"] == "in"
        assert _progress(api.engine, jid)["reading"] == 1

    def test_adding_a_catalog_paper(self, api):
        # 06d 빠른검색 [담기] — 잡과 상관없는 논문도 소장 목록에 있으면 담는다
        jid = _work_job(api.engine)
        add_book(api.engine, "U1", title="빠른검색에서 담은 논문")

        res = api.client.put(f"/api/research/{jid}/reading/U1", json={"state": "in"})

        assert res.status_code == 200
        row = _reading(api.engine, jid)["U1"]
        assert (row["origin"], row["origin_ref"], row["state"]) == ("user", {}, "in")
        assert res.json()["meta"]["title"] == "빠른검색에서 담은 논문"
        assert res.json()["path"] == {"subqs": [], "revived": None, "user": True}

    def test_unknown_paper_is_404(self, api):
        jid = _work_job(api.engine)

        res = api.client.put(f"/api/research/{jid}/reading/NOPE", json={"state": "in"})

        assert res.status_code == 404 and res.json()["detail"] == api.router.NO_PAPER
        assert "NOPE" not in _reading(api.engine, jid) and api.events == []

    def test_nothing_sent_to_an_existing_row_writes_nothing(self, api):
        jid = _work_job(api.engine)
        res = api.client.put(f"/api/research/{jid}/reading/C1", json={})
        assert res.status_code == 200 and res.json()["state"] == "candidate"
        assert api.events == []

    @pytest.mark.parametrize("body", [
        {"state": "maybe"}, {"state": None}, {"note": "가" * 1001}, {"group_label": "가" * 61},
        {"position": -1},
    ])
    def test_invalid_body_is_422(self, api, body):
        jid = _work_job(api.engine)
        assert api.client.put(f"/api/research/{jid}/reading/C1", json=body).status_code == 422
        assert _reading(api.engine, jid)["C1"]["state"] == "candidate"

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        assert api.client.put(f"/api/research/{jid}/reading/C1", json={"state": "in"}).status_code == 409

    def test_404_until_continued(self, api):
        jid = _work_job(api.engine, continued=False)
        assert api.client.put(f"/api/research/{jid}/reading/C1", json={"state": "in"}).status_code == 404


class TestPreselectedReading:
    """이어가기가 미리 담은 행(preselect — 채택 근거 상위 READING_PRESELECT 편)이 읽기 목록 API 에서 그대로 보이고,
    빼기·되살리기는 전과 같다."""

    def _continued(self, engine) -> uuid.UUID:
        jid = _work_job(engine, continued=False)
        add_work(engine, jid, phase="reading")
        candidates = [_candidate(f"P{n:02d}", {"0": n}) for n in range(1, 11)]
        for row in preselect(candidates):
            add_reading(engine, jid, row["cnts_id"], state=row["state"], origin=row["origin"],
                        origin_ref=row["origin_ref"])
        return jid

    def test_funnel_and_the_report_button_condition(self, api):
        jid = self._continued(api.engine)

        body = api.client.get(f"/api/research/{jid}/reading").json()

        assert body["funnel"] == {"reviewed": 121, "adopted": 48, "candidates": 10, "picked": READING_PRESELECT}
        assert body["funnel"]["picked"] >= MIN_READING_FOR_OUTLINE
        assert body["preselected"] == READING_PRESELECT
        # 표 맨 위 여덟 줄이 담음이다
        assert [i["state"] for i in body["items"]] == ["in"] * 8 + ["candidate"] * 2
        assert [i["cnts_id"] for i in body["items"][:8]] == [f"P{n:02d}" for n in range(1, 9)]

    def test_taking_one_out_and_reviving_work_as_before(self, api):
        jid = self._continued(api.engine)

        out = api.client.put(f"/api/research/{jid}/reading/P01", json={"state": "out"})
        revived = api.client.put(f"/api/research/{jid}/reading/X2", json={})

        assert out.status_code == 200 and out.json()["state"] == "out"
        assert revived.status_code == 200 and revived.json()["origin"] == "revived"
        rows = _reading(api.engine, jid)
        assert rows["P01"]["state"] == "out" and rows["P01"]["origin_ref"]["preselected"] is True
        assert (rows["X2"]["state"], rows["X2"]["origin_ref"]) == (
            "candidate", {"subq_idx": 1, "round": 1, "note": "영향 연구가 적다"})
        assert _progress(api.engine, jid)["reading"] == READING_PRESELECT - 1
        body = api.client.get(f"/api/research/{jid}/reading").json()
        # 후보 = 뺌이 아닌 행(미리 담은 일곱 + 남은 후보 둘 + 되살린 하나), 미리 담은 수는 뺀 행도 센다
        assert body["funnel"]["candidates"] == 10 and body["funnel"]["picked"] == READING_PRESELECT - 1
        assert body["preselected"] == READING_PRESELECT


class TestAppWiring:
    def test_main_includes_the_reading_router_after_the_topics_router(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
        imported = {
            (node.module, alias.name, alias.asname)
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        included = [
            node.args[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "include_router"
        ]
        assert ("api.research_reading", "router", "research_reading_router") in imported
        assert included.index("research_topics_router") < included.index("research_reading_router")
