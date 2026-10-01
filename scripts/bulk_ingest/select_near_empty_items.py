r"""select_near_empty_items.py — 본문이 거의 빈 채 완료된 아이템 고르기 (읽기 전용)

배경 (round07, 2026-10-01 진단):
  kci-full-236k 완료분 가운데 8쪽 이상인데 본문이 거의 없는 문서가 있다(가중 추정 약 907건).
  원인은 09-03 02~08 UTC 의 일시 코드(약 458, 이미 고침)·VLM 실패 뒤 ODL 폴백·빈 표 격자·
  부분 본문 등이다. round07 코드로 추출부터 다시 돌릴 대상만 고른다.

기준 — 쪽당 본문 글자 수:
  book_sections.full_text 길이(글자) 합 ÷ meta.pages 가 기준(기본 150자) 미만인 done 아이템.
  청크 수 기준은 쓰지 않는다 — 표 하나짜리 정상 문서(예: 표 2,980토큰이 청크 1개)가 섞인다.
  length() 는 TOAST 된 본문을 풀어야 해서 완료 12만 건에 다 돌리면 본문 전체를 읽는다. 그래서
  풀지 않고 크기를 아는 octet_length()(바이트)로 먼저 거른다. UTF-8 한 글자는 1~4바이트라
  바이트가 쪽당 기준×4 이상이면 글자가 기준 미만일 수 없다.

읽기만 한다: 트랜잭션을 READ ONLY 로 열고 문장마다 15분 상한(SET LOCAL statement_timeout)을 건다. 큰 집계가
도는 동안 fastapi 가 재생성되면 lifespan 의 ALTER 가 배타 잠금을 기다리며 적재의 book_sections 접근이 줄을
서기 때문이다(docs/ops/recurring-gotchas.md 18번). 재처리는 사람이 CSV 를 본 뒤 JSON 으로 retry API 를
부른다(docs/ops/bulk_ingest_runbook.md §9).

실행 (서버 — scripts/ 는 앱 이미지에 없어 데이터 바인드 마운트로 넣는다):
  mkdir -p /data/nl-lib/data/round07
  cp select_near_empty_items.py /data/nl-lib/data/round07/
  docker exec -e PYTHONPATH=/app nl-lib-fastapi \
    python /app/data/round07/select_near_empty_items.py \
      --job 1ca22f59-1e50-4dd1-81f5-2d3c79126825 --out /app/data/round07 \
      --finished-before 2026-10-02T03:00:00+00:00

  --finished-before 에는 round07 배포 시각을 시간대까지 붙여 준다. 배포 뒤 새 코드로 끝난 문서는
  다시 돌려도 결과가 같다.
  PYTHONPATH=/app 이 필요한 이유: 스크립트를 경로로 실행하면 sys.path[0] 이 스크립트 디렉터리로
  잡혀 /app 의 앱 모듈(db.postgres)을 못 찾는다(docs/ops/recurring-gotchas.md 4번).

출력 (--out 아래, 호스트에서는 /data/nl-lib/data/round07/):
  near_empty_items.csv   item_id,book_id,pages,body_chars,chars_per_page,finished_at,
                         extract_method,sections,chunks,vlm_capped — 사람이 본다
  near_empty_retry.json  {"item_ids": [...], "reset_stage": "pending"} — retry API 본문 그대로

  CSV 의 뒤 네 칸은 ingest_job_items.meta 에서 그대로 옮긴 값이다(그 키가 없으면 빈칸). vlm_capped=true 는
  VLM 쪽수 상한(VLM_MAX_PAGES_PER_DOC, 60)에 걸려 일부 쪽이 빠진 문서라 상한이 그대로면 다시 돌려도 결과가
  같다 — 재처리 전에 JSON 의 item_ids 에서 뺄지 사람이 정한다.
"""
import argparse
import csv
import datetime as _dt
import json
from collections import Counter
from pathlib import Path

CSV_NAME = "near_empty_items.csv"
JSON_NAME = "near_empty_retry.json"
BASE_FIELDS = ["item_id", "book_id", "pages", "body_chars", "chars_per_page", "finished_at"]
META_FIELDS = ["extract_method", "sections", "chunks", "vlm_capped"]   # meta 에서 옮긴 사람 검토용 칸
CSV_FIELDS = BASE_FIELDS + META_FIELDS

# 읽기 전용 트랜잭션 안에서 문장마다 15분 상한 - 큰 집계가 배타 잠금 요청 뒤에서 오래 버티지 않게 한다(함정 18번)
STATEMENT_TIMEOUT_SQL = "SET LOCAL statement_timeout = '15min'"

# :before 가 NULL 이면 완료 시각으로 거르지 않는다. 바인드 뒤 `::` 캐스트는 쓰지 않는다(함정 7번).
# meta 칼럼(->> 는 문자열이고 키가 없으면 NULL)은 걸러진 몇 건에만 붙도록 마지막에 기본키로 되붙인다.
CANDIDATES_SQL = """
WITH done AS (
    SELECT id, book_id, finished_at,
           CASE WHEN jsonb_typeof(meta -> 'pages') = 'number'
                THEN (meta ->> 'pages')::numeric END AS pages
    FROM ingest_job_items
    WHERE job_id = :job AND status = 'done'
      AND (CAST(:before AS timestamptz) IS NULL OR finished_at < CAST(:before AS timestamptz))
), sized AS (
    SELECT d.id, d.book_id, d.finished_at, d.pages,
           coalesce(sum(octet_length(s.full_text)), 0) AS body_bytes
    FROM done d
    LEFT JOIN book_sections s ON s.book_id = d.book_id
    WHERE d.pages >= :min_pages
    GROUP BY d.id, d.book_id, d.finished_at, d.pages
)
SELECT z.id AS item_id, z.book_id, z.pages::int AS pages, z.finished_at,
       (SELECT coalesce(sum(length(s.full_text)), 0)
          FROM book_sections s WHERE s.book_id = z.book_id) AS body_chars,
       i.meta ->> 'extract_method' AS extract_method,
       i.meta ->> 'sections' AS sections,
       i.meta ->> 'chunks' AS chunks,
       i.meta ->> 'vlm_capped' AS vlm_capped
FROM sized z
JOIN ingest_job_items i ON i.id = z.id
WHERE z.body_bytes < 4 * :max_cpp * z.pages
"""


def select_near_empty(rows: list[dict], *, min_pages: int, max_chars_per_page: float) -> list[dict]:
    """쪽수 min_pages 이상이고 쪽당 글자 수가 기준 미만인 행 — 쪽당 글자 수 오름차순."""
    picked = []
    for row in rows:
        if row["pages"] < min_pages:
            continue
        cpp = row["body_chars"] / row["pages"]
        if cpp < max_chars_per_page:
            picked.append({**row, "chars_per_page": round(cpp, 1)})
    return sorted(picked, key=lambda r: (r["chars_per_page"], r["item_id"]))


def finished_by_day(rows: list[dict]) -> list[tuple[str, int]]:
    """완료 날짜(UTC)별 건수 — 09-03 일시 코드분처럼 몰린 날을 본다."""
    days = Counter(r["finished_at"].astimezone(_dt.timezone.utc).strftime("%Y-%m-%d") for r in rows)
    return sorted(days.items())


def retry_body(rows: list[dict]) -> dict:
    return {"item_ids": [r["item_id"] for r in rows], "reset_stage": "pending"}


def write_outputs(out_dir: Path, rows: list[dict]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / CSV_NAME
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in rows:
            # meta 칸은 키가 없으면 None - csv 가 빈칸으로 쓴다
            writer.writerow({**{k: r[k] for k in CSV_FIELDS}, "finished_at": r["finished_at"].isoformat()})
    json_path = out_dir / JSON_NAME
    json_path.write_text(json.dumps(retry_body(rows), ensure_ascii=False), encoding="utf-8")
    return csv_path, json_path


def fetch_candidates(job_id: str, *, min_pages: int, max_chars_per_page: float,
                     finished_before: str | None) -> list[dict]:
    from sqlalchemy import text as sa_text

    from db.postgres import SyncSessionLocal

    db = SyncSessionLocal()
    try:
        db.execute(sa_text("SET TRANSACTION READ ONLY"))
        db.execute(sa_text(STATEMENT_TIMEOUT_SQL))
        result = db.execute(sa_text(CANDIDATES_SQL), {
            "job": job_id, "before": finished_before,
            "min_pages": min_pages, "max_cpp": max_chars_per_page,
        })
        return [dict(r._mapping) for r in result]
    finally:
        db.rollback()
        db.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="빈 본문 완료 아이템 선정 (읽기 전용)")
    ap.add_argument("--job", required=True, help="잡 id (ingest_jobs.id)")
    ap.add_argument("--out", required=True, help="CSV·JSON 을 쓸 디렉터리")
    ap.add_argument("--min-pages", type=int, default=8)
    ap.add_argument("--max-chars-per-page", type=float, default=150.0)
    ap.add_argument("--finished-before", default=None,
                    help="이 시각 전에 끝난 것만 (ISO8601, 시간대 필수 - 예: 2026-10-02T03:00:00+00:00)")
    args = ap.parse_args(argv)
    if args.finished_before:
        try:
            when = _dt.datetime.fromisoformat(args.finished_before)
        except ValueError:
            ap.error(f"--finished-before 형식이 틀렸다: {args.finished_before}")
        if when.tzinfo is None:
            ap.error("--finished-before 에 시간대를 붙인다(예: +00:00) - 없으면 DB 세션 시간대로 읽힌다")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    rows = fetch_candidates(
        args.job, min_pages=args.min_pages, max_chars_per_page=args.max_chars_per_page,
        finished_before=args.finished_before,
    )
    picked = select_near_empty(rows, min_pages=args.min_pages, max_chars_per_page=args.max_chars_per_page)
    csv_path, json_path = write_outputs(Path(args.out), picked)

    print(f"── 쪽당 본문 {args.max_chars_per_page:g}자 미만 ({args.min_pages}쪽 이상 done) ──")
    print(f"  후보(크기로 거른 뒤) {len(rows)}건 → 선정 {len(picked)}건")
    print("  완료 날짜(UTC)별:")
    for day, n in finished_by_day(picked):
        print(f"    {day}  {n}")
    print(f"\n→ {csv_path}")
    print(f"→ {json_path}")
    print("\n목록을 본 뒤 재처리(지울 행은 JSON 의 item_ids 에서도 뺀다):")
    print(f"  docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/{args.job}/retry "
          f"-H 'Content-Type: application/json' -d @{json_path}")


if __name__ == "__main__":
    main()
