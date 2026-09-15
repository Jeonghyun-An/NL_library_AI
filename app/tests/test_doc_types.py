"""test_doc_types.py — 문서 유형 판정 단위 테스트."""
from domains.nl_library.doc_types import detect_doc_type


# ── PDF 자동추출 genre 불신 ─────────────────────────────────────

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
