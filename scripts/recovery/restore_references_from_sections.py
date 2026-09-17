"""restore_references_from_sections.py — 섹션 원문에서 참고문헌 재추출

배경:
  2026-09-14 library_catalog 유실로 extra["references"] 가 날아갔다. 같은 enrichment
  산출물인 키워드는 Milvus 에 `[키워드] …` 청크로 사본이 남아 복원했지만, 참고문헌은
  청크로 만들어지지 않아(enrichment 청크는 초록·키워드·표·그림뿐) 복원 소스가 없었다.

  다만 paper_enricher.extract_references() 는 LLM 이 아니라 패턴 기반이고, 입력인
  본문은 book_sections 에 그대로 살아있다. 섹션을 이어붙여 재구성하면 적재 당시와
  같은 규칙으로 다시 뽑을 수 있다 — Milvus·OCR·LLM 없이 Postgres 안에서 끝난다.

  LLM 폴백(generate_references)은 쓰지 않는다. 대량 복원에서 수만 건의 LLM 호출을
  유발하고, 패턴 추출이 실패한 문서는 애초에 참고문헌 섹션이 없거나 형식이 깨진
  경우라 폴백의 기대값도 낮다.

실행:
  cp restore_references_from_sections.py /data/nl-lib/data/recovery/
  docker exec -e PYTHONPATH=/app nl-lib-fastapi \
    python /app/data/recovery/restore_references_from_sections.py --limit 200
  docker exec -e PYTHONPATH=/app nl-lib-fastapi \
    python /app/data/recovery/restore_references_from_sections.py --apply

  PYTHONPATH=/app 이 필요한 이유: 스크립트를 경로로 실행하면 sys.path[0] 이 스크립트
  디렉터리로 잡혀 /app 의 앱 모듈을 못 찾는다.
"""
import json
import sys
from typing import TYPE_CHECKING

from sqlalchemy import text as sa_text

from db.postgres import SyncSessionLocal
from models.section import BookSection
from services.ingestion.paper_enricher import extract_references

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

COMMIT_EVERY = 200


def _arg_value(flag: str) -> str | None:
    if flag not in sys.argv:
        return None
    idx = sys.argv.index(flag)
    if idx + 1 >= len(sys.argv):
        print(f"{flag} <값> 형태로 지정한다")
        sys.exit(2)
    return sys.argv[idx + 1]


def find_targets(db: "Session", doc_type: str | None, limit: int | None) -> list[str]:
    """참고문헌이 비어있는 임베딩 완료 문서."""
    where = ["is_embedded", "NOT (coalesce(extra, '{}'::jsonb) ? 'references')"]
    params: dict = {}
    if doc_type:
        where.append("doc_type = :dt")
        params["dt"] = doc_type
    sql = f"SELECT cnts_id FROM library_catalog WHERE {' AND '.join(where)} ORDER BY cnts_id"
    if limit:
        sql += " LIMIT :lim"
        params["lim"] = limit
    return [r[0] for r in db.execute(sa_text(sql), params)]


def rebuild_full_text(db: "Session", book_id: str) -> str:
    """섹션을 순서대로 이어붙여 적재 당시 본문을 재구성한다.

    구분자가 "\n\n" 인 것은 load_extraction_artifact 가 페이지를 그렇게 이었기
    때문이다. 참고문헌은 문서 끝에 있고 extract_references 가 헤더의 마지막 매칭을
    쓰므로, 경계가 정확히 일치하지 않아도 추출 결과는 같다.
    """
    rows = (
        db.query(BookSection.full_text)
        .filter_by(book_id=book_id)
        .order_by(BookSection.section_idx)
        .all()
    )
    return "\n\n".join(r[0] for r in rows if r[0])


def main() -> int:
    apply = "--apply" in sys.argv
    doc_type = _arg_value("--doc-type") or "paper"
    limit_raw = _arg_value("--limit")
    limit = int(limit_raw) if limit_raw else None

    db = SyncSessionLocal()
    try:
        targets = find_targets(db, doc_type, limit)
        print(f"참고문헌 없는 문서: {len(targets):,}건 (doc_type={doc_type})")
        if not targets:
            return 0

        found = updated = empty = 0
        sample = None
        for n, book_id in enumerate(targets, 1):
            full_text = rebuild_full_text(db, book_id)
            if not full_text.strip():
                empty += 1
                continue

            refs = extract_references(full_text)
            if not refs:
                continue
            found += 1
            if sample is None:
                sample = (book_id, len(refs), refs[0][:90])

            if apply:
                updated += db.execute(sa_text(
                    "UPDATE library_catalog "
                    "SET extra = coalesce(extra, '{}'::jsonb) || CAST(:ext AS jsonb), "
                    "    updated_at = now() "
                    "WHERE cnts_id = :id "
                    "  AND NOT (coalesce(extra, '{}'::jsonb) ? 'references')"
                ), {"ext": json.dumps({"references": refs}), "id": book_id}).rowcount or 0
                if n % COMMIT_EVERY == 0:
                    db.commit()

            if n % 500 == 0:
                print(f"  …{n:,}/{len(targets):,} 처리, 추출 {found:,}")

        if apply:
            db.commit()

        print(f"\n참고문헌 추출: {found:,}건 / 미검출: {len(targets) - found - empty:,}건 "
              f"/ 본문 없음: {empty:,}건")
        if sample:
            print(f"샘플 {sample[0]}: {sample[1]}건 — {sample[2]}…")
        print(f"갱신: {updated:,}건" if apply else "dry-run — 반영하려면 --apply")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
