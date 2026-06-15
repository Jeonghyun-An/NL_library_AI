"""PromptLibrary — 도메인 프롬프트 YAML 로딩/렌더링 단위 테스트."""
import textwrap
from pathlib import Path

import pytest

from services.prompts import PromptLibrary


def _write(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    _write(tmp_path / "greet.yaml", """\
        parser: plain
        params:
          max_tokens: 100
          temperature: 0.5
        system: |-
          기본 시스템 프롬프트
        user: |-
          안녕하세요 {{ name }}님
    """)
    _write(tmp_path / "greet.paper.yaml", """\
        parser: summary_themes
        params:
          max_tokens: 200
        system: |-
          논문용 시스템 프롬프트
        user: |-
          논문 {{ name }} 분석
    """)
    return tmp_path


def test_doc_type_variant_takes_precedence(prompts_dir):
    lib = PromptLibrary(prompts_dir)
    tpl = lib.get("greet", doc_type="paper")
    system, user, params = tpl.render(name="홍길동")
    assert system == "논문용 시스템 프롬프트"
    assert user == "논문 홍길동 분석"
    assert params["max_tokens"] == 200


def test_fallback_to_base_when_doc_type_variant_missing(prompts_dir):
    lib = PromptLibrary(prompts_dir)
    tpl = lib.get("greet", doc_type="literature")
    system, user, params = tpl.render(name="김철수")
    assert system == "기본 시스템 프롬프트"
    assert user == "안녕하세요 김철수님"
    assert params == {"max_tokens": 100, "temperature": 0.5}


def test_missing_prompt_raises(prompts_dir):
    lib = PromptLibrary(prompts_dir)
    with pytest.raises(FileNotFoundError):
        lib.get("nonexistent")


def test_parser_key_exposed(prompts_dir):
    lib = PromptLibrary(prompts_dir)
    assert lib.get("greet", doc_type="paper").parser == "summary_themes"
    assert lib.get("greet").parser == "plain"


def test_json_literal_braces_survive_render(tmp_path):
    """metadata_filter처럼 본문에 JSON 리터럴 {}가 있어도 깨지지 않아야 함 (Jinja2 채택 근거)."""
    _write(tmp_path / "mf.yaml", """\
        system: |-
          출력 형식: {"has_filter": true}
        user: |-
          검색어: {{ query }}
    """)
    lib = PromptLibrary(tmp_path)
    system, user, _ = lib.get("mf").render(query="최근 책")
    assert system == '출력 형식: {"has_filter": true}'
    assert user == "검색어: 최근 책"


def test_nl_library_prompts_exist_and_render():
    """실제 nl_library 도메인 프롬프트 11종이 존재하고 렌더 가능한지 확인."""
    real_dir = Path(__file__).resolve().parents[1] / "domains" / "nl_library" / "prompts"
    lib = PromptLibrary(real_dir)

    # 섹션 요약 — doc_type 4종 (기존 summarizer._SECTION_SYSTEMS와 동일해야 함)
    for dt in ("paper", "literature", "policy", "book"):
        tpl = lib.get("section_summary", doc_type=dt)
        system, user, params = tpl.render(title="테스트 도서", text="본문입니다")
        assert system.strip()
        assert "테스트 도서" in user and "본문입니다" in user
        assert params.get("max_tokens") == 4000

    # 섹션 요약 literature 시스템 프롬프트는 기존 문자열과 동일해야 함 (회귀 가드)
    sys_lit, _, _ = lib.get("section_summary", doc_type="literature").render(title="t", text="x")
    assert sys_lit.startswith("당신은 의미 기반 문학 검색 전문가입니다.")
    assert sys_lit.endswith("예: 욕망, 억압, 자아 상실, 폭력성, 사회 규범 저항)")

    # 도서 요약 4종
    for dt in ("paper", "literature", "policy", "book"):
        tpl = lib.get("book_summary", doc_type=dt)
        system, user, _ = tpl.render(title="t", author="a", section_summaries="[섹션 1] s")
        assert system.strip() and "[섹션별 요약]" in user

    # 단일 프롬프트들
    intro_s, intro_u, intro_p = lib.get("introduction").render(
        title="t", author="a", publisher="p", pub_date="2024", section_summaries="s")
    assert "베테랑 사서" in intro_s and intro_p.get("max_tokens") == 5000

    cover_s, cover_u, _ = lib.get("cover_prompt").render(
        title="t", author="a", kdc="800", themes="th", introduction="i", summary="s")
    assert "art director" in cover_s

    qr_s, qr_u, _ = lib.get("query_rewrite").render(query="채식주의자 같은 책")
    assert "도서관 검색 전문가" in qr_s and "채식주의자" in qr_u

    mf_s, mf_u, _ = lib.get("metadata_filter").render(
        today="2026-06-11", current_year=2026, query="최근 책")
    assert '"pub_year_from"' in mf_s and "2026" in mf_u

    bc_s, _, bc_p = lib.get("book_chat").render(
        title="t", author="a", pub_date=", 2024", summary="s", themes="th")
    assert "전담 독서 도우미" in bc_s and bc_p.get("max_tokens") == 10000
