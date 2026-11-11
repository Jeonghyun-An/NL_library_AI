"""
embedder.py — BGE-M3 dense + sparse 임베딩

embed_texts() → (dense_vecs, sparse_vecs) 튜플 반환
  dense_vecs : list[list[float]]       – Milvus FLOAT_VECTOR
  sparse_vecs: list[dict[int, float]]  – Milvus SPARSE_FLOAT_VECTOR (lexical weights)

두 갈래(EMBEDDING_BACKEND):
- local: 프로세스 안에서 FlagEmbedding 으로 BGE-M3 를 올린다(예전 방식 — 프로세스마다 GPU 에 한 벌씩).
- http : GPU 서버의 공용 bge-m3(vLLM) 두 개를 부른다 — dense 는 /v1/embeddings, sparse 는 /pooling(task token_classify).
  vLLM 은 서버 하나가 결과 한 종류만 내서 둘로 나뉜다(~/models/bge-m3-dense.sh·bge-m3-sparse.sh, 2026-11-11).
  sparse 서버는 토큰 위치마다 가중치만 주고(앞뒤 BOS·EOS 자리는 뺀다) 토큰 번호는 주지 않는다. 그래서 여기서 같은
  토크나이저로 잘라 만든 토큰 번호를 그대로 보내고, 돌아온 가중치를 그 번호와 짝지어 FlagEmbedding 의
  _process_token_weights 와 같은 규칙으로 모은다 — 특수 토큰(cls·eos·pad·unk)과 0 이하는 빼고, 같은 토큰은 큰 값 하나.
  글자가 아니라 토큰 번호를 보내야 서버가 다르게 잘라 번호와 가중치가 어긋날 일이 없다. 어긋나도 오류 없이 검색 순위만
  나빠지므로, 받은 가중치 수가 보낸 토큰 수와 맞지 않으면 그 자리에서 멈춘다.
  공용 서버는 다른 서비스도 같이 써서 앞 요청이 밀리면 기다릴 수 있다 — async 호출자는 offload_embed 로 부른다(http 갈래는
  스레드에서 기다려 fastapi 이벤트 루프를 잡지 않는다).
"""
import asyncio
import logging
import threading
import time
from functools import lru_cache
from typing import Any, Callable, TypeAlias

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)

DenseVecs: TypeAlias = list[list[float]]
SparseVecs: TypeAlias = list[dict[int, float]]

# 빨리 끝나는 일시 오류(연결 거절·재사용 연결 끊김·연결 시간 초과·5xx·429)는 이만큼 쉬고 다시 보낸다(첫 시도 포함 3번).
# 같은 공용 vLLM 을 부르는 llm_client 도 재시도한다. 읽기 시간 초과는 다시 보내지 않는다 — 질의 하나가
# EMBEDDING_HTTP_TIMEOUT 보다 오래 묶이지 않게. 적재는 아이템 단위 자동 재시도(job_runtime)가 뒤를 받친다
_RETRY_DELAYS = (0.5, 2.0)
_RETRYABLE_TRANSPORT = (httpx.NetworkError, httpx.RemoteProtocolError, httpx.ConnectTimeout, httpx.PoolTimeout)
# vLLM(uvicorn)의 keep-alive 는 5초다 — 서버가 막 닫은 연결을 다시 쓰지 않게 이보다 짧게 버린다
_KEEPALIVE_EXPIRY = 2.0


class EmbeddingUnavailable(ConnectionError):
    """공용 임베딩 서버에 닿지 못했거나(연결·시간 초과) 서버가 일시 오류(5xx·429)를 냈다.

    ConnectionError(=OSError) 라서 기존 처리가 그대로 잡는다 — 검색 라우트 가드(core.errors.is_search_outage)는 503,
    딥리서치 개념 친밀도(membership._FAILURES)·대목 고르기(pipeline._RERANK_FAILURES)는 경고 후 대체 경로로 간다."""


# ── local: 프로세스 안 FlagEmbedding ─────────────────────
@lru_cache(maxsize=1)
def _load_model():
    # http 갈래에서는 부르지 않는다 — FlagEmbedding(torch) 을 불러오지도, GPU 에 모델을 올리지도 않게 여기서 import 한다
    from FlagEmbedding import BGEM3FlagModel

    cfg = get_settings()
    return BGEM3FlagModel(
        cfg.EMBEDDING_MODEL_NAME,
        use_fp16=True,
    )


def _embed_local(texts: list[str]) -> tuple[DenseVecs, SparseVecs]:
    cfg = get_settings()
    model = _load_model()
    output = model.encode(
        texts,
        batch_size=cfg.EMBEDDING_BATCH_SIZE,
        max_length=cfg.EMBEDDING_MAX_LENGTH,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    dense: DenseVecs = output["dense_vecs"].tolist()
    sparse: SparseVecs = output["lexical_weights"]  # list[dict[int, float]]
    return dense, sparse


# ── http: 공용 bge-m3(vLLM) ─────────────────────────────
# 빠른 토크나이저(Rust)는 여러 스레드가 동시에 쓰면 'Already borrowed' 로 깨진다 — 자르는 동안만 잠근다
_TOKENIZER_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _tokenizer():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(get_settings().EMBEDDING_MODEL_NAME)


@lru_cache(maxsize=1)
def _http_client() -> httpx.Client:
    cfg = get_settings()
    timeout = httpx.Timeout(cfg.EMBEDDING_HTTP_TIMEOUT, connect=cfg.EMBEDDING_HTTP_CONNECT_TIMEOUT)
    return httpx.Client(timeout=timeout, limits=httpx.Limits(keepalive_expiry=_KEEPALIVE_EXPIRY))


def _token_ids(texts: list[str]) -> list[list[int]]:
    """FlagEmbedding.encode 와 같은 자르기 — 특수 토큰(앞 <s>·뒤 </s>)을 포함해 EMBEDDING_MAX_LENGTH 토큰까지."""
    cfg = get_settings()
    with _TOKENIZER_LOCK:
        encoded = _tokenizer()(texts, truncation=True, max_length=cfg.EMBEDDING_MAX_LENGTH, padding=False)
    return [list(ids) for ids in encoded["input_ids"]]


def _unused_token_ids() -> frozenset[int]:
    """FlagEmbedding._process_token_weights 가 빼는 토큰 — cls·eos·pad·unk."""
    tok = _tokenizer()
    return frozenset(
        i for i in (tok.cls_token_id, tok.eos_token_id, tok.pad_token_id, tok.unk_token_id) if i is not None
    )


def _post(url: str, payload: dict) -> list[dict]:
    """공용 서버에 보내고 data 를 index 순서로 돌려준다. 연결·일시 오류는 EmbeddingUnavailable, 그 밖은 RuntimeError.

    빨리 끝나는 일시 오류는 _RETRY_DELAYS 만큼 쉬고 다시 보낸다. 다 실패하면 마지막 오류를 EmbeddingUnavailable 로 낸다."""
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        cause: BaseException | None = None
        try:
            resp = _http_client().post(url, json=payload)
        except _RETRYABLE_TRANSPORT as e:   # 연결 거절·재사용 연결 끊김·연결 시간 초과
            failure = EmbeddingUnavailable(f"임베딩 서버 연결 실패({url}): {type(e).__name__}: {e}")
            cause = e
        except httpx.TransportError as e:   # 읽기·쓰기 시간 초과 등 — 다시 보내지 않는다
            raise EmbeddingUnavailable(f"임베딩 서버 연결 실패({url}): {type(e).__name__}: {e}") from e
        else:
            # 5xx·429 는 서버가 잠시 못 받는다는 뜻 — 연결 장애처럼 다룬다(검색 503·딥리드 retrieval_failed·딥리서치 폴백)
            if resp.status_code != 429 and resp.status_code < 500:
                return _parse(url, resp)
            failure = EmbeddingUnavailable(f"임베딩 서버 일시 오류({url}): HTTP {resp.status_code} {resp.text[:300]}")
        if delay is None:
            raise failure from cause
        log.warning("임베딩 서버 일시 오류 — %.1f초 뒤 다시 보낸다(%d/%d): %s", delay, attempt, len(_RETRY_DELAYS), failure)
        time.sleep(delay)
    raise AssertionError("도달하지 않는다")   # 마지막 차례(delay None)는 위에서 돌려주거나 던진다


def _parse(url: str, resp: httpx.Response) -> list[dict]:
    if resp.status_code != 200:
        raise RuntimeError(f"임베딩 서버가 요청을 거절했다({url}): HTTP {resp.status_code} {resp.text[:300]}")
    try:
        data = resp.json()["data"]
        return sorted(data, key=lambda d: d["index"])
    except (ValueError, KeyError, TypeError) as e:
        raise RuntimeError(f"임베딩 서버 응답 형식이 다르다({url}): {resp.text[:300]}") from e


def _dense_http(batch_ids: list[list[int]]) -> DenseVecs:
    cfg = get_settings()
    data = _post(
        f"{cfg.EMBEDDING_DENSE_URL.rstrip('/')}/v1/embeddings",
        {"model": cfg.EMBEDDING_SERVED_MODEL, "input": batch_ids, "encoding_format": "float"},
    )
    if len(data) != len(batch_ids):
        raise RuntimeError(f"dense 응답 수({len(data)})가 보낸 수({len(batch_ids)})와 다르다")
    return [[float(x) for x in d["embedding"]] for d in data]


def _sparse_weights(weights: list, ids: list[int], unused: frozenset[int]) -> dict[int, float]:
    """한 입력의 토큰 위치별 가중치를 {토큰 번호: 가중치} 로 — FlagEmbedding._process_token_weights 와 같은 규칙.

    서버는 맨 앞(BOS)·맨 끝(EOS) 자리를 빼고 준다 → ids[1:-1] 과 짝짓는다. 수가 다르면 짝이 어긋난 것이니 멈춘다."""
    inner = ids[1:-1]
    if len(weights) != len(inner):
        raise RuntimeError(f"sparse 가중치 수({len(weights)})가 토큰 수({len(inner)}, 앞뒤 특수 토큰 제외)와 다르다")
    result: dict[int, float] = {}
    for w, token_id in zip(weights, inner):
        w = float(w[0] if isinstance(w, list) else w)   # 서버 판에 따라 [[w], …] 로 올 수 있다
        if token_id in unused or w <= 0:
            continue
        if w > result.get(token_id, 0.0):
            result[token_id] = w
    return result


def _sparse_http(batch_ids: list[list[int]]) -> SparseVecs:
    cfg = get_settings()
    data = _post(
        f"{cfg.EMBEDDING_SPARSE_URL.rstrip('/')}/pooling",
        {"model": cfg.EMBEDDING_SERVED_MODEL, "task": "token_classify", "input": batch_ids},
    )
    if len(data) != len(batch_ids):
        raise RuntimeError(f"sparse 응답 수({len(data)})가 보낸 수({len(batch_ids)})와 다르다")
    unused = _unused_token_ids()
    return [_sparse_weights(d["data"], ids, unused) for d, ids in zip(data, batch_ids)]


def _embed_http(texts: list[str], need_sparse: bool) -> tuple[DenseVecs, SparseVecs]:
    cfg = get_settings()
    all_ids = _token_ids(texts)
    size = max(1, cfg.EMBEDDING_BATCH_SIZE)
    dense: DenseVecs = []
    sparse: SparseVecs = []
    for start in range(0, len(all_ids), size):
        batch = all_ids[start:start + size]
        dense.extend(_dense_http(batch))
        sparse.extend(_sparse_http(batch) if need_sparse else [{} for _ in batch])
    return dense, sparse


# ── 공개 함수 ─────────────────────────────────────────
def embed_texts(
    texts: list[str],
    is_query: bool = False,  # BGE-M3은 내부 처리 — API 호환용으로 유지
    *,
    need_sparse: bool = True,
) -> tuple[DenseVecs, SparseVecs]:
    """
    texts 인코딩 → (dense_vecs, sparse_vecs) 반환.

    sparse_vecs 각 원소: {token_id(int): weight(float)}
    → Milvus SPARSE_FLOAT_VECTOR 에 직접 삽입 가능
    need_sparse=False: dense 만 쓰는 호출(의미 청킹·개념 친밀도)용 — http 갈래는 sparse 서버를 부르지 않고 빈 dict 를
    채운다(sparse 서버가 꺼져도 dense 만 쓰는 일은 돈다). local 갈래는 예전처럼 둘 다 계산한다.
    공용 서버에 닿지 못하면 EmbeddingUnavailable(ConnectionError) 을 던진다.
    """
    _ = is_query  # BGE-M3은 query/passage 인코딩이 동일 — 호환성을 위해 파라미터 유지
    if not texts:
        return [], []
    if get_settings().EMBEDDING_BACKEND == "http":
        return _embed_http(texts, need_sparse)
    return _embed_local(texts)


async def offload_embed(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """async 호출자(검색·관련 자료·DeepRead)용 — fn(=호출하는 모듈이 import 한 embed_texts)을 부른다.

    http: 스레드에서 부른다. 공용 서버가 다른 서비스 요청에 밀려 기다리는 동안 fastapi(워커 1개)의 이벤트 루프를 잡으면
          다른 사용자의 검색·DeepRead 스트림(15초 ping)까지 같이 멈춘다. 토크나이저는 _TOKENIZER_LOCK, httpx.Client 는
          스레드 사이에서 같이 써도 된다.
    local: 예전처럼 루프에서 바로 부른다 — FlagEmbedding 의 빠른 토크나이저는 여러 스레드가 동시에 쓰면 'Already borrowed'
           로 깨진다(book_chat._search_book_chunks 참고). GPU 연산이라 수십 ms 다.
    fn 을 받는 것은 호출 모듈의 embed_texts 이름을 테스트가 바꿔 끼우는 자리를 그대로 두려고다."""
    if get_settings().EMBEDDING_BACKEND == "http":
        return await asyncio.to_thread(fn, *args, **kwargs)
    return fn(*args, **kwargs)


def warmup() -> None:
    """fastapi 기동 때 한 번 부른다.

    local: 모델을 GPU 에 올린다 — 실패하면 예전처럼 기동을 멈춘다.
    http : 공용 서버가 응답하는지만 본다 — 꺼져 있거나 아직 뜨는 중이어도 기동은 이어 간다. 여기서 멈추면 fastapi 가
    재시작을 되풀이하고 그 뒤 gateway 까지 안 떠 사이트 전체가 내려간다. 서버가 돌아오면 다음 요청부터 그대로 쓴다."""
    cfg = get_settings()
    if cfg.EMBEDDING_BACKEND != "http":
        embed_texts(["워밍업"])
        log.info("임베딩 모델 로드 완료(local)")
        return
    try:
        embed_texts(["워밍업"])
    except Exception as e:   # 기동을 막지 않는 것이 목적 — 토크나이저 로드 실패(OSError)·응답 형식 오류(RuntimeError) 포함
        log.warning("공용 임베딩 서버 확인 실패 — 기동은 계속한다(검색은 서버가 돌아오면 된다): %s: %s",
                    type(e).__name__, e)
        return
    log.info("공용 임베딩 서버 응답 확인(dense %s · sparse %s)", cfg.EMBEDDING_DENSE_URL, cfg.EMBEDDING_SPARSE_URL)
