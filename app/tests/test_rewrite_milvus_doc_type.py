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
