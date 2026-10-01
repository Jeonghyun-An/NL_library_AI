"""
summarizer.py — 섹션/도서 요약·테마·소개글 생성

프롬프트는 도메인 프로파일의 YAML 템플릿(domains/{D}/prompts/)에서 로드한다.
doc_type 판별 로직은 domains/{D}/doc_types.py 로 이동 (아래 shim 으로 호환 유지).
"""
import asyncio
import logging
import re
from dataclasses import dataclass

import httpx
from core.config import get_settings
from services.prompts import get_prompt, PromptTemplate

log = logging.getLogger(__name__)


# SUMMARY:/THEMES: 라벨 — gemma가 마크다운 볼드(**)·헤더(#)로 감싸도 허용
_THEMES_SPLIT_RE = re.compile(r"\n*[*#]*\s*THEMES\s*:\s*[*#]*\s*\n?")
_THEMES_LINE_RE  = re.compile(r"^[*#]*\s*THEMES\s*:\s*(.+)$", re.MULTILINE)
_THEMES_LINE_DEL = re.compile(r"^[*#]*\s*THEMES\s*:.*$\n?", re.MULTILINE)
_SUMMARY_PREFIX_RE = re.compile(r"^[*#]*\s*SUMMARY\s*:\s*[*#]*\s*\n?")


def _clean_token(s: str) -> str:
    """테마 토큰/요약 잔여에서 마크다운 별표·헤더 기호 제거."""
    return s.strip().strip("*#").strip()


def _parse_summary_themes(text: str) -> tuple[str, list[str]]:
    """SUMMARY:/THEMES: 구조화 출력 파싱 (마크다운 볼드/헤더 라벨도 허용)."""
    themes: list[str] = []
    text = text.strip()

    # ① THEMES 섹션 분리
    themes_split = _THEMES_SPLIT_RE.split(text, maxsplit=1)
    if len(themes_split) == 2:
        text, themes_raw = themes_split
        themes = [t for t in (_clean_token(x) for x in re.split(r"[,，\n]", themes_raw)) if t][:20]
    else:
        m = _THEMES_LINE_RE.search(text)
        if m:
            themes = [t for t in (_clean_token(x) for x in m.group(1).split(",")) if t][:20]
            text = _THEMES_LINE_DEL.sub("", text)

    # ② SUMMARY: 접두어 제거 (볼드/헤더 포함, 같은 줄 / 다음 줄 모두)
    text = text.strip()
    m = _SUMMARY_PREFIX_RE.match(text)
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

    # ④ 라벨 누수 방어 — 앞뒤 잔여 마크다운 별표 제거
    return text.strip().strip("*").strip(), themes


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
    # LLM 호출은 llm_client 어댑터로 통일 (OpenAI vLLM / Ollama 네이티브 겸용).
    # 스타일 분기·think 제어·base URL 처리는 어댑터가 담당한다.
    from services.llm_client import chat
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return await chat(messages, params=params, timeout=timeout)


async def summarize_section(
    book_title: str,
    section_text: str,
    doc_type: str = "book",
) -> tuple[str, list[str]]:
    """섹션 요약 + 테마 키워드 동시 추출. returns (summary, themes)."""
    tpl = get_prompt("section_summary", _normalize_doc_type(doc_type))
    # 컨텍스트 초과 방어 — 섹션 분할은 토큰을 추정치로 계산하므로 실제 토큰이 더 클 수 있다.
    cap = getattr(get_settings(), "SUMMARIZER_MAX_SECTION_CHARS", 0)
    if cap and len(section_text) > cap:
        log.warning(f"섹션 입력 {len(section_text)}자 → {cap}자로 절단 (컨텍스트 초과 방지)")
        section_text = section_text[:cap]
    system, user, params = tpl.render(title=book_title, text=section_text)
    raw = await _chat_completion(system, user, params, timeout=get_settings().SUMMARIZER_SECTION_TIMEOUT)
    return _parse_llm_output(tpl, raw)


def _join_sections(seq: list[str]) -> str:
    return "\n\n".join(f"[섹션 {i + 1}] {s}" for i, s in enumerate(seq))


def _combine_sections(section_summaries: list[str]) -> str:
    """섹션 요약들을 합친다. 상한 초과 시 앞부분만 자르지 않고 책 전체에 걸쳐
    균등 샘플링하여(앞·중간·뒤 고루) 전체 맥락을 보존한다.
    (샘플링은 버려지는 섹션이 생긴다 — 마무리 단계는 reduce_section_summaries 로 상한 안까지
    줄인 입력을 쓰고, 여기 샘플링은 그것마저 실패했을 때의 최후 가드다.)
    """
    items = [s for s in section_summaries if s]
    if not items:
        return ""

    full = _join_sections(items)
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
    return _join_sections(picked)[:cap]  # 최종 안전 가드


# ── 계층 요약 (nanet 746744e 이식) ──────────────────────────────
# 섹션 요약을 이어 붙인 길이가 SUMMARIZER_MAX_INPUT_CHARS 를 넘으면 _combine_sections 는 균등
# 샘플링으로 일부 섹션을 버린다(마지막 섹션이 늘 빠진다). 그 전에 연속한 섹션 요약을 묶어
# 묶음마다 중간 요약을 만들고, 중간 요약을 이어 붙여 문서 요약·소개글의 입력으로 쓴다.
_REDUCE_MAX_LEVELS = 2
# 중간 요약 1개의 예상 분량(글자). 프롬프트 목표는 1,000자 내외지만 넘겨 쓰는 경우가 있어
# 여유를 둔다 — 묶음 수 × 이 값이 상한을 넘지 않게 묶음 수를 정한다.
_INTERMEDIATE_EXPECTED_CHARS = 1500
# 묶음 1개의 최소 입력 분량(글자, 섹션 요약 열 개 남짓). 이보다 잘게 나누면 중간 요약이
# 입력과 길이가 비슷해져 줄지 않고 LLM 호출만 는다.
_MIN_GROUP_CHARS = 3000
# "[섹션 123~456] " 라벨과 블록 사이 빈 줄 몫(묶음 수 계산용 여유분)
_BLOCK_OVERHEAD = 18


def _block_label(first: int, last: int) -> str:
    return f"섹션 {first}" if first == last else f"섹션 {first}~{last}"


def _join_blocks(blocks: list[tuple[int, int, str]]) -> str:
    """(첫 섹션 번호, 끝 섹션 번호, 요약) 블록을 "[섹션 3] …" / "[섹션 1~12] …" 로 빈 줄을 두고 잇는다.
    섹션 하나짜리 블록만 있으면 _join_sections 와 같은 텍스트다."""
    return "\n\n".join(f"[{_block_label(a, b)}] {s}" for a, b, s in blocks)


def _group_for_reduce(
    blocks: list[tuple[int, int, str]], cap: int,
) -> list[list[tuple[int, int, str]]]:
    """연속한 블록을 이어 붙인 길이가 cap 이하인 묶음으로 나눈다 — 필요한 만큼만 압축한다.

    묶음을 적게 만들면(예: 2개) 상한을 살짝 넘은 문서도 최종 입력이 확 줄어 요약이 빈약해진다.
    그래서 중간 요약들을 이어 붙여도 cap 안에 드는 범위에서 묶음을 되도록 많이 만들되, 묶음당
    최소 분량과 블록 2개 이상(하나짜리는 다시 요약해도 줄지 않는다)을 지킨다. 누적 분량을 n 등분해
    블록 가운데 지점이 떨어지는 구간에 배정하므로(순서 유지) 마지막 묶음만 자투리가 되지 않는다.
    """
    sizes = [len(_join_blocks([b])) + 2 for b in blocks]    # + 블록 사이 "\n\n"
    total = sum(sizes)
    n_needed = -(-total // cap)                              # 묶음 하나가 cap 을 넘지 않을 최소 개수
    n_fit = cap // (_INTERMEDIATE_EXPECTED_CHARS + _BLOCK_OVERHEAD)
    n_groups = max(n_needed, min(n_fit, total // _MIN_GROUP_CHARS, len(blocks) // 2), 1)

    buckets: list[list[tuple[tuple[int, int, str], int]]] = [[] for _ in range(n_groups)]
    cum = 0
    for b, size in zip(blocks, sizes):
        buckets[min(n_groups - 1, int((cum + size / 2) * n_groups / total))].append((b, size))
        cum += size

    # 블록 길이가 들쭉날쭉해 cap 을 넘은 묶음(드물다)은 그 묶음만 cap 단위로 한 번 더 나눈다.
    groups: list[list[tuple[int, int, str]]] = []
    for bucket in buckets:
        cur: list[tuple[int, int, str]] = []
        cur_len = 0
        for b, size in bucket:
            if cur and cur_len + size > cap:
                groups.append(cur)
                cur, cur_len = [], 0
            cur.append(b)
            cur_len += size
        if cur:
            groups.append(cur)
    return groups


@dataclass
class ReduceStats:
    """reduce_section_summaries 의 실행 기록 — 마무리 단계가 아이템 meta 에 싣는다(카나리에서 상한을 넘은
    문서가 실제로 계층 요약을 탔는지 SQL 로 센다). 호출자가 만들어 넘기면 함수가 진행하는 대로 채우므로,
    바깥 시간 예산에 걸려 중간에 끊겨도 거기까지의 값이 남는다.

    levels   : 시작한 중간 요약 단계 수. 0 = 상한 이하라 합치기만 했다, 1·2 = 그 단계까지 갔다(실패한 단계 포함).
    groups   : 만든 묶음 수 (단계 합, 블록 하나짜리 묶음 포함).
    fallback : 균등 샘플링(_combine_sections)으로 대신했는가 — 묶음 실패, 2단계 뒤에도 상한 초과.
               시간 예산 초과·예외는 이 함수 밖에서 일어나므로 호출자가 켠다.
    """
    levels: int = 0
    groups: int = 0
    fallback: bool = False


class _GroupFailed(Exception):
    """중간 요약 묶음 하나가 실패(예외·빈 응답) — 그 단계 전체를 버리고 균등 샘플링으로 돌아간다."""


async def reduce_section_summaries(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
    *,
    stats: ReduceStats | None = None,
) -> str:
    """문서 요약·소개글·줄거리·독후 효과가 함께 쓸 섹션 요약 입력을 만든다 (2단계 계층 요약).

    - 이어 붙인 길이가 SUMMARIZER_MAX_INPUT_CHARS 이하면 LLM 호출 없이 _combine_sections 와
      같은 텍스트를 돌려준다 — 대부분의 문서는 지금과 같다.
    - 넘으면 섹션 요약을 순서대로 상한 안의 묶음으로 나눠 묶음마다 중간 요약(section_group_summary
      프롬프트)을 만들고 "[섹션 1~12] …" 처럼 이어 붙인다. 묶음끼리는 동시에 부르되 동시 호출은
      LLM_SECTION_CONCURRENCY 까지다. 이어 붙여도 넘으면 한 단계 더 묶는다(최대 2단계).
    - 2단계 뒤에도 넘거나 중간 요약이 하나라도 실패하면(예외·빈 응답) 지금의 균등 샘플링
      (_combine_sections)으로 돌아간다. 묶음 하나가 실패하면 그 단계 결과는 어차피 버려지므로
      남은 묶음 호출(진행 중이거나 세마포어를 기다리는 것)을 바로 취소한다 — 응답 없는 장애에서
      시간과 LLM 자리를 아낀다.
    - 바깥이 이 코루틴을 취소하면(예: 마무리 단계의 시간 예산 asyncio.wait_for) CancelledError 는
      그대로 올라가고 진행 중인 중간 요약 호출도 함께 취소된다.
    - stats 를 주면 진행하는 대로 실행 기록(ReduceStats)을 채운다.
    """
    if stats is None:
        stats = ReduceStats()
    items = [s for s in section_summaries if s]
    if not items:
        return ""
    cfg = get_settings()
    cap = cfg.SUMMARIZER_MAX_INPUT_CHARS
    blocks = [(i + 1, i + 1, s) for i, s in enumerate(items)]
    if not cap or len(_join_blocks(blocks)) <= cap:
        return _combine_sections(items)

    tpl = get_prompt("section_group_summary", _normalize_doc_type(doc_type))
    sem = asyncio.Semaphore(max(1, cfg.LLM_SECTION_CONCURRENCY))

    async def _reduce_group(group: list[tuple[int, int, str]]) -> tuple[int, int, str]:
        first, last = group[0][0], group[-1][1]
        if len(group) == 1:          # 하나짜리는 다시 요약해도 줄 게 없다 — 그대로 둔다
            return group[0]
        label = _block_label(first, last)
        try:
            system, user, params = tpl.render(
                title=title, author=author or "미상", section_summaries=_join_blocks(group),
            )
            async with sem:
                raw = await _chat_completion(
                    system, user, params, timeout=cfg.SUMMARIZER_BOOK_TIMEOUT,
                )
            summary = (_parse_llm_output(tpl, raw)[0] or "").strip()
        except Exception as e:       # CancelledError 는 BaseException — 여기서 삼키지 않는다
            log.warning(f"[{title[:40]}] 중간 요약 실패({label}): {str(e) or type(e).__name__}")
            raise _GroupFailed(label) from e
        if not summary:
            log.warning(f"[{title[:40]}] 중간 요약 빈 응답({label})")
            raise _GroupFailed(label)
        return first, last, summary

    async def _run_level(groups: list[list[tuple[int, int, str]]]) -> list[tuple[int, int, str]] | None:
        """한 단계의 묶음을 동시에 요약한다. 하나라도 실패하면 None (남은 호출은 취소)."""
        tasks = [asyncio.ensure_future(_reduce_group(g)) for g in groups]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        finally:
            # 모두 정상으로 끝났으면 cancel 은 아무 일도 하지 않는다. 묶음 하나가 실패해 빠져나오거나
            # 바깥이 이 코루틴을 취소한 경우에는 남은 호출을 끊고 끝나기를 기다린다(기다리지 않으면 취소된
            # 호출이 이벤트 루프가 닫힌 뒤까지 남는다). asyncio.wait 는 gather 와 달리 하위 태스크를 대신
            # 취소해 주지 않으므로 여기서 직접 한다. CancelledError 는 잡지 않아 바깥 취소는 finally 를
            # 지난 뒤 그대로 올라간다.
            for t in tasks:
                t.cancel()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        if any(isinstance(r, BaseException) for r in results):
            return None
        return list(results)

    for level in range(1, _REDUCE_MAX_LEVELS + 1):
        before = len(_join_blocks(blocks))
        groups = _group_for_reduce(blocks, cap)
        stats.levels = level
        stats.groups += len(groups)
        reduced = await _run_level(groups)
        if reduced is None:
            log.warning(f"[{title[:40]}] 중간 요약 {level}단계 실패 — 남은 묶음을 취소하고 "
                        f"균등 샘플링으로 대신한다")
            stats.fallback = True
            return _combine_sections(items)
        blocks = reduced
        joined = _join_blocks(blocks)
        log.info(f"[{title[:40]}] 중간 요약 {level}단계: 묶음 {len(groups)}개, "
                 f"{before}자 → {len(joined)}자 (상한 {cap}자)")
        if len(joined) <= cap:
            return joined
    log.warning(f"[{title[:40]}] 중간 요약 {_REDUCE_MAX_LEVELS}단계 뒤에도 상한 {cap}자 초과 — "
                f"균등 샘플링으로 대신한다")
    stats.fallback = True
    return _combine_sections(items)


async def generate_book_introduction(
    title: str,
    author: str,
    publisher: str,
    pub_date: str,
    section_summaries: list[str],
    doc_type: str = "book",
    *,
    combined_text: str | None = None,
) -> str | None:
    """도서/논문 소개글 생성 (doc_type별 프롬프트 — paper는 학술 톤). 실패 시 None 반환.

    combined_text 를 주면(마무리 단계가 reduce_section_summaries 로 한 번 만든 입력) 그대로 쓰고,
    없으면 section_summaries 를 _combine_sections 로 합친다(백필 등 기존 호출).
    """
    if not section_summaries and not combined_text:
        return None
    combined = combined_text or _combine_sections(section_summaries)
    tpl = get_prompt("introduction", _normalize_doc_type(doc_type))
    system, user, params = tpl.render(
        title=title,
        author=author or "미상",
        publisher=publisher or "미상",
        pub_date=pub_date or "미상",
        section_summaries=combined,
    )
    raw = await _chat_completion(system, user, params, timeout=get_settings().SUMMARIZER_INTRO_TIMEOUT)
    return raw or None


async def generate_read_effect(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
    *,
    combined_text: str | None = None,
) -> str | None:
    """독후 효과(read_effect) 생성 — 인덱싱 시 사전 저장용. 실패 시 None 반환.

    doc_type 별 프롬프트(read_effect.{doc_type}.yaml)로 분기한다.
    combined_text 를 주면 _combine_sections 대신 그 입력을 쓴다(generate_book_introduction 참고).
    """
    if not section_summaries and not combined_text:
        return None
    combined = combined_text or _combine_sections(section_summaries)
    tpl = get_prompt("read_effect", _normalize_doc_type(doc_type))
    system, user, params = tpl.render(
        title=title,
        author=author or "미상",
        section_summaries=combined,
    )
    raw = await _chat_completion(system, user, params, timeout=get_settings().SUMMARIZER_READ_EFFECT_TIMEOUT)
    return raw or None


async def generate_book_plot(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
    *,
    combined_text: str | None = None,
) -> str | None:
    """도서 줄거리(plot) 생성 — 인덱싱 시 사전 저장용. 실패 시 None 반환.

    doc_type 별 프롬프트(plot.{doc_type}.yaml)로 분기한다.
    introduction 과 같은 입력을 받는다 — combined_text 가 있으면 그것, 없으면 _combine_sections.
    """
    if not section_summaries and not combined_text:
        return None
    combined = combined_text or _combine_sections(section_summaries)
    tpl = get_prompt("plot", _normalize_doc_type(doc_type))
    system, user, params = tpl.render(
        title=title,
        author=author or "미상",
        section_summaries=combined,
    )
    raw = await _chat_completion(system, user, params, timeout=get_settings().SUMMARIZER_PLOT_TIMEOUT)
    return raw or None


async def summarize_book_from_sections(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
    *,
    combined_text: str | None = None,
) -> tuple[str, list[str]]:
    """전체 도서 요약 + 테마 키워드 생성. returns (summary, themes).

    combined_text 를 주면 _combine_sections 대신 그 입력을 쓴다(generate_book_introduction 참고).
    """
    combined = combined_text or _combine_sections(section_summaries)
    tpl = get_prompt("book_summary", _normalize_doc_type(doc_type))
    system, user, params = tpl.render(
        title=title, author=author, section_summaries=combined,
    )
    raw = await _chat_completion(system, user, params, timeout=get_settings().SUMMARIZER_BOOK_TIMEOUT)
    return _parse_llm_output(tpl, raw)
