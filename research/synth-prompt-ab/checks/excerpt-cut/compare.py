"""운영 잡 4건의 대목으로 대목 창 자르기 전후를 비교한다 — 새 excerpt_text·_narrative(작업 트리 코드)와 예전 규칙.

사용: PYTHONIOENCODING=utf-8 python compare.py <jobs 폴더> <출력 txt>
코드는 SYNTH_AB_APP(기본 저장소 app/ — 이 파일 기준 ../../../../app). '예전' = 4998487 앞의 400자 그냥 자르기.
"""
import glob, html, json, os, re, sys
from pathlib import Path
WT = Path(os.environ.get("SYNTH_AB_APP") or Path(__file__).resolve().parents[4] / "app")
sys.path.insert(0, str(WT))
from services.research import synthesizer as S  # noqa: E402
from services.research.bibliography import has_prose  # noqa: E402
from services.research.state import Chunk  # noqa: E402

SD, OUT = sys.argv[1], sys.argv[2]

def old_excerpt(c):
    return S._BR.sub("\n", html.unescape(c.text))[:400]

def old_narrative(c):
    w = old_excerpt(c)
    rows = [l for l in w.splitlines() if l.count("|") >= 2]
    if w and sum(len(r) for r in rows) >= S._TABLE_SHARE * len(w):
        return False
    st = list(S._SENTENCE_STOP.finditer(w))
    body = w[:st[-1].end()] if st else ""
    return has_prose(body) or bool(S._ENGLISH_VERBS.search(body))

out = []
read_stats = {"read": 0, "over400": 0, "cut_at_sentence": 0, "kept_400": 0, "len_old": 0, "len_new": 0}
flips = []
all_chunks = {}
for p in sorted(glob.glob(SD + "/job_*.json")):
    j = json.load(open(p, encoding="utf-8"))
    r = j["report"]
    byid = {}
    for e in r["evidence"].values():
        for c in e["chunks"]:
            byid[c["chunk_id"]] = Chunk(c["chunk_id"], c["text"], c.get("page_start", 0), c.get("page_end", 0), c.get("score", 0))
    all_chunks.update(byid)
    seen = set()
    for si, s in enumerate(r["sections"], 1):
        for eid, ids in s["evidence_chunks"].items():
            if not ids or ids[0] not in byid or ids[0] in seen:
                continue
            seen.add(ids[0])
            c = byid[ids[0]]
            o, n = old_excerpt(c), S.excerpt_text(c)
            read_stats["read"] += 1
            read_stats["len_old"] += len(o); read_stats["len_new"] += len(n)
            full = S._BR.sub("\n", html.unescape(c.text))
            if len(full) <= 400:
                continue
            read_stats["over400"] += 1
            if len(n) < 400 or n != o:
                read_stats["cut_at_sentence"] += 1
            else:
                read_stats["kept_400"] += 1
            out.append(f"{j['job_id'][:4]} {si}절 {eid} {c.chunk_id} 원문 {len(full)}자 → 예전 {len(o)}자 / 새 {len(n)}자"
                       f" (서술 판정 예전 {old_narrative(c)} / 새 {S._narrative(c)})")
            out.append(f"   예전 끝: …{o[-70:]!r}")
            out.append(f"   새   끝: …{n[-70:]!r}")
for cid, c in all_chunks.items():
    if old_narrative(c) != S._narrative(c):
        flips.append(f"{cid} 예전 {old_narrative(c)} → 새 {S._narrative(c)}: 새 창 끝 …{S.excerpt_text(c)[-80:]!r}")
head = [f"모델이 읽은 대목(절마다 evidence_chunks 첫 항목, 중복 제거): {read_stats}",
        f"근거 대목 전체 {len(all_chunks)}건 중 서술 판정이 바뀐 것: {len(flips)}건", *flips, ""]
# 대목 끝에 저자 연락처가 붙은 청크가 있다 — 이메일 꼴은 가리고 남긴다(저장소에 개인정보를 넣지 않는다)
_EMAIL = re.compile(r"[\w.+-]*@[\w-]+(?:\.[\w-]+)+")
open(OUT, "w", encoding="utf-8").write(_EMAIL.sub("<이메일>", "\n".join(head + out)))
