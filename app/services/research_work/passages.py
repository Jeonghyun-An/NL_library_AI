"""passages.py — 절 생성 입력의 원문 대목 모으기·고르기 (spec §5-5, 계약 §5) — FastAPI 전용.

절에 넣는 논문(6편 이하)마다 원문 대목 하나(EXCERPT_CHARS 자 이하)를 붙인다. 대목은 생성을 넣는 FastAPI 가
고른다 — 리랭커·Milvus 는 FastAPI 프로세스에만 있고 생성 워커(celery-research-plan)에는 GPU·모델이 없다(함정 17).

후보는 딥리서치 스냅숏의 근거 청크(state_snapshot.evidence[eid].chunks)가 먼저다 — 탐색이 이미 원문 대목만
골라 두었다. 스냅숏에 없는 논문(되살림·담기)은 Milvus 에서 그 논문 한 편의 청크를 읽는다. 어느 쪽이든 메타청크·
보강 청크([초록]·[키워드]·[표 설명]·[그림 설명])는 탐색과 같은 규칙(explorer.is_source_passage)으로 뺀다.

리랭커(compute_scores)·Milvus(ensure_collection)·검색 파이프라인(_RERANK_FAILURES)은 torch·FlagEmbedding·
pymilvus 를 끌어오므로 함수 안에서 import 한다(함정 13). 실패는 실제로 나는 타입만 받는다(함정 19) — 리랭커는
pipeline._RERANK_FAILURES, Milvus 는 거기에 MilvusException 과 grpc.RpcError(기한 초과)를 더한다. 동기 함수다 —
엔드포인트가 읽기 트랜잭션을 닫은 뒤 run_in_threadpool 로 부른다(함정 18).
"""
import logging
import re
from types import SimpleNamespace

from services.research.explorer import is_source_passage
from services.research_work.shapes import EXCERPT_CHARS

log = logging.getLogger(__name__)

CLIP_WINDOW = 100      # 자를 자리(문장 끝·공백)를 찾는 끝 구간(글자)
MAX_PASSAGES = 500     # Milvus 에서 한 편당 읽는 청크 상한 — 리랭크가 동기 요청(게이트웨이 120초) 안에 끝나게
# 문장 끝 — . ! ? 는 원문에서 바로 뒤가 공백일 때만(소수점 3.14·p<.05 에서 자르지 않게, chunker._split_sentences 의
# `(?<=[.?!。])\s+` 와 같은 규칙), 。 는 뒤에 공백 없이도 문장 끝이다
_SENTENCE_END = ".!?"
_FULL_STOP = "。"
# Milvus 표현식에 넣는 cnts_id — 따옴표·역슬래시가 든 값은 표현식을 깨므로 읽지 않는다
_SAFE_ID = re.compile(r"[A-Za-z0-9_.\-]{1,64}")
# Milvus query 상한(초). 정수로 준다 — pymilvus 는 timeout 이 int 일 때만 RPC 재시도 루프도 그 시간에서 끊는다
# (아니면 75번 재시도로만 끊겨 UNAVAILABLE 이면 한 편에 약 3.5분, 응답이 없으면 gRPC 기한이 없어 무한정 기다린다).
# [이 절 쓰기]는 스냅숏에 없는 논문(되살림·담기)마다 최대 6번 차례로 부르므로 한 편이 묶이면 게이트웨이
# proxy_read_timeout 120s 를 넘겨 504 가 나고 스레드풀 스레드도 묶인다 — membership._MILVUS_TIMEOUT_SECONDS 와 같은 값·교훈
_MILVUS_TIMEOUT_SECONDS = 10


def clip(text: str, limit: int = EXCERPT_CHARS) -> str:
    """limit 자 안으로 자른다. 말줄임표를 붙이지 않는다 — 대목은 원문 그대로의 글자여야 한다.

    끝 CLIP_WINDOW 자 안에 문장 끝(바로 뒤가 공백인 . ! ?, 또는 。)이 있으면 그 뒤에서, 없으면 그 구간의 마지막
    공백 앞에서, 그것도 없으면 limit 자에서 자른다. 소수점(3.14·p<.05)은 문장 끝이 아니다 — 숫자 가운데서
    끊기면 근거의 값이 바뀐다.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    window = range(max(0, limit - CLIP_WINDOW), limit)
    # len(text) > limit 이라 text[i + 1] 은 늘 있다 — limit 바로 앞 마침표도 원문의 다음 글자로 판단한다
    ends = [i for i in window
            if head[i] == _FULL_STOP or (head[i] in _SENTENCE_END and text[i + 1].isspace())]
    if ends:
        return head[: ends[-1] + 1]
    spaces = [i for i in window if head[i].isspace()]
    if spaces:
        return head[: spaces[-1]].rstrip()
    return head


def _chunk_idx(chunk_id: str) -> int:
    """'KCI_FI001__0012' → 12, 메타청크 '…__-001' → -1(indexer 의 chunk_id 규칙). 모르는 모양은 본문(0)으로 본다."""
    _, sep, tail = (chunk_id or "").rpartition("__")
    try:
        return int(tail) if sep else 0
    except ValueError:
        return 0


def _source(chunk_idx: int, page_start, text: str) -> bool:
    return is_source_passage(SimpleNamespace(chunk_idx=chunk_idx, page_start=page_start or 0, text=text))


def _passage(chunk_id: str, text: str, page_start, page_end, score) -> dict:
    start = int(page_start or 0)
    return {"chunk_id": chunk_id, "text": text, "page_start": start,
            "page_end": int(page_end if page_end is not None else start),
            "score": None if score is None else float(score)}


def snapshot_passages(snapshot: dict | None, cnts_id: str) -> list[dict]:
    """딥리서치 스냅숏에서 그 논문의 청크 — [{chunk_id, text, page_start, page_end, score}], 점수 높은 순(같으면
    스냅숏 순서), 같은 청크는 한 번. 탐색이 원문 대목만 남겼지만 그 규칙 전에 만든 옛 잡에는 보강 청크가 섞여
    있을 수 있어 같은 규칙으로 한 번 더 거른다."""
    evidence = snapshot.get("evidence") if isinstance(snapshot, dict) else None
    out: list[dict] = []
    seen: set[str] = set()
    for ev in (evidence or {}).values():
        if not isinstance(ev, dict) or ev.get("cnts_id") != cnts_id:
            continue
        for c in ev.get("chunks") or []:
            chunk_id, text = c.get("chunk_id"), c.get("text")
            if not chunk_id or not text or chunk_id in seen:
                continue
            if not _source(_chunk_idx(chunk_id), c.get("page_start"), text):
                continue
            seen.add(chunk_id)
            out.append(_passage(chunk_id, text, c.get("page_start"), c.get("page_end"), c.get("score")))
    out.sort(key=lambda p: p["score"] if p["score"] is not None else float("-inf"), reverse=True)
    return out


def milvus_passages(cnts_id: str) -> list[dict]:
    """Milvus 에서 그 논문 한 편의 원문 청크(청크 순서, 점수 없음). FastAPI 전용·동기.

    읽지 못하면(연결 실패·컬렉션 문제·기한 초과) 빈 목록 — 그 논문은 대목 없이 초록만으로 쓴다."""
    if not _SAFE_ID.fullmatch(cnts_id or ""):
        log.warning("[passages] Milvus 표현식에 넣을 수 없는 cnts_id — 대목 없이 쓴다 %r", cnts_id)
        return []
    import grpc
    from pymilvus.exceptions import MilvusException
    from services.ingestion.indexer import ensure_collection
    from services.search.pipeline import _RERANK_FAILURES

    try:
        rows = ensure_collection().query(
            expr=f'book_id == "{cnts_id}" && chunk_idx >= 0',
            output_fields=["chunk_id", "chunk_idx", "text", "page_start", "page_end"],
            limit=MAX_PASSAGES, timeout=_MILVUS_TIMEOUT_SECONDS,
        )
    # 기한을 넘기면 pymilvus 는 DEADLINE_EXCEEDED 를 MilvusException 이 아니라 날 grpc.RpcError 로 다시 던진다
    except (MilvusException, grpc.RpcError, *_RERANK_FAILURES) as e:
        log.warning("[passages] Milvus 청크를 읽지 못했다 — 대목 없이 쓴다 cnts=%s: %s", cnts_id, e)
        return []
    out: list[dict] = []
    for r in sorted(rows, key=lambda r: r.get("chunk_idx") or 0):
        text = r.get("text") or ""
        if not text or not _source(r.get("chunk_idx") or 0, r.get("page_start"), text):
            continue
        out.append(_passage(r.get("chunk_id") or "", text, r.get("page_start"), r.get("page_end"), None))
    return out


def pick_excerpt(query: str, passages: list[dict], *, limit: int = EXCERPT_CHARS) -> dict | None:
    """후보 가운데 질의에 가장 맞는 대목 하나 — {chunk_id, page_start, page_end, text(limit 자 이하)}. 후보가 없으면 None.

    리랭커 점수(compute_scores)가 가장 높은 대목을 고른다. 리랭커가 실제로 내는 실패(pipeline._RERANK_FAILURES)면
    저장된 점수(스냅숏의 검색 점수)가 가장 높은 대목, 점수가 없으면 앞 대목이다(같으면 앞)."""
    if not passages:
        return None
    from services.search.pipeline import _RERANK_FAILURES
    from services.search.reranker import compute_scores

    try:
        scores = list(compute_scores(query, [p["text"] for p in passages]))
    except _RERANK_FAILURES as e:
        log.warning("[passages] 리랭커 실패 — 저장된 점수로 대목을 고른다: %s", e)
        scores = [p["score"] if p.get("score") is not None else float("-inf") for p in passages]
    best = passages[max(range(len(passages)), key=scores.__getitem__)]
    return {"chunk_id": best["chunk_id"], "page_start": best["page_start"], "page_end": best["page_end"],
            "text": clip(best["text"], limit)}
