"""
단계(체크포인트) 단위로 분리되어 실패 시 해당 단계부터 재개 가능:

  run_extract     : 다운로드 → 텍스트 추출 → 섹션 분할(0개면 강제 OCR 재추출 → no_text/vlm_error)
                    → 그림 저장 → PG 저장 + MinIO artifacts/{book_id}/extraction.json.gz (재개용 중간 산출물)
  run_summarize   : 섹션 요약/테마 LLM → book_sections UPDATE (doc_type 판별·영속화 포함)
                    + [paper] 보강 LLM(섹션 요약과 같은 세마포어) → enrichment.json.gz·카탈로그
  run_embed_index : 아티팩트 + 섹션 요약 로드 → 청킹 → 임베딩 → Milvus delete+insert
                    ([paper] 보강 아티팩트로 보강 청크 — 없거나 다른 실행의 것이면 여기서 보강 LLM)
  run_finalize    : 계층 요약 입력 1회 → 문서 요약/소개글(도서류는 줄거리·독후 효과도) LLM 동시 호출
                    → library_catalog UPDATE (skip_cover 파라미터 또는 논문이면 FLUX 표지 생략 —
                    썸네일은 API가 온디맨드 생성)

잡 레이어(workers/job_runtime.py)는 이 함수들의 시그니처(StageContext → dict)만 의존한다.
ingest_state 전이·락·타이밍 기록은 호출자(태스크 래퍼) 책임.
"""
import asyncio
import gzip
import io
import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.book import Book
from models.section import BookSection

if TYPE_CHECKING:   # 실행 시에는 함수 안에서 import 한다 (기존 관례)
    from services.ingestion.chunker import Chunk
    from services.ingestion.paper_enricher import PaperEnrichment

log = logging.getLogger(__name__)
cfg = get_settings()

SECTION_MIN_TOKENS = cfg.SECTION_MIN_TOKENS
SECTION_MAX_TOKENS = cfg.SECTION_MAX_TOKENS

DOWNLOAD_DIR = cfg.DOWNLOAD_DIR

# 섹션 0개 강제 OCR 재추출에 주는 데드라인의 하한(초) — 첫 추출이 INGEST_EXTRACT_DEADLINE 을 거의 다 썼어도
# 이만큼은 OCR 할 시간을 준다
FORCED_OCR_MIN_DEADLINE_SECONDS = 60


class StageError(Exception):
    """단계 실패 — error_group 분류를 동반하는 예외."""

    def __init__(self, error_group: str, message: str):
        super().__init__(message)
        self.error_group = error_group


@dataclass
class StageContext:
    """단계 간 전달 컨텍스트 — 모든 필드는 JSON 직렬화 가능 (어느 워커에서든 재수화)."""
    book_id: str
    source_key: str | None = None    # MinIO 원본 key (file_path 없으면 여기서 다운로드)
    file_path: str | None = None     # 로컬 파일 경로 (단건 흐름에서 전달)
    job_item_id: int | None = None   # 잡 아이템 (단건 흐름이면 None)
    params: dict = field(default_factory=dict)  # {"skip_cover": true, "doc_type": "paper", ...}
    # 잡 아이템 meta 사본 — 앞 단계가 남긴 값(예: 추출의 pages). 단건 흐름이면 빈 dict
    item_meta: dict = field(default_factory=dict)


# ── 공통 헬퍼 ────────────────────────────────────────────────


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def minio_client():
    from minio import Minio

    return Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )


def split_into_sections(pages: list) -> list[dict]:
    """
    페이지 텍스트를 의미 경계 기반으로 섹션 분할.

    chunker.semantic_chunk()를 SECTION_MIN_TOKENS/SECTION_MAX_TOKENS 타겟으로
    재사용한다 — 3단계(embed_index)의 검색용 청킹과 완전히 같은 의미 경계
    탐지 로직을 쓰되, 병합·분할 크기 기준만 섹션용으로 다르게 준다.
    (예전에는 페이지를 누적하다 토큰 수 넘으면 그 자리서 그냥 잘랐음 — 문장·
    논지가 한창이어도 상관없이 끊겨서, 다음 단계 요약이 반쪽 맥락만 보는 문제가 있었음.)
    """
    from services.ingestion.chunker import semantic_chunk
    from services.ingestion.embedder import embed_texts

    texts = [p.text for p in pages if p.text]
    if not texts:
        return []

    full_text = "\n\n".join(texts)

    # 문자 위치 → 페이지 번호 매핑 (load_extraction_artifact와 동일 방식)
    page_map: dict[int, int] = {}
    cursor = 0
    for p in pages:
        if not p.text:
            continue
        for i in range(len(p.text)):
            page_map[cursor + i] = p.page_num
        cursor += len(p.text) + 2  # "\n\n" 구분자

    def _embed_fn(sentences: list[str]) -> list[list[float]]:
        dense, _ = embed_texts(sentences)
        return dense

    chunks = semantic_chunk(
        full_text, _embed_fn, page_map=page_map,
        min_tokens=SECTION_MIN_TOKENS,
        max_tokens=SECTION_MAX_TOKENS,
        apply_byte_guard=False,  # PostgreSQL TEXT 컬럼 — Milvus VARCHAR 바이트 한도 무관
    )

    return [
        {
            "section_idx": c.chunk_idx,
            "text": c.text,
            "page_start": c.page_start if c.page_start is not None else 0,
            "page_end": c.page_end if c.page_end is not None else 0,
            "token_count": c.token_count,
        }
        for c in chunks
    ]


def assign_section_idx(chunks, sections) -> None:
    """각 청크에 소속 섹션 인덱스를 매핑 (누적 문자 위치 기준)."""
    if not sections:
        return

    section_boundaries = []
    cumulative = 0
    for sec in sections:
        start = cumulative
        end = cumulative + len(sec["text"])
        section_boundaries.append((start, end, sec["section_idx"]))
        cumulative = end + 2  # "\n\n" 구분자

    chunk_pos = 0
    for chunk in chunks:
        mid_pos = chunk_pos + len(chunk.text) // 2

        matched = False
        for start, end, sec_idx in section_boundaries:
            if start <= mid_pos < end:
                chunk.section_idx = sec_idx
                matched = True
                break

        if not matched:
            chunk.section_idx = sections[-1]["section_idx"]

        chunk_pos += len(chunk.text) + 1


def save_figures(book_id: str, figures: list, client) -> int:
    """그림 바이너리 → MinIO 업로드 + PostgreSQL 메타데이터 저장."""
    from models.figure import BookFigure

    saved = 0
    db = SyncSessionLocal()
    try:
        db.query(BookFigure).filter_by(book_id=book_id).delete()
        for fig in figures:
            minio_key = f"figures/{book_id}/p{fig.page_num}_i{fig.img_idx}.jpg"
            try:
                client.put_object(
                    cfg.MINIO_BUCKET,
                    minio_key,
                    io.BytesIO(fig.img_bytes),
                    length=len(fig.img_bytes),
                    content_type="image/jpeg",
                )
            except Exception as e:
                log.warning(f"[{book_id}] 그림 MinIO 업로드 실패 {minio_key}: {e}")
                continue
            db.add(BookFigure(
                book_id=book_id,
                page_num=fig.page_num,
                img_idx=fig.img_idx,
                minio_key=minio_key,
                before_context=fig.before_context or None,
                after_context=fig.after_context or None,
            ))
            saved += 1
        db.commit()
    except Exception as e:
        db.rollback()
        log.warning(f"[{book_id}] 그림 DB 저장 실패: {e}")
    finally:
        db.close()
    return saved


# ── 추출 아티팩트 (단계 간 중간 산출물, MinIO 저장) ─────────────


def artifact_key(book_id: str) -> str:
    return f"artifacts/{book_id}/extraction.json.gz"


def save_extraction_artifact(book_id: str, extraction, client) -> str:
    data = {
        "book_id": book_id,
        "total_pages": extraction.total_pages,
        "pages": [
            {"page_num": p.page_num, "text": p.text,
             "method": p.method, "confidence": p.confidence}
            for p in extraction.pages
        ],
        "errors": extraction.errors,
    }
    raw = gzip.compress(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    key = artifact_key(book_id)
    client.put_object(
        cfg.MINIO_BUCKET, key, io.BytesIO(raw),
        length=len(raw), content_type="application/gzip",
    )
    return key


def _read_extraction_artifact(book_id: str, client) -> dict:
    """아티팩트(JSON) 원본을 읽는다. 읽지 못하면 artifact_missing."""
    try:
        resp = client.get_object(cfg.MINIO_BUCKET, artifact_key(book_id))
        raw = resp.read()
        resp.close()
        resp.release_conn()
    except Exception as e:
        raise StageError(
            "artifact_missing",
            f"추출 아티팩트 없음 ({artifact_key(book_id)}) — extract 단계부터 재실행 필요: {e}",
        ) from e
    return json.loads(gzip.decompress(raw).decode("utf-8"))


def load_extraction_text(book_id: str, client) -> str:
    """아티팩트에서 본문(full_text)만 읽는다 — 쪽 위치(page_map)가 필요 없는 호출용.

    page_map 은 글자마다 항목을 만드는 큰 dict 라, 본문만 쓰는 호출(요약 단계의 논문 보강)이
    load_extraction_artifact 를 부르면 쓰지 않을 것을 만든다.
    """
    data = _read_extraction_artifact(book_id, client)
    return "\n\n".join(p["text"] for p in data["pages"] if p["text"])


def load_extraction_artifact(book_id: str, client) -> tuple[str, dict[int, int]]:
    """아티팩트 로드 → (full_text, page_map) 재구성 (extractor와 동일 로직)."""
    data = _read_extraction_artifact(book_id, client)

    texts = [p["text"] for p in data["pages"] if p["text"]]
    full_text = "\n\n".join(texts)

    cursor = 0
    page_map: dict[int, int] = {}
    for p in data["pages"]:
        if not p["text"]:
            continue
        for i in range(len(p["text"])):
            page_map[cursor + i] = p["page_num"]
        cursor += len(p["text"]) + 2  # "\n\n"

    return full_text, page_map


def delete_artifact(book_id: str, client) -> None:
    try:
        client.remove_object(cfg.MINIO_BUCKET, artifact_key(book_id))
    except Exception:
        pass


# ── 단계 ① 추출 ──────────────────────────────────────────────


def run_extract(ctx: StageContext) -> dict:
    """다운로드 → 추출 → 섹션 분할 → 그림 저장 → 메타 보장/doc_type 판별 → 섹션 PG 저장 → 아티팩트.

    섹션 0개는 추출 성공으로 넘기지 않는다. 첫 추출에 OCR 요청 실패·데드라인이 있었으면 vlm_error(추출부터
    재시도), '원래 짧은 쪽'으로 ODL 채택한 쪽이 없으면 no_text(재시도 안 함), 있으면 그 쪽까지 OCR 하는 강제
    재추출을 첫 추출이 남긴 시간 안에서 한 번 더 하고, 그래도 0개면 같은 기준으로 vlm_error/no_text.
    """
    from services.ingestion.extractor import extract_text

    book_id = ctx.book_id
    client = minio_client()

    local_path = ctx.file_path
    downloaded = False
    if not local_path:
        if not ctx.source_key:
            raise StageError("minio_error", "source_key와 file_path가 모두 없음")
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        local_path = os.path.join(DOWNLOAD_DIR, f"{book_id}.pdf")
        try:
            client.fget_object(cfg.MINIO_BUCKET, ctx.source_key, local_path)
            downloaded = True
        except Exception as e:
            raise StageError("minio_error", f"MinIO 다운로드 실패 ({ctx.source_key}): {e}") from e

    try:
        t_first = time.monotonic()
        extraction = run_async(extract_text(local_path, book_id))
        if not extraction.pages:
            raise StageError("extract_empty", f"텍스트 추출 실패: {extraction.errors}")
        log.info(f"[{book_id}] 추출 완료: {extraction.stats}")

        sections = split_into_sections(extraction.pages)
        forced_ocr = False
        if not sections:
            # 첫 추출에서 OCR 요청이 실패했거나 데드라인에 걸렸으면 지금 강제 OCR 을 해도 같은 장애·시간 부족을
            # 되풀이한다 — 추출부터 재시도(백오프)하도록 넘긴다.
            if extraction.ocr_errors or extraction.deadline_hit:
                raise StageError(
                    "vlm_error",
                    f"섹션 0개 — OCR 오류 {extraction.ocr_errors}건·데드라인 {extraction.deadline_hit}: "
                    f"{extraction.errors[:3]}",
                )
            # 강제 OCR 이 판정을 바꾸는 것은 '원래 짧은 쪽'으로 ODL 결과를 채택한 쪽뿐이다 — 그런 쪽이 없으면
            # (스캔본처럼 짧은 쪽을 이미 다 OCR 했으면) 다시 추출해도 같으므로 바로 no_text.
            if not extraction.short_kept:
                raise StageError(
                    "no_text",
                    f"섹션 0개 — 본문 없음({extraction.total_pages}쪽, 강제 OCR 로 바뀔 쪽 없음)",
                )
            # 첫 추출이 남긴 시간만 준다 — 두 번째 추출은 ODL 변환까지 그 시간 안에서 한다(extract_text 가 ODL 상한을
            # 남은 시간으로 줄인다). 하한 60초만큼 두 추출을 합치면 INGEST_EXTRACT_DEADLINE 을 조금 넘을 수 있지만
            # stale 판정(INGEST_STAGE_TIMEOUT_EXTRACT 3600초) 아래다.
            deadline_s = max(
                cfg.INGEST_EXTRACT_DEADLINE - (time.monotonic() - t_first), FORCED_OCR_MIN_DEADLINE_SECONDS
            )
            log.warning(
                f"[{book_id}] 섹션 0개 — 원래 짧은 쪽 {extraction.short_kept}쪽까지 OCR 로 보내 다시 추출"
                f"(데드라인 {deadline_s:.0f}초)"
            )
            forced_ocr = True
            extraction = run_async(
                extract_text(local_path, book_id, force_ocr_short_pages=True, deadline_s=deadline_s)
            )
            log.info(f"[{book_id}] 강제 OCR 재추출 완료: {extraction.stats}")
            sections = split_into_sections(extraction.pages) if extraction.pages else []
            if not sections:
                if extraction.ocr_errors or extraction.deadline_hit:
                    raise StageError(
                        "vlm_error",
                        f"섹션 0개(강제 OCR) — OCR 오류 {extraction.ocr_errors}건·데드라인 "
                        f"{extraction.deadline_hit}: {extraction.errors[:3]}",
                    )
                raise StageError(
                    "no_text",
                    f"섹션 0개 — 강제 OCR 재추출로도 본문 없음({extraction.total_pages}쪽)",
                )
        log.info(f"[{book_id}] 섹션 {len(sections)}개 분할 완료")

        if extraction.figures:
            n_figs = save_figures(book_id, extraction.figures, client)
            log.info(f"[{book_id}] 그림 {n_figs}개 저장 완료")

        doc_type = _ensure_book_and_doc_type(ctx, local_path)

        db = SyncSessionLocal()
        try:
            db.query(BookSection).filter_by(book_id=book_id).delete()
            for sec in sections:
                db.add(BookSection(
                    book_id=book_id,
                    section_idx=sec["section_idx"],
                    full_text=sec["text"],
                    page_start=sec["page_start"],
                    page_end=sec["page_end"],
                    token_count=sec["token_count"],
                ))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        save_extraction_artifact(book_id, extraction, client)

        method_counts = {k: v for k, v in extraction.stats.items()
                         if k not in ("total", "errors")}
        return {
            "pages": extraction.total_pages,
            "sections": len(sections),
            "figures": len(extraction.figures),
            "extract_method": max(method_counts, key=method_counts.get) if method_counts else "",
            "doc_type": doc_type,
            "vlm_capped": extraction.vlm_capped,
            "forced_ocr": forced_ocr,
            "vlm_truncated": extraction.vlm_truncated,
            "extract_deadline_hit": extraction.deadline_hit,
            "ocr_errors": extraction.ocr_errors,
            "render_errors": extraction.render_errors,
            "odl_fallback": extraction.odl_fallback,
            "odl_seconds": round(extraction.odl_seconds, 1),
        }
    finally:
        if downloaded:
            try:
                os.remove(local_path)
            except OSError:
                pass


def _ensure_book_and_doc_type(ctx: StageContext, local_path: str) -> str:
    """카탈로그 row 보장 (없으면 PDF 메타 자동 추출) + doc_type 판별·영속화."""
    from domains import get_active_profile

    book_id = ctx.book_id
    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=book_id).first()
        if not book:
            log.info(f"[{book_id}] 메타데이터 없음 → PDF 자동 추출 시도")
            from services.ingestion.pdf_meta_extractor import extract_pdf_metadata
            meta = run_async(extract_pdf_metadata(local_path))
            book = Book(
                cnts_id=book_id,
                title=meta.get("title") or book_id,
                personal_author=meta.get("personal_author", ""),
                corporate_author=meta.get("corporate_author", ""),
                publisher=meta.get("publisher", ""),
                pub_date=meta.get("pub_date", ""),
                abstract=meta.get("abstract", ""),
                keyword=meta.get("keyword", ""),
                language=meta.get("language", ""),
                url=meta.get("url", ""),
                genre=meta.get("genre", "other"),
                source_format="PDF",
            )
            db.add(book)
            db.commit()
            db.refresh(book)
            log.info(f"[{book_id}] 메타데이터 자동 생성 완료: '{book.title}' (genre={book.genre})")

        # 우선순위: 잡 파라미터 > 기존 doc_type(KCI 로더 등이 영속화) > 프로파일 판별
        doc_type = ctx.params.get("doc_type") or book.doc_type or get_active_profile().detect_doc_type({
            "kdc": book.kdc,
            "title": book.title or book_id,
            "source_format": book.source_format,
            "genre": book.genre,
        })
        book.doc_type = doc_type
        db.commit()
        log.info(f"[{book_id}] 문서 유형: {doc_type}")
        return doc_type
    finally:
        db.close()


# ── [paper] 보강 — 요약 단계가 만들고 embed 단계가 청크로 쓴다 ──────


def _enrichment_coverage(enrichment: "PaperEnrichment") -> dict:
    """보강 커버리지 — item.meta 로 노출 (전부 0이면 PDF 추출 품질 의심).

    enrich_error 는 None 으로 싣는다 — 단계 결과는 item.meta 에 병합되고 None 값도 기록되므로,
    요약 단계의 보강이 실패해 남은 사유를 이어서 보강에 성공한 단계(embed 의 인라인 보강)가 지운다.
    """
    return {
        "enriched": True,
        "enrich_error": None,
        "has_abstract": bool(enrichment.abstract),
        "n_keywords": len(enrichment.keywords),
        "n_references": len(enrichment.references),
        "n_tables": len(enrichment.table_chunks),
        "n_figures": len(enrichment.figure_chunks),
        "n_toc": len(enrichment.toc),
    }


def _persist_enrichment(book_id: str, enrichment: "PaperEnrichment") -> None:
    """보강 결과를 카탈로그에 반영 — 초록·키워드는 비어 있을 때만 채우고 extra 에 참고문헌·목차·키워드.

    LLM 을 다 기다린 뒤에 세션을 연다(함정 18). 실패해도 경고만 — 보강이 색인을 막지 않는다.
    """
    if not (enrichment.abstract or enrichment.references or enrichment.keywords or enrichment.toc):
        return
    from sqlalchemy.orm.attributes import flag_modified

    db = SyncSessionLocal()
    try:
        book_row = db.query(Book).filter_by(cnts_id=book_id).first()
        if book_row:
            if enrichment.abstract and not book_row.abstract:
                book_row.abstract = enrichment.abstract
            if enrichment.keywords and not book_row.keyword:
                book_row.keyword = ", ".join(enrichment.keywords)
            extra = dict(book_row.extra or {})
            extra["references"] = enrichment.references
            if enrichment.toc:
                extra["toc"] = enrichment.toc
            if enrichment.keywords:
                extra["keywords"] = enrichment.keywords
            book_row.extra = extra
            flag_modified(book_row, "extra")
            db.commit()
    except Exception as e:
        log.warning(f"[{book_id}] enrichment DB 저장 실패: {e}")
        db.rollback()
    finally:
        db.close()


def _build_enriched_chunks(enrichment: "PaperEnrichment", base_idx: int) -> "list[Chunk]":
    """보강 결과 → 색인 청크(초록·키워드·표 원본·표 설명·그림 설명). chunk_idx 는 base_idx 부터 잇는다.

    표 원본은 수치 질문용, 표 설명은 해석·의미 검색용이다(설명이 비면 생략).
    """
    from services.ingestion.chunker import Chunk

    texts: list[str] = []
    if enrichment.abstract:
        texts.append(f"[초록] {enrichment.abstract}")
    if enrichment.keywords:
        texts.append(f"[키워드] {', '.join(enrichment.keywords)}")
    for tc in enrichment.table_chunks:
        table_text = f"[표]\n{tc.context}\n\n{tc.table_md}" if tc.context else f"[표]\n{tc.table_md}"
        texts.append(table_text.encode("utf-8")[: cfg.MAX_CHUNK_BYTES].decode("utf-8", errors="ignore"))
        if tc.description:
            texts.append(f"[표 설명] {tc.description}")
    for fc in enrichment.figure_chunks:
        texts.append(f"[그림 설명] {fc.description}")
    return [Chunk(chunk_idx=base_idx + i, text=t, section_idx=None) for i, t in enumerate(texts)]


# ── 단계 ② 섹션 요약 ─────────────────────────────────────────


def run_summarize(ctx: StageContext) -> dict:
    """섹션별 요약/테마 LLM 생성 → book_sections UPDATE."""
    from services.ingestion.summarizer import summarize_section

    book_id = ctx.book_id
    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=book_id).first()
        if not book:
            raise StageError("not_found", "카탈로그 row 없음 — extract 단계부터 재실행 필요")
        title = book.title or book_id
        doc_type = book.doc_type or "book"
        sections = (
            db.query(BookSection)
            .filter_by(book_id=book_id)
            .order_by(BookSection.section_idx)
            .all()
        )
        section_data = [
            {"section_idx": s.section_idx, "text": s.full_text, "summary": s.summary}
            for s in sections
        ]
    finally:
        db.close()

    if not section_data:
        raise StageError("not_found", "섹션 없음 — extract 단계부터 재실행 필요")

    # 재시도 시 이미 요약된 섹션은 건너뛰기 (기본 동작 — 전체 재생성은 resume_summaries=false)
    resume = ctx.params.get("resume_summaries", True)
    targets = [s for s in section_data if not (resume and s["summary"])]

    # [paper] 보강(키워드·참고문헌 폴백·표 해석·그림 설명)을 섹션 요약과 같은 루프에서 돌린다 —
    # embed 단계(celery-embed 1칸)가 LLM 을 기다리지 않게 결과를 아티팩트로 넘긴다.
    # 아티팩트에는 이 체인의 run_token 을 붙이고, 시작 전에 옛 아티팩트를 지운다 — 재처리
    # 문서에는 이전 실행이 남긴 보강이 있고(마무리는 지우지 않는다) 배포 전 것은 토큰이 없어,
    # 이번 보강이 실패하면 embed 가 그것을 읽게 되기 때문이다.
    run_token = (ctx.item_meta or {}).get("run_token")
    client = None
    enrich_text: str | None = None
    if doc_type == "paper" and cfg.PAPER_ENRICH_ENABLED:
        from services.ingestion.paper_enricher import delete_enrichment_artifact

        client = minio_client()
        delete_enrichment_artifact(book_id, client)
        try:
            enrich_text = load_extraction_text(book_id, client)
        except StageError as e:
            if e.error_group != "artifact_missing":
                raise
            log.warning(f"[{book_id}] 추출 아티팩트 없음 — 보강은 embed 단계가 맡는다")
        if enrich_text is not None and not enrich_text.strip():
            enrich_text = None

    async def _summarize_batch(items: list[dict], sem: asyncio.Semaphore) -> list[tuple[str, list[str]] | None]:
        async def _one(text: str):
            async with sem:
                try:
                    return await summarize_section(title, text, doc_type)
                except Exception as e:
                    log.warning(f"[{book_id}] 섹션 요약 실패: {e}")
                    return None

        return await asyncio.gather(*[_one(s["text"]) for s in items])

    async def _summarize_with_retry(sem: asyncio.Semaphore) -> list[tuple[str, list[str]] | None]:
        results = await _summarize_batch(targets, sem)
        # 일부만 실패해도 stage 전체는 성공 처리되어 그 섹션 summary가 영구 NULL로
        # 남는 문제 방지 — 실패분만 한 번 더 재시도 (타임아웃/부하로 인한 일시적
        # 실패가 대부분이라 재시도로 대부분 복구됨).
        failed_idx = [i for i, r in enumerate(results) if r is None]
        if failed_idx:
            log.warning(f"[{book_id}] 섹션 요약 실패 {len(failed_idx)}건 재시도")
            retry_results = await _summarize_batch([targets[i] for i in failed_idx], sem)
            for i, r in zip(failed_idx, retry_results):
                results[i] = r
        return results

    async def _enrich(sem: asyncio.Semaphore):
        from services.ingestion.paper_enricher import enrich_paper

        try:
            return await enrich_paper(book_id, title, enrich_text, client, sem=sem), None
        except Exception as e:
            log.warning(f"[{book_id}] paper enrichment 실패 — 섹션 요약은 계속: {e}")
            return None, e

    async def _run_llm():
        # 섹션 요약과 보강의 LLM 호출이 세마포어 하나를 나눠 쓴다 — celery-llm 은 프로세스당
        # 태스크 1개라 이것이 프로세스의 동시 LLM 상한이다. run_async 가 단계마다 새 루프를
        # 만들므로 세마포어도 이 루프 안에서 만든다(모듈 전역 금지).
        sem = asyncio.Semaphore(cfg.LLM_SECTION_CONCURRENCY)
        if enrich_text is None:
            return await _summarize_with_retry(sem), (None, None)
        summaries, enriched = await asyncio.gather(_summarize_with_retry(sem), _enrich(sem))
        return summaries, enriched

    if targets or enrich_text is not None:
        results, (enrichment, enrich_error) = run_async(_run_llm())
    else:
        results, enrichment, enrich_error = [], None, None
    ok = sum(1 for r in results if r)
    log.info(f"[{book_id}] 섹션 요약 {ok}/{len(targets)}개 생성 완료 (스킵 {len(section_data) - len(targets)})")

    if targets and ok == 0:
        raise StageError("llm_error", f"섹션 요약 전체 실패 ({len(targets)}건)")

    db = SyncSessionLocal()
    try:
        for sec, result in zip(targets, results):
            if not result:
                continue
            summary, themes = result
            db.query(BookSection).filter_by(
                book_id=book_id, section_idx=sec["section_idx"]
            ).update({
                "summary": summary or None,
                "themes": ", ".join(themes) if themes else None,
            })
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # 보강 결과 저장 — 아티팩트(embed 단계가 읽는다) + 카탈로그(초록·키워드·extra)
    enrich_meta: dict = {}
    if enrichment is not None:
        from services.ingestion.paper_enricher import save_enrichment_artifact

        save_enrichment_artifact(book_id, enrichment, client, run_token=run_token)
        _persist_enrichment(book_id, enrichment)
        enrich_meta = _enrichment_coverage(enrichment)
    elif enrich_error is not None:
        enrich_meta = {"enriched": False, "enrich_error": str(enrich_error)[:500]}

    failed_section_idxs = [sec["section_idx"] for sec, r in zip(targets, results) if not r]
    return {"sections_total": len(section_data), "sections_summarized": ok,
            "sections_failed": len(targets) - ok,
            "failed_section_idxs": failed_section_idxs, **enrich_meta}


# ── 단계 ③ 청킹 + 임베딩 + Milvus 인덱싱 ─────────────────────


def run_embed_index(ctx: StageContext) -> dict:
    """아티팩트 + 섹션 요약 로드 → 시맨틱 청킹 → contextual 임베딩 → Milvus delete+insert."""
    from domains import get_active_profile
    from domains.base import build_scalar_meta
    from services.ingestion.chunker import semantic_chunk, Chunk as ChunkType
    from services.ingestion.embedder import embed_texts
    from services.ingestion.indexer import index_chunks

    book_id = ctx.book_id
    client = minio_client()

    try:
        full_text, page_map = load_extraction_artifact(book_id, client)
    except StageError as _se:
        if _se.error_group != "artifact_missing":
            raise
        # 추출이 쪽수를 남긴 문서는 PDF 가 있었다. 아티팩트가 없는 것은 마무리가 이미 지웠거나
        # (옛 체인의 재실행 — 함정 16) 읽지 못한 것이다. 초록으로 진행하면 index_chunks 가 본문
        # 청크를 지우고 초록 청크로 덮으므로 인덱스를 건드리기 전에 멈춘다
        pages = ctx.item_meta.get("pages")
        if isinstance(pages, (int, float)) and pages > 0:
            raise StageError(
                "artifact_missing",
                f"PDF 가 있던 문서(pages={pages})라 초록으로 대체하지 않는다 — {_se}",
            ) from _se
        # PDF 없는 메타데이터 전용 논문 — abstract를 임베딩 텍스트로 사용
        full_text = ""
        page_map = {}

    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=book_id).first()
        if not book:
            raise StageError("not_found", "카탈로그 row 없음")

        # KCI 메타데이터 전용 논문 — abstract → title+journal 순으로 fallback
        if not full_text.strip() and (book.doc_type or "") == "paper":
            if book.abstract:
                full_text = book.abstract
                log.info(f"[{book_id}] PDF 없음 — abstract를 임베딩 텍스트로 사용 ({len(full_text)}자)")
            else:
                # abstract도 없으면 제목+저자+학술지로 최소 텍스트 구성
                fallback_parts = [p for p in [
                    book.title,
                    book.personal_author or book.corporate_author,
                    book.series_title,
                    book.subject,
                    book.keyword,
                ] if p]
                if fallback_parts:
                    full_text = " ".join(fallback_parts)
                    log.info(f"[{book_id}] PDF·abstract 없음 — 메타 필드로 최소 임베딩 ({len(full_text)}자)")

        # index_chunks 는 book_id 기준 delete 후 insert 라, 빈 본문으로 진행하면
        # 기존 청크가 전부 사라진다. 인덱스를 건드리기 전에 멈춘다.
        # 공백만 있는 페이지(OCR 저품질)는 truthy라 full_text 가 비어있지 않을 수
        # 있으므로 strip 기준으로 판단 — chunker 도 최종적으로 strip 해 문장 0개가 된다.
        if not full_text.strip():
            raise StageError(
                "empty_body",
                "추출 본문이 비어있다(아티팩트 없음 또는 공백뿐) — 빈 본문 인덱싱은 기존 청크를 전부 삭제한다",
            )

        sections_rows = (
            db.query(BookSection)
            .filter_by(book_id=book_id)
            .order_by(BookSection.section_idx)
            .all()
        )
        sections = [{"section_idx": s.section_idx, "text": s.full_text} for s in sections_rows]
        section_summary_map = {s.section_idx: s.summary for s in sections_rows if s.summary}
        section_themes_map = {
            s.section_idx: [t.strip() for t in s.themes.split(",") if t.strip()]
            for s in sections_rows if s.themes
        }
        doc_type = book.doc_type or "book"
        title = book.title or book_id
        meta_parts = [
            f"제목: {title}",
            f"기관: {book.corporate_author}" if book.corporate_author else None,
            f"저자: {book.personal_author}" if book.personal_author else None,
            f"출판사: {book.publisher}" if book.publisher else None,
            f"발행년도: {book.pub_date}" if book.pub_date else None,
            f"KDC분류: {book.kdc}" if book.kdc else None,
            f"주제: {book.subject}" if book.subject else None,
            f"키워드: {book.keyword}" if book.keyword else None,
            f"초록: {book.abstract}" if book.abstract else None,
        ]
        scalar_meta = build_scalar_meta(book, get_active_profile().milvus_scalar_fields)
    finally:
        db.close()

    def _embed_fn(texts: list[str]) -> list[list[float]]:
        dense, _ = embed_texts(texts)
        return dense

    chunks = semantic_chunk(full_text, _embed_fn, page_map=page_map)
    log.info(f"[{book_id}] 청킹 완료: {len(chunks)}개")

    assign_section_idx(chunks, sections)

    # 본문 청크: [핵심 테마] + [섹션 요약] + [본문] — 테마가 벡터 방향을 결정
    contextual_texts = []
    for c in chunks:
        parts = []
        if c.section_idx in section_themes_map:
            parts.append(f"[핵심 테마] {', '.join(section_themes_map[c.section_idx])}")
        if c.section_idx in section_summary_map:
            parts.append(f"[섹션 요약] {section_summary_map[c.section_idx]}")
        parts.append(f"[본문] {c.text}")
        contextual_texts.append("\n".join(parts))

    # ── [paper] 보강 청크 ────────────────────────────────────
    # 보강 LLM 은 요약 단계가 돌려 아티팩트로 남겼다 — 여기서는 청크만 만든다. 아티팩트가
    # 없거나 다른 실행(run_token)의 것이면(요약 단계가 보강을 못 한 아이템, 배포 전
    # 체크포인트, embed 부터 다시 도는 체인) 예전처럼 여기서 돌린다.
    enriched_chunks: list[ChunkType] = []
    enrich_meta: dict = {}   # enrichment 커버리지 — 검증/모니터링용 (item.meta 로 노출)
    # 보강 출처 — "artifact"(요약 단계가 만든 것을 읽음) | "inline"(여기서 보강 LLM 을 다시 기다림,
    # 실패해도 inline) | "none"(논문이 아니거나 보강이 꺼져 있음). 카나리에서 embed 칸이 보강을
    # 다시 돌린 비율을 센다.
    enrich_source = "none"
    if doc_type == "paper" and cfg.PAPER_ENRICH_ENABLED:
        try:
            from services.ingestion.paper_enricher import (
                enrich_paper,
                load_enrichment_artifact,
                save_enrichment_artifact,
            )

            run_token = (ctx.item_meta or {}).get("run_token")
            enrichment = load_enrichment_artifact(book_id, client, run_token=run_token)
            enrich_source = "artifact" if enrichment is not None else "inline"
            if enrichment is None:
                log.info(f"[{book_id}] 이번 실행의 보강 아티팩트 없음 — embed 단계에서 보강을 돌린다")
                enrichment = run_async(enrich_paper(book_id, title, full_text, client))
                save_enrichment_artifact(book_id, enrichment, client, run_token=run_token)
                _persist_enrichment(book_id, enrichment)

            # 추출이 조용히 실패해도 보이도록 커버리지 기록 (전부 0이면 PDF 추출 품질 의심)
            enrich_meta = _enrichment_coverage(enrichment)
            enriched_chunks = _build_enriched_chunks(enrichment, base_idx=len(chunks))
        except Exception as _e:
            import traceback
            log.warning(f"[{book_id}] paper enrichment 실패, 계속 진행: {_e}\n{traceback.format_exc()}")
            enrich_meta = {"enriched": False, "enrich_error": str(_e)[:500]}

    # 메타데이터 전용 청크 (chunk_idx=-1)
    meta_text = " | ".join(p for p in meta_parts if p)
    enriched_texts = [c.text for c in enriched_chunks]
    all_texts = contextual_texts + enriched_texts + [meta_text]

    dense_embeddings, sparse_embeddings = embed_texts(all_texts)
    log.info(
        f"[{book_id}] contextual 임베딩 완료: {len(chunks)}개 본문"
        f" + {len(enriched_chunks)}개 보강 + 1개 메타"
    )

    meta_chunk = ChunkType(chunk_idx=-1, text=meta_text, section_idx=None)
    all_chunks = chunks + enriched_chunks + [meta_chunk]

    idx_result = index_chunks(
        book_id, all_chunks, dense_embeddings, sparse_embeddings, scalar_meta=scalar_meta,
    )
    if idx_result.errors:
        raise StageError("milvus_error", f"Milvus 인덱싱 실패: {idx_result.errors}")
    log.info(f"[{book_id}] 인덱싱 완료: {idx_result.chunks_indexed}개")

    return {"chunks": len(chunks), "indexed": idx_result.chunks_indexed, **enrich_meta,
            "enrich_source": enrich_source}


# ── 단계 ④ 문서 요약/소개글 + (선택) 표지 ─────────────────────

# 계층 요약의 시간 예산. INGEST_STAGE_TIMEOUT_FINALIZE 는 시도별 하드 마감이다 — 넘으면 stale 복구가 토큰을
# 바꿔 늦게 끝난 성공은 버려지고(job_runtime._run_stage) 같은 일이 처음부터 되풀이된다. 그래서 계층 요약이
# 그 마감 안에서 끝나도록, 뒤따르는 최종 호출과 표지가 쓸 시간과 여유를 뺀 만큼만 쓰게 하고 못 끝내면 끊어서
# 균등 샘플링 입력으로 이어 간다.
_FINALIZE_MARGIN_SECONDS = 60       # 마감 앞 여유 (DB 저장·아티팩트 정리·큐 지연)
_REDUCE_MIN_BUDGET_SECONDS = 60     # 몫을 빼고 남는 시간이 이보다 적어도 이만큼은 준다


def _reduce_budget_seconds(final_timeouts: list[float], make_cover: bool) -> float:
    """계층 요약이 쓸 수 있는 최대 시간(초).

    INGEST_STAGE_TIMEOUT_FINALIZE − 최종 호출 몫 − 여유 (표지를 만들면 표지 프롬프트 LLM·FLUX 타임아웃도
    뺀다), 하한 _REDUCE_MIN_BUDGET_SECONDS. final_timeouts 는 계층 요약 뒤에 나가는 최종 호출(요약·소개글,
    도서류는 줄거리·독후 효과까지)의 타임아웃이다. 이 호출들은 LLM_SECTION_CONCURRENCY 개씩(0 이하는 1)
    동시에 나가므로 몫은 ceil(호출 수 / 동시 한도) 차례 × 가장 긴 타임아웃이다 — 차례마다 가장 긴 것만큼
    걸린다고 보면 어떤 순서로 끝나도 그 안에 든다.
    """
    waves = math.ceil(len(final_timeouts) / max(1, cfg.LLM_SECTION_CONCURRENCY))
    reserve = waves * max(final_timeouts) + _FINALIZE_MARGIN_SECONDS
    if make_cover:
        reserve += cfg.COVER_PROMPT_TIMEOUT + cfg.FLUX_TIMEOUT
    return max(_REDUCE_MIN_BUDGET_SECONDS, cfg.INGEST_STAGE_TIMEOUT_FINALIZE - reserve)


def run_finalize(ctx: StageContext) -> dict:
    """문서 요약·테마·소개글 (+선택적 FLUX 표지) → library_catalog UPDATE + 아티팩트 정리.

    계층 요약 실행 기록(reduce_levels·reduce_groups·reduce_fallback)을 반환 meta 에 남긴다.
    """
    from sqlalchemy.orm.attributes import flag_modified
    from services.ingestion.summarizer import (
        ReduceStats,
        reduce_section_summaries,
        summarize_book_from_sections,
        generate_book_introduction,
        generate_book_plot,
        generate_read_effect,
    )

    # book/literature/policy만 줄거리·독후 효과 생성. paper는 abstract가 대체.
    _GENERATE_EXTRA_DOC_TYPES = frozenset({"book", "literature", "policy"})

    book_id = ctx.book_id

    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=book_id).first()
        if not book:
            raise StageError("not_found", "카탈로그 row 없음")
        title = book.title or book_id
        author = book.personal_author or book.corporate_author or ""
        publisher = book.publisher or ""
        pub_date = book.pub_date or ""
        kdc = book.kdc or ""
        doc_type = book.doc_type or "book"
        rows = (
            db.query(BookSection.summary)
            .filter_by(book_id=book_id)
            .order_by(BookSection.section_idx)
            .all()
        )
        valid_summaries = [r[0] for r in rows if r[0]]
    finally:
        db.close()

    # 표지 생성 여부 — skip_cover=true 이거나 논문이면 생략한다(썸네일 폴백 사용).
    # 논문은 표지를 만들지 않는다(사용자 결정 2026-10-01): 잡 params 에 skip_cover 가 빠져도
    # 논문마다 표지 프롬프트 LLM(+FLUX)을 부르지 않도록 doc_type 으로도 막는다.
    # 계층 요약 시간 예산이 표지 몫을 남겨 둘지 가르는 데도 쓰므로 먼저 정한다.
    make_cover = not ctx.params.get("skip_cover") and doc_type != "paper"

    reduce_stats = ReduceStats()

    async def _generate_texts() -> dict:
        # 계층 요약 입력을 한 번 만들어 넷이 같이 쓴다. 시간 예산 안에 못 끝내거나 실패하면 None — 각 생성
        # 함수가 지금처럼 _combine_sections(균등 샘플링)로 합친다. 어느 쪽이든 마무리는 이어서 끝난다.
        final_timeouts = [cfg.SUMMARIZER_BOOK_TIMEOUT, cfg.SUMMARIZER_INTRO_TIMEOUT]
        if doc_type in _GENERATE_EXTRA_DOC_TYPES:
            final_timeouts += [cfg.SUMMARIZER_PLOT_TIMEOUT, cfg.SUMMARIZER_READ_EFFECT_TIMEOUT]
        budget = _reduce_budget_seconds(final_timeouts, make_cover)
        try:
            combined = await asyncio.wait_for(
                reduce_section_summaries(title, author, valid_summaries, doc_type, stats=reduce_stats),
                timeout=budget,
            )
        except asyncio.TimeoutError:
            log.warning(f"[{book_id}] 계층 요약이 시간 예산 {budget:g}초 안에 끝나지 않아 중단 — "
                        f"균등 샘플링 입력으로 진행 (단계 {reduce_stats.levels}, 묶음 {reduce_stats.groups})")
            reduce_stats.fallback = True
            combined = None
        except Exception as e:
            log.warning(f"[{book_id}] 계층 요약 실패 — 균등 샘플링 입력으로 진행: "
                        f"{str(e) or type(e).__name__}")
            reduce_stats.fallback = True
            combined = None
        calls = {
            "summary": summarize_book_from_sections(
                title=title, author=author, section_summaries=valid_summaries,
                doc_type=doc_type, combined_text=combined,
            ),
            "introduction": generate_book_introduction(
                title=title, author=author, publisher=publisher, pub_date=pub_date,
                section_summaries=valid_summaries, doc_type=doc_type, combined_text=combined,
            ),
        }
        if doc_type in _GENERATE_EXTRA_DOC_TYPES:
            calls["plot"] = generate_book_plot(
                title=title, author=author, section_summaries=valid_summaries,
                doc_type=doc_type, combined_text=combined,
            )
            calls["read_effect"] = generate_read_effect(
                title=title, author=author, section_summaries=valid_summaries,
                doc_type=doc_type, combined_text=combined,
            )
        # 서로 기다릴 이유가 없는 호출들이라 한 이벤트 루프에서 동시에 보낸다(프로세스당 LLM 동시
        # 호출은 요약 단계와 같은 LLM_SECTION_CONCURRENCY 까지). 하나가 실패해도 나머지는 그대로
        # 받는다(return_exceptions) — 실패한 것만 아래에서 경고 후 None.
        sem = asyncio.Semaphore(max(1, cfg.LLM_SECTION_CONCURRENCY))

        async def _bounded(coro):
            async with sem:
                return await coro

        results = await asyncio.gather(*(_bounded(c) for c in calls.values()), return_exceptions=True)
        return dict(zip(calls, results))

    _FAILURE_LABELS = {
        "summary": "도서 요약", "introduction": "도서 소개글",
        "plot": "도서 줄거리", "read_effect": "독후 효과",
    }
    book_summary = book_themes = book_introduction = book_plot = book_read_effect = None
    if valid_summaries:
        texts = run_async(_generate_texts())
        for key, value in texts.items():
            if isinstance(value, BaseException):
                log.warning(f"[{book_id}] {_FAILURE_LABELS[key]} 생성 실패: "
                            f"{str(value) or type(value).__name__}")
                texts[key] = None
        if texts["summary"] is not None:
            book_summary, themes_list = texts["summary"]
            book_themes = ", ".join(themes_list) if themes_list else None
        book_introduction = texts["introduction"]
        book_plot = texts.get("plot")
        book_read_effect = texts.get("read_effect")

    # 표지 생성 — make_cover(위에서 정한다)인 문서만
    cover_key = cover_prompt = None
    if make_cover:
        try:
            from services.ingestion.cover_generator import generate_and_store_cover

            cover_key, cover_prompt = run_async(generate_and_store_cover(
                book_id=book_id, title=title, author=author, kdc=kdc,
                themes=book_themes or "", introduction=book_introduction or "",
                summary=book_summary or "", minio_client=minio_client(),
            ))
        except Exception as e:
            log.warning(f"[{book_id}] 표지 생성 단계 실패: {e}")

    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=book_id).first()
        if book:
            book.summary = book_summary
            book.themes = book_themes
            book.introduction = book_introduction
            extra = dict(book.extra or {})
            if book_plot is not None:
                extra["plot"] = book_plot
            if book_read_effect is not None:
                extra["read_effect"] = book_read_effect
            book.extra = extra
            flag_modified(book, "extra")
            if cover_key:
                book.cover_image_key = cover_key
            if cover_prompt:
                book.cover_prompt = cover_prompt
            book.is_embedded = True
            db.commit()
        else:
            extra: dict = {}
            if book_plot is not None:
                extra["plot"] = book_plot
            if book_read_effect is not None:
                extra["read_effect"] = book_read_effect
            db.add(Book(
                cnts_id=book_id, title=book_id,
                summary=book_summary, themes=book_themes,
                introduction=book_introduction, extra=extra,
                cover_image_key=cover_key, cover_prompt=cover_prompt,
                is_embedded=True,
            ))
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # 완료된 도서의 추출 아티팩트 정리
    if not ctx.params.get("keep_artifacts"):
        delete_artifact(book_id, minio_client())

    return {
        "summary": bool(book_summary),
        "plot": bool(book_plot),
        "read_effect": bool(book_read_effect),
        "introduction": bool(book_introduction),
        "cover": bool(cover_key),
        # 계층 요약 실행 기록 — 카나리에서 섹션이 많은 문서가 계층 요약을 탔는지 meta 로 센다. 섹션 요약이 없어
        # 계층 요약을 안 불러도 0·0·False 로 늘 싣는다(재처리 때 이전 실행의 값이 남지 않게).
        # reduce_levels: 시작한 중간 요약 단계 수(0 = 상한 이하라 합치기만), reduce_groups: 묶음 수(단계 합),
        # reduce_fallback: 실패·시간 예산 초과로 균등 샘플링 입력을 썼는가
        "reduce_levels": reduce_stats.levels,
        "reduce_groups": reduce_stats.groups,
        "reduce_fallback": reduce_stats.fallback,
    }


# 단계 레지스트리 — 잡 레이어가 stage 체크포인트 기준으로 남은 단계 체인을 구성할 때 사용
STAGE_FUNCS = {
    "extract": run_extract,
    "summarize": run_summarize,
    "embed_index": run_embed_index,
    "finalize": run_finalize,
}

# stage 체크포인트(완료 표시) ↔ 단계 이름 매핑
STAGE_ORDER = ["extract", "summarize", "embed_index", "finalize"]
STAGE_CHECKPOINT = {
    "extract": "extracted",
    "summarize": "summarized",
    "embed_index": "indexed",
    "finalize": "finalized",
}
# 체크포인트 기준 다음에 실행할 단계들
CHECKPOINT_TO_REMAINING = {
    "pending": STAGE_ORDER,
    "extracted": STAGE_ORDER[1:],
    "summarized": STAGE_ORDER[2:],
    "indexed": STAGE_ORDER[3:],
    "finalized": [],
}
