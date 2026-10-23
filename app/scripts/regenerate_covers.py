"""
소장자료 표지 다시 만들기 — 논문이 아닌 자료(정책 보고서·문학 학위논문·도서)의 AI 표지를 새 아트 디렉션(cover_art — 실사풍)으로 다시 그린다.

2026-10-23 대표 지적('표지가 다 비슷하다', 제목 기준 실사풍으로)에 따라 표지 프롬프트를 바꿨다(cover_generator·cover_art 머리말).
적재 때만 표지를 만들어서 이미 만든 표지를 다시 그리는 길이 없어 이 스크립트를 둔다. 새로 적재하는 자료는 적재 마무리가 새 방식으로 만든다.

운영 fastapi 컨테이너 안에서 돈다(DB·MinIO·LLM·FLUX 설정이 그대로 있다). FLUX 컨테이너가 떠 있어야 한다(FLUX_BASE_URL,
기본 http://flux:8000 — e북 표지 LoRA 는 끈 채로 띄운다).

  # 프롬프트만 먼저 본다(그리지도 쓰지도 않는다)
  docker exec -w /app nl-lib-fastapi python -m scripts.regenerate_covers --limit 10
  # 다시 그려 올린다 — 옛 표지는 covers_backup/<시각>/ 에 복사한 뒤에만 덮어쓴다(복사가 안 되면 그 자료는 건너뛴다)
  docker exec -w /app nl-lib-fastapi python -m scripts.regenerate_covers --apply --log /app/covers_run.jsonl

기록 파일(--log)은 자료마다 한 줄이다 — 옛 표지 키·옛 프롬프트·백업 위치가 들어 있어 되돌리기에 쓴다. 같은 기록 파일로 다시 돌리면
끝낸 자료는 건너뛰고 이어 간다. 컨테이너 안 파일은 컨테이너를 다시 만들면 사라지니 끝나면 `docker cp` 로 꺼내 둔다.
되돌리기: 기록의 backup(covers_backup/<시각>/<id>.jpg)을 covers/<id>.jpg 로 다시 복사하고 cover_prompt 를 old_prompt 로 돌린다.
화면의 표지 응답은 브라우저가 하루 동안 기억한다(Cache-Control max-age=86400) — 시연 PC 는 다시 그린 뒤 캐시를 비운다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from collections import deque

log = logging.getLogger("regenerate_covers")

DEFAULT_DOC_TYPES = ("policy", "literature", "book")
AVOID_KEEP = 12


def done_ids(log_path: str | None) -> set[str]:
    """기록 파일에서 이미 끝낸 자료 id — 같은 기록 파일로 다시 돌리면 건너뛴다(그려 올린 것만, 미리보기·실패는 다시)."""
    if not log_path or not os.path.exists(log_path):
        return set()
    out: set[str] = set()
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "ok":
                out.add(row.get("cnts_id"))
    return out


def pending(targets: list[dict], done: set[str], limit: int) -> list[dict]:
    """끝낸 자료를 먼저 빼고 limit 을 건다 — 같은 기록으로 나눠 돌릴 때 다음 묶음으로 넘어가게(앞에 limit 을 걸면 첫 묶음만 돈다)."""
    rest = [t for t in targets if t["cnts_id"] not in done]
    return rest[:limit] if limit else rest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="소장자료 AI 표지 다시 만들기")
    p.add_argument("--apply", action="store_true", help="그려서 MinIO 에 올리고 DB 를 고친다(없으면 프롬프트만 출력)")
    p.add_argument("--ids", default="", help="쉼표로 나눈 자료 id 만")
    p.add_argument("--doc-types", default=",".join(DEFAULT_DOC_TYPES),
                   help="대상 doc_type(쉼표) — 논문(paper)은 넣어도 뺀다. book 이면 doc_type 이 비어 있는 자료도 든다(적재가 book 으로 본다)")
    p.add_argument("--include-missing", action="store_true", help="AI 표지가 없던 자료도(기본은 AI 표지가 있던 자료만)")
    p.add_argument("--limit", type=int, default=0, help="끝낸 자료를 빼고 앞에서 N 건만(0 = 전부)")
    p.add_argument("--log", default="", help="진행 기록 JSONL — 같은 파일로 다시 돌리면 끝낸 자료는 건너뛴다")
    p.add_argument("--no-backup", action="store_true", help="옛 표지를 covers_backup/ 에 복사하지 않는다(되돌릴 수 없다)")
    p.add_argument("--max-fails", type=int, default=5, help="잇달아 이만큼 실패하면 멈춘다(FLUX·LLM 이 죽었을 때 운영 LLM 을 계속 부르지 않게)")
    p.add_argument("--sleep", type=float, default=0.0, help="자료 사이 쉬는 초(운영 LLM·GPU 부하를 낮출 때)")
    return p.parse_args(argv)


def _load_targets(args) -> list[dict]:
    """대상 자료를 한 번 읽어 값만 들고 나온다 — LLM·FLUX 를 기다리는 동안 DB 트랜잭션을 열어 두지 않는다(함정 18)."""
    from sqlalchemy import or_

    from db.postgres import SyncSessionLocal
    from models.book import Book

    doc_types = [d.strip() for d in args.doc_types.split(",") if d.strip() and d.strip() != "paper"]
    cond = Book.doc_type.in_(doc_types)
    if "book" in doc_types:
        cond = or_(cond, Book.doc_type.is_(None))
    db = SyncSessionLocal()
    try:
        q = db.query(Book).filter(cond)
        if args.ids:
            q = q.filter(Book.cnts_id.in_([i.strip() for i in args.ids.split(",") if i.strip()]))
        if not args.include_missing:
            q = q.filter(Book.cover_image_key.isnot(None))
        rows = q.order_by(Book.doc_type, Book.cnts_id).all()
        return [{
            "cnts_id": b.cnts_id, "title": b.title, "author": b.personal_author or b.corporate_author or "",
            "kdc": b.kdc or "", "doc_type": b.doc_type or "book", "themes": b.themes or "",
            "introduction": b.introduction or "", "summary": b.summary or "",
            "old_key": b.cover_image_key, "old_prompt": b.cover_prompt,
        } for b in rows]
    finally:
        db.close()


def _save(cnts_id: str, key: str, prompt: str) -> None:
    """한 자료의 표지 키·프롬프트를 짧은 트랜잭션으로 고친다."""
    from db.postgres import SyncSessionLocal
    from models.book import Book

    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=cnts_id).first()
        if book is None:
            raise RuntimeError("자료가 DB 에서 사라졌다")
        book.cover_image_key = key
        book.cover_prompt = prompt
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def _run(args) -> dict:
    from minio.commonconfig import CopySource

    from core.config import get_settings
    from services.ingestion import cover_art
    from services.ingestion.cover_generator import compose_cover, render_cover_image, upload_cover_to_minio
    from services.ingestion.stages import minio_client

    cfg = get_settings()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    done = done_ids(args.log)
    targets = _load_targets(args)
    todo = pending(targets, done, args.limit)
    avoid: dict[str, deque] = {g: deque(maxlen=AVOID_KEEP) for g in ("policy", "classical", "modern")}
    counts = {"ok": 0, "dry": 0, "kept_old": 0, "fail": 0}
    client = minio_client() if args.apply else None
    fails_in_row = 0
    log.info(f"대상 {len(targets)}건 중 이번 {len(todo)}건 (이미 끝낸 {len(done)}건 제외, {'그려서 올림' if args.apply else '프롬프트만'})")

    logf = open(args.log, "a", encoding="utf-8") if args.log else None
    try:
        for i, t in enumerate(todo, 1):
            cid = t["cnts_id"]
            row = {"cnts_id": cid, "title": t["title"], "doc_type": t["doc_type"],
                   "old_key": t["old_key"], "old_prompt": t["old_prompt"]}
            genre = cover_art.genre_of(t["doc_type"], t["title"] or "", t["themes"], t["summary"])
            try:
                made = await compose_cover(
                    title=t["title"] or cid, author=t["author"], kdc=t["kdc"], themes=t["themes"],
                    introduction=t["introduction"], summary=t["summary"], book_id=cid, doc_type=t["doc_type"],
                    avoid=list(avoid[genre]),
                )
                if not made:
                    # 금지어를 끝내 못 뺀 문학 아닌 자료 — 옛 표지를 그대로 둔다
                    row["status"] = "kept_old"
                    counts["kept_old"] += 1
                else:
                    prompt, scene = made
                    row["prompt"] = prompt
                    avoid[genre].append(cover_art.key_nouns(scene))
                    if not args.apply:
                        row["status"] = "dry"
                        counts["dry"] += 1
                    else:
                        image = await render_cover_image(prompt)
                        if not image:
                            raise RuntimeError("FLUX 가 빈 이미지를 돌려줬다")
                        if t["old_key"] and not args.no_backup:
                            backup = f"covers_backup/{stamp}/{cid}.jpg"
                            # 백업이 안 되면 덮어쓰지 않는다 — 옛 표지를 되돌릴 수 없게 된다(이 자료는 실패로 남기고 넘어간다)
                            client.copy_object(cfg.MINIO_BUCKET, backup, CopySource(cfg.MINIO_BUCKET, t["old_key"]))
                            row["backup"] = backup
                        key = upload_cover_to_minio(cid, image, client)
                        _save(cid, key, prompt)
                        row["new_key"] = key
                        row["status"] = "ok"
                        counts["ok"] += 1
                fails_in_row = 0
            except Exception as e:
                row["status"] = "fail"
                row["error"] = f"{type(e).__name__}: {e}"
                counts["fail"] += 1
                fails_in_row += 1
                log.warning(f"[{cid}] 실패: {row['error']}")
            if logf:
                logf.write(json.dumps(row, ensure_ascii=False) + "\n")
                logf.flush()
            print(f"[{i}/{len(todo)}] {row['status']} {cid} {(t['title'] or '')[:30]} | "
                  f"{(row.get('prompt') or row.get('error') or '')[:140]}", flush=True)
            if fails_in_row >= args.max_fails:
                log.error(f"잇달아 {fails_in_row}건 실패 — 멈춘다(FLUX·LLM 상태를 보고 같은 --log 로 다시 돌리면 이어 간다)")
                break
            if args.sleep:
                await asyncio.sleep(args.sleep)
    finally:
        if logf:
            logf.close()
    return counts


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    counts = asyncio.run(_run(args))
    print(json.dumps({"stamp": time.strftime("%Y-%m-%d %H:%M:%S"), **counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
