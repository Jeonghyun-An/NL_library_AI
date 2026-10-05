"""vlm_trunc_probe.py — VLM 이 max_tokens 에서 잘린 쪽이 '되풀이'인지 '빽빽한 본문'인지 가린다(1회성, 읽기 전용).
본 잡에서 vlm_truncated 가 있던 문서를 운영과 같은 extract_text 로 다시 추출하며 VLM 응답을 기록하고,
finish_reason=length 인 쪽은 같은 요청을 max_tokens 를 올려 한 번 더 보낸다. DB·MinIO 에는 쓰지 않는다."""
import asyncio, json, os, shutil, statistics, tempfile, time
import httpx
from sqlalchemy import text
from db.postgres import SyncSessionLocal
from core.config import get_settings
from services.ingestion import extractor, page_routing
from services.ingestion.stages import minio_client

cfg = get_settings()
JOB, DEP = os.environ["JOB"], os.environ["DEP"]
N_DOCS = int(os.environ.get("N_DOCS", "2"))
HIGH = int(os.environ.get("HIGH_TOKENS", "8192"))
OUT = "/app/data/round07/vlm_trunc_probe.json"
_Orig = httpx.AsyncClient
calls = []

class Rec(_Orig):
    async def post(self, url, *a, **kw):
        resp = await super().post(url, *a, **kw)
        if str(url).endswith("/chat/completions"):
            rec = {"payload": kw.get("json")}
            try:
                body = resp.json(); ch = body["choices"][0]; usage = body.get("usage") or {}
                rec.update(finish=ch.get("finish_reason"), content=(ch.get("message") or {}).get("content") or "",
                           prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"))
            except Exception as e:
                rec["error"] = repr(e)
            calls.append(rec)
        return resp

httpx.AsyncClient = Rec  # extractor 가 만드는 클라이언트가 이것이 된다

def pick_docs():
    db = SyncSessionLocal()
    try:
        return db.execute(text(
            "SELECT book_id, source_key, (meta->>'vlm_truncated')::int, (meta->>'pages')::int FROM ingest_job_items "
            "WHERE job_id = :job AND status = 'done' AND finished_at > CAST(:dep AS timestamptz) "
            "AND (meta->>'vlm_truncated')::int > 0 AND (meta->>'pages')::int <= 40 "
            "ORDER BY (meta->>'vlm_truncated')::int DESC, id LIMIT :n"), {"job": JOB, "dep": DEP, "n": N_DOCS}).fetchall()
    finally:
        db.close()

async def max_model_len():
    async with _Orig() as c:
        r = await c.get(f"{cfg.VLM_BASE_URL}/models", timeout=30)
        return int(r.json()["data"][0].get("max_model_len") or 16384)

async def reask(payload, max_tokens):
    async with _Orig() as c:
        r = await c.post(f"{cfg.VLM_BASE_URL}/chat/completions", json=dict(payload, max_tokens=max_tokens), timeout=900)
        if r.status_code != 200:
            return {"status": r.status_code, "body": r.text[:200]}
        body = r.json(); ch = body["choices"][0]
        return {"status": 200, "finish": ch.get("finish_reason"), "content": (ch.get("message") or {}).get("content") or "",
                "completion_tokens": (body.get("usage") or {}).get("completion_tokens")}

def shape(raw):
    trimmed, degenerate = page_routing.trim_repetition(raw)
    return len(raw), len(trimmed), degenerate

async def main():
    mml = await max_model_len()
    docs = pick_docs()
    print(f"VLM max_model_len={mml}, VLM_MAX_TOKENS={cfg.VLM_MAX_TOKENS}, 문서 {len(docs)}개", flush=True)
    rows = []
    for book_id, key, truncated, pages in docs:
        tmp = tempfile.mkdtemp(); path = os.path.join(tmp, f"{book_id}.pdf")
        minio_client().fget_object(cfg.MINIO_BUCKET, key, path)
        start, t0 = len(calls), time.monotonic()
        await extractor.extract_text(path, book_id)
        shutil.rmtree(tmp, ignore_errors=True)
        mine = calls[start:]
        print(f"\n[{book_id}] {pages}쪽 · 본 잡 vlm_truncated {truncated} · 다시 추출 {time.monotonic() - t0:.0f}초 · "
              f"VLM 호출 {len(mine)} · 이번 length {sum(c.get('finish') == 'length' for c in mine)}", flush=True)
        for i, c in enumerate(mine):
            if c.get("finish") != "length":
                continue
            raw = c["content"]; n4, t4, d4 = shape(raw)
            kind = "퇴화(되풀이만)" if d4 else ("되풀이 꼬리" if t4 < 0.9 * n4 else "되풀이 없음")
            hi = min(HIGH, mml - (c.get("prompt_tokens") or 0) - 32)
            r = await reask(c["payload"], hi) if hi > cfg.VLM_MAX_TOKENS else {"status": "자리 없음"}
            if r.get("status") == 200:
                nh, th, dh = shape(r["content"]) if r["finish"] == "length" else (len(r["content"]), len(r["content"]), False)
                after = f"{hi}토큰 → finish={r['finish']}, {r['completion_tokens']}토큰, {nh}자"
                if r["finish"] == "length":
                    after += f"(되풀이 걷으면 {th}자{', 퇴화' if dh else ''})"
            else:
                nh = th = dh = None
                after = f"{hi}토큰 다시 묻기 실패: {r}"
            tail = raw[-60:].replace("\n", " ")
            print(f"  호출 {i}: 입력 {c.get('prompt_tokens')}토큰 · 4096 응답 {n4}자(되풀이 걷으면 {t4}자) → {kind} | {after} | 끝: …{tail}", flush=True)
            rows.append({"book_id": book_id, "call": i, "prompt_tokens": c.get("prompt_tokens"), "chars_4096": n4,
                         "trimmed_4096": t4, "degenerate_4096": d4, "kind": kind, "high_max_tokens": hi,
                         "high": {k: v for k, v in r.items() if k != "content"}, "chars_high": nh, "trimmed_high": th,
                         "degenerate_high": dh, "tail_4096": raw[-300:]})
        stops = [c.get("completion_tokens") or 0 for c in mine if c.get("finish") == "stop"]
        if stops:
            print(f"  정상 종료 {len(stops)}쪽 출력 토큰: 중앙 {statistics.median(stops):.0f} · 최대 {max(stops)} · 3,500 넘음 {sum(t > 3500 for t in stops)}", flush=True)
    kinds, fins = {}, {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        f = r["high"].get("finish") or str(r["high"].get("status"))
        fins[f] = fins.get(f, 0) + 1
    print(f"\n요약 — 4096 에서 잘린 쪽 {len(rows)}: {kinds} · 한도를 올려 다시 물은 결과: {fins}")
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(rows, fp, ensure_ascii=False, indent=1)
    print(f"자세한 기록: /data/nl-lib/data/round07/vlm_trunc_probe.json")

asyncio.run(main())
