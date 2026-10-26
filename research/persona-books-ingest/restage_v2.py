"""페르소나 책 14권 — 표지 쪽 내부 문구를 뺀 PDF(v2)로 원문을 바꾸고 다시 적재할 목록을 만든다 (1회성, 2026-10-23).

첫 판(stage_books.py)은 txt 에서 그린 14권의 1쪽(표지)에 'SKOVIX 소장자료 원문 — 페르소나 에이전트 원문 보관본(2026-10-20)에서
옮김' 을 넣었고, 그 글이 검색 대목(청크)과 원문 뷰어 1쪽에 그대로 보였다. render_pdfs.py 에서 그 줄만 뺀 v2(쪽 수 같음, 2쪽부터
글 같음)로 바꾼다. nl-lib-fastapi 컨테이너 안에서 돈다(앱 설정으로 DB·MinIO·Milvus 에 붙는다). 같은 폴더의 pdf/<id>.pdf(v2)와
sha256s.txt 를 읽는다(bundle_v2.py 가 만든다). --ids 는 ID 를 띄어 쓰거나 'rest'(소나기를 뺀 13권)·'all'(14권).

    R="docker exec -w /app -e PYTHONPATH=/app nl-lib-fastapi python /app/data/persona_books/v2/restage_v2.py"
    $R snapshot --ids all                              # 읽기만 — 다시 적재 전 14행의 요약 글을 catalog_before.json 에
    $R report   --ids PSN-SONAGI                       # 읽기만 — 카탈로그·섹션·Milvus 청크·원문·썸네일 캐시
    $R stage    --ids PSN-SONAGI --manifest canary [--apply]
    $R thumbs   --ids … [--apply]                      # 잡이 끝난 뒤 옛 1쪽으로 다시 생긴 썸네일 캐시 치우기
    $R restore  --ids … [--apply]                      # 되돌리기 — 백업한 v1 을 같은 키로

카탈로그·book_sections·Milvus 에는 쓰지 않는다. 다시 적재는 적재 작업(params reembed)이 책 하나씩 한다 — 그 경로의 지우기는
모두 그 책(book_id)으로 좁혀져 있다. 이 스크립트가 지키는 것:
- 14권 허용 목록 밖이거나, 카탈로그 행이 이번 묶음(extra.acquisition.batch)의 txt 렌더본(rendered)·문학이 아닌 ID 는 손대지
  않는다. 금도끼·우온달·Griffis 는 PDF 를 그대로 옮겨 문구가 없고, Griffis 는 스캔본이라 Qwen 이 꺼진 지금 다시 적재하면 OCR 쪽
  본문을 잃는다.
- MinIO 는 정확한 키만 쓰고 지운다(접두어로 지우지 않는다). 원문 originals/<id>/<id>.pdf 가 v1(카탈로그 sha256)도 v2 도 아니면
  멈춘다. 옛 판은 originals/ 밖 backup/persona-books-20261023-v1/ 에 먼저 올리고 해시를 확인한 뒤에 덮는다 — 원문 목록을 훑는
  뷰어(_resolve_original_key 는 폴더의 첫 객체를 연다)·잡 검증에 섞이지 않게. 새 키(.v2.pdf)를 같은 폴더에 두면 사전순으로 옛
  판이 먼저 열려 같은 키에 덮는다.
- Milvus 는 Collection(name).query 로 읽기만 한다 — indexer.ensure_collection 은 부르지 않는다(스키마가 다르고
  MILVUS_RECREATE_ON_MISMATCH 이면 컬렉션을 통째로 지우는 길이다).
- 검사가 하나라도 실패하면 아무것도 쓰지 않고 멈춘다. 쓰는 도중 끊겨도 책마다 '백업 → 덮기' 순서라 다시 돌리면 이어진다.
- DB 세션은 읽고 바로 닫는다 — 트랜잭션을 연 채 MinIO·Milvus 를 기다리지 않는다(함정 18).
"""
import argparse
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import fitz
from minio.error import S3Error
from sqlalchemy import select, text

from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.book import Book
from services.ingestion.stages import minio_client

HERE = Path(__file__).resolve().parent
BATCH = "persona-books-20261023"
MANIFEST_DIR = f"manifests/{BATCH}-v2"
BACKUP = f"backup/{BATCH}-v1"
CANARY = "PSN-SONAGI"
ALLOW = ("PSN-MANSEJEON", "PSN-SONAGI", "PSN-JEOKBIN", "PSN-CHUNHYANG", "PSN-HEOSAENG", "PSN-BEAUTY-BEAST", "PSN-RED-CAP",
         "PSN-STUDY-SCARLET", "PSN-DOG-FLANDERS", "PSN-ROBIN-HOOD", "PSN-BULFINCH", "PSN-ANDERSEN", "PSN-DADDY-LONG-LEGS",
         "PSN-PERRAULT")
NOTE = ("SKOVIX 소장자료", "페르소나 에이전트")
NOTE_SQL = "(full_text LIKE '%페르소나 에이전트%' OR full_text LIKE '%SKOVIX 소장자료%')"
CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f�]")
JOB_PARAMS = {
    "canary": {"reembed": True, "skip_cover": True, "max_attempts": 1, "high_water": 1, "kind": "literature_reembed"},
    "main": {"reembed": True, "skip_cover": True, "high_water": 1, "kind": "literature_reembed"},
}
LOG = HERE / "restage_log.jsonl"
cfg = get_settings()
sys.stdout.reconfigure(encoding="utf-8")


def sha(b: bytes | None) -> str | None:
    return hashlib.sha256(b).hexdigest() if b is not None else None


def get_object(client, key: str) -> bytes | None:
    """객체가 없을 때만 None — 연결 오류 같은 다른 실패는 그대로 올려 멈춘다."""
    try:
        r = client.get_object(cfg.MINIO_BUCKET, key)
    except S3Error as e:
        if e.code in ("NoSuchKey", "NoSuchObject"):
            return None
        raise
    try:
        return r.read()
    finally:
        r.close()
        r.release_conn()


def put_object(client, key: str, data: bytes, content_type: str) -> None:
    client.put_object(cfg.MINIO_BUCKET, key, io.BytesIO(data), len(data), content_type=content_type)
    if sha(get_object(client, key)) != sha(data):
        sys.exit(f"멈춤 — {key} 를 올린 뒤 다시 받은 해시가 다르다")


def resolve_ids(raw: list[str]) -> list[str]:
    if raw == ["all"]:
        return list(ALLOW)
    ids = [i for i in ALLOW if i != CANARY] if raw == ["rest"] else list(dict.fromkeys(raw))
    bad = [i for i in ids if i not in ALLOW]
    if not ids or bad:
        sys.exit(f"멈춤 — --ids 는 허용 목록 14권 안에서만(밖: {bad})")
    return ids


def load_v2_sha() -> dict:
    p = HERE / "sha256s.txt"
    if not p.exists():
        return {}
    pairs = (line.split() for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
    return {cid: digest for digest, cid in pairs}


def catalog(ids: list[str]) -> dict:
    """14행을 읽고 세션을 바로 닫는다(SELECT 만)."""
    t = Book.__table__
    db = SyncSessionLocal()
    try:
        rows = db.execute(select(t.c.cnts_id, t.c.title, t.c.doc_type, t.c.extra, t.c.is_embedded, t.c.ingest_state,
                                 t.c.summary, t.c.themes, t.c.introduction, t.c.cover_image_key, t.c.cover_prompt)
                          .where(t.c.cnts_id.in_(ids))).all()
        return {r.cnts_id: r for r in rows}
    finally:
        db.close()


def acquisition(row) -> dict:
    return ((row.extra or {}).get("acquisition") or {}) if row is not None else {}


def row_problems(row) -> list[str]:
    acq = acquisition(row)
    out = []
    if acq.get("batch") != BATCH:
        out.append(f"batch={acq.get('batch')!r}")
    if acq.get("rendered") is not True:
        out.append("txt 렌더본(rendered)이 아니다")
    if not acq.get("sha256"):
        out.append("카탈로그에 v1 sha256 이 없다")
    if row.doc_type != "literature":
        out.append(f"doc_type={row.doc_type!r}")
    return out


def pdf_problems(new: bytes, old: bytes) -> list[str]:
    """v2 가 v1 과 표지 쪽만 다른지 — 쪽 수, 1쪽 문구, 2쪽부터 글, 제어 문자(NUL 이 든 본문은 DB 저장이 실패한다)."""
    a, b = fitz.open(stream=old, filetype="pdf"), fitz.open(stream=new, filetype="pdf")
    out = []
    if a.page_count != b.page_count:
        out.append(f"쪽 수 {a.page_count} → {b.page_count}")
    if any(n in b[0].get_text() for n in NOTE):
        out.append("1쪽에 문구가 남았다")
    diff = next((k + 1 for k in range(1, min(a.page_count, b.page_count)) if a[k].get_text() != b[k].get_text()), None)
    if diff:
        out.append(f"{diff}쪽 글이 옛 판과 다르다")
    if CONTROL.search("".join(p.get_text() for p in b)):
        out.append("제어 문자가 있다")
    return out


def original_objects(client, cid: str) -> list[str]:
    return [o.object_name for o in client.list_objects(cfg.MINIO_BUCKET, prefix=f"originals/{cid}/", recursive=True)]


def job_command(name: str) -> str:
    body = {"name": f"{BATCH}-v2-{name}", "manifest_key": f"{MANIFEST_DIR}/{name}.jsonl", "params": JOB_PARAMS[name]}
    return ("docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs "
            f"-H 'Content-Type: application/json' -d '{json.dumps(body, ensure_ascii=False)}'")


def log_writable() -> None:
    """쓰기 전에 기록 파일을 열 수 있는지 본다 — 첫 책만 바뀐 채 기록 없이 멈추지 않게."""
    try:
        with open(LOG, "a", encoding="utf-8"):
            pass
    except OSError as e:
        sys.exit(f"멈춤 — 기록 파일 {LOG} 를 쓸 수 없다: {e}")


def log_line(rec: dict) -> None:
    rec["at"] = datetime.now(timezone.utc).isoformat()
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def ln(s) -> int:
    return len(s) if s else 0


# ── snapshot·report(읽기만) ──────────────────────────────────────

def snapshot(ids: list[str]) -> None:
    """다시 적재의 마무리 단계는 summary·themes·introduction 을 새 값으로 무조건 덮는다(LLM 이 실패하면 NULL —
    stages.run_finalize). 되돌릴 수 있게 지금 글을 남긴다. 이미 있으면 덮지 않는다(첫 스냅숏이 '다시 적재 전'이다)."""
    out = HERE / "catalog_before.json"
    if out.exists():
        sys.exit(f"멈춤 — {out} 가 이미 있다(다시 적재 전 스냅숏을 덮지 않는다)")
    rows = catalog(ids)
    data = {cid: {"summary": r.summary, "themes": r.themes, "introduction": r.introduction, "extra": r.extra,
                  "cover_image_key": r.cover_image_key, "cover_prompt": r.cover_prompt}
            for cid, r in rows.items()}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out} — {len(data)}행 (요약 빈 행 {[c for c, d in data.items() if not d['summary']]})")


def report(ids: list[str]) -> None:
    from pymilvus import Collection, connections

    rows = catalog(ids)
    db = SyncSessionLocal()
    try:
        secs = {cid: db.execute(text(f"SELECT count(*), count(summary), coalesce(sum({NOTE_SQL}::int), 0) "
                                     "FROM book_sections WHERE book_id = :i"), {"i": cid}).one() for cid in ids}
    finally:
        db.close()
    if not connections.has_connection("default"):
        connections.connect(host=cfg.MILVUS_HOST, port=cfg.MILVUS_PORT)
    col = Collection(cfg.MILVUS_COLLECTION)          # 읽기만 — ensure_collection 을 부르지 않는다
    v2sha, client = load_v2_sha(), minio_client()
    for cid in ids:
        row = rows.get(cid)
        if row is None:
            print(f"{cid}: 카탈로그 행 없음")
            continue
        extra = row.extra or {}
        sec = secs[cid]
        chunks = col.query(expr=f'book_id == "{cid}"', output_fields=["chunk_idx", "page_start", "text"], limit=16384,
                           consistency_level="Strong")
        note = sum(1 for c in chunks if any(n in (c.get("text") or "") for n in NOTE))
        objs = original_objects(client, cid)
        cur = sha(get_object(client, f"originals/{cid}/{cid}.pdf"))
        state = ("v2" if cur and cur == v2sha.get(cid) else "v1" if cur and cur == acquisition(row).get("sha256")
                 else f"?({cur})")
        backup = get_object(client, f"{BACKUP}/{cid}.pdf") is not None
        thumb = get_object(client, f"thumbnails/{cid}.jpg") is not None
        print(f"{cid}: embedded={row.is_embedded} state={row.ingest_state} 요약 {ln(row.summary)} 테마 {ln(row.themes)} "
              f"소개 {ln(row.introduction)} 줄거리 {ln(extra.get('plot'))} 읽고난후 {ln(extra.get('read_effect'))} "
              f"표지키={row.cover_image_key} 표지프롬프트md5={hashlib.md5((row.cover_prompt or '').encode()).hexdigest()[:8]}")
        print(f"   섹션 {sec[0]}(요약 {sec[1]}, 문구 {sec[2]}) · 청크 {len(chunks)}(문구 {note}, 메타 "
              f"{sum(1 for c in chunks if c.get('chunk_idx', 0) < 0)}, 0쪽 {sum(1 for c in chunks if not c.get('page_start'))}) · "
              f"원문 {objs} = {state} · 백업 {'있음' if backup else '없음'} · 썸네일 캐시 {'있음' if thumb else '없음'}")


# ── stage ────────────────────────────────────────────────────────

def stage(ids: list[str], manifest: str | None, apply: bool) -> None:
    v2sha, client = load_v2_sha(), minio_client()
    rows = catalog(ids)
    plan, errors = [], []
    for cid in ids:
        row = rows.get(cid)
        if row is None:
            errors.append(f"{cid}: 카탈로그 행 없음")
            continue
        probs = row_problems(row)
        if probs:
            errors += [f"{cid}: {e}" for e in probs]
            continue
        key, bk = f"originals/{cid}/{cid}.pdf", f"{BACKUP}/{cid}.pdf"
        objs = original_objects(client, cid)
        if objs != [key]:
            errors.append(f"{cid}: originals/{cid}/ 에 {objs} — {key} 하나여야 한다")
            continue
        new_path = HERE / "pdf" / f"{cid}.pdf"
        new = new_path.read_bytes() if new_path.exists() else None
        if new is None or not v2sha.get(cid) or sha(new) != v2sha[cid]:
            errors.append(f"{cid}: 새 PDF 가 없거나 sha256s.txt 와 다르다")
            continue
        cur, held = get_object(client, key), get_object(client, bk)
        v1 = acquisition(row)["sha256"]
        if sha(cur) == v2sha[cid]:
            state, old = "이미 v2", held
            if old is None or sha(old) != v1:
                errors.append(f"{cid}: 원문은 이미 v2 인데 백업 v1 이 없거나 다르다")
                continue
        elif sha(cur) == v1:
            state, old = "v1 → v2", cur
            if held is not None and sha(held) != v1:
                errors.append(f"{cid}: 백업 키 {bk} 에 v1 이 아닌 파일이 있다")
                continue
        else:
            errors.append(f"{cid}: 원문이 v1(카탈로그 sha256)도 v2 도 아니다 — 누가 바꿨는지 먼저 확인")
            continue
        probs = pdf_problems(new, old)
        if probs:
            errors.append(f"{cid}: 새 PDF 검사 실패 {probs}")
            continue
        thumb = get_object(client, f"thumbnails/{cid}.jpg")
        plan.append({"id": cid, "title": row.title, "key": key, "backup": bk, "state": state, "new": new, "old": old,
                     "need_backup": held is None, "thumb": thumb})

    for p in plan:
        print(f"  {p['id']:20} {p['state']:8} {len(p['old'])} → {len(p['new'])}B · 백업 {'만듦' if p['need_backup'] else '있음'} "
              f"· 썸네일 캐시 {'치움' if p['thumb'] is not None else '없음'} · {p['title']}")
    if errors:
        sys.exit("멈춤 — 아무것도 쓰지 않았다:\n  " + "\n  ".join(errors))
    if manifest not in JOB_PARAMS:
        sys.exit("멈춤 — --manifest canary|main 을 줘야 한다")
    if manifest == "canary" and ids != [CANARY]:
        sys.exit(f"멈춤 — canary 적재 목록은 {CANARY} 한 권만")
    if manifest == "main" and CANARY in ids:
        sys.exit(f"멈춤 — main 적재 목록에 카나리 {CANARY} 를 다시 넣지 않는다")
    mkey = f"{MANIFEST_DIR}/{manifest}.jsonl"
    mdata = ("\n".join(json.dumps({"book_id": p["id"], "object_key": p["key"], "size": len(p["new"]), "title": p["title"]},
                                  ensure_ascii=False) for p in plan) + "\n").encode("utf-8")
    held_manifest = get_object(client, mkey)
    if held_manifest is not None and held_manifest != mdata:
        sys.exit(f"멈춤 — {mkey} 가 이미 있고 내용이 다르다(덮지 않는다)")
    if not (HERE / "catalog_before.json").exists():
        sys.exit("멈춤 — 먼저 snapshot --ids all 로 다시 적재 전 요약 글을 남긴다")
    if not apply:
        print(f"\n미리 보기만 했다. 실제로 하려면 --apply (적재 목록 {mkey})")
        return

    log_writable()
    for p in plan:
        if p["state"] == "v1 → v2":
            if p["need_backup"]:
                put_object(client, p["backup"], p["old"], "application/pdf")
            put_object(client, p["key"], p["new"], "application/pdf")
        if p["thumb"] is not None:
            tb = f"{BACKUP}/thumbnails/{p['id']}.jpg"
            if get_object(client, tb) is None:
                put_object(client, tb, p["thumb"], "image/jpeg")
            client.remove_object(cfg.MINIO_BUCKET, f"thumbnails/{p['id']}.jpg")
        log_line({"cmd": "stage", "id": p["id"], "state": p["state"], "v1": sha(p["old"]), "v2": sha(p["new"]),
                  "thumb_removed": p["thumb"] is not None})
        print(f"바꿈 {p['key']} ({p['state']})")
    if held_manifest is None:
        put_object(client, mkey, mdata, "application/x-ndjson")
    print(f"\n적재 목록 {mkey} ({len(plan)}권). 다음 — 잡 만들기(한 번만. validation_report 의 to_ingest 가 {len(plan)} 이고"
          " 나머지가 비어야 한다):")
    print("  " + job_command(manifest))


# ── thumbs·restore ───────────────────────────────────────────────

def thumbs(ids: list[str], apply: bool) -> None:
    """적재 도중 옛 원문을 읽은 표지 요청이 캐시를 옛 1쪽으로 다시 만들었을 수 있다 — 원문이 v2 인 책만 다시 치운다."""
    v2sha, client = load_v2_sha(), minio_client()
    if apply:
        log_writable()
    for cid in ids:
        key, tk = f"originals/{cid}/{cid}.pdf", f"thumbnails/{cid}.jpg"
        cur = sha(get_object(client, key))
        is_v2 = bool(cur) and cur == v2sha.get(cid)
        has = get_object(client, tk) is not None
        print(f"  {cid:20} 원문 {'v2' if is_v2 else 'v2 아님'} · 썸네일 캐시 {'있음' if has else '없음'}")
        if apply and is_v2 and has:
            client.remove_object(cfg.MINIO_BUCKET, tk)
            log_line({"cmd": "thumbs", "id": cid})
    if not apply:
        print("미리 보기만 했다. 치우려면 --apply (원문이 v2 인 책의 캐시만 지운다 — 다음 표지 요청이 새 1쪽으로 다시 그린다)")


def restore(ids: list[str], apply: bool) -> None:
    """지금 원문이 v1 이나 v2 일 때만, 백업 v1 을 같은 키로 되돌린다(v2 는 out/v2 에 있어 잃지 않는다)."""
    v2sha, client = load_v2_sha(), minio_client()
    rows = catalog(ids)
    plan, errors = [], []
    for cid in ids:
        row = rows.get(cid)
        v1 = acquisition(row).get("sha256")
        key = f"originals/{cid}/{cid}.pdf"
        old = get_object(client, f"{BACKUP}/{cid}.pdf")
        if not v1 or old is None or sha(old) != v1:
            errors.append(f"{cid}: 백업 v1 이 없거나 카탈로그 sha256 과 다르다")
            continue
        if original_objects(client, cid) != [key]:
            errors.append(f"{cid}: originals/{cid}/ 에 {key} 하나만 있어야 한다")
            continue
        cur = sha(get_object(client, key))
        if cur not in (v1, v2sha.get(cid)):
            errors.append(f"{cid}: 지금 원문이 v1 도 v2 도 아니다 — 덮지 않는다")
            continue
        plan.append((cid, old, row.title))
    if errors:
        sys.exit("멈춤 — 아무것도 쓰지 않았다:\n  " + "\n  ".join(errors))
    for cid, old, _ in plan:
        print(f"  {cid:20} 백업 v1({len(old)}B) → originals/{cid}/{cid}.pdf")
    if not apply:
        print("미리 보기만 했다. 되돌리려면 --apply")
        return
    log_writable()
    name = "restore-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    for cid, old, _ in plan:
        put_object(client, f"originals/{cid}/{cid}.pdf", old, "application/pdf")
        if get_object(client, f"thumbnails/{cid}.jpg") is not None:
            client.remove_object(cfg.MINIO_BUCKET, f"thumbnails/{cid}.jpg")
        log_line({"cmd": "restore", "id": cid})
    mkey = f"{MANIFEST_DIR}/{name}.jsonl"
    put_object(client, mkey, ("\n".join(json.dumps({"book_id": c, "object_key": f"originals/{c}/{c}.pdf", "size": len(o),
                                                   "title": t}, ensure_ascii=False) for c, o, t in plan) + "\n").encode(),
               "application/x-ndjson")
    JOB_PARAMS[name] = JOB_PARAMS["main"]
    print(f"되돌림. 다시 적재하려면(옛 문구가 다시 들어간다):\n  {job_command(name)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["snapshot", "report", "stage", "thumbs", "restore"])
    ap.add_argument("--ids", nargs="+", required=True)
    ap.add_argument("--manifest", choices=["canary", "main"])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    ids = resolve_ids(args.ids)
    if args.cmd == "snapshot":
        snapshot(ids)
    elif args.cmd == "report":
        report(ids)
    elif args.cmd == "stage":
        stage(ids, args.manifest, args.apply)
    elif args.cmd == "thumbs":
        thumbs(ids, args.apply)
    else:
        restore(ids, args.apply)


if __name__ == "__main__":
    main()
