"""
scenario.py — 시나리오 추천 (내 상황에 맞는 도서)

독자의 고민을 받아 각 도서의 감성적 reason + quote를 생성한다.
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


def _parse_scenario_result(content: str) -> dict | None:
    """LLM 시나리오 추천 출력 JSON 파싱. ```json 래핑 처리 포함. 실패 시 None."""
    if "```" in content:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if m:
            content = m.group(1)
    try:
        data = json.loads(content.strip())
        return {
            "intro": str(data.get("intro", "")),
            "items": [
                {
                    "book_id": str(item["book_id"]),
                    "reason": str(item.get("reason", "")),
                    "quote": str(item.get("quote", "")),
                }
                for item in data.get("items", [])
                if "book_id" in item
            ],
        }
    except Exception:
        return None


async def recommend_books(concern: str, books: list) -> dict:
    """
    독자 고민 + 도서 목록 → reason + quote 생성.
    도서 수 제한은 호출자(api/scenario.py)가 req.top_k로 결정한다.
    반환: {"items": [{"book_id": str, "reason": str, "quote": str}]}
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
        if book.read_effect:
            lines.append(f"읽고 난 후: {book.read_effect[:200]}")
        if book.themes:
            lines.append(f"테마: {book.themes[:80]}")
        books_lines.append("\n".join(lines))

    books_context = "\n\n".join(books_lines)

    tpl = get_prompt("scenario_recommend")
    system_message, user_message, params = tpl.render(
        concern=concern,
        books_context=books_context,
    )

    # 출력 예산: intro(~300) + 책별 reason/quote(~250) — 잘리면 JSON 파싱이 깨지므로 넉넉하게
    max_tokens = max(cfg.CURATION_MAX_TOKENS, 600 + 250 * len(target_books))

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
            result = _parse_scenario_result(content)
            if result is None:
                raise ValueError(f"JSON 파싱 실패: {content[:200]}")
            return result
    except Exception as e:
        log.error(f"시나리오 추천 생성 실패: {e}")
        return {
            "intro": "",
            "items": [{"book_id": b.cnts_id, "reason": "", "quote": ""} for b in target_books],
        }
