"""test_search_reranker_dtype.py — 리랭커 정밀도는 장치를 따른다.

딥리서치 탐색은 GPU 예약이 없는 워커에서도 리랭커를 부른다. fp16 을 고정해 두면
CPU 에서 반정밀도로 올라간다. torch·transformers 는 늘 대역으로 꽂는다 —
장치 분기만 보면 되고, 실물이 있는 환경에서도 결과가 같아야 한다.
"""
import importlib
import sys
import types
from collections.abc import Callable, Iterator
from unittest.mock import MagicMock

import pytest

_MODULE = "services.search.reranker"


def _reranker_loader(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., tuple]]:
    def _load(*, cuda: bool) -> tuple:
        torch = MagicMock()
        torch.cuda.is_available.return_value = cuda
        monkeypatch.setitem(sys.modules, "torch", torch)
        monkeypatch.setitem(sys.modules, "transformers", MagicMock())
        # 원래 있던 부모 속성은 monkeypatch 가 되돌리게 맡긴다. 새 import 가 덮어쓰고,
        # 되살아난 sys.modules 항목은 다시 import 해도 속성을 되달지 않는다
        # (test_search_chunk_answer_flag.py 로더 주석).
        if hasattr(sys.modules.get("services.search"), "reranker"):
            monkeypatch.delattr(sys.modules["services.search"], "reranker")
        monkeypatch.delitem(sys.modules, _MODULE, raising=False)
        reranker = importlib.import_module(_MODULE)
        reranker._load_model()
        return reranker, torch

    yield _load
    # 여기서 import 한 리랭커는 대역 torch 에 묶여 있다. monkeypatch 는 원래 있던
    # 항목만 되돌리고 새로 생긴 키는 남겨 두므로 직접 뺀다.
    if _MODULE in sys.modules:
        module = sys.modules.pop(_MODULE)
        parent = sys.modules.get("services.search")
        if getattr(parent, "reranker", None) is module:
            delattr(parent, "reranker")


@pytest.fixture
def load_reranker(monkeypatch):
    yield from _reranker_loader(monkeypatch)


def test_loader_restores_a_reranker_that_was_already_loaded():
    original = types.ModuleType(_MODULE)
    with pytest.MonkeyPatch.context() as outer:
        outer.setitem(sys.modules, _MODULE, original)
        outer.setattr(importlib.import_module("services.search"), "reranker", original,
                      raising=False)
        with pytest.MonkeyPatch.context() as mp:
            loader = _reranker_loader(mp)
            next(loader)(cuda=False)
            next(loader, None)
        assert sys.modules[_MODULE] is original
        assert getattr(sys.modules["services.search"], "reranker", None) is original


def _loaded_dtype(reranker):
    return reranker.AutoModelForSequenceClassification.from_pretrained.call_args.kwargs["torch_dtype"]


def test_cpu_loads_float32(load_reranker):
    reranker, torch = load_reranker(cuda=False)
    assert _loaded_dtype(reranker) is torch.float32
    assert reranker._device == "cpu"


def test_gpu_keeps_float16(load_reranker):
    reranker, torch = load_reranker(cuda=True)
    assert _loaded_dtype(reranker) is torch.float16
    assert reranker._device == "cuda"
