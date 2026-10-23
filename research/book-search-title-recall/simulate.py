"""재작성 켬·끔 두 응답으로 검색 방식을 그대로 다시 만든다 (1회성).

- CUR: 지금 화면 — 재작성한 질의로만 후보를 찾는다(켬 응답 그대로).
- A:   원래 질의·재작성 질의 두 갈래로 후보를 찾아 합친다. 도서마다 갈래별 내용 점수(각 갈래 질의로 재정렬한 값) 중 큰 것을
       쓰고, 제목 일치율은 [원래, 재작성] 으로 다시 계산해 지금과 같이 종합한다.
- C:   CUR 에 원래 질의 갈래의 도서 중 제목 일치율(원래 질의 기준) 0.5 이상만 더한다.
- AH0: A 에 제목 정규화가 한자를 지우지 않게만 한 것(첫 커밋 60b81d2b) — 판정 묶음(judge/)은 CUR·A·AH0 의 상위 10권이다.
- AH:  A 에 지금 저장소의 제목 일치(app/services/search/title_scorer.py — 한자를 남기고 NFKC, 한자를 뺀 꼴이 제목 길이의
       절반 이상 남으면 그 꼴로도 견준다). 구현된 방식.

CUR·A·C·AH0 의 제목 일치는 고치기 전 사본(title_scorer_before.py, origin/dev 판)으로 계산한다 — 저장소 모듈을 쓰면 고친 뒤
다시 돌릴 때 CUR 이 이미 고친 규칙으로 계산돼 표가 재현되지 않는다.

끔 응답이 도서 필터 0건이라 API 가 전체(논문)로 다시 찾은 경우가 있다 — 원래 질의 갈래는 도서 필터 안에서 찾으므로 끔 응답의
논문(doc_type paper·KCI_FI…)은 뺀다(두 갈래가 모두 0건이면 API 는 두 갈래 모두 필터 없이 다시 찾는다 — 이 계산 밖).

내용 점수는 운영이 돌려준 content_score(제목 보정 전 값)를 쓰므로, 갈래마다 자기 질의로 재정렬하는 구현이면 이 계산과 같다.

    python simulate.py   # sim.json — 질의마다 방식별 순위 목록, 그리고 자동 지표 요약을 찍는다
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "app"))
sys.stdout.reconfigure(encoding="utf-8")

import title_scorer_before as before  # noqa: E402
from services.search import title_scorer as now  # noqa: E402

_STRIP_BEFORE = re.compile(r"[^0-9a-zA-Z가-힣]+")
_STRIP_KEEP_HANJA = re.compile(r"[^0-9a-zA-Z가-힣㐀-䶿一-鿿豈-﫿]+")
assert before._STRIP_RE.pattern == _STRIP_BEFORE.pattern

RESCUE = 0.5


def titles(b: dict) -> list[str]:
    t = [b["title"]] if b.get("title") else []
    if b.get("title") and b.get("title_remainder"):
        t.append(f"{b['title']} {b['title_remainder']}")
    return t


def title_score(scorer, queries: list[str], b: dict) -> float:
    return max((scorer.title_match_score(queries, t) for t in titles(b)), default=0.0)


def rescore(books: dict[str, dict], queries: list[str], scorer) -> list[dict]:
    out = []
    for bid, b in books.items():
        ts = title_score(scorer, queries, b)
        out.append({**b, "book_id": bid, "title_score": ts, "best": now.combine_scores(ts, b["content"])})
    return sorted(out, key=lambda x: x["best"], reverse=True)


def is_paper(b: dict) -> bool:
    return b.get("doc_type") == "paper" or b["book_id"].startswith("KCI_FI")


def variants(rec: dict) -> dict[str, list[dict]]:
    q, rw = rec["query"], rec["on"]["rewritten"]
    queries = [q] + ([rw] if rw and rw != q else [])
    on = {b["book_id"]: b for b in rec["on"]["books"]}
    off = {b["book_id"]: b for b in rec["off"]["books"] if not is_paper(b)}
    merged = dict(on)
    for bid, b in off.items():
        if bid not in merged or (b["content"] or 0) > (merged[bid]["content"] or 0):
            merged[bid] = b
    rescued = dict(on)
    for bid, b in off.items():
        if bid not in rescued and title_score(before, [q], b) >= RESCUE:
            rescued[bid] = b
    out = {"CUR": rescore(on, queries, before), "A": rescore(merged, queries, before), "C": rescore(rescued, queries, before)}
    before._STRIP_RE = _STRIP_KEEP_HANJA
    try:
        out["AH0"] = rescore(merged, queries, before)
    finally:
        before._STRIP_RE = _STRIP_BEFORE
    out["AH"] = rescore(merged, queries, now)
    return out


def rank(lst: list[dict], bid: str) -> int | None:
    ids = [b["book_id"] for b in lst]
    return ids.index(bid) + 1 if bid in ids else None


def main() -> None:
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((HERE / "raw").glob("*.json"))]
    sim, summary = [], {}
    for rec in recs:
        v = variants(rec)
        sim.append({"query": rec["query"], "kind": rec["kind"], "targets": rec["targets"],
                    "rewritten": rec["on"]["rewritten"],
                    "variants": {k: [{"book_id": b["book_id"], "title": b.get("title"), "best": b["best"],
                                      "content": b["content"], "title_score": b["title_score"]} for b in lst]
                                 for k, lst in v.items()},
                    "n": {k: len(lst) for k, lst in v.items()}})
        for k, lst in v.items():
            s = summary.setdefault(rec["kind"], {}).setdefault(k, {"queries": 0, "hit1": 0, "hit5": 0, "found": 0, "n": 0})
            s["queries"] += 1
            s["n"] += len(lst)
            if rec["targets"]:
                ranks = [r for r in (rank(lst, t) for t in rec["targets"]) if r]
                best = min(ranks) if ranks else None
                s["hit1"] += best == 1
                s["hit5"] += bool(best and best <= 5)
                s["found"] += bool(best)
    (HERE / "sim.json").write_text(json.dumps(sim, ensure_ascii=False, indent=1), encoding="utf-8")
    for kind, vs in summary.items():
        for k, s in vs.items():
            n = s["queries"]
            line = f"{kind:18} {k:3} 질의 {n:3} 평균 후보 {s['n'] / n:5.1f}"
            if kind != "judged":
                line += f" | 1위 {s['hit1']}/{n} · 5위 안 {s['hit5']}/{n} · 목록에 있음 {s['found']}/{n}"
            print(line)
    (HERE / "auto_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
