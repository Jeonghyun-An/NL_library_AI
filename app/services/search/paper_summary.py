"""
paper_summary.py — 논문 검색 결과 핵심 요약 SSE 스트리밍

프론트엔드 흐름:
  1. POST /api/papers/search         → 논문 리스트 즉시 반환
  2. POST /api/papers/summary/stream → 핵심 요약 + 출처 SSE 스트리밍 (병렬)

summary 엔드포인트:
  - 입력: query + top-K 논문 book_id 목록 (검색 결과에서 전달)
  - 처리: 각 논문의 발췌(best_chunk_text — 화면이 고른 원문 초록·색인 요약 본문, frontend/utils/summaryExcerpt.ts)를
          문장 경계에서 잘라 컨텍스트 구성 → LLM 스트리밍
  - 출력: text 토큰 SSE + 마지막에 sources 이벤트(LLM 호출이 실패하거나 빈 답으로 끝나면 sources 뒤에 error 이벤트)
"""
import json
import logging
import re
from typing import AsyncGenerator

import httpx

from core.config import get_settings
from services.llm_sse import sse_deltas
from services.prompts import get_prompt

log = logging.getLogger(__name__)
cfg = get_settings()

# 논문당 발췌 최대 길이 — 500자일 때는 국문 초록이 결과·결론 앞에서, 영문 초록은 목적·방법에서 끊겨 요약이 결과를 지어냈다.
# 국문 초록은 대개 이 안에 다 든다. 화면의 기록 스냅샷(SNAPSHOT_EXCERPT_MAX_CHARS)은 이보다 넉넉히 담는다
_MAX_EXCERPT_CHARS = 1000
_MAX_PAPERS = 5            # 요약에 사용할 최대 논문 수

# 세 스트림이 LLM 호출 실패(httpx 연결·읽기 오류, 4xx·5xx 응답, 스트림 안 오류 줄·[DONE] 없이 끝남 — llm_sse.sse_deltas)로
# 끝날 때 [DONE] 바로 앞에 보내는 {error} 이벤트의 문구 — 소장자료 추천 이유(pipeline.REASON_STREAM_ERROR)와 같은 꼴. 화면은 이것을 답 글에 잇지 않고 오류로 보이며
# 캐시·검색 기록에 담지 않는다. 전에는 '…오류가 발생했습니다.' 를 보통 {text} 로 흘려 정상 답처럼 저장됐다.
# LLM 이 글 조각 없이(공백뿐 포함) [DONE] 으로 끝난 빈 답도 같은 이벤트로 끝낸다 — 전에는 [DONE] 만 와 화면이 빈 글을
# 끝까지 받은 답으로 읽었다(DeepRead 대화의 empty_answer 와 같은 판별, chat/book_chat.py).
# 논문 상세 AI 요약은 LLM 에 줄 논문 내용(초록·요약·해제)이 하나도 없을 때도 LLM 을 부르지 않고 같은 이벤트로 끝낸다
SUMMARY_STREAM_ERROR = "AI 요약을 만들지 못했습니다"          # 논문 검색 결과의 AI 요약(stream_paper_summary)
RELATED_REASON_STREAM_ERROR = "추천 사유를 만들지 못했습니다"  # 논문 상세 관련 논문의 AI 추천 사유(stream_related_reason)
PAPER_REASON_STREAM_ERROR = "AI 요약을 만들지 못했습니다"     # 논문 상세의 AI 요약(stream_paper_reason)


def _error_event(message: str) -> str:
    return f"data: {json.dumps({'error': message}, ensure_ascii=False)}\n\n"


def _log_empty_answer(where: str, sent: int) -> None:
    # 호출은 정상으로 끝났는데 글이 없다 — 연결·응답 실패(ERROR)와 갈라 경고로 남긴다. 보낸 글 길이로 빈 글인지 공백뿐인지 가린다
    log.warning("[%s] LLM 이 빈 답으로 끝났다(보낸 글 %d자)", where, sent)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


# 문장 끝 — 마침표·물음표·느낌표 뒤가 공백·닫는 따옴표·괄호이거나 글 끝. 소수점(β=.448·p<.05)은 점 뒤가 숫자라 걸리지 않는다
_SENTENCE_END_RE = re.compile(r"[.?!。](?=[\s\"'”’)\]]|$)")


def _truncate_at_sentence(text: str, max_chars: int) -> str:
    """max_chars 안의 마지막 문장 끝에서 자르고 ' …' 를 붙인다.

    공백에서 자르면 문장 한가운데('…노인의 특성에 따른…')서 끊겨, 요약 모델이 뒷부분을 지어 채웠다(원문 결론과 다른 제언).
    문장 끝이 앞쪽 절반 안에만 있으면(아주 긴 한 문장) 전처럼 공백에서 자른다.
    """
    if len(text) <= max_chars:
        return text
    # 한 글자 더 보아 자르는 자리 바로 뒤가 공백인지 가린다 — 마지막 칸의 점은 뒤를 모르므로 문장 끝으로 치지 않는다
    ends = [m.end() for m in _SENTENCE_END_RE.finditer(text, 0, max_chars + 1) if m.end() <= max_chars]
    if ends and ends[-1] >= max_chars // 2:
        return text[: ends[-1]] + " …"
    return _truncate(text, max_chars)


def _clean_excerpt(text: str) -> str:
    """청크 텍스트에서 '초록\n**SUMMARY:**' 같은 메타 프리픽스 제거."""
    if not text:
        return text
    text = _CHUNK_META_RE.sub("", text.strip())
    text = _SUMMARY_PREFIX_RE.sub("", text.strip())
    return text.strip()


_SUMMARY_PREFIX_RE = re.compile(r"^##\s*SUMMARY:\s*", re.IGNORECASE)
_CHUNK_META_RE = re.compile(
    r"^(초록|abstract|summary|요약|introduction|서론)\s*[\n\r]+\s*\*{0,2}SUMMARY:\s*",
    re.IGNORECASE,
)
_KEYWORD_SECTION_RE = re.compile(
    r"\*\*관련\s*연구자가\s*검색할\s*학술\s*키워드\s*:\*\*\s*([\s\S]*?)$",
    re.IGNORECASE,
)


def _parse_summary(raw: str) -> tuple[str, list[str]]:
    """레거시 summary 포맷 파싱.

    ## SUMMARY: [본문] **관련 연구자가 검색할 학술 키워드:** k1, k2, ...
    Returns: (clean_body, [keywords])
    """
    if not raw:
        return "", []
    text = _SUMMARY_PREFIX_RE.sub("", raw.strip())
    kw_match = _KEYWORD_SECTION_RE.search(text)
    embedded_kw: list[str] = []
    if kw_match:
        kw_raw = kw_match.group(1)
        embedded_kw = [k.strip() for k in re.split(r"[,;·]", kw_raw) if k.strip()][:12]
        text = text[: kw_match.start()].strip()
    return text, embedded_kw


async def stream_paper_summary(
    query: str,
    papers: list[dict],  # [{"book_id", "title", "authors", "best_chunk_text"}]
) -> AsyncGenerator[str, None]:
    """
    papers: 검색 결과에서 정렬된 논문 목록 (최대 _MAX_PAPERS 개 사용).
    각 항목: {"book_id": str, "title": str, "authors": str, "best_chunk_text": str}

    SSE 이벤트:
      data: {"text": "..."}       — 토큰 스트리밍
      data: {"sources": [...]}    — 최종 출처 목록
      data: {"error": SUMMARY_STREAM_ERROR} — LLM 호출이 실패하거나 빈 답으로 끝나면(받은 글·sources 뒤, [DONE] 바로 앞)
      data: [DONE]
    """
    if not papers:
        yield f"data: {json.dumps({'text': '분석할 논문이 없습니다.'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    papers = papers[:_MAX_PAPERS]

    # 프롬프트용 컨텍스트 구성
    paper_ctx = [
        {
            "num": i + 1,
            "title": p.get("title") or "제목 없음",
            "authors": p.get("authors") or "저자 미상",
            "excerpt": _truncate_at_sentence(_clean_excerpt(p.get("best_chunk_text") or ""), _MAX_EXCERPT_CHARS),
        }
        for i, p in enumerate(papers)
    ]

    tpl = get_prompt("paper_search_summary")
    system, user, params = tpl.render(query=query, papers=paper_ctx)

    payload = {
        "model": cfg.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **params,
        "stream": True,
    }

    # 출처는 LLM 이 아니라 넘겨받은 논문으로 만든다 — 요약이 실패해도 그대로 맞아 오류 앞에 보낸다(화면 오른쪽 참고 논문 칸)
    sources: list[dict] = [
        {
            "num": p["num"],
            "book_id": papers[i]["book_id"],
            "title": p["title"],
            "authors": p["authors"],
        }
        for i, p in enumerate(paper_ctx)
    ]

    # ── 텍스트 스트리밍 ───────────────────────────────────────
    sent = 0   # 이미 흘린 글 길이 — 실패 로그가 시작 전 실패인지 글 일부 뒤 실패인지 남긴다
    shown = False   # 공백 아닌 글을 한 조각이라도 흘렸는가 — 빈 답 판별
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json=payload,
                timeout=float(cfg.PAPER_SUMMARY_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
                async for delta in sse_deltas(resp):
                    sent += len(delta)
                    shown = shown or bool(delta.strip())
                    yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
    except Exception as e:
        log.error("[paper_summary] LLM 스트리밍 실패(보낸 글 %d자): %s: %s", sent, type(e).__name__, e)
        yield f"data: {json.dumps({'sources': sources}, ensure_ascii=False)}\n\n"
        yield _error_event(SUMMARY_STREAM_ERROR)
        yield "data: [DONE]\n\n"
        return

    # ── 출처 목록 이벤트 ─────────────────────────────────────
    yield f"data: {json.dumps({'sources': sources}, ensure_ascii=False)}\n\n"
    if not shown:
        _log_empty_answer("paper_summary", sent)
        yield _error_event(SUMMARY_STREAM_ERROR)
    yield "data: [DONE]\n\n"


async def stream_related_reason(
    source_title: str,
    source_abstract: str,
    related_title: str,
    related_abstract: str,
) -> AsyncGenerator[str, None]:
    """두 논문의 유사성 이유를 SSE 스트리밍.

    SSE 이벤트:
      data: {"text": "..."}   — 토큰 스트리밍
      data: {"error": RELATED_REASON_STREAM_ERROR} — LLM 호출이 실패하거나 빈 답으로 끝나면(받은 글 뒤, [DONE] 바로 앞)
      data: [DONE]
    """
    src_excerpt = _truncate(_clean_excerpt(source_abstract), 400) if source_abstract else "초록 없음"
    rel_excerpt = _truncate(_clean_excerpt(related_abstract), 400) if related_abstract else "초록 없음"

    system_msg = (
        "당신은 학술 논문 전문가입니다. "
        "두 논문의 연구적 유사성을 1~2문장으로 간결하게 설명하세요. "
        "반드시 '해당 논문은 ~ 한 내용이 유사합니다.' 형식으로 작성하세요."
    )
    user_msg = (
        f"원본 논문: {source_title}\n초록: {src_excerpt}\n\n"
        f"연관 논문: {related_title}\n초록: {rel_excerpt}\n\n"
        "두 논문이 유사한 이유를 설명하세요."
    )

    payload = {
        "model": cfg.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 200,
        "temperature": 0.2,
        "stream": True,
    }

    sent = 0
    shown = False
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json=payload,
                timeout=30.0,
            ) as resp:
                resp.raise_for_status()
                async for delta in sse_deltas(resp):
                    sent += len(delta)
                    shown = shown or bool(delta.strip())
                    yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
    except Exception as e:
        log.error("[paper_related_reason] LLM 스트리밍 실패(보낸 글 %d자): %s: %s", sent, type(e).__name__, e)
        yield _error_event(RELATED_REASON_STREAM_ERROR)
    else:
        if not shown:
            _log_empty_answer("paper_related_reason", sent)
            yield _error_event(RELATED_REASON_STREAM_ERROR)

    yield "data: [DONE]\n\n"


async def stream_paper_reason(
    query: str,
    paper,                  # Book ORM 인스턴스
    rewritten_query: str = "",
) -> AsyncGenerator[str, None]:
    """
    논문 단건 분석 이유 SSE 스트리밍.

    검색 의도 + 논문의 인덱싱 데이터(abstract / summary / introduction)를
    바탕으로 이 논문이 검색 의도와 어떻게 연관되는지 사실 기반으로 분석한다.

    SSE 이벤트:
      data: {"keywords": [...]}   — 키워드 즉시 emit (있을 때)
      data: {"text": "..."}       — 토큰 스트리밍
      data: {"error": PAPER_REASON_STREAM_ERROR} — LLM 호출이 실패하거나 빈 답으로 끝나면(받은 글 뒤, [DONE] 바로 앞),
                                                   또는 LLM 에 줄 논문 내용(초록·요약·해제)이 없으면(키워드 뒤, 글 없이)
      data: [DONE]
    """
    # ── 키워드 즉시 emit ─────────────────────────────────────
    raw_kw = (paper.keyword or paper.themes or paper.subject or "") if paper else ""
    emit_kw: list[str] = []
    if raw_kw:
        emit_kw = [k.strip() for k in re.split(r"[,;|/·]", raw_kw) if k.strip()][:8]
    # fallback: 내장 키워드 섹션에서 추출
    if not emit_kw and paper:
        _, embedded_kw = _parse_summary(paper.summary or "")
        emit_kw = embedded_kw[:8]
    if emit_kw:
        yield f"data: {json.dumps({'keywords': emit_kw}, ensure_ascii=False)}\n\n"

    # ── 논문 서지 정보 블록 ──────────────────────────────────
    meta_lines = []
    if paper:
        if paper.title:
            meta_lines.append(f"제목: {paper.title}")
        author = paper.personal_author or paper.corporate_author
        if author:
            meta_lines.append(f"저자: {author}")
        if paper.pub_date:
            meta_lines.append(f"발행연도: {paper.pub_date[:4]}")
        if paper.publisher:
            meta_lines.append(f"저널/출판기관: {paper.publisher}")
        if paper.series_title:
            meta_lines.append(f"학술지: {paper.series_title}")
        if paper.grade:
            meta_lines.append(f"KCI 등급: {paper.grade}")
    paper_meta = "\n".join(meta_lines)

    # ── 컨텍스트 블록 (초록 우선, 없으면 cleaned summary / introduction) ──
    context_parts = []
    if paper:
        if paper.abstract:
            context_parts.append(f"[초록]\n{_truncate(paper.abstract, 800)}")
        elif paper.summary:
            clean_summary, _ = _parse_summary(paper.summary)
            if clean_summary:
                context_parts.append(f"[논문 요약]\n{_truncate(clean_summary, 800)}")
        if paper.introduction:
            context_parts.append(f"[논문 해제]\n{_truncate(paper.introduction, 600)}")
    context_text = "\n\n".join(context_parts)

    if not context_text:
        # 초록·요약·해제가 모두 없어 LLM 에 줄 내용이 없다 — 요약을 만들지 못한 것이므로 이 스트림의 실패 이벤트로 끝낸다.
        # 전에는 '논문 내용 정보가 부족하여 분석을 생성할 수 없습니다.' 를 보통 {text} + [DONE] 으로 보내 화면(논문 상세)이
        # 정상 요약처럼 그리고 sessionStorage 캐시에 담았다. 화면은 {error} 를 실패로 읽어 자기 해요체 문구로 보이고 담지 않는다
        log.warning("[paper_reason] 논문 내용 정보(초록·요약·해제)가 없어 AI 요약을 만들지 않았다")
        yield _error_event(PAPER_REASON_STREAM_ERROR)
        yield "data: [DONE]\n\n"
        return

    # ── 프롬프트 렌더링 ──────────────────────────────────────
    intent = rewritten_query or query
    tpl = get_prompt("recommendation.paper")
    system_message, user_message, params = tpl.render(
        intent=intent,
        query=query,
        paper_meta=paper_meta,
        context_text=context_text,
    )

    # ── LLM 스트리밍 ─────────────────────────────────────────
    sent = 0
    shown = False
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json={
                    "model": cfg.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user",   "content": user_message},
                    ],
                    "max_tokens": 600,
                    "temperature": params.get("temperature", 0.2),
                    "stream": True,
                },
                timeout=float(cfg.REASON_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
                async for delta in sse_deltas(resp):
                    sent += len(delta)
                    shown = shown or bool(delta.strip())
                    yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
    except Exception as e:
        log.error("[paper_reason] LLM 스트리밍 실패(보낸 글 %d자): %s: %s", sent, type(e).__name__, e)
        yield _error_event(PAPER_REASON_STREAM_ERROR)
    else:
        if not shown:
            _log_empty_answer("paper_reason", sent)
            yield _error_event(PAPER_REASON_STREAM_ERROR)

    yield "data: [DONE]\n\n"
