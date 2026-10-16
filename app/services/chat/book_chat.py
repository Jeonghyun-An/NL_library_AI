"""
book_chat.py — 특정 도서와의 심층 대화 (RAG + SSE 스트리밍)
"""
import json
import logging
import re
from typing import AsyncGenerator

import httpx

from core.config import get_settings
from schemas.book import BookOut
from services.ingestion.embedder import embed_texts
from services.ingestion.indexer import SearchHit, search_chunks
from services.llm_sse import sse_deltas
from services.prompts import PromptTemplate, get_prompt

log = logging.getLogger(__name__)
cfg = get_settings()

# 대화 스트림이 LLM 호출 실패(httpx 연결·읽기 오류, 4xx·5xx 응답, 스트림 안 오류 줄·[DONE] 없이 끝남 — llm_sse.sse_deltas)로 끝날 때 [DONE] 바로 앞에 보내는 {error} 이벤트의
# 문구 — 소장자료 추천 이유(pipeline.REASON_STREAM_ERROR)와 같은 꼴. 화면(frontend/composables/useDeepReadChat)은 이것을
# 답 글에 잇지 않고 오류로 보이며 대화에 남기지 않는다. 전에는 '응답 생성 중 오류가 발생했습니다.' 를 보통 {text} 로 흘려
# 정상 답처럼 대화에 남고 다음 질문의 history 로 모델에게까지 갔다
CHAT_STREAM_ERROR = "답을 만들지 못했습니다"

# 그 밖의 실패도 같은 {error} 이벤트로 끝낸다 — error 는 화면에 보일 문구(문자열), code 는 화면이 갈래를 고르는 기계 값이다.
# 옛 화면은 code 를 몰라도 error 만으로 오류를 보인다
#   not_found        — 대화할 자료(cnts_id)가 서지에 없다. 전에는 '도서를 찾을 수 없습니다.' 를 보통 {text} 로 흘려 답처럼 남았다
#   empty_answer     — LLM 이 글 조각 하나 없이 [DONE] 으로 끝났다. 전에는 빈 답이 정상 답으로 대화에 남았다
#   retrieval_failed — 청크 검색(임베딩·Milvus)이 실패했다. 전에는 로그만 남기고 근거 없이 질문만 보내 답을 지어냈다
CHAT_NOT_FOUND_ERROR = "자료를 찾을 수 없습니다"
CHAT_EMPTY_ANSWER_ERROR = "답을 만들지 못했습니다"
CHAT_RETRIEVAL_ERROR = "자료 내용을 읽지 못했습니다. 잠시 뒤 다시 시도하세요"


def _error_event(message: str, code: str) -> str:
    return f"data: {json.dumps({'error': message, 'code': code}, ensure_ascii=False)}\n\n"

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


def chat_prompt(book: BookOut) -> PromptTemplate:
    """대화 시스템 프롬프트 — 문서 종류(doc_type)의 변형이 있으면 그것(논문 → book_chat.paper.yaml), 없으면 기본
    book_chat.yaml(책 문구). doc_type 이 비었거나 그 속성이 없는 객체도 기본으로 간다(get_prompt 의 해석 순서)."""
    return get_prompt("book_chat", getattr(book, "doc_type", None) or None)


def _book_references(book: BookOut) -> list[str]:
    """참고문헌 의도('참고문헌'·'인용'·'출처' 등)일 때 모델에 넘길 목록. 대화 엔드포인트가 넘기는 BookOut 에는 extra 가
    없고 references 칸이 extra["references"] 를 싣는다(ORM Book 도 같은 이름의 property). 없으면 빈 목록."""
    return list(getattr(book, "references", None) or [])


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
        yield _error_event(CHAT_NOT_FOUND_ERROR, "not_found")
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
        refs = _book_references(book)
        if refs:
            ref_context_block = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(refs[:50]))
            log.info(f"[{cnts_id}] 참고문헌 의도 감지 → {len(refs)}건 컨텍스트 주입")

    # ── 2b. 청크 검색 (참고문헌 목록을 넣을 때만 건너뜀) ─────
    #    참고문헌 의도여도 목록이 없으면(책·참고문헌을 뽑지 못한 논문) 청크로 돌아간다 — 근거 없이 질문만 보내지 않는다.
    #    검색이 실패하면 근거 없이 답하지 않는다 — LLM 을 부르지 않고 retrieval_failed 로 끝낸다. 스트림 안이라 어떤 예외든
    #    이벤트로 알려야 한다(응답 머리가 이미 나가 500 으로 바꿀 수 없다). 검색은 됐는데 청크가 0개인 것(본문 미적재)은
    #    실패가 아니다 — 지금처럼 서지·요약만으로 답한다
    hits = []
    if not ref_context_block:
        try:
            dense, sparse = embed_texts([search_query], is_query=True)
            hits = search_chunks(dense[0], sparse[0], top_k=cfg.BOOK_CHAT_SEARCH_TOP_K, book_filter=cnts_id)
        except Exception as e:
            log.error("[%s] 채팅 청크 검색 실패 — 답하지 않고 끝낸다: %s: %s", cnts_id, type(e).__name__, e, exc_info=True)
            yield _error_event(CHAT_RETRIEVAL_ERROR, "retrieval_failed")
            yield "data: [DONE]\n\n"
            return

    # ── 3. 시스템 프롬프트 + 메시지 빌드 ────────────────────
    author = book.personal_author or book.corporate_author or "저자 미상"
    pub_date = f", {book.pub_date}" if book.pub_date else ""
    tpl = chat_prompt(book)   # 논문이면 논문 문구(book_chat.paper.yaml)
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
                async for delta in sse_deltas(resp):
                    full_response += delta
                    yield f"data: {json.dumps({'text': delta}, ensure_ascii=False)}\n\n"
    except Exception as e:
        log.error("[%s] 채팅 스트리밍 실패(보낸 글 %d자): %s: %s", cnts_id, len(full_response), type(e).__name__, e)
        # 실패한 답에는 출처 칩을 붙이지 않는다 — 오류가 [DONE] 바로 앞, 마지막 이벤트다
        yield f"data: {json.dumps({'error': CHAT_STREAM_ERROR}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # 글 조각 없이 끝난 빈 답(공백뿐 포함) — 정상 답으로 남기지 않는다. 출처 칩도 붙이지 않는다
    if not full_response.strip():
        log.warning("[%s] 채팅 LLM 이 빈 답으로 끝났다(받은 글 %d자)", cnts_id, len(full_response))
        yield _error_event(CHAT_EMPTY_ANSWER_ERROR, "empty_answer")
        yield "data: [DONE]\n\n"
        return

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
