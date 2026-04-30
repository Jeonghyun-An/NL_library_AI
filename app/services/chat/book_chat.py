"""
book_chat.py — 특정 도서와의 심층 대화 (RAG + SSE 스트리밍)
"""
import json
import logging
from typing import AsyncGenerator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from repositories.book import BookRepository
from services.ingestion.embedder import embed_texts
from services.ingestion.indexer import search_chunks

log = logging.getLogger(__name__)
cfg = get_settings()

_SYSTEM_TEMPLATE = """\
당신은 "{title}" ({author}{pub_date}) 의 전담 독서 도우미입니다.
이 책의 내용을 바탕으로 사용자와 심층적인 대화를 나눕니다.

[책 요약]
{summary}

[핵심 주제]
{themes}

답변 규칙:
- 반드시 제공된 [참고 내용]을 근거로 답변하세요.
- 책에 없는 내용은 "이 책에서는 다루지 않습니다"라고 솔직하게 말하세요.
- 관련 내용의 출처(페이지)를 자연스럽게 언급하세요.
- 추측이나 창작은 하지 마세요.
- 한국어로 답변하세요.\
"""


async def stream_book_chat(
    cnts_id: str,
    message: str,
    history: list[dict],
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    # ── 1. 도서 메타데이터 로드 ──────────────────────────────
    repo = BookRepository(db)
    book = await repo.get_by_cnts_id(cnts_id)
    if not book:
        yield f"data: {json.dumps({'text': '도서를 찾을 수 없습니다.'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # ── 2. 질문과 관련된 청크 검색 (해당 책만) ──────────────
    hits = []
    try:
        dense, sparse = embed_texts([message], is_query=True)
        hits = search_chunks(dense[0], sparse[0], top_k=6, book_filter=cnts_id)
    except Exception as e:
        log.warning(f"[{cnts_id}] 채팅 청크 검색 실패: {e}")

    # ── 3. 시스템 프롬프트 + 메시지 빌드 ────────────────────
    author = book.personal_author or book.corporate_author or "저자 미상"
    pub_date = f", {book.pub_date}" if book.pub_date else ""
    system = _SYSTEM_TEMPLATE.format(
        title=book.title or cnts_id,
        author=author,
        pub_date=pub_date,
        summary=book.summary or "요약 정보 없음",
        themes=book.themes or "테마 정보 없음",
    )

    messages = [{"role": "system", "content": system}]

    # 최근 10턴 히스토리
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # 검색된 청크를 컨텍스트로 첨부
    context_block = ""
    if hits:
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
        "max_tokens": 1500,
        "temperature": 0.3,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json=payload,
                timeout=90.0,
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
        log.error(f"[{cnts_id}] 채팅 스트리밍 실패: {e}")
        yield f"data: {json.dumps({'text': '응답 생성 중 오류가 발생했습니다.'}, ensure_ascii=False)}\n\n"

    # ── 5. 참고 출처 전달 (텍스트 스트리밍 완료 후) ──────────
    if hits:
        sources = [
            {"page_start": h.page_start, "page_end": h.page_end, "text": h.text[:80]}
            for h in hits[:4]
        ]
        yield f"data: {json.dumps({'sources': sources}, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
