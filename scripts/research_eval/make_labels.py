r"""make_labels.py — 두 갈래 잡의 라벨 파일 만들기 (HTTP 만, DB 를 읽지도 쓰지도 않는다)

질문마다 labels/<질문키>.csv(cnts_id,title,authors,label) 를 쓴다. 두 갈래 보고서의 절 논문
(report.sections[].papers — 서지는 report.evidence)과 제외 논문(report.trail[].excluded_papers)을 합쳐
한 논문은 한 줄만 둔다 — 라벨은 잡이 아니라 질문 단위다(spec §8). 파일이 이미 있으면 그 줄과 라벨을
그대로 두고(비어 있던 제목·저자만 채운다) 새 논문만 뒤에 붙인다 — 리허설에서 다시 돌려도 단 라벨을 잃지 않는다.
기획자가 엑셀에서 더한 칸(메모 등)도 그대로 둔다.
새로 붙이는 줄은 제목·cnts_id 순으로 섞는다(맹검) — 갈래·절·제외 순서대로 두면 뒤쪽 줄이 critic 이 뺀 논문인 것을
라벨 다는 사람이 짐작해 판정(D11)이 치우친다.

label 칸은 사람이 '관련'·'무관' 으로 채운다. 원 질문의 주제를 다루면 '관련'(하위질문에서 벗어나도),
같은 단어를 다른 뜻으로 쓴 논문을 포함해 원 질문과 무관하면 '무관'. 엑셀이 한글을 깨지 않게 BOM 을 붙인다.

실행 (서버):
  docker exec nl-lib-fastapi python /app/data/research_eval/make_labels.py \
    --api http://localhost:8000/api --pairs /app/data/research_eval/pairs.json \
    --out-dir /app/data/research_eval/labels
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import httpx

from run_pair import get_job

HERE = Path(__file__).resolve().parent
FIELDS = ["cnts_id", "title", "authors", "label"]


def _add(rows: dict[str, dict], cnts_id: str, title: str | None, authors: str | None) -> None:
    row = rows.setdefault(cnts_id, {"cnts_id": cnts_id, "title": "", "authors": "", "label": ""})
    row["title"] = row["title"] or (title or "")
    row["authors"] = row["authors"] or (authors or "")


def paper_rows(report: dict) -> list[dict]:
    """보고서 하나의 절 논문 → 제외 논문 순으로, 한 논문 한 줄(label 은 빈 칸)."""
    meta = {e["cnts_id"]: e.get("meta") or {} for e in (report.get("evidence") or {}).values()}
    rows: dict[str, dict] = {}
    for sec in report.get("sections") or []:
        for p in sec.get("papers") or []:
            m = meta.get(p["cnts_id"], {})
            _add(rows, p["cnts_id"], m.get("title"), m.get("personal_author"))
    for t in report.get("trail") or []:
        for p in t.get("excluded_papers") or []:
            _add(rows, p["cnts_id"], p.get("title"), p.get("personal_author"))
    return list(rows.values())


def read_rows(path: Path) -> tuple[list[dict], list[str]]:
    """(줄, FIELDS 밖의 칸 이름). 기획자가 엑셀에서 더한 칸을 다시 쓸 때 지우지 않으려고 칸 이름도 돌려준다."""
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        extra = [k for k in reader.fieldnames or [] if k and k not in FIELDS]
        return [{k: (r.get(k) or "") for k in FIELDS + extra} for r in reader], extra


def fresh_rows(reports: list[dict]) -> list[dict]:
    """두 갈래 보고서의 논문을 한 논문 한 줄로 합쳐(빈 제목·저자는 다른 갈래 값으로 채운다) 제목·cnts_id 순으로 —
    갈래·절·제외 순서를 지운다(맹검)."""
    rows: dict[str, dict] = {}
    for report in reports:
        for r in paper_rows(report):
            _add(rows, r["cnts_id"], r["title"], r["authors"])
    return sorted(rows.values(), key=lambda r: (r["title"], r["cnts_id"]))


def merge_rows(existing: list[dict], fresh: list[dict]) -> list[dict]:
    """있던 줄은 그대로(라벨·더한 칸 포함 — 비어 있던 제목·저자만 채운다), 새 논문만 뒤에 붙인다."""
    by_id = {r["cnts_id"]: r for r in fresh}
    out = []
    for r in existing:
        new = by_id.get(r["cnts_id"])
        if new is not None:
            r = {**r, "title": r["title"] or new["title"], "authors": r["authors"] or new["authors"]}
        out.append(r)
    seen = {r["cnts_id"] for r in existing}
    for r in fresh:
        if r["cnts_id"] not in seen:
            seen.add(r["cnts_id"])
            out.append(r)
    return out


def write_labels(path: Path, reports: list[dict]) -> tuple[int, int]:
    """라벨 파일을 쓰고 (전체 줄 수, 새로 붙인 줄 수) 를 돌려준다."""
    existing, extra = read_rows(path)
    rows = merge_rows(existing, fresh_rows(reports))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS + extra, restval="")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows), len(rows) - len(existing)


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description="두 갈래 잡의 라벨 파일 만들기 (HTTP 만)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--pairs", required=True, type=Path, help="run_pair.py 출력 JSON")
    ap.add_argument("--out-dir", type=Path, default=HERE / "labels")
    args = ap.parse_args(argv)

    api = args.api.rstrip("/")
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    failed: list[str] = []
    try:
        for key, arms in pairs.items():
            try:
                jobs = [get_job(client, api, arms[arm]) for arm in ("0", "1")]
            except httpx.HTTPError as e:
                print(f"[{key}] 잡을 읽지 못했다({type(e).__name__}: {e}) - 건너뛴다")
                failed.append(key)
                continue
            missing = [j["job_id"] for j in jobs if not j.get("report")]
            if missing:
                print(f"[{key}] 보고서가 없는 잡 {', '.join(missing)} - 건너뛴다")
                continue
            path = args.out_dir / f"{key}.csv"
            total, new = write_labels(path, [j["report"] for j in jobs])
            print(f"[{key}] {total}편(새 {new}) -> {path}")
    finally:
        if own:
            client.close()
    if failed:
        print(f"잡을 읽지 못한 질문 {len(failed)}개: {', '.join(failed)} - 같은 명령으로 다시 돌린다(단 라벨은 남는다)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
