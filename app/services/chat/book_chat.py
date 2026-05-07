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

log = logging.getLogger(__name__)
cfg = get_settings()


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
    *,
    book=None,
) -> AsyncGenerator[str, None]:
    # book 객체는 엔드포인트에서 미리 조회해 넘긴다 (db 세션 누수 방지).
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

    # 최근 10턴 히스토리 (user+assistant 쌍 = 메시지 20개)
    for msg in history[-20:]:
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

    full_response = ""
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
