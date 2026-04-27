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

log = logging.getLogger(__name__)

_SYSTEM = """\
사용자의 도서관 검색어에서 날짜·정렬 조건만 JSON으로 추출하세요.

출력 형식 (JSON 한 줄):
{
  "pub_year_from": 발행 시작 연도 4자리 정수 또는 null,
  "pub_year_to":   발행 종료 연도 4자리 정수 또는 null,
  "sort_by":       "recent" | "oldest" | null,
  "has_filter":    true | false
}

규칙:
- "최신", "최근", "가장 최근", "최신판" → sort_by: "recent"
- "오래된", "초기", "처음 나온"         → sort_by: "oldest"
- "올해"                                → pub_year_from = pub_year_to = 현재연도
- "YYYY년" (단독 언급)                  → pub_year_from = pub_year_to = YYYY
- "YYYY년 이후"                         → pub_year_from = YYYY
- "YYYY년 이전"                         → pub_year_to = YYYY
- "최근 N년"                            → pub_year_from = 현재연도 - N
- has_filter: 위 항목 중 하나라도 있으면 true
- JSON만 출력하고 다른 설명 없음"""


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
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json={
                    "model": cfg.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": (
                            f"오늘 날짜: {today} (현재 연도: {current_year})\n"
                            f"검색어: {query}"
                        )},
                    ],
                    "max_tokens": 128,
                    "temperature": 0.0,
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
