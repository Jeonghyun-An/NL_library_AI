"""restore_from_milvus_meta.py — Milvus 메타청크 역복원 (카탈로그 원본이 없는 잔여 고아용)

배경:
  2026-09-14 library_catalog 유실분 중 대부분은 원본 카탈로그 파일(metadata.xlsx,
  marc_mods*.xlsx) 재적재로 복구했지만, 원본 파일에 없는 소수가 남는다
  (위키문헌 WS_*, 공유마당 GM_*, 그 외 개별 누락 건).
  이들은 Milvus 메타청크(chunk_idx = -1)에 제목·저자·키워드·초록이 남아있어 역복원이 가능하다.

복원 범위 — 메타청크에 들어간 9개 필드뿐이다(services/ingestion/stages.py 의 meta_parts):
  제목 · 기관 · 저자 · 출판사 · 발행년도 · KDC분류 · 주제 · 키워드 · 초록
  ISBN·DDC·extent 등 MARC/MODS 전용 필드와 LLM 생성물(summary/introduction 등)은 못 살린다.
  복원된 행은 extra.restored_from 으로 표시해 둔다 — 메타데이터가 부분적임을 뒤에서 알 수 있게.

파싱 주의:
  구분자가 " | " 인데 값 안에도 " | " 가 들어간다(실측: `저자: 柳在元 | 林慧俊`).
  단순 split 하면 저자가 깨지므로 "알려진 라벨 + ': '" 경계로만 자른다.

doc_type:
  Milvus 스칼라의 doc_type 은 신뢰하지 않는다 — WS_*/GM_* 문학 작품이 'paper' 로
  잘못 박혀 있어 논문 검색을 오염시키는 기존 버그가 있다. ID 접두어로 판정하고,
  모르는 접두어만 Milvus 값으로 폴백한다.
  (Postgres 를 먼저 바로잡아 두면, 나중에 해당 문서를 재인덱싱할 때 올바른 값이 Milvus 로 전파된다.)

실행:
  mkdir -p /data/nl-lib/data/recovery && cp restore_from_milvus_meta.py /data/nl-lib/data/recovery/
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/restore_from_milvus_meta.py
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/restore_from_milvus_meta.py --apply
"""
import re
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from domains.base import ParsedRecord, split_core_extra
from db.postgres import SyncSessionLocal
from repositories.catalog_bulk import upsert_catalog_records
from services.ingestion.indexer import ensure_collection

LABEL_FIELD = {
    "제목":     "title",
    "기관":     "corporate_author",
    "저자":     "personal_author",
    "출판사":   "publisher",
    "발행년도": "pub_date",
    "KDC분류":  "kdc",
    "주제":     "subject",
    "키워드":   "keyword",
    "초록":     "abstract",
}
_BOUNDARY = re.compile(r"(?:^|\s\|\s)(" + "|".join(map(re.escape, LABEL_FIELD)) + r"): ")

# 적재 당시 "값 없음"을 문자열로 박아둔 것들 — 컬럼에 그대로 넣으면 노이즈가 된다
PLACEHOLDERS = {"unknown", "unkn", "알 수 없음", "알 수", "미상", "n/a", "na", "-", "none"}

# ID 접두어 → doc_type (Milvus 스칼라보다 우선)
PREFIX_DOC_TYPE = [
    ("WS_",            "literature"),   # 위키문헌
    ("GM_",            "literature"),   # 공유마당
    ("LIT-GUTENBERG",  "literature"),
    ("KCI_FI",         "paper"),
    ("CNTS-",          "book"),
]


def parse_meta(meta_text: str) -> dict:
    """메타청크 텍스트 → {컬럼명: 값}. 값 안의 ' | ' 를 깨지 않는다."""
    out: dict = {}
    marks = list(_BOUNDARY.finditer(meta_text))
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(meta_text)
        val = meta_text[start:end].strip()
        if val and val.lower() not in PLACEHOLDERS:
            out[LABEL_FIELD[m.group(1)]] = val
    return out


def doc_type_for(book_id: str, milvus_doc_type: str | None) -> str | None:
    for prefix, dt in PREFIX_DOC_TYPE:
        if book_id.startswith(prefix):
            return dt
    return milvus_doc_type or None


def find_orphans(db) -> list[str]:
    """book_sections 에는 있는데 library_catalog 에 없는 book_id."""
    rows = db.execute(text(
        "SELECT d.book_id FROM (SELECT DISTINCT book_id FROM book_sections) d "
        "WHERE NOT EXISTS (SELECT 1 FROM library_catalog c WHERE c.cnts_id = d.book_id) "
        "ORDER BY d.book_id"
    ))
    return [r[0] for r in rows]


def fetch_meta(col, book_ids: list[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for i in range(0, len(book_ids), 100):
        chunk = book_ids[i:i + 100]
        ids_expr = ", ".join(f'"{b}"' for b in chunk)
        rows = col.query(
            expr=f"book_id in [{ids_expr}] && chunk_idx == -1",
            output_fields=["book_id", "doc_type", "text"],
            limit=len(chunk),
        )
        for r in rows:
            found[r["book_id"]] = r
    return found


def build_records(orphans: list[str], metas: dict[str, dict], stamp: str):
    for bid in orphans:
        meta = metas.get(bid)
        if not meta:
            continue
        fields = parse_meta(meta.get("text") or "")
        if not fields.get("title"):
            continue  # 제목조차 못 건지면 넣을 가치가 없다
        dt = doc_type_for(bid, meta.get("doc_type"))
        if dt:
            fields["doc_type"] = dt
        core, extra = split_core_extra(fields)
        core["cnts_id"] = bid
        extra["restored_from"] = "milvus_meta_chunk"
        extra["restored_at"] = stamp
        yield ParsedRecord(source_id=bid, core=core, extra=extra)


def main() -> None:
    apply = "--apply" in sys.argv
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    db = SyncSessionLocal()
    try:
        orphans = find_orphans(db)
        print(f"카탈로그 없는 고아: {len(orphans)}건")
        if not orphans:
            return

        metas = fetch_meta(ensure_collection(), orphans)
        print(f"Milvus 메타청크 확보: {len(metas)}건 / 없음: {len(orphans) - len(metas)}건")

        records = list(build_records(orphans, metas, stamp))
        print(f"복원 가능(제목 확보): {len(records)}건\n")

        for rec in records:
            c = rec.core
            print(f"  {rec.source_id:22} [{c.get('doc_type','?'):10}] {c.get('title','')[:38]:40} / {c.get('personal_author') or '-'}")

        skipped = [b for b in orphans if b not in {r.source_id for r in records}]
        if skipped:
            print(f"\n  건너뜀({len(skipped)}건 — 메타청크 없거나 제목 없음): {', '.join(skipped)}")

        if not apply:
            print("\ndry-run — 아무것도 쓰지 않았다. 반영하려면 --apply")
            return

        result = upsert_catalog_records(db, iter(records))
        print(f"\n적재 완료: 신규 {result['created']} / 갱신 {result['updated']} / 총 {result['total']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
