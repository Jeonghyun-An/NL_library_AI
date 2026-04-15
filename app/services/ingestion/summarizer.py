import re
import httpx
from core.config import get_settings


# ── 문서 유형 판별 ───────────────────────────────────────────
_POLICY_TITLE_KEYWORDS = [
    "법", "령", "규정", "고시", "지침", "매뉴얼", "조달", "입찰",
    "계약", "공고", "훈령", "예규", "시행", "규칙", "조례",
]
_LITERATURE_TITLE_KEYWORDS = ["소설", "시집", "수필", "문학", "동화", "희곡"]


def detect_doc_type(kdc: str | None, title: str | None) -> str:
    """
    KDC 코드 + 제목 키워드로 문서 유형 판별

    Returns:
        "literature" : 문학/소설 (KDC 800~899)
        "policy"     : 정책/법령/행정 (KDC 320~359 또는 제목 키워드)
        "general"    : 그 외 일반 문서
    """
    if kdc:
        digits = re.sub(r"[^0-9]", "", kdc)[:3]
        if digits:
            n = int(digits)
            if 800 <= n <= 899:
                return "literature"
            if 320 <= n <= 359:
                return "policy"

    if title:
        t = title
        if any(k in t for k in _POLICY_TITLE_KEYWORDS):
            return "policy"
        if any(k in t for k in _LITERATURE_TITLE_KEYWORDS):
            return "literature"

    return "general"


# ── 섹션 요약 프롬프트 (유형별) ──────────────────────────────
_SECTION_SYSTEMS = {
    "literature": (
        "당신은 문학 전문 사서입니다.\n"
        "주어진 소설·문학 작품의 섹션을 읽고 핵심 사건, 인물의 행동과 심리 변화,\n"
        "문체적 특징을 포함하여 300자 내외의 한국어로 요약하세요.\n"
        "요약 외 다른 말은 하지 마세요."
    ),
    "policy": (
        "당신은 행정·법령 문서 전문가입니다.\n"
        "주어진 정책·법령 문서의 섹션을 읽고 조항의 목적, 주요 규정 내용,\n"
        "적용 범위, 핵심 정의 및 용어를 포함하여 300자 내외의 한국어로 요약하세요.\n"
        "요약 외 다른 말은 하지 마세요."
    ),
    "general": (
        "당신은 도서관 사서입니다.\n"
        "주어진 문서 섹션을 읽고 핵심 주제, 주요 논점, 등장 개념을 포함하여\n"
        "300자 내외의 한국어로 풍부하게 요약하세요.\n"
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
    doc_type: str = "general",
) -> str:
    cfg = get_settings()
    system = _SECTION_SYSTEMS.get(doc_type, _SECTION_SYSTEMS["general"])
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


# ── 도서 요약 프롬프트 (유형별) ──────────────────────────────
_BOOK_FROM_SECTIONS_SYSTEMS = {
    "literature": (
        "당신은 문학 전문 사서입니다.\n"
        "주어진 섹션별 요약들을 종합하여 독자가 작품을 이해하고 유사 작품을 찾을 수 있도록\n"
        "핵심 주제, 문체, 감정 톤, 주요 등장인물, 서사 구조, 작가의 메시지를 포함한\n"
        "600자 내외의 한국어 작품 요약을 작성하세요.\n"
        "요약 외 다른 말은 하지 마세요."
    ),
    "policy": (
        "당신은 행정·법령 문서 전문가입니다.\n"
        "주어진 섹션별 요약들을 종합하여 문서의 목적, 주요 규정 사항,\n"
        "적용 대상 및 범위, 핵심 조항, 시행 관련 정보를 포함한\n"
        "600자 내외의 한국어 문서 요약을 작성하세요.\n"
        "요약 외 다른 말은 하지 마세요."
    ),
    "general": (
        "당신은 도서관 사서입니다.\n"
        "주어진 섹션별 요약들을 종합하여 독자가 내용을 이해하고 유사 자료를 찾을 수 있도록\n"
        "핵심 주제, 주요 내용과 논점, 저자의 관점, 독자에게 유용한 정보를 포함한\n"
        "600자 내외의 한국어 요약을 작성하세요.\n"
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
    doc_type: str = "general",
) -> str:
    cfg = get_settings()
    system = _BOOK_FROM_SECTIONS_SYSTEMS.get(doc_type, _BOOK_FROM_SECTIONS_SYSTEMS["general"])
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
