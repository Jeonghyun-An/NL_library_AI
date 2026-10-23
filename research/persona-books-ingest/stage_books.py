"""페르소나 책 17권 — 서버에서 카탈로그 등록·원문 올리기·적재 목록 만들기 (1회성, 2026-10-23).

nl-lib-fastapi 컨테이너 안에서 돈다(앱 설정으로 DB·MinIO 에 붙는다). 같은 폴더의 books.json·pdf/<id>.pdf 를 읽는다.

    docker exec -w /app -e PYTHONPATH=/app nl-lib-fastapi python /app/data/persona_books/stage_books.py          # 미리 보기
    docker exec -w /app -e PYTHONPATH=/app nl-lib-fastapi python /app/data/persona_books/stage_books.py --apply  # 실행

기존 자료를 건드리지 않는 것이 첫째다(2026-09-14 카탈로그 전멸 사고 — 적재 전 '정리'가 추정 원인).
- 카탈로그: 새 ID 만 넣는다. INSERT … ON CONFLICT DO NOTHING 이라 같은 ID 가 있으면 넣지 않고(덮어쓰지 않는다 —
  repositories.catalog_bulk.upsert_catalog_records 는 같은 ID 의 제목·doc_type 을 덮어써서 쓰지 않는다), 이번 묶음이
  넣은 행이 아닌데 ID 가 이미 있으면 아무것도 하지 않고 멈춘다. DELETE·UPDATE 는 하지 않는다.
- MinIO: originals/<id>/<id>.pdf 가 없을 때만 올린다. 같은 크기로 이미 있으면 건너뛰고, 크기가 다르면 멈춘다.
- 적재 목록: manifests/persona-books-20261023/{canary,main}.jsonl — 카나리 2권(한국어·영어 txt 렌더본)과 나머지 15권.
적재 작업은 이 스크립트가 만들지 않는다 — 끝에 찍는 명령으로 카나리부터 사람이 만든다.
"""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

from minio.error import S3Error
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.book import Book
from services.ingestion.stages import minio_client

HERE = Path(__file__).resolve().parent
BATCH = "persona-books-20261023"
MANIFEST_DIR = f"manifests/{BATCH}"
CANARY = ["PSN-SONAGI", "PSN-RED-CAP"]
SOURCE_FORMAT = {"txt": "PD_TEXT", "pdf": "PD_PDF"}
CORE = ("title", "title_remainder", "pub_date", "publisher", "kdc", "subject", "keyword", "abstract", "url", "doc_type")


def row_of(book: dict, pdf: Path) -> dict:
    row = {k: (book.get(k) or None) for k in CORE}
    row.update(
        cnts_id=book["id"], personal_author=book["author"], language=book.get("lang", "kor"),
        source_format=SOURCE_FORMAT[book["kind"]],
        extra={"acquisition": {
            "batch": BATCH, "source": "페르소나 에이전트 원문 보관본(20261020_책원문_보관본·카카오톡 받은 PDF)",
            "source_file": book["src"], "rendered": book["kind"] == "txt",
            "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()}},
    )
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="카탈로그 등록·원문 올리기·적재 목록 쓰기를 실제로 한다")
    args = ap.parse_args()
    cfg = get_settings()
    books = json.loads((HERE / "books.json").read_text(encoding="utf-8"))["books"]
    ids = [b["id"] for b in books]
    assert len(ids) == len(set(ids)) == 17, "ID 가 17개이고 겹치지 않아야 한다"
    pdfs = {b["id"]: HERE / "pdf" / f"{b['id']}.pdf" for b in books}
    missing = [i for i, p in pdfs.items() if not p.exists()]
    if missing:
        sys.exit(f"PDF 가 없다: {missing}")

    db = SyncSessionLocal()
    client = minio_client()
    try:
        tbl = Book.__table__
        found = db.execute(select(tbl.c.cnts_id, tbl.c.title, tbl.c.extra, tbl.c.is_embedded)
                           .where(tbl.c.cnts_id.in_(ids))).all()
        ours = {r.cnts_id for r in found if ((r.extra or {}).get("acquisition") or {}).get("batch") == BATCH}
        foreign = [(r.cnts_id, r.title) for r in found if r.cnts_id not in ours]
        if foreign:
            sys.exit(f"멈춤 — 이번 묶음이 아닌 카탈로그 행이 같은 ID 로 이미 있다(건드리지 않는다): {foreign}")

        keys, upload, conflict = {}, [], []
        for i, p in pdfs.items():
            key = f"originals/{i}/{i}.pdf"
            keys[i] = key
            try:
                st = client.stat_object(cfg.MINIO_BUCKET, key)
            except S3Error as e:            # 없을 때만 올린다 — 연결 오류 같은 다른 실패는 그대로 멈춘다
                if e.code not in ("NoSuchKey", "NoSuchObject"):
                    raise
                upload.append(i)
                continue
            if st.size != p.stat().st_size:
                conflict.append((key, st.size, p.stat().st_size))
        if conflict:
            sys.exit(f"멈춤 — MinIO 에 크기가 다른 같은 키가 있다(덮어쓰지 않는다): {conflict}")

        to_insert = [b for b in books if b["id"] not in ours]
        print(f"카탈로그: 새로 넣을 행 {len(to_insert)} · 이번 묶음이 이미 넣은 행 {len(ours)} · 같은 ID 의 다른 행 0")
        print(f"MinIO: 올릴 PDF {len(upload)} · 이미 있는 PDF {17 - len(upload)}")
        for b in books:
            print(f"  {b['id']:22} {b['doc_type']:10} {b['kdc']:6} {b['title']} / {b['author']} "
                  f"({pdfs[b['id']].stat().st_size // 1024}KB)")
        if not args.apply:
            print("\n미리 보기만 했다. 실제로 하려면 --apply")
            return

        if to_insert:
            stmt = (pg_insert(tbl).values([row_of(b, pdfs[b["id"]]) for b in to_insert])
                    .on_conflict_do_nothing(index_elements=["cnts_id"]).returning(tbl.c.cnts_id))
            inserted = [r[0] for r in db.execute(stmt)]
            db.commit()
            print(f"카탈로그 등록 {len(inserted)}행")
            if len(inserted) != len(to_insert):
                sys.exit(f"멈춤 — 넣으려던 {len(to_insert)}행 중 {len(inserted)}행만 들어갔다(다른 곳에서 같은 ID 를 넣었나?)")
        for i in upload:
            client.fput_object(cfg.MINIO_BUCKET, keys[i], str(pdfs[i]), content_type="application/pdf")
            print(f"올림 {keys[i]}")

        def manifest(name: str, sel: list[str]) -> str:
            lines = [json.dumps({"book_id": i, "object_key": keys[i], "size": pdfs[i].stat().st_size,
                                 "title": next(b["title"] for b in books if b["id"] == i)}, ensure_ascii=False)
                     for i in sel]
            data = ("\n".join(lines) + "\n").encode("utf-8")
            key = f"{MANIFEST_DIR}/{name}.jsonl"
            client.put_object(cfg.MINIO_BUCKET, key, io.BytesIO(data), len(data), content_type="application/x-ndjson")
            return key

        canary_key = manifest("canary", CANARY)
        main_key = manifest("main", [i for i in ids if i not in CANARY])
        print(f"\n적재 목록: {canary_key} ({len(CANARY)}권) · {main_key} ({17 - len(CANARY)}권)")
        print("다음 — 카나리 작업 만들기(params 에 doc_type·reembed 를 넣지 않는다 — 카탈로그 행의 doc_type 을 쓴다):")
        print("  docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs "
              "-H 'Content-Type: application/json' "
              f"-d '{{\"name\":\"{BATCH}-canary\",\"manifest_key\":\"{canary_key}\",\"params\":{{\"skip_cover\":true}}}}'")
    finally:
        db.close()


if __name__ == "__main__":
    main()
