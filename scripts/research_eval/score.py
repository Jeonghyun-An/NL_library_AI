r"""score.py — critic 두 갈래 채점 (HTTP 만, DB 를 읽지도 쓰지도 않는다)

spec §8 의 합격선(D11)을 질문·갈래마다 센다.
  ① 절마다 무관 1편 이하 — 보고서 절(sections[].papers)에 실린 논문 중 라벨이 '무관' 인 수
  ② 과잉 제외 10% 이하 — 제외된 서로 다른 논문(trail[].excluded_papers) 중 라벨이 '관련' 인 비율.
     라벨 칸이 빈 논문은 분모에서 뺀다. 라벨 단 제외 논문이 없으면(제외 0편 포함) 비율은 없고 ② 는 통과다.
라벨 칸이 빈 논문 수(절 논문·제외 논문)를 함께 찍는다 — 0 이 아니면 그 갈래는 '판정 보류'(합격으로 세지 않는다)이고
라벨을 마저 단 뒤 다시 센다. 단 ① 을 이미 넘긴 갈래는 라벨을 더 달아도 줄지 않으므로 '불합격' 이다.
'합격 질문' 의 분모는 고정 질문 목록(--questions, 기본 questions.json)의 질문 수다 — pairs 에 빠진 질문(run_pair 가
실패해 기록하지 않은 질문)과 라벨 파일·보고서가 없거나 조회에 실패해 채점하지 못한 질문도 분모에 들고 따로 이름을
찍는다(D11 은 다섯 질문 모두 합격이어야 한다). 질문 목록에 없는 pairs 의 키는 경고만 하고 채점하지 않는다.
라벨 파일은 make_labels.py 가 만든 labels/<질문키>.csv 이고 label 칸은 '관련'·'무관' 만 받는다.
갈래마다 '보고서 정밀도'(보고서 절에 실린 서로 다른 논문 중 '관련' 비율 — 라벨 칸이 빈 논문은 분모에서 뺀다)를 한 줄
더 찍고, 끝에 채점한 질문의 합계(보고서 정밀도·제외 판정의 관련 수)를 찍는다. 06a 완료노트 §5-5 가 손으로 센 표
(갈래 0 관련 62·무관 36·63%, 갈래 1 55·43·56%, 제외 판정의 관련 52/118·0/3)와 같은 셈이라 D18 재판정을 06a 와
견줄 수 있다. 합격 판정에는 쓰지 않는다.

실행 (서버):
  docker exec nl-lib-fastapi python /app/data/research_eval/score.py \
    --api http://localhost:8000/api --pairs /app/data/research_eval/pairs.json \
    --labels-dir /app/data/research_eval/labels
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import httpx

from run_pair import QUESTIONS, get_job, load_questions

HERE = Path(__file__).resolve().parent
RELEVANT, IRRELEVANT = "관련", "무관"
LABELS = (RELEVANT, IRRELEVANT)
MAX_IRRELEVANT_PER_SECTION = 1
MAX_OVER_EXCLUSION = 0.10
ARMS = ("0", "1")
TOTAL_KEYS = ("relevant", "irrelevant", "unlabeled", "excluded", "excluded_labeled", "excluded_relevant")


def load_labels(path: Path) -> dict[str, str]:
    """{cnts_id: '관련'|'무관'}. 빈 칸은 라벨 없음으로 빼고, 다른 값이 있으면 줄 번호와 함께 ValueError."""
    labels: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = (row.get("label") or "").strip()
            if not label:
                continue
            if label not in LABELS:
                raise ValueError(f"{path.name} {reader.line_num}행: 알 수 없는 라벨 {label!r} - 관련·무관 중 하나")
            labels[row["cnts_id"].strip()] = label
    return labels


def _section_ids(report: dict) -> list[list[str]]:
    return [[p["cnts_id"] for p in sec.get("papers") or []] for sec in report.get("sections") or []]


def _excluded_ids(report: dict) -> list[str]:
    """제외된 서로 다른 논문 — 두 하위질문이 같은 논문을 뺐으면 한 번만."""
    ids = (p["cnts_id"] for t in report.get("trail") or [] for p in t.get("excluded_papers") or [])
    return list(dict.fromkeys(ids))


def section_irrelevant(report: dict, labels: dict[str, str]) -> list[int]:
    """절마다 '무관' 라벨 논문 수(보고서 절 순서)."""
    return [sum(labels.get(c) == IRRELEVANT for c in dict.fromkeys(ids)) for ids in _section_ids(report)]


def over_exclusion(report: dict, labels: dict[str, str]) -> float | None:
    """제외된 서로 다른 논문 중 '관련' 비율. 라벨 없는 논문은 분모에서 빼고, 라벨 단 제외 논문이 없으면 None."""
    labeled = [c for c in _excluded_ids(report) if c in labels]
    if not labeled:
        return None
    return sum(labels[c] == RELEVANT for c in labeled) / len(labeled)


def report_papers(report: dict) -> list[str]:
    """보고서 절에 실린 서로 다른 논문(절 순서) — 두 절에 실린 논문은 한 번만."""
    return list(dict.fromkeys(c for ids in _section_ids(report) for c in ids))


def report_precision(report: dict, labels: dict[str, str]) -> dict:
    """보고서 정밀도의 셈 — 보고서 절 논문(서로 다른 편) 중 '관련'·'무관' 라벨 수와 라벨 칸이 빈 수."""
    papers = report_papers(report)
    relevant = sum(labels.get(c) == RELEVANT for c in papers)
    irrelevant = sum(labels.get(c) == IRRELEVANT for c in papers)
    return {"relevant": relevant, "irrelevant": irrelevant, "unlabeled": len(papers) - relevant - irrelevant}


def precision(relevant: int, irrelevant: int) -> float | None:
    """관련 / (관련 + 무관). 라벨 단 논문이 없으면 None."""
    labeled = relevant + irrelevant
    return relevant / labeled if labeled else None


def score_arm(report: dict, labels: dict[str, str]) -> dict:
    excluded = _excluded_ids(report)
    labeled = [c for c in excluded if c in labels]
    papers = {c for ids in _section_ids(report) for c in ids} | set(excluded)
    return {
        "section_irrelevant": section_irrelevant(report, labels),
        "over_exclusion": over_exclusion(report, labels),
        "excluded": len(excluded),
        "excluded_labeled": len(labeled),
        "excluded_relevant": sum(labels[c] == RELEVANT for c in labeled),
        "unlabeled": len(papers - set(labels)),
        "report": report_precision(report, labels),
    }


def _sections_ok(arm: dict) -> bool:
    return all(n <= MAX_IRRELEVANT_PER_SECTION for n in arm["section_irrelevant"])


def passes(arm: dict) -> bool:
    """합격선(D11): 절마다 무관 1편 이하이고 과잉 제외 10% 이하(비율이 없으면 통과)."""
    over = arm["over_exclusion"]
    return _sections_ok(arm) and (over is None or over <= MAX_OVER_EXCLUSION)


def verdict(arm: dict) -> str:
    """'합격'·'불합격'·'판정 보류'. 라벨 칸이 빈 논문이 있으면 보류한다 — 단 ① 을 이미 넘긴 갈래는
    라벨을 더 달아도 절의 무관 수가 줄지 않으므로 불합격이다."""
    if not _sections_ok(arm):
        return "불합격"
    if arm["unlabeled"]:
        return "판정 보류"
    return "합격" if passes(arm) else "불합격"


def format_arm(arm_key: str, arm: dict) -> str:
    per_section = ",".join(str(n) for n in arm["section_irrelevant"]) or "-"
    if arm["over_exclusion"] is None:
        over = f"과잉 제외 - (라벨 단 제외 0편, 제외 {arm['excluded']}편)"
    else:
        over = (f"과잉 제외 {arm['over_exclusion'] * 100:.1f}% (관련 {arm['excluded_relevant']}"
                f"/라벨 {arm['excluded_labeled']}, 제외 {arm['excluded']}편)")
    return f"  갈래 {arm_key}  절별 무관 {per_section}  {over}  라벨 없음 {arm['unlabeled']}편  -> {verdict(arm)}"


def _precision_text(counts: dict) -> str:
    rate = precision(counts["relevant"], counts["irrelevant"])
    shown = "-" if rate is None else f"{rate * 100:.1f}%"
    return f"{shown} (관련 {counts['relevant']} · 무관 {counts['irrelevant']}, 라벨 없음 {counts['unlabeled']}편)"


def format_precision(arm_key: str, counts: dict) -> str:
    return f"  갈래 {arm_key}  보고서 정밀도 {_precision_text(counts)}"


def add_totals(total: dict, arm: dict) -> None:
    """갈래 결과 하나를 그 갈래의 합계에 더한다(보고서 정밀도의 셈 + 제외 판정의 셈)."""
    for key in ("relevant", "irrelevant", "unlabeled"):
        total[key] += arm["report"][key]
    for key in ("excluded", "excluded_labeled", "excluded_relevant"):
        total[key] += arm[key]


def format_totals(totals: dict[str, dict], scored: int) -> list[str]:
    """채점한 질문의 합계 두 줄 — 06a 완료노트 §5-5 표의 '보고서 관련·무관·정밀도'·'제외 판정의 관련' 칸과 같은 셈."""
    return [
        f"보고서 정밀도 합계(채점한 {scored}개 질문): "
        + " · ".join(f"갈래 {arm} {_precision_text(totals[arm])}" for arm in ARMS),
        "제외 판정의 관련 합계: "
        + " · ".join(f"갈래 {arm} 관련 {totals[arm]['excluded_relevant']}/라벨 {totals[arm]['excluded_labeled']}"
                     f" (제외 {totals[arm]['excluded']}편)" for arm in ARMS),
    ]


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description="critic 두 갈래 채점 (HTTP 만)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--pairs", required=True, type=Path, help="run_pair.py 출력 JSON")
    ap.add_argument("--labels-dir", type=Path, default=HERE / "labels")
    ap.add_argument("--questions", type=Path, default=QUESTIONS, help="고정 질문 목록 — 합격 질문의 분모")
    args = ap.parse_args(argv)

    api = args.api.rstrip("/")
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    keys = [q["key"] for q in load_questions(args.questions)]
    for key in pairs:
        if key not in keys:
            print(f"[{key}] 질문 목록({args.questions.name})에 없는 키 - 채점하지 않는다")
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    passed = {"0": 0, "1": 0}
    totals = {arm: dict.fromkeys(TOTAL_KEYS, 0) for arm in ARMS}
    scored = 0
    skipped: list[str] = []
    unlabeled = 0
    try:
        for key in keys:
            arms = pairs.get(key)
            if arms is None:
                print(f"[{key}] pairs 에 없다 - run_pair.py --only {key} 로 돌린다")
                skipped.append(key)
                continue
            path = args.labels_dir / f"{key}.csv"
            if not path.exists():
                print(f"[{key}] 라벨 파일이 없다: {path} - make_labels.py 를 먼저 돌린다")
                skipped.append(key)
                continue
            try:
                labels = load_labels(path)
            except ValueError as e:
                print(f"[{key}] {e}")
                return 2
            try:
                reports = {arm: get_job(client, api, arms[arm]).get("report") for arm in ("0", "1")}
            except httpx.HTTPError as e:
                print(f"[{key}] 잡을 읽지 못했다({type(e).__name__}: {e}) - 건너뛴다")
                skipped.append(key)
                continue
            if not all(reports.values()):
                print(f"[{key}] 보고서가 없는 갈래가 있다 - 건너뛴다")
                skipped.append(key)
                continue
            print(f"[{key}] {reports['0'].get('question', '')}")
            scored += 1
            for arm in ARMS:
                result = score_arm(reports[arm], labels)
                passed[arm] += verdict(result) == "합격"
                unlabeled += result["unlabeled"]
                add_totals(totals[arm], result)
                print(format_arm(arm, result))
                print(format_precision(arm, result["report"]))
    finally:
        if own:
            client.close()
    total = len(keys)
    print(f"합격 질문: 갈래 0 {passed['0']}/{total} · 갈래 1 {passed['1']}/{total}")
    if scored:
        for line in format_totals(totals, scored):
            print(line)
    if skipped:
        print(f"채점하지 못한 질문 {len(skipped)}개: {', '.join(skipped)} - 합격으로 세지 않았다")
    if unlabeled:
        print(f"라벨 칸이 빈 논문이 갈래 합계 {unlabeled}편 있다 - 그 갈래는 판정 보류, 다 단 뒤 다시 센다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
