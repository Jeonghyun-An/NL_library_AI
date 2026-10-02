"""summarize_out.py - README 의 표·백분위를 out/ 에서 다시 낸다(1회성, odl_heap). usage: python summarize_out.py

61건 4회(nocap·xmx3g·xmx2g·xmx1g)의 결과·추출 동일 수·시간 합, 경계 찾기(bis_*), 688건 화면 검사(screen_xmx2g)의
java RSS 최고치(VmHWM — 힙 사용량 gc_used 가 아니다) 중앙값·p95·p99, 메모리 부족 문서를 찍는다.
"""
import collections
import glob
import json
import os
import statistics

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def load(tag):
    rows = []
    with open(os.path.join(OUT, tag + ".jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("{"):
                rows.append(json.loads(line))
    return rows


base = {r["id"]: r for r in load("nocap")}
print("== 61건")
for tag in ["nocap", "xmx3g", "xmx2g", "xmx1g"]:
    rows = load(tag)
    status = collections.Counter(r["status"] for r in rows)
    same = sum(1 for r in rows if base.get(r["id"], {}).get("all_sha1") == r["all_sha1"])
    print(tag, dict(status), "같은 추출", same, "시간 합", round(sum(r["wall"] for r in rows), 1))
print("== 경계 찾기")
for path in sorted(glob.glob(os.path.join(OUT, "bis_*.jsonl"))):
    tag = os.path.basename(path)[:-6]
    rows = load(tag)
    print(tag, f"{sum(r['status'] == 'ok' for r in rows)}/{len(rows)} 성공",
          [r["id"][-7:] for r in rows if r["status"] != "ok"])
print("== 688건(2g)")
rows = load("screen_xmx2g")
rss = sorted(r["peak_java_hwm_mb"] for r in rows)
print("n", len(rows), dict(collections.Counter(r["status"] for r in rows)))
print("java RSS(MB) 중앙값", statistics.median(rss), "p95", rss[int(len(rss) * 0.95)], "p99", rss[int(len(rss) * 0.99)])
print("메모리 부족", [(r["id"], r["n_pages"], r["peak_java_hwm_mb"]) for r in rows if r["status"] != "ok"])
