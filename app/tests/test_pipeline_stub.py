"""test_pipeline_stub.py — 공용 import 대역(pipeline_stub.stubbed_pipeline)이 끝나면 import 전 그대로 되돌리는지.

이 대역을 쓰는 test_search_chunk_answer_flag.py·test_stream_book_reason_end.py 가 어떤 순서로 함께 돌아도 서로가
남긴 모듈(더미 torch·pymilvus 에 묶인 채)을 물려받지 않아야 한다.
"""
import importlib
import sys
import types

import pytest

from pipeline_stub import CACHED, stubbed_pipeline


def test_loader_leaves_sys_modules_as_it_found_them():
    snapshot = {name: sys.modules.get(name) for name in CACHED}
    with pytest.MonkeyPatch.context() as mp:
        loader = stubbed_pipeline(mp)
        next(loader)
        next(loader, None)
    assert {name: sys.modules.get(name) for name in CACHED} == snapshot


def test_loader_restores_parent_attributes_of_modules_already_loaded():
    """앞 테스트가 올려 둔 모듈이면 끝난 뒤 부모 패키지 속성도 그 모듈이어야 한다.

    sys.modules 만 되돌리면 부모 속성이 지워진 채 남는다. 문자열 경로
    monkeypatch("services.ingestion.indexer.x")는 부모 속성을 따라가므로 뒤 테스트가
    AttributeError 로 죽는다 — sys.modules 에 있는 모듈은 다시 import 해도 속성을
    되달지 않는다.
    """
    originals = {name: types.ModuleType(name) for name in CACHED}
    with pytest.MonkeyPatch.context() as outer:
        for name, module in originals.items():
            parent, _, child = name.rpartition(".")
            outer.setitem(sys.modules, name, module)
            outer.setattr(importlib.import_module(parent), child, module, raising=False)
        with pytest.MonkeyPatch.context() as mp:
            loader = stubbed_pipeline(mp)
            next(loader)
            next(loader, None)
        for name, module in originals.items():
            parent, _, child = name.rpartition(".")
            assert sys.modules[name] is module
            assert getattr(sys.modules[parent], child, None) is module, name
