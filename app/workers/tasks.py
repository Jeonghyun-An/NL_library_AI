"""
workers/tasks.py — Celery 비동기 작업

수집 파이프라인:
  ① 텍스트 추출 (fitz → VLM fallback)
  ② 섹션 분할 (페이지 그룹 단위) → PostgreSQL 저장
  ③ 섹션 내 시맨틱 청킹 → 각 청크에 section_idx 매핑
  ④ 청크별 임베딩 → Milvus 저장
  ⑤ 요약 생성 → PostgreSQL 업데이트
"""
import logging
import asyncio

from workers.celery_app import celery_app
from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.book import Book
from models.section import BookSection

log = logging.getLogger(__name__)
cfg = get_settings()

SECTION_TARGET_TOKENS = 3000
SECTION_MAX_TOKENS = 5000


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 1.5))


def _split_into_sections(pages: list, target_tokens: int = SECTION_TARGET_TOKENS) -> list[dict]:
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


def _assign_section_idx(chunks, sections) -> None:
    """
    각 청크에 소속 섹션 인덱스를 매핑
    청크의 누적 문자 위치로 어느 섹션에 속하는지 판정
    """
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


# ── 1. 엑셀 메타데이터 로드 ─────────────────────────────
@celery_app.task(name="tasks.load_catalog_xlsx", queue="ingestion")
def load_catalog_xlsx(xlsx_path: str):
    from services.ingestion.xlsx_loader import load_xlsx

    records = load_xlsx(xlsx_path)
    db = SyncSessionLocal()
    try:
        created = 0
        for rec in records:
            exists = db.query(Book).filter_by(cnts_id=rec["cnts_id"]).first()
            if exists:
                continue
            book = Book(**rec)
            db.add(book)
            created += 1
        db.commit()
        log.info(f"메타데이터 {created}건 저장 완료")
        return {"created": created, "total": len(records)}
    except Exception as e:
        db.rollback()
        log.error(f"메타데이터 저장 실패: {e}")
        raise
    finally:
        db.close()


# ── 2. 단일 도서 원본 파일 처리 ──────────────────────────
@celery_app.task(
    name="tasks.process_book_file",
    queue="ingestion",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def process_book_file(self, book_id: str, file_path: str):
    from services.ingestion.extractor import extract_text
    from services.ingestion.chunker import semantic_chunk
    from services.ingestion.embedder import embed_texts
    from services.ingestion.indexer import index_chunks
    from services.ingestion.summarizer import summarize_book

    log.info(f"[{book_id}] 처리 시작: {file_path}")

    # ① 텍스트 추출
    extraction = _run_async(extract_text(file_path, book_id))
    if not extraction.pages:
        log.error(f"[{book_id}] 텍스트 추출 실패: {extraction.errors}")
        return {"book_id": book_id, "status": "failed", "errors": extraction.errors}

    full_text = extraction.full_text
    log.info(f"[{book_id}] 추출 완료: {extraction.stats}")

    # ② 섹션 분할 → PostgreSQL 저장
    sections = _split_into_sections(extraction.pages)
    log.info(f"[{book_id}] 섹션 {len(sections)}개 분할 완료")

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
        log.info(f"[{book_id}] 섹션 {len(sections)}개 DB 저장 완료")
    except Exception as e:
        db.rollback()
        log.error(f"[{book_id}] 섹션 저장 실패: {e}")
    finally:
        db.close()

    # ③ 시맨틱 청킹
    def _embed_fn(texts: list[str]):
        return embed_texts(texts)

    chunks = semantic_chunk(full_text, _embed_fn)
    log.info(f"[{book_id}] 청킹 완료: {len(chunks)}개")

    _assign_section_idx(chunks, sections)

    # 페이지 정보 매핑
    page_acc = 0
    for chunk in chunks:
        ratio = page_acc / max(len(full_text), 1)
        chunk.page_start = int(ratio * extraction.total_pages)
        chunk.page_end = min(chunk.page_start + 1, extraction.total_pages - 1)
        page_acc += len(chunk.text)

    # ④ 청크별 임베딩 → Milvus 저장
    chunk_texts = [c.text for c in chunks]
    embeddings = embed_texts(chunk_texts)
    log.info(f"[{book_id}] 임베딩 완료: {len(embeddings)}개")

    idx_result = index_chunks(book_id, chunks, embeddings)
    log.info(f"[{book_id}] 인덱싱 완료: {idx_result.chunks_indexed}개")

    # ⑤ 요약 생성 → PostgreSQL 업데이트
    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=book_id).first()

        title = book.title if book else book_id
        author = book.personal_author or "" if book else ""
        summary_input = full_text[:4000]

        summary = _run_async(summarize_book(
            title=title,
            author=author,
            raw_text=summary_input,
        ))

        if book:
            book.summary = summary
            book.full_text_length = len(full_text)
            book.chunk_count = len(chunks)
            book.extraction_stats = str(extraction.stats)
            book.is_embedded = True
            db.commit()
            log.info(f"[{book_id}] DB 업데이트 완료")
        else:
            new_book = Book(
                cnts_id=book_id,
                title=book_id,
                summary=summary,
                full_text_length=len(full_text),
                chunk_count=len(chunks),
                extraction_stats=str(extraction.stats),
                is_embedded=True,
            )
            db.add(new_book)
            db.commit()
            log.info(f"[{book_id}] 신규 도서 + 요약 저장 완료")
    except Exception as e:
        db.rollback()
        log.warning(f"[{book_id}] 요약 저장 실패: {e}")
    finally:
        db.close()

    return {
        "book_id": book_id,
        "status": "completed",
        "extraction": extraction.stats,
        "sections": len(sections),
        "chunks": len(chunks),
        "indexed": idx_result.chunks_indexed,
    }


# ── 3. 배치 처리 ────────────────────────────────────────
@celery_app.task(name="tasks.ingest_batch", queue="ingestion")
def ingest_batch(file_mappings: list[dict]):
    results = []
    for item in file_mappings:
        task = process_book_file.delay(item["book_id"], item["file_path"])
        results.append({"book_id": item["book_id"], "task_id": task.id})
    return {"dispatched": len(results), "tasks": results}


# ── 4. MinIO에서 파일 다운로드 후 처리 ───────────────────
@celery_app.task(name="tasks.process_from_minio", queue="ingestion")
def process_from_minio(book_id: str, minio_key: str):
    from minio import Minio
    import os

    client = Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )

    download_dir = "/app/data/downloads"
    os.makedirs(download_dir, exist_ok=True)
    local_path = os.path.join(download_dir, f"{book_id}.pdf")

    client.fget_object(cfg.MINIO_BUCKET, minio_key, local_path)
    log.info(f"[{book_id}] MinIO → {local_path} 다운로드 완료")

    task = process_book_file.delay(book_id, local_path)
    return {"book_id": book_id, "task_id": task.id}