"""embedder — 공용 bge-m3(vLLM) http 갈래.

dense 는 /v1/embeddings, sparse 는 /pooling(task token_classify) 를 부른다. sparse 서버는 토큰 위치별 가중치만 주고
(앞뒤 BOS·EOS 자리 제외) 토큰 번호는 주지 않으므로, 보낸 토큰 번호와 짝지어 FlagEmbedding 과 같은 규칙으로 모은다.
서버는 httpx.MockTransport, 토크나이저는 대역 — 네트워크·모델 파일 없이 돈다.
"""
import asyncio
import json
import re
import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml

from core.config import Settings, get_settings
from services.ingestion import embedder

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"
DENSE = "http://dense.test:8000"
SPARSE = "http://sparse.test:8000"


class _Tok:
    """bge-m3(XLM-R) 꼴 대역 — <s>=0, <pad>=1, </s>=2, <unk>=3. 낱말마다 번호를 붙이고 '?' 는 unk."""

    cls_token_id, pad_token_id, eos_token_id, unk_token_id = 0, 1, 2, 3

    def __init__(self):
        self.vocab: dict[str, int] = {}
        self.calls: list[dict] = []

    def _id(self, word: str) -> int:
        if word == "?":
            return self.unk_token_id
        return self.vocab.setdefault(word, 10 + len(self.vocab))

    def __call__(self, texts, *, truncation, max_length, padding):
        self.calls.append({"truncation": truncation, "max_length": max_length, "padding": padding})
        out = []
        for text in texts:
            ids = [self._id(w) for w in text.split()]
            if truncation:
                ids = ids[: max_length - 2]
            out.append([self.cls_token_id, *ids, self.eos_token_id])
        return {"input_ids": out}


class _Servers:
    """dense·sparse 공용 서버 대역. 받은 요청을 남기고, 토큰마다 정해진 가중치를 돌려준다."""

    def __init__(self):
        self.requests: list[tuple[str, dict]] = []
        self.weight = lambda token_id, pos: 0.1 * (pos + 1)   # 위치에 따라 커지는 가중치
        self.fail: Exception | None = None
        self.status = 200
        self.body: str | None = None
        self.reverse = False
        self.nested = False
        self.queue: list = []   # 요청마다 앞에서 하나씩 꺼내 쓰는 일시 오류(예외 또는 상태 코드) — 다 쓰면 정상

    def handler(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        self.requests.append((str(request.url), payload))
        if self.queue:
            step = self.queue.pop(0)
            if isinstance(step, Exception):
                raise step
            return httpx.Response(step, text="busy")
        if self.fail is not None:
            raise self.fail
        if self.status != 200 or self.body is not None:
            return httpx.Response(self.status, text=self.body or "error")
        inputs = payload["input"]
        if request.url.path == "/v1/embeddings":
            data = [{"index": i, "object": "embedding", "embedding": [float(len(ids)), float(ids[1] if len(ids) > 2 else 0)]}
                    for i, ids in enumerate(inputs)]
        else:
            data = []
            for i, ids in enumerate(inputs):
                weights = [self.weight(t, p) for p, t in enumerate(ids[1:-1])]
                data.append({"index": i, "object": "pooling",
                             "data": [[w] for w in weights] if self.nested else weights})
        if self.reverse:
            data = list(reversed(data))
        return httpx.Response(200, json={"object": "list", "data": data})

    def urls(self) -> list[str]:
        return [u for u, _ in self.requests]


@pytest.fixture
def http(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "EMBEDDING_BACKEND", "http")
    monkeypatch.setattr(cfg, "EMBEDDING_DENSE_URL", DENSE)
    monkeypatch.setattr(cfg, "EMBEDDING_SPARSE_URL", SPARSE + "/")   # 끝 / 는 떼고 붙인다
    monkeypatch.setattr(cfg, "EMBEDDING_SERVED_MODEL", "bge-m3")
    monkeypatch.setattr(cfg, "EMBEDDING_BATCH_SIZE", 32)
    monkeypatch.setattr(cfg, "EMBEDDING_MAX_LENGTH", 512)
    tok, servers = _Tok(), _Servers()
    monkeypatch.setattr(embedder, "_tokenizer", lambda: tok)
    monkeypatch.setattr(embedder, "_http_client", lambda: httpx.Client(transport=httpx.MockTransport(servers.handler)))
    monkeypatch.setattr(embedder, "_embed_local", lambda texts: pytest.fail("http 갈래에서 FlagEmbedding 을 부르면 안 된다"))
    monkeypatch.setattr(embedder, "_RETRY_DELAYS", (0.0, 0.0))   # 재시도 횟수는 그대로, 쉬는 시간만 없앤다
    return SimpleNamespace(cfg=cfg, tok=tok, servers=servers)


def test_http_returns_dense_and_sparse_in_input_order(http):
    http.servers.reverse = True   # 서버가 index 순서를 섞어 줘도
    dense, sparse = embed(["가 나", "다 라 마"])

    assert dense == [[4.0, 10.0], [5.0, 12.0]]       # [토큰 수, 첫 토큰 번호] — 입력 순서 그대로
    assert sparse == [{10: 0.1, 11: 0.2}, {12: 0.1, 13: 0.2, 14: pytest.approx(0.3)}]
    assert all(isinstance(k, int) and isinstance(v, float) for s in sparse for k, v in s.items())


def test_requests_send_token_ids_with_special_tokens_and_served_model(http):
    embed(["가 나"])

    (dense_url, dense_body), (sparse_url, sparse_body) = http.servers.requests
    assert dense_url == f"{DENSE}/v1/embeddings"
    assert dense_body == {"model": "bge-m3", "input": [[0, 10, 11, 2]], "encoding_format": "float"}
    assert sparse_url == f"{SPARSE}/pooling"
    assert sparse_body == {"model": "bge-m3", "task": "token_classify", "input": [[0, 10, 11, 2]]}


def test_tokenizes_like_flagembedding_encode(http):
    http.cfg.EMBEDDING_MAX_LENGTH = 4
    _, sparse = embed(["가 나 다 라 마"])

    assert http.tok.calls == [{"truncation": True, "max_length": 4, "padding": False}]
    # 특수 토큰 포함 4개로 잘린 같은 번호가 두 서버에 간다 — sparse 에는 잘린 앞부분 토큰만 남는다
    assert [body["input"] for _, body in http.servers.requests] == [[[0, 10, 11, 2]], [[0, 10, 11, 2]]]
    assert sparse == [{10: 0.1, 11: 0.2}]


def test_sparse_drops_special_unk_and_non_positive_and_keeps_max_per_token(http):
    weights = {10: [0.9, 0.5], 11: [-0.2], 3: [0.8]}   # 토큰 10 은 두 번(앞이 큼 — 뒤 값으로 덮으면 틀린다), 11 은 음수, 3 은 unk
    seen: dict[int, int] = {}

    def weight(token_id, pos):
        n = seen.get(token_id, 0)
        seen[token_id] = n + 1
        return weights[token_id][n]
    http.servers.weight = weight

    _, sparse = embed(["가 나 ? 가"])   # [0, 10, 11, 3, 10, 2]

    assert sparse == [{10: 0.9}]


def test_sparse_rules_match_flagembedding_encode(http):
    """설치된 FlagEmbedding 의 encode(return_sparse) 가 낸 lexical_weights 와 같은 결과 — 서버는 앞뒤(BOS·EOS) 자리를
    빼고 준다. 1.2.11 의 가중치 정리(_process_token_weights)는 encode 안의 지역 함수라, 모델·토크나이저만 대역으로 바꿔
    encode 를 그대로 부른다. FlagEmbedding 이 규칙을 바꾸면 여기서 드러난다."""
    torch = pytest.importorskip("torch")
    flag = pytest.importorskip("FlagEmbedding")
    ids = [0, 10, 11, 10, 3, 12, 1, 11, 2]   # 반복·unk·pad 가 섞인 입력
    full = [0.7, 0.6, 0.0, 0.2, 0.9, -0.1, 0.4, 0.3, 0.5]   # 위치별 가중치(앞뒤 포함) — 토큰 10 은 앞이 크다

    class _Batch(dict):
        def to(self, device):
            return self

    class _TorchTok:
        cls_token_id, pad_token_id, eos_token_id, unk_token_id = 0, 1, 2, 3

        def __call__(self, sentences, **kw):
            return _Batch(input_ids=torch.tensor([ids]), attention_mask=torch.ones(1, len(ids), dtype=torch.long))

    class _Model:
        def eval(self):
            return self

        def __call__(self, batch, **kw):
            return {"sparse_vecs": torch.tensor([full]).unsqueeze(-1)}

    model = object.__new__(flag.BGEM3FlagModel)
    model.num_gpus, model.device, model.tokenizer, model.model = 1, "cpu", _TorchTok(), _Model()
    expected = model.encode(["x"], return_dense=False, return_sparse=True)["lexical_weights"][0]

    got = embedder._sparse_weights(full[1:-1], ids, embedder._unused_token_ids())

    assert expected   # 대역이 엇나가 빈 결과끼리 같아지는 것을 막는다
    assert got == {int(k): pytest.approx(float(v)) for k, v in expected.items()}


def test_sparse_accepts_nested_weight_lists(http):
    http.servers.nested = True
    _, sparse = embed(["가 나"])
    assert sparse == [{10: 0.1, 11: 0.2}]


def test_sparse_weight_count_mismatch_stops_instead_of_misaligning(http):
    with pytest.raises(RuntimeError, match="sparse 가중치 수"):
        embedder._sparse_weights([0.1], [0, 10, 11, 2], frozenset({0, 1, 2, 3}))


def test_batches_by_embedding_batch_size(http):
    http.cfg.EMBEDDING_BATCH_SIZE = 2
    dense, sparse = embed(["가", "나", "다", "라", "마"])

    assert len(dense) == len(sparse) == 5
    assert [len(body["input"]) for _, body in http.servers.requests] == [2, 2, 2, 2, 1, 1]
    assert http.servers.urls() == [f"{DENSE}/v1/embeddings", f"{SPARSE}/pooling"] * 3
    assert [d[1] for d in dense] == [10.0, 11.0, 12.0, 13.0, 14.0]
    assert sparse == [{10: 0.1}, {11: 0.1}, {12: 0.1}, {13: 0.1}, {14: 0.1}]   # 묶음을 넘어서도 제 입력과 짝


def test_need_sparse_false_skips_sparse_server(http):
    dense, sparse = embed(["가", "나"], need_sparse=False)

    assert http.servers.urls() == [f"{DENSE}/v1/embeddings"]
    assert len(dense) == 2 and sparse == [{}, {}]


def test_empty_input_makes_no_request(http):
    assert embedder.embed_texts([]) == ([], [])
    assert http.servers.requests == []


@pytest.mark.parametrize("error, attempts", [
    (httpx.ConnectError("refused"), 3),            # 빨리 끝나는 오류 — 두 번 더 보낸다
    (httpx.RemoteProtocolError("closed"), 3),      # 서버가 막 닫은 재사용 연결
    (httpx.ConnectTimeout("connect"), 3),
    (httpx.ReadTimeout("slow"), 1),                # 읽기 시간 초과는 다시 보내지 않는다 — 질의가 오래 묶이지 않게
])
def test_transport_errors_become_search_outage(http, error, attempts):
    from core.errors import is_search_outage

    http.servers.fail = error
    with pytest.raises(embedder.EmbeddingUnavailable) as caught:
        embed(["가"])
    assert isinstance(caught.value, ConnectionError) and isinstance(caught.value, OSError)
    assert is_search_outage(caught.value)
    assert http.servers.urls() == [f"{DENSE}/v1/embeddings"] * attempts


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_server_busy_or_down_responses_become_search_outage(http, status):
    from core.errors import is_search_outage

    http.servers.status = status
    with pytest.raises(embedder.EmbeddingUnavailable) as caught:
        embed(["가"])
    assert is_search_outage(caught.value)
    assert len(http.servers.requests) == 3   # 두 번 더 보낸 뒤 포기한다


@pytest.mark.parametrize("hiccup", [503, 429, httpx.ConnectError("refused"), httpx.RemoteProtocolError("closed")])
def test_a_passing_hiccup_is_retried_and_recovers(http, hiccup):
    http.servers.queue = [hiccup]   # dense 첫 요청만 실패
    dense, sparse = embed(["가 나"])

    assert dense == [[4.0, 10.0]] and sparse == [{10: 0.1, 11: 0.2}]
    assert http.servers.urls() == [f"{DENSE}/v1/embeddings", f"{DENSE}/v1/embeddings", f"{SPARSE}/pooling"]


def test_retries_wait_between_attempts(http, monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(embedder, "_RETRY_DELAYS", (0.5, 2.0))
    monkeypatch.setattr(embedder.time, "sleep", slept.append)
    http.servers.fail = httpx.ConnectError("refused")
    with pytest.raises(embedder.EmbeddingUnavailable):
        embed(["가"])
    assert slept == [0.5, 2.0]


@pytest.mark.parametrize("status, body", [(400, "too long"), (404, "model not found")])
def test_rejected_requests_are_errors_not_outages(http, status, body):
    from core.errors import is_search_outage

    http.servers.status, http.servers.body = status, body
    with pytest.raises(RuntimeError, match=body) as caught:
        embed(["가"])
    assert not isinstance(caught.value, ConnectionError)
    assert not is_search_outage(caught.value)
    assert len(http.servers.requests) == 1   # 다시 보내도 같은 답이라 재시도하지 않는다


def test_unexpected_response_shape_is_an_error(http):
    http.servers.body = "<html>gateway</html>"
    with pytest.raises(RuntimeError, match="형식"):
        embed(["가"])


def test_local_backend_is_default_and_unchanged(monkeypatch):
    monkeypatch.delenv("EMBEDDING_BACKEND", raising=False)
    assert Settings(_env_file=None).EMBEDDING_BACKEND == "local"

    monkeypatch.setattr(get_settings(), "EMBEDDING_BACKEND", "local")
    monkeypatch.setattr(embedder, "_http_client", lambda: pytest.fail("local 갈래에서 공용 서버를 부르면 안 된다"))
    monkeypatch.setattr(embedder, "_embed_local", lambda texts: ([[1.0] for _ in texts], [{"5": 0.5} for _ in texts]))

    assert embedder.embed_texts(["가"], need_sparse=False) == ([[1.0]], [{"5": 0.5}])


def test_backend_accepts_only_local_or_http(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BACKEND", "gpu")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_warmup_http_does_not_block_startup_when_server_is_down(http, caplog):
    http.servers.fail = httpx.ConnectError("refused")
    embedder.warmup()   # 던지지 않는다
    assert "공용 임베딩 서버 확인 실패" in caplog.text


def test_warmup_local_still_fails_loudly(monkeypatch):
    monkeypatch.setattr(get_settings(), "EMBEDDING_BACKEND", "local")

    def boom(texts):
        raise RuntimeError("CUDA out of memory")
    monkeypatch.setattr(embedder, "_embed_local", boom)
    with pytest.raises(RuntimeError, match="CUDA"):
        embedder.warmup()


def test_common_env_declares_embedding_backend_keys_with_config_defaults(monkeypatch):
    """Portainer 는 compose 에 ${KEY:-기본값} 선언이 없는 스택 env 를 무시한다 — 되돌리기 스위치가 먹으려면 선언이 있어야 한다."""
    keys = ("EMBEDDING_BACKEND", "EMBEDDING_DENSE_URL", "EMBEDDING_SPARSE_URL", "EMBEDDING_SERVED_MODEL",
            "EMBEDDING_HTTP_CONNECT_TIMEOUT", "EMBEDDING_HTTP_TIMEOUT")
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    defaults = Settings(_env_file=None)
    env = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["x-common-env"]
    for key in keys:
        m = re.fullmatch(r"\$\{" + key + r":-(.*)\}", str(env.get(key)))
        assert m, f"{key}: x-common-env 에 ${{{key}:-기본값}} 으로 선언해야 한다"
        assert m.group(1) == str(getattr(defaults, key))


def test_offload_embed_waits_in_a_thread_for_the_shared_server(http):
    """http 갈래 — 공용 서버를 기다리는 동안 이벤트 루프를 잡지 않는다(다른 요청·DeepRead ping 이 돈다)."""
    seen: list[int] = []

    def fake_embed(texts, is_query=False, **kw):
        seen.append(threading.get_ident())
        return [[0.0]], [{}]

    async def run():
        return await embedder.offload_embed(fake_embed, ["가"], is_query=True), threading.get_ident()

    result, loop_thread = asyncio.run(run())
    assert result == ([[0.0]], [{}])
    assert seen and seen[0] != loop_thread


def test_offload_embed_stays_on_the_loop_for_local(monkeypatch):
    """local 갈래 — FlagEmbedding 의 빠른 토크나이저는 여러 스레드가 같이 쓰면 깨져 예전처럼 루프에서 부른다."""
    monkeypatch.setattr(get_settings(), "EMBEDDING_BACKEND", "local")
    seen: list[int] = []

    def fake_embed(texts, is_query=False, **kw):
        seen.append(threading.get_ident())
        return [[0.0]], [{}]

    async def run():
        await embedder.offload_embed(fake_embed, ["가"])
        return threading.get_ident()

    loop_thread = asyncio.run(run())
    assert seen == [loop_thread]


def embed(texts, **kw):
    return embedder.embed_texts(texts, **kw)
