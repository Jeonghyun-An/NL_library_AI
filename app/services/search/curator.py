"""
curator.py — 큐레이션 리포트 생성

컬렉션 도서(최대 CURATION_TOP_K권)를 단일 LLM 호출로 묶어
큐레이션 리포트(intro + 책별 reason)를 생성한다.
pipeline.py에서 가져다 쓰고, 단위 테스트가 직접 임포트한다.
"""
import json
import logging
import re

import httpx

from core.config import get_settings
from services.prompts import get_prompt

log = logging.getLogger(__name__)
cfg = get_settings()


def _parse_curation_result(content: str) -> dict | None:
    """LLM 큐레이션 출력 JSON 파싱. ```json 래핑 처리 포함. 실패 시 None."""
    if "```" in content:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if m:
            content = m.group(1)
    try:
        data = json.loads(content.strip())
        return {
            "intro": str(data.get("intro", "")),
            "items": [
                {"book_id": str(item["book_id"]), "reason": str(item.get("reason", ""))}
                for item in data.get("items", [])
                if "book_id" in item
            ],
        }
    except Exception:
        return None


async def curate_books(
    intent: str,
    query: str,
    books: list,
) -> dict:
    """
    컬렉션 도서(최대 CURATION_TOP_K권) 큐레이션 리포트 생성.
    반환: {"intro": str, "items": [{"book_id": str, "reason": str}]}
    book_id는 cnts_id.
    """
    target_books = books[: cfg.CURATION_TOP_K]
    books_lines = []
    for i, book in enumerate(target_books, 1):
        lines = [f"[도서 {i}]", f"book_id: {book.cnts_id}"]
        if book.title:
            lines.append(f"제목: {book.title}")
        author = getattr(book, "personal_author", None) or getattr(book, "corporate_author", None)
        if author:
            lines.append(f"저자: {author}")
        if book.summary:
            lines.append(f"요약: {book.summary[:400]}")
        if book.plot:
            lines.append(f"줄거리: {book.plot[:200]}")
        if book.themes:
            lines.append(f"테마: {book.themes[:100]}")
        books_lines.append("\n".join(lines))

    books_context = "\n\n".join(books_lines)

    tpl = get_prompt("curation")
    system_message, user_message, params = tpl.render(
        intent=intent,
        query=query,
        books_context=books_context,
    )

    # 도서 수에 비례해 출력 토큰 확보 (책별 reason ~120토큰 + intro 여유분)
    max_tokens = max(cfg.CURATION_MAX_TOKENS, 400 + 120 * len(target_books))

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json={
                    "model": cfg.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user",   "content": user_message},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": params.get("temperature", cfg.CURATION_TEMPERATURE),
                },
                timeout=float(cfg.CURATION_TIMEOUT),
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            result = _parse_curation_result(content)
            if result is None:
                raise ValueError(f"JSON 파싱 실패: {content[:200]}")
            return result
    except Exception as e:
        log.error(f"큐레이션 생성 실패: {e}")
        return {
            "intro": "",
            "items": [{"book_id": b.cnts_id, "reason": ""} for b in target_books],
        }
