import re
import httpx
from core.config import get_settings


def _parse_summary_themes(text: str) -> tuple[str, list[str]]:
    """SUMMARY:/THEMES: 구조화 출력 파싱.

    LLM이 아래 두 포맷 중 하나로 출력하는 경우를 모두 처리:
      A) SUMMARY: 내용  (같은 줄)
      B) SUMMARY:\\n내용  (다음 줄)
    THEMES도 동일하게 처리.
    구조 없으면 전체를 summary로.
    """
    themes: list[str] = []
    text = text.strip()

    # ① THEMES 섹션 분리 — "THEMES:" 기준으로 앞(summary부)/뒤(themes부) 분할
    themes_split = re.split(r"\n*THEMES:\s*\n?", text, maxsplit=1)
    if len(themes_split) == 2:
        text, themes_raw = themes_split
        themes = [t.strip() for t in re.split(r"[,，\n]", themes_raw) if t.strip()][:20]
    else:
        # 같은 줄에 있는 구형 포맷 폴백
        m = re.search(r"^THEMES:\s*(.+)$", text, re.MULTILINE)
        if m:
            themes = [t.strip() for t in m.group(1).split(",") if t.strip()][:20]
            text = re.sub(r"^THEMES:.*$\n?", "", text, flags=re.MULTILINE)

    # ② SUMMARY: 접두어 제거 — 같은 줄 또는 다음 줄 모두 처리
    m = re.search(r"^SUMMARY:\s*\n?([\s\S]*)", text.strip(), re.MULTILINE)
    summary = m.group(1).strip() if m else text.strip()

    return summary, themes


# ── 문서 유형 판별 ───────────────────────────────────────────
# policy: 법령·행정·조달 문서 (예외적으로 섞이는 케이스)
# book  : 그 외 모든 도서 (소설·학술·인문·과학 등) — 기본값
_POLICY_KDC_RANGE = range(320, 360)  # 정치학·법학·행정학

_POLICY_TITLE_KEYWORDS = [
    "법", "령", "규정", "고시", "지침", "매뉴얼", "조달", "입찰",
    "계약", "공고", "훈령", "예규", "시행", "규칙", "조례",
]


def detect_doc_type(
    kdc: str | None,
    title: str | None,
    source_format: str | None = None,
    genre: str | None = None,
) -> str:
    """
    문서 유형 판별.

    Returns:
        "paper"      : 학술논문·학위논문·보고서 (PDF 자동추출 또는 genre 기반)
        "literature" : 문학 작품 (KDC 800~899)
        "policy"     : 법령·행정·조달 문서 (KDC 320~359 또는 제목 키워드)
        "book"       : 그 외 모든 도서 (기본값)
    """
    # PDF 자동추출 문서는 genre 값으로 판별
    if source_format == "PDF":
        if genre in ("paper", "thesis", "report"):
            return "paper"

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
    "paper": (
        "당신은 학술 문헌 검색 전문가입니다.\n"
        "주어진 논문·보고서 섹션에서 다음을 추출하세요:\n"
        "- 저자가 이 섹션에서 제시하는 핵심 주장·가설·발견\n"
        "- 사용된 연구 방법론·데이터·실험 조건\n"
        "- 주요 결과·수치·통계 (있는 경우)\n"
        "- 이 내용을 검색할 연구자가 쓸 법한 학술 용어·개념\n"
        "다음 형식으로 출력하세요:\n"
        "SUMMARY: (검색 가능성이 높은 학술 키워드를 포함한 300자 내외 요약)\n"
        "THEMES: (이 섹션의 핵심 연구 개념·방법론·키워드 5~8개, 쉼표 구분)"
    ),
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
        "max_tokens": 4000,
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
    "paper": (
        "당신은 학술 문헌 검색 전문가입니다.\n"
        "섹션별 요약들을 종합하여 이 논문·보고서의 전체 분석을 작성하세요.\n"
        "다음 형식으로 출력하세요:\n"
        "SUMMARY: (연구 목적·방법론·주요 발견·시사점, 관련 연구자가 검색할 "
        "학술 키워드 포함. 800자 내외)\n"
        "THEMES: (이 연구를 관통하는 핵심 개념·방법론·기여 키워드 8~10개, 쉼표 구분)"
    ),
    "literature": (
        "당신은 의미 기반 문학 검색 전문가입니다.\n"
        "섹션별 요약들을 종합하여 이 작품의 전체 분석을 작성하세요.\n"
        "다음 형식으로 출력하세요:\n"
        "SUMMARY: (줄거리 요약이 아닌 '이 작품이 무엇을 다루는가' 중심. "
        "주인공의 내적 여정, 심리 변화, 사회·문화적 맥락, 작가의 문제의식, "
        "비슷한 감성으로 찾을 독자의 검색어 포함. 800자 내외)\n"
        "THEMES: (작품 전체를 관통하는 핵심 심리·철학적 테마 8~10개, 쉼표 구분. "
        "예: 욕망, 억압, 자아 상실, 폭력성, 사회 규범 저항, 여성 정체성, 실존적 공포)"
    ),
    "book": (
        "당신은 의미 기반 도서 검색 전문가입니다.\n"
        "섹션별 요약들을 종합하여 이 도서의 전체 분석을 작성하세요.\n"
        "다음 형식으로 출력하세요:\n"
        "SUMMARY: (저자의 핵심 주장, 주요 개념·이론, 독자가 얻는 인사이트, "
        "어떤 독자에게 유용한지, 연관 주제 키워드 포함. 800자 내외)\n"
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
        "800자 내외로 작성하세요.\n"
        "요약 외 다른 말은 하지 마세요."
    ),
}

_BOOK_FROM_SECTIONS_PROMPT = """제목: {title}
저자/기관: {author}

[섹션별 요약]
{section_summaries}

위 내용을 바탕으로 전체 요약을 작성하세요."""


_INTRODUCTION_SYSTEM = """\
당신은 공공도서관의 베테랑 사서입니다.
독자가 이 책을 직접 손에 들기 전에, 어떤 책인지 자연스럽게 소개해 주세요.
책 전문가의 따뜻하고 진솔한 목소리로 작성하세요.

요구사항:
- "이 책은..." 또는 자연스러운 도입부로 시작
- 어떤 독자에게 이 책이 맞는지 구체적으로 언급
- 책이 다루는 핵심 주제나 이야기를 독자의 관심사와 연결
- 기대할 수 있는 경험·깨달음·감동을 담아 표현
- 딱딱한 목차식 나열은 피하고, 읽고 싶어지는 흐름으로 작성
- 한국어, 400~600자 내외
- SUMMARY: / THEMES: 형식 없이 소개글 본문만 출력\
"""

_INTRODUCTION_PROMPT = """제목: {title}
저자/기관: {author}
출판사: {publisher}
발행연도: {pub_date}

[섹션별 요약]
{section_summaries}

위 내용을 바탕으로 이 책의 독자 소개글을 작성하세요."""


async def generate_book_introduction(
    title: str,
    author: str,
    publisher: str,
    pub_date: str,
    section_summaries: list[str],
) -> str | None:
    """독자·사서 톤의 도서 소개글 생성. 실패 시 None 반환."""
    if not section_summaries:
        return None
    cfg = get_settings()
    combined = "\n\n".join(
        f"[섹션 {i + 1}] {s}" for i, s in enumerate(section_summaries) if s
    )
    payload = {
        "model": cfg.LLM_MODEL,
        "messages": [
            {"role": "system", "content": _INTRODUCTION_SYSTEM},
            {"role": "user", "content": _INTRODUCTION_PROMPT.format(
                title=title,
                author=author or "미상",
                publisher=publisher or "미상",
                pub_date=pub_date or "미상",
                section_summaries=combined,
            )},
        ],
        "max_tokens": 5000,
        "temperature": 0.5,
    }
    user_chars = len(payload["messages"][1]["content"])
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{cfg.LLM_BASE_URL}/chat/completions", json=payload)
        if resp.status_code >= 400:
            import logging
            logging.getLogger(__name__).error(
                f"[introduction] LLM {resp.status_code} — user={user_chars}자, body={resp.text[:500]}"
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip() or None


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
        "max_tokens": 5000,
        "temperature": 0.1,
    }
    user_chars = len(payload["messages"][1]["content"])
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{cfg.LLM_BASE_URL}/chat/completions", json=payload)
        if resp.status_code >= 400:
            import logging
            logging.getLogger(__name__).error(
                f"[book_summary] LLM {resp.status_code} — user={user_chars}자, body={resp.text[:500]}"
            )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
    if doc_type == "policy":
        return raw, []
    return _parse_summary_themes(raw)
