"""예시 연구 후보 점검 묶음 — 탐색 보고서 절마다·이어가기 절마다 문장 번호를 매긴 감사 묶음 (GET 만)."""
import json, re, sys, urllib.request, urllib.parse
from pathlib import Path
BASE = "http://192.168.12.57:92"
H = {"Accept": "application/json", "x-session-id": "6f7d8c1e-0b7a-4c43-9d0f-3f2e5a1b9c20"}
SENT = re.compile(r"(?<=[.!?])\s+")
def get(path, **q):
    url = BASE + path + ("?" + urllib.parse.urlencode(q) if q else "")
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))
def sents(text):
    return [s.strip() for s in SENT.split((text or "").strip()) if s.strip()]
out = Path("packets"); out.mkdir(exist_ok=True)
for job in sys.argv[1:]:
    j8 = job[:8]
    jd = get(f"/api/research/{job}")
    rep = jd["report"]; ev = rep["evidence"]
    for i, sec in enumerate(rep["sections"], start=1):
        ec = sec.get("evidence_chunks") or {}
        chunk_of = dict(ec) if isinstance(ec, dict) else {e: ids for e, ids in ec}
        used = set(chunk_of)
        items = []
        for s in sents(sec.get("intro")):
            items.append({"part": "intro", "text": s})
        for p in sec.get("papers") or []:
            e = (p.get("evidence") or [None])[0]
            for s in sents(p.get("summary")):
                items.append({"part": "summary", "paper": e, "text": s})
        for f in sec.get("future") or []:
            items.append({"part": "future", "text": f.get("text", "")})
        for n, it in enumerate(items, start=1):
            it["n"] = n
        evid = []
        for e in sorted(used | {p.get("evidence", [None])[0] for p in sec.get("papers") or []} - {None}, key=lambda x: int(x[1:])):
            item = ev.get(e) or {}
            ids = set(chunk_of.get(e) or [])
            chunks = [c["text"] for c in item.get("chunks") or [] if not ids or c["chunk_id"] in ids]
            evid.append({"eid": e, "title": (item.get("meta") or {}).get("title"), "year": (item.get("meta") or {}).get("pub_date"),
                         "chunks": chunks})
        pk = {"job": j8, "kind": "deep_research_section", "question": jd["question"], "heading": sec.get("heading"),
              "sentences": items, "evidence": evid}
        (out / f"{j8}_dr{i}.json").write_text(json.dumps(pk, ensure_ascii=False, indent=1), encoding="utf-8")
    prop = get(f"/api/research/{job}/proposal")
    for key, sec in (prop.get("sections") or {}).items():
        src = get(f"/api/research/{job}/sections/{key}/sources", gen=sec.get("gen_id"))
        items = []
        for pi, p in enumerate(sec.get("paragraphs") or [], start=1):
            for s in sents(p["text"]):
                items.append({"paragraph": pi, "text": s})
        for n, it in enumerate(items, start=1):
            it["n"] = n
        evid = [{"eid": e, "abstract": d.get("abstract"), "excerpt": (d.get("excerpt") or {}).get("text")} for e, d in src.items()]
        outline = prop.get("outline") or {}
        pk = {"job": j8, "kind": "proposal_" + ("gap" if key == "gap" else "prior"), "section": key,
              "topic_title": (outline.get("topic") or {}).get("title"), "research_question": outline.get("question"),
              "group_name": next((g.get("name") for g in outline.get("groups") or [] if g.get("key") == key), None),
              "sentences": items, "evidence": evid}
        (out / f"{j8}_{key}.json").write_text(json.dumps(pk, ensure_ascii=False, indent=1), encoding="utf-8")
    print(j8, sorted(p.name for p in out.glob(f"{j8}_*")))
