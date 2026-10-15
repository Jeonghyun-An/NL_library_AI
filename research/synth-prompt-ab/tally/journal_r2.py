"""2차 출력 요약의 게재지(학술지명) 군말 — '○○ 학술지에 게재된 연구로'·'Korean Journal of …의 연구 결과를 참고하여' 꼴.

'국내 학술지에 발표된'(리뷰 논문의 검토 범위)은 뺀다. 좁은 정규식이라 근사치다.
"""
import glob, json, os, re
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
HEAD = re.compile(r"^(?!.*국내 학술지)[^.]{0,60}?(학술지|학회지|연구|저널|Journal|journal|Review|논문집|학회)[^.]{0,10}?에\s*(게재된|실린|발표된)\s*(논문|연구)")
JN = re.compile(r"(Journal of|Korean Journal|American Journal|학회지에 게재|학술지에 게재|에 게재된 논문|에 게재된 연구)")
c, n, where = Counter(), Counter(), Counter()
for f in sorted(glob.glob(str(here.parent / "gen_r2" / "*.json"))):
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    var = d["variant"]
    for k, s in enumerate(d["sections"], 1):
        for p in s.get("papers", []):
            t = (p.get("summary") or "").strip()
            n[var] += 1
            if (HEAD.search(t) or JN.search(t)) and "국내 학술지에 발표된" not in t[:40]:
                c[var] += 1
                where[(var, d["tag"], d["run"], k)] += 1
print("게재지 군말 요약(편/전체):", {v: f"{c[v]}/{n[v]}" for v in sorted(n)})
for (v, t, r, k), m in sorted(where.items()):
    print(f"  {v} {t} r{r} 절{k}: {m}편")
