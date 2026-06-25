"""
catalog_bulk.py — ParsedRecord 스트림의 카탈로그 bulk upsert

행단위 SELECT+UPDATE (30만회 왕복) 대신 PostgreSQL INSERT ... ON CONFLICT 로
1,000행 단위 배치 처리. 기존 행단위 적재의 의미 보존:
  - 파싱된 non-None 값만 덮어쓰기 (COALESCE(excluded.col, 기존값))
  - 수집 관련 필드(is_embedded, summary, ingest_* 등)는 건드리지 않음
  - 전환기 dual-write: extra 키가 Book 컬럼에 있으면 컬럼에도, extra JSONB에는 항상 병합
"""
import logging
from typing import Iterable

from sqlalchemy import func, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domains.base import ParsedRecord
from models.book import Book

log = logging.getLogger(__name__)

# upsert 시 절대 덮어쓰지 않는 컬럼 (RAG 생성물 + 인덱싱 상태 + 시스템)
PROTECTED_ON_UPDATE = {
    "id", "cnts_id",
    "is_embedded", "summary", "themes", "introduction",
    "cover_image_key", "cover_prompt", "milvus_id", "raw_text",
    "ingest_state", "ingest_task_id", "ingest_source_key",
    "ingest_started_at", "ingest_finished_at", "ingest_error",
    "created_at", "updated_at",
}

from core.config import get_settings

DEFAULT_BATCH_SIZE = get_settings().CATALOG_BULK_BATCH_SIZE

_TBL = Book.__table__
_BOOK_COLUMNS: frozenset[str] = frozenset(c.key for c in _TBL.columns)


def _record_to_row(rec: ParsedRecord) -> dict:
    row = dict(rec.core)
    row["cnts_id"] = rec.source_id
    if rec.source_format and "source_format" not in row:
        row["source_format"] = rec.source_format
    # 전환기 dual-write: Book 실제 컬럼에 있으면 컬럼에도 기록
    for k, v in rec.extra.items():
        if k in _BOOK_COLUMNS and k not in row:
            row[k] = v
    row.setdefault("title", rec.source_id)  # title NOT NULL 보호
    row["extra"] = rec.extra
    return row


def upsert_catalog_records(
    db,
    records: Iterable[ParsedRecord],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    """ParsedRecord 스트림을 배치 upsert. returns {"created", "updated", "total"}."""
    created = updated = total = 0
    batch: list[dict] = []

    def _flush(rows: list[dict]) -> tuple[int, int]:
        if not rows:
            return 0, 0

        # 배치 내 cnts_id 중복 제거 (나중 행 우선)
        seen: dict[str, dict] = {}
        for r in rows:
            key = r.get("cnts_id")
            if key:
                seen[key] = r
        rows = list(seen.values())

        # 배치 내 키 합집합 → 균일한 dict + 실제 컬럼만 추림
        all_keys: set[str] = set()
        for r in rows:
            all_keys.update(r.keys())
        col_keys = all_keys & _BOOK_COLUMNS      # 실제 DB 컬럼만
        uniform = [{k: r.get(k) for k in col_keys} for r in rows]

        # Core INSERT (ORM 매퍼 대신 Table 객체로 — returning/on_conflict 호환)
        stmt = pg_insert(_TBL).values(uniform)

        # ON CONFLICT DO UPDATE
        update_set: dict = {}
        for k in col_keys:
            if k in PROTECTED_ON_UPDATE or k == "extra":
                continue
            # 파싱된 non-None 값만 덮어쓰기
            update_set[k] = func.coalesce(stmt.excluded[k], _TBL.c[k])

        # JSONB 병합: 기존 extra에 새 extra 덮어씌우기 (NULL-safe)
        update_set["extra"] = func.coalesce(
            _TBL.c["extra"], literal_column("'{}'::jsonb")
        ).op("||")(stmt.excluded["extra"])
        update_set["updated_at"] = func.now()

        stmt = stmt.on_conflict_do_update(
            index_elements=["cnts_id"],
            set_=update_set,
        ).returning(literal_column("(xmax = 0) AS inserted"))

        result = db.execute(stmt)
        flags = [r[0] for r in result]
        db.commit()
        n_created = sum(1 for f in flags if f)
        return n_created, len(flags) - n_created

    try:
        for rec in records:
            if not rec.source_id:
                continue
            batch.append(_record_to_row(rec))
            total += 1
            if len(batch) >= batch_size:
                c, u = _flush(batch)
                created += c
                updated += u
                batch = []
        c, u = _flush(batch)
        created += c
        updated += u
    except Exception:
        db.rollback()
        raise

    log.info(f"카탈로그 bulk upsert 완료: 신규 {created}, 갱신 {updated} / 총 {total}")
    return {"created": created, "updated": updated, "total": total}
