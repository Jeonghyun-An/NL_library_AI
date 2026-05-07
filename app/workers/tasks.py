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
        created = updated = 0
        for rec in records:
            cnts_id = rec.get("cnts_id")
            if not cnts_id:
                continue

            exists = db.query(Book).filter_by(cnts_id=cnts_id).first()
            if exists:
                # 기존 레코드 업데이트: 파싱된 non-None 값만 덮어쓰기
                # (is_embedded, summary 등 수집 관련 필드는 건드리지 않음)
                SKIP_ON_UPDATE = {"cnts_id", "is_embedded", "summary", "milvus_id", "chunk_count"}
                changed = False
                for key, val in rec.items():
                    if key in SKIP_ON_UPDATE:
                        continue
                    if val is not None and getattr(exists, key, None) != val:
                        setattr(exists, key, val)
                        changed = True
                if changed:
                    updated += 1
            else:
                book = Book(**rec)
                db.add(book)
                created += 1

        db.commit()
        log.info(f"메타데이터 신규 {created}건 저장, {updated}건 업데이트 완료")
        return {"created": created, "updated": updated, "total": len(records)}
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
    from services.ingestion.indexer import index_chunks, BookMeta
    from services.ingestion.summarizer import (
        summarize_section,
        summarize_book_from_sections,
        generate_book_introduction,
        detect_doc_type,
    )

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

    # 도서 메타 미리 조회 (요약에 필요)
    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=book_id).first()
        if not book:
            log.error(f"[{book_id}] 메타데이터 없음 → 인덱싱 중단")
            raise self.retry(
                exc=Exception("metadata_not_found"),
                countdown=60
            )

        if not (book.publisher or book.corporate_author or book.pub_date):
            log.warning(f"[{book_id}] 메타데이터 불완전 → 인덱싱 중단")
            raise self.retry(
                exc=Exception("metadata_not_ready"),
                countdown=60
            )

        title = book.title if book else book_id
        author = (book.personal_author or book.corporate_author or "") if book else ""
        doc_type = detect_doc_type(
            kdc=book.kdc if book else None,
            title=title,
        )
        log.info(f"[{book_id}] 문서 유형: {doc_type} (기본: book)")
    finally:
        db.close()

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
        raise
    finally:
        db.close()

    # ②-b 섹션별 요약+테마 병렬 생성 (vLLM max-num-seqs 16 기준 동시 8개)
    async def _summarize_all_sections() -> list[tuple[str, list[str]] | None]:
        sem = asyncio.Semaphore(8)
        async def _one(text: str) -> tuple[str, list[str]] | None:
            async with sem:
                try:
                    return await summarize_section(title, text, doc_type)
                except Exception as e:
                    log.warning(f"[{book_id}] 섹션 요약 실패: {e}")
                    return None
        return await asyncio.gather(*[_one(s["text"]) for s in sections])

    section_results_list = _run_async(_summarize_all_sections())
    log.info(f"[{book_id}] 섹션 요약 {sum(1 for s in section_results_list if s)}개 생성 완료")

    # 섹션 요약/테마 DB 저장 + 맵 구성
    section_summary_map: dict[int, str] = {}
    section_themes_map: dict[int, list[str]] = {}
    db = SyncSessionLocal()
    try:
        for sec, result in zip(sections, section_results_list):
            if not result:
                continue
            summary, themes = result
            if summary:
                section_summary_map[sec["section_idx"]] = summary
            if themes:
                section_themes_map[sec["section_idx"]] = themes
            db.query(BookSection).filter_by(
                book_id=book_id, section_idx=sec["section_idx"]
            ).update({
                "summary": summary or None,
                "themes": ", ".join(themes) if themes else None,
            })
        db.commit()
        log.info(f"[{book_id}] 섹션 요약/테마 DB 저장 완료")
    except Exception as e:
        db.rollback()
        log.warning(f"[{book_id}] 섹션 요약/테마 저장 실패: {e}")
    finally:
        db.close()

    # ③ 시맨틱 청킹
    def _embed_fn(texts: list[str]) -> list[list[float]]:
        dense, _ = embed_texts(texts)
        return dense

    chunks = semantic_chunk(full_text, _embed_fn, page_map=extraction.page_map)
    log.info(f"[{book_id}] 청킹 완료: {len(chunks)}개")

    _assign_section_idx(chunks, sections)

    # 페이지 정보 매핑
    # page_acc = 0
    # for chunk in chunks:
    #     ratio = page_acc / max(len(full_text), 1)
    #     chunk.page_start = int(ratio * extraction.total_pages)
    #     chunk.page_end = min(chunk.page_start + 1, extraction.total_pages - 1)
    #     page_acc += len(chunk.text)

    # ④ Contextual 임베딩 → Milvus 저장
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

    # 메타데이터 전용 청크 1개 추가 (chunk_idx=-1)
    _meta_parts = [
        f"제목: {title}",
        f"기관: {book.corporate_author}" if book and book.corporate_author else None,
        f"저자: {book.personal_author}"  if book and book.personal_author  else None,
        f"출판사: {book.publisher}"      if book and book.publisher        else None,
        f"발행년도: {book.pub_date}"     if book and book.pub_date         else None,
        f"KDC분류: {book.kdc}"          if book and book.kdc              else None,
        f"주제: {book.subject}"          if book and book.subject          else None,
        f"키워드: {book.keyword}"        if book and book.keyword          else None,
        f"초록: {book.abstract}"         if book and book.abstract         else None,
    ]
    meta_text = " | ".join(p for p in _meta_parts if p)
    all_texts = contextual_texts + [meta_text]

    dense_embeddings, sparse_embeddings = embed_texts(all_texts)
    log.info(f"[{book_id}] contextual 임베딩 완료: {len(dense_embeddings) - 1}개 본문 + 1개 메타")

    # 메타데이터 전용 청크 객체 (chunk_idx=-1, section_idx=None)
    from services.ingestion.chunker import Chunk as ChunkType
    meta_chunk = ChunkType(chunk_idx=-1, text=meta_text, section_idx=None)
    all_chunks = chunks + [meta_chunk]

    book_meta = BookMeta(
        publisher=book.publisher or "" if book else "",
        corporate_author=book.corporate_author or "" if book else "",
        pub_date=book.pub_date or "" if book else "",
        kdc=book.kdc or "" if book else "",
    )
    idx_result = index_chunks(book_id, all_chunks, dense_embeddings, sparse_embeddings, book_meta=book_meta)
    log.info(f"[{book_id}] 인덱싱 완료: {idx_result.chunks_indexed}개")

    # ⑤ 도서 요약+테마+소개글 생성 (섹션 요약 합산 → LLM 2회) → PostgreSQL 업데이트
    valid_summaries = list(section_summary_map.values())
    book_summary: str | None = None
    book_themes: str | None = None
    book_introduction: str | None = None
    if valid_summaries:
        try:
            summary_result = _run_async(summarize_book_from_sections(
                title=title,
                author=author,
                section_summaries=valid_summaries,
                doc_type=doc_type,
            ))
            book_summary, themes_list = summary_result
            book_themes = ", ".join(themes_list) if themes_list else None
        except Exception as e:
            log.warning(f"[{book_id}] 도서 요약 생성 실패: {e}")

        try:
            book_introduction = _run_async(generate_book_introduction(
                title=title,
                author=author,
                publisher=book.publisher or "" if book else "",
                pub_date=book.pub_date or "" if book else "",
                section_summaries=valid_summaries,
            ))
            log.info(f"[{book_id}] 도서 소개글 생성 완료")
        except Exception as e:
            log.warning(f"[{book_id}] 도서 소개글 생성 실패: {e}")

    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=book_id).first()
        if book:
            book.summary = book_summary
            book.themes = book_themes
            book.introduction = book_introduction
            book.is_embedded = True
            db.commit()
            log.info(f"[{book_id}] DB 업데이트 완료")
        else:
            new_book = Book(
                cnts_id=book_id,
                title=book_id,
                summary=book_summary,
                themes=book_themes,
                introduction=book_introduction,
                is_embedded=True,
            )
            db.add(new_book)
            db.commit()
            log.info(f"[{book_id}] 신규 도서 + 요약/테마/소개글 저장 완료")
    except Exception as e:
        db.rollback()
        log.warning(f"[{book_id}] 요약/테마 저장 실패: {e}")
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