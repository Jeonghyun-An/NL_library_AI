"""pipeline_stub.py — services.search.pipeline 을 부르는 테스트가 함께 쓰는 import 대역.

pipeline 은 reranker(torch)·indexer(pymilvus) 를 물고 오므로, 미설치 환경에서만 더미를 꽂아 새로 import 하고 끝나면
import 전 그대로 되돌린다(test_embed_index_guard.py 와 같은 방식). 쓰는 곳: test_search_chunk_answer_flag.py·
test_stream_book_reason_end.py. 되돌림 자체는 test_pipeline_stub.py 가 본다.

테스트 파일에서는 픽스처를 이름 그대로 가져온다 — `from pipeline_stub import pipeline` 이면 pytest 가 그 모듈의
픽스처로 등록한다.
"""
import importlib
import sys
from unittest.mock import MagicMock

import pytest

HEAVY = ("torch", "transformers", "FlagEmbedding", "pymilvus")
CACHED = ("services.search.pipeline", "services.search.reranker",
          "services.ingestion.embedder", "services.ingestion.indexer")


def stubbed_pipeline(monkeypatch):
    """더미 위에서 pipeline 을 새로 import 해 넘기고, 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 앞 테스트가 남긴 모듈을 물려받지 않게 해 줄 뿐이다.
    원래 없던 키는 되돌릴 목록에 오르지 않아서, 여기서 새로 import 한 모듈(더미
    torch·pymilvus 에 묶인 채)은 teardown 뒤에도 남고 뒤에 도는 테스트가 그것을
    물려받는다. 그래서 직접 빼고, 원래 있던 항목은 monkeypatch 가 되돌리게 둔다.

    부모 패키지 속성도 같은 규칙이다. 문자열 경로 monkeypatch 는 sys.modules 보다
    부모 속성을 먼저 따라가므로, 새 모듈을 가리키는 속성은 지우고 원래 있던 속성은
    import 전에 monkeypatch 에 맡겨 되돌리게 한다 — 새 import 가 그 속성을 덮어쓰고,
    되살아난 sys.modules 항목은 다시 import 해도 속성을 되달지 않는다.
    """
    for name in HEAVY:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    for name in CACHED:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield importlib.import_module("services.search.pipeline")
    for name in CACHED:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)


@pytest.fixture
def pipeline(monkeypatch):
    yield from stubbed_pipeline(monkeypatch)
