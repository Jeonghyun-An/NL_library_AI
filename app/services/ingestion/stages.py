"""
단계(체크포인트) 단위로 분리되어 실패 시 해당 단계부터 재개 가능:

  run_extract     : 다운로드 → 텍스트 추출 → 그림 저장 → 섹션 분할 → PG 저장
                    + MinIO artifacts/{book_id}/extraction.json.gz (재개용 중간 산출물)
  run_summarize   : 섹션 요약/테마 LLM → book_sections UPDATE (doc_type 판별·영속화 포함)
  run_embed_index : 아티팩트 + 섹션 요약 로드 → 청킹 → 임베딩 → Milvus delete+insert
  run_finalize    : 문서 요약/소개글 LLM → library_catalog UPDATE
                    (skip_cover 파라미터로 FLUX 생략 — 썸네일은 API가 온디맨드 생성)

잡 레이어(workers/job_runtime.py)는 이 함수들의 시그니처(StageContext → dict)만 의존한다.
ingest_state 전이·락·타이밍 기록은 호출자(태스크 래퍼) 책임.
"""
import asyncio
import gzip
import io
import json
import logging
import os
from dataclasses import dataclass, field

from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.book import Book
from models.section import BookSection

log = logging.getLogger(__name__)
cfg = get_settings()

SECTION_TARGET_TOKENS = 3000
SECTION_MAX_TOKENS = 5000

DOWNLOAD_DIR = "/app/data/downloads"


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


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 1.5))


def split_into_sections(pages: list, target_tokens: int = SECTION_TARGET_TOKENS) -> list[dict]:
    sections = []
    current_texts = []
    current_tokens = 0
    current_page_start = 0

    for page in pages:
        page_tokens = _estimate_tokens(page.text)

        if current_tokens + page_tokens > SECTION_MAX_TOKENS and current_texts:
            sections.append({
                "section_idx": len(sections),
                "text": "\n\n".join(current_texts),
                "page_start": current_page_start,
                "page_end": page.page_num - 1,
                "token_count": current_tokens,
            })
            current_texts = []
            current_tokens = 0
            current_page_start = page.page_num

        current_texts.append(page.text)
        current_tokens += page_tokens

    if current_texts:
        sections.append({
            "section_idx": len(sections),
            "text": "\n\n".join(current_texts),
            "page_start": current_page_start,
            "page_end": pages[-1].page_num if pages else 0,
            "token_count": current_tokens,
        })

    return sections


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


def load_extraction_artifact(book_id: str, client) -> tuple[str, dict[int, int]]:
    """아티팩트 로드 → (full_text, page_map) 재구성 (extractor와 동일 로직)."""
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
    data = json.loads(gzip.decompress(raw).decode("utf-8"))

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
    """다운로드 → 추출 → 그림 저장 → 메타 보장/doc_type 판별 → 섹션 PG 저장 → 아티팩트."""
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
        extraction = run_async(extract_text(local_path, book_id))
        if not extraction.pages:
            raise StageError("extract_empty", f"텍스트 추출 실패: {extraction.errors}")
        log.info(f"[{book_id}] 추출 완료: {extraction.stats}")

        if extraction.figures:
            n_figs = save_figures(book_id, extraction.figures, client)
            log.info(f"[{book_id}] 그림 {n_figs}개 저장 완료")

        sections = split_into_sections(extraction.pages)
        log.info(f"[{book_id}] 섹션 {len(sections)}개 분할 완료")

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

        # 잡 파라미터 doc_type 강제 > 프로파일 판별
        doc_type = ctx.params.get("doc_type") or get_active_profile().detect_doc_type({
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

    async def _summarize_all() -> list[tuple[str, list[str]] | None]:
        sem = asyncio.Semaphore(cfg.LLM_SECTION_CONCURRENCY)

        async def _one(text: str):
            async with sem:
                try:
                    return await summarize_section(title, text, doc_type)
                except Exception as e:
                    log.warning(f"[{book_id}] 섹션 요약 실패: {e}")
                    return None

        return await asyncio.gather(*[_one(s["text"]) for s in targets])

    results = run_async(_summarize_all()) if targets else []
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

    return {"sections_total": len(section_data), "sections_summarized": ok,
            "sections_failed": len(targets) - ok}


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
    full_text, page_map = load_extraction_artifact(book_id, client)

    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=book_id).first()
        if not book:
            raise StageError("not_found", "카탈로그 row 없음")
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

    # 메타데이터 전용 청크 (chunk_idx=-1)
    meta_text = " | ".join(p for p in meta_parts if p)
    all_texts = contextual_texts + [meta_text]

    dense_embeddings, sparse_embeddings = embed_texts(all_texts)
    log.info(f"[{book_id}] contextual 임베딩 완료: {len(dense_embeddings) - 1}개 본문 + 1개 메타")

    meta_chunk = ChunkType(chunk_idx=-1, text=meta_text, section_idx=None)
    all_chunks = chunks + [meta_chunk]

    idx_result = index_chunks(
        book_id, all_chunks, dense_embeddings, sparse_embeddings, scalar_meta=scalar_meta,
    )
    if idx_result.errors:
        raise StageError("milvus_error", f"Milvus 인덱싱 실패: {idx_result.errors}")
    log.info(f"[{book_id}] 인덱싱 완료: {idx_result.chunks_indexed}개")

    return {"chunks": len(chunks), "indexed": idx_result.chunks_indexed}


# ── 단계 ④ 문서 요약/소개글 + (선택) 표지 ─────────────────────


def run_finalize(ctx: StageContext) -> dict:
    """문서 요약·테마·소개글 (+선택적 FLUX 표지) → library_catalog UPDATE + 아티팩트 정리."""
    from services.ingestion.summarizer import (
        summarize_book_from_sections,
        generate_book_introduction,
    )

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

    book_summary = book_themes = book_introduction = None
    if valid_summaries:
        try:
            book_summary, themes_list = run_async(summarize_book_from_sections(
                title=title, author=author,
                section_summaries=valid_summaries, doc_type=doc_type,
            ))
            book_themes = ", ".join(themes_list) if themes_list else None
        except Exception as e:
            log.warning(f"[{book_id}] 도서 요약 생성 실패: {e}")

        try:
            book_introduction = run_async(generate_book_introduction(
                title=title, author=author, publisher=publisher,
                pub_date=pub_date, section_summaries=valid_summaries,
            ))
        except Exception as e:
            log.warning(f"[{book_id}] 도서 소개글 생성 실패: {e}")

    # 표지 생성 — 대량 논문 인덱싱에서는 skip_cover=true 로 생략 (썸네일 폴백 사용)
    cover_key = cover_prompt = None
    if not ctx.params.get("skip_cover"):
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
            if cover_key:
                book.cover_image_key = cover_key
            if cover_prompt:
                book.cover_prompt = cover_prompt
            book.is_embedded = True
            db.commit()
        else:
            db.add(Book(
                cnts_id=book_id, title=book_id,
                summary=book_summary, themes=book_themes,
                introduction=book_introduction,
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
        "introduction": bool(book_introduction),
        "cover": bool(cover_key),
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
