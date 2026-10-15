"""400자 이하 근거 대목(자르지 않는 대목) 가운데 문장 끝으로 끝나지 않는 것을 센다.

사용: PYTHONIOENCODING=utf-8 python short.py <jobs 폴더> <출력 txt>   (코드는 SYNTH_AB_APP, 기본 저장소 app/)
"""
import glob, html, json, os, sys
from pathlib import Path
sys.path.insert(0, str(os.environ.get("SYNTH_AB_APP") or Path(__file__).resolve().parents[4] / "app"))
from services.research import synthesizer as S  # noqa: E402
from services.research.state import Chunk  # noqa: E402
n = bad = 0
tails = []
for p in sorted(glob.glob(sys.argv[1] + "/job_*.json")):
    r = json.load(open(p, encoding="utf-8"))["report"]
    seen = set()
    for e in r["evidence"].values():
        for c in e["chunks"]:
            if c["chunk_id"] in seen: continue
            seen.add(c["chunk_id"])
            t = S._BR.sub("\n", html.unescape(c["text"]))
            if len(t) > 400: continue
            n += 1
            ends = S._sentence_ends(t)
            if not ends or ends[-1] < len(t.rstrip()):
                bad += 1
                tails.append(repr(t.rstrip()[-50:]))
open(sys.argv[2], "w", encoding="utf-8").write(f"400자 이하 대목 {n}건 중 문장 끝으로 끝나지 않는 것 {bad}건\n" + "\n".join(tails))
