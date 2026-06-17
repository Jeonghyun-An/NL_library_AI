"""
summarizer.py — 섹션/도서 요약·테마·소개글 생성

프롬프트는 도메인 프로파일의 YAML 템플릿(domains/{D}/prompts/)에서 로드한다.
doc_type 판별 로직은 domains/{D}/doc_types.py 로 이동 (아래 shim 으로 호환 유지).
"""
import re
import httpx
from core.config import get_settings
from services.prompts import get_prompt, PromptTemplate


def _parse_summary_themes(text: str) -> tuple[str, list[str]]:
    """SUMMARY:/THEMES: 구조화 출력 파싱."""
    themes: list[str] = []
    text = text.strip()

    # ① THEMES 섹션 분리
    themes_split = re.split(r"\n*THEMES:\s*\n?", text, maxsplit=1)
    if len(themes_split) == 2:
        text, themes_raw = themes_split
        themes = [t.strip() for t in re.split(r"[,，\n]", themes_raw) if t.strip()][:20]
    else:
        m = re.search(r"^THEMES:\s*(.+)$", text, re.MULTILINE)
        if m:
            themes = [t.strip() for t in m.group(1).split(",") if t.strip()][:20]
            text = re.sub(r"^THEMES:.*$\n?", "", text, flags=re.MULTILINE)

    # ② SUMMARY: 접두어 제거 (같은 줄 / 다음 줄 모두)
    text = text.strip()
    m = re.match(r"SUMMARY:\s*\n?", text)
    if m:
        text = text[m.end():]

    # ③ LLM이 SUMMARY 안에 내장한 "검색어:" 레이블 섹션 제거
    #    (예: "비슷한 감성으로 찾을 독자의 검색어: ..." → themes로 흡수 후 본문에서 제거)
    kw_pattern = re.compile(
        r"\n+(?:비슷한 감성으로 찾을 독자의 검색어|관련 검색어|검색어)\s*:\s*([\s\S]+)$"
    )
    km = kw_pattern.search(text)
    if km:
        if not themes:
            themes = [t.strip() for t in re.split(r"[,，\n]", km.group(1)) if t.strip()][:20]
        text = text[:km.start()]

    return text.strip(), themes


def detect_doc_type(
    kdc: str | None,
    title: str | None,
    source_format: str | None = None,
    genre: str | None = None,
) -> str:
    """문서 유형 판별 — 활성 도메인 프로파일에 위임 (구 시그니처 호환 shim)."""
    from domains import get_active_profile

    return get_active_profile().detect_doc_type({
        "kdc": kdc,
        "title": title,
        "source_format": source_format,
        "genre": genre,
    })


def _normalize_doc_type(doc_type: str | None) -> str:
    """프로파일에 없는 doc_type은 기본값으로 (기존 dict.get(…, "book") 동작 보존)."""
    from domains import get_active_profile

    profile = get_active_profile()
    if doc_type in profile.doc_types:
        return doc_type
    return profile.default_doc_type


def _parse_llm_output(tpl: PromptTemplate, raw: str) -> tuple[str, list[str]]:
    if tpl.parser == "summary_themes":
        return _parse_summary_themes(raw)
    return raw, []


async def _chat_completion(system: str, user: str, params: dict, timeout: float) -> str:
    cfg = get_settings()
    payload = {
        "model": cfg.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **params,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{cfg.LLM_BASE_URL}/chat/completions", json=payload)
        if resp.status_code >= 400:
            import logging
            logging.getLogger(__name__).error(
                f"[summarizer] LLM {resp.status_code} — user={len(user)}자, body={resp.text[:500]}"
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


async def summarize_section(
    book_title: str,
    section_text: str,
    doc_type: str = "book",
) -> tuple[str, list[str]]:
    """섹션 요약 + 테마 키워드 동시 추출. returns (summary, themes)."""
    tpl = get_prompt("section_summary", _normalize_doc_type(doc_type))
    system, user, params = tpl.render(title=book_title, text=section_text)
    raw = await _chat_completion(system, user, params, timeout=get_settings().SUMMARIZER_SECTION_TIMEOUT)
    return _parse_llm_output(tpl, raw)


def _combine_sections(section_summaries: list[str]) -> str:
    """섹션 요약들을 합친다. 상한 초과 시 앞부분만 자르지 않고 책 전체에 걸쳐
    균등 샘플링하여(앞·중간·뒤 고루) 전체 맥락을 보존한다.
    """
    items = [s for s in section_summaries if s]
    if not items:
        return ""

    def _join(seq: list[str]) -> str:
        return "\n\n".join(f"[섹션 {i + 1}] {s}" for i, s in enumerate(seq))

    full = _join(items)
    cap = get_settings().SUMMARIZER_MAX_INPUT_CHARS
    if not cap or len(full) <= cap:
        return full

    # 초과 → 균등 간격으로 섹션 샘플링 (순서 유지). 앞에서 자르면 후반부가 통째로 누락됨.
    avg = max(1, len(full) // len(items))
    keep = max(1, cap // avg)
    if keep >= len(items):
        return full[:cap]
    step = len(items) / keep
    picked = [items[min(len(items) - 1, int(i * step))] for i in range(keep)]
    return _join(picked)[:cap]  # 최종 안전 가드


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
    combined = _combine_sections(section_summaries)
    tpl = get_prompt("introduction")
    system, user, params = tpl.render(
        title=title,
        author=author or "미상",
        publisher=publisher or "미상",
        pub_date=pub_date or "미상",
        section_summaries=combined,
    )
    raw = await _chat_completion(system, user, params, timeout=get_settings().SUMMARIZER_INTRO_TIMEOUT)
    return raw or None


async def summarize_book_from_sections(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
) -> tuple[str, list[str]]:
    """전체 도서 요약 + 테마 키워드 생성. returns (summary, themes)."""
    combined = _combine_sections(section_summaries)
    tpl = get_prompt("book_summary", _normalize_doc_type(doc_type))
    system, user, params = tpl.render(
        title=title, author=author, section_summaries=combined,
    )
    raw = await _chat_completion(system, user, params, timeout=get_settings().SUMMARIZER_BOOK_TIMEOUT)
    return _parse_llm_output(tpl, raw)
