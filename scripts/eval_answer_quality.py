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

2단계 분리 (심판 교차검증의 전제):
  판정자를 바꿔가며 비교하려면 **두 판정자가 동일한 답변 집합**을 채점해야 한다.
  생성과 채점을 한 프로세스에서 돌리면 실행마다 표본·질문이 달라져 비교가 무효가 된다.
    --stage generate  질문·답변만 생성해 --answers 에 저장 (심판 미사용)
    --stage judge     저장된 답변을 읽어 채점만 수행 (여러 심판으로 반복 실행)
    --stage all       위 둘을 한 번에 (기본, 단일 심판 용)

컨테이너 안에서 실행:
  docker cp scripts/eval_answer_quality.py nl-lib-fastapi:/app/eval_answer_quality.py
  # 1) 답변 1회 생성 (재사용)
  docker exec -w /app nl-lib-fastapi python /app/eval_answer_quality.py \
      --stage generate --n 30
  # 2) 판정자별 채점 — 동일 답변 집합
  docker exec -w /app nl-lib-fastapi python /app/eval_answer_quality.py \
      --stage judge --judge llm --out /app/data/eval_answer_quality_gemma.json
  docker exec -w /app nl-lib-fastapi python /app/eval_answer_quality.py \
      --stage judge --judge vlm --out /app/data/eval_answer_quality_qwen.json

주의: 운영 gemma 공유 — 동시성 낮게(기본 3), 표본 작게(기본 30). 트래픽 적은 시간대 권장.
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

# setseed()+random() 은 random() 값을 '힙 스캔 순서'대로 배정한다. 따라서 후보 집합이
# 똑같아도 행이 UPDATE 되어 힙 순서가 바뀌면 표본이 통째로 달라진다.
#   실측(PG16, 후보 200건·표본 30건, 후보집합 불변·UPDATE 만 발생):
#     setseed+random  30건 중 7건만 유지  /  md5 해시 정렬  30건 전부 유지
# 색인 갱신이 잦은 이 DB에서 판정자별 실행의 표본이 어긋난 실제 원인이 이것이다.
# 해시 정렬은 힙 순서와 무관하나, 신규 색인으로 후보 집합 자체가 늘면 표본도 바뀐다.
# → 판정자 간 비교는 해시 정렬만으로 부족하고, 아래 --stage 분리로 답변을 고정해야 한다.
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
    ORDER BY md5(c.cnts_id || CAST(:seed AS text))
    LIMIT :n
"""


def _strip_reasoning(raw: str, thinking: bool) -> tuple[str, bool]:
    """추론 블록을 떼고 실제 답변만 반환 → (본문, 정상종료).

    Qwen3 계열 chat template 은 프롬프트 끝에 `<think>` 를 미리 붙여, 출력이
    여는 태그 없이 "추론… </think> 실제답변" 형태로 온다. thinking 을 켠 채
    max_tokens 가 모자라면 `</think>` 전에 잘려 '점수: N' 이 아예 안 나온다
    (심판=Qwen3-VL 일 때 채점 결측의 실제 원인). 미종료는 실패로 보고 재시도한다.
    """
    if "</think>" in raw:
        return raw.split("</think>")[-1].strip(), True
    if thinking:
        return "", False
    return raw.strip(), True


async def _chat(base_url, model, messages, *, max_tokens=512, temperature=0.2,
                timeout=90.0, thinking=None) -> tuple[str, bool]:
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": temperature}
    # vLLM 은 chat_template_kwargs 를 템플릿에 그대로 전달. None 이면 미전송(기존 동작).
    if thinking is not None:
        payload["chat_template_kwargs"] = {"enable_thinking": thinking}
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{base_url}/chat/completions", json=payload,
                                 timeout=float(timeout))
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        msg = choice.get("message", {})
        raw = (msg.get("content") or "").strip()
        if msg.get("reasoning_content"):
            # vLLM --reasoning-parser 사용 시 추론이 별 필드라 content 는 이미 깨끗함
            return raw, True
        return _strip_reasoning(raw, thinking=bool(thinking))


# 답변 생성 = gemma(피평가 시스템). 심판 = 선택(기본 gemma, --judge vlm 이면 Qwen3-VL).
async def _gen(messages, **kw) -> str:
    out, complete = await _chat(cfg.LLM_BASE_URL, cfg.LLM_MODEL, messages,
                                thinking=cfg.LLM_THINK, **kw)
    if not complete:
        out, _ = await _chat(cfg.LLM_BASE_URL, cfg.LLM_MODEL, messages,
                             thinking=False, **kw)
    return out


JUDGE_BASE = cfg.LLM_BASE_URL
JUDGE_MODEL = cfg.LLM_MODEL
JUDGE_THINK: bool | None = cfg.LLM_THINK


async def _judge_llm(messages, **kw) -> str:
    out, complete = await _chat(JUDGE_BASE, JUDGE_MODEL, messages,
                                thinking=JUDGE_THINK, **kw)
    if not complete:  # 추론 미종료 → thinking 끄고 1회 재시도
        out, _ = await _chat(JUDGE_BASE, JUDGE_MODEL, messages, thinking=False, **kw)
    return out


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


async def _scored_judge(sys_prompt: str, user_prompt: str) -> tuple[int | None, str | None]:
    """채점 1건 → (점수, 실패시 원문 꼬리).

    파싱 실패를 조용히 결측으로 흘리면 그 문항이 집계에서 사라져 선택 편향이 된다.
    → 형식만 강제해 1회 재시도하고, 그래도 실패하면 원문 꼬리를 남겨 감사 가능하게 한다.
    """
    out = ""
    for attempt in range(2):
        prompt = user_prompt if attempt == 0 else (
            user_prompt + "\n\n설명 없이 '점수: N' 한 줄만 출력하세요.")
        try:
            out = await _judge_llm(
                [{"role": "system", "content": sys_prompt},
                 {"role": "user", "content": prompt}],
                max_tokens=600 if attempt == 0 else 32,
                temperature=0.1,
            )
        except Exception as e:
            out = f"<error: {e}>"
            continue
        s = _parse_score(out)
        if s is not None:
            return s, None
    return None, (out or "")[-300:]


async def gen_question(content: str) -> str:
    try:
        out = await _gen(
            [{"role": "system", "content": _QGEN_SYS},
             {"role": "user", "content": f"[논문 내용]\n{content[:2500]}\n\n위 내용으로 답할 수 있는 자연스러운 질문 1개:"}],
            max_tokens=120, temperature=0.4,
        )
        return re.sub(r"\s+", " ", out.strip().splitlines()[0]).strip('"').strip() if out.strip() else ""
    except Exception:
        return ""


_CITATION_RE = re.compile(r"출처|\[출처|p\.\s*\d|KCI_FI\d")


# ── 1단계: 질문 생성 + 검색 + 답변 (심판 미사용) ──────────────
async def generate_one(row, top_k: int, sem: asyncio.Semaphore) -> dict:
    async with sem:
        q = await gen_question(row.content_src or "")
        if not q:
            return {"id": row.cnts_id, "title": row.title, "q": "", "answer": "",
                    "context": "", "hit": False, "cite": False, "n_chunks": 0,
                    "status": "qgen_failed"}
        try:
            resp = await search(q, mode="chunk", top_k=top_k, use_rewrite=False,
                                use_rerank=True, doc_scope="paper", db=None)
        except Exception as e:
            return {"id": row.cnts_id, "title": row.title, "q": q, "answer": "",
                    "context": "", "hit": False, "cite": False, "n_chunks": 0,
                    "status": f"search_error: {e}"}

        answer = (resp.answer or "").strip()
        chunks = resp.chunks or []
        return {
            "id": row.cnts_id, "title": row.title, "q": q, "answer": answer,
            "context": "\n\n".join(c.text for c in chunks)[:8000],
            "hit": row.cnts_id in {c.book_id for c in chunks},
            "cite": bool(_CITATION_RE.search(answer)),
            "n_chunks": len(chunks),
            "status": "ok" if answer else "empty_answer",
        }


# ── 2단계: 저장된 답변 채점 ───────────────────────────────────
async def judge_one(item: dict, sem: asyncio.Semaphore) -> dict:
    async with sem:
        out = dict(item)
        if item.get("status") == "empty_answer":
            # 답변이 비었으면 이는 시스템의 실패지 심판의 결측이 아니다.
            # 결측으로 빼면 실패 사례가 집계에서 사라져 점수가 부풀려진다.
            # 적합성 척도가 '1=무응답'을 명시하므로 rel=1 로 채점하고,
            # 충실성은 대조할 진술이 없어 판정 불가(None)로 둔다.
            out.update({"faith": None, "rel": 1,
                        "faith_fail": "empty_answer", "rel_fail": None})
            return out
        if item.get("status") != "ok":
            # 질문 생성/검색 자체가 실패 — 피평가 대상이 아니므로 양쪽 모두 제외
            out.update({"faith": None, "rel": None,
                        "faith_fail": item.get("status"), "rel_fail": item.get("status")})
            return out
        q, a, ctx = item["q"], item["answer"], item.get("context", "")
        (faith, ff), (rel, rf) = await asyncio.gather(
            _scored_judge(_FAITH_SYS,
                          f"[근거]\n{ctx}\n\n[질문]\n{q}\n\n[답변]\n{a}\n\n충실성 점수(1~5)와 한 줄 이유:"),
            _scored_judge(_REL_SYS,
                          f"[질문]\n{q}\n\n[답변]\n{a}\n\n적합성 점수(1~5)와 한 줄 이유:"),
        )
        out.update({"faith": faith, "rel": rel, "faith_fail": ff, "rel_fail": rf})
        return out


def _metric(results: list[dict], key: str) -> dict:
    """유효 응답만으로 평균·비율을 내고, 결측을 분모에서 빼되 개수를 명시한다.

    기존 구현은 평균은 결측을 건너뛰고 4점이상 비율은 결측을 분모에 넣어(=오답 취급)
    두 수치가 서로 다른 표본을 가리켰다. 여기서는 분모를 n_valid 로 통일한다.
    """
    vals = [r.get(key) for r in results]
    valid = [v for v in vals if isinstance(v, int)]
    nv = len(valid)
    return {
        "mean": round(statistics.mean(valid), 2) if nv else None,
        "ge4_rate": round(sum(1 for v in valid if v >= 4) / nv, 3) if nv else None,
        "n_valid": nv,
        "n_missing": len(vals) - nv,
        "coverage": round(nv / len(vals), 3) if vals else None,
    }


async def run_generate(args) -> list[dict]:
    engine = create_async_engine(cfg.DATABASE_URL)
    async with engine.connect() as conn:
        rows = (await conn.execute(text(_SAMPLE_SQL),
                                   {"n": args.n, "seed": str(args.seed)})).fetchall()
    await engine.dispose()

    print(f"표본 : {len(rows)} · top_k={args.top_k} · 답변={cfg.LLM_MODEL} · 동시성 {args.concurrency}")
    print("질문 생성 → 검색 + 답변 중… (수 분)")
    sem = asyncio.Semaphore(args.concurrency)
    items = [x for x in await asyncio.gather(
        *[generate_one(r, args.top_k, sem) for r in rows], return_exceptions=True)
        if isinstance(x, dict)]
    items.sort(key=lambda d: d["id"])  # 실행 간 순서 고정
    ok = sum(1 for i in items if i["status"] == "ok")
    print(f"답변 생성 완료 : {ok}/{len(items)} (실패 {len(items)-ok})")
    return items


async def run_judge(items: list[dict], args) -> list[dict]:
    print(f"심판 = {JUDGE_MODEL} (thinking={JUDGE_THINK}) · 채점 대상 {len(items)}건")
    sem = asyncio.Semaphore(args.concurrency)
    scored = [x for x in await asyncio.gather(
        *[judge_one(i, sem) for i in items], return_exceptions=True)
        if isinstance(x, dict)]
    scored.sort(key=lambda d: d["id"])
    return scored


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=float, default=0.42)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--stage", choices=["all", "generate", "judge"], default="all",
                    help="generate=답변만 생성 / judge=저장된 답변 채점 / all=둘 다")
    ap.add_argument("--judge", choices=["llm", "vlm"], default="llm",
                    help="심판 백엔드: llm=gemma(동일계열), vlm=Qwen3-VL(다른계열, 편향↓)")
    ap.add_argument("--judge-think", choices=["auto", "on", "off"], default="auto",
                    help="심판 추론 모드. auto=vlm이면 off(잘림 방지), llm이면 설정값")
    ap.add_argument("--answers", type=str, default="/app/data/eval_answers.json",
                    help="1단계 답변 캐시 경로 (generate 는 쓰고, judge 는 읽음)")
    ap.add_argument("--out", type=str, default="/app/data/eval_answer_quality.json")
    args = ap.parse_args()

    global JUDGE_BASE, JUDGE_MODEL, JUDGE_THINK
    if args.judge == "vlm":
        JUDGE_BASE, JUDGE_MODEL = cfg.VLM_BASE_URL, cfg.VLM_MODEL
        JUDGE_THINK = cfg.VLM_THINK
    if args.judge_think == "on":
        JUDGE_THINK = True
    elif args.judge_think == "off":
        JUDGE_THINK = False
    elif args.judge == "vlm" and JUDGE_THINK is None:
        # 추론형 VLM 은 채점 이유를 사고과정에 쏟아내다 '점수: N' 전에 잘린다 → 기본 off
        JUDGE_THINK = False

    print("=" * 74)
    print("RAG 답변 품질 평가 (합성 QA + LLM 심판)")
    print("=" * 74)

    # ── 1단계 ────────────────────────────────────────────
    if args.stage in ("all", "generate"):
        items = await run_generate(args)
        payload = {"corpus": {"n": len(items), "seed": args.seed, "top_k": args.top_k,
                              "answer_model": cfg.LLM_MODEL},
                   "items": items}
        try:
            with open(args.answers, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"답변 캐시 저장: {args.answers}")
        except Exception as e:
            print(f"(답변 캐시 저장 실패: {e})")
        if args.stage == "generate":
            print("=" * 74)
            print("→ 이제 --stage judge 로 판정자를 바꿔가며 동일 답변을 채점하세요.")
            return
    else:
        with open(args.answers, encoding="utf-8") as f:
            items = json.load(f)["items"]
        print(f"답변 캐시 로드: {args.answers} ({len(items)}건)")

    # ── 2단계 ────────────────────────────────────────────
    print("-" * 74)
    results = await run_judge(items, args)

    n = len(results)
    faith = _metric(results, "faith")
    rel = _metric(results, "rel")
    hit_rate = round(sum(1 for r in results if r.get("hit")) / n, 3) if n else 0
    cite_rate = round(sum(1 for r in results if r.get("cite")) / n, 3) if n else 0

    print("-" * 74)
    print(f"평가 문항 수     : {n}")
    print(f"충실성 평균      : {faith['mean']} / 5   (4점 이상 {faith['ge4_rate']}) "
          f"[유효 {faith['n_valid']}/{n}, 결측 {faith['n_missing']}]")
    print(f"적합성 평균      : {rel['mean']} / 5   (4점 이상 {rel['ge4_rate']}) "
          f"[유효 {rel['n_valid']}/{n}, 결측 {rel['n_missing']}]")
    print(f"원문 검색 성공률 : {hit_rate*100:.1f}%  (답변 근거에 원본 문서 포함)")
    print(f"출처 표기율      : {cite_rate*100:.1f}%")
    if faith["n_missing"] or rel["n_missing"]:
        print("⚠ 결측이 있습니다 — 논문에는 평균과 함께 유효 표본수(n_valid)를 반드시 병기하세요.")
    print("=" * 74)

    out = {
        "corpus": {"n": n, "seed": args.seed, "top_k": args.top_k,
                   "answer_model": cfg.LLM_MODEL, "judge": JUDGE_MODEL,
                   "judge_thinking": JUDGE_THINK, "answers_file": args.answers,
                   "item_ids": [r["id"] for r in results]},
        "result": {"faithfulness": faith, "relevance": rel,
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
