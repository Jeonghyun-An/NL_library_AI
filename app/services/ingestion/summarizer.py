import re
import httpx
from core.config import get_settings


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
        "서술적 줄거리보다 '이 대목이 다루는 것'과 '독자가 느끼는 것' 중심으로\n"
        "300자 내외로 작성하세요. 유사한 감성·주제로 이 작품을 찾을 독자의\n"
        "검색어가 자연스럽게 포함되도록 하세요.\n"
        "요약 외 다른 말은 하지 마세요."
    ),
    "book": (
        "당신은 의미 기반 도서 검색 전문가입니다.\n"
        "주어진 도서 섹션에서 다음을 추출하세요:\n"
        "- 저자가 이 섹션에서 답하려는 핵심 질문과 주장\n"
        "- 사용된 개념·이론·키워드\n"
        "- 실제 적용 맥락이나 사례\n"
        "- 이 내용에 관심 있는 독자가 자연스럽게 떠올릴 연관 주제\n"
        "300자 내외로 작성하세요. 이 섹션을 검색할 독자의 표현과\n"
        "키워드가 자연스럽게 포함되도록 하세요.\n"
        "요약 외 다른 말은 하지 마세요."
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
) -> str:
    cfg = get_settings()
    system = _SECTION_SYSTEMS.get(doc_type, _SECTION_SYSTEMS["book"])
    payload = {
        "model": cfg.VLLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _SECTION_PROMPT.format(
                title=book_title,
                text=section_text,
            )},
        ],
        "max_tokens": 512,
        "temperature": 0.1,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{cfg.VLLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


# ── 도서 요약 프롬프트 ───────────────────────────────────────
_BOOK_FROM_SECTIONS_SYSTEMS = {
    "literature": (
        "당신은 의미 기반 문학 검색 전문가입니다.\n"
        "섹션별 요약들을 종합하여 이 작품을 검색할 독자에게 최적화된 요약을 작성하세요.\n"
        "포함할 내용:\n"
        "- 작품 전체를 관통하는 핵심 주제와 모티프 (추상적 개념으로 표현)\n"
        "- 주인공의 내적 여정과 심리적 변화 궤적\n"
        "- 작품의 감정적·정서적 분위기 (예: 냉소적, 서정적, 압도적, 잔잔한)\n"
        "- 사회·문화적 맥락과 작가의 문제의식\n"
        "- 독자가 이 작품을 통해 느끼거나 얻게 되는 것\n"
        "줄거리 요약이 아닌 '이 작품이 무엇을 다루는가'를 중심으로 600자 내외로 작성하세요.\n"
        "비슷한 감성이나 주제로 이 작품을 찾을 독자의 검색어가 자연스럽게 포함되도록 하세요.\n"
        "요약 외 다른 말은 하지 마세요."
    ),
    "book": (
        "당신은 의미 기반 도서 검색 전문가입니다.\n"
        "섹션별 요약들을 종합하여 이 도서를 검색할 독자에게 최적화된 요약을 작성하세요.\n"
        "포함할 내용:\n"
        "- 저자가 이 책을 통해 답하려는 핵심 질문과 중심 주장\n"
        "- 책에서 다루는 주요 개념·이론·방법론\n"
        "- 독자가 얻어가는 핵심 인사이트\n"
        "- 어떤 독자에게 유용한지 (관심 분야, 문제 상황)\n"
        "- 연관 분야와 유사 주제 키워드\n"
        "600자 내외로 작성하세요.\n"
        "이 책을 찾을 독자의 검색 표현이 자연스럽게 포함되도록 하세요.\n"
        "요약 외 다른 말은 하지 마세요."
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
) -> str:
    cfg = get_settings()
    system = _BOOK_FROM_SECTIONS_SYSTEMS.get(doc_type, _BOOK_FROM_SECTIONS_SYSTEMS["book"])
    combined = "\n\n".join(
        f"[섹션 {i + 1}] {s}" for i, s in enumerate(section_summaries) if s
    )
    payload = {
        "model": cfg.VLLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _BOOK_FROM_SECTIONS_PROMPT.format(
                title=title,
                author=author,
                section_summaries=combined,
            )},
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{cfg.VLLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
