# round03 — 문학 41편 doc_type 오분류 교정 + 재발방지 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 위키문헌·공유마당 문학 41편의 Milvus `doc_type` 을 `paper` → `literature` 로 안전하게 재기록하고, 같은 오분류가 재발하지 않도록 판정 로직과 인덱싱 가드를 고친다.

**Architecture:** Milvus 에는 부분 갱신이 없으므로 문서 단위로 `query(임베딩 포함) → 백업 → delete → insert(doc_type 만 교체)` 를 돈다. 백업은 호스트 바인드 마운트에 JSONL 로 남겨 `--restore` 로 되돌린다. 재발방지는 2층 — 적재 잡이 `params.doc_type` 을 명시하는 운영 절차와, 명시가 없을 때 PDF 자동추출 `genre` 를 학술 유형 근거로 쓰지 않는 코드 가드다.

**Tech Stack:** Python 3.11 · pymilvus 2.4.6 · SQLAlchemy(sync) · pytest · Docker Compose

**설계 문서:** `docs/superpowers/specs/2026-09-15-round03-doc-type-reindex-design.md`

---

## 사전 지식 (이 코드베이스를 처음 보는 사람용)

**테스트 실행.** 항상 `app/` 에서 돈다. `app/tests/conftest.py` 가 `app/` 을 `sys.path` 에 넣어 컨테이너의 `/app` 과 임포트 경로를 맞춘다 — 그래서 테스트 코드는 `from services...`, `from domains...` 로 쓴다.

```bash
cd app && python -m pytest tests/ -q
```

**Milvus 컬렉션 스키마** (`app/services/ingestion/indexer.py:66`). 필드 순서가 곧 insert 데이터의 컬럼 순서다:

```
chunk_id(PK) · book_id · chunk_idx · section_idx · text · page_start · page_end
  · <스칼라들>  ← _scalar_field_specs() 순서: doc_type, pub_date, publisher, corporate_author, kdc
  · embedding(FLOAT_VECTOR) · sparse_embedding(SPARSE_FLOAT_VECTOR)
```

`_scalar_field_specs()` = `_CORE_SCALAR`(doc_type, pub_date) + 프로파일 스칼라(publisher, corporate_author, kdc). `pub_date` 는 코어로 승격돼 프로파일 쪽에서 중복 제거된다.

**주석 표준** (`docs/standards/coding-standard.md:33`). 기본은 주석 없음. 왜(why)가 non-obvious 할 때만 짧게 단다. **현재 작업·이슈·라운드 번호를 참조하는 주석은 쓰지 않는다** — 사건 경위는 spec 과 완료노트에 적고, 코드에는 비자명한 이유만 남긴다.

**커밋 규칙** (`GIT_WORKFLOW.md:42`). `[Type] 설명` 한국어 한 줄. Type 은 `Feat`·`Fix`·`Docs`·`Chore`·`Refactor`·`Test`. **`Co-Authored-By` 트레일러는 넣지 않는다.**

**작업 브랜치.** `fix/round03-doc-type-reindex` (이미 생성·커밋 3개 존재).

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `app/domains/nl_library/doc_types.py` (수정) | 문서 유형 판정. PDF 자동추출 `genre` 불신 규칙 추가 |
| `app/services/ingestion/stages.py` (수정) | 임베딩 단계에 빈 본문 가드 추가 |
| `scripts/recovery/rewrite_milvus_doc_type.py` (신규) | 재기록 도구. 순수 변환 함수 + I/O 오케스트레이션 |
| `app/tests/test_doc_types.py` (교체) | 판정 로직 단위 테스트. 기존 KCI 회귀 테스트 6개가 있던 파일을 상위집합으로 교체 |
| `app/tests/test_embed_index_guard.py` (신규) | 빈 본문 가드 단위 테스트 |
| `app/tests/test_rewrite_milvus_doc_type.py` (신규) | 재기록 도구 순수 함수 단위 테스트 |
| `docs/ops/bulk_ingest_runbook.md` (수정) | 카탈로그 없는 코퍼스 적재 절차 |

재기록 도구는 **순수 변환 함수**(직렬화·컬럼 조립)와 **I/O 오케스트레이션**(Milvus·Postgres·파일)을 한 파일 안에서 분리한다. 순수 함수만 단위 테스트하고, I/O 는 dry-run 과 운영 검증으로 확인한다. 스크립트가 200줄 안쪽이라 파일을 쪼갤 이유는 없다.

---

## Task 1: `detect_doc_type` — PDF 자동추출 genre 불신

**Files:**
- Test: `app/tests/test_doc_types.py` (교체 — 기존 KCI 회귀 테스트 6개가 들어있다. 아래 내용이 그 상위집합이라 통째로 바꾼다. 유일하게 사라지는 `test_pdf_paper_by_genre` 는 이 Task 가 의도적으로 뒤집는 동작이다)
- Test: `app/tests/test_domains.py` (수정 — `detect_doc_type` parametrize 3건이 옛 동작을 전제한다)
- Modify: `app/domains/nl_library/doc_types.py:36-39`

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_doc_types.py` 를 아래 내용으로 교체한다:

```python
"""test_doc_types.py — 문서 유형 판정 단위 테스트."""
from domains.nl_library.doc_types import detect_doc_type


# ── PDF 자동추출 genre 불신 ──────────────────────────────────────

def test_pdf_autoextract_genre_paper_is_not_trusted():
    """카탈로그 없이 적재된 문서의 genre 는 LLM 추측이라 paper 근거로 쓰지 않는다.

    paper 오판정은 도서 필터(doc_type != "paper")에서 문서를 통째로 탈락시키는데,
    논문 필터와 달리 도서 필터에는 ID 기반 폴백이 없어 복구 불가능한 실종이 된다.
    """
    meta = {"source_format": "PDF", "genre": "paper", "title": "개척자"}
    assert detect_doc_type(meta) == "book"


def test_pdf_autoextract_genre_thesis_is_not_trusted():
    meta = {"source_format": "PDF", "genre": "thesis", "title": "무정"}
    assert detect_doc_type(meta) == "book"


def test_pdf_autoextract_genre_report_is_not_trusted():
    meta = {"source_format": "PDF", "genre": "report", "title": "동백꽃"}
    assert detect_doc_type(meta) == "book"


def test_pdf_autoextract_still_uses_kdc():
    """genre 를 무시해도 KDC 가 있으면 그건 신뢰한다."""
    meta = {"source_format": "PDF", "genre": "paper", "kdc": "813.6", "title": "날개"}
    assert detect_doc_type(meta) == "literature"


# ── 카탈로그 출신 genre 는 계속 신뢰 ──────────────────────────────

def test_catalog_genre_paper_still_wins():
    """KCI 로더가 넣은 genre 는 실제 카탈로그 값이라 그대로 신뢰한다."""
    meta = {"source_format": "KCI", "genre": "paper", "title": "초소수성 표면 제작"}
    assert detect_doc_type(meta) == "paper"


def test_marc_genre_thesis_still_wins():
    meta = {"source_format": "MARC", "genre": "thesis", "title": "宋純의 詩歌文學研究"}
    assert detect_doc_type(meta) == "paper"


def test_genre_paper_without_source_format_still_wins():
    """source_format 이 없으면 PDF 자동추출이 아니므로 기존 동작 유지."""
    meta = {"genre": "paper", "title": "제목"}
    assert detect_doc_type(meta) == "paper"


# ── 기존 분기 회귀 ────────────────────────────────────────────────

def test_kdc_literature_range():
    assert detect_doc_type({"kdc": "811.6", "title": "진달래꽃"}) == "literature"


def test_kdc_policy_range():
    assert detect_doc_type({"kdc": "327.1", "title": "재정 보고서"}) == "policy"


def test_policy_title_keyword():
    assert detect_doc_type({"title": "공공조달 계약 지침"}) == "policy"


def test_default_is_book():
    assert detect_doc_type({"title": "세계화와 개방정책"}) == "book"
```

- [ ] **Step 2: 실패 확인**

```bash
cd app && python -m pytest tests/test_doc_types.py -q
```

기대: `test_pdf_autoextract_genre_paper_is_not_trusted` 등 4개가 FAIL. 실패 메시지는 `assert 'paper' == 'book'` 형태. 나머지 7개는 PASS(기존 동작).

- [ ] **Step 3: 최소 구현**

`app/domains/nl_library/doc_types.py` 에서 아래 블록을

```python
    kdc = meta.get("kdc")
    title = meta.get("title")
    genre = meta.get("genre")

    # genre가 학술 유형이면 source_format 무관하게 paper.
    # (KCI 로더는 source_format="KCI" + genre="paper", PDF 자동추출은 source_format="PDF" + genre 판별)
    if genre in ("paper", "thesis", "report"):
        return "paper"
```

이렇게 바꾼다:

```python
    kdc = meta.get("kdc")
    title = meta.get("title")
    genre = meta.get("genre")
    source_format = meta.get("source_format")

    # source_format="PDF" 는 카탈로그 없이 적재돼 genre 를 PDF 에서 자동추출(LLM 추측)한
    # 경우라 paper 판정 근거로 쓰지 않는다. 도서 필터에는 논문 필터의
    # `book_id like "KCI_FI%"` 같은 ID 폴백이 없어 paper 오판정이 복구 불가능하다.
    if genre in ("paper", "thesis", "report") and source_format != "PDF":
        return "paper"
```

docstring 의 `"paper"` 설명 줄도 함께 고친다:

```python
        "paper"      : 학술논문·학위논문·보고서 (카탈로그 출신 genre 기반 — PDF 자동추출 genre 는 제외)
```

- [ ] **Step 4: 통과 확인**

```bash
cd app && python -m pytest tests/test_doc_types.py -q
```

기대: `11 passed`

- [ ] **Step 5: 전체 회귀**

```bash
cd app && python -m pytest tests/ -q
```

기대: 실패 0. `app/tests/test_domains.py` 의 `test_detect_doc_type` parametrize 중 `{"source_format": "PDF", "genre": "paper"/"thesis"/"report"}` 3건이 옛 동작(`"paper"`)을 전제하므로 기대값을 `"book"` 으로 바꾼다.

로컬 환경에서는 `test_book_chat.py`·`test_build_manifest.py`·`test_loaders.py` 3개 모듈이 `FlagEmbedding`·`openpyxl` 미설치로 **수집(collect) 단계에서** 실패한다. 이 변경과 무관한 기존 상태이니, 부모 커밋에서도 동일하게 실패하는지 확인하고 넘어간다.

- [ ] **Step 6: 커밋**

```bash
git add app/tests/test_doc_types.py app/tests/test_domains.py app/domains/nl_library/doc_types.py
git commit -F - <<'MSG'
[Fix] round03 — PDF 자동추출 genre 로 doc_type=paper 판정하지 않도록 수정

카탈로그 없이 적재된 문서는 PDF 에서 자동추출한 genre 가 doc_type 을 정하는데,
그 값은 LLM 추측이다. paper 오판정은 도서 필터에 ID 폴백이 없어 문서를 도서
검색에서 완전히 실종시킨다(위키문헌·공유마당 문학 41편이 그 경우).
MSG
```

---

## Task 2: `run_embed_index` 빈 본문 가드

**Files:**
- Test: `app/tests/test_embed_index_guard.py` (신규)
- Modify: `app/services/ingestion/stages.py:479-520`

배경: `run_finalize` 가 성공한 문서의 추출 아티팩트를 지운다(`stages.py:803`). 그래서 이미 적재 완료된 문서에서 임베딩 단계만 다시 돌리면 `load_extraction_artifact` 가 `artifact_missing` 을 던지고, 현재 코드는 `full_text = ""` 로 조용히 진행한다. 그러면 청킹 결과 0개인 채로 `index_chunks` 가 `col.delete(book_id)` → 메타청크 1개만 insert 를 돌려 **기존 본문 청크가 전멸한다.**

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_embed_index_guard.py` 를 새로 만든다:

```python
"""test_embed_index_guard.py — 임베딩 단계 빈 본문 가드 테스트.

run_finalize 가 성공 문서의 추출 아티팩트를 지우므로, 적재 완료된 문서에서
임베딩 단계만 다시 돌리면 아티팩트가 없다. 이때 빈 본문으로 진행하면
index_chunks 가 book_id 기준 delete 후 insert 를 돌려 기존 청크가 전멸한다.
"""
from unittest.mock import MagicMock

import pytest

from services.ingestion import stages
from services.ingestion.stages import StageContext, StageError


def _patch_common(monkeypatch, book):
    """아티팩트 없음 + 주어진 book 한 건을 반환하는 DB 세션으로 고정."""
    monkeypatch.setattr(stages, "minio_client", lambda: MagicMock())

    def _missing(book_id, client):
        raise StageError("artifact_missing", "아티팩트 없음")

    monkeypatch.setattr(stages, "load_extraction_artifact", _missing)

    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = book
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: session)


def test_aborts_when_no_artifact_and_not_paper(monkeypatch):
    """문학 문서 + 아티팩트 없음 → 인덱스를 건드리기 전에 중단한다."""
    book = MagicMock(doc_type="literature", abstract=None, title="무정",
                     personal_author=None, corporate_author=None,
                     series_title=None, subject=None, keyword=None)
    _patch_common(monkeypatch, book)

    called = []
    monkeypatch.setattr(
        "services.ingestion.indexer.index_chunks",
        lambda *a, **kw: called.append(True),
    )

    with pytest.raises(StageError) as exc:
        stages.run_embed_index(StageContext(book_id="WS_001"))

    assert exc.value.error_group == "empty_body"
    assert called == [], "인덱스를 건드리기 전에 멈춰야 한다"


def test_aborts_when_paper_has_no_fallback_text(monkeypatch):
    """논문인데 abstract 도 제목도 없으면 폴백 텍스트를 못 만든다 → 중단."""
    book = MagicMock(doc_type="paper", abstract=None, title=None,
                     personal_author=None, corporate_author=None,
                     series_title=None, subject=None, keyword=None)
    _patch_common(monkeypatch, book)

    called = []
    monkeypatch.setattr(
        "services.ingestion.indexer.index_chunks",
        lambda *a, **kw: called.append(True),
    )

    with pytest.raises(StageError) as exc:
        stages.run_embed_index(StageContext(book_id="KCI_FI000000001"))

    assert exc.value.error_group == "empty_body"
    assert called == []


def test_aborts_when_artifact_text_is_whitespace_only(monkeypatch):
    """아티팩트가 있어도 내용이 공백뿐이면 중단한다.

    load_extraction_artifact 의 페이지 필터가 truthiness 기반이라 공백만 있는
    페이지 텍스트가 걸러지지 않는다. 청킹 단계에서야 빈 문자열이 돼 0청크가 된다.
    """
    book = MagicMock(doc_type="literature", abstract=None, title="동백꽃",
                     personal_author=None, corporate_author=None,
                     series_title=None, subject=None, keyword=None)
    _patch_common(monkeypatch, book)
    monkeypatch.setattr(stages, "load_extraction_artifact",
                        lambda book_id, client: ("   

  ", {}))

    called = []
    monkeypatch.setattr(
        "services.ingestion.indexer.index_chunks",
        lambda *a, **kw: called.append(True),
    )

    with pytest.raises(StageError) as exc:
        stages.run_embed_index(StageContext(book_id="GM_001"))

    assert exc.value.error_group == "empty_body"
    assert called == []
```

- [ ] **Step 2: 실패 확인**

```bash
cd app && python -m pytest tests/test_embed_index_guard.py -q
```

기대: 3개 모두 FAIL. 현재 코드는 `StageError` 를 던지지 않고 빈 본문으로 진행하려다 다른 지점에서 죽거나 `index_chunks` 를 호출한다.

- [ ] **Step 3: 최소 구현**

`app/services/ingestion/stages.py` 의 `run_embed_index` 안, 폴백 블록 바로 뒤(`sections_rows = (` 직전)에 가드를 넣는다. 현재 코드:

```python
                if fallback_parts:
                    full_text = " ".join(fallback_parts)
                    log.info(f"[{book_id}] PDF·abstract 없음 — 메타 필드로 최소 임베딩 ({len(full_text)}자)")
        sections_rows = (
```

이렇게 바꾼다:

```python
                if fallback_parts:
                    full_text = " ".join(fallback_parts)
                    log.info(f"[{book_id}] PDF·abstract 없음 — 메타 필드로 최소 임베딩 ({len(full_text)}자)")

        # index_chunks 는 book_id 기준 delete 후 insert 라, 빈 본문으로 진행하면
        # 기존 청크가 전부 사라진다. 인덱스를 건드리기 전에 멈춘다.
        # strip() 필수 — 아티팩트의 페이지 필터가 truthiness 기반이라 공백만 있는
        # 페이지 텍스트가 살아남고, 청킹 단계에서야 빈 문자열로 정규화된다.
        if not full_text.strip():
            raise StageError(
                "empty_body",
                "추출 아티팩트도 폴백 텍스트도 없다 — 빈 본문 인덱싱은 기존 청크를 전부 삭제한다",
            )

        sections_rows = (
```

- [ ] **Step 4: 통과 확인**

```bash
cd app && python -m pytest tests/test_embed_index_guard.py -q
```

기대: `3 passed`

- [ ] **Step 5: 전체 회귀**

```bash
cd app && python -m pytest tests/ -q
```

기대: 실패 0.

- [ ] **Step 6: 커밋**

```bash
git add app/tests/test_embed_index_guard.py app/services/ingestion/stages.py
git commit -F - <<'MSG'
[Fix] round03 — 임베딩 단계 빈 본문 가드 추가

run_finalize 가 성공 문서의 추출 아티팩트를 지우므로, 적재 완료 문서에서
임베딩 단계만 재실행하면 아티팩트가 없다. 지금까지는 빈 본문으로 조용히
진행해 index_chunks 의 delete+insert 로 기존 청크가 전멸했다. 인덱스를
건드리기 전에 StageError 로 중단한다.
MSG
```

---

## Task 3: 재기록 도구 — 순수 변환 함수

**Files:**
- Create: `scripts/recovery/rewrite_milvus_doc_type.py`
- Test: `app/tests/test_rewrite_milvus_doc_type.py` (신규)

이 Task 는 I/O 없는 변환 함수만 만든다. Milvus·Postgres 접근은 Task 4.

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_rewrite_milvus_doc_type.py` 를 새로 만든다. `scripts/` 는 `app/` 밖이라 `test_build_manifest.py` 와 같은 방식으로 경로를 넣는다:

```python
"""test_rewrite_milvus_doc_type.py — Milvus doc_type 재기록 도구 순수 함수 테스트."""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "recovery"
sys.path.insert(0, str(SCRIPTS_DIR))

from rewrite_milvus_doc_type import (  # noqa: E402
    SCALAR_ORDER,
    denormalize_sparse,
    normalize_sparse,
    records_to_insert_data,
    row_to_record,
)


def _row(chunk_idx=0, doc_type="paper"):
    return {
        "chunk_id": f"WS_001__{chunk_idx:04d}",
        "book_id": "WS_001",
        "chunk_idx": chunk_idx,
        "section_idx": 3,
        "text": "본문 | 파이프가 들어간 텍스트",
        "page_start": 1,
        "page_end": 2,
        "doc_type": doc_type,
        "pub_date": "1917",
        "publisher": "",
        "corporate_author": "",
        "kdc": "813.6",
        "embedding": [0.5, -0.25, 0.125],
        "sparse_embedding": {7: 0.5, 19: 0.25},
    }


# ── sparse 벡터 왕복 ──────────────────────────────────────────────

def test_normalize_sparse_makes_json_safe_keys():
    assert normalize_sparse({7: 0.5, 19: 0.25}) == {"7": 0.5, "19": 0.25}


def test_denormalize_sparse_restores_int_keys():
    assert denormalize_sparse({"7": 0.5, "19": 0.25}) == {7: 0.5, 19: 0.25}


def test_sparse_roundtrip_preserves_values():
    original = {0: 1.0, 1023: 0.03125}
    assert denormalize_sparse(normalize_sparse(original)) == original


# ── row → record ─────────────────────────────────────────────────

def test_row_to_record_keeps_all_schema_fields():
    rec = row_to_record(_row())
    for field in ("chunk_id", "book_id", "chunk_idx", "section_idx",
                  "text", "page_start", "page_end", "embedding"):
        assert field in rec
    for name in SCALAR_ORDER:
        assert name in rec


def test_row_to_record_preserves_text_verbatim():
    """text 를 다시 자르거나 정규화하지 않는다 — 읽은 값 그대로 되넣어야 한다."""
    rec = row_to_record(_row())
    assert rec["text"] == "본문 | 파이프가 들어간 텍스트"


def test_row_to_record_json_serializable():
    import json
    json.dumps(row_to_record(_row()))  # 예외가 나면 실패


# ── record → insert 컬럼 ──────────────────────────────────────────

def test_records_to_insert_data_column_order_matches_schema():
    records = [row_to_record(_row(0)), row_to_record(_row(1))]
    data = records_to_insert_data(records, override_doc_type="literature")
    # 고정 7개 + 스칼라 + dense + sparse
    assert len(data) == 7 + len(SCALAR_ORDER) + 2
    assert data[0] == ["WS_001__0000", "WS_001__0001"]
    assert data[1] == ["WS_001", "WS_001"]
    assert data[2] == [0, 1]


def test_records_to_insert_data_overrides_only_doc_type():
    records = [row_to_record(_row(0))]
    data = records_to_insert_data(records, override_doc_type="literature")
    doc_type_col = 7 + SCALAR_ORDER.index("doc_type")
    kdc_col = 7 + SCALAR_ORDER.index("kdc")
    assert data[doc_type_col] == ["literature"]
    assert data[kdc_col] == ["813.6"], "doc_type 외 스칼라는 건드리지 않는다"


def test_records_to_insert_data_without_override_keeps_original():
    """--restore 경로 — 백업에 담긴 doc_type 을 그대로 되넣는다."""
    records = [row_to_record(_row(0, doc_type="paper"))]
    data = records_to_insert_data(records, override_doc_type=None)
    doc_type_col = 7 + SCALAR_ORDER.index("doc_type")
    assert data[doc_type_col] == ["paper"]


def test_records_to_insert_data_sparse_has_int_keys():
    records = [row_to_record(_row(0))]
    data = records_to_insert_data(records, override_doc_type="literature")
    assert data[-1] == [{7: 0.5, 19: 0.25}]
```

- [ ] **Step 2: 실패 확인**

```bash
cd app && python -m pytest tests/test_rewrite_milvus_doc_type.py -q
```

기대: collection error — `ModuleNotFoundError: No module named 'rewrite_milvus_doc_type'`

- [ ] **Step 3: 최소 구현**

`scripts/recovery/rewrite_milvus_doc_type.py` 를 새로 만든다 (이 Task 에서는 순수 함수만):

```python
"""rewrite_milvus_doc_type.py — Milvus doc_type 스칼라 재기록

배경:
  카탈로그 없이 크롤링 적재된 위키문헌(WS_*)·공유마당(GM_*) 문학 41편이
  Milvus 스칼라에 doc_type='paper' 로 박혀 있다. 논문 검색을 오염시킬 뿐 아니라,
  도서 필터가 `doc_type != "paper"` 라서 도서 검색에서는 아예 실종된다.

  Milvus 에는 부분 갱신이 없어 문서 단위로 delete + insert 를 돈다. 임베딩을 다시
  만들지 않고 읽은 값을 그대로 되넣으므로 LLM·GPU 비용이 없다.

안전장치:
  처리 단위는 문서 1건. Milvus 에 트랜잭션이 없어 묶어봐야 의미가 없고, 문서 단위로
  끊으면 실패 피해가 그 1편에 갇힌다. delete 전에 전 청크를 JSONL 로 백업하고,
  백업 줄 수가 Milvus 청크 수와 다르면 그 문서는 건드리지 않는다.

실행 (앱 이미지에 scripts/ 가 없어 호스트 바인드 마운트 /app/data 경유.
      스크립트 파일로 실행하면 sys.path[0] 이 스크립트 디렉터리라 PYTHONPATH 가 필요하다):
  cp rewrite_milvus_doc_type.py /data/nl-lib/data/recovery/
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/rewrite_milvus_doc_type.py
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/rewrite_milvus_doc_type.py --apply
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/rewrite_milvus_doc_type.py --restore <백업디렉터리>
"""

# Milvus 스키마의 고정 앞부분 (indexer._build_schema 와 동일 순서)
FIXED_ORDER = [
    "chunk_id", "book_id", "chunk_idx", "section_idx",
    "text", "page_start", "page_end",
]

# 스칼라 필드 순서 — indexer._scalar_field_specs() 와 동일해야 한다.
# 코어(doc_type, pub_date) + nl_library 프로파일(publisher, corporate_author, kdc).
SCALAR_ORDER = ["doc_type", "pub_date", "publisher", "corporate_author", "kdc"]


def normalize_sparse(sparse) -> dict:
    """sparse 벡터를 JSON 안전하게 — 키를 문자열로. (JSON 객체 키는 문자열만 된다)"""
    return {str(k): float(v) for k, v in dict(sparse).items()}


def denormalize_sparse(sparse: dict) -> dict:
    """JSON 에서 읽은 sparse 벡터를 Milvus insert 형식으로 — 키를 정수로."""
    return {int(k): float(v) for k, v in sparse.items()}


def row_to_record(row: dict) -> dict:
    """Milvus query 결과 1행 → JSON 직렬화 가능한 백업 레코드.

    text 를 다시 자르거나 정규화하지 않는다. 읽은 값을 한 글자도 바꾸지 않고
    되넣는 것이 이 도구의 전제다.
    """
    rec = {name: row[name] for name in FIXED_ORDER}
    for name in SCALAR_ORDER:
        rec[name] = row.get(name, "")
    rec["embedding"] = list(row["embedding"])
    rec["sparse_embedding"] = normalize_sparse(row["sparse_embedding"])
    return rec


def records_to_insert_data(records: list[dict], override_doc_type: str | None) -> list[list]:
    """백업 레코드 목록 → Milvus insert 용 컬럼 지향 데이터.

    override_doc_type 이 None 이면 각 레코드의 원래 doc_type 을 쓴다 (--restore 경로).
    indexer.index_chunks 를 재사용하지 않는 이유: 그 함수는 chunk_id 를 재생성하고
    text 를 다시 16,000바이트로 자른다.
    """
    data = [[r[name] for r in records] for name in FIXED_ORDER]
    for name in SCALAR_ORDER:
        if name == "doc_type" and override_doc_type is not None:
            data.append([override_doc_type] * len(records))
        else:
            data.append([r[name] for r in records])
    data.append([r["embedding"] for r in records])
    data.append([denormalize_sparse(r["sparse_embedding"]) for r in records])
    return data
```

- [ ] **Step 4: 통과 확인**

```bash
cd app && python -m pytest tests/test_rewrite_milvus_doc_type.py -q
```

기대: `10 passed`

- [ ] **Step 5: 스칼라 순서가 실제 스키마와 일치하는지 검증**

`SCALAR_ORDER` 는 하드코딩이라 스키마와 어긋나면 데이터가 엉뚱한 컬럼에 들어간다. 실제 값과 대조한다:

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python -c "
from services.ingestion.indexer import _scalar_field_specs
print([n for n, _ in _scalar_field_specs()])
"
```

기대 출력: `['doc_type', 'pub_date', 'publisher', 'corporate_author', 'kdc']`

**다르면 `SCALAR_ORDER` 를 출력값에 맞추고 Task 3 의 테스트를 다시 돌린다.** Task 4 로 넘어가지 않는다.

- [ ] **Step 6: 커밋**

```bash
git add scripts/recovery/rewrite_milvus_doc_type.py app/tests/test_rewrite_milvus_doc_type.py
git commit -F - <<'MSG'
[Feat] round03 — Milvus doc_type 재기록 도구 순수 변환 함수

Milvus query 결과 ↔ JSON 백업 ↔ insert 컬럼 변환. sparse 벡터 키를 JSON 용
문자열과 insert 용 정수 사이에서 왕복시킨다. index_chunks 를 재사용하지 않는
이유는 그 함수가 chunk_id 를 재생성하고 text 를 다시 자르기 때문이다.
MSG
```

---

## Task 4: 재기록 도구 — 백업·재기록·복구 오케스트레이션

**Files:**
- Modify: `scripts/recovery/rewrite_milvus_doc_type.py`

I/O 계층이라 단위 테스트 대신 dry-run 과 운영 검증(Task 6)으로 확인한다.

- [ ] **Step 1: 구현 추가**

Task 3 에서 만든 파일 끝에 아래를 이어 붙인다:

```python
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKUP_ROOT = Path("/app/data/recovery/backup")
QUERY_PAGE = 1000

OUTPUT_FIELDS = FIXED_ORDER + SCALAR_ORDER + ["embedding", "sparse_embedding"]


def find_targets(db) -> list[tuple[str, str]]:
    """재기록 대상 → [(cnts_id, Postgres doc_type)].

    이번 사고에서 Milvus 메타청크로 역복원한 행만 본다. 전체 24만 행을 훑지 않는다.
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


def fetch_chunks(col, book_id: str) -> list[dict]:
    """해당 book_id 의 전 청크를 임베딩까지 읽는다. offset 페이징."""
    out: list[dict] = []
    offset = 0
    while True:
        page = col.query(
            expr=f'book_id == "{book_id}"',
            output_fields=OUTPUT_FIELDS,
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
    rows = col.query(expr=f'book_id == "{book_id}"', output_fields=["chunk_id"], limit=16384)
    return len(rows)


def backup_path(stamp: str, book_id: str) -> Path:
    return BACKUP_ROOT / f"doc_type_{stamp}" / f"{book_id}.jsonl"


def write_backup(path: Path, records: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def read_backup(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def rewrite_one(col, book_id: str, records: list[dict], doc_type: str | None) -> None:
    """delete → insert. 여기가 유일한 위험 구간이고, 백업은 이미 디스크에 있다."""
    col.delete(expr=f'book_id == "{book_id}"')
    col.insert(records_to_insert_data(records, override_doc_type=doc_type))
    col.flush()


def run(apply: bool) -> int:
    from db.postgres import SyncSessionLocal
    from services.ingestion.indexer import ensure_collection

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    col = ensure_collection()
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
        rows = fetch_chunks(col, cnts_id)
        records = [row_to_record(r) for r in rows]
        path = backup_path(stamp, cnts_id)
        written = write_backup(path, records)

        if written != expected:
            print(f"  [SKIP] {cnts_id} — 백업 {written} != Milvus {expected}, 건드리지 않는다")
            continue

        rewrite_one(col, cnts_id, records, pg_doc_type)

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
    files = sorted(Path(backup_dir).glob("*.jsonl"))
    if not files:
        print(f"백업 파일이 없다: {backup_dir}")
        return 1

    print(f"복구 대상: {len(files)}건")
    for path in files:
        book_id = path.stem
        records = read_backup(path)
        rewrite_one(col, book_id, records, None)   # 백업의 원래 doc_type 유지
        print(f"  [OK] {book_id} — 청크 {len(records):,} 복구")
    return 0


def main() -> int:
    if "--restore" in sys.argv:
        idx = sys.argv.index("--restore")
        if idx + 1 >= len(sys.argv):
            print("--restore <백업디렉터리> 형태로 경로를 지정한다")
            return 2
        return restore(sys.argv[idx + 1])
    return run(apply="--apply" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: import 가 깨지지 않는지 확인**

```bash
cd app && python -m pytest tests/test_rewrite_milvus_doc_type.py -q
```

기대: `10 passed` (Task 3 테스트가 여전히 통과 — 파일 끝에 붙인 코드가 순수 함수를 깨지 않았다)

- [ ] **Step 3: 전체 회귀**

```bash
cd app && python -m pytest tests/ -q
```

기대: 실패 0.

- [ ] **Step 4: 커밋**

```bash
git add scripts/recovery/rewrite_milvus_doc_type.py
git commit -F - <<'MSG'
[Feat] round03 — Milvus doc_type 재기록 오케스트레이션 (백업·검증·복구)

문서 단위로 query → JSONL 백업 → 줄 수 검증 → delete+insert → 사후 검증.
백업 줄 수가 Milvus 청크 수와 다르면 그 문서는 건드리지 않고, 사후 검증이
실패하면 남은 문서를 손대지 않고 중단한다. --restore 로 백업을 되돌린다.
MSG
```

---

## Task 5: 운영 절차 문서화

**Files:**
- Modify: `docs/ops/bulk_ingest_runbook.md`

코드 가드는 최악을 막을 뿐이다. 제대로 된 `doc_type` 은 적재 시 명시해야 나온다.

- [ ] **Step 1: 런북 확인**

```bash
grep -nE "^#{1,3} " docs/ops/bulk_ingest_runbook.md
```

목차를 보고 "적재 실행" 성격의 섹션을 찾는다. 없으면 문서 끝에 새 섹션으로 붙인다.

- [ ] **Step 2: 절차 추가**

해당 섹션에 아래를 넣는다:

```markdown
## 카탈로그 없는 코퍼스 적재 (필수 절차)

웹 크롤링처럼 **카탈로그 메타 적재를 거치지 않고 바로 인덱싱하는 코퍼스**는
잡 생성 시 `params.doc_type` 을 반드시 명시한다.

```json
{"doc_type": "literature", "skip_cover": true}
```

명시하지 않으면 `_ensure_book_and_doc_type`(`app/services/ingestion/stages.py:337`)이
PDF 에서 메타를 자동추출하고, 그때 LLM 이 찍은 `genre` 가 `doc_type` 을 정한다.
`params.doc_type` 은 판정 우선순위 1위라 자동추출이 개입할 여지를 없앤다.

**빠뜨리면 생기는 일** — round03 에서 위키문헌(`WS_*`)·공유마당(`GM_*`) 문학 41편이
`doc_type='paper'` 로 박혔다. 논문 검색을 오염시켰을 뿐 아니라, 도서 필터가
`doc_type != "paper"` 라서 「무정」·「진달래꽃」·「구운몽」이 **도서 검색에서 완전히
실종됐다.** 논문 필터에는 `book_id like "KCI_FI%"` ID 폴백이 있지만 도서 필터에는 없다.

코드 쪽 안전망(`source_format="PDF"` 의 `genre` 를 학술 유형 근거로 쓰지 않음)이
최악은 막지만, 그 경우 문서는 `book` 으로 떨어진다 — `literature` 나 `paper` 가
맞는 코퍼스라면 여기서 명시하는 것 외에 방법이 없다.

한 코퍼스 = 한 `doc_type` 이므로 잡 단위 지정으로 충분하다. 매니페스트 스키마에는
`doc_type` 필드가 없고, 넣을 필요도 없다.
```

- [ ] **Step 3: 커밋**

```bash
git add docs/ops/bulk_ingest_runbook.md
git commit -F - <<'MSG'
[Docs] round03 — 카탈로그 없는 코퍼스 적재 시 doc_type 명시 절차 추가

params.doc_type 을 빠뜨리면 PDF 자동추출 genre 가 doc_type 을 정하고,
paper 오판정 시 문서가 도서 검색에서 완전히 실종된다(문학 41편 사례).
MSG
```

---

## Task 6: 운영 실행 — dry-run → apply → 라이브 검증

**Files:** 없음 (운영 작업)

- [ ] **Step 1: 스크립트를 서버로 복사**

`scripts/` 는 앱 이미지에 없다. 호스트 바인드 마운트(`/data/nl-lib/data` → `/app/data`)를 쓴다.

```bash
mkdir -p /data/nl-lib/data/recovery && cp scripts/recovery/rewrite_milvus_doc_type.py /data/nl-lib/data/recovery/
```

- [ ] **Step 2: dry-run**

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/rewrite_milvus_doc_type.py
```

기대: `대상 후보: 41건`, `재기록 필요: 41건`, 문서별로 `Milvus 'paper' → Postgres 'literature'` 와 청크 수. 마지막 줄이 `dry-run — 아무것도 쓰지 않았다`.

**대상이 41건이 아니면 멈춘다.** `extra->>'restored_from' = 'milvus_meta_chunk'` 조건이 예상과 다른 행을 잡고 있다는 뜻이다.

- [ ] **Step 3: 반영**

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/rewrite_milvus_doc_type.py --apply
```

기대: 문서마다 `[OK] WS_001 — 청크 N · doc_type 'literature'`, 마지막에 `재기록 완료: 41건`.

`[FAIL]` 이 나오면 즉시 중단되고 복구 명령이 출력된다. 그 명령을 그대로 실행한 뒤 원인을 확인한다.

- [ ] **Step 4: 멱등 확인**

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/rewrite_milvus_doc_type.py
```

기대: `불일치 없음 — 할 일이 없다`

- [ ] **Step 5: 라이브 검증 — 도서 검색 (합격 기준)**

```bash
curl -s --max-time 240 -X POST "https://skovix.landsoft.co.kr/api/books/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"이광수 무정","mode":"book","top_k":5}' | head -c 600
```

기대: `books[]` 에 `WS_001` 이 포함되고 `book_info.title` 이 `무정`. **지금은 안 잡히는 것이 정상이며, 이게 이 라운드의 합격 기준이다.**

- [ ] **Step 6: 라이브 검증 — 논문 검색에서 빠졌는지**

```bash
curl -s --max-time 240 -X POST "https://skovix.landsoft.co.kr/api/papers/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"이광수 무정","mode":"book","top_k":5}' | head -c 600
```

기대: `books[]` 에 `WS_*` · `GM_*` 이 없다.

- [ ] **Step 7: 백업 정리 판단**

검증이 모두 통과하면 백업은 지워도 된다. 다만 라운드가 `main` 에 머지되기 전까지는 남겨둔다.

```bash
du -sh /data/nl-lib/data/recovery/backup/*
```

---

## Task 7: 라운드 종료 문서

**Files:**
- Create: `docs/roadmap/round03-완료노트.md`
- Modify: `docs/roadmap/00_status.md`
- Create: `docs/guides/round03/` (교본 — `GIT_WORKFLOW.md:49` 필수)

- [ ] **Step 1: 완료노트 작성**

템플릿 `docs/roadmap/_ROUND_COMPLETE_TEMPLATE.md` 를 따른다. 반드시 담을 것:

- **선행 사건** — 2026-09-14 `library_catalog` 전체 유실, 고아 72,601건, 복구 실적(spec §6-1 표 그대로)
- **이번 라운드 구현** — doc_type 재기록 + 재발방지 2건
- **이월 6건** — spec §7 그대로 (LLM 생성물 재생성 / 논문 2편 / OCR 품질 / ID 정규화 누수 / **Postgres 백업 부재** / **호스트 포트 직접 노출**)

- [ ] **Step 2: 00_status.md 갱신**

`최종 갱신` 날짜, `현재 상태`, `다음 할 일`, 라운드 이력 표에 round03 행 추가.

- [ ] **Step 3: 교본 작성**

`docs/guides/_TEMPLATE.md` 를 따라 `docs/guides/round03/` 에 작성. 발췌·플레이스홀더 금지 — 전 코드/문서를 클론코딩 가능하게 수록하고 면접식 Q&A 를 붙인다.

- [ ] **Step 4: 커밋**

```bash
git add docs/roadmap/round03-완료노트.md docs/roadmap/00_status.md docs/guides/round03/
git commit -F - <<'MSG'
[Docs] round03 — 완료노트·상태 갱신·교본 작성
MSG
```

- [ ] **Step 5: 리뷰 → 머지**

`GIT_WORKFLOW.md:39` 에 따라 `.claude/agents/code-reviewer.md` 서브에이전트 정적 리뷰 → 발견 수정 → **사용자 채팅 승인** → `dev` 머지. 라운드 종료(`dev→main` + push)는 `/round-finish` 스킬.

---

## 자체 검토 결과

**Spec 커버리지.** §3 재기록 흐름 → Task 3·4, §4-2 판정 수정 → Task 1, §4-2 운영 절차 → Task 5, §4-3 빈 본문 가드 → Task 2, §5 롤백 → Task 4 의 `restore()`, §6-2 단위 테스트 → Task 1·2·3, §6-3 운영 검증 → Task 6. 누락 없음.

**타입 일관성.** `SCALAR_ORDER` · `FIXED_ORDER` · `row_to_record` · `records_to_insert_data` · `normalize_sparse` · `denormalize_sparse` 의 이름과 시그니처가 Task 3 정의와 Task 4 사용처에서 일치한다. `records_to_insert_data(records, override_doc_type)` 는 Task 4 의 `rewrite_one` 에서 키워드로 넘긴다.

**알려진 취약점 — `SCALAR_ORDER` 하드코딩.** `_scalar_field_specs()` 를 import 하지 않고 순서를 복제했다. 스크립트가 앱 모듈 없이도 순수 함수를 테스트할 수 있게 하려는 의도지만, 프로파일 스칼라가 바뀌면 조용히 어긋나 **데이터가 엉뚱한 컬럼에 들어간다.** Task 3 Step 5 에서 실제 값과 대조하는 절차를 넣어 이 라운드에서는 막았다. 장기적으로는 `_scalar_field_specs()` 를 직접 쓰고 테스트에서 앱 모듈을 로드하는 쪽이 옳다 — 완료노트 이월 후보.
