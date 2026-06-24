"""
book_chat.py — 특정 도서와의 심층 대화 (RAG + SSE 스트리밍)
"""
import json
import logging
import re
from typing import AsyncGenerator

import httpx

from core.config import get_settings
from services.ingestion.embedder import embed_texts
from services.ingestion.indexer import SearchHit, search_chunks
from services.prompts import get_prompt

log = logging.getLogger(__name__)
cfg = get_settings()

_REF_INTENT_KEYWORDS = frozenset({
    "참고문헌", "참고 문헌", "인용", "reference", "cited", "출처", "bibliography",
    "참고자료", "인용문헌", "인용 문헌",
})


def _format_history_for_rewrite(history: list[dict], max_msgs: int) -> str:
    """질의 재구성용 최근 대화 텍스트 구성. 빈 내용·max_msgs 컷 처리."""
    recent = history[-max_msgs:] if max_msgs and max_msgs > 0 else history
    lines: list[str] = []
    for msg in recent:
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        label = "사용자" if msg.get("role") == "user" else "도우미"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


async def rewrite_chat_query(message: str, history: list[dict]) -> str:
    """이전 대화 맥락으로 현재 질문을 독립적 검색 질의로 재구성.
    히스토리가 없으면 원문을 그대로 반환한다.
    """
    hist_text = _format_history_for_rewrite(history, cfg.BOOK_CHAT_QUERY_REWRITE_HISTORY)
    if not hist_text:
        return message
    system, user, params = get_prompt("chat_query_rewrite").render(
        history=hist_text, message=message,
    )
    payload = {
        "model": cfg.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **params,
    }
    async with httpx.AsyncClient(timeout=cfg.BOOK_CHAT_QUERY_REWRITE_TIMEOUT) as client:
        resp = await client.post(f"{cfg.LLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        out = resp.json()["choices"][0]["message"]["content"].strip()
    return out or message


def _find_cited_hits(response_text: str, hits: list[SearchHit]) -> list[SearchHit]:
    """LLM 응답에서 실제 인용된 청크만 필터링.

    컨텍스트 블록 형식 [p.X–Y] 을 기준으로 인용 여부를 판단.
    page_start 가 0 이하인 청크(페이지 정보 없음)는 제외.
    """
    cited: list[SearchHit] = []
    for hit in hits:
        ps, pe = hit.page_start, hit.page_end
        if ps <= 0:
            continue
        patterns = [
            rf'p\.{ps}[–\-~]{pe}\b',   # p.23–45 / p.23-45
            rf'p\.{ps}\b',              # p.23
            rf'\b{ps}[–\-~]{pe}페이지',  # 23–45페이지
            rf'\b{ps}페이지',            # 23페이지
        ]
        for pat in patterns:
            if re.search(pat, response_text):
                cited.append(hit)
                break
    return cited


async def stream_book_chat(
    cnts_id: str,
    message: str,
    history: list[dict],
    *,
    book=None,
) -> AsyncGenerator[str, None]:
    # book 객체는 엔드포인트에서 미리 조회해 넘긴다 (db 세션 누수 방지).
    if not book:
        yield f"data: {json.dumps({'text': '도서를 찾을 수 없습니다.'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # ── 1. 히스토리 기반 질의 재구성 (검색용) ───────────────
    #    대명사·생략 질의의 청크 검색 recall 향상. LLM 답변에는 원문 질문을 그대로 사용.
    search_query = message
    if cfg.BOOK_CHAT_QUERY_REWRITE and history:
        try:
            rewritten = await rewrite_chat_query(message, history)
            if rewritten and rewritten != message:
                search_query = rewritten
                log.info(f"[{cnts_id}] 대화 질의 재구성: {message!r} → {rewritten!r}")
        except Exception as e:
            log.warning(f"[{cnts_id}] 대화 질의 재구성 실패, 원문 사용: {e}")

    # ── 2a. 참고문헌 의도 감지 — Milvus 우회 ───────────────────
    msg_lower = message.lower()
    is_ref_query = any(kw in msg_lower for kw in _REF_INTENT_KEYWORDS)

    ref_context_block = ""
    if is_ref_query:
        refs: list[str] = (book.extra or {}).get("references", [])
        if refs:
            ref_context_block = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(refs[:50]))
            log.info(f"[{cnts_id}] 참고문헌 의도 감지 → {len(refs)}건 컨텍스트 주입")

    # ── 2b. 청크 검색 (참고문헌 의도 시 건너뜀) ─────────────
    hits = []
    if not is_ref_query:
        try:
            dense, sparse = embed_texts([search_query], is_query=True)
            hits = search_chunks(dense[0], sparse[0], top_k=cfg.BOOK_CHAT_SEARCH_TOP_K, book_filter=cnts_id)
        except Exception as e:
            log.warning(f"[{cnts_id}] 채팅 청크 검색 실패: {e}")

    # ── 3. 시스템 프롬프트 + 메시지 빌드 ────────────────────
    author = book.personal_author or book.corporate_author or "저자 미상"
    pub_date = f", {book.pub_date}" if book.pub_date else ""
    tpl = get_prompt("book_chat")
    system, _, gen_params = tpl.render(
        title=book.title or cnts_id,
        author=author,
        pub_date=pub_date,
        summary=book.summary or "요약 정보 없음",
        themes=book.themes or "테마 정보 없음",
    )

    messages = [{"role": "system", "content": system}]

    # 최근 히스토리 (BOOK_CHAT_HISTORY_MESSAGES 개 메시지 = 절반 턴 수)
    for msg in history[-cfg.BOOK_CHAT_HISTORY_MESSAGES:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # 컨텍스트 블록 빌드 — 참고문헌 의도 시 refs 우선, 아니면 청크 검색 결과
    if ref_context_block:
        user_content = f"[이 논문의 참고문헌 목록]\n{ref_context_block}\n\n[질문]\n{message}"
    elif hits:
        context_block = "\n\n".join(
            f"[p.{h.page_start}–{h.page_end}]\n{h.text}" for h in hits
        )
        user_content = f"[참고 내용]\n{context_block}\n\n[질문]\n{message}"
    else:
        user_content = message

    messages.append({"role": "user", "content": user_content})

    # ── 4. LLM 스트리밍 호출 ────────────────────────────────
    payload = {
        "model": cfg.LLM_MODEL,
        "messages": messages,
        **gen_params,
        "stream": True,
    }

    full_response = ""
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json=payload,
                timeout=float(cfg.BOOK_CHAT_TIMEOUT),
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
                            full_response += delta
                            yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
                    except Exception:
                        pass
    except Exception as e:
        log.error(f"[{cnts_id}] 채팅 스트리밍 실패: {e}")
        yield f"data: {json.dumps({'text': '응답 생성 중 오류가 발생했습니다.'}, ensure_ascii=False)}\n\n"

    # ── 5. 실제 인용된 출처만 전달 ───────────────────────────
    # LLM 응답에서 p.X 또는 p.X–Y 형태로 언급된 청크만 타일로 표시.
    # 인용이 없으면 sources 이벤트를 보내지 않는다 (빈 타일 방지).
    if hits:
        cited = _find_cited_hits(full_response, hits)
        if cited:
            sources = [
                {
                    "page_start": h.page_start,
                    "page_end": h.page_end,
                    "text": h.text,
                }
                for h in cited
            ]
            yield f"data: {json.dumps({'sources': sources}, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
