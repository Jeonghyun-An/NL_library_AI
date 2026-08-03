"""
eval_summ_ablation.py — 요약 품질 대조 실험: 고정 섹션 vs 의미 경계 섹션(본 발명).

가설: 의미 경계로 나눈 섹션은 주제가 온전해, 계층 요약(섹션요약→문서요약) 품질이
      고정 크기 섹션보다 낫다. (청킹 발명의 실질 효과가 검색보다 요약에서 드러남)

방법 (통제 실험 — 섹션 분할 방식만 다르고 요약 파이프라인·모델 동일):
  1) book_sections.full_text 를 이어붙여 문서 원문 복원
  2) 같은 원문을 두 방식으로 섹션 분할
       - semantic : semantic_chunk(min=SECTION_MIN, max=SECTION_MAX)  ← 본 발명
       - fixed    : 같은 평균 크기의 고정 문자 윈도우
  3) 각 섹션 분할로 프로덕션 계층 요약 실행:
       summarize_section(섹션별) → summarize_book_from_sections(문서 요약)
  4) LLM 심판이 블라인드 A/B 페어와이즈로 우열 판정 (충실성·포괄성·일관성)
     위치 편향 제거 위해 A/B 순서를 바꿔 2회 판정, 두 번 다 이겨야 승리 인정

컨테이너 안에서 실행:
  이미지에 포함되어 있으므로 복사 없이 실행:
    docker exec -w /app nl-lib-fastapi python -m scripts.eval_summ_ablation --help
  docker exec -w /app nl-lib-fastapi python -m scripts.eval_summ_ablation --n 30

주의: LLM 호출이 많다(문서당 섹션요약+문서요약+심판 2회). 운영 gemma를 공유하므로
      동시성(--concurrency)을 낮게 두고, 트래픽 적은 시간대 권장. 표본도 작게(기본 30).
"""
import argparse
import asyncio
import json
import math
import re
import statistics

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import get_settings
from services.ingestion.embedder import embed_texts
from services.ingestion.chunker import semantic_chunk

cfg = get_settings()


async def _llm(messages: list[dict], max_tokens: int = 400,
               temperature: float = 0.1, timeout: float = 90.0) -> str:
    """LLM 직접 호출 (pipeline.py 와 동일 방식 — 구버전 이미지 호환)."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{cfg.LLM_BASE_URL}/chat/completions",
            json={"model": cfg.LLM_MODEL, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=float(timeout),
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

_SAMPLE_SQL = """
    SELECT c.cnts_id, c.title,
           COALESCE(c.personal_author, c.corporate_author, '미상') AS author
    FROM library_catalog c
    WHERE c.is_embedded = true
      AND c.cnts_id LIKE 'KCI_FI%'
      AND c.title IS NOT NULL AND length(btrim(c.title)) > 3
      AND EXISTS (SELECT 1 FROM book_sections s WHERE s.book_id = c.cnts_id)
    ORDER BY md5(c.cnts_id || CAST(:seed AS text))
    LIMIT :n
"""
# setseed()+random() 은 random() 값을 힙 스캔 순서대로 배정하므로, 후보 집합이 같아도
# 행 UPDATE 로 힙 순서가 바뀌면 표본이 달라진다(실측: 30건 중 7건만 유지).
# id 해시 정렬은 힙 순서와 무관해 같은 후보 집합이면 항상 같은 표본을 준다.

_SECTIONS_SQL = """
    SELECT book_id, section_idx, full_text
    FROM book_sections
    WHERE book_id = ANY(:ids)
    ORDER BY book_id, section_idx
"""


def _embed_dense(texts):
    dense, _ = embed_texts(texts)
    return dense


def make_fixed_sections(text_: str, size_chars: int) -> list[str]:
    """의미·문장 경계 무시 고정 문자 윈도우 (종래 섹션 분할)."""
    t = (text_ or "").strip()
    if not t:
        return []
    size = max(200, size_chars)
    return [t[i:i + size].strip() for i in range(0, len(t), size) if t[i:i + size].strip()]


# 계층 요약 프롬프트 — 양 조건(의미/고정)에 동일하게 적용 (통제 변수)
_SEC_SYS = (
    "당신은 학술 문헌 요약 전문가입니다. 주어진 섹션 내용을 3~5문장으로 충실히 요약하세요. "
    "원문에 없는 내용은 지어내지 마세요."
)
_DOC_SYS = (
    "당신은 학술 문헌 요약 전문가입니다. 섹션 요약들을 종합하여 논문 전체 초록을 작성하세요. "
    "'본 논문은' 또는 '본 연구는' 으로 시작하고, 배경·방법·결과·결론이 자연스럽게 담기게 하되 "
    "원문에 없는 내용은 지어내지 마세요. 800자 내외."
)


async def summarize_via_sections(title: str, author: str, section_texts: list[str]) -> str:
    """계층 요약: 섹션별 요약 → 문서 요약. (양 조건 동일 프롬프트 — 섹션 분할만 변수)"""
    sec_sums = []
    for st in section_texts:
        if not st or not st.strip():
            continue
        try:
            s = await _llm(
                [{"role": "system", "content": _SEC_SYS},
                 {"role": "user", "content": f"[논문 제목] {title}\n\n[섹션 내용]\n{st[:8000]}\n\n위 섹션을 요약하세요."}],
                max_tokens=400, temperature=0.2, timeout=cfg.SUMMARIZER_SECTION_TIMEOUT,
            )
            if s and s.strip():
                sec_sums.append(s.strip())
        except Exception:
            pass
    if not sec_sums:
        return ""
    combined = "\n\n".join(f"[섹션 {i+1}] {s}" for i, s in enumerate(sec_sums))[:12000]
    try:
        return (await _llm(
            [{"role": "system", "content": _DOC_SYS},
             {"role": "user", "content": f"[제목] {title}\n[저자] {author}\n\n[섹션 요약]\n{combined}\n\n위를 바탕으로 초록을 작성하세요."}],
            max_tokens=1200, temperature=0.2, timeout=cfg.SUMMARIZER_BOOK_TIMEOUT,
        )).strip()
    except Exception:
        return ""


_JUDGE_SYS = (
    "당신은 학술 문헌 요약 품질 평가자입니다. 원문을 기준으로 두 요약 A, B를 비교해 "
    "어느 쪽이 더 우수한지 판정하세요. 평가 기준: ① 충실성(원문 근거, 왜곡·환각 없음) "
    "② 포괄성(핵심 내용 누락 없음) ③ 일관성(주제가 매끄럽게 이어짐). "
    "반드시 마지막 줄에 다음 형식으로만 답하세요: '판정: A' 또는 '판정: B' 또는 '판정: 무승부'."
)


async def judge(title: str, source: str, a: str, b: str) -> str | None:
    user = (
        f"[원문 제목]\n{title}\n\n"
        f"[원문 발췌]\n{source[:6000]}\n\n"
        f"[요약 A]\n{a}\n\n[요약 B]\n{b}\n\n"
        "어느 요약이 더 우수합니까? 기준(충실성·포괄성·일관성)에 따라 판정하세요."
    )
    try:
        out = await _llm(
            [{"role": "system", "content": _JUDGE_SYS}, {"role": "user", "content": user}],
            max_tokens=400, temperature=0.1, timeout=90,
        )
    except Exception:
        return None
    m = re.search(r"판정\s*:?\s*(A|B|무승부)", out or "")
    return m.group(1) if m else None


def binom_two_sided(k: int, n: int) -> float:
    """양측 정확 이항검정 p (p0=0.5). scipy 없이 계산 — 컨테이너 의존성 추가 없음."""
    if n == 0:
        return 1.0
    k = min(k, n - k)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


async def process_doc(row, full_text: str, sem: asyncio.Semaphore) -> dict | None:
    async with sem:
        # 1) 섹션 분할 (semantic vs fixed)
        sem_secs = semantic_chunk(
            full_text, _embed_dense, page_map={},
            min_tokens=cfg.SECTION_MIN_TOKENS, max_tokens=cfg.SECTION_MAX_TOKENS,
            apply_byte_guard=False,
        )
        sem_texts = [c.text for c in sem_secs if c.text and c.text.strip()]
        if len(sem_texts) < 2:
            return None  # 섹션이 1개면 분할 차이가 없어 비교 무의미
        avg = int(round(statistics.mean(len(t) for t in sem_texts)))
        fix_texts = make_fixed_sections(full_text, avg)

        # 2) 계층 요약
        title, author = row.title, row.author
        sum_sem = await summarize_via_sections(title, author, sem_texts)
        sum_fix = await summarize_via_sections(title, author, fix_texts)
        if not sum_sem or not sum_fix:
            return None

        # 3) 블라인드 페어와이즈 심판 (위치 스왑 2회)
        c1 = await judge(title, full_text, sum_sem, sum_fix)   # A=semantic, B=fixed
        c2 = await judge(title, full_text, sum_fix, sum_sem)   # A=fixed,    B=semantic
        # 두 판정을 위치만 바꿔 물었으므로, 일관된 판정이라면 서로 뒤집힌 답이 나와야 한다.
        # 그렇지 않은 경우(inconsistent)는 무승부가 아니라 '심판이 흔들린 것'이므로
        # 같은 tie 로 묶으면 심판 신뢰도가 결과에 숨는다 → 따로 센다.
        if c1 == "A" and c2 == "B":
            winner, verdict = "semantic", "consistent"
        elif c1 == "B" and c2 == "A":
            winner, verdict = "fixed", "consistent"
        elif c1 == "무승부" and c2 == "무승부":
            winner, verdict = "tie", "consistent"
        else:
            winner, verdict = "tie", "inconsistent"

        return {
            "id": row.cnts_id, "title": title,
            "sem_sections": len(sem_texts), "fixed_sections": len(fix_texts),
            "avg_section_chars": avg,
            "winner": winner, "verdict": verdict, "vote1": c1, "vote2": c2,
            "summary_semantic": sum_sem, "summary_fixed": sum_fix,
        }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30, help="표본 문서 수 (LLM 부하 큼)")
    ap.add_argument("--seed", type=float, default=0.42)
    ap.add_argument("--concurrency", type=int, default=4, help="동시 문서 처리 수")
    ap.add_argument("--out", type=str, default="/app/data/eval_summ_ablation.json")
    args = ap.parse_args()

    engine = create_async_engine(cfg.DATABASE_URL)
    async with engine.connect() as conn:
        rows = (await conn.execute(text(_SAMPLE_SQL),
                                   {"n": args.n, "seed": str(args.seed)})).fetchall()
        ids = [r.cnts_id for r in rows]
        sec_rows = (await conn.execute(text(_SECTIONS_SQL), {"ids": ids})).fetchall()
    await engine.dispose()

    doc_parts: dict[str, list[str]] = {}
    for r in sec_rows:
        doc_parts.setdefault(r.book_id, []).append(r.full_text or "")
    full_text = {bid: "\n\n".join(p).strip() for bid, p in doc_parts.items()}

    print("=" * 74)
    print("요약 품질 대조 실험 — 고정 섹션 vs 의미 경계 섹션(본 발명)")
    print("=" * 74)
    print(f"표본 문서 : {len(rows)} (seed={args.seed}) · 심판 = {cfg.LLM_MODEL} · 동시성 {args.concurrency}")
    print("계층 요약(섹션요약→문서요약) 실행 + 블라인드 페어와이즈 판정 중… (수 분 소요)")
    print("-" * 74)

    sem = asyncio.Semaphore(args.concurrency)
    tasks = [process_doc(r, full_text.get(r.cnts_id, ""), sem)
             for r in rows if len(full_text.get(r.cnts_id, "")) >= 300]
    results = [x for x in await asyncio.gather(*tasks, return_exceptions=True)
               if isinstance(x, dict)]

    if not results:
        print("비교 가능한 문서가 없습니다 (원문 부족 또는 요약 실패).")
        return

    n = len(results)
    win_sem = sum(1 for r in results if r["winner"] == "semantic")
    win_fix = sum(1 for r in results if r["winner"] == "fixed")
    true_tie = sum(1 for r in results if r["winner"] == "tie" and r["verdict"] == "consistent")
    incons = sum(1 for r in results if r["verdict"] == "inconsistent")
    decided = win_sem + win_fix
    agree = round((n - incons) / n, 4) if n else None
    p_val = round(binom_two_sided(win_sem, decided), 4)

    sec_sem = statistics.mean(r["sem_sections"] for r in results)
    sec_fix = statistics.mean(r["fixed_sections"] for r in results)
    fewer = sum(1 for r in results if r["sem_sections"] < r["fixed_sections"])

    print(f"평가 완료 문서 : {n}")
    print(f"  의미 경계 승 : {win_sem}  ({win_sem/n*100:.1f}%)")
    print(f"  고정 분할 승 : {win_fix}  ({win_fix/n*100:.1f}%)")
    print(f"  무승부       : {true_tie}  ({true_tie/n*100:.1f}%)")
    print(f"  판정 불일치  : {incons}  ({incons/n*100:.1f}%)  ← 위치 스왑 시 판정이 뒤집히지 않음")
    print(f"  심판 일치율  : {agree*100:.1f}%   (낮으면 심판 신뢰도 한계로 별도 보고 필요)")
    if decided:
        print(f"  → 승부난 것 중 의미 경계 승률 : {win_sem/decided*100:.1f}%  (n_decided={decided})")
    print(f"  부호검정(양측) p = {p_val}"
          f"{'  → 품질 차이 유의하지 않음(동등)' if p_val > 0.05 else '  → 유의한 차이'}")
    print(f"  섹션 수      : 의미 {sec_sem:.1f} vs 고정 {sec_fix:.1f}  "
          f"(의미가 더 적은 문서 {fewer}/{n})")
    print("=" * 74)

    out = {
        "corpus": {"docs": n, "seed": args.seed, "judge": cfg.LLM_MODEL},
        "result": {"semantic_win": win_sem, "fixed_win": win_fix, "tie": true_tie,
                   "inconsistent": incons, "judge_agreement": agree,
                   "n_decided": decided, "sign_test_p": p_val,
                   "semantic_winrate_overall": round(win_sem / n, 4),
                   "semantic_winrate_decided": round(win_sem / decided, 4) if decided else None,
                   "sections_semantic_mean": round(sec_sem, 2),
                   "sections_fixed_mean": round(sec_fix, 2),
                   "docs_with_fewer_semantic_sections": fewer},
        "details": results,
    }
    try:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"JSON 저장(요약 원문 포함): {args.out}")
    except Exception as e:
        print(f"(JSON 저장 실패: {e})")


if __name__ == "__main__":
    asyncio.run(main())
