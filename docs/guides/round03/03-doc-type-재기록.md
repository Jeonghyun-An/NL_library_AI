# round03 교본 (4) — Milvus doc_type 재기록

전체 개요·검증·Q&A 는 [00-개요.md](00-개요.md) 참조.

## 무엇이 문제였나

한국 근대문학 문서(위키문헌 `WS_*` · 공유마당 `GM_*`)는 카탈로그 적재를 거치지 않고 바로 인덱싱돼, Milvus 스칼라 필드 `doc_type` 에 Postgres 와 어긋난 값이 박혀 있었다. 증상이 한쪽으로만 치우친 이유는 검색 필터가 비대칭이기 때문이다(`app/services/search/pipeline.py:45`).

```python
_PAPER_EXPR = '(doc_type == "paper" || book_id like "KCI_FI%")'
_BOOK_EXPR  = '(doc_type != "paper" && not (book_id like "KCI_FI%"))'
```

논문 필터에는 `book_id like "KCI_FI%"` 라는 ID 폴백이 있어 `doc_type` 이 틀려도 진짜 논문은 잡힌다. 도서 필터에는 그런 폴백이 없다. 그래서 `paper` 오판정 한 번이면 그 문서는 도서 필터에서 제외돼 **도서 검색에서 통째로 사라지고**, 동시에 논문 필터를 통과해 **논문 검색에 섞여 나온다**. "도서에서 사라지고 논문에 섞인다"는 증상은 이 두 줄의 비대칭에서 그대로 따라 나온다.

**dry-run 실측이 설계 전제를 뒤집었다.** spec 초안(§1-2)은 문학 41편이 전부 `paper` 로 들어가 있다고 적었으나, 실제 dry-run 은 `대상 후보: 41건` 중 **`재기록 필요: 15건`** 이었다 — Milvus 값이 `paper` 5건 · `book` 10건 · 이미 `literature` 26건. 두 숫자는 다른 개념이다(후보는 조회 대상, 재기록 필요는 Postgres 와 어긋난 건수). 도서 필터가 `doc_type != "paper"` 이므로 `book` 10건은 **원래부터 도서 검색에 잡히고 있었고**, 실제 실종은 `paper` 5건뿐이었다. 실측 규모는 15건 · 966청크 · 백업 11.3MB 다(완료노트 §2-3 Task 6). 스크립트의 모듈 docstring 도 이 실측에 맞춰 정정했다(초안은 41편 전부 `paper` 라고 적고 있었다).

**왜 재인덱싱이 아니라 스칼라 재기록인가.** 문서를 다시 적재하면 `run_extract` 가 `book_sections` 를 지우고 다시 만들어(`app/services/ingestion/stages.py:300`) 99.9% 살아있는 섹션 요약·테마를 갈아엎고, OCR·LLM 비용도 다시 든다. 고쳐야 할 것은 스칼라 한 칸뿐이고 본문·임베딩은 멀쩡하다. 후처리 필터(검색 후 `book_info.doc_type` 으로 걸러내기)도 검토했으나 채택하지 않았다 — 도서 검색이 애초에 그 문서를 반환하지 않으므로, 검색된 뒤에 거르는 방식으로는 증상의 절반(실종)을 고칠 수 없다.

## 2. 구현 (클론코딩)

### 2.15 Milvus doc_type 재기록 도구

**파일**: `scripts/recovery/rewrite_milvus_doc_type.py`

코드를 읽기 전에 설계의 핵심 다섯 가지를 본다.

**① Milvus 에는 부분 update 가 없다.** 스칼라 필드 하나를 고치려면 그 문서의 모든 청크를 dense·sparse 임베딩까지 읽어서 통째로 다시 써야 한다. 기존 `index_chunks()` 를 재사용하지 않는 이유도 여기에 있다 — 그 함수는 `chunk_id` 를 `f"{book_id}__{chunk_idx:04d}"` 로 재생성하고 `text` 를 16,000바이트로 다시 자른다(`app/services/ingestion/indexer.py`). 읽은 값을 한 글자도 바꾸지 않고 되넣어야 하므로 스키마 컬럼 순서만 공유하는 별도 insert 경로를 쓴다. Milvus 에는 트랜잭션도 없어 여러 문서를 묶어봐야 원자성 이득이 없고, 처리 단위를 문서 1건으로 끊어야 실패 피해가 그 1편에 갇힌다.

**② 스키마 필드 순서 = insert 컬럼 순서.** Milvus insert 는 컬럼 지향이라 `[[chunk_id들], [book_id들], …]` 모양으로 넘기고, 이 리스트의 순서가 컬렉션 스키마의 필드 순서와 정확히 같아야 한다. 어긋나도 예외가 나지 않는다 — 임베딩이 텍스트 컬럼에 들어가는 식의 **조용한 파괴**가 일어난다. 그래서 스칼라 필드 순서를 이 스크립트에 하드코딩하지 않고, `scalar_order()` 가 앱의 `_scalar_field_specs()`(→ `get_active_profile().milvus_scalar_fields`)를 런타임에 그대로 읽어온다. 순서의 단일 진실원천이 거기뿐이라 여기 복제하면 도메인 프로파일이 바뀔 때 조용히 어긋난다. 드리프트는 테스트가 고정한다(§2.16).

**③ `delete + insert` 가 아니라 `col.upsert()`.** 기본키(`chunk_id`)가 동일하므로 의미는 같지만, delete 직후에 실패하면 그 문서의 청크가 0개인 상태로 남는다. upsert 는 실패해도 기존 청크가 그대로다 — 이 선택으로 **실제 데이터 소실 경로 자체가 사라진다.** 그 문서의 청크 수가 0이 되는 구간이 없다.

**④ 그래도 백업을 먼저 쓰고 `--restore` 를 둔다.** 운영 Milvus 를 직접 건드리는 도구다. upsert 가 안전해도 `fetch_chunks` 가 offset 페이징 도중 일부 청크를 놓치면, 읽어온 것만 교체되고 못 읽은 청크는 옛 `doc_type` 을 가진 채 조용히 남는다. 그래서 읽은 청크를 임베딩까지 JSONL 로 먼저 쓰고, **디스크에서 다시 읽어 센 줄 수**를 Milvus 청크 수와 대조한다(`write_backup` 이 "썼다고 치지" 않고 다시 읽어 세는 이유다). 대조 기준은 사전 스캔 값이 아니라 `fetch_chunks` 직후에 다시 센 값이다 — 놓쳤는지를 잡는 게 목적이라 기준이 최신이어야 한다. 어긋나면 그 문서는 손대지 않고 백업 파일에 `.incomplete` 를 붙여 보존한다. 사후 검증까지 어긋나면 `restore()` 로 되돌린다. `restore()` 가 디렉터리뿐 아니라 **파일 하나**도 받는 이유는, 같은 실행에서 이미 검증을 통과한 앞선 문서들까지 함께 되돌아가는 것을 막기 위해서다.

**⑤ 운영 실행에서 실제로 터진 버그 — `numpy.float32`.** 첫 1건(`GM_001` 동백꽃) 선행 검증에서 백업 쓰기 단계가 `TypeError: Object of type float32 is not JSON serializable` 로 죽었다. 원인은 `list(row["embedding"])` 이었다. pymilvus 는 dense 벡터를 numpy 배열로 돌려주는데, `list()` 는 **컨테이너만 파이썬 list 로 바꿀 뿐 원소는 `numpy.float32` 로 남는다.** `json.dumps` 는 그 원소를 직렬화하지 못한다. 고친 한 줄이 이것이다.

```python
record["embedding"] = [float(x) for x in row["embedding"]]
```

컨테이너가 아니라 **원소마다** `float()` 을 거는 것이 요점이다. `normalize_sparse` 가 sparse 값에 `float(v)` 를 거는 것도 같은 방어다. 이 버그가 백업 쓰기 단계에서 터진 덕에 Milvus 는 무손상이었다 — 순서가 「백업 먼저, 쓰기 나중」이기 때문이다. 고친 뒤 재실행해 `GM_001` 청크 19개 · `doc_type {'literature'}` · 다른 스칼라 불변 · 임베딩 1024차원 생존을 확인하고 나머지 14건을 반영했다.

**구조 — 순수 함수와 I/O 를 나눴다.** 파일 앞쪽의 `scalar_order` · `normalize_sparse` · `denormalize_sparse` · `row_to_record` · `records_to_insert_data` 는 Milvus·Postgres 를 전혀 만지지 않는 변환 함수뿐이고, 중간의 `import json` 이후가 I/O 계층(`find_targets` · `fetch_chunks` · `write_backup` · `rewrite_one` · `run` · `restore` · `main`)이다. `scalar_order()` 의 `from services.ingestion.indexer import _scalar_field_specs` 도 모듈 최상단이 아니라 **함수 로컬 import** 라, pymilvus 가 깔려 있지 않은 개발 PC 에서도 이 파일을 임포트할 수 있다. 그 덕에 컬럼 순서·스칼라 교체·sparse 왕복 같은 위험한 로직을 **Milvus 없이** 테스트로 고정할 수 있다.

```python
"""rewrite_milvus_doc_type.py — Milvus doc_type 스칼라 재기록 (문학 오분류 교정)

배경:
  위키문헌(WS_*)·공유마당(GM_*) 문학 작품 41편이 카탈로그 적재 없이 바로
  인덱싱되면서 Milvus doc_type 이 Postgres 와 어긋났다. dry-run 실측 기준
  41편 중 재기록이 필요한 것은 15건이다 — paper 5 / book 10, 나머지 26 은
  이미 literature 로 맞게 들어가 있었다.

  피해가 가장 큰 것은 paper 5건이다. 논문 검색은 book_id 접두어 안전망이
  있어 영향이 적지만 도서 검색은 doc_type != 'paper' 만 보므로, 이 5건은
  도서 검색에서 완전히 실종된다. book 10건은 도서 검색에는 잡히지만
  라벨이 틀린 상태라 함께 바로잡는다.

왜 문서 단위 재기록인가:
  Milvus 는 부분 update 가 없다 — 필드 하나를 고치려면 해당 문서의 모든 청크를
  다시 써야 한다. 트랜잭션도 없으므로 여러 문서를 묶어봐야 원자성 이득이 없고,
  문서 단위로 끊어야 실패 피해가 그 1편에 갇힌다.

왜 백업이 필수인가:
  기본키(chunk_id)로 제자리 교체하는 upsert 를 쓰므로 그 자체가 실패해도
  기존 청크는 그대로 남는다. 하지만 fetch_chunks 가 애초에 일부 청크를 놓친
  채로 override_doc_type 만 바꿔 되넣으면, 놓친 청크는 옛 doc_type 을 가진
  채로 조용히 방치된다. 읽은 청크(embedding·sparse_embedding 포함)를 JSONL 로
  디스크에 먼저 써서 그 줄 수를 Milvus 청크 수와 대조해야 이 상황을 잡아내고,
  그래도 사후 검증이 어긋나면 --restore 로 그 문서만 되돌릴 수 있다.

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
    embedding 은 원소까지 float 로 캐스팅한다. pymilvus 는 dense 벡터를 numpy
    배열로 돌려주는데, list() 로 감싸도 원소는 numpy.float32 로 남아 json.dumps 가
    죽는다(운영 실행에서 실측). 컨테이너를 감싸는 것만으로는 부족하다.
    """
    record = {name: row[name] for name in FIXED_ORDER}
    for name in scalar_names:
        record[name] = row.get(name, "") or ""
    record["embedding"] = [float(x) for x in row["embedding"]]
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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymilvus import Collection
    from sqlalchemy.orm import Session

BACKUP_ROOT = Path("/app/data/recovery/backup")
QUERY_PAGE = 1000


def output_fields(scalar_names: list[str]) -> list[str]:
    """Milvus query 로 읽어올 필드 — 스키마 전 필드(임베딩 포함)."""
    return FIXED_ORDER + scalar_names + ["embedding", "sparse_embedding"]


def find_targets(db: "Session") -> list[tuple[str, str]]:
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


def milvus_doc_type(col: "Collection", book_id: str) -> str | None:
    """메타청크(chunk_idx = -1)의 doc_type. 없으면 None."""
    rows = col.query(
        expr=f'book_id == "{book_id}" && chunk_idx == -1',
        output_fields=["doc_type"],
        limit=1,
    )
    return rows[0].get("doc_type") if rows else None


def fetch_chunks(col: "Collection", book_id: str, scalar_names: list[str]) -> list[dict]:
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


def count_chunks(col: "Collection", book_id: str) -> int:
    """limit=16384 는 실측 최대 511청크 대비 충분히 크다. 그보다 많아도
    written != current 로 안전하게 스킵될 뿐 데이터가 잘못 쓰이지는 않는다."""
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


def rewrite_one(col: "Collection", book_id: str, records: list[dict],
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
    skipped = 0
    for cnts_id, pg_doc_type, _mv, _prescan_count in pending:
        rows = fetch_chunks(col, cnts_id, scalar_names)
        records = [row_to_record(r, scalar_names) for r in rows]
        # 사전 스캔 값(_prescan_count)이 아니라 fetch 직후 값과 비교한다 —
        # fetch_chunks 가 일부를 놓쳤는지 잡는 게 목적이라 기준이 최신이어야 한다.
        current = count_chunks(col, cnts_id)
        path = backup_path(stamp, cnts_id)
        written = write_backup(path, records)

        if written != current:
            incomplete = path.with_name(path.name + ".incomplete")
            path.rename(incomplete)
            skipped += 1
            print(f"  [SKIP] {cnts_id} — 백업 {written} != Milvus {current}, 건드리지 않는다 "
                  f"({incomplete.name} 로 보존, --restore 대상에서는 제외)")
            continue

        rewrite_one(col, cnts_id, records, pg_doc_type, scalar_names)

        after = count_chunks(col, cnts_id)
        after_doc_type = milvus_doc_type(col, cnts_id)
        if after != current or after_doc_type != pg_doc_type:
            print(f"  [FAIL] {cnts_id} — 검증 실패 (청크 {after}/{current}, "
                  f"doc_type {after_doc_type!r}/{pg_doc_type!r})")
            print(f"         복구(이 문서만): --restore {path}")
            print(f"         디렉터리 전체({path.parent})로 --restore 하면 이번 실행에서 "
                  "이미 검증을 통과한 앞선 문서들까지 함께 되돌아간다")
            print("         남은 문서는 손대지 않고 중단한다")
            return 1

        done += 1
        print(f"  [OK]   {cnts_id} — 청크 {after:,} · doc_type {after_doc_type!r}")

    print()
    if skipped:
        print(f"스킵됨: {skipped}건 — 백업 불일치로 건드리지 않음")
    print(f"재기록 완료: {done}건")
    return 1 if skipped else 0


def restore(backup_dir: str) -> int:
    """백업디렉터리 또는 단일 .jsonl 파일 하나를 복구한다.

    단일 파일을 받을 수 있어야 하는 이유: [FAIL] 안내가 그 문서 하나의
    파일을 가리키기 때문이다 — 디렉터리 전체로 복구하면 같은 실행에서
    이미 검증까지 통과한 다른 문서들까지 되돌아간다.
    """
    from services.ingestion.indexer import ensure_collection

    col = ensure_collection()
    scalar_names = scalar_order()
    target = Path(backup_dir)
    files = [target] if target.is_file() else sorted(target.glob("*.jsonl"))
    if not files:
        print(f"백업 파일이 없다: {backup_dir}")
        return 1

    print(f"복구 대상: {len(files)}건")
    failed = 0
    for path in files:
        book_id = path.stem
        records = read_backup(path)
        rewrite_one(col, book_id, records, None, scalar_names)

        after = count_chunks(col, book_id)
        if after != len(records):
            failed += 1
            print(f"  [FAIL] {book_id} — 복구 검증 실패 (청크 {after}/{len(records)})")
            continue

        print(f"  [OK] {book_id} — 청크 {len(records):,} 복구")
    return 1 if failed else 0


def main() -> int:
    if "--restore" in sys.argv:
        idx = sys.argv.index("--restore")
        if idx + 1 >= len(sys.argv):
            print("--restore <백업디렉터리 또는 .jsonl 파일> 형태로 경로를 지정한다")
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
```

### 2.16 재기록 도구 순수 함수 테스트

**파일**: `app/tests/test_rewrite_milvus_doc_type.py`

이 테스트는 Milvus 를 띄우지 않는다. 순수 변환 함수와 파일 I/O 만으로 다음 계약을 고정한다.

- **컬럼 순서 계약** — `records_to_insert_data` 가 돌려주는 컬럼 수가 7(고정) + 5(스칼라) + 2(dense·sparse) = 14 인지, 앞 7개가 `chunk_id` · `book_id` · `chunk_idx` · `section_idx` · `text` · `page_start` · `page_end` 순으로 나오는지 확인한다. 스칼라 단언에서 `corporate_author` 와 `kdc` 에 **서로 다른 값**을 넣어 둔 것이 핵심이다 — 두 컬럼이 자리바꿈되면 값이 같을 때는 아무 일도 없는 것처럼 보이지만, 값이 다르면 단언이 깨진다. §2.15 ②의 "조용한 파괴"를 잡는 자리다.
- **스칼라 교체 범위** — `override_doc_type` 을 줬을 때 `doc_type` 만 바뀌고 `pub_date` · `publisher` · `corporate_author` · `kdc` 는 그대로인지. `None` 일 때는 각 레코드가 가진 `doc_type` 을 그대로 쓰는지(`--restore` 경로 — 백업 시점 값을 그대로 복원해야 한다).
- **스키마 드리프트 감지** — `test_scalar_order_matches_schema` 가 `scalar_order()` 결과를 기대 리스트와 직접 대조한다. 프로파일(`profile.py`)의 스칼라 순서를 바꾸면 이 테스트가 깨진다(실증 확인). pymilvus 가 없는 환경에서는 `_stub_pymilvus_if_missing` 이 더미 모듈을 꽂아 `indexer` 임포트만 통과시킨다 — 그래야 로컬에서도 이 계약을 검증할 수 있다.
- **sparse 벡터 왕복** — `normalize_sparse` → `denormalize_sparse` 가 키 타입(int ↔ str)과 값을 정확히 되돌리는지. JSON 객체 키는 문자열이어야 해서 백업 시 변환이 필요하고, 되돌릴 때 int 로 복구되지 않으면 Milvus insert 가 깨진다.
- **본문 무가공** — `text` 에 ` | ` 구분자가 들어 있어도 재가공 없이 그대로 담는지. 메타청크 복원에서 이 구분자가 값 안에 섞여 있던 전례(`저자: 柳在元 | 林慧俊`)가 있어 명시적으로 고정했다.
- **백업 파일 왕복** — `write_backup` 이 없는 부모 디렉터리를 만들고, 반환값이 실제 줄 수이며, `read_backup` 으로 읽으면 원 레코드와 같은지.

**float32 회귀 테스트가 잡는 것.** `_NumpyLikeScalar` 는 `__float__` 만 가진 클래스로, `numpy.float32` 처럼 **`float` 서브클래스가 아니어서 `float()` 로만 변환되는** 타입을 흉내낸다. 이게 없으면 평범한 `0.5` 로 테스트해봐야 `list()` 든 `[float(x) for x in ...]` 든 똑같이 통과해 버린다. `test_row_to_record_casts_embedding_elements_to_plain_float` 는 `isinstance` 가 아니라 **`type(x) is float`** 로 단언하므로, 구현이 `list(row["embedding"])` 로 되돌아가면 즉시 실패한다. 그리고 마지막 줄의 `json.dumps(record)` 가 운영에서 실제로 터졌던 그 예외를 재현하는 자리다. `test_row_to_record_casts_sparse_values_to_plain_float` 가 sparse 값에 대해 같은 일을 한다.

```python
"""scripts/recovery/rewrite_milvus_doc_type.py — 순수 변환 함수 테스트."""
import importlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "recovery"
sys.path.insert(0, str(SCRIPTS_DIR))

SCALAR_NAMES = ["doc_type", "pub_date", "publisher", "corporate_author", "kdc"]


def _stub_pymilvus_if_missing(monkeypatch):
    """설치 안 된 환경에서만 pymilvus 를 더미로 꽂는다 — indexer 임포트가 필요한
    scalar_order() 를 로컬에서도 검증하기 위함(test_embed_index_guard.py 와 동일 기법)."""
    try:
        importlib.import_module("pymilvus")
    except ModuleNotFoundError:
        from unittest.mock import MagicMock

        monkeypatch.setitem(sys.modules, "pymilvus", MagicMock())
        monkeypatch.delitem(sys.modules, "services.ingestion.indexer", raising=False)


def test_normalize_sparse_produces_string_keys():
    from rewrite_milvus_doc_type import normalize_sparse

    result = normalize_sparse({1023: 0.03125, 5: 1.0})
    assert result == {"1023": 0.03125, "5": 1.0}
    assert all(isinstance(k, str) for k in result)


def test_denormalize_sparse_restores_int_keys():
    from rewrite_milvus_doc_type import denormalize_sparse

    result = denormalize_sparse({"1023": 0.03125, "5": 1.0})
    assert result == {1023: 0.03125, 5: 1.0}
    assert all(isinstance(k, int) for k in result)


def test_sparse_round_trip_preserves_exact_values():
    from rewrite_milvus_doc_type import denormalize_sparse, normalize_sparse

    original = {1023: 0.03125, 7: 0.5, 42: 0.1}
    round_tripped = denormalize_sparse(normalize_sparse(original))
    assert round_tripped == original


def test_row_to_record_keeps_all_fields_and_preserves_text_verbatim():
    from rewrite_milvus_doc_type import row_to_record

    text_with_delim = "저자: 柳在元 | 林慧俊"
    row = {
        "chunk_id": "WS_001__0000",
        "book_id": "WS_001",
        "chunk_idx": 0,
        "section_idx": 0,
        "text": text_with_delim,
        "page_start": 1,
        "page_end": 2,
        "doc_type": "paper",
        "pub_date": "1917",
        "publisher": "",
        "corporate_author": "",
        "kdc": "",
        "embedding": [0.1, 0.2, 0.3],
        "sparse_embedding": {1023: 0.03125},
    }

    record = row_to_record(row, SCALAR_NAMES)

    assert record["text"] == text_with_delim
    assert record["chunk_id"] == "WS_001__0000"
    assert record["book_id"] == "WS_001"
    assert record["chunk_idx"] == 0
    assert record["section_idx"] == 0
    assert record["page_start"] == 1
    assert record["page_end"] == 2
    assert record["embedding"] == [0.1, 0.2, 0.3]
    assert record["sparse_embedding"] == {"1023": 0.03125}
    for name in SCALAR_NAMES:
        assert name in record
    assert record["doc_type"] == "paper"
    assert record["pub_date"] == "1917"

    json.dumps(record)  # JSON 직렬화 가능해야 백업 파일로 쓸 수 있다


def test_row_to_record_defaults_missing_scalars_to_empty_string():
    from rewrite_milvus_doc_type import row_to_record

    row = {
        "chunk_id": "WS_002__0000",
        "book_id": "WS_002",
        "chunk_idx": 0,
        "section_idx": 0,
        "text": "본문",
        "page_start": 0,
        "page_end": 0,
        "doc_type": "literature",
        # pub_date/publisher/corporate_author/kdc 누락
        "embedding": [0.0],
        "sparse_embedding": {},
    }

    record = row_to_record(row, SCALAR_NAMES)

    assert record["pub_date"] == ""
    assert record["publisher"] == ""
    assert record["corporate_author"] == ""
    assert record["kdc"] == ""


def _make_records(n: int) -> list[dict]:
    return [
        {
            "chunk_id": f"WS_001__{i:04d}",
            "book_id": "WS_001",
            "chunk_idx": i,
            "section_idx": 0,
            "text": f"본문 {i}",
            "page_start": i,
            "page_end": i,
            "doc_type": "paper",
            "pub_date": "1917",
            "publisher": "출판사",
            "corporate_author": "대외경제정책연구원",
            "kdc": "813.6",
            "embedding": [0.1, 0.2],
            "sparse_embedding": {"1": 0.5},
        }
        for i in range(n)
    ]


def test_records_to_insert_data_has_correct_column_count_and_leading_columns():
    from rewrite_milvus_doc_type import records_to_insert_data

    records = _make_records(3)
    data = records_to_insert_data(records, override_doc_type="literature", scalar_names=SCALAR_NAMES)

    # 7(고정) + 5(스칼라) + 2(embedding, sparse_embedding) = 14
    assert len(data) == 14
    assert data[0] == ["WS_001__0000", "WS_001__0001", "WS_001__0002"]  # chunk_id
    assert data[1] == ["WS_001", "WS_001", "WS_001"]                     # book_id
    assert data[2] == [0, 1, 2]                                          # chunk_idx
    assert data[3] == [0, 0, 0]                                          # section_idx
    assert data[4] == ["본문 0", "본문 1", "본문 2"]                      # text
    assert data[5] == [0, 1, 2]                                          # page_start
    assert data[6] == [0, 1, 2]                                          # page_end


def test_records_to_insert_data_override_changes_only_doc_type():
    from rewrite_milvus_doc_type import records_to_insert_data

    records = _make_records(2)
    data = records_to_insert_data(records, override_doc_type="literature", scalar_names=SCALAR_NAMES)

    scalar_start = 7
    doc_type_col = data[scalar_start + SCALAR_NAMES.index("doc_type")]
    pub_date_col = data[scalar_start + SCALAR_NAMES.index("pub_date")]
    publisher_col = data[scalar_start + SCALAR_NAMES.index("publisher")]
    corporate_author_col = data[scalar_start + SCALAR_NAMES.index("corporate_author")]
    kdc_col = data[scalar_start + SCALAR_NAMES.index("kdc")]

    assert doc_type_col == ["literature", "literature"]
    assert pub_date_col == ["1917", "1917"]
    assert publisher_col == ["출판사", "출판사"]
    # corporate_author·kdc 는 서로 다른 값이라 자리바꿈 버그가 나면 여기서 잡힌다
    assert corporate_author_col == ["대외경제정책연구원", "대외경제정책연구원"]
    assert kdc_col == ["813.6", "813.6"]


def test_records_to_insert_data_no_override_keeps_original_doc_type():
    from rewrite_milvus_doc_type import records_to_insert_data

    records = _make_records(2)
    records[0]["doc_type"] = "literature"
    records[1]["doc_type"] = "paper"

    data = records_to_insert_data(records, override_doc_type=None, scalar_names=SCALAR_NAMES)

    scalar_start = 7
    doc_type_col = data[scalar_start + SCALAR_NAMES.index("doc_type")]
    assert doc_type_col == ["literature", "paper"]


def test_records_to_insert_data_sparse_column_has_int_keys():
    from rewrite_milvus_doc_type import records_to_insert_data

    records = _make_records(1)
    records[0]["sparse_embedding"] = {"1023": 0.03125}

    data = records_to_insert_data(records, override_doc_type="literature", scalar_names=SCALAR_NAMES)

    sparse_col = data[-1]
    assert sparse_col == [{1023: 0.03125}]
    assert all(isinstance(k, int) for k in sparse_col[0])


def test_scalar_order_matches_schema(monkeypatch):
    """스키마 드리프트 감지기 — _scalar_field_specs() 순서가 바뀌면 이 테스트가 깨진다."""
    _stub_pymilvus_if_missing(monkeypatch)

    from rewrite_milvus_doc_type import scalar_order

    assert scalar_order() == ["doc_type", "pub_date", "publisher", "corporate_author", "kdc"]


def test_write_backup_returns_line_count_matching_records(tmp_path):
    from rewrite_milvus_doc_type import write_backup

    records = _make_records(3)
    path = tmp_path / "WS_001.jsonl"

    written = write_backup(path, records)

    assert written == 3


def test_write_backup_then_read_backup_round_trips_records(tmp_path):
    from rewrite_milvus_doc_type import read_backup, write_backup

    records = _make_records(2)
    records[0]["sparse_embedding"] = {"1023": 0.03125}
    path = tmp_path / "WS_001.jsonl"

    write_backup(path, records)
    restored = read_backup(path)

    assert restored == records
    assert all(isinstance(k, str) for k in restored[0]["sparse_embedding"])


def test_write_backup_creates_missing_parent_directory(tmp_path):
    from rewrite_milvus_doc_type import write_backup

    path = tmp_path / "missing" / "nested" / "WS_001.jsonl"
    assert not path.parent.exists()

    write_backup(path, _make_records(1))

    assert path.exists()


# ── pymilvus 반환 타입 방어 ───────────────────────────────────────

class _NumpyLikeScalar:
    """numpy.float32 대역 — float 서브클래스가 아니라 float() 로만 변환된다."""

    def __init__(self, value: float):
        self._value = value

    def __float__(self) -> float:
        return self._value


def _milvus_row() -> dict:
    """Milvus query 가 돌려주는 1행 모양(백업 레코드 이전 단계)."""
    return {
        "chunk_id": "WS_001__0000",
        "book_id": "WS_001",
        "chunk_idx": 0,
        "section_idx": 0,
        "text": "본문 | 파이프가 들어간 텍스트",
        "page_start": 1,
        "page_end": 2,
        "doc_type": "paper",
        "pub_date": "1917",
        "publisher": "출판사",
        "corporate_author": "기관",
        "kdc": "813.6",
        "embedding": [0.5, -0.25],
        "sparse_embedding": {7: 0.5},
    }


def test_row_to_record_casts_embedding_elements_to_plain_float():
    """list() 로 감싸는 것만으로는 부족하다 — 원소가 numpy 스칼라면 json.dumps 가 죽는다."""
    from rewrite_milvus_doc_type import row_to_record

    row = _milvus_row()
    row["embedding"] = [_NumpyLikeScalar(0.5), _NumpyLikeScalar(-0.25)]
    record = row_to_record(row, SCALAR_NAMES)

    assert all(type(x) is float for x in record["embedding"])
    assert record["embedding"] == [0.5, -0.25]
    json.dumps(record)


def test_row_to_record_casts_sparse_values_to_plain_float():
    from rewrite_milvus_doc_type import row_to_record

    row = _milvus_row()
    row["sparse_embedding"] = {7: _NumpyLikeScalar(0.5)}
    record = row_to_record(row, SCALAR_NAMES)

    assert all(type(v) is float for v in record["sparse_embedding"].values())
    json.dumps(record)


def test_row_to_record_preserves_text_verbatim():
    """구분자가 값 안에 있어도 재가공하지 않는다."""
    from rewrite_milvus_doc_type import row_to_record

    record = row_to_record(_milvus_row(), SCALAR_NAMES)
    assert record["text"] == "본문 | 파이프가 들어간 텍스트"
```
