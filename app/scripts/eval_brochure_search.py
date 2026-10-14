"""브로셔용 검색 품질 수치 실험 — 키워드 통합검색(BM25) vs SKOVIX.

목적
----
브로셔·부스에 실을 "검색이 얼마나 잘 되나" 수치를 만든다. 평균 점수 하나가 아니라
**무엇을 비교했고 어디까지 말해도 되는지**가 수치와 함께 남도록 만든 하니스다.

비교 방식(arm)
  bm25_meta      키워드 통합검색 기준선. 제목·주제어·초록(없으면 소개)을 음절 bigram 으로
                 색인한 BM25. SKOVIX 가 만든 요약(summary)은 색인하지 않는다 — 통합검색이
                 갖지 못하는 정보라서 넣으면 기준선이 부당하게 강해진다.
  skovix_hybrid  BGE-M3 dense+sparse RRF. 질의 재작성·리랭커 없음.
  skovix_rerank  위 + 리랭커.
  skovix_norewrite 리랭커 + 메타데이터 필터, 질의 재작성 끔 — 2026-10-14 부터 논문 검색의 기본 구성(리랭커에서 갈라지는 분기).
  skovix_rewrite 리랭커 + LLM 질의 재작성(메타데이터 필터 없음).
  skovix_full    pipeline.search 기본 플래그 그대로(LLM 질의 재작성 + 메타데이터 필터 + 리랭커). 2026-10-14 전까지 논문 검색의 운영 기본이었고
                 그 뒤로는 '재작성 켬' 대조 구성이다(논문 검색은 재작성을 끈 채 배포됨).
                 rewrite 와 full 을 나눈 이유 — 단계마다 실제로 기여하는지, 어느 단계가 해치는지 가르기 위해서다.
  prod_api       배포된 POST /api/papers/search 를 그대로 호출(논문 화면과 같은 top_k=20·리랭커). pipeline.search 바깥의 제목 일치율
                 재정렬까지 포함한, 사용자가 실제로 받는 결과. 요청에 재작성 켬을 보내 서버가 무시하는지 확인하는 카나리를 둔다.

질의 세트
  nl      자연어 질문 — 문서 초록에서 LLM 이 "이용자가 검색창에 칠 법한 질문"으로 합성.
          제목·저자 금지, 원문 문장 베끼기 금지(문자열 검사로 거른다). **실사용자 질의가 아니다.**
  golden  (선택) build_golden_queries.py 결과(keyword/metadata/abstract). 문서 필드에서
          기계적으로 뽑은 질의라 "자연어 검색"이라고 표기하면 안 된다.

지표
  Recall@1/5/10, MRR@10, nDCG@10   정답 = 질의의 원문서 1건(known-item). 같은 주제의 다른
                                   문서는 정답이 아니므로 이 값들은 하한이다.
  OTR@10 (On-Topic Rate)           상위 10건 중 질의 주제에 '주로' 맞는 문서의 비율.
                                   (질의, 문서) 쌍을 LLM 이 이진 판정(arXiv:2410.21549 방식).
                                   '정답 1건' 가정에서 자유롭다. 판정은 질의 재작성에 쓰는
                                   모델(gemma)과 다른 계열(VLM)을 기본으로 쓴다 — 같은 모델이
                                   검색에도 판정에도 끼면 순환이 되기 때문.
  모든 값에 질의 단위 부트스트랩 95% 신뢰구간. 방식 간 차이는 쌍대 부트스트랩 + 부호검정.

실행 (운영 서버, nl-lib-fastapi 컨테이너 안 — 읽기 전용, 색인·DB 에 쓰지 않는다)
  docker cp app/scripts/eval_brochure_search.py nl-lib-fastapi:/app/scripts/
  docker exec -w /app nl-lib-fastapi python -m scripts.eval_brochure_search build  --n-papers 150 --n-books 50
  docker exec -w /app nl-lib-fastapi python -m scripts.eval_brochure_search run
  docker exec -w /app nl-lib-fastapi python -m scripts.eval_brochure_search judge  --judge vlm
  docker exec -w /app nl-lib-fastapi python -m scripts.eval_brochure_search report
산출물은 /app/data/brochure_eval/ — 상세는 research/brochure-search-eval/README.md.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import math
import os
import random
import re
import statistics
import time
import unicodedata
from array import array
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import numpy as np

K = 10
API_TOP_K = 20    # 논문 검색 화면(pages/papers/index.vue)이 보내는 top_k
API_ARM = "prod_api"    # 배포된 POST /api/papers/search 를 그대로 부르는 방식(파이프라인 바깥 단계 포함)
ARMS = ("bm25_meta", "skovix_hybrid", "skovix_rerank", "skovix_norewrite", "skovix_rewrite", "skovix_full", API_ARM)
BASELINE = "bm25_meta"
# 단계별 차이의 '직전 단계'. 사다리가 한 줄이 아니다 — 재작성 끔(norewrite)과 재작성은 둘 다 리랭커에서 갈라진다.
_STEP_PREV = {
    "skovix_hybrid": "bm25_meta", "skovix_rerank": "skovix_hybrid", "skovix_norewrite": "skovix_rerank",
    "skovix_rewrite": "skovix_rerank", "skovix_full": "skovix_rewrite",
    API_ARM: "skovix_norewrite",    # 파이프라인 구성(재작성 끔) 위에 API 의 제목 일치율 재정렬·top_k=20 이 얹힌 것
}


def step_prev(arm: str, present) -> str | None:
    """arm 의 직전 단계. 그 단계가 실행되지 않았다면 사다리를 거슬러 올라가 가장 가까운 실행된 단계."""
    prev = _STEP_PREV.get(arm)
    while prev is not None and prev not in present:
        prev = _STEP_PREV.get(prev)
    return prev
# SKOVIX 방식별 pipeline.search 플래그: (질의 재작성, 리랭커, 메타데이터 필터)
_ARM_FLAGS = {
    "skovix_hybrid": (False, False, False),
    "skovix_rerank": (False, True, False),
    "skovix_norewrite": (False, True, True),    # 운영 기본에서 질의 재작성만 끈 구성(리랭커 + 메타필터)
    "skovix_rewrite": (True, True, False),
    "skovix_full": (True, True, True),
}
_KEEP_LOG = re.compile(r"재작성|필터|expression|실패")
OTR_THRESHOLD = 0.5
ARM_LABEL = {
    "bm25_meta": "키워드 통합검색(BM25)",
    "skovix_hybrid": "SKOVIX 하이브리드",
    "skovix_rerank": "SKOVIX + 리랭커",
    "skovix_norewrite": "SKOVIX 재작성 끔(리랭커+메타필터)",
    API_ARM: "스코빅스 논문 검색 API(배포본, top_k=20)",
    "skovix_rewrite": "SKOVIX + 질의 재작성",
    "skovix_full": "SKOVIX 재작성 켬(재작성+메타필터+리랭커, 이전 운영 기본)",
}

_PAPER_SQL = "(COALESCE(doc_type, '') = 'paper' OR cnts_id LIKE 'KCI_FI%')"
_SCOPE_SQL = {"paper": _PAPER_SQL, "book": f"NOT {_PAPER_SQL}", "all": "TRUE"}
# BM25 색인과 질문 합성은 같은 원천(초록·소개)만 쓴다 — 질문이 기준선 색인에 없는 내용에서
# 나오면 기준선이 부당하게 불리해진다. summary 는 SKOVIX 가 만든 것이라 일부러 뺀다.
_BODY_SQL = "COALESCE(NULLIF(btrim(abstract), ''), NULLIF(btrim(introduction), ''))"
_BODY_JUDGE_SQL = (
    "COALESCE(NULLIF(btrim(abstract), ''), NULLIF(btrim(introduction), ''), "
    "NULLIF(btrim(summary), ''))"
)


# ══════════════════════════════════════════════════════════════
# 텍스트 · BM25
# ══════════════════════════════════════════════════════════════
_NON_WORD = re.compile(r"[^0-9a-z가-힣\s]")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"\s+", " ", _NON_WORD.sub(" ", s)).strip()


def tokenize(s: str) -> list[str]:
    """어절 내부 음절 bigram(1음절 어절은 그대로). 형태소 분석기 없이도 조사 붙은 어절이 매칭된다."""
    out: list[str] = []
    for w in _norm(s).split():
        if len(w) == 1:
            out.append(w)
        else:
            out.extend(w[i:i + 2] for i in range(len(w) - 1))
    return out


def lex_coverage(query: str, doc_text: str) -> float:
    """질의 bigram 중 문서 색인 텍스트에 이미 들어 있는 비율 — 높을수록 어휘 일치로 풀리는 질의."""
    q = set(tokenize(query))
    if not q:
        return 0.0
    return len(q & set(tokenize(doc_text))) / len(q)


def shares_substring(a: str, b: str, n: int) -> bool:
    """공백·기호를 뺀 a 가 b 와 n자 이상 연속으로 겹치는가(베끼기 검사)."""
    a = _norm(a).replace(" ", "")
    b = _norm(b).replace(" ", "")
    return any(a[i:i + n] in b for i in range(len(a) - n + 1))


class BM25Index:
    """numpy 역색인 BM25(k1=1.2, b=0.75). 의존성을 늘리지 않으려고 직접 구현했다."""

    def __init__(self, ids: list[str], texts: list[str], k1: float = 1.2, b: float = 0.75):
        self.ids = list(ids)
        n = len(self.ids)
        vocab: dict[str, int] = {}
        t_arr, d_arr, f_arr = array("i"), array("i"), array("i")
        dl = np.zeros(n, dtype=np.float32)
        for d, text in enumerate(texts):
            toks = tokenize(text)
            dl[d] = len(toks)
            counts = Counter(toks)
            t_arr.extend(vocab.setdefault(t, len(vocab)) for t in counts)
            d_arr.extend([d] * len(counts))
            f_arr.extend(counts.values())
        self.vocab = vocab
        t = np.array(t_arr, dtype=np.int32)
        d = np.array(d_arr, dtype=np.int32)
        f = np.array(f_arr, dtype=np.float32)
        order = np.argsort(t, kind="stable")
        t, d, f = t[order], d[order], f[order]
        df = np.bincount(t, minlength=len(vocab))
        self.indptr = np.concatenate(([0], np.cumsum(df)))
        idf = np.log(1.0 + (n - df + 0.5) / (df + 0.5))
        avgdl = float(dl.mean()) or 1.0
        denom = f + k1 * (1.0 - b + b * dl[d] / avgdl)
        self.w = (idf[t] * f * (k1 + 1.0) / denom).astype(np.float32)
        self.docs = d

    def search(self, query: str, k: int = K) -> list[tuple[str, float]]:
        scores = np.zeros(len(self.ids), dtype=np.float32)
        seen: set[int] = set()
        for tok in tokenize(query):
            tid = self.vocab.get(tok)
            if tid is None or tid in seen:
                continue
            seen.add(tid)
            s, e = self.indptr[tid], self.indptr[tid + 1]
            scores[self.docs[s:e]] += self.w[s:e]
        if not seen:
            return []
        k = min(k, len(scores))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top], kind="stable")]
        return [(self.ids[i], float(scores[i])) for i in top if scores[i] > 0]


# ══════════════════════════════════════════════════════════════
# 지표 · 통계
# ══════════════════════════════════════════════════════════════
def rank_of(ids: list[str], target: str) -> int | None:
    try:
        return ids.index(target) + 1
    except ValueError:
        return None


def recall_at(rank: int | None, k: int) -> float:
    return 1.0 if rank is not None and rank <= k else 0.0


def reciprocal_rank(rank: int | None, k: int = K) -> float:
    return 1.0 / rank if rank is not None and rank <= k else 0.0


def ndcg_at(rank: int | None, k: int = K) -> float:
    """정답이 1건이면 IDCG=1 이라 nDCG = 1/log2(rank+1)."""
    return 1.0 / math.log2(rank + 1) if rank is not None and rank <= k else 0.0


def bootstrap_ci(values, *, b: int = 2000, seed: int = 0, alpha: float = 0.05) -> list[float] | None:
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return None
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, v.size, size=(b, v.size))].mean(axis=1)
    return [float(np.percentile(means, 100 * alpha / 2)), float(np.percentile(means, 100 * (1 - alpha / 2)))]


def mean_ci(values, seed: int = 0) -> dict:
    v = [x for x in values if x is not None]
    if not v:
        return {"mean": None, "ci": None, "n": 0}
    return {"mean": float(np.mean(v)), "ci": bootstrap_ci(v, seed=seed), "n": len(v)}


@contextmanager
def capture_logs(name: str = "services.search"):
    """검색 중 파이프라인이 남기는 재작성·메타데이터 필터 로그를 그대로 모은다.

    질의 재작성이 무엇으로 바꿨고 필터가 실제로 걸렸는지는 응답에 없고 로그에만 남는다.
    재호출로 다시 뽑으면 실제 적용된 값과 다를 수 있어 호출 중의 로그를 잡는다.
    """
    records: list[str] = []

    class _H(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    h, lg = _H(level=logging.INFO), logging.getLogger(name)
    prev = lg.level
    lg.addHandler(h)
    lg.setLevel(logging.INFO)
    try:
        yield records
    finally:
        lg.removeHandler(h)
        lg.setLevel(prev)


def label_from_models(data: list[dict], name: str) -> str:
    """vLLM /v1/models 의 id(서빙 별칭)와 root(실제 모델)가 다르면 둘 다 적는다.

    설정의 모델명은 별칭일 수 있다 — 브로셔에는 실제로 판정한 모델을 적어야 한다.
    """
    m = next((x for x in data if x.get("id") == name), None)
    root = (m or {}).get("root")
    return f"{name} (서빙 모델: {root})" if root and root != name else name


def sign_test_p(b: int, c: int) -> float:
    """쌍대 이진 결과의 양측 정확 부호검정. b=한쪽만 성공, c=다른 쪽만 성공."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def cohen_kappa(a: list[int], b: list[int]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return None if pe == 1 else (po - pe) / (1 - pe)


# ══════════════════════════════════════════════════════════════
# 질문 합성 · 판정 프롬프트
# ══════════════════════════════════════════════════════════════
_QGEN_SYS = (
    "당신은 도서관 이용자 질의 생성기입니다. 주어진 문헌 내용을 찾으려는 이용자가 검색창에 "
    "자연스럽게 입력할 한국어 질문 또는 요청 1개를 만드세요.\n"
    "규칙: ① 한 문장, 15~80자 ② 제목·저자·기관명을 쓰지 않고, '요즘·최근·최신·올해' 같은 "
    "시간 표현과 연도도 쓰지 않는다 ③ 문헌에 나온 문장을 "
    "그대로 베끼지 말고 일상적인 표현으로 바꿔 말한다(전문용어는 풀어서 써도 된다) "
    "④ 질문 문장만 출력한다."
)

# 메타데이터 필터 프롬프트가 날짜 조건·정렬로 읽는 표현("최신·최근·올해·YYYY년"). 이런 질문은 제품이 의도대로
# 날짜 정렬·필터를 걸기 때문에 '정답 1건' 평가와 맞지 않는다 — 스모크에서 "요즘 …" 이 sort_by=recent 를 켜
# 정답을 밀어냈다. "17세기" 같은 시대 표현은 필터를 만들지 않았으므로 막지 않는다.
_TIME_EXPR = re.compile(r"요즘|최근|최신|올해|작년|지난해|\d{3,4}\s*년|\d{2,4}\s*[~∼\-]\s*\d{2,4}\s*년대|\d{2}\s*년대")

_JUDGE_EXAMPLES = (
    '[검색어] 노인 일자리 사업이 소득에 미치는 효과\n'
    '[문서] 제목: 노인일자리 참여가 고령자 가구 소득과 빈곤율에 미치는 영향 분석\n'
    '→ {"reason":"노인 일자리의 소득 효과를 직접 분석한 문서","on_topic":1,"score":0.95}\n\n'
    '[검색어] 청소년 스마트폰 과의존 예방\n'
    '[문서] 제목: 스마트폰 앱 사용자 인터페이스 설계 가이드라인\n'
    '→ {"reason":"스마트폰이 나오지만 핵심은 UI 설계이고 청소년·과의존과 무관(단어만 일치)","on_topic":0,"score":0.1}\n\n'
    '[검색어] 지방 대학 위기와 입학 정원 감소\n'
    '[문서] 제목: 학령인구 감소에 따른 지방대학 신입생 충원율 변화\n'
    '→ {"reason":"학령인구 감소와 지방대 충원 문제를 직접 다룸","on_topic":1,"score":0.9}\n\n'
    '[검색어] 조선 후기 농촌 사회의 변화\n'
    '[문서] 제목: 조선 후기 한양 시전 상인의 상업 활동 연구\n'
    '→ {"reason":"같은 시대지만 핵심은 도시 상업이고 농촌이 아님","on_topic":0,"score":0.3}'
)

_JUDGE_SYS = (
    "당신은 도서관 검색 결과의 주제 적합성(on-topic) 평가자입니다. [검색어]와 [문서]를 보고 "
    "이 문서가 검색어가 찾는 주제를 '주로 다루는지(primarily about)' 판정하세요.\n"
    "규칙:\n"
    "1. 검색어의 단어가 문서에 나온다는 사실만으로 관련이라고 판단하지 마세요. 키워드 일치는 주제 일치가 아닙니다.\n"
    "2. 검색어가 알고 싶어 하는 것(의도)과 문서의 핵심 주제가 의미상 맞는지를 보세요.\n"
    "3. 주제를 부수적으로만 언급하거나 일부 단어만 겹치면 on_topic=0 입니다.\n"
    "4. 문서 정보가 너무 빈약해 판단할 수 없으면 on_topic=0, score 는 0.5 미만으로 주세요.\n"
    '출력은 JSON 한 줄만: {"reason":"한 문장 근거","on_topic":0 또는 1,"score":0~1 사이 숫자}\n\n'
    "예시:\n" + _JUDGE_EXAMPLES
)

_JSON_RE = re.compile(r"\{[^{}]*\}", re.S)


def clean_question(out: str) -> str:
    lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    q = re.sub(r"^(질문|요청|검색어)\s*[:：]\s*", "", lines[0])
    return re.sub(r"\s+", " ", q).strip().strip('"“”\'').strip()


def reject_reason(q: str, row: dict) -> str | None:
    if not q:
        return "empty"
    if not 10 <= len(q) <= 120:
        return "length"
    if _TIME_EXPR.search(q):
        return "time_expr"
    if shares_substring(q, row.get("title") or "", 6):
        return "title_copy"
    if shares_substring(q, row.get("body") or "", 12):
        return "body_copy"
    return None


def parse_judgment(text: str) -> dict | None:
    for m in reversed(_JSON_RE.findall(text or "")):
        try:
            obj = json.loads(m)
            raw, score = obj["on_topic"], float(obj["score"])
        except (ValueError, KeyError, TypeError):
            continue
        # int() 로 자르면 0.8 이 0 으로 읽혀 파싱 실패가 '주제 아님'이 된다 — 0·1(과 "0"·"1")만 받는다
        if isinstance(raw, bool):
            on_topic = int(raw)
        elif isinstance(raw, int):
            on_topic = raw
        elif isinstance(raw, str) and raw.strip() in ("0", "1"):
            on_topic = int(raw)
        else:
            continue
        if on_topic in (0, 1) and 0.0 <= score <= 1.0:
            return {"on_topic": on_topic, "score": score, "reason": str(obj.get("reason", ""))[:200]}
    return None


def is_on_topic(j: dict) -> bool:
    """논문의 최종 규칙: 이진 판정이 1 이고 관련성 점수가 임계값 이상."""
    return j["on_topic"] == 1 and j["score"] >= OTR_THRESHOLD


def judge_user_prompt(query: str, doc: dict) -> str:
    body = re.sub(r"\s+", " ", doc.get("body") or "").strip()[:700]
    return (
        f"[검색어] {query}\n[문서]\n제목: {doc.get('title') or ''}\n"
        f"주제어: {doc.get('keyword') or ''}\n내용: {body}"
    )


# ══════════════════════════════════════════════════════════════
# 서버 백엔드 — DB · 검색 · LLM 접근은 여기에만 둔다 (테스트는 가짜 백엔드로 대체)
# ══════════════════════════════════════════════════════════════
class ServerBackend:
    def __init__(self):
        from core.config import get_settings
        from db.postgres import AsyncSessionLocal

        self.cfg = get_settings()
        self._Session = AsyncSessionLocal

    async def model_label(self, role: str) -> str:
        import httpx

        base, name = ((self.cfg.VLM_BASE_URL, self.cfg.VLM_MODEL) if role == "vlm"
                      else (self.cfg.LLM_BASE_URL, self.cfg.LLM_MODEL))
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                data = (await c.get(f"{base}/models")).json().get("data", [])
            return label_from_models(data, name)
        except Exception:
            return name

    async def close(self) -> None:
        from db.postgres import engine

        await engine.dispose()    # 커넥션 풀을 닫아 끝난 뒤 연결이 남지 않게

    async def _rows(self, sql: str, params: dict | None = None, expanding: tuple = ()) -> list[dict]:
        from sqlalchemy import bindparam, text

        stmt = text(sql)
        if expanding:
            stmt = stmt.bindparams(*[bindparam(n, expanding=True) for n in expanding])
        # 세션을 오래 열어 두면 운영 DB 에 'idle in transaction' 이 남으므로 호출마다 연다.
        async with self._Session() as s:
            res = await s.execute(stmt, params or {})
            return [dict(r) for r in res.mappings().all()]

    async def count_docs(self, scope: str) -> int:
        rows = await self._rows(
            f"SELECT count(*) AS n FROM library_catalog WHERE is_embedded = true AND {_SCOPE_SQL[scope]}"
        )
        return int(rows[0]["n"])

    async def sample_docs(self, scope: str, n: int, seed: int) -> list[dict]:
        # md5 정렬 = 시드 고정 무작위(setseed 와 달리 세션·트랜잭션에 묶이지 않는다)
        return await self._rows(
            f"""SELECT cnts_id, title, keyword, {_BODY_SQL} AS body
                FROM library_catalog
                WHERE is_embedded = true AND {_SCOPE_SQL[scope]}
                  AND title IS NOT NULL AND length(btrim(title)) > 3
                  AND length(COALESCE({_BODY_SQL}, '')) >= 200
                ORDER BY md5(cnts_id || :seed) LIMIT :n""",
            {"seed": str(seed), "n": n},
        )

    async def catalog(self, scope: str) -> list[dict]:
        return await self._rows(
            f"""SELECT cnts_id, title, keyword, {_BODY_SQL} AS body
                FROM library_catalog WHERE is_embedded = true AND {_SCOPE_SQL[scope]}"""
        )

    async def doc_infos(self, ids: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(ids), 500):
            rows = await self._rows(
                f"""SELECT cnts_id, title, keyword, {_BODY_JUDGE_SQL} AS body
                    FROM library_catalog WHERE cnts_id IN :ids""",
                {"ids": ids[i:i + 500]}, expanding=("ids",),
            )
            out.update({r["cnts_id"]: r for r in rows})
        return out

    async def search(self, arm: str, query: str, scope: str) -> dict:
        if arm == API_ARM:    # 배포된 엔드포인트는 HTTP 로 부른다 — pipeline 을 import 할 필요가 없다
            return await self._search_api(query, scope)
        if arm not in _ARM_FLAGS:
            raise ValueError(f"unknown arm: {arm}")
        from services.search.pipeline import search as pipeline_search

        rewrite, rerank, meta_filter = _ARM_FLAGS[arm]
        kw: dict = {"mode": "book", "top_k": K, "doc_scope": scope, "use_rewrite": rewrite,
                    "use_rerank": rerank, "use_metadata_filter": meta_filter}
        t0 = time.perf_counter()
        with capture_logs() as logs:
            if rewrite or meta_filter:
                async with self._Session() as db:   # 메타필터는 db 가 있어야 켜지고, 재작성은 db 로 'X 같은 책'의 참조 도서를 조회한다 — API 와 같은 호출 모양
                    resp = await pipeline_search(query, db=db, **kw)
            else:
                resp = await pipeline_search(query, db=None, **kw)
        return {
            "ids": [b.book_id for b in resp.books][:K],
            "ms": round((time.perf_counter() - t0) * 1000, 1),
            "rewritten": getattr(resp, "rewritten_query", None),
            "log": [m for m in logs if _KEEP_LOG.search(m)],
        }

    async def _search_api(self, query: str, scope: str) -> dict:
        """배포된 논문 검색(POST /api/papers/search)을 그대로 부른다 — 제목 일치율 재정렬처럼 pipeline.search 바깥의
        단계까지 포함한, 사용자가 실제로 받는 결과. 논문 검색 화면이 보내는 값(mode=book, top_k=20, use_rerank=true)을 따르되
        use_rewrite 는 일부러 true 로 보낸다 — 서버가 요청값을 무시하고 재작성을 끄는지 확인하는 카나리다(재작성된 질의가
        돌아오면 재작성을 끈 이미지가 아직 올라가지 않은 것). 순위는 서버가 돌려준 순서(재정렬 뒤)를 그대로 쓴다."""
        import httpx

        if scope != "paper":
            raise ValueError("prod_api 는 논문 범위만 지원한다")
        base = os.environ.get("EVAL_API_BASE", "http://localhost:8000")
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=120.0) as c:
            r = await c.post(f"{base}/api/papers/search", json={
                "query": query, "mode": "book", "top_k": API_TOP_K, "use_rewrite": True, "use_rerank": True})
            r.raise_for_status()
            data = r.json()
        ids = [b["book_id"] for b in data.get("books", [])]
        return {"ids": ids[:K], "ids_all": ids, "ms": round((time.perf_counter() - t0) * 1000, 1),
                "rewritten": data.get("rewritten_query") or None, "log": []}

    async def chat(self, role: str, messages: list[dict], *, max_tokens: int, temperature: float) -> str:
        # eval_answer_quality 의 _chat 은 Qwen3 의 </think> 처리 함정을 이미 풀어 둔 것을 재사용한다.
        from scripts.eval_answer_quality import _chat

        if role == "vlm":
            base, model, think = self.cfg.VLM_BASE_URL, self.cfg.VLM_MODEL, False
        else:
            base, model, think = self.cfg.LLM_BASE_URL, self.cfg.LLM_MODEL, self.cfg.LLM_THINK
        out, _ = await _chat(base, model, messages, max_tokens=max_tokens,
                             temperature=temperature, thinking=think)
        return out


# ══════════════════════════════════════════════════════════════
# 파일 입출력
# ══════════════════════════════════════════════════════════════
def _dump(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _load(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


# ══════════════════════════════════════════════════════════════
# 1단계 build — 질의 세트
# ══════════════════════════════════════════════════════════════
async def _gen_one(be, row: dict, sem: asyncio.Semaphore) -> tuple[str | None, str | None]:
    async with sem:
        note, why = "", "empty"
        for attempt in range(2):
            try:
                out = await be.chat(
                    "gen",
                    [{"role": "system", "content": _QGEN_SYS},
                     {"role": "user", "content": f"[문헌 내용]\n{(row['body'] or '')[:1500]}\n\n"
                                                 f"이 문헌을 찾으려는 이용자의 질문 1개:{note}"}],
                    max_tokens=120, temperature=0.4 + 0.3 * attempt,
                )
            except Exception:
                return None, "llm_error"
            q = clean_question(out)
            why = reject_reason(q, row)
            if why is None:
                return q, None
            note = f"\n(앞선 시도는 '{why}' 문제로 거절됐다. 제목·원문 문장을 그대로 쓰지 말고 바꿔 말하라.)"
        return None, why


async def stage_build(args, be, wd: Path) -> dict:
    if (wd / "runs.json").exists() and not args.force:
        raise SystemExit(
            "이 작업 폴더에 이미 runs.json 이 있다 — build 를 다시 돌리면 같은 qid 에 다른 질문이 들어가 옛 검색 결과·판정과 섞인다. "
            "새 --workdir 를 쓰세요. 정말 덮어쓰려면 runs.json·judgments_*.json 을 먼저 치우고 --force 를 주세요.")
    sem = asyncio.Semaphore(args.concurrency)
    queries: list[dict] = []
    dropped: Counter = Counter()
    corpus: dict[str, int] = {}

    for scope, n in (("paper", args.n_papers), ("book", args.n_books)):
        if n <= 0:
            continue
        corpus[scope] = await be.count_docs(scope)
        rows = await be.sample_docs(scope, int(n * 1.5) + 2, args.seed)
        print(f"[{scope}] 표본 후보 {len(rows)}건 (색인 문서 {corpus[scope]:,}건) → 질문 합성 중…", flush=True)
        results = await asyncio.gather(*[_gen_one(be, r, sem) for r in rows])
        kept = 0
        for r, (q, why) in zip(rows, results):
            if q is None:
                dropped[why] += 1
                continue
            if kept >= n:
                break
            queries.append({
                "qid": f"nl-{scope[0]}-{kept:04d}", "qtype": "nl", "scope": scope, "query": q,
                "expected_id": r["cnts_id"], "title": r["title"],
                "lex_coverage": round(lex_coverage(q, f"{r['title']} {r.get('keyword') or ''} {r['body']}"), 4),
            })
            kept += 1
        print(f"[{scope}] 질문 {kept}건 확정 (탈락 {dict(dropped)})", flush=True)

    if args.golden and Path(args.golden).exists():
        gold = json.loads(Path(args.golden).read_text(encoding="utf-8"))
        for i, g in enumerate(gold):
            queries.append({
                "qid": f"g-{i:04d}", "qtype": g.get("query_type", "golden"),
                "scope": g.get("doc_scope", "all"), "query": g["query"],
                "expected_id": g["expected_book_id"], "title": g.get("title", ""),
            })
        print(f"golden 질의 {len(gold)}건 추가", flush=True)

    meta = {
        "created": datetime.now().isoformat(timespec="seconds"), "seed": args.seed,
        "corpus_docs": corpus, "question_model": await be.model_label("gen"),
        "dropped": dict(dropped), "n_queries": len(queries),
    }
    _dump(wd / "queries.json", {"meta": meta, "queries": queries})
    return meta


# ══════════════════════════════════════════════════════════════
# 2단계 run — 방식별 검색 결과
# ══════════════════════════════════════════════════════════════
async def _build_bm25(be, scopes: set[str]) -> dict[str, BM25Index]:
    out: dict[str, BM25Index] = {}
    for scope in scopes:
        t0 = time.perf_counter()
        rows = await be.catalog(scope)
        out[scope] = BM25Index(
            [r["cnts_id"] for r in rows],
            [f"{r['title'] or ''} {r.get('keyword') or ''} {r['body'] or ''}" for r in rows],
        )
        print(f"[bm25:{scope}] {len(rows):,}건 색인 ({time.perf_counter() - t0:.1f}s)", flush=True)
    return out


async def stage_run(args, be, wd: Path) -> None:
    data = _load(wd / "queries.json")
    if not data:
        raise SystemExit("queries.json 이 없다 — 먼저 build 를 실행하세요.")
    queries = data["queries"]
    arms = [a for a in args.arms.split(",") if a]
    bad = [a for a in arms if a not in ARMS]
    if bad:
        raise SystemExit(f"알 수 없는 arm: {bad} (가능: {ARMS})")

    runs: dict = _load(wd / "runs.json", {})
    bm25 = await _build_bm25(be, {q["scope"] for q in queries}) if BASELINE in arms else {}

    for i, q in enumerate(queries, 1):
        for arm in arms:
            prev = runs.get(q["qid"], {}).get(arm)
            if prev is not None and not prev.get("error"):    # 오류로 끝난 항목은 재실행 때 다시 돈다
                continue
            if arm == API_ARM and q["scope"] != "paper":    # 배포된 엔드포인트는 논문 검색뿐
                continue
            if arm == BASELINE:
                t0 = time.perf_counter()
                hits = bm25[q["scope"]].search(q["query"], K)
                res = {"ids": [d for d, _ in hits], "ms": round((time.perf_counter() - t0) * 1000, 2)}
            else:
                try:
                    res = await be.search(arm, q["query"], q["scope"])
                except Exception as e:
                    res = {"ids": [], "ms": None, "error": str(e)[:200]}
            runs.setdefault(q["qid"], {})[arm] = res
        if i % 10 == 0 or i == len(queries):
            _dump(wd / "runs.json", runs)
            print(f"[run] {i}/{len(queries)}", flush=True)
    _dump(wd / "runs.json", runs)
    if API_ARM in arms:    # 배포 확인 — 재작성 요청을 보냈는데도 재작성된 질의가 돌아오면 재작성을 끈 이미지가 아직 안 올라간 것
        applied = sum(1 for r in runs.values() if (r.get(API_ARM) or {}).get("rewritten"))
        done = sum(1 for r in runs.values() if (r.get(API_ARM) or {}).get("ids"))
        if not done:
            print(f"경고: {API_ARM} 호출이 하나도 성공하지 못했다 — EVAL_API_BASE·배포 상태를 확인하세요(배포 확인을 할 수 없다).")
        elif applied:
            print(f"경고: 배포본이 재작성을 적용했다({applied}/{done}건) — 재작성을 끈 이미지가 아직 올라가지 않았다. "
                  f"이 상태의 {API_ARM} 수치는 '재작성 켬'이므로 배포 뒤 다시 측정하세요.")
        else:
            print(f"확인: 배포본이 재작성을 적용하지 않았다(재작성 요청을 보내도 rewritten_query 없음, {done}건).")
    errs = sum(1 for r in runs.values() for v in r.values() if v.get("error"))
    if errs:
        print(f"경고: 검색 오류 {errs}건 — runs.json 의 error 필드 확인(정답 미발견으로 집계되므로 수치가 낮아진다)")


# ══════════════════════════════════════════════════════════════
# 3단계 judge — OTR 판정
# ══════════════════════════════════════════════════════════════
def pair_key(qid: str, doc_id: str) -> str:
    return f"{qid}|{doc_id}"


async def stage_judge(args, be, wd: Path) -> None:
    data = _load(wd / "queries.json")
    runs = _load(wd / "runs.json")
    if not data or not runs:
        raise SystemExit("queries.json / runs.json 이 없다 — build, run 을 먼저 실행하세요.")
    role = "vlm" if args.judge == "vlm" else "gen"
    qtypes = set(args.qtypes.split(","))
    qmap = {q["qid"]: q for q in data["queries"] if q["qtype"] in qtypes}

    judgments: dict = _load(wd / f"judgments_{args.judge}.json", {})
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for qid, arms in runs.items():
        if qid not in qmap:
            continue
        for res in arms.values():
            for d in res.get("ids", [])[:K]:
                key = pair_key(qid, d)
                if key not in seen and (key not in judgments or judgments[key].get("failed")):    # 실패한 쌍은 다시 판정
                    seen.add(key)
                    pairs.append((qid, d))
    label = args.model_label or await be.model_label(role)
    models = _load(wd / "judge_models.json", {})
    old_label = models.get(args.judge, {}).get("label")
    if old_label and old_label != label and any(not v.get("failed") for v in judgments.values()):
        print(f"경고: 이어 하는 판정의 서빙 모델 표기가 바뀌었다({old_label} → {label}) — 앞뒤 판정이 섞인다. "
              "필요하면 판정 파일을 지우고 처음부터 다시 하세요.", flush=True)
    models[args.judge] = {"label": label}
    _dump(wd / "judge_models.json", models)
    ok_n = sum(1 for v in judgments.values() if not v.get("failed"))
    retry_n = sum(1 for qid, d in pairs if pair_key(qid, d) in judgments)
    print(f"판정 대상 쌍 {len(pairs)}건 (이미 판정 {ok_n}건 · 실패 재시도 {retry_n}건) · 판정자 {label}", flush=True)
    if not pairs:
        return

    infos = await be.doc_infos(sorted({d for _, d in pairs}))
    sem = asyncio.Semaphore(args.concurrency)
    done = 0

    async def one(qid: str, d: str) -> None:
        nonlocal done
        async with sem:
            doc = infos.get(d, {})
            user = judge_user_prompt(qmap[qid]["query"], doc)
            j, tail, kind = None, "", "parse"
            for attempt in range(2):
                try:
                    out = await be.chat(
                        role,
                        [{"role": "system", "content": _JUDGE_SYS},
                         {"role": "user", "content": user + ("" if attempt == 0 else "\n\nJSON 한 줄만 출력하세요.")}],
                        max_tokens=200, temperature=0.0,
                    )
                except Exception as e:
                    tail, kind = f"<error: {e}>"[:200], "error"    # 연결·타임아웃 등 — 파싱 실패와 구분해 남긴다
                    continue
                j = parse_judgment(out)
                if j:
                    break
                tail, kind = (out or "")[-200:], "parse"
            # 파싱 실패를 조용히 버리면 선택 편향이 되므로 failed 로 남겨 결측률을 보고한다.
            judgments[pair_key(qid, d)] = j or {"failed": True, "kind": kind, "tail": tail}
            done += 1
            if done % 50 == 0:
                _dump(wd / f"judgments_{args.judge}.json", judgments)
                print(f"[judge] {done}/{len(pairs)}", flush=True)

    await asyncio.gather(*[one(q, d) for q, d in pairs])
    _dump(wd / f"judgments_{args.judge}.json", judgments)
    failed = sum(1 for v in judgments.values() if v.get("failed"))
    print(f"판정 완료 · 실패 {failed}건({failed / max(1, len(judgments)):.1%})")


# ══════════════════════════════════════════════════════════════
# 4단계 report
# ══════════════════════════════════════════════════════════════
def _query_metrics(q: dict, res: dict) -> dict:
    rank = rank_of(res.get("ids", []), q["expected_id"])
    return {"r1": recall_at(rank, 1), "r5": recall_at(rank, 5), "r10": recall_at(rank, 10),
            "mrr": reciprocal_rank(rank), "ndcg": ndcg_at(rank)}


def _query_otr(qid: str, ids: list[str], judgments: dict) -> tuple[float | None, int, int]:
    labels, missing = [], 0
    for d in ids[:K]:
        j = judgments.get(pair_key(qid, d))
        if j is None or j.get("failed"):
            missing += 1
        else:
            labels.append(1 if is_on_topic(j) else 0)
    return (sum(labels) / len(labels) if labels else None), len(labels), missing


def _paired_delta(per: dict, arm: str, base: str, seed: int) -> dict | None:
    """같은 질의에서 arm 과 base 의 지표 차이(쌍대 부트스트랩) + Recall@10 부호검정."""
    common = [qid for qid in per[arm] if qid in per[base]]
    if not common:
        return None
    d: dict = {"n": len(common)}
    for k in ("r10", "mrr", "ndcg"):
        diffs = [per[arm][qid][k] - per[base][qid][k] for qid in common]
        d[k] = {"mean": float(np.mean(diffs)), "ci": bootstrap_ci(diffs, seed=seed)}
    b = sum(1 for qid in common if per[base][qid]["r10"] and not per[arm][qid]["r10"])
    c = sum(1 for qid in common if per[arm][qid]["r10"] and not per[base][qid]["r10"])
    d["r10_only_baseline"], d["r10_only_arm"], d["r10_sign_p"] = b, c, sign_test_p(b, c)
    od = [per[arm][qid]["otr"][0] - per[base][qid]["otr"][0] for qid in common
          if per[arm][qid]["otr"][0] is not None and per[base][qid]["otr"][0] is not None]
    if od:
        d["otr"] = {"mean": float(np.mean(od)), "ci": bootstrap_ci(od, seed=seed), "n": len(od)}
    return d


def summarize_group(qs: list[dict], runs: dict, judgments: dict, seed: int = 0) -> dict:
    arms = [a for a in ARMS if any(a in runs.get(q["qid"], {}) for q in qs)]
    per: dict[str, dict[str, dict]] = {a: {} for a in arms}
    for a in arms:
        for q in qs:
            res = runs.get(q["qid"], {}).get(a)
            if res is not None:
                per[a][q["qid"]] = {**_query_metrics(q, res),
                                    "otr": _query_otr(q["qid"], res.get("ids", []), judgments)}
    out_arms: dict = {}
    for a in arms:
        rows = list(per[a].values())
        m = {k: mean_ci([r[k] for r in rows], seed) for k in ("r1", "r5", "r10", "mrr", "ndcg")}
        otrs = [r["otr"][0] for r in rows]
        m["otr"] = mean_ci(otrs, seed)
        m["otr"]["judged_pairs"] = sum(r["otr"][1] for r in rows)
        m["otr"]["missing_pairs"] = sum(r["otr"][2] for r in rows)
        ms = sorted(runs[q["qid"]][a]["ms"] for q in qs
                    if a in runs.get(q["qid"], {}) and runs[q["qid"]][a].get("ms") is not None)
        m["latency_p50_ms"] = ms[len(ms) // 2] if ms else None
        m["errors"] = sum(1 for q in qs if runs.get(q["qid"], {}).get(a, {}).get("error"))
        out_arms[a] = m

    deltas: dict = {}
    steps: dict = {}
    ladder = [a for a in ARMS if a in per]
    for a in ladder:
        if a != BASELINE and BASELINE in per:
            d = _paired_delta(per, a, BASELINE, seed)
            if d:
                deltas[a] = d
        prev = step_prev(a, per)
        if prev:    # 직전 단계 대비 — 이 단계가 실제로 보탬이 되는지, 해치는지
            d = _paired_delta(per, a, prev, seed)
            if d:
                steps[a] = {**d, "prev": prev}
    return {"n": len(qs), "arms": out_arms, "deltas": deltas, "steps": steps}


def _filter_applied(runs: dict, qid: str) -> bool:
    """메타필터가 켜진 구성(skovix_full·skovix_norewrite)이 이 질의에 날짜 필터·정렬을 실제로 건 적이 있는가(로그 기준)."""
    r = runs.get(qid, {})
    return any("메타데이터 필터 감지" in m for arm in ("skovix_full", "skovix_norewrite") for m in r.get(arm, {}).get("log", []))


def build_report(queries: list[dict], runs: dict, judgments: dict, seed: int = 0) -> dict:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for q in queries:
        groups[(q["scope"], q["qtype"])].append(q)
    out: dict = {}
    for (scope, qtype), qs in sorted(groups.items()):
        out[f"{scope}|{qtype}"] = summarize_group(qs, runs, judgments, seed)
        if qtype == "nl":
            # 생성 단계의 정규식이 못 거른 시간 표현("762년", "1960~70년대")도 있으니 실제로 날짜 필터·정렬이
            # 걸렸는지를 로그로 보고 가른다 — 그런 질의는 '정답 1건' 평가가 맞지 않아 별도 층으로 보고한다.
            filtered = {q["qid"] for q in qs if _filter_applied(runs, q["qid"])}
            kept = [q for q in qs if q["qid"] not in filtered]
            if filtered and kept:
                out[f"{scope}|nl_unfiltered"] = {**summarize_group(kept, runs, judgments, seed),
                                                 "n_excluded_filtered": len(filtered)}
        covs = sorted(q["lex_coverage"] for q in qs if "lex_coverage" in q)
        if qtype == "nl" and len(covs) >= 20:
            med = covs[len(covs) // 2]
            low = [q for q in qs if q.get("lex_coverage", 1) <= med]
            out[f"{scope}|nl_low_coverage"] = {**summarize_group(low, runs, judgments, seed),
                                               "coverage_median": med}
    return out


def _pct(m: dict | None, digits: int = 1) -> str:
    if not m or m.get("mean") is None:
        return "—"
    s = f"{m['mean'] * 100:.{digits}f}%"
    if m.get("ci"):
        s += f" [{m['ci'][0] * 100:.{digits}f}–{m['ci'][1] * 100:.{digits}f}]"
    return s


def _dec(m: dict | None) -> str:
    if not m or m.get("mean") is None:
        return "—"
    s = f"{m['mean']:.3f}"
    if m.get("ci"):
        s += f" [{m['ci'][0]:.3f}–{m['ci'][1]:.3f}]"
    return s


_GROUP_TITLE = {
    "nl": "자연어 질문(합성)", "nl_low_coverage": "자연어 질문 중 어휘 겹침이 낮은 절반(의역 위주)",
    "nl_unfiltered": "자연어 질문 중 날짜 필터·정렬이 걸리지 않은 질의",
    "keyword": "주제어 질의(문서 필드 기반)", "metadata": "기관+연도+주제 질의(문서 필드 기반)",
    "abstract": "초록 첫 문장 질의(문서 필드 기반)",
}
_SCOPE_TITLE = {"paper": "학술논문", "book": "도서·보고서", "all": "전체"}


def render_markdown(report: dict, meta: dict, judge_info: dict) -> str:
    lines = ["# 브로셔용 검색 품질 수치", "",
             f"- 측정일 {meta.get('created', '')[:10]} · 색인 문서 {meta.get('corpus_docs', {})}",
             f"- 질문 합성 모델 {meta.get('question_model')} · 시드 {meta.get('seed')}",
             *([f"- 신뢰구간(부트스트랩) 시드 {meta['report_seed']}"] if meta.get("report_seed") is not None else []),
             f"- OTR 판정자 {judge_info.get('judges', '미실시')}", ""]
    for gk, g in report.items():
        scope, qtype = gk.split("|")
        lines += [f"## {_SCOPE_TITLE.get(scope, scope)} · {_GROUP_TITLE.get(qtype, qtype)} (n={g['n']})", ""]
        if g.get("n_excluded_filtered"):
            lines += [f"> 제외 {g['n_excluded_filtered']}건 — 메타데이터 필터가 날짜 필터·정렬을 건 질의. "
                      "시간 조건이 든 질문은 제품이 의도대로 정렬·필터하므로 '정답 1건' 평가가 맞지 않아 별도 층으로 뺐다.", ""]
        lines += ["| 방식 | Recall@1 | Recall@10 | MRR@10 | nDCG@10 | OTR@10 |", "|---|---|---|---|---|---|"]
        for a, m in g["arms"].items():
            lines.append(f"| {ARM_LABEL[a]} | {_pct(m['r1'])} | {_pct(m['r10'])} | {_dec(m['mrr'])} "
                         f"| {_dec(m['ndcg'])} | {_pct(m['otr'])} |")
        errs = {a: m["errors"] for a, m in g["arms"].items() if m.get("errors")}
        if errs:
            lines += ["", "> ⚠️ 검색 오류(정답 미발견으로 집계되어 표의 수치가 낮아진다): "
                      + ", ".join(f"{ARM_LABEL[a]} {n}건" for a, n in errs.items())]
        for a, d in g["deltas"].items():
            r10 = d["r10"]
            ci = f" [{r10['ci'][0] * 100:+.1f}, {r10['ci'][1] * 100:+.1f}]" if r10.get("ci") else ""
            otr = ""
            if d.get("otr"):
                o = d["otr"]
                otr = f" · OTR@10 {o['mean'] * 100:+.1f}%p [{o['ci'][0] * 100:+.1f}, {o['ci'][1] * 100:+.1f}]"
            lines.append(f"\n- **{ARM_LABEL[a]} − {ARM_LABEL[BASELINE]}**: Recall@10 {r10['mean'] * 100:+.1f}%p{ci}"
                         f" (BM25만 성공 {d['r10_only_baseline']} / 해당 방식만 성공 {d['r10_only_arm']}, "
                         f"부호검정 p={d['r10_sign_p']:.3g}){otr}")
        for a, d in g.get("steps", {}).items():
            r10 = d["r10"]
            ci = f" [{r10['ci'][0] * 100:+.1f}, {r10['ci'][1] * 100:+.1f}]" if r10.get("ci") else ""
            otr = ""
            if d.get("otr"):
                o = d["otr"]
                otr = f" · OTR@10 {o['mean'] * 100:+.1f}%p [{o['ci'][0] * 100:+.1f}, {o['ci'][1] * 100:+.1f}]"
            lines.append(f"- 단계별: {ARM_LABEL[d['prev']]} → **{ARM_LABEL[a]}**: Recall@10 {r10['mean'] * 100:+.1f}%p{ci}"
                         f" (이전만 성공 {d['r10_only_baseline']} / 이번만 성공 {d['r10_only_arm']}){otr}")
        lines.append("")
    lines += ["---", "## 표기 시 반드시 지킬 것",
              "- 질의는 문서 내용에서 LLM 이 합성한 것이다. **실사용자 질의가 아니며**, 수치는 '합성 질문 기준'이라고 적는다.",
              "- 정답은 질의의 원문서 1건이다. 같은 주제의 다른 문서는 정답이 아니므로 Recall·MRR·nDCG 는 하한이다.",
              "- '문서 필드 기반' 질의(주제어·기관+연도·초록 첫 문장)는 **자연어 검색 정확도로 표기하지 않는다.**",
              "- BM25 기준선은 제목·주제어·초록(없으면 소개)만 색인한 키워드 통합검색이다. 본문 전체 색인과의 비교가 아니다.",
              f"- OTR 은 LLM 판정이다. 사람 검증: {judge_info.get('human', '미실시(review-sheet 로 확인 필요)')}."
              + (f" 다른 LLM 교차 확인(사람 아님): {judge_info['rater_check']}." if judge_info.get("rater_check") else ""),
              "- **OTR@10 의 절대값을 '정확도'로 읽지 않는다.** 질문에 맞는 문서가 코퍼스에 2건뿐이면 OTR@10 은 아무리 잘해도 20% 가 "
              "상한이다. 방식 간 상대 비교(예: BM25 대비 몇 배)로만 쓴다.",
              *(["- ⚠️ **이 표의 OTR 판정자(llm=gemma)가 질문 합성·메타필터·질의 재작성에도 쓰였다.** 재작성을 켠 구성과 메타필터가 낀 구성(재작성 끔·배포본 API)의 "
                 "OTR 은 순환 가능성이 있어 단정하지 않는다. 순환이 없는 비교는 BM25 → 하이브리드 → +리랭커 구간이다."]
                if (judge_info.get("judge_names") or [None])[0] == "llm" else []),
              "- 지연시간·만족도·'찾는 시간 단축'은 이 실험이 측정하지 않았다."]
    return "\n".join(lines) + "\n"


def _scope_filter(arg: str | None) -> set[str] | None:
    """--scopes paper 처럼 쉼표로 준 범위. 비어 있으면 None(전부)."""
    return {x for x in (arg or "").split(",") if x} or None


def stage_report(args, wd: Path) -> None:
    data = _load(wd / "queries.json")
    runs = _load(wd / "runs.json")
    if not data or not runs:
        raise SystemExit("queries.json / runs.json 이 없다.")
    scopes = _scope_filter(args.scopes)
    queries = [q for q in data["queries"] if not scopes or q["scope"] in scopes]
    if not queries:
        raise SystemExit(f"--scopes {args.scopes} 에 해당하는 질의가 없다.")
    meta = dict(data["meta"])
    meta["report_seed"] = args.seed    # 신뢰구간 부트스트랩 시드 — build 시드와 다를 수 있어 summary.json 에 남긴다
    if scopes:    # 빼 둔 범위의 색인 문서 수가 표 머리에 남지 않게
        meta["corpus_docs"] = {k: v for k, v in meta.get("corpus_docs", {}).items() if k in scopes}
    judges = [j for j in args.judges.split(",") if j]
    jmaps = {j: _load(wd / f"judgments_{j}.json", {}) for j in judges}
    jmaps = {j: m for j, m in jmaps.items() if m}
    primary = next(iter(jmaps.values()), {})
    report = build_report(queries, runs, primary, seed=args.seed)

    models = _load(wd / "judge_models.json", {})
    judge_info: dict = {"judges": ", ".join(f"{j}={models.get(j, {}).get('label', '모델명 미기록')}"
                                            for j in jmaps) or "미실시"}
    if len(jmaps) >= 2:
        (n1, m1), (n2, m2) = list(jmaps.items())[:2]
        scope_of = {q["qid"]: q["scope"] for q in data["queries"]}
        common = [k for k in m1 if k in m2 and not m1[k].get("failed") and not m2[k].get("failed")
                  and (not scopes or scope_of.get(k.split("|", 1)[0]) in scopes)]
        a = [1 if is_on_topic(m1[k]) else 0 for k in common]
        b = [1 if is_on_topic(m2[k]) else 0 for k in common]
        judge_info["cross_judge"] = {
            "pair": [n1, n2], "n": len(common),
            "agreement": (sum(x == y for x, y in zip(a, b)) / len(common)) if common else None,
            "kappa": cohen_kappa(a, b),
        }
    agree = _load(wd / "human_agreement.json")
    if agree:
        kappa = agree.get("kappa")
        text = f"{agree['n']}쌍 일치율 {agree['agreement']:.1%}, kappa {'정의 불가' if kappa is None else format(kappa, '.2f')}"
        judged = agree.get("judge")
        if judged and judged != next(iter(jmaps), None):    # 다른 판정자의 라벨을 대상으로 한 일치도를 이 표의 판정자에 붙이지 않는다
            text += f" — {judged} 판정 대상(이 표의 판정자와 다름)"
        rater = agree.get("rater", "사람")
        if rater == "사람":
            judge_info["human"] = text
        else:    # 사람이 아닌 채점자(다른 LLM)의 결과는 '사람 검증'으로 표기하지 않는다
            judge_info["rater_check"] = f"{rater} {text}"
    judge_info["judge_names"] = list(jmaps)

    _dump(wd / "summary.json", {"meta": meta, "judge": judge_info, "groups": report})
    (wd / "brochure_table.md").write_text(render_markdown(report, meta, judge_info), encoding="utf-8")
    print((wd / "brochure_table.md").read_text(encoding="utf-8"))
    if "cross_judge" in judge_info:
        print("판정자 간:", json.dumps(judge_info["cross_judge"], ensure_ascii=False))


def stage_audit(args, wd: Path) -> str:
    """질의별 방식별 순위 + 재작성·메타데이터 필터가 실제로 한 일.

    '전체'가 '리랭커만'보다 나쁠 때 어느 질의에서 왜 그런지(필터가 정답을 걸렀나, 재작성이
    질의를 흐렸나) 로그로 확인하는 용도. --only-differ 로 두 방식의 순위가 갈린 질의만 본다.
    """
    data, runs = _load(wd / "queries.json"), _load(wd / "runs.json")
    if not data or not runs:
        raise SystemExit("queries.json / runs.json 이 없다.")
    arms = [a for a in ARMS if any(a in r for r in runs.values())]
    only = [a for a in (args.only_differ or "").split(",") if a]
    lines: list[str] = []
    for q in data["queries"]:
        r = runs.get(q["qid"], {})
        ranks = {a: rank_of(r[a].get("ids", []), q["expected_id"]) for a in arms if a in r}
        if only and len({ranks.get(a) for a in only}) <= 1:
            continue
        shown = " ".join(f"{a.replace('skovix_', 'sk_')}={ranks[a] or '-'}" for a in arms if a in ranks)
        lines.append(f"{q['qid']}  [{shown}]\n  질문: {q['query']}")
        for a in arms:
            lines += [f"  {a}: {m}" for m in r.get(a, {}).get("log", [])]
    text = "\n".join(lines) or "(해당하는 질의 없음)"
    (wd / "audit.txt").write_text(text + "\n", encoding="utf-8")
    print(text)
    return text


# ══════════════════════════════════════════════════════════════
# 사람 검증 — OTR 판정이 사람과 얼마나 맞는지
# ══════════════════════════════════════════════════════════════
async def stage_review_sheet(args, be, wd: Path) -> None:
    data = _load(wd / "queries.json")
    judgments = _load(wd / f"judgments_{args.judge}.json", {})
    if not data or not judgments:
        raise SystemExit("queries.json / judgments 가 없다 — judge 를 먼저 실행하세요.")
    qmap = {q["qid"]: q for q in data["queries"]}
    scopes = _scope_filter(args.scopes)
    usable = {k: v for k, v in judgments.items()
              if not v.get("failed") and (not scopes or qmap.get(k.split("|", 1)[0], {}).get("scope") in scopes)}
    pos = [k for k, v in sorted(usable.items()) if is_on_topic(v)]       # 정렬해 두어야 같은 시드가 같은 표본을 뽑는다
    neg = [k for k, v in sorted(usable.items()) if not is_on_topic(v)]
    rng = random.Random(args.seed)
    rng.shuffle(pos), rng.shuffle(neg)
    picked = pos[: args.n // 2] + neg[: args.n - args.n // 2]
    rng.shuffle(picked)
    infos = await be.doc_infos(sorted({k.split("|", 1)[1] for k in picked}))

    key, path = {}, wd / "review_sheet.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pair_id", "검색어", "문서 제목", "주제어", "내용 발췌", "사람 판정(1=주제에 주로 맞음, 0=아님)", "메모"])
        for i, k in enumerate(picked):
            qid, d = k.split("|", 1)
            doc = infos.get(d, {})
            key[str(i)] = {"pair": k, "llm": 1 if is_on_topic(judgments[k]) else 0}
            w.writerow([i, qmap[qid]["query"], doc.get("title", ""), doc.get("keyword", ""),
                        re.sub(r"\s+", " ", doc.get("body") or "")[:400], "", ""])
    _dump(wd / "review_key.json", key)
    _dump(wd / "review_meta.json", {"judge": args.judge, "scopes": sorted(scopes) if scopes else None})
    print(f"검토 시트 {len(picked)}쌍 → {path}  (LLM 판정은 가려져 있음. 채운 뒤 agreement 단계 실행)")


def stage_agreement(args, wd: Path) -> None:
    key = _load(wd / "review_key.json")
    if not key:
        raise SystemExit("review_key.json 이 없다 — review-sheet 를 먼저 실행하세요.")
    human: dict[str, int] = {}
    with open(args.sheet, encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if not row or not row[0].isdigit():
                continue
            v = (row[5] if len(row) > 5 else "").strip()
            if v in ("0", "1"):
                human[row[0]] = int(v)
    ids = [i for i in key if i in human]
    if not ids:
        raise SystemExit("사람 판정 열이 비어 있다.")
    llm = [key[i]["llm"] for i in ids]
    hum = [human[i] for i in ids]
    tp = sum(1 for x, y in zip(llm, hum) if x == 1 and y == 1)
    res = {
        "rater": args.rater, "judge": _load(wd / "review_meta.json", {}).get("judge"), "n": len(ids), "agreement": sum(x == y for x, y in zip(llm, hum)) / len(ids),
        "kappa": cohen_kappa(llm, hum),
        "llm_precision": tp / max(1, sum(llm)), "llm_recall": tp / max(1, sum(hum)),
        "note": "표본은 LLM 판정 1/0 을 절반씩 뽑은 층화 표본이라 일치율은 전체 분포 기준이 아니다.",
    }
    _dump(wd / "human_agreement.json", res)
    print(json.dumps(res, ensure_ascii=False, indent=1))


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════
def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--workdir", default="/app/data/brochure_eval")
    ap.add_argument("--seed", type=int, default=20261013)
    sub = ap.add_subparsers(dest="stage", required=True)

    b = sub.add_parser("build", help="자연어 질문 세트 생성")
    b.add_argument("--n-papers", type=int, default=150)
    b.add_argument("--n-books", type=int, default=50)
    b.add_argument("--golden", default=None, help="build_golden_queries.py 결과 JSON(선택)")
    b.add_argument("--concurrency", type=int, default=4)
    b.add_argument("--force", action="store_true", help="runs.json 이 있는 작업 폴더에서도 build 를 허용(옛 runs·judgments 는 직접 치울 것)")

    r = sub.add_parser("run", help="방식별 검색 실행")
    r.add_argument("--arms", default=",".join(a for a in ARMS if a != API_ARM),
                   help=f"기본은 {API_ARM} 를 뺀 전부 — 배포된 API 를 부르는 {API_ARM} 는 배포 뒤 --arms 로 따로 지정")

    j = sub.add_parser("judge", help="OTR 판정")
    j.add_argument("--judge", choices=["vlm", "llm"], default="vlm",
                   help="vlm=Qwen3-VL(기본, 질의 재작성 모델과 다른 계열) / llm=gemma")
    j.add_argument("--qtypes", default="nl", help="판정할 질의 유형(쉼표). 기본 nl 만 — golden 유형까지 하면 비용이 커진다")
    j.add_argument("--concurrency", type=int, default=4)
    j.add_argument("--model-label", default=None,
                   help="리포트에 적을 판정 모델명. 기본은 /v1/models 로 실제 서빙 모델을 확인 — 그래도 별칭만 보이면 직접 지정")

    p = sub.add_parser("report", help="집계 + 브로셔용 표")
    p.add_argument("--judges", default="vlm", help="쉼표 구분. 첫 번째가 OTR 의 기준 판정자, 둘 이상이면 판정자 간 일치도도 계산")
    p.add_argument("--scopes", default=None, help="표에 넣을 범위(쉼표). 예: paper — 안 주면 전부")

    u = sub.add_parser("audit", help="질의별 순위 + 재작성·메타데이터 필터 적용 내역")
    u.add_argument("--only-differ", default=None,
                   help="이 방식들(쉼표)의 순위가 갈린 질의만 보기. 예: skovix_rerank,skovix_full")

    s = sub.add_parser("review-sheet", help="사람 검증용 CSV 생성")
    s.add_argument("--judge", choices=["vlm", "llm"], default="vlm")
    s.add_argument("--n", type=int, default=60)
    s.add_argument("--scopes", default=None, help="표본을 뽑을 범위(쉼표). 예: paper — 안 주면 전부")

    a = sub.add_parser("agreement", help="사람 판정 vs LLM 판정 일치도")
    a.add_argument("--sheet", required=True)
    a.add_argument("--rater", default="사람",
                   help="시트를 채운 채점자. 사람이 아니면(예: Claude) 리포트에 '사람 검증'이 아니라 '다른 LLM 교차 확인'으로 적힌다")
    return ap


async def main_async(args) -> None:
    wd = Path(args.workdir)
    wd.mkdir(parents=True, exist_ok=True)
    if args.stage == "report":
        stage_report(args, wd)
        return
    if args.stage == "agreement":
        stage_agreement(args, wd)
        return
    if args.stage == "audit":
        stage_audit(args, wd)
        return
    be = ServerBackend()
    try:
        if args.stage == "build":
            print(json.dumps(await stage_build(args, be, wd), ensure_ascii=False))
        elif args.stage == "run":
            await stage_run(args, be, wd)
        elif args.stage == "judge":
            await stage_judge(args, be, wd)
        elif args.stage == "review-sheet":
            await stage_review_sheet(args, be, wd)
    finally:
        await be.close()


if __name__ == "__main__":
    asyncio.run(main_async(make_parser().parse_args()))
