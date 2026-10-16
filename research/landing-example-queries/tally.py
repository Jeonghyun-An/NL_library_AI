"""판정 집계 — 말투(질의)마다 판정자 셋의 상위 10건 점수(관련 2·일부 1·무관 0, 만점 20)와 상위 5건 점수, 판정자 사이 차이.

    python tally.py <workflow 결과 JSON> [judge_key 파일]   → tally.json
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    res = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    res = res.get("result", res)
    key = json.loads((HERE / (sys.argv[2] if len(sys.argv) > 2 else "judge_key.json")).read_text(encoding="utf-8"))
    out = {}
    for r in res["results"]:
        topic = r["topic"]
        rows = {}
        for j, judge in enumerate(r["judges"]):
            for lst in (judge or {}).get("lists") or []:
                q = key[topic].get(lst["label"])
                if q is None:
                    continue
                rt = lst["ratings"][:10]
                rows.setdefault(q, []).append({"top10": sum(rt), "top5": sum(rt[:5]), "n": len(rt)})
        out[topic] = {q: {"top10": [x["top10"] for x in v], "top5": [x["top5"] for x in v],
                          "mean10": round(sum(x["top10"] for x in v) / len(v), 1)} for q, v in rows.items()}
        print(f"## {topic}")
        for q, v in sorted(out[topic].items(), key=lambda kv: -kv[1]["mean10"]):
            print(f"  {v['mean10']:5.1f}  top10 {v['top10']}  top5 {v['top5']}  | {q}")
    (HERE / "tally.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
