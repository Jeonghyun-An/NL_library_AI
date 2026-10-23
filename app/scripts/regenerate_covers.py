"""
소장자료 표지 다시 만들기 — 논문이 아닌 자료(정책 보고서·문학 학위논문·도서)의 표지를 새 방식으로 다시 만든다.

2026-10-23 대표 지적('표지가 다 비슷하다', 제목 기준 실사풍으로)에 따라 그림 표지 프롬프트를 바꿨고(cover_generator·cover_art
머리말), 정책 보고서는 그림 대신 목업 표지(cover_typo — 제목·발행처 조판)를 보이기로 했다(사용자 결정 같은 날).
정책 보고서는 두 판을 다 만들어 둔다 — 목업(typo, covers/typo/{id}.jpg)과 그림(photo, covers/{id}.jpg). 화면에는 --show 판
(기본 cover_generator.POLICY_COVER = typo)이 보이고, 다시 그리지 않고 --switch 로 바꿀 수 있다. 문학·도서는 그림 한 판이다.
적재 때만 표지를 만들어서 이미 만든 표지를 다시 그리는 길이 없어 이 스크립트를 둔다. 새로 적재하는 자료는 적재 마무리가 새 방식으로 만든다.

운영 fastapi 컨테이너 안에서 돈다(DB·MinIO·LLM·FLUX 설정이 그대로 있다). 그림(photo)을 만들 때만 FLUX 컨테이너가 떠 있어야
한다(FLUX_BASE_URL, 기본 http://flux:8000 — e북 표지 LoRA 는 끈 채로 띄운다). 목업은 GPU 없이 몇 분이면 끝난다.

  # 미리보기 — 그리지도 쓰지도 않는다(목업은 메모리에서만 그려 글꼴을 확인하고, 그림은 프롬프트만 출력)
  docker exec -w /app nl-lib-fastapi python -m scripts.regenerate_covers --limit 10
  # ① 정책 보고서 목업만 먼저(빠르다) — 화면에 바로 목업이 보인다
  docker exec -w /app nl-lib-fastapi python -m scripts.regenerate_covers --apply --doc-types policy --parts typo --log /app/covers_typo.jsonl
  # ② 문학·도서 그림 — 옛 그림은 covers_backup/<시각>/ 에 복사한 뒤에만 덮어쓴다(복사가 안 되면 그 자료는 건너뛴다)
  docker exec -w /app nl-lib-fastapi python -m scripts.regenerate_covers --apply --doc-types literature,book --log /app/covers_run.jsonl
  # ③ 정책 보고서 그림(보이지 않는 예비 판) — 나중에 돌려도 된다
  docker exec -w /app nl-lib-fastapi python -m scripts.regenerate_covers --apply --doc-types policy --parts photo --log /app/covers_run.jsonl
  # 정책 보고서를 그림으로 바꾸기(다시 그리지 않는다 — 그 판이 있는 자료만)
  docker exec -w /app nl-lib-fastapi python -m scripts.regenerate_covers --apply --switch --show photo

기록 파일(--log)은 자료마다 한 줄이다 — 만든 판(made)·옛 표지 키·옛 프롬프트·백업 위치가 들어 있어 되돌리기에 쓴다. 같은 기록
파일로 다시 돌리면 그 판을 이미 만든 자료는 건너뛰고 이어 간다. 컨테이너 안 파일은 컨테이너를 다시 만들면 사라지니 끝나면
`docker cp` 로 꺼내 둔다.
되돌리기: 기록의 backup(covers_backup/<시각>/<id>.jpg)을 covers/<id>.jpg 로 다시 복사하고 cover_image_key·cover_prompt 를
old_key·old_prompt 로 돌린다.
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

from services.ingestion.cover_generator import PHOTO, POLICY_COVER, TYPO, cover_key

log = logging.getLogger("regenerate_covers")

DEFAULT_DOC_TYPES = ("policy", "literature", "book")
AVOID_KEEP = 12


def done_parts(log_path: str | None) -> dict[str, set[str]]:
    """기록 파일에서 자료마다 이미 만들어 올린 판 — 같은 기록 파일로 다시 돌리면 그 판은 건너뛴다(올린 것만, 미리보기·실패는 다시).
    판을 적지 않은 옛 기록 줄(목업 전)은 그림(photo)이다."""
    out: dict[str, set[str]] = {}
    if not log_path or not os.path.exists(log_path):
        return out
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "ok":
                out.setdefault(row.get("cnts_id"), set()).update(row.get("made") or [PHOTO])
    return out


def needed_parts(doc_type: str | None, parts: set[str]) -> set[str]:
    """만들 판 — 정책 보고서는 --parts, 문학·도서는 늘 그림 한 판."""
    return set(parts) if doc_type == "policy" else {PHOTO}


def pending(targets: list[dict], done: dict[str, set[str]], limit: int, parts: set[str] = frozenset({PHOTO})) -> list[dict]:
    """만들 판이 남은 자료만 두고 limit 을 건다 — 같은 기록으로 나눠 돌릴 때 다음 묶음으로 넘어가게(앞에 limit 을 걸면 첫 묶음만 돈다)."""
    rest = [t for t in targets if needed_parts(t.get("doc_type"), parts) - done.get(t["cnts_id"], set())]
    return rest[:limit] if limit else rest


def shown_key(cid: str, doc_type: str | None, show: str, has) -> str | None:
    """화면에 보일 키 — 정책 보고서는 --show 판, 없으면 다른 판, 문학·도서는 그림. has(판)는 그 판이 MinIO 에 있는가."""
    order = [show, PHOTO if show == TYPO else TYPO] if doc_type == "policy" else [PHOTO]
    for version in order:
        if has(version):
            return cover_key(cid, version)
    return None


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
    p.add_argument("--parts", default=f"{TYPO},{PHOTO}",
                   help="정책 보고서에서 만들 판(쉼표) — typo(목업, 빠르다)·photo(그림, FLUX). 문학·도서는 늘 photo")
    p.add_argument("--show", choices=[TYPO, PHOTO], default=POLICY_COVER, help="정책 보고서가 화면에 보일 판")
    p.add_argument("--switch", action="store_true",
                   help="만들지 않고 정책 보고서의 표지만 --show 판으로 바꾼다(그 판이 MinIO 에 있는 자료만)")
    args = p.parse_args(argv)
    args.parts = {x.strip() for x in args.parts.split(",") if x.strip()}
    if not args.parts or args.parts - {TYPO, PHOTO}:
        p.error(f"--parts 는 {TYPO}·{PHOTO} 중에서 고른다")
    return args


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
            "kdc": b.kdc or "", "doc_type": b.doc_type or "book", "themes": b.themes or "", "publisher": b.publisher or "",
            "introduction": b.introduction or "", "summary": b.summary or "",
            "old_key": b.cover_image_key, "old_prompt": b.cover_prompt,
        } for b in rows]
    finally:
        db.close()


def _save(cnts_id: str, key: str, prompt: str | None) -> None:
    """한 자료의 표지 키(와 그림 프롬프트 — None 이면 그대로 둔다)를 짧은 트랜잭션으로 고친다."""
    from db.postgres import SyncSessionLocal
    from models.book import Book

    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=cnts_id).first()
        if book is None:
            raise RuntimeError("자료가 DB 에서 사라졌다")
        book.cover_image_key = key
        if prompt is not None:
            book.cover_prompt = prompt
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _exists(client, bucket: str, key: str) -> bool:
    """MinIO 에 그 키가 있는가 — 없음만 False, 연결 장애 같은 다른 오류는 그대로 던진다."""
    from minio.error import S3Error

    try:
        client.stat_object(bucket, key)
        return True
    except S3Error as e:
        if e.code in ("NoSuchKey", "NoSuchObject"):
            return False
        raise


def _switch(args, targets: list[dict], client, bucket: str) -> dict:
    """정책 보고서의 표지 키만 --show 판으로 바꾼다 — 그리지 않는다. 그 판이 없는 자료는 그대로 둔다(missing)."""
    counts = {"switched": 0, "dry": 0, "missing": 0, "fail": 0}
    for i, t in enumerate([t for t in targets if t["doc_type"] == "policy"], 1):
        cid, key = t["cnts_id"], cover_key(t["cnts_id"], args.show)
        try:
            if not _exists(client, bucket, key):
                status = "missing"
            elif not args.apply:
                status = "dry"
            else:
                _save(cid, key, None)
                status = "switched"
        except Exception as e:
            status = "fail"
            log.warning(f"[{cid}] 바꾸기 실패: {type(e).__name__}: {e}")
        counts[status] += 1
        print(f"[{i}] {status} {cid} {t['old_key']} -> {key}", flush=True)
    return counts


async def _run(args) -> dict:
    from minio.commonconfig import CopySource

    from core.config import get_settings
    from services.ingestion import cover_art
    from services.ingestion.cover_generator import compose_cover, render_cover_image, upload_cover_to_minio
    from services.ingestion.cover_typo import render_typo_cover
    from services.ingestion.stages import minio_client

    cfg = get_settings()
    bucket = cfg.MINIO_BUCKET
    targets = _load_targets(args)
    if args.switch:
        return _switch(args, targets, minio_client(), bucket)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    done = done_parts(args.log)
    todo = pending(targets, done, args.limit, args.parts)
    avoid: dict[str, deque] = {g: deque(maxlen=AVOID_KEEP) for g in ("policy", "classical", "modern")}
    counts = {"ok": 0, "dry": 0, "kept_old": 0, "fail": 0}
    client = minio_client() if args.apply else None
    fails_in_row = 0
    log.info(f"대상 {len(targets)}건 중 이번 {len(todo)}건 (기록에 있는 {len(done)}건의 끝낸 판은 건너뜀, 정책 보고서 판 "
             f"{sorted(args.parts)}, {'만들어 올림' if args.apply else '미리보기'})")

    logf = open(args.log, "a", encoding="utf-8") if args.log else None
    try:
        for i, t in enumerate(todo, 1):
            cid = t["cnts_id"]
            need = needed_parts(t["doc_type"], args.parts) - done.get(cid, set())
            row = {"cnts_id": cid, "title": t["title"], "doc_type": t["doc_type"],
                   "old_key": t["old_key"], "old_prompt": t["old_prompt"], "made": []}
            genre = cover_art.genre_of(t["doc_type"], t["title"] or "", t["themes"], t["summary"])
            try:
                if TYPO in need:
                    image = render_typo_cover(cid, t["title"] or cid, t["publisher"])
                    if args.apply:
                        upload_cover_to_minio(cid, image, client, TYPO)
                    row["made"].append(TYPO)
                if PHOTO in need:
                    made = await compose_cover(
                        title=t["title"] or cid, author=t["author"], kdc=t["kdc"], themes=t["themes"],
                        introduction=t["introduction"], summary=t["summary"], book_id=cid, doc_type=t["doc_type"],
                        avoid=list(avoid[genre]),
                    )
                    if not made:
                        # 금지어를 끝내 못 뺀 문학 아닌 자료 — 옛 그림을 그대로 둔다(같은 기록으로 다시 돌리면 다시 해 본다)
                        row["photo"] = "kept_old"
                    else:
                        prompt, scene = made
                        row["prompt"] = prompt
                        avoid[genre].append(cover_art.key_nouns(scene))
                        if args.apply:
                            image = await render_cover_image(prompt)
                            if not image:
                                raise RuntimeError("FLUX 가 빈 이미지를 돌려줬다")
                            photo = cover_key(cid, PHOTO)
                            if not args.no_backup and _exists(client, bucket, photo):
                                backup = f"covers_backup/{stamp}/{cid}.jpg"
                                # 백업이 안 되면 덮어쓰지 않는다 — 옛 그림을 되돌릴 수 없게 된다(이 자료는 실패로 남기고 넘어간다)
                                client.copy_object(bucket, backup, CopySource(bucket, photo))
                                row["backup"] = backup
                            upload_cover_to_minio(cid, image, client)
                        row["made"].append(PHOTO)
                if args.apply and row["made"]:
                    made_now = set(row["made"])
                    key = shown_key(cid, t["doc_type"], args.show,
                                    lambda v: v in made_now or _exists(client, bucket, cover_key(cid, v)))
                    _save(cid, key, row.get("prompt"))
                    row["new_key"] = key
                row["status"] = ("ok" if args.apply else "dry") if row["made"] else "kept_old"
                counts[row["status"]] += 1
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
            print(f"[{i}/{len(todo)}] {row['status']} {'+'.join(row['made']) or '-'} {cid} {(t['title'] or '')[:30]} | "
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
