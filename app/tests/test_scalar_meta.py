"""build_scalar_meta — 프로파일 스칼라 필드 정의 → Milvus 스칼라 값 dict."""
from types import SimpleNamespace

from domains.base import MilvusScalarField, build_scalar_meta


def test_build_scalar_meta_from_columns_and_doc_type():
    fields = [
        MilvusScalarField("publisher", max_length=512),
        MilvusScalarField("corporate_author", max_length=512),
        MilvusScalarField("kdc", max_length=32),
    ]
    book = SimpleNamespace(
        publisher="한국출판",
        corporate_author="국립중앙도서관",
        kdc="813.7",
        doc_type="literature",
        extra={},
    )
    meta = build_scalar_meta(book, fields)
    assert meta == {
        "publisher": "한국출판",
        "corporate_author": "국립중앙도서관",
        "kdc": "813.7",
        "doc_type": "literature",
    }


def test_build_scalar_meta_from_extra_and_none_defaults():
    fields = [
        MilvusScalarField("publisher", max_length=512),
        MilvusScalarField("journal", max_length=256, source="ext.journal"),
    ]
    book = SimpleNamespace(publisher=None, doc_type=None, extra={"journal": "한국학술지"})
    meta = build_scalar_meta(book, fields)
    assert meta["publisher"] == ""          # None → 빈 문자열
    assert meta["journal"] == "한국학술지"   # ext.* → extra에서
    assert meta["doc_type"] == ""           # doc_type 없음 → 빈 문자열


def test_build_scalar_meta_missing_extra_key():
    fields = [MilvusScalarField("vol", max_length=32, source="ext.vol_issue")]
    book = SimpleNamespace(doc_type="paper", extra={})
    meta = build_scalar_meta(book, fields)
    assert meta["vol"] == ""
    assert meta["doc_type"] == "paper"
