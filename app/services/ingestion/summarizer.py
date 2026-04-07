import httpx
from core.config import get_settings

_SUMMARIZE_SYSTEM = """당신은 도서관 사서입니다.
주어진 도서 본문을 읽고 독자가 내용을 이해하고 유사 도서를 찾을 수 있도록
핵심 주제, 문체, 감정 톤, 등장인물(소설의 경우), 주요 메시지를 포함한
200자 내외의 한국어 요약을 작성하세요.
요약 외 다른 말은 하지 마세요."""

_SUMMARIZE_PROMPT = """제목: {title}
저자: {author}

본문:
{text}

위 도서의 의미 기반 검색을 위한 요약을 작성하세요."""


async def summarize_book(title: str, author: str, raw_text: str) -> str:
    cfg = get_settings()
    payload = {
        "model": cfg.VLLM_MODEL,
        "messages": [
            {"role": "system", "content": _SUMMARIZE_SYSTEM},
            {"role": "user", "content": _SUMMARIZE_PROMPT.format(
                title=title, author=author, text=raw_text[:4000]
            )},
        ],
        "max_tokens": cfg.VLLM_MAX_TOKENS,
        "temperature": cfg.VLLM_TEMPERATURE,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{cfg.VLLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

