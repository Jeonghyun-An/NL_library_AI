import re
import httpx
from core.config import get_settings


def _parse_summary_themes(text: str) -> tuple[str, list[str]]:
    """SUMMARY:/THEMES: 구조화 출력 파싱. 구조 없으면 전체를 summary로."""
    themes: list[str] = []
    themes_match = re.search(r"^THEMES:\s*(.+)$", text, re.MULTILINE)
    if themes_match:
        themes = [t.strip() for t in themes_match.group(1).split(",") if t.strip()][:8]
        text = re.sub(r"^THEMES:.*$\n?", "", text, flags=re.MULTILINE)
    summary_match = re.search(r"^SUMMARY:\s*(.*)", text, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else text.strip()
    return summary, themes


# ── 문서 유형 판별 ───────────────────────────────────────────
# policy: 법령·행정·조달 문서 (예외적으로 섞이는 케이스)
# book  : 그 외 모든 도서 (소설·학술·인문·과학 등) — 기본값
_POLICY_KDC_RANGE = range(320, 360)  # 정치학·법학·행정학

_POLICY_TITLE_KEYWORDS = [
    "법", "령", "규정", "고시", "지침", "매뉴얼", "조달", "입찰",
    "계약", "공고", "훈령", "예규", "시행", "규칙", "조례",
]


def detect_doc_type(kdc: str | None, title: str | None) -> str:
    """
    문서 유형 판별.

    Returns:
        "literature" : 문학 작품 (KDC 800~899)
        "policy"     : 법령·행정·조달 문서 (KDC 320~359 또는 제목 키워드)
        "book"       : 그 외 모든 도서 (기본값)
    """
    if kdc:
        digits = re.sub(r"[^0-9]", "", kdc)[:3]
        if digits:
            n = int(digits)
            if 800 <= n <= 899:
                return "literature"
            if n in _POLICY_KDC_RANGE:
                return "policy"

    if title and any(k in title for k in _POLICY_TITLE_KEYWORDS):
        return "policy"

    return "book"


# ── 섹션 요약 프롬프트 ───────────────────────────────────────
_SECTION_SYSTEMS = {
    "literature": (
        "당신은 의미 기반 문학 검색 전문가입니다.\n"
        "주어진 문학 작품 섹션에서 다음을 추출하세요:\n"
        "- 이 대목이 탐구하는 주제와 모티프 (예: 고독, 저항, 상실, 욕망)\n"
        "- 인물의 심리 상태·내적 갈등·감정 변화\n"
        "- 장면이 전달하는 분위기와 정서적 톤\n"
        "- 사건이나 이미지의 상징적 의미\n"
        "다음 형식으로 출력하세요:\n"
        "SUMMARY: (서술적 줄거리보다 '이 대목이 다루는 것'과 '독자가 느끼는 것' 중심으로 300자 내외)\n"
        "THEMES: (이 섹션의 핵심 심리·철학적 테마 5~8개, 쉼표 구분. 예: 욕망, 억압, 자아 상실, 폭력성, 사회 규범 저항)"
    ),
    "book": (
        "당신은 의미 기반 도서 검색 전문가입니다.\n"
        "주어진 도서 섹션에서 다음을 추출하세요:\n"
        "- 저자가 이 섹션에서 답하려는 핵심 질문과 주장\n"
        "- 사용된 개념·이론·키워드\n"
        "- 실제 적용 맥락이나 사례\n"
        "- 이 내용에 관심 있는 독자가 자연스럽게 떠올릴 연관 주제\n"
        "다음 형식으로 출력하세요:\n"
        "SUMMARY: (이 섹션을 검색할 독자의 표현과 키워드가 포함된 300자 내외 요약)\n"
        "THEMES: (이 섹션의 핵심 개념·주제 키워드 5~8개, 쉼표 구분)"
    ),
    "policy": (
        "당신은 행정·법령 문서 검색 전문가입니다.\n"
        "주어진 섹션에서 다음을 추출하세요:\n"
        "- 조항의 목적과 규율 대상\n"
        "- 핵심 의무·금지·허용 사항\n"
        "- 적용 범위와 예외 조건\n"
        "- 핵심 정의 및 용어\n"
        "300자 내외로 작성하세요.\n"
        "요약 외 다른 말은 하지 마세요."
    ),
}

_SECTION_PROMPT = """도서명/문서명: {title}

[섹션 본문]
{text}

위 섹션의 핵심 내용을 요약하세요."""


async def summarize_section(
    book_title: str,
    section_text: str,
    doc_type: str = "book",
) -> tuple[str, list[str]]:
    """섹션 요약 + 테마 키워드 동시 추출. returns (summary, themes)."""
    cfg = get_settings()
    system = _SECTION_SYSTEMS.get(doc_type, _SECTION_SYSTEMS["book"])
    payload = {
        "model": cfg.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _SECTION_PROMPT.format(
                title=book_title,
                text=section_text,
            )},
        ],
        "max_tokens": 600,
        "temperature": 0.1,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{cfg.LLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
    if doc_type == "policy":
        return raw, []
    return _parse_summary_themes(raw)


# ── 도서 요약 프롬프트 ───────────────────────────────────────
_BOOK_FROM_SECTIONS_SYSTEMS = {
    "literature": (
        "당신은 의미 기반 문학 검색 전문가입니다.\n"
        "섹션별 요약들을 종합하여 이 작품의 전체 분석을 작성하세요.\n"
        "다음 형식으로 출력하세요:\n"
        "SUMMARY: (줄거리 요약이 아닌 '이 작품이 무엇을 다루는가' 중심. "
        "주인공의 내적 여정, 심리 변화, 사회·문화적 맥락, 작가의 문제의식, "
        "비슷한 감성으로 찾을 독자의 검색어 포함. 600자 내외)\n"
        "THEMES: (작품 전체를 관통하는 핵심 심리·철학적 테마 8~10개, 쉼표 구분. "
        "예: 욕망, 억압, 자아 상실, 폭력성, 사회 규범 저항, 여성 정체성, 실존적 공포)"
    ),
    "book": (
        "당신은 의미 기반 도서 검색 전문가입니다.\n"
        "섹션별 요약들을 종합하여 이 도서의 전체 분석을 작성하세요.\n"
        "다음 형식으로 출력하세요:\n"
        "SUMMARY: (저자의 핵심 주장, 주요 개념·이론, 독자가 얻는 인사이트, "
        "어떤 독자에게 유용한지, 연관 주제 키워드 포함. 600자 내외)\n"
        "THEMES: (이 도서를 관통하는 핵심 개념·주제 키워드 8~10개, 쉼표 구분)"
    ),
    "policy": (
        "당신은 행정·법령 문서 검색 전문가입니다.\n"
        "섹션별 요약들을 종합하여 다음을 포함한 문서 요약을 작성하세요:\n"
        "- 문서의 제정 목적과 규율 대상\n"
        "- 주요 규정 사항과 핵심 조항\n"
        "- 적용 대상·범위·예외\n"
        "- 의무·금지·제재 내용\n"
        "- 시행 관련 정보\n"
        "600자 내외로 작성하세요.\n"
        "요약 외 다른 말은 하지 마세요."
    ),
}

_BOOK_FROM_SECTIONS_PROMPT = """제목: {title}
저자/기관: {author}

[섹션별 요약]
{section_summaries}

위 내용을 바탕으로 전체 요약을 작성하세요."""


async def summarize_book_from_sections(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
) -> tuple[str, list[str]]:
    """전체 도서 요약 + 테마 키워드 생성. returns (summary, themes)."""
    cfg = get_settings()
    system = _BOOK_FROM_SECTIONS_SYSTEMS.get(doc_type, _BOOK_FROM_SECTIONS_SYSTEMS["book"])
    combined = "\n\n".join(
        f"[섹션 {i + 1}] {s}" for i, s in enumerate(section_summaries) if s
    )
    payload = {
        "model": cfg.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _BOOK_FROM_SECTIONS_PROMPT.format(
                title=title,
                author=author,
                section_summaries=combined,
            )},
        ],
        "max_tokens": 1200,
        "temperature": 0.1,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{cfg.LLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
    if doc_type == "policy":
        return raw, []
    return _parse_summary_themes(raw)
