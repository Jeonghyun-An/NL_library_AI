"""논문 보강을 요약 단계로 옮긴 흐름 — run_summarize·run_embed_index·헬퍼 단위 테스트.

요약 단계가 섹션 요약과 같은 루프·같은 세마포어로 enrich_paper 를 돌려 아티팩트와 DB 에
남기고, embed 단계는 그 아티팩트로 보강 청크만 만든다(없거나 다른 실행의 것이면 직접 보강).
아티팩트에는 만든 체인의 run_token 이 붙는다. DB·MinIO·LLM 은 전부 대역이다.
"""
import asyncio
import gzip
import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from models.book import Book
from services.ingestion import paper_enricher, stages, summarizer
from services.ingestion.paper_enricher import FigureChunk, PaperEnrichment, TableChunk
from services.ingestion.stages import StageContext, StageError

ARTIFACT_TEXT = "추출 본문 문장이다. " * 40
_REAL_ENRICH_PAPER = paper_enricher.enrich_paper   # 대역으로 바꾸기 전의 진짜 함수


def _enrichment() -> PaperEnrichment:
    return PaperEnrichment(
        abstract="초록 본문",
        keywords=["가", "나"],
        references=["r1", "r2", "r3"],
        table_chunks=[TableChunk(context="맥락", table_md="| a | b |", description="설명.")],
    )


def _session(book, section_rows=()):
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = book
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = list(section_rows)
    return session


# ── run_summarize ────────────────────────────────────────────


def _patch_summarize(monkeypatch, *, doc_type="paper", n_sections=3, artifact=ARTIFACT_TEXT, enrich=None,
                     summary=None):
    """요약 단계 대역 — 섹션 n 개(summary: 이미 저장된 섹션 요약, 기본 없음), 추출 아티팩트, 보강 삭제·저장 기록."""
    rows = [SimpleNamespace(section_idx=i, full_text=f"섹션 {i} 본문", summary=summary) for i in range(n_sections)]
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: _session(SimpleNamespace(title="논문 제목", doc_type=doc_type), rows))
    monkeypatch.setattr(stages, "minio_client", lambda: "MINIO")
    monkeypatch.setattr(stages.cfg, "PAPER_ENRICH_ENABLED", True)

    rec = SimpleNamespace(loaded=[], enrich_calls=[], saved=[], persisted=[], sections=[], events=[])

    def fake_load(book_id, client):
        rec.loaded.append(book_id)
        if artifact is None:
            raise StageError("artifact_missing", "아티팩트 없음")
        return artifact

    def no_page_map_loader(book_id, client):
        pytest.fail("요약 단계는 쪽 위치가 필요 없다 — page_map 을 만드는 load_extraction_artifact 를 부르면 안 된다")

    async def fake_section(title, text, doc_type="book"):
        rec.sections.append(text)
        return "요약", ["테마"]

    async def fake_enrich(book_id, title, full_text, minio_client, *, sem=None):
        rec.events.append("enrich")
        rec.enrich_calls.append((book_id, title, full_text, minio_client, sem))
        if isinstance(enrich, Exception):
            raise enrich
        return enrich or _enrichment()

    def fake_save(book_id, e, client, *, run_token=None):
        rec.saved.append((book_id, e, client, run_token))

    monkeypatch.setattr(stages, "load_extraction_text", fake_load)
    monkeypatch.setattr(stages, "load_extraction_artifact", no_page_map_loader)
    monkeypatch.setattr(summarizer, "summarize_section", fake_section)
    monkeypatch.setattr(paper_enricher, "enrich_paper", fake_enrich)
    monkeypatch.setattr(paper_enricher, "delete_enrichment_artifact",
                        lambda book_id, client: rec.events.append("delete"))
    monkeypatch.setattr(paper_enricher, "save_enrichment_artifact", fake_save)
    monkeypatch.setattr(stages, "_persist_enrichment", lambda book_id, e: rec.persisted.append((book_id, e)))
    return rec


def test_summarize_paper_enriches_from_extraction_text_and_stores_result(monkeypatch):
    enrichment = _enrichment()
    rec = _patch_summarize(monkeypatch, enrich=enrichment)

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.events == ["delete", "enrich"]           # 옛 아티팩트를 먼저 지운다
    book_id, title, full_text, client, sem = rec.enrich_calls[0]
    assert (book_id, title, full_text, client) == ("KCI_1", "논문 제목", ARTIFACT_TEXT, "MINIO")
    assert isinstance(sem, asyncio.Semaphore)
    assert rec.saved == [("KCI_1", enrichment, "MINIO", "T1")]   # 이번 실행 토큰을 붙여 저장
    assert rec.persisted == [("KCI_1", enrichment)]
    assert result["sections_summarized"] == 3
    assert {k: result[k] for k in ("enriched", "has_abstract", "n_keywords", "n_references",
                                   "n_tables", "n_figures", "n_toc")} == {
        "enriched": True, "has_abstract": True, "n_keywords": 2, "n_references": 3,
        "n_tables": 1, "n_figures": 0, "n_toc": 0,
    }


def test_summarize_paper_without_extraction_artifact_leaves_enrichment_to_embed(monkeypatch):
    rec = _patch_summarize(monkeypatch, artifact=None)

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.loaded == ["KCI_1"]
    assert rec.events == ["delete"]                     # 옛 보강은 남기지 않는다
    assert rec.enrich_calls == [] and rec.saved == [] and rec.persisted == []
    assert "enriched" not in result
    assert result["sections_summarized"] == 3


def test_summarize_non_paper_does_not_touch_enrichment(monkeypatch):
    rec = _patch_summarize(monkeypatch, doc_type="book")

    result = stages.run_summarize(StageContext(book_id="WS_1", item_meta={"run_token": "T1"}))

    assert rec.loaded == [] and rec.events == []
    assert "enriched" not in result


def test_summarize_enrichment_failure_keeps_section_summaries(monkeypatch):
    """보강이 실패하면 옛 아티팩트는 이미 지워졌고 새로 쓰지 않는다 — embed 가 다시 만든다."""
    rec = _patch_summarize(monkeypatch, enrich=RuntimeError("표 파싱 폭주"))

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert result["sections_summarized"] == 3
    assert result["enriched"] is False and "표 파싱 폭주" in result["enrich_error"]
    assert rec.events == ["delete", "enrich"]
    assert rec.saved == [] and rec.persisted == []


def test_enrichment_coverage_overwrites_a_stale_enrich_error():
    """요약 단계의 보강이 실패해 meta 에 남은 enrich_error 를, 이어서 성공한 단계의 커버리지가 지운다.

    잡 레이어는 단계 결과를 item.meta 에 병합하고 None 값도 그대로 기록하므로(키를 빼지 않는다),
    커버리지가 enrich_error=None 을 싣지 않으면 embed 가 인라인 보강에 성공해도 옛 사유가 남는다.
    """
    stale_meta = {"enriched": False, "enrich_error": "표 파싱 폭주"}

    merged = {**stale_meta, **stages._enrichment_coverage(_enrichment())}

    assert merged["enriched"] is True
    assert merged["enrich_error"] is None


def test_retry_with_every_section_summarized_still_enriches_with_the_run_token(monkeypatch):
    """재시도에서 섹션 요약이 모두 남아 있으면(resume_summaries 기본) 섹션 요약 호출은 없다. 그래도 논문 보강은
    돌아 이번 실행 토큰으로 아티팩트를 남긴다 — 앞 시도가 옛 보강을 지웠으므로, 건너뛰면 embed 가 보강을
    다시 만들거나(인라인) 보강 없이 색인한다."""
    enrichment = _enrichment()
    rec = _patch_summarize(monkeypatch, enrich=enrichment, summary="앞 시도의 섹션 요약")

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T2"}))

    assert rec.sections == []                                   # 이미 요약된 섹션은 다시 부르지 않는다
    assert rec.events == ["delete", "enrich"]
    assert isinstance(rec.enrich_calls[0][4], asyncio.Semaphore)
    assert rec.saved == [("KCI_1", enrichment, "MINIO", "T2")]   # 이번 실행 토큰을 붙여 저장
    assert rec.persisted == [("KCI_1", enrichment)]
    assert (result["sections_total"], result["sections_summarized"], result["sections_failed"]) == (3, 0, 0)
    assert result["enriched"] is True and result["enrich_error"] is None


def test_summarize_without_run_token_saves_none(monkeypatch):
    """단건 흐름(process_book_file)은 item_meta 가 비어 있다 — 토큰 없이 저장한다."""
    rec = _patch_summarize(monkeypatch)

    stages.run_summarize(StageContext(book_id="KCI_1"))

    assert [s[3] for s in rec.saved] == [None]


def test_summarize_still_retries_failed_sections_once(monkeypatch):
    rec = _patch_summarize(monkeypatch)
    failed_once: set[str] = set()

    async def flaky_section(title, text, doc_type="book"):
        rec.sections.append(text)
        if text == "섹션 1 본문" and text not in failed_once:
            failed_once.add(text)
            raise RuntimeError("일시 실패")
        return "요약", ["테마"]

    monkeypatch.setattr(summarizer, "summarize_section", flaky_section)

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert result["sections_summarized"] == 3 and result["sections_failed"] == 0
    assert rec.sections.count("섹션 1 본문") == 2


def test_section_summaries_and_enrichment_share_one_semaphore(monkeypatch):
    """섹션 요약과 표 해석이 같은 세마포어를 나눠 쓴다 — 동시 LLM 호출이 상한을 넘지 않는다."""
    rec = _patch_summarize(monkeypatch, n_sections=6)
    monkeypatch.setattr(stages.cfg, "LLM_SECTION_CONCURRENCY", 2)
    tables = "\n\n".join(
        f"표 {i} 앞 문단.\n| 집단 | 평균 |\n|---|---|\n| A | {i} |\n| B | {i + 1} |\n" for i in range(4)
    )
    monkeypatch.setattr(stages, "load_extraction_text",
                        lambda book_id, client: ARTIFACT_TEXT + "\n\n" + tables)
    gauge = SimpleNamespace(active=0, peak=0, kinds=[])

    async def hold(kind):
        gauge.kinds.append(kind)
        gauge.active += 1
        gauge.peak = max(gauge.peak, gauge.active)
        await asyncio.sleep(0.01)
        gauge.active -= 1

    async def fake_section(title, text, doc_type="book"):
        await hold("section")
        return "요약", ["테마"]

    async def fake_table(title, ctx, md):
        await hold("table")
        return "설명."

    async def fake_keywords(title, text):
        await hold("keywords")
        return ["가"]

    async def fake_references(text):
        await hold("references")
        return ["r1", "r2", "r3"]

    monkeypatch.setattr(summarizer, "summarize_section", fake_section)
    monkeypatch.setattr(paper_enricher, "enrich_paper", _REAL_ENRICH_PAPER)   # 진짜 보강 경로
    monkeypatch.setattr(paper_enricher, "interpret_table", fake_table)
    monkeypatch.setattr(paper_enricher, "generate_keywords", fake_keywords)
    monkeypatch.setattr(paper_enricher, "generate_references", fake_references)
    monkeypatch.setattr(paper_enricher, "_list_figure_keys", lambda book_id, client: [])

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert gauge.peak == 2
    assert gauge.kinds.count("section") == 6 and gauge.kinds.count("table") == 4
    assert result["n_tables"] == 4 and len(rec.saved) == 1


# ── _persist_enrichment ──────────────────────────────────────


def test_persist_enrichment_fills_only_empty_catalog_fields(monkeypatch):
    book = Book(cnts_id="KCI_1", abstract=None, keyword="기존 키워드", extra={"plot": "유지"})
    session = _session(book)
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: session)
    enrichment = PaperEnrichment(abstract="보강 초록", keywords=["가", "나"],
                                 toc=["1. 서론", "2. 방법", "3. 결론"], references=["r1"])

    stages._persist_enrichment("KCI_1", enrichment)

    assert book.abstract == "보강 초록"
    assert book.keyword == "기존 키워드"            # 이미 있으면 덮지 않는다
    assert book.extra == {"plot": "유지", "references": ["r1"],
                          "toc": ["1. 서론", "2. 방법", "3. 결론"], "keywords": ["가", "나"]}
    session.commit.assert_called_once()
    session.close.assert_called_once()


def test_persist_enrichment_skips_db_when_nothing_to_store(monkeypatch):
    opened = []
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: opened.append(True) or MagicMock())

    stages._persist_enrichment("KCI_1", PaperEnrichment())

    assert opened == []


# ── _build_enriched_chunks ───────────────────────────────────


def test_build_enriched_chunks_keeps_order_text_and_indices():
    enrichment = PaperEnrichment(
        abstract="초록 본문",
        keywords=["가", "나"],
        table_chunks=[TableChunk(context="맥락", table_md="| a | b |", description="설명."),
                      TableChunk(context="", table_md="| c | d |", description="")],
        figure_chunks=[FigureChunk(minio_key="figures/X/p1_i0.jpg", description="그림.")],
    )

    chunks = stages._build_enriched_chunks(enrichment, base_idx=5)

    assert [(c.chunk_idx, c.text) for c in chunks] == [
        (5, "[초록] 초록 본문"),
        (6, "[키워드] 가, 나"),
        (7, "[표]\n맥락\n\n| a | b |"),
        (8, "[표 설명] 설명."),
        (9, "[표]\n| c | d |"),
        (10, "[그림 설명] 그림."),
    ]
    assert all(c.section_idx is None for c in chunks)


def test_build_enriched_chunks_caps_table_bytes(monkeypatch):
    monkeypatch.setattr(stages.cfg, "MAX_CHUNK_BYTES", 20)
    enrichment = PaperEnrichment(table_chunks=[TableChunk(context="", table_md="| 가나다라마바사 |")])

    (chunk,) = stages._build_enriched_chunks(enrichment, base_idx=0)

    assert len(chunk.text.encode("utf-8")) <= 20


# ── run_embed_index 의 보강 블록 ──────────────────────────────

ENRICH_KEY = "artifacts/KCI_1/enrichment.json.gz"


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def close(self):
        pass

    def release_conn(self):
        pass


class _NoSuchKey(Exception):
    code = "NoSuchKey"     # minio S3Error 와 같은 속성


class _FakeMinio:
    """보강 아티팩트만 담는 MinIO 대역 — 진짜 save/load_enrichment_artifact 가 이걸 쓴다."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, bucket, key, data, length, content_type=None):
        self.objects[key] = data.read()

    def get_object(self, bucket, key):
        if key not in self.objects:
            raise _NoSuchKey(key)
        return _FakeResp(self.objects[key])


def _stored(enrichment: PaperEnrichment, run_token: str | None) -> bytes:
    """진짜 save_enrichment_artifact 가 쓰는 바이트 그대로."""
    client = _FakeMinio()
    paper_enricher.save_enrichment_artifact("KCI_1", enrichment, client, run_token=run_token)
    return client.objects[ENRICH_KEY]


def _stub_missing_module(monkeypatch, name: str, cache_clear: tuple[str, ...] = ()) -> None:
    """설치 안 된 모듈만 더미로 꽂는다(test_embed_index_guard.py 와 같은 기법)."""
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, MagicMock())
        for mod in cache_clear:
            monkeypatch.delitem(sys.modules, mod, raising=False)


def _patch_embed(monkeypatch, *, stored: bytes | None, doc_type: str = "paper"):
    """embed 단계 대역 — 추출 본문 있음, 기본은 논문, MinIO 에 보강 아티팩트 stored(없으면 None)."""
    _stub_missing_module(monkeypatch, "pymilvus", cache_clear=("services.ingestion.indexer",))
    _stub_missing_module(monkeypatch, "FlagEmbedding", cache_clear=("services.ingestion.embedder",))
    import services.ingestion.chunker as chunker_mod
    import services.ingestion.embedder as embedder_mod
    import services.ingestion.indexer as indexer_mod

    book = MagicMock(doc_type=doc_type, abstract="카탈로그 초록", title="논문 제목",
                     personal_author=None, corporate_author=None, series_title=None,
                     subject=None, keyword=None)
    minio = _FakeMinio()
    if stored is not None:
        minio.objects[ENRICH_KEY] = stored
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: _session(book))
    monkeypatch.setattr(stages, "minio_client", lambda: minio)
    monkeypatch.setattr(stages, "load_extraction_artifact", lambda book_id, client: (ARTIFACT_TEXT, {}))
    monkeypatch.setattr(stages.cfg, "PAPER_ENRICH_ENABLED", True)
    monkeypatch.setattr(chunker_mod, "semantic_chunk",
                        lambda text, embed_fn, **kw: [chunker_mod.Chunk(chunk_idx=0, text=text, section_idx=None)])
    monkeypatch.setattr(embedder_mod, "embed_texts",
                        lambda texts, *a, **kw: ([[0.0] for _ in texts], [{} for _ in texts]))

    rec = SimpleNamespace(indexed=None, enrich_calls=[], persisted=[], minio=minio)

    def fake_index(book_id, chunks, dense, sparse, scalar_meta=None):
        rec.indexed = chunks
        return MagicMock(errors=[], chunks_indexed=len(chunks))

    async def fake_enrich(book_id, title, full_text, minio_client, *, sem=None):
        rec.enrich_calls.append(full_text)
        return PaperEnrichment(abstract="인라인 초록")

    monkeypatch.setattr(indexer_mod, "index_chunks", fake_index)
    monkeypatch.setattr(paper_enricher, "enrich_paper", fake_enrich)
    monkeypatch.setattr(stages, "_persist_enrichment", lambda book_id, e: rec.persisted.append(e))
    return rec


def test_embed_uses_artifact_written_by_this_run(monkeypatch):
    rec = _patch_embed(monkeypatch, stored=_stored(_enrichment(), run_token="T1"))

    result = stages.run_embed_index(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.enrich_calls == [] and rec.persisted == []
    texts = [c.text for c in rec.indexed]
    assert "[초록] 초록 본문" in texts and "[표 설명] 설명." in texts
    assert result["enriched"] is True and result["n_tables"] == 1
    assert result["enrich_source"] == "artifact"


def test_embed_rebuilds_inline_when_artifact_is_from_another_run(monkeypatch):
    rec = _patch_embed(monkeypatch, stored=_stored(_enrichment(), run_token="T0"))

    result = stages.run_embed_index(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert result["enrich_source"] == "inline"
    assert rec.enrich_calls == [ARTIFACT_TEXT] and len(rec.persisted) == 1
    texts = [c.text for c in rec.indexed]
    assert "[초록] 인라인 초록" in texts and "[초록] 초록 본문" not in texts
    # 새로 만든 보강을 이번 실행 토큰으로 덮어 저장했다
    assert paper_enricher.load_enrichment_artifact("KCI_1", rec.minio, run_token="T1") == \
        PaperEnrichment(abstract="인라인 초록")


def test_embed_uses_pre_deploy_artifact_without_token(monkeypatch):
    """배포 전 embed 가 남긴 아티팩트(run_token 키 없음)는 그대로 쓴다 — 배포 전 체크포인트 호환."""
    old = {"abstract": "배포 전 초록", "keywords": [], "toc": [], "references": [],
           "table_chunks": [], "figure_chunks": []}
    rec = _patch_embed(monkeypatch, stored=gzip.compress(json.dumps(old, ensure_ascii=False).encode("utf-8")))

    result = stages.run_embed_index(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.enrich_calls == []
    assert "[초록] 배포 전 초록" in [c.text for c in rec.indexed]
    assert result["enrich_source"] == "artifact"


def test_embed_enriches_inline_when_artifact_is_missing(monkeypatch):
    rec = _patch_embed(monkeypatch, stored=None)

    result = stages.run_embed_index(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.enrich_calls == [ARTIFACT_TEXT] and len(rec.persisted) == 1
    assert "[초록] 인라인 초록" in [c.text for c in rec.indexed]
    assert result["enriched"] is True and result["has_abstract"] is True
    assert result["enrich_source"] == "inline"      # embed 칸이 보강 LLM 을 다시 기다렸다
    assert result["enrich_error"] is None           # 요약 단계가 남긴 옛 사유를 meta 병합이 지운다


def test_embed_inline_enrichment_failure_still_counts_as_inline(monkeypatch):
    """인라인 보강이 예외로 끝나도 embed 는 보강 없이 계속하고, 출처는 inline 으로 남는다(카나리 집계)."""
    rec = _patch_embed(monkeypatch, stored=None)

    async def boom(book_id, title, full_text, minio_client, *, sem=None):
        raise RuntimeError("보강 폭주")

    monkeypatch.setattr(paper_enricher, "enrich_paper", boom)

    result = stages.run_embed_index(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert result["enriched"] is False and "보강 폭주" in result["enrich_error"]
    assert result["enrich_source"] == "inline"
    assert result["indexed"] == len(rec.indexed) and not any(c.text.startswith("[초록]") for c in rec.indexed)


@pytest.mark.parametrize("doc_type, enabled", [("literature", True), ("paper", False)],
                         ids=["not-a-paper", "enrichment-disabled"])
def test_embed_enrich_source_is_none_when_not_a_paper_or_disabled(monkeypatch, doc_type, enabled):
    rec = _patch_embed(monkeypatch, stored=_stored(_enrichment(), run_token="T1"), doc_type=doc_type)
    monkeypatch.setattr(stages.cfg, "PAPER_ENRICH_ENABLED", enabled)

    result = stages.run_embed_index(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert result["enrich_source"] == "none" and "enriched" not in result
    assert rec.enrich_calls == []


# ── 추출 아티팩트 본문만 읽기 ─────────────────────────────────


def _extraction(pages: list[tuple[int, str]]):
    return SimpleNamespace(
        total_pages=len(pages), errors=[],
        pages=[SimpleNamespace(page_num=n, text=t, method="fitz", confidence=1.0) for n, t in pages],
    )


def test_load_extraction_text_returns_the_same_text_as_the_full_loader():
    client = _FakeMinio()
    stages.save_extraction_artifact("KCI_1", _extraction([(1, "첫 쪽 본문"), (2, ""), (3, "셋째 쪽 본문")]), client)

    full_text, page_map = stages.load_extraction_artifact("KCI_1", client)

    assert stages.load_extraction_text("KCI_1", client) == full_text == "첫 쪽 본문\n\n셋째 쪽 본문"
    assert page_map[0] == 1 and page_map[len("첫 쪽 본문") + 2] == 3     # 전체 로더는 그대로 page_map 을 만든다


def test_load_extraction_text_missing_artifact_is_artifact_missing():
    with pytest.raises(StageError) as exc:
        stages.load_extraction_text("KCI_1", _FakeMinio())

    assert exc.value.error_group == "artifact_missing"
