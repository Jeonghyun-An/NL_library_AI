"""test_embed_index_guard.py — 임베딩 단계 빈 본문 가드 테스트.

run_finalize 가 성공 문서의 추출 아티팩트를 지우므로, 적재 완료된 문서에서
임베딩 단계만 다시 돌리면 아티팩트가 없다. 이때 빈 본문으로 진행하면
index_chunks 가 book_id 기준 delete 후 insert 를 돌려 기존 청크가 전멸한다.
"""
import importlib
import sys
from unittest.mock import MagicMock

import pytest

from services.ingestion import stages
from services.ingestion.stages import StageContext, StageError


def _stub_missing_module(monkeypatch, name: str, cache_clear: tuple[str, ...] = ()) -> None:
    """설치 안 된 모듈만 더미로 꽂는다 — 실제 설치된 환경에서는 건드리지 않는다.

    더미를 꽂은 경우에만 cache_clear 로 지정한 우리 쪽 모듈도 sys.modules 에서
    비운다 — monkeypatch 는 이 모듈 항목 자체만 원복하고, 이미 캐시된
    indexer/embedder 의 전역 바인딩(예: pymilvus.Collection)은 원복하지
    않아 뒤에 도는 다른 테스트가 오염된 Mock 을 물려받을 수 있다.
    """
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, MagicMock())
        for mod in cache_clear:
            monkeypatch.delitem(sys.modules, mod, raising=False)


def _patch_common(monkeypatch, book, artifact_loader=None):
    """아티팩트 로더(기본: '아티팩트 없음' 예외) + 주어진 book 한 건을 반환하는
    DB 세션으로 고정.

    run_embed_index 는 pymilvus(indexer)·FlagEmbedding(embedder) 를 함수
    최상단에서 무조건 로컬 import 한다 — 로컬 환경엔 둘 다 미설치라
    가드 도달 전에 ModuleNotFoundError 로 죽는다. import 만 통과시키면
    되므로 미설치인 경우에만 sys.modules 에 더미를 꽂아둔다.
    """
    _stub_missing_module(monkeypatch, "pymilvus", cache_clear=("services.ingestion.indexer",))
    _stub_missing_module(monkeypatch, "FlagEmbedding", cache_clear=("services.ingestion.embedder",))

    monkeypatch.setattr(stages, "minio_client", lambda: MagicMock())

    if artifact_loader is None:
        def artifact_loader(book_id, client):
            raise StageError("artifact_missing", "아티팩트 없음")

    monkeypatch.setattr(stages, "load_extraction_artifact", artifact_loader)

    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = book
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: session)


def test_aborts_when_no_artifact_and_not_paper(monkeypatch):
    """문학 문서 + 아티팩트 없음 → 인덱스를 건드리기 전에 중단한다."""
    book = MagicMock(doc_type="literature", abstract=None, title="무정",
                     personal_author=None, corporate_author=None,
                     series_title=None, subject=None, keyword=None)
    _patch_common(monkeypatch, book)

    called = []
    monkeypatch.setattr(
        "services.ingestion.indexer.index_chunks",
        lambda *a, **kw: called.append(True),
    )

    with pytest.raises(StageError) as exc:
        stages.run_embed_index(StageContext(book_id="WS_001"))

    assert exc.value.error_group == "empty_body"
    assert called == [], "인덱스를 건드리기 전에 멈춰야 한다"


def test_aborts_when_paper_has_no_fallback_text(monkeypatch):
    """논문인데 abstract 도 제목도 없으면 폴백 텍스트를 못 만든다 → 중단."""
    book = MagicMock(doc_type="paper", abstract=None, title=None,
                     personal_author=None, corporate_author=None,
                     series_title=None, subject=None, keyword=None)
    _patch_common(monkeypatch, book)

    called = []
    monkeypatch.setattr(
        "services.ingestion.indexer.index_chunks",
        lambda *a, **kw: called.append(True),
    )

    with pytest.raises(StageError) as exc:
        stages.run_embed_index(StageContext(book_id="KCI_FI000000001"))

    assert exc.value.error_group == "empty_body"
    assert called == []


def test_aborts_when_extracted_text_is_whitespace_only(monkeypatch):
    """아티팩트는 있지만 페이지가 전부 공백(OCR 저품질) → strip 하면 빈 본문, 중단.

    load_extraction_artifact 의 페이지 필터는 truthiness 기준이라 "  \\n  " 같은
    공백뿐인 페이지도 그대로 통과시킨다 — 아티팩트 자체는 정상 로드된 경우다.
    """
    book = MagicMock(doc_type="literature", abstract=None, title="무정",
                     personal_author=None, corporate_author=None,
                     series_title=None, subject=None, keyword=None)
    _patch_common(monkeypatch, book, artifact_loader=lambda book_id, client: ("   \n\n  ", {}))

    called = []
    monkeypatch.setattr(
        "services.ingestion.indexer.index_chunks",
        lambda *a, **kw: called.append(True),
    )

    with pytest.raises(StageError) as exc:
        stages.run_embed_index(StageContext(book_id="WS_002"))

    assert exc.value.error_group == "empty_body"
    assert called == []
