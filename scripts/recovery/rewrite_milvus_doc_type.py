"""rewrite_milvus_doc_type.py — Milvus doc_type 스칼라 재기록 (문학 41편 오분류 교정)

배경:
  위키문헌(WS_*)·공유마당(GM_*) 문학 작품 41편이 카탈로그 적재 없이 바로
  인덱싱되면서 doc_type='paper' 로 잘못 박혔다. 논문 검색은 book_id 접두어
  안전망 덕에 영향이 적지만, 도서 검색은 doc_type 만 보므로 이 41편이
  도서 검색에서 완전히 실종된다.

왜 문서 단위 재기록인가:
  Milvus 는 부분 update 가 없다 — 필드 하나를 고치려면 해당 문서의 모든 청크를
  delete 후 insert 해야 한다. 트랜잭션도 없으므로 여러 문서를 묶어봐야 원자성
  이득이 없고, 문서 단위로 끊어야 실패 피해가 그 1편에 갇힌다.

왜 백업이 필수인가:
  delete 가 insert 보다 먼저 실행된다 — 그 사이에 중단되면 해당 문서의 청크가
  전멸한다(임베딩 재생성 없이는 복구 불가). 읽은 청크(embedding·sparse_embedding
  포함)를 JSONL 로 디스크에 먼저 써 둬야 delete/insert 실패 시 --restore 로
  되돌릴 수 있다.

왜 index_chunks() 를 재사용하지 않는가:
  그 함수는 chunk_id 를 f"{book_id}__{chunk_idx:04d}" 로 재생성하고 text 를
  16,000바이트로 재차 자른다(app/services/ingestion/indexer.py). 읽은 값을
  한 글자도 바꾸지 않고 되넣어야 바이트 단위로 원상복구되므로, 이 스크립트는
  Milvus 스키마 컬럼 순서만 공유하는 별도 insert 경로를 쓴다.

컬럼 순서 — 스키마와의 정합성:
  Milvus insert 는 컬럼 지향이며 스키마 필드 순서를 정확히 따라야 한다:
    chunk_id·book_id·chunk_idx·section_idx·text·page_start·page_end
      · <스칼라 필드, _scalar_field_specs() 순서> · embedding · sparse_embedding
  스칼라 필드 순서를 이 스크립트에 하드코딩하면, 도메인 프로파일의 스칼라
  필드가 나중에 바뀔 때 조용히 어긋나 데이터가 엉뚱한 컬럼에 들어간다.
  scalar_order() 가 앱의 _scalar_field_specs() 를 런타임에 그대로 읽어와
  이 위험을 없앤다.

PYTHONPATH=/app 가 필요한 이유:
  scripts/ 는 앱 이미지에 없어 호스트 바인드 마운트를 경유해 스크립트 파일
  경로로 실행한다. 파일 경로로 실행하면 sys.path[0] 이 스크립트가 있는
  디렉터리로 잡혀 services/domains 같은 앱 모듈을 찾지 못한다:

    docker exec -e PYTHONPATH=/app nl-lib-fastapi \\
      python /app/data/recovery/rewrite_milvus_doc_type.py

이 파일의 범위:
  여기 있는 함수는 순수 변환뿐이다(Milvus·Postgres I/O 없음) — pymilvus 없이도
  임포트·테스트 가능. 대상 선정·백업 파일 쓰기·--apply/--restore CLI 는 별도.
"""

FIXED_ORDER = [
    "chunk_id",
    "book_id",
    "chunk_idx",
    "section_idx",
    "text",
    "page_start",
    "page_end",
]


def scalar_order() -> list[str]:
    """앱의 _scalar_field_specs() 에서 스칼라 필드명 순서를 읽어온다.

    함수 로컬 import — pymilvus 를 거치는 indexer 모듈은 호출 시점에만 필요하고,
    이 파일의 나머지 순수 함수는 pymilvus 없이도 임포트·테스트 가능해야 한다.
    private 함수를 그대로 참조하는 이유: 스키마 컬럼 순서의 단일 진실원천이
    거기뿐이라 여기 복제하면 조용히 어긋난다 — 드리프트 테스트가 이 계약을 고정한다.
    """
    from services.ingestion.indexer import _scalar_field_specs

    return [name for name, _ in _scalar_field_specs()]


def normalize_sparse(sparse: dict) -> dict[str, float]:
    """Milvus sparse 벡터(int 키) → JSON 백업용(문자열 키). JSON 객체 키는 문자열이어야 한다.

    pymilvus 의 반환 타입을 신뢰하지 않는다 — dict 로 감싸고 값을 float 로
    캐스팅해, numpy 스칼라가 섞여 들어와도 이후 json.dumps 가 죽지 않게 한다.
    """
    return {str(k): float(v) for k, v in dict(sparse).items()}


def denormalize_sparse(sparse: dict) -> dict[int, float]:
    """백업(문자열 키) → Milvus insert 용(int 키)."""
    return {int(k): float(v) for k, v in sparse.items()}


def row_to_record(row: dict, scalar_names: list[str]) -> dict:
    """Milvus query 결과 1행 → JSON 직렬화 가능한 백업 레코드.

    text 는 재가공 없이 그대로 담는다 — 읽은 값을 바이트 단위로 그대로
    되넣는 것이 이 도구의 전제다. 스칼라 필드가 누락된 행은 ""로 채운다.
    embedding 은 list() 로 감싼다 — pymilvus 가 ndarray 를 반환하면
    json.dumps 가 죽으므로 반환 타입을 신뢰하지 않는다.
    """
    record = {name: row[name] for name in FIXED_ORDER}
    for name in scalar_names:
        record[name] = row.get(name, "") or ""
    record["embedding"] = list(row["embedding"])
    record["sparse_embedding"] = normalize_sparse(row["sparse_embedding"])
    return record


def records_to_insert_data(
    records: list[dict],
    override_doc_type: str | None,
    scalar_names: list[str],
) -> list[list]:
    """백업 레코드 목록 → Milvus insert 용 컬럼 지향 데이터.

    override_doc_type 이 주어지면 모든 레코드의 doc_type 을 그 값으로 바꾸고
    나머지 스칼라는 그대로 둔다(재기록 경로). None 이면 각 레코드가 가진
    doc_type 을 그대로 쓴다(--restore 경로 — 백업 시점 값을 그대로 복원).
    """
    data = [[record[name] for record in records] for name in FIXED_ORDER]
    for name in scalar_names:
        if name == "doc_type" and override_doc_type is not None:
            data.append([override_doc_type] * len(records))
        else:
            data.append([record[name] for record in records])
    data.append([record["embedding"] for record in records])
    data.append([denormalize_sparse(record["sparse_embedding"]) for record in records])
    return data


import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKUP_ROOT = Path("/app/data/recovery/backup")
QUERY_PAGE = 1000


def output_fields(scalar_names: list[str]) -> list[str]:
    """Milvus query 로 읽어올 필드 — 스키마 전 필드(임베딩 포함)."""
    return FIXED_ORDER + scalar_names + ["embedding", "sparse_embedding"]


def find_targets(db) -> list[tuple[str, str]]:
    """재기록 대상 → [(cnts_id, Postgres doc_type)].

    Milvus 메타청크로 역복원한 행만 본다 — 전체 24만 행을 훑지 않는다.
    """
    from sqlalchemy import text as sa_text

    rows = db.execute(sa_text(
        "SELECT cnts_id, doc_type FROM library_catalog "
        "WHERE extra->>'restored_from' = 'milvus_meta_chunk' "
        "  AND doc_type IS NOT NULL "
        "ORDER BY cnts_id"
    ))
    return [(r[0], r[1]) for r in rows]


def milvus_doc_type(col, book_id: str) -> str | None:
    """메타청크(chunk_idx = -1)의 doc_type. 없으면 None."""
    rows = col.query(
        expr=f'book_id == "{book_id}" && chunk_idx == -1',
        output_fields=["doc_type"],
        limit=1,
    )
    return rows[0].get("doc_type") if rows else None


def fetch_chunks(col, book_id: str, scalar_names: list[str]) -> list[dict]:
    """해당 book_id 의 전 청크를 임베딩까지 읽는다. offset 페이징."""
    out: list[dict] = []
    offset = 0
    while True:
        page = col.query(
            expr=f'book_id == "{book_id}"',
            output_fields=output_fields(scalar_names),
            limit=QUERY_PAGE,
            offset=offset,
        )
        if not page:
            break
        out.extend(page)
        if len(page) < QUERY_PAGE:
            break
        offset += QUERY_PAGE
    return out


def count_chunks(col, book_id: str) -> int:
    rows = col.query(
        expr=f'book_id == "{book_id}"', output_fields=["chunk_id"], limit=16384,
    )
    return len(rows)


def backup_path(stamp: str, book_id: str) -> Path:
    return BACKUP_ROOT / f"doc_type_{stamp}" / f"{book_id}.jsonl"


def write_backup(path: Path, records: list[dict]) -> int:
    """백업을 쓰고 디스크에서 다시 읽어 줄 수를 센다 — 썼다고 치지 않는다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def read_backup(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def rewrite_one(col, book_id: str, records: list[dict],
                doc_type: str | None, scalar_names: list[str]) -> None:
    """읽은 청크를 doc_type 만 바꿔 제자리 교체한다.

    delete 후 insert 가 아니라 upsert 를 쓴다 — 기본키(chunk_id)가 동일해
    의미는 같으면서, 그 문서의 청크가 0개가 되는 구간이 생기지 않는다.
    실패해도 기존 청크가 그대로 남는다.
    """
    col.upsert(records_to_insert_data(records, doc_type, scalar_names))
    col.flush()


def run(apply: bool, limit: int | None = None) -> int:
    from db.postgres import SyncSessionLocal
    from services.ingestion.indexer import ensure_collection

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    col = ensure_collection()
    scalar_names = scalar_order()

    db = SyncSessionLocal()
    try:
        targets = find_targets(db)
    finally:
        db.close()
    print(f"대상 후보: {len(targets)}건")

    pending = []
    for cnts_id, pg_doc_type in targets:
        mv = milvus_doc_type(col, cnts_id)
        if mv == pg_doc_type:
            continue
        pending.append((cnts_id, pg_doc_type, mv, count_chunks(col, cnts_id)))

    if not pending:
        print("불일치 없음 — 할 일이 없다")
        return 0

    if limit is not None:
        pending = pending[:limit]

    total_chunks = sum(p[3] for p in pending)
    print(f"재기록 필요: {len(pending)}건 / 청크 합계 {total_chunks:,}개")
    print(f"예상 백업 용량: 약 {total_chunks * 12 / 1024:.1f} MB (청크당 ~12KB 추정)\n")
    for cnts_id, pg, mv, n in pending:
        print(f"  {cnts_id:22} Milvus {mv!r} → Postgres {pg!r}  (청크 {n:,})")

    if not apply:
        print("\ndry-run — 아무것도 쓰지 않았다. 반영하려면 --apply")
        return 0

    print(f"\n백업 위치: {BACKUP_ROOT / ('doc_type_' + stamp)}\n")
    done = 0
    for cnts_id, pg_doc_type, _mv, expected in pending:
        rows = fetch_chunks(col, cnts_id, scalar_names)
        records = [row_to_record(r, scalar_names) for r in rows]
        path = backup_path(stamp, cnts_id)
        written = write_backup(path, records)

        if written != expected:
            print(f"  [SKIP] {cnts_id} — 백업 {written} != Milvus {expected}, 건드리지 않는다")
            continue

        rewrite_one(col, cnts_id, records, pg_doc_type, scalar_names)

        after = count_chunks(col, cnts_id)
        after_doc_type = milvus_doc_type(col, cnts_id)
        if after != expected or after_doc_type != pg_doc_type:
            print(f"  [FAIL] {cnts_id} — 검증 실패 (청크 {after}/{expected}, "
                  f"doc_type {after_doc_type!r}/{pg_doc_type!r})")
            print(f"         복구: --restore {path.parent}")
            print("         남은 문서는 손대지 않고 중단한다")
            return 1

        done += 1
        print(f"  [OK]   {cnts_id} — 청크 {after:,} · doc_type {after_doc_type!r}")

    print(f"\n재기록 완료: {done}건")
    return 0


def restore(backup_dir: str) -> int:
    from services.ingestion.indexer import ensure_collection

    col = ensure_collection()
    scalar_names = scalar_order()
    files = sorted(Path(backup_dir).glob("*.jsonl"))
    if not files:
        print(f"백업 파일이 없다: {backup_dir}")
        return 1

    print(f"복구 대상: {len(files)}건")
    for path in files:
        book_id = path.stem
        records = read_backup(path)
        rewrite_one(col, book_id, records, None, scalar_names)
        print(f"  [OK] {book_id} — 청크 {len(records):,} 복구")
    return 0


def main() -> int:
    if "--restore" in sys.argv:
        idx = sys.argv.index("--restore")
        if idx + 1 >= len(sys.argv):
            print("--restore <백업디렉터리> 형태로 경로를 지정한다")
            return 2
        return restore(sys.argv[idx + 1])

    limit = None
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 >= len(sys.argv):
            print("--limit <N> 형태로 건수를 지정한다")
            return 2
        limit = int(sys.argv[idx + 1])

    return run(apply="--apply" in sys.argv, limit=limit)


if __name__ == "__main__":
    sys.exit(main())
