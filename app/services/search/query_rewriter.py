import httpx
from core.config import get_settings

_REWRITE_SYSTEM = """당신은 도서관 검색 전문가입니다.
사용자의 자연어 검색어를 의미 기반 도서 검색에 최적화된 쿼리로 변환하세요.
- 비유적 표현을 구체적 주제/키워드로 변환
- 감정·분위기 표현을 문학 장르·테마로 확장
- 특정 도서 언급 시 해당 도서의 핵심 특징을 추출
변환된 쿼리만 출력하세요. 한국어로 작성하세요."""


async def rewrite_query(query: str) -> str:
    cfg = get_settings()
    payload = {
        "model": cfg.VLLM_MODEL,
        "messages": [
            {"role": "system", "content": _REWRITE_SYSTEM},
            {"role": "user", "content": f"원본 쿼리: {query}"},
        ],
        "max_tokens": 256,
        "temperature": 0.0,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{cfg.VLLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
