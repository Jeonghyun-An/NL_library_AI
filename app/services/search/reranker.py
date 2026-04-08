import json
import httpx
from core.config import get_settings

_SYSTEM = """당신은 도서 추천 전문가입니다.
사용자의 검색 의도와 후보 도서 목록을 분석하여 가장 관련성 높은 도서 순으로 재정렬하세요.
반드시 아래 JSON 형식으로만 출력하세요:
[{"cnts_id": "...", "score": 0.0~1.0, "reason": "한국어로 유사 이유 1문장"}, ...]"""


async def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    cfg = get_settings()
    candidate_text = "\n".join(
        f"{i+1}. [{c['cnts_id']}] {c['title']} (주제: {c.get('subject', '')})"
        for i, c in enumerate(candidates)
    )
    payload = {
        "model": cfg.VLLM_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": (
                f"검색 의도: {query}\n\n후보 도서:\n{candidate_text}\n\n"
                f"상위 {top_k}권을 선택해 JSON으로 응답하세요."
            )},
        ],
        "max_tokens": 1024,
        "temperature": 0.0,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{cfg.VLLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

    ranked: list[dict] = json.loads(raw.replace("```json", "").replace("```", "").strip())
    cand_map = {c["cnts_id"]: c for c in candidates}
    return [
        {**cand_map[item["cnts_id"]], "llm_score": item["score"], "reason": item["reason"]}
        for item in ranked[:top_k]
        if item["cnts_id"] in cand_map
    ]

