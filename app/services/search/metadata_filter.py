"""
metadata_filter.py — 쿼리에서 날짜·정렬 조건만 추출

publisher/author 기반 필터는 메타데이터 전용 청크 임베딩이 처리하므로 제외.
여기서는 임베딩으로 처리 불가능한 구조적 조건만 추출:
  - pub_year_from / pub_year_to : Milvus pub_date 스칼라 expression 필터
  - sort_by                     : 결과를 pub_date 기준으로 재정렬
"""
import json
import logging
import re
from dataclasses import dataclass, replace
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


_RECENT_N_YEARS = re.compile(r"최근\s*(\d+)\s*년")


def _year_grounded(year: int, query: str, current_year: int) -> bool:
    """연도가 질의 글자에 근거가 있는가 — 프롬프트 규칙(metadata_filter.yaml)이 연도를 만드는 표현만 본다."""
    if str(year) in query:                                   # 2020년 이후 · 1984
        return True
    if f"{year // 10 * 10}년대" in query:                    # 1930년대 → 1930~1939
        return True
    if year == current_year and "올해" in query:
        return True
    if year == current_year - 1 and ("작년" in query or "지난해" in query):
        return True
    if year == current_year - 2 and "재작년" in query:
        return True
    m = _RECENT_N_YEARS.search(query)                        # 최근 3년 → 2023(2024 로 세기도 한다)~올해
    return bool(m) and current_year - int(m.group(1)) <= year <= current_year


def _drop_ungrounded_years(f: MetadataFilter, query: str, current_year: int) -> MetadataFilter:
    """LLM 이 질의에 없는 연도를 발행 연도 조건으로 거는 일이 있다(운영 2026-10-23) — '올리버'·'올바른'·'올림픽'의 '올'을
    '올해'로 읽어 2026년 자료만, '82년생 김지영'을 1982년 자료만 찾았다. 소장자료 검색은 도서가 0권이 되어 그해 논문으로
    떨어졌고 논문 검색도 그해 논문만 보였다(research/book-search-filter-recall). 근거 없는 연도는 버리고 정렬은 그대로
    둔다. 조건을 빼기만 하고 켜지는 않는다 — has_filter 는 LLM 값이 참이고 남은 조건이 있을 때만 참이다."""
    year_from = f.pub_year_from if f.pub_year_from and _year_grounded(f.pub_year_from, query, current_year) else None
    year_to = f.pub_year_to if f.pub_year_to and _year_grounded(f.pub_year_to, query, current_year) else None
    if (year_from, year_to) == (f.pub_year_from, f.pub_year_to):
        return f
    log.info(f"메타데이터 필터: 질의에 근거 없는 연도 버림 '{query}' "
             f"({f.pub_year_from}~{f.pub_year_to} → {year_from}~{year_to})")
    return replace(f, pub_year_from=year_from, pub_year_to=year_to,
                   has_filter=f.has_filter and bool(year_from or year_to or f.sort_by))


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

        return _drop_ungrounded_years(MetadataFilter(
            pub_year_from=int(data["pub_year_from"]) if data.get("pub_year_from") else None,
            pub_year_to=int(data["pub_year_to"])     if data.get("pub_year_to")   else None,
            sort_by=data.get("sort_by") or None,
            has_filter=bool(data.get("has_filter")),
        ), query, current_year)

    except Exception as e:
        log.warning(f"메타데이터 필터 추출 실패: {e}")
        return MetadataFilter()
