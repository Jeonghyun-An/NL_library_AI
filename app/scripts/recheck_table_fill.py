"""recheck_table_fill.py — 재배포 이전에 처리된 문서를 새 라우팅 규칙으로 재검사.

배경
----
표 셀 충전율 기반 라우팅(7cdf27b)이 들어가기 전에 처리된 문서는, 빈 표 격자가
글자 수만 채워 '본문 충분'으로 오판된 페이지를 그대로 색인했을 수 있다.
이 스크립트는 그런 페이지를 가진 문서를 골라낸다. **VLM 을 호출하지 않는다.**
ODL 을 JSON 형식으로만 다시 돌려 셀 충전율만 계산하므로 비용이 낮다.

읽기 전용이다. DB·색인·MinIO 에 아무것도 쓰지 않는다.

주의
----
운영 인덱싱이 돌고 있으면 CPU 를 나눠 쓰게 된다. 기본값은 순차 1개이고,
--sleep 으로 문서 사이 간격을 줄 수 있다. 먼저 --limit 로 표본을 돌려
영향 비율을 추정한 뒤 전수로 넓히는 것을 권한다.

사용법
------
    docker exec -w /app nl-lib-fastapi python -m scripts.recheck_table_fill \
        --before "2026-08-24 00:00:00" --limit 300 --out /app/data/recheck.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from pathlib import Path

from sqlalchemy import text

from core.config import get_settings
from db.postgres import AsyncSessionLocal

cfg = get_settings()

FILL_THRESHOLD = 0.30          # extractor.py 의 판정 임계값과 동일하게 유지


def _minio_client():
    from minio import Minio

    return Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )


def page_fill_ratios(pdf_path: str) -> dict[int, float]:
    """ODL 을 JSON 으로만 실행해 페이지별 표 셀 충전율을 낸다.

    extractor.py 와 같은 방식(셀 수 가중 합산)으로 계산한다. 이미지는 뽑지 않아
    (image_output="off") 운영 추출보다 가볍다.
    """
    import opendataloader_pdf

    out_dir = tempfile.mkdtemp()
    opendataloader_pdf.convert(
        input_path=pdf_path,
        output_dir=out_dir,
        format=["json"],
        image_output="off",
        table_method="cluster",
        keep_line_breaks=False,
        quiet=True,
    )
    files = list(Path(out_dir).glob("*.json"))
    if not files:
        return {}
    with open(files[0], encoding="utf-8") as f:
        data = json.load(f)

    per_page: dict[int, list[tuple[int, int]]] = {}
    for el in data.get("kids", []):
        if el.get("type") != "table":
            continue
        pnum = el.get("page number", 1)
        total = filled = 0
        for row in el.get("rows", []):
            for cell in row.get("cells", []):
                total += 1
                if cell.get("kids"):
                    filled += 1
        if total:
            per_page.setdefault(pnum, []).append((total, filled))

    ratios = {}
    for pnum, tabs in per_page.items():
        tot = sum(t for t, _ in tabs)
        fil = sum(f for _, f in tabs)
        ratios[pnum] = fil / tot
    return ratios


async def fetch_items(before: str | None, limit: int | None) -> list[dict]:
    """재배포 이전에 완료된 항목을 읽는다(읽기 전용)."""
    sql = """
        SELECT book_id, source_key, updated_at
        FROM ingest_job_items
        WHERE status = 'done' AND source_key IS NOT NULL
    """
    params: dict = {}
    if before:
        sql += " AND updated_at < :before"
        params["before"] = before
    sql += " ORDER BY updated_at"
    if limit:
        sql += " LIMIT :limit"
        params["limit"] = limit
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", help="이 시각 이전에 완료된 항목만 (재배포 시각)")
    ap.add_argument("--limit", type=int, help="표본 수 (미지정이면 전수)")
    ap.add_argument("--sleep", type=float, default=0.0, help="문서 사이 대기 초")
    ap.add_argument("--out", default="/app/data/recheck_table_fill.json")
    args = ap.parse_args()

    items = await fetch_items(args.before, args.limit)
    print(f"대상 {len(items)}건", flush=True)

    done: dict = {}
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            done = json.load(f)

    client = _minio_client()
    for i, it in enumerate(items, 1):
        bid = it["book_id"]
        if bid in done:
            continue
        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
            client.fget_object(cfg.MINIO_BUCKET, it["source_key"], tmp)
            ratios = page_fill_ratios(tmp)
            low = {p: round(r, 3) for p, r in ratios.items() if r < FILL_THRESHOLD}
            done[bid] = {"pages_with_tables": len(ratios), "low_fill_pages": low}
            mark = f"  ← 재추출 후보 {len(low)}쪽" if low else ""
            print(f"[{i}/{len(items)}] {bid} 표 {len(ratios)}쪽{mark}", flush=True)
        except Exception as e:
            done[bid] = {"error": str(e)[:200]}
            print(f"[{i}/{len(items)}] {bid} 실패: {e}", flush=True)
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(done, f, ensure_ascii=False)
        if args.sleep:
            await asyncio.sleep(args.sleep)

    ok = [v for v in done.values() if "error" not in v]
    hit = [v for v in ok if v["low_fill_pages"]]
    print(f"\n완료 {len(ok)}건 (실패 {len(done)-len(ok)}건)")
    print(f"재추출 후보 문서 {len(hit)}건 ({len(hit)/len(ok)*100:.1f}%)" if ok else "")
    print(f"후보 페이지 합계 {sum(len(v['low_fill_pages']) for v in hit)}쪽")
    print(f"저장: {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
