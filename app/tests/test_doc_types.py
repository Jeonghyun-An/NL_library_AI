"""detect_doc_type — genre/KDC/제목 기반 문서 유형 판별 (KCI 회귀 방지)."""
from domains.nl_library.doc_types import detect_doc_type


def test_kci_paper_by_genre_regardless_of_source_format():
    """KCI 논문(source_format='KCI', kdc 없음)도 genre=paper면 paper로 분류."""
    meta = {"source_format": "KCI", "genre": "paper", "kdc": None,
            "title": "코스닥시장 가격제한폭 변화가 주가지수 변동성에 미치는 영향"}
    assert detect_doc_type(meta) == "paper"


def test_pdf_paper_by_genre():
    assert detect_doc_type({"source_format": "PDF", "genre": "thesis"}) == "paper"


def test_literature_by_kdc():
    assert detect_doc_type({"kdc": "813.7", "genre": "book"}) == "literature"


def test_policy_by_kdc():
    assert detect_doc_type({"kdc": "330", "genre": "book"}) == "policy"


def test_policy_by_title_keyword():
    assert detect_doc_type({"title": "국가재정법 시행령", "genre": "book"}) == "policy"


def test_default_book():
    assert detect_doc_type({"title": "평범한 소설", "genre": "book", "kdc": None}) == "book"
