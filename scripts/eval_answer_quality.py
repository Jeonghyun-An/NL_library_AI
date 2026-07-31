"""
eval_answer_quality.py — RAG 답변 품질 평가 (시스템 특허 "답변 잘 나온다" 근거).

방법 (합성 QA + LLM 심판):
  1) 색인된 논문에서 내용 기반 자연어 질문을 자동 생성 (제목/저자 미언급)
  2) 프로덕션 파이프라인으로 검색+답변 생성
       search(mode="chunk") → 하이브리드 검색 + 리랭킹 + 근거 기반 답변
  3) LLM 심판이 두 축으로 채점 (1~5):
       - 충실성(groundedness): 답변이 검색된 근거에 의해 뒷받침되는가 (환각 없음)
       - 적합성(relevance): 답변이 질문에 실제로 답하는가
  4) 부가: 원본 문서 검색 성공률, 출처 표기율

컨테이너 안에서 실행:
  docker cp scripts/eval_answer_quality.py nl-lib-fastapi:/app/eval_answer_quality.py
  docker exec -w /app nl-lib-fastapi python /app/eval_answer_quality.py --n 30

주의: 운영 gemma 공유 — 동시성 낮게(기본 3), 표본 작게(기본 30). 트래픽 적은 시간대 권장.
심판이 동일 gemma 계열이라 계열 편향 존재(충실성/적합성은 선호 비교보다 객관적이라 영향 적음).
"""
import argparse
import asyncio
import json
import re
import statistics

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import get_settings
from services.search.pipeline import search

cfg = get_settings()

_SAMPLE_SQL = """
    SELECT c.cnts_id, c.title,
           COALESCE(
               NULLIF(btrim(c.abstract),     ''),
               NULLIF(btrim(c.summary),      ''),
               NULLIF(btrim(c.introduction), '')
           ) AS content_src
    FROM library_catalog c
    WHERE c.is_embedded = true
      AND c.cnts_id LIKE 'KCI_FI%'
      AND c.title IS NOT NULL AND length(btrim(c.title)) > 3
      AND COALESCE(NULLIF(btrim(c.abstract),''), NULLIF(btrim(c.summary),''),
                   NULLIF(btrim(c.introduction),'')) IS NOT NULL
    ORDER BY random()
    LIMIT :n
"""


async def _chat(base_url, model, messages, max_tokens=512, temperature=0.2, timeout=90.0) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            json={"model": model, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=float(timeout),
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


# 답변 생성 = gemma(피평가 시스템). 심판 = 선택(기본 gemma, --judge vlm 이면 Qwen3-VL).
async def _gen(messages, **kw) -> str:
    return await _chat(cfg.LLM_BASE_URL, cfg.LLM_MODEL, messages, **kw)


JUDGE_BASE = cfg.LLM_BASE_URL
JUDGE_MODEL = cfg.LLM_MODEL


async def _judge_llm(messages, **kw) -> str:
    return await _chat(JUDGE_BASE, JUDGE_MODEL, messages, **kw)


_QGEN_SYS = (
    "당신은 학술 문헌 기반 질문 생성기입니다. 주어진 논문 내용으로 답할 수 있는, "
    "사용자가 실제로 던질 법한 자연스러운 한국어 질문 1개를 생성하세요. "
    "논문 제목·저자를 직접 언급하지 말고 내용·주제 기반으로 만드세요. 질문만 한 줄로 출력."
)

_FAITH_SYS = (
    "당신은 RAG 답변의 충실성(groundedness) 평가자입니다. 답변이 [근거]에 의해 뒷받침되는지 "
    "1~5로 채점하세요. 5=모든 핵심 내용이 근거에 있음, 3=일부만 뒷받침, 1=근거에 없는 내용(환각) 다수. "
    "반드시 마지막 줄에 '점수: N' 형식으로만 숫자를 쓰세요."
)

_REL_SYS = (
    "당신은 RAG 답변의 질문 적합성 평가자입니다. 답변이 질문에 실제로 답하는지 1~5로 채점하세요. "
    "5=완전히 답함, 3=부분적, 1=동문서답/무응답. 반드시 마지막 줄에 '점수: N' 형식으로만 숫자를 쓰세요."
)


def _parse_score(out: str):
    m = re.search(r"점수\s*:?\s*([1-5])", out or "")
    return int(m.group(1)) if m else None


async def gen_question(content: str) -> str:
    try:
        out = await _gen(
            [{"role": "system", "content": _QGEN_SYS},
             {"role": "user", "content": f"[논문 내용]\n{content[:2500]}\n\n위 내용으로 답할 수 있는 자연스러운 질문 1개:"}],
            max_tokens=120, temperature=0.4,
        )
        return re.sub(r"\s+", " ", out.strip().splitlines()[0]).strip('"').strip()
    except Exception:
        return ""


async def judge_faith(context: str, q: str, a: str):
    out = await _judge_llm(
        [{"role": "system", "content": _FAITH_SYS},
         {"role": "user", "content": f"[근거]\n{context[:8000]}\n\n[질문]\n{q}\n\n[답변]\n{a}\n\n충실성 점수(1~5)와 한 줄 이유:"}],
        max_tokens=300, temperature=0.1,
    )
    return _parse_score(out)


async def judge_rel(q: str, a: str):
    out = await _judge_llm(
        [{"role": "system", "content": _REL_SYS},
         {"role": "user", "content": f"[질문]\n{q}\n\n[답변]\n{a}\n\n적합성 점수(1~5)와 한 줄 이유:"}],
        max_tokens=300, temperature=0.1,
    )
    return _parse_score(out)


_CITATION_RE = re.compile(r"출처|\[출처|p\.\s*\d|KCI_FI\d")


async def process(row, top_k: int, sem: asyncio.Semaphore) -> dict | None:
    async with sem:
        q = await gen_question(row.content_src or "")
        if not q:
            return None
        try:
            resp = await search(q, mode="chunk", top_k=top_k, use_rewrite=False,
                                use_rerank=True, doc_scope="paper", db=None)
        except Exception as e:
            return {"id": row.cnts_id, "q": q, "error": str(e)}

        answer = (resp.answer or "").strip()
        chunks = resp.chunks or []
        context = "\n\n".join(c.text for c in chunks)
        hit = row.cnts_id in {c.book_id for c in chunks}
        if not answer:
            return {"id": row.cnts_id, "q": q, "answer": "", "faith": None,
                    "rel": None, "hit": hit, "cite": False, "n_chunks": len(chunks)}

        faith, rel = await asyncio.gather(
            judge_faith(context, q, answer), judge_rel(q, answer),
            return_exceptions=True,
        )
        faith = faith if isinstance(faith, int) else None
        rel = rel if isinstance(rel, int) else None
        return {
            "id": row.cnts_id, "title": row.title, "q": q, "answer": answer,
            "faith": faith, "rel": rel, "hit": hit,
            "cite": bool(_CITATION_RE.search(answer)), "n_chunks": len(chunks),
        }


def _mean(vals):
    v = [x for x in vals if isinstance(x, int)]
    return round(statistics.mean(v), 2) if v else None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=float, default=0.42)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--judge", choices=["llm", "vlm"], default="llm",
                    help="심판 백엔드: llm=gemma(동일계열), vlm=Qwen3-VL(다른계열, 편향↓)")
    ap.add_argument("--out", type=str, default="/app/data/eval_answer_quality.json")
    args = ap.parse_args()

    global JUDGE_BASE, JUDGE_MODEL
    if args.judge == "vlm":
        JUDGE_BASE, JUDGE_MODEL = cfg.VLM_BASE_URL, cfg.VLM_MODEL

    engine = create_async_engine(cfg.DATABASE_URL)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT setseed(:s)"), {"s": args.seed})
        rows = (await conn.execute(text(_SAMPLE_SQL), {"n": args.n})).fetchall()
    await engine.dispose()

    print("=" * 74)
    print("RAG 답변 품질 평가 (합성 QA + LLM 심판)")
    print("=" * 74)
    print(f"표본 : {len(rows)} · top_k={args.top_k} · 답변={cfg.LLM_MODEL} · 심판={JUDGE_MODEL} · 동시성 {args.concurrency}")
    print("질문 생성 → 검색+답변 → 충실성/적합성 채점 중… (수 분)")
    print("-" * 74)

    sem = asyncio.Semaphore(args.concurrency)
    results = [x for x in await asyncio.gather(*[process(r, args.top_k, sem) for r in rows],
                                               return_exceptions=True)
               if isinstance(x, dict)]
    scored = [r for r in results if r.get("faith") is not None or r.get("rel") is not None]

    n = len(results)
    faith_m = _mean([r.get("faith") for r in results])
    rel_m = _mean([r.get("rel") for r in results])
    hit_rate = round(sum(1 for r in results if r.get("hit")) / n, 3) if n else 0
    cite_rate = round(sum(1 for r in results if r.get("cite")) / n, 3) if n else 0
    faith_ge4 = round(sum(1 for r in results if isinstance(r.get("faith"), int) and r["faith"] >= 4) / n, 3) if n else 0
    rel_ge4 = round(sum(1 for r in results if isinstance(r.get("rel"), int) and r["rel"] >= 4) / n, 3) if n else 0

    print(f"평가 문항 수     : {n}")
    print(f"충실성 평균      : {faith_m} / 5   (4점 이상 비율 {faith_ge4*100:.0f}%)")
    print(f"적합성 평균      : {rel_m} / 5   (4점 이상 비율 {rel_ge4*100:.0f}%)")
    print(f"원문 검색 성공률 : {hit_rate*100:.1f}%  (답변 근거에 원본 문서 포함)")
    print(f"출처 표기율      : {cite_rate*100:.1f}%")
    print("=" * 74)

    out = {
        "corpus": {"n": n, "seed": args.seed, "top_k": args.top_k,
                   "answer_model": cfg.LLM_MODEL, "judge": JUDGE_MODEL},
        "result": {"faithfulness_mean": faith_m, "relevance_mean": rel_m,
                   "faith_ge4_rate": faith_ge4, "rel_ge4_rate": rel_ge4,
                   "retrieval_hit_rate": hit_rate, "citation_rate": cite_rate},
        "details": results,
    }
    try:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"JSON 저장(질문·답변 포함): {args.out}")
    except Exception as e:
        print(f"(JSON 저장 실패: {e})")


if __name__ == "__main__":
    asyncio.run(main())
