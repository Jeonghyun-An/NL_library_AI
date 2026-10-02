r"""build_canary_manifest.py — 카나리 잡 매니페스트 만들기 (DB 읽기 전용, 파일만 쓴다)

배포 뒤 본 잡을 재개하기 전에, 문제 유형별 약 50건으로 소량 잡을 돌려 새 코드를 본다
(round07 spec §5 카나리). 본 잡(kci-full-236k)의 아이템에서 범주별로 고른다.

  scan_no_sections  20  failed · not_found · '섹션 없음' — 텍스트 층에 몇 글자만 남은 스캔본(함정 21번)
  many_tables       10  done · meta.n_tables ≥ 5 — 요약 단계로 옮긴 표 해석
  dense_chunks       5  done · 쪽당 청크 > 6 — <br> 껍데기처럼 잘게 쪼개진 본문 의심
  many_sections      5  done · meta.sections_total > 40 — 계층 요약
  normal            10  done · 위 어디에도 들지 않는 것

한 아이템이 여러 범주에 들면 위 순서에서 앞선 범주로 센다. 범주 안에서는 seed 해시 순으로 고른다 —
id 순 앞부분은 표본이 아니고(docs/ops/recurring-gotchas.md 11번), 같은 seed 면 다시 돌려도 같은
50건이 나온다. 후보는 SQL 이 범주마다 같은 해시 순으로 (몫 × --oversample)건까지만 읽는다.

DB 는 읽기만 하고(READ ONLY 트랜잭션, 문장마다 15분 상한 SET LOCAL statement_timeout) 매니페스트는 로컬
파일로만 쓴다. 상한을 두는 까닭: 질의가 오래 도는 동안 fastapi 가 재생성되면 lifespan 의 ALTER 가 배타
잠금을 기다리며 적재의 접근이 줄을 선다(docs/ops/recurring-gotchas.md 18번). MinIO 업로드·잡 생성·시작은
하지 않고 명령만 출력한다 — 운영에 쓰는 일은 사람이 한다(docs/ops/bulk_ingest_runbook.md §9).

매니페스트 형식: build_manifest.py 와 같은 JSONL, 한 줄 = 한 문서. 잡 생성(job_manager.build_job_plan)은
book_id·object_key 만 읽는다. object_key 는 본 잡 아이템의 source_key(본 잡을 만들 때 MinIO 에 있음을
확인한 키)를 그대로 쓴다. category·item_id(본 잡 아이템 id)는 사람이 보는 기록이다.

실행 (서버 — scripts/ 는 앱 이미지에 없어 데이터 바인드 마운트로 넣는다. 함정 4번):
  mkdir -p /data/nl-lib/data/round07
  cp build_canary_manifest.py /data/nl-lib/data/round07/
  docker exec -e PYTHONPATH=/app nl-lib-fastapi \
    python /app/data/round07/build_canary_manifest.py \
      --job 1ca22f59-1e50-4dd1-81f5-2d3c79126825 --out /app/data/round07/canary
"""
import argparse
import hashlib
import json
from pathlib import Path

# 범주와 몫 — 순서가 우선순위다
QUOTAS = {
    "scan_no_sections": 20,
    "many_tables": 10,
    "dense_chunks": 5,
    "many_sections": 5,
    "normal": 10,
}
DEFAULT_SEED = "round07"
MANIFEST_NAME = "manifest.jsonl"
NO_SECTIONS_PREFIX = "섹션 없음"   # stages.run_summarize 의 StageError("not_found", "섹션 없음 — …")
# 읽기 전용 트랜잭션 안에서 문장마다 15분 상한 - 질의가 배타 잠금 요청 뒤에서 오래 버티지 않게 한다(함정 18번)
STATEMENT_TIMEOUT_SQL = "SET LOCAL statement_timeout = '15min'"


def _num(meta: dict, key: str) -> float:
    # SQL 의 _meta_num 처럼 JSON 숫자만 숫자로 본다 — 숫자 문자열·bool 은 0
    value = meta.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def classify(row: dict) -> str | None:
    """아이템 한 줄 → 범주. 어느 범주도 아니면 None."""
    if row["status"] == "failed":
        if row.get("error_group") == "not_found" and (row.get("last_error") or "").startswith(NO_SECTIONS_PREFIX):
            return "scan_no_sections"
        return None
    if row["status"] != "done":
        return None
    meta = row.get("meta") or {}
    pages = _num(meta, "pages")
    if _num(meta, "n_tables") >= 5:
        return "many_tables"
    if pages > 0 and _num(meta, "chunks") / pages > 6:
        return "dense_chunks"
    if _num(meta, "sections_total") > 40:
        return "many_sections"
    return "normal"


def order_key(book_id: str, seed: str) -> str:
    """SQL 의 md5(book_id || :seed) 와 같은 값 — 후보를 자르는 순서와 고르는 순서를 맞춘다."""
    return hashlib.md5(f"{book_id}{seed}".encode("utf-8")).hexdigest()


def pick_canary(rows: list[dict], quotas: dict[str, int] = QUOTAS, seed: str = DEFAULT_SEED) -> list[dict]:
    """범주마다 seed 해시 순으로 몫만큼. 같은 아이템이 후보에 여러 번 와도 한 번만 센다."""
    by_category: dict[str, list[dict]] = {c: [] for c in quotas}
    seen: set[int] = set()
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        category = classify(row)
        if category in by_category:
            by_category[category].append(row)
    picked = []
    for category, n in quotas.items():
        pool = sorted(by_category[category], key=lambda r: (order_key(r["book_id"], seed), r["id"]))
        picked += [{**r, "category": category} for r in pool[:n]]
    return picked


def shortfalls(picked: list[dict], quotas: dict[str, int] = QUOTAS) -> dict[str, int]:
    """몫을 못 채운 범주 → 모자란 수."""
    got = {c: sum(1 for r in picked if r["category"] == c) for c in quotas}
    return {c: quotas[c] - got[c] for c in quotas if got[c] < quotas[c]}


def manifest_rows(picked: list[dict]) -> list[dict]:
    return [
        {"book_id": r["book_id"], "object_key": r["source_key"], "category": r["category"], "item_id": r["id"]}
        for r in picked
    ]


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def next_steps(manifest_path: str, name: str) -> list[str]:
    """사람이 차례로 돌릴 명령 — MinIO 업로드, 잡 생성(dry-run 검증 → ready), 시작."""
    key = f"manifests/{name}/manifest.jsonl"
    body = json.dumps(
        {"name": name, "manifest_key": key, "params": {"reembed": True, "skip_cover": True}},
        separators=(",", ":"),
    )
    upload = (
        "from core.config import get_settings; from services.ingestion.stages import minio_client; "
        f"minio_client().fput_object(get_settings().MINIO_BUCKET, '{key}', '{manifest_path}'); print('uploaded')"
    )
    return [
        f'docker exec -e PYTHONPATH=/app nl-lib-fastapi python -c "{upload}"',
        "docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs "
        f"-H 'Content-Type: application/json' -d '{body}'",
        "docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/<canary_job_id>/start",
    ]


# 범주별 후보 조건 — classify 와 같은 규칙을 SQL 로(우선순위 정리는 classify 가 한다)
def _meta_num(key: str) -> str:
    return f"CASE WHEN jsonb_typeof(meta -> '{key}') = 'number' THEN (meta ->> '{key}')::numeric END"


CATEGORY_FILTERS = {
    "scan_no_sections": "status = 'failed' AND error_group = 'not_found' AND last_error LIKE :pat",
    "many_tables": f"status = 'done' AND {_meta_num('n_tables')} >= 5",
    "dense_chunks": f"status = 'done' AND {_meta_num('pages')} > 0 AND {_meta_num('chunks')} > 6 * {_meta_num('pages')}",
    "many_sections": f"status = 'done' AND {_meta_num('sections_total')} > 40",
    "normal": "status = 'done'",
}


def candidate_sql(category: str) -> str:
    return (
        "SELECT id, book_id, source_key, status, error_group, last_error, meta "
        "FROM ingest_job_items "
        f"WHERE job_id = :job AND {CATEGORY_FILTERS[category]} "
        "ORDER BY md5(book_id || :seed) LIMIT :cap"
    )


def fetch_candidates(job_id: str, seed: str, oversample: int) -> list[dict]:
    from sqlalchemy import text as sa_text

    from db.postgres import SyncSessionLocal

    db = SyncSessionLocal()
    try:
        db.execute(sa_text("SET TRANSACTION READ ONLY"))
        db.execute(sa_text(STATEMENT_TIMEOUT_SQL))   # 같은 트랜잭션이라 아래 범주 질의 다섯 개 모두에 걸린다
        rows: list[dict] = []
        for category, quota in QUOTAS.items():
            params = {"job": job_id, "seed": seed, "cap": quota * oversample}
            if category == "scan_no_sections":
                params["pat"] = NO_SECTIONS_PREFIX + "%"
            rows += [dict(r._mapping) for r in db.execute(sa_text(candidate_sql(category)), params)]
        return rows
    finally:
        db.rollback()
        db.close()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="카나리 잡 매니페스트 (DB 읽기 전용)")
    ap.add_argument("--job", required=True, help="고를 아이템이 있는 잡 id (본 잡)")
    ap.add_argument("--out", required=True, help="manifest.jsonl 을 쓸 디렉터리")
    ap.add_argument("--name", default="round07-canary", help="카나리 잡 이름 = MinIO manifests/<name>/")
    ap.add_argument("--seed", default=DEFAULT_SEED)
    ap.add_argument("--oversample", type=int, default=20, help="범주마다 몫의 몇 배까지 후보를 읽을지")
    args = ap.parse_args(argv)

    picked = pick_canary(fetch_candidates(args.job, args.seed, args.oversample), seed=args.seed)
    path = Path(args.out) / MANIFEST_NAME
    write_manifest(path, manifest_rows(picked))

    print("── 범주별 (몫 / 고른 수) ──")
    for category, quota in QUOTAS.items():
        got = sum(1 for r in picked if r["category"] == category)
        print(f"  {category:<17} {quota:>3} / {got}")
    short = shortfalls(picked)
    if short:
        print(f"  모자람: {short} - --oversample 을 늘려 다시 돌리거나 그대로 쓴다")
    print(f"\n→ {path} ({len(picked)}건)")
    print("\n다음은 사람이 차례로 한다 (이 스크립트는 운영에 쓰지 않는다):")
    for i, cmd in enumerate(next_steps(str(path), args.name), 1):
        print(f"  {i}) {cmd}")


if __name__ == "__main__":
    main()
