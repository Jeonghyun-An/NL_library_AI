"""
paper_summary.py — 논문 검색 결과 핵심 요약 SSE 스트리밍

프론트엔드 흐름:
  1. POST /api/papers/search         → 논문 리스트 즉시 반환
  2. POST /api/papers/summary/stream → 핵심 요약 + 출처 SSE 스트리밍 (병렬)

summary 엔드포인트:
  - 입력: query + top-K 논문 book_id 목록 (검색 결과에서 전달)
  - 처리: 각 논문의 best chunk 로 컨텍스트 구성 → LLM 스트리밍
  - 출력: text 토큰 SSE + 마지막에 sources 이벤트
"""
import json
import logging
from typing import AsyncGenerator

import httpx

from core.config import get_settings
from services.prompts import get_prompt

log = logging.getLogger(__name__)
cfg = get_settings()

_MAX_EXCERPT_CHARS = 500   # 논문당 발췌 최대 길이
_MAX_PAPERS = 5            # 요약에 사용할 최대 논문 수


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


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
            "excerpt": _truncate(p.get("best_chunk_text") or "", _MAX_EXCERPT_CHARS),
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

    # ── 텍스트 스트리밍 ───────────────────────────────────────
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json=payload,
                timeout=float(cfg.PAPER_SUMMARY_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
                    except Exception:
                        pass
    except Exception as e:
        log.error(f"[paper_summary] LLM 스트리밍 실패: {e}")
        yield f"data: {json.dumps({'text': '요약 생성 중 오류가 발생했습니다.'}, ensure_ascii=False)}\n\n"

    # ── 출처 목록 이벤트 ─────────────────────────────────────
    sources: list[dict] = [
        {
            "num": p["num"],
            "book_id": papers[i]["book_id"],
            "title": p["title"],
            "authors": p["authors"],
        }
        for i, p in enumerate(paper_ctx)
    ]
    yield f"data: {json.dumps({'sources': sources}, ensure_ascii=False)}\n\n"
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
      data: [DONE]
    """
    src_excerpt = _truncate(source_abstract, 400) if source_abstract else "초록 없음"
    rel_excerpt = _truncate(related_abstract, 400) if related_abstract else "초록 없음"

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

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json=payload,
                timeout=30.0,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
                    except Exception:
                        pass
    except Exception as e:
        log.error(f"[paper_related_reason] LLM 스트리밍 실패: {e}")
        yield f"data: {json.dumps({'text': '유사성 분석 중 오류가 발생했습니다.'}, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
