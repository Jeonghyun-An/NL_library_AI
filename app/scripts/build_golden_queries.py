"""build_golden_queries.py — 검색 품질 평가용 골든 쿼리 세트 생성.

배경
----
검색 파이프라인(청킹·리랭커·라우팅 등)을 바꿀 때마다 "검색 품질이 실제로
좋아졌는지"를 감으로만 판단하고 있었다. 이 스크립트는 이미 인덱싱된 실제
카탈로그에서 메타데이터를 이용해 "이 질의를 던지면 이 책/논문이 나와야 한다"는
쿼리-정답 쌍을 기계적으로(LLM 호출 없이) 생성한다.

쿼리는 세 가지 유형을 섞어서 만든다 — 제목을 그대로 베끼면 어휘 매칭만으로도
항상 통과해버려 검증 의미가 없으므로, 제목은 쓰지 않는다:
  keyword   : book.keyword 필드를 자연어 주제어로 사용 (의미 검색 신호)
  metadata  : 기관명 + 발행년도를 자연어 문장으로 결합 (메타데이터 필터 경로 검증)
  abstract  : 초록 앞부분을 그대로 질의로 사용 (제목 어휘와 겹치지 않는 순수 의미 검색)

이 스크립트가 만드는 건 "후보"다. 기계적으로 뽑은 것이라 애매하거나 중복된
항목이 섞일 수 있으니, 출력 JSON을 사람이 한 번 훑어보고 이상한 항목을 지운
뒤 eval_search_quality.py 에 넘기는 걸 권장한다.

읽기 전용이다. DB·색인에 아무것도 쓰지 않는다.

사용법
------
    docker exec -w /app nl-lib-fastapi python -m scripts.build_golden_queries \
        --n 40 --out /app/data/golden_queries.json

    # 이미 만든 세트에 추가로 더 뽑고 싶을 때 (--n 만큼 새로 추가, 기존 book_id는 건너뜀)
    docker exec -w /app nl-lib-fastapi python -m scripts.build_golden_queries \
        --n 20 --out /app/data/golden_queries.json --append
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re

from sqlalchemy import text

from db.postgres import AsyncSessionLocal

# 결과가 안정적이길 원하면 고정, 매번 다른 표본을 원하면 None으로 바꿔서 실행
RANDOM_SEED = 20260903


def _first_sentence(text_: str, max_chars: int = 70) -> str:
    """초록 앞부분을 문장 경계(또는 max_chars)에서 자른다."""
    text_ = re.sub(r"\s+", " ", text_).strip()
    m = re.search(r"^.{20," + str(max_chars) + r"}?[.!?。]", text_)
    return (m.group().strip() if m else text_[:max_chars]).strip()


def _doc_scope(book_id: str, doc_type: str | None) -> str:
    if (doc_type or "") == "paper" or book_id.startswith("KCI_FI"):
        return "paper"
    return "book"


def _build_candidates(rows: list[dict]) -> list[dict]:
    candidates: list[dict] = []
    for i, r in enumerate(rows):
        book_id = r["cnts_id"]
        scope = _doc_scope(book_id, r.get("doc_type"))
        kind = ["keyword", "metadata", "abstract"][i % 3]

        query = None
        if kind == "keyword" and r.get("keyword"):
            terms = [t.strip() for t in r["keyword"].split(",") if t.strip()]
            if len(terms) >= 2:
                query = " ".join(terms[:3])
        elif kind == "metadata" and r.get("corporate_author") and r.get("pub_date") and r.get("keyword"):
            # 기관+연도만 쓰면 같은 기관·같은 해 발행물이 여럿일 때 정답을 특정할 수
            # 없다(실측: 이 유형만 recall@10 7.7%로 붕괴, 나머지 두 유형은 60~82%).
            # 실제 사용자 질의(README 예시: "기획예산처 2024년 이후 보고서")처럼
            # 주제어를 반드시 함께 넣어 정답을 특정할 수 있게 한다.
            year = (r["pub_date"] or "")[:4]
            topic = r["keyword"].split(",")[0].strip()
            if year.isdigit() and topic:
                query = f"{r['corporate_author']}에서 {year}년에 발행한 {topic} 관련 자료"
        elif kind == "abstract" and r.get("abstract") and len(r["abstract"]) > 60:
            query = _first_sentence(r["abstract"])

        # 선택한 유형에 쓸 필드가 없으면 다른 유형으로 폴백 시도
        if not query:
            if r.get("keyword"):
                terms = [t.strip() for t in r["keyword"].split(",") if t.strip()]
                if len(terms) >= 2:
                    query, kind = " ".join(terms[:3]), "keyword"
            if not query and r.get("abstract") and len(r["abstract"]) > 60:
                query, kind = _first_sentence(r["abstract"]), "abstract"

        if not query:
            continue  # 이 문서는 쓸 만한 필드가 없음 — 건너뜀

        candidates.append({
            "query": query,
            "expected_book_id": book_id,
            "doc_scope": scope,
            "query_type": kind,
            "title": r["title"],  # 사람이 검토할 때 참고용, 평가에는 안 씀
        })
    return candidates


async def fetch_rows(n: int, exclude: set[str]) -> list[dict]:
    sql = """
        SELECT cnts_id, title, keyword, abstract, corporate_author, pub_date, doc_type
        FROM library_catalog
        WHERE is_embedded = true
          AND (keyword IS NOT NULL OR abstract IS NOT NULL)
        ORDER BY random()
        LIMIT :limit
    """
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text(sql), {"limit": n * 3})).mappings().all()
    rows = [dict(r) for r in rows if r["cnts_id"] not in exclude]
    return rows[: n * 2]  # 후보 필드 부족으로 일부 스킵될 걸 감안해 넉넉히


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30, help="생성할 쿼리 수(목표치)")
    ap.add_argument("--out", default="/app/data/golden_queries.json")
    ap.add_argument("--append", action="store_true", help="기존 파일에 추가(중복 book_id는 스킵)")
    args = ap.parse_args()

    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    existing: list[dict] = []
    exclude: set[str] = set()
    if args.append:
        try:
            with open(args.out, encoding="utf-8") as f:
                existing = json.load(f)
            exclude = {e["expected_book_id"] for e in existing}
        except FileNotFoundError:
            pass

    rows = await fetch_rows(args.n, exclude)
    candidates = _build_candidates(rows)[: args.n]

    out = existing + candidates
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    by_type: dict[str, int] = {}
    for c in candidates:
        by_type[c["query_type"]] = by_type.get(c["query_type"], 0) + 1

    print(f"신규 {len(candidates)}건 생성 (요청 {args.n}건 중 필드 부족으로 {args.n - len(candidates)}건 스킵)")
    print(f"유형별: {by_type}")
    print(f"누적 {len(out)}건 저장: {args.out}")
    print("→ 사람이 한 번 훑어보고 애매한 질의는 지운 뒤 eval_search_quality.py로 실행하세요.")


if __name__ == "__main__":
    asyncio.run(main())
