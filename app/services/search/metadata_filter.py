"""
metadata_filter.py — 쿼리에서 날짜·정렬 조건만 추출

publisher/author 기반 필터는 메타데이터 전용 청크 임베딩이 처리하므로 제외.
여기서는 임베딩으로 처리 불가능한 구조적 조건만 추출:
  - pub_year_from / pub_year_to : Milvus pub_date 스칼라 expression 필터
  - sort_by                     : 결과를 pub_date 기준으로 재정렬
"""
import json
import logging
from dataclasses import dataclass
from datetime import date

import httpx
from core.config import get_settings
from services.prompts import get_prompt

log = logging.getLogger(__name__)


@dataclass
class MetadataFilter:
    pub_year_from: int | None = None
    pub_year_to:   int | None = None
    sort_by:       str | None = None   # "recent" | "oldest" | None
    has_filter:    bool = False


async def extract_metadata_filter(query: str) -> MetadataFilter:
    cfg = get_settings()
    today = date.today().isoformat()
    current_year = date.today().year

    try:
        system, user, params = get_prompt("metadata_filter").render(
            today=today, current_year=current_year, query=query,
        )
        async with httpx.AsyncClient(timeout=cfg.METADATA_FILTER_TIMEOUT) as client:
            resp = await client.post(
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json={
                    "model": cfg.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    **params,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()

        if "```" in content:
            for part in content.split("```"):
                part = part.strip().lstrip("json").strip()
                try:
                    data = json.loads(part)
                    break
                except json.JSONDecodeError:
                    continue
            else:
                raise ValueError("JSON 파싱 실패")
        else:
            data = json.loads(content)

        return MetadataFilter(
            pub_year_from=int(data["pub_year_from"]) if data.get("pub_year_from") else None,
            pub_year_to=int(data["pub_year_to"])     if data.get("pub_year_to")   else None,
            sort_by=data.get("sort_by") or None,
            has_filter=bool(data.get("has_filter")),
        )

    except Exception as e:
        log.warning(f"메타데이터 필터 추출 실패: {e}")
        return MetadataFilter()
