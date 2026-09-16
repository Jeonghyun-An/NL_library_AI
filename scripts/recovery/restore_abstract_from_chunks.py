"""restore_abstract_from_chunks.py — Milvus 보강 청크에서 abstract·keywords 복원

배경:
  2026-09-14 library_catalog 유실 후 카탈로그 원본 파일로 서지정보는 되살렸지만,
  KCI 카탈로그(metadata.xlsx)에는 초록 컬럼이 없다. 원래 abstract 는 적재 시
  PDF 에서 뽑은 enrichment 결과였고 library_catalog 에만 있었다 — 같이 날아갔다.
  화면은 초록 → 요약 순으로 폴백하는데 둘 다 비어 논문 상세가 빈칸이 됐다.

  다행히 enrichment 는 본문 청크와 별개로 `[초록] …` / `[키워드] …` 청크를
  Milvus 에 남긴다(services/ingestion/stages.py). 그걸 되읽어 채운다.
  LLM 재생성이 아니라 원본 값 복원이라 비용이 없고 내용도 그대로다.

  도서(CNTS-*)는 메타청크(chunk_idx=-1)의 `초록:` 항목에 들어있는 경우가 많다.
  --from-meta 로 그 경로를 쓴다.

주의:
  청크 text 는 적재 시 MAX_CHUNK_BYTES 로 잘렸을 수 있다. 원본보다 짧을 수 있으나
  빈칸보다는 낫다. 이미 abstract 가 있는 행은 건드리지 않는다.

실행 (앱 이미지에 scripts/ 가 없어 호스트 바인드 마운트 /app/data 경유.
      스크립트 파일 실행은 sys.path[0] 이 스크립트 디렉터리라 PYTHONPATH 가 필요하다):
  cp restore_abstract_from_chunks.py /data/nl-lib/data/recovery/
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/restore_abstract_from_chunks.py
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/restore_abstract_from_chunks.py --apply
"""
import json
import re
import sys

from sqlalchemy import text as sa_text

from db.postgres import SyncSessionLocal
from services.ingestion.indexer import ensure_collection

ID_BATCH = 200          # Milvus expr 에 넣을 book_id 개수
ABSTRACT_PREFIX = "[초록] "
KEYWORD_PREFIX = "[키워드] "
_META_ABSTRACT = re.compile(r"(?:^|\s\|\s)초록: (.+)$", re.S)


def find_targets(db, doc_type: str | None, limit: int | None) -> list[str]:
    """abstract 가 비어있는 임베딩 완료 문서."""
    where = ["is_embedded", "abstract IS NULL"]
    params: dict = {}
    if doc_type:
        where.append("doc_type = :dt")
        params["dt"] = doc_type
    sql = f"SELECT cnts_id FROM library_catalog WHERE {' AND '.join(where)} ORDER BY cnts_id"
    if limit:
        sql += " LIMIT :lim"
        params["lim"] = limit
    return [r[0] for r in db.execute(sa_text(sql), params)]


def _ids_expr(ids: list[str]) -> str:
    return ", ".join(f'"{b}"' for b in ids)


def fetch_from_enrichment(col, ids: list[str]) -> dict[str, dict]:
    """`[초록]` / `[키워드]` 보강 청크 조회 → {book_id: {abstract, keywords}}.

    text 접두 매칭을 Milvus 에 맡긴다 — 청크 전량을 끌어오면 수십 MB 가 된다.
    """
    out: dict[str, dict] = {}
    for prefix, key in ((ABSTRACT_PREFIX, "abstract"), (KEYWORD_PREFIX, "keywords")):
        rows = col.query(
            expr=f'book_id in [{_ids_expr(ids)}] && text like "{prefix}%"',
            output_fields=["book_id", "text"],
            limit=len(ids) * 4,
        )
        for r in rows:
            body = (r.get("text") or "")[len(prefix):].strip()
            if body:
                out.setdefault(r["book_id"], {})[key] = body
    return out


def fetch_from_meta(col, ids: list[str]) -> dict[str, dict]:
    """메타청크(chunk_idx=-1)의 `초록:` 항목 → {book_id: {abstract}}."""
    rows = col.query(
        expr=f"book_id in [{_ids_expr(ids)}] && chunk_idx == -1",
        output_fields=["book_id", "text"],
        limit=len(ids),
    )
    out: dict[str, dict] = {}
    for r in rows:
        m = _META_ABSTRACT.search(r.get("text") or "")
        if m and m.group(1).strip():
            out[r["book_id"]] = {"abstract": m.group(1).strip()}
    return out


def apply_batch(db, found: dict[str, dict]) -> int:
    """abstract 는 컬럼에, keywords 는 extra JSONB 에 병합. 기존 값은 덮지 않는다.

    `:ext::jsonb` 가 아니라 `CAST(:ext AS jsonb)` 를 쓴다 — SQLAlchemy text() 는
    바인드 파라미터 뒤에 PostgreSQL 캐스트 `::` 가 붙으면 그 파라미터를 바인딩하지
    못하고 SQL 에 그대로 흘려보낸다.
    """
    n = 0
    for bid, vals in found.items():
        abstract = vals.get("abstract")
        if not abstract:
            continue
        kw = [k.strip() for k in (vals.get("keywords") or "").split(",") if k.strip()]
        res = db.execute(sa_text(
            "UPDATE library_catalog "
            "SET abstract = :abs, "
            "    extra = coalesce(extra, '{}'::jsonb) || CAST(:ext AS jsonb), "
            "    updated_at = now() "
            "WHERE cnts_id = :id AND abstract IS NULL"
        ), {"abs": abstract, "ext": json.dumps({"keywords": kw} if kw else {}), "id": bid})
        n += res.rowcount or 0
    db.commit()
    return n


def main() -> int:
    apply = "--apply" in sys.argv
    from_meta = "--from-meta" in sys.argv
    doc_type = None
    if "--doc-type" in sys.argv:
        doc_type = sys.argv[sys.argv.index("--doc-type") + 1]
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    col = ensure_collection()
    db = SyncSessionLocal()
    try:
        targets = find_targets(db, doc_type, limit)
        source = "메타청크" if from_meta else "보강청크([초록]/[키워드])"
        print(f"abstract 없는 임베딩 문서: {len(targets):,}건  (소스: {source})")
        if not targets:
            return 0

        matched = updated = 0
        sample = None
        for i in range(0, len(targets), ID_BATCH):
            batch = targets[i:i + ID_BATCH]
            found = fetch_from_meta(col, batch) if from_meta else fetch_from_enrichment(col, batch)
            found = {b: v for b, v in found.items() if v.get("abstract")}
            matched += len(found)
            if sample is None and found:
                bid = next(iter(found))
                sample = (bid, found[bid]["abstract"][:120])
            if apply and found:
                updated += apply_batch(db, found)
            if (i // ID_BATCH) % 25 == 0:
                print(f"  …{min(i + ID_BATCH, len(targets)):,}/{len(targets):,} 처리, 매칭 {matched:,}")

        print(f"\n초록 확보: {matched:,}건 / 미확보: {len(targets) - matched:,}건")
        if sample:
            print(f"샘플 {sample[0]}: {sample[1]}…")
        if apply:
            print(f"갱신 완료: {updated:,}건")
        else:
            print("dry-run — 아무것도 쓰지 않았다. 반영하려면 --apply")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
