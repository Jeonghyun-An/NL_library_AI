"""scripts/research_eval/ — critic 기준 스위치 두 갈래 판정 도구(질문 목록·두 갈래 실행·라벨 파일·채점·예시 지정).

스크립트는 HTTP(httpx)만 쓰거나(run_pair·make_labels·score) DB 세션을 함수 안에서 import 한다(mark_example).
HTTP 는 httpx.MockTransport 로, DB 는 db.postgres 대역으로 바꿔 운영에 닿지 않는다.
"""
import csv
import json
import re
import sys
import types
from pathlib import Path

import httpx
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "research_eval"
sys.path.insert(0, str(SCRIPTS_DIR))

API = "http://api.test/api"
WORK = "3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e"


def _report(sections, excluded_by_subq, evidence=None):
    """보고서(synthesizer.assemble_report) 가운데 도구가 읽는 키만."""
    return {
        "question": "컴퓨팅 자원에 대한 연구가 궁금해",
        "sections": [
            {"heading": f"하위질문 {i + 1}", "papers": [{"cnts_id": c} for c in ids]}
            for i, ids in enumerate(sections)
        ],
        "evidence": evidence or {},
        "trail": [
            {"subquestion": f"하위질문 {i + 1}", "excluded_papers": [
                {"cnts_id": c, "title": f"제외 {c}", "personal_author": "홍길동", "pub_date": "2010"}
                for c in ids
            ]}
            for i, ids in enumerate(excluded_by_subq)
        ],
    }


def _write_labels(path: Path, rows: list[tuple[str, str]]) -> None:
    body = "".join(f"{cnts},제목 {cnts},저자,{label}\n" for cnts, label in rows)
    path.write_text("cnts_id,title,authors,label\n" + body, encoding="utf-8-sig")


def _questions(tmp_path: Path, *keys: str) -> Path:
    path = tmp_path / "questions.json"
    path.write_text(json.dumps([{"key": k, "question": f"{k} 질문"} for k in keys], ensure_ascii=False),
                    encoding="utf-8")
    return path


# ── questions.json ──────────────────────────────────────────────────────


def test_questions_file_lists_five_fixed_questions():
    items = json.loads((SCRIPTS_DIR / "questions.json").read_text(encoding="utf-8"))
    keys = [q["key"] for q in items]
    assert len(items) == 5 and len(set(keys)) == 5
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", k) for k in keys)    # 라벨 파일 이름이 된다
    assert all(set(q) == {"key", "question"} and 2 <= len(q["question"]) <= 500 for q in items)
    # 운영 잡 2a56f8b6 의 질문 — 옛 잡과 견주지 않고 같은 질문을 두 갈래로 다시 돌린다(spec §8)
    assert items[0] == {"key": "computing", "question": "컴퓨팅 자원에 대한 연구가 궁금해"}


# ── score.py ────────────────────────────────────────────────────────────


def test_section_irrelevant_counts_irrelevant_labels_per_section():
    from score import section_irrelevant

    report = _report([["A", "B", "C"], ["D", "E"], []], [])
    labels = {"A": "무관", "B": "관련", "C": "무관", "D": "관련"}     # E 는 라벨 없음 — 세지 않는다
    assert section_irrelevant(report, labels) == [2, 0, 0]


def test_over_exclusion_is_relevant_share_of_distinct_labeled_exclusions():
    from score import over_exclusion

    # X 는 두 하위질문이 함께 뺐다 — 서로 다른 논문으로 한 번만 센다. Z 는 라벨이 없어 분모에서 빠진다
    report = _report([], [["X", "Y"], ["X", "Z"], ["W"]])
    labels = {"X": "관련", "Y": "무관", "W": "무관"}
    assert over_exclusion(report, labels) == pytest.approx(1 / 3)


def test_over_exclusion_is_none_without_labeled_exclusions():
    from score import over_exclusion

    assert over_exclusion(_report([["A"]], []), {"A": "관련"}) is None    # 제외 0편
    assert over_exclusion(_report([], [["Z"]]), {}) is None                # 제외는 있으나 라벨 없음


@pytest.mark.parametrize("irrelevant, over, ok", [
    ([1, 1, 0], 0.10, True),     # 경계값은 합격 — '이하'
    ([0], None, True),           # 라벨 단 제외 논문이 없으면 ② 는 통과
    ([2, 0], 0.0, False),        # 한 절에 무관 2편
    ([0, 1], 0.11, False),       # 과잉 제외 11%
    ([], 0.0, True),
])
def test_passes_uses_the_d11_thresholds(irrelevant, over, ok):
    from score import passes

    assert passes({"section_irrelevant": irrelevant, "over_exclusion": over}) is ok


def test_load_labels_reads_excel_csv_and_rejects_unknown_labels(tmp_path):
    from score import load_labels

    path = tmp_path / "computing.csv"
    path.write_text("cnts_id,title,authors,label\nA,가,홍,관련\nB,나,김, 무관 \nC,다,이,\n",
                    encoding="utf-8-sig")
    assert load_labels(path) == {"A": "관련", "B": "무관"}     # 빈 칸은 라벨 없음

    path.write_text("cnts_id,title,authors,label\nA,가,홍,관련있음\n", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="2행"):
        load_labels(path)


def test_score_prints_both_arms_on_a_cp949_console(tmp_path, capsys):
    from score import main

    reports = {"job-1": _report([["A", "B"]], [["X"]]), "job-2": _report([["A"]], [])}

    def handler(request: httpx.Request) -> httpx.Response:
        jid = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, json={"job_id": jid, "status": "completed", "report": reports[jid]})

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"}}), encoding="utf-8")
    labels = tmp_path / "labels"
    labels.mkdir()
    _write_labels(labels / "computing.csv", [("A", "관련"), ("B", "무관"), ("X", "관련")])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--labels-dir", str(labels),
                   "--questions", str(_questions(tmp_path, "computing"))], client=client)

    assert rc == 0
    out = capsys.readouterr().out
    out.encode("cp949")
    # 갈래 0: 절 무관 1(B) 은 통과지만 뺀 X 가 '관련' — 과잉 제외 100% 로 불합격. 갈래 1: 무관 0·제외 없음
    assert "갈래 0  절별 무관 1  과잉 제외 100.0%" in out and "불합격" in out
    assert "합격 질문: 갈래 0 0/1 · 갈래 1 1/1" in out


def test_score_counts_every_question_and_holds_arms_with_blank_labels(tmp_path, capsys):
    """D11 은 다섯 질문 모두 합격이어야 한다 — 채점하지 못한 질문도 분모에 넣고, 라벨 칸이 빈 갈래는 합격으로 세지 않는다."""
    from score import main

    reports = {"job-1": _report([["A", "B"], ["C"]], []), "job-2": _report([["A", "D"]], [])}

    def handler(request: httpx.Request) -> httpx.Response:
        jid = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, json={"job_id": jid, "status": "completed", "report": reports[jid]})

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"},
                                 "library": {"0": "job-3", "1": "job-4"}}), encoding="utf-8")
    labels = tmp_path / "labels"
    labels.mkdir()
    # library 는 라벨 파일이 없다. computing 의 D 는 라벨 칸이 비었다
    _write_labels(labels / "computing.csv", [("A", "무관"), ("B", "무관"), ("C", "관련"), ("D", "")])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--labels-dir", str(labels),
                   "--questions", str(_questions(tmp_path, "computing", "library"))], client=client)

    assert rc == 0
    out = capsys.readouterr().out
    out.encode("cp949")
    # 갈래 0 은 한 절에 무관 2편 — 라벨을 더 달아도 줄지 않으니 불합격. 갈래 1 은 D 의 라벨이 비어 판정 보류
    assert "갈래 0  절별 무관 2,0" in out and "라벨 없음 0편  -> 불합격" in out
    assert "갈래 1  절별 무관 1" in out and "라벨 없음 1편  -> 판정 보류" in out
    assert "합격 질문: 갈래 0 0/2 · 갈래 1 0/2" in out
    assert "채점하지 못한 질문 1개: library" in out
    assert "라벨 칸이 빈 논문이 갈래 합계 1편" in out


def test_score_denominator_is_the_fixed_question_list(tmp_path, capsys):
    """run_pair 가 한 질문을 실패해 pairs 에 넷만 남아도 분모는 고정 질문 5개다 — 빠진 질문은 채점하지 못한 질문."""
    from score import main

    keys = [q["key"] for q in json.loads((SCRIPTS_DIR / "questions.json").read_text(encoding="utf-8"))]
    report = _report([["A"]], [])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"job_id": "j", "status": "completed", "report": report})

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({k: {"0": f"{k}-0", "1": f"{k}-1"} for k in keys[:4]} | {
        "extra": {"0": "x-0", "1": "x-1"}}), encoding="utf-8")
    labels = tmp_path / "labels"
    labels.mkdir()
    for k in keys[:4]:
        _write_labels(labels / f"{k}.csv", [("A", "관련")])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--labels-dir", str(labels)], client=client)

    assert rc == 0
    out = capsys.readouterr().out
    out.encode("cp949")
    assert "합격 질문: 갈래 0 4/5 · 갈래 1 4/5" in out
    assert f"채점하지 못한 질문 1개: {keys[4]}" in out
    assert f"run_pair.py --only {keys[4]}" in out
    assert "[extra] 질문 목록(questions.json)에 없는 키 - 채점하지 않는다" in out


def test_score_skips_a_question_whose_job_cannot_be_read(tmp_path, capsys):
    from score import main

    def handler(request: httpx.Request) -> httpx.Response:
        if "job-3" in request.url.path:
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(200, json={"job_id": "j", "status": "completed", "report": _report([["A"]], [])})

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"},
                                 "library": {"0": "job-3", "1": "job-4"}}), encoding="utf-8")
    labels = tmp_path / "labels"
    labels.mkdir()
    for k in ("computing", "library"):
        _write_labels(labels / f"{k}.csv", [("A", "관련")])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--labels-dir", str(labels),
                   "--questions", str(_questions(tmp_path, "computing", "library"))], client=client)

    assert rc == 0
    out = capsys.readouterr().out
    assert "[library] 잡을 읽지 못했다(HTTPStatusError" in out
    assert "합격 질문: 갈래 0 1/2 · 갈래 1 1/2" in out and "채점하지 못한 질문 1개: library" in out


def test_report_precision_counts_distinct_section_papers_and_skips_blank_labels():
    """06a 완료노트 §5-5 의 손 계산과 같은 셈 — 보고서 절에 실린 서로 다른 논문의 관련·무관(라벨 빈 칸은 뺀다)."""
    from score import format_precision, precision, report_precision

    # A 는 두 절에 실렸다 — 한 번만 센다. E 는 라벨이 없어 분모에서 빠진다. 제외 논문 X 는 보고서에 없어 세지 않는다
    report = _report([["A", "B", "C"], ["A", "D", "E"]], [["X"]])
    labels = {"A": "관련", "B": "무관", "C": "관련", "D": "관련", "X": "관련"}

    counts = report_precision(report, labels)

    assert counts == {"relevant": 3, "irrelevant": 1, "unlabeled": 1}
    assert precision(3, 1) == pytest.approx(0.75) and precision(0, 0) is None
    assert format_precision("1", counts) == "  갈래 1  보고서 정밀도 75.0% (관련 3 · 무관 1, 라벨 없음 1편)"
    assert format_precision("0", {"relevant": 0, "irrelevant": 0, "unlabeled": 2}) == (
        "  갈래 0  보고서 정밀도 - (관련 0 · 무관 0, 라벨 없음 2편)")


def test_score_prints_report_precision_per_arm_and_totals_without_changing_the_verdict(tmp_path, capsys):
    """D18 재판정은 06a(보고서 정밀도 63%·56%)와 견준다 — 갈래마다 정밀도 줄과 질문 합계 줄을 찍는다.
    합격 판정(절마다 무관 1편 이하·과잉 제외 10% 이하)은 그대로다."""
    from score import main

    reports = {
        "job-1": _report([["A", "B"], ["C"]], [["X"]]), "job-2": _report([["A", "B", "D"]], []),
        "job-3": _report([["P"]], []), "job-4": _report([["P", "Q"]], [["R"]]),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        jid = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, json={"job_id": jid, "status": "completed", "report": reports[jid]})

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"},
                                 "library": {"0": "job-3", "1": "job-4"}}), encoding="utf-8")
    labels = tmp_path / "labels"
    labels.mkdir()
    _write_labels(labels / "computing.csv", [("A", "관련"), ("B", "무관"), ("C", "관련"), ("D", "무관"), ("X", "관련")])
    _write_labels(labels / "library.csv", [("P", "관련"), ("Q", "무관"), ("R", "무관")])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--labels-dir", str(labels),
                   "--questions", str(_questions(tmp_path, "computing", "library"))], client=client)

    assert rc == 0
    out = capsys.readouterr().out
    out.encode("cp949")
    assert "갈래 0  보고서 정밀도 66.7% (관련 2 · 무관 1, 라벨 없음 0편)" in out
    assert "갈래 1  보고서 정밀도 33.3% (관련 1 · 무관 2, 라벨 없음 0편)" in out
    assert ("보고서 정밀도 합계(채점한 2개 질문): 갈래 0 75.0% (관련 3 · 무관 1, 라벨 없음 0편)"
            " · 갈래 1 40.0% (관련 2 · 무관 3, 라벨 없음 0편)") in out
    assert "제외 판정의 관련 합계: 갈래 0 관련 1/라벨 1 (제외 1편) · 갈래 1 관련 0/라벨 1 (제외 1편)" in out
    # 판정은 그대로 — computing 갈래 0 은 뺀 X 가 '관련'(과잉 제외 100%), 갈래 1 은 한 절에 무관 2편
    assert "합격 질문: 갈래 0 1/2 · 갈래 1 1/2" in out


# ── make_labels.py ──────────────────────────────────────────────────────


def test_label_rows_take_section_papers_then_exclusions_once_each():
    from make_labels import paper_rows

    evidence = {
        "E1": {"cnts_id": "A", "meta": {"title": "그리드 자원 관리", "personal_author": "김철수; 이영희"}},
        "E2": {"cnts_id": "B", "meta": {"title": "클라우드 스케줄링", "personal_author": None}},
    }
    report = _report([["A", "B"], ["A"]], [["X"], ["X", "B"]], evidence)
    assert paper_rows(report) == [
        {"cnts_id": "A", "title": "그리드 자원 관리", "authors": "김철수; 이영희", "label": ""},
        # B 는 절 서지에 저자가 비어 있고 다른 하위질문의 제외 기록에 있다 — 빈 칸만 채운다
        {"cnts_id": "B", "title": "클라우드 스케줄링", "authors": "홍길동", "label": ""},
        {"cnts_id": "X", "title": "제외 X", "authors": "홍길동", "label": ""},
    ]


def test_write_labels_keeps_existing_labels_and_appends_new_papers(tmp_path):
    from make_labels import write_labels
    from score import load_labels

    path = tmp_path / "computing.csv"
    _write_labels(path, [("A", "관련")])
    arm0 = _report([["A"]], [["X"]])
    arm1 = _report([["A", "C"]], [])

    assert write_labels(path, [arm0, arm1]) == (3, 2)        # (전체, 새로 붙인 줄)

    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    # 새 줄은 제목·cnts_id 순 — C(제목 없음)가 제외 논문 X 보다 앞이다
    assert [r["cnts_id"] for r in rows] == ["A", "C", "X"]
    assert rows[0]["title"] == "제목 A"                      # 이미 있는 줄은 손대지 않는다
    assert load_labels(path) == {"A": "관련"}
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")     # 엑셀이 한글을 깨지 않게 BOM


def test_make_labels_main_writes_one_file_per_question(tmp_path, capsys):
    from make_labels import main

    reports = {"job-1": _report([["A"]], [["X"]]), "job-2": _report([["B"]], [])}

    def handler(request: httpx.Request) -> httpx.Response:
        jid = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, json={"job_id": jid, "status": "completed", "report": reports[jid]})

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"}}), encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--out-dir", str(tmp_path / "labels")], client=client)

    assert rc == 0
    with (tmp_path / "labels" / "computing.csv").open(encoding="utf-8-sig", newline="") as f:
        assert [r["cnts_id"] for r in csv.DictReader(f)] == ["A", "B", "X"]
    capsys.readouterr().out.encode("cp949")


def test_new_label_rows_hide_which_papers_critic_excluded(tmp_path):
    """절 논문 → 제외 논문 → 갈래 1 순서로 두면 뒤쪽 줄이 critic 이 뺀 논문인 것이 드러난다 — 제목 순으로 섞는다."""
    from make_labels import write_labels

    evidence = {"E1": {"cnts_id": "S", "meta": {"title": "하 절 논문"}}}
    arm0 = _report([["S"]], [["X"]], evidence)            # X 의 제목은 '제외 X'
    arm1 = _report([["S"]], [["B"]], evidence)
    path = tmp_path / "computing.csv"

    write_labels(path, [arm0, arm1])

    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [(r["cnts_id"], r["title"]) for r in rows] == [("B", "제외 B"), ("X", "제외 X"), ("S", "하 절 논문")]


def test_rewriting_keeps_planner_columns_and_fills_blank_titles(tmp_path):
    """리허설에서 다시 돌려도 기획자가 엑셀에서 더한 칸과 라벨을 지우지 않는다 — 비었던 제목·저자만 채운다."""
    from make_labels import write_labels
    from score import load_labels

    path = tmp_path / "computing.csv"
    path.write_text("cnts_id,title,authors,label,메모\nX,,,관련,원 질문의 핵심\n", encoding="utf-8-sig")

    assert write_labels(path, [_report([], [["X"]])]) == (1, 0)

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert reader.fieldnames == ["cnts_id", "title", "authors", "label", "메모"]
    assert rows == [{"cnts_id": "X", "title": "제외 X", "authors": "홍길동", "label": "관련", "메모": "원 질문의 핵심"}]
    assert load_labels(path) == {"X": "관련"}


def test_make_labels_reports_a_question_whose_job_cannot_be_read(tmp_path, capsys):
    from make_labels import main

    def handler(request: httpx.Request) -> httpx.Response:
        if "job-1" in request.url.path:
            raise httpx.ConnectError("연결 거부")
        jid = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, json={"job_id": jid, "status": "completed", "report": _report([["A"]], [])})

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"},
                                 "library": {"0": "job-3", "1": "job-4"}}), encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--out-dir", str(tmp_path / "labels")], client=client)

    assert rc == 1
    out = capsys.readouterr().out
    out.encode("cp949")
    assert "[computing] 잡을 읽지 못했다(ConnectError" in out and "잡을 읽지 못한 질문 1개: computing" in out
    assert (tmp_path / "labels" / "library.csv").exists()


# ── run_pair.py ─────────────────────────────────────────────────────────


def _fake_research_api(fail: str | None = None):
    """POST /research·GET /research/{id}·POST approve 를 흉내 낸다.

    조회할 때마다 한 걸음씩 나아간다 — created → planning → awaiting_approval, approved → running → completed.
    fail 로 준 잡은 planning 다음에 failed 가 된다.
    """
    state = {"jobs": {}, "requests": []}
    steps = {"created": "planning", "planning": "awaiting_approval", "approved": "running", "running": "completed"}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        path = request.url.path
        if request.method == "POST" and path == "/api/research":
            body = json.loads(request.content)
            jid = f"job-{len(state['jobs']) + 1}"
            state["jobs"][jid] = {"job_id": jid, "question": body["question"], "params": body["params"],
                                  "status": "created", "plan": None, "last_error": None, "approved_with": "없음"}
            return httpx.Response(200, json={"job_id": jid, "status": "created"})
        m = re.fullmatch(r"/api/research/([^/]+)(/approve)?", path)
        job = state["jobs"][m.group(1)]
        if m.group(2):
            job["approved_with"] = json.loads(request.content) if request.content else None
            job["status"] = "approved"
            return httpx.Response(200, json={"job_id": job["job_id"], "status": "approved"})
        if job["status"] == "planning" and job["job_id"] == fail:
            job["status"], job["last_error"] = "failed", "계획 LLM 실패"
        elif job["status"] in steps:
            job["status"] = steps[job["status"]]
            if job["status"] == "awaiting_approval":
                job["plan"] = [f"{job['job_id']} 계획 1", f"{job['job_id']} 계획 2"]
        return httpx.Response(200, json={k: job[k] for k in ("job_id", "question", "params", "status",
                                                             "plan", "last_error")})

    return state, handler


def test_run_question_approves_arm1_with_arm0_plan_and_no_browser_id():
    from run_pair import run_question

    state, handler = _fake_research_api()
    sleeps: list[float] = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        pair = run_question(client, API, "컴퓨팅 자원에 대한 연구가 궁금해",
                            poll=5.0, timeout=60.0, sleep=sleeps.append)

    assert pair == {"0": "job-1", "1": "job-2"}
    jobs = state["jobs"]
    assert [j["params"] for j in jobs.values()] == [{"critic_scope": 0}, {"critic_scope": 1}]
    # 갈래 0 은 제 계획 그대로(본문 없음), 갈래 1 은 갈래 0 의 계획 — 같은 하위질문으로 critic 만 다르게 돈다
    assert jobs["job-1"]["approved_with"] is None
    assert jobs["job-2"]["approved_with"] == {"plan": ["job-1 계획 1", "job-1 계획 2"]}
    assert [j["status"] for j in jobs.values()] == ["completed", "completed"]
    # 브라우저 ID 를 보내지 않는다 — created_by 가 NULL 이라 브라우저당 실행 제한에 걸리지 않는다
    assert all("x-session-id" not in r.headers for r in state["requests"])
    assert sleeps and set(sleeps) == {5.0}


def test_run_question_prints_job_ids_as_soon_as_they_exist(capsys):
    """한 질문은 수 분 돈다 — 도중에 실패해도 남은 잡을 찾을 수 있게 만들자마자 id 를 찍는다."""
    from run_pair import run_question

    state, handler = _fake_research_api(fail="job-1")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError):
            run_question(client, API, "컴퓨팅 자원에 대한 연구가 궁금해", poll=0, timeout=60.0, sleep=lambda _: None)

    assert "갈래 0 job-1" in capsys.readouterr().out


def test_wait_for_rides_out_a_few_transient_errors():
    from run_pair import wait_for

    request = httpx.Request("GET", f"{API}/research/job-1")
    outcomes = [httpx.ReadTimeout("느림", request=request), httpx.Response(502, request=request),
                httpx.Response(200, request=request, json={"job_id": "job-1", "status": "completed"})]

    def handler(req: httpx.Request) -> httpx.Response:
        item = outcomes.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    sleeps: list[float] = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        job = wait_for(client, API, "job-1", "completed", poll=5.0, timeout=60.0, sleep=sleeps.append)

    assert job["status"] == "completed" and sleeps == [5.0, 5.0]


@pytest.mark.parametrize("failure", ["404", "many"])
def test_wait_for_gives_up_on_client_errors_and_on_repeated_failures(failure):
    from run_pair import TRANSIENT_RETRIES, wait_for

    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if failure == "404":
            return httpx.Response(404, request=req)
        raise httpx.ConnectError("연결 거부", request=req)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPError):
            wait_for(client, API, "job-1", "completed", poll=0, timeout=60.0, sleep=lambda _: None)

    assert len(calls) == (1 if failure == "404" else TRANSIENT_RETRIES + 1)


def test_run_pair_creates_the_output_folder_and_replaces_the_file_whole(tmp_path):
    from run_pair import main

    questions = tmp_path / "questions.json"
    questions.write_text(json.dumps([{"key": "computing", "question": "컴퓨팅 자원에 대한 연구가 궁금해"}],
                                    ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "새 폴더" / "pairs.json"          # 아직 없는 폴더 — 첫 질문을 다 돌린 뒤에 터지면 안 된다
    _, handler = _fake_research_api()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--out", str(out), "--questions", str(questions), "--poll", "0"], client=client)

    assert rc == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"computing": {"0": "job-1", "1": "job-2"}}
    assert [p.name for p in out.parent.iterdir()] == ["pairs.json"]      # 임시 파일이 남지 않는다


def test_run_pair_main_reports_a_failed_question_and_keeps_the_others(tmp_path, capsys):
    from run_pair import main

    questions = tmp_path / "questions.json"
    questions.write_text(json.dumps([{"key": "computing", "question": "컴퓨팅 자원에 대한 연구가 궁금해"},
                                     {"key": "library", "question": "공공도서관 서비스 품질 평가 연구가 궁금해"}],
                                    ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "pairs.json"
    out.write_text(json.dumps({"old": {"0": "a", "1": "b"}}), encoding="utf-8")
    state, handler = _fake_research_api(fail="job-1")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--out", str(out), "--questions", str(questions), "--poll", "0"],
                  client=client)

    assert rc == 1
    # computing 의 갈래 0(job-1)이 계획에서 실패 — 그 질문은 기록하지 않고 다음 질문을 돌린다. 먼저 있던 기록은 남긴다
    assert json.loads(out.read_text(encoding="utf-8")) == {"old": {"0": "a", "1": "b"},
                                                           "library": {"0": "job-2", "1": "job-3"}}
    text = capsys.readouterr().out
    text.encode("cp949")
    assert "--only computing" in text


# ── mark_example.py ─────────────────────────────────────────────────────


class _FakeSession:
    """db.postgres.SyncSessionLocal() 대역 — 실행한 문장을 기록하고 is_example 지금 값을 돌려준다."""

    def __init__(self, current, deleted_at=None):
        self.current = current          # None 이면 그 연구 행이 없다
        self.deleted_at = deleted_at
        self.executed: list[tuple[str, dict]] = []
        self.committed = False
        self.closed = False

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params))
        row = None if self.current is None else (self.current, self.deleted_at)
        return types.SimpleNamespace(one_or_none=lambda: row)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True

    def updates(self) -> list[tuple[str, dict]]:
        return [(s, p) for s, p in self.executed if s.lstrip().upper().startswith("UPDATE")]


@pytest.fixture
def fake_db(monkeypatch):
    """스크립트가 함수 안에서 import 하는 db.postgres 를 대역으로 바꾼다 — 진짜 DB 에 닿지 않는다."""
    def _make(current, deleted_at=None):
        session = _FakeSession(current, deleted_at)
        db_pkg = types.ModuleType("db")
        db_pg = types.ModuleType("db.postgres")
        db_pg.SyncSessionLocal = lambda: session
        db_pkg.postgres = db_pg
        monkeypatch.setitem(sys.modules, "db", db_pkg)
        monkeypatch.setitem(sys.modules, "db.postgres", db_pg)
        return session
    return _make


def test_mark_example_without_yes_only_reads(fake_db, capsys):
    from mark_example import main

    session = fake_db(False)
    assert main(["--work", WORK, "--on"]) == 0
    assert session.updates() == [] and not session.committed and session.closed
    out = capsys.readouterr().out
    assert "--yes" in out and "False -> True" in out
    out.encode("cp949")


def test_mark_example_with_yes_updates_only_is_example(fake_db):
    from mark_example import main

    session = fake_db(False)
    assert main(["--work", WORK.upper(), "--on", "--yes"]) == 0
    (sql, params), = session.updates()
    assert "SET is_example = :flag" in sql and "WHERE id = CAST(:id AS uuid)" in sql
    assert params == {"id": WORK, "flag": True}             # 대문자로 줘도 표준형 id 로 찾는다
    assert session.committed and session.closed


def test_mark_example_leaves_unknown_or_unchanged_work_alone(fake_db):
    from mark_example import main

    missing = fake_db(None)
    assert main(["--work", WORK, "--off", "--yes"]) == 1
    assert missing.updates() == [] and not missing.committed

    already = fake_db(True)
    assert main(["--work", WORK, "--on", "--yes"]) == 0
    assert already.updates() == [] and not already.committed


def test_mark_example_refuses_a_deleted_work(fake_db, capsys):
    """지운 연구는 목록에 나오지 않는다 — 지정해도 방문자에게 보이지 않으니 '바꿨다' 로 끝내지 않는다."""
    from mark_example import main

    session = fake_db(False, deleted_at="2026-10-09 10:00:00+09")
    assert main(["--work", WORK, "--on", "--yes"]) == 1
    assert session.updates() == [] and not session.committed
    out = capsys.readouterr().out
    assert "지운 연구" in out
    out.encode("cp949")
