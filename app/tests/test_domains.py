"""도메인 프로파일 레지스트리 + nl_library doc_type 판별 테스트."""
import pytest


# ── detect_doc_type (기존 summarizer 로직과 동일해야 함) ──────────
@pytest.mark.parametrize("meta,expected", [
    ({"source_format": "PDF", "genre": "paper"}, "paper"),
    ({"source_format": "PDF", "genre": "thesis"}, "paper"),
    ({"source_format": "PDF", "genre": "report"}, "paper"),
    ({"source_format": "PDF", "genre": "other"}, "book"),
    ({"kdc": "813.7"}, "literature"),
    ({"kdc": "800"}, "literature"),
    ({"kdc": "340.11"}, "policy"),
    ({"kdc": "320"}, "policy"),
    ({"kdc": "359"}, "policy"),
    ({"kdc": "360"}, "book"),
    ({"title": "조달청 입찰 규정 매뉴얼"}, "policy"),
    ({"title": "시행규칙 해설"}, "policy"),
    ({"kdc": "100", "title": "철학의 위안"}, "book"),
    ({}, "book"),
    # KDC가 우선, 제목 키워드는 후순위
    ({"kdc": "813", "title": "법과 문학"}, "literature"),
])
def test_detect_doc_type(meta, expected):
    from domains.nl_library.doc_types import detect_doc_type
    assert detect_doc_type(meta) == expected


# ── 프로파일 레지스트리 ───────────────────────────────────────────
def test_active_profile_is_nl_library():
    from domains import get_active_profile
    profile = get_active_profile()
    assert profile.name == "nl_library"
    assert set(profile.doc_types) == {"book", "paper", "literature", "policy"}
    assert profile.default_doc_type == "book"
    assert profile.prompts_path.is_dir()
    # 프로파일의 detect_doc_type이 도메인 함수와 연결되어 있어야 함
    assert profile.detect_doc_type({"kdc": "813"}) == "literature"


def test_unknown_profile_raises():
    from domains import _load_profile
    with pytest.raises(ModuleNotFoundError):
        _load_profile("no_such_domain")


# ── Milvus 스칼라 필드 선언 ──────────────────────────────────────
def test_nl_library_milvus_scalar_fields():
    from domains import get_active_profile
    profile = get_active_profile()
    names = [f.name for f in profile.milvus_scalar_fields]
    # 기존 indexer 스키마와 동일 집합 (pub_date는 코어 승격 예정이지만 전환 전까지 유지)
    assert names == ["publisher", "corporate_author", "pub_date", "kdc"]
