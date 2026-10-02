"""analyze.py - summarise odl_heap passes (host side). One-off experiment.
usage: python analyze.py TAG [TAG ...]   (first TAG = baseline)
"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).parent / "out"


def load(tag):
    recs = {}
    for line in open(OUT / f"{tag}.jsonl", encoding="utf-8"):
        r = json.loads(line)
        recs[r["id"]] = r
    return recs


def outcome(r):
    if r.get("status") == "ok":
        return "ok"
    if "oom" in (r.get("attempt_kinds") or []):
        return "oom"
    return "other_fail"


def main():
    tags = sys.argv[1:]
    base = load(tags[0])
    for tag in tags:
        recs = load(tag)
        cnt = {"ok": 0, "oom": 0, "other_fail": 0}
        fails = []
        diffs = []
        for did, r in recs.items():
            o = outcome(r)
            cnt[o] += 1
            if o != "ok":
                fails.append(f"{did}:{r.get('status')}:{r.get('wall')}s:hwm{r.get('peak_java_hwm_mb')}")
            b = base.get(did)
            if b and o == "ok" and outcome(b) == "ok" and tag != tags[0]:
                if (r["all_sha1"], r["fill"], r["n_pages"], r["page_sha1"]) != (b["all_sha1"], b["fill"], b["n_pages"], b["page_sha1"]):
                    diffs.append(did)
        normal = [r for d, r in recs.items() if d != "KCI_FI001238691"]
        mx = max(normal, key=lambda r: r.get("peak_java_hwm_mb") or 0)
        print(f"== {tag}: n={len(recs)} {cnt} max_rss_normal={mx.get('peak_java_hwm_mb')}MB ({mx['id']}) "
              f"max_rss_all={max(r.get('peak_java_hwm_mb') or 0 for r in recs.values())}MB "
              f"sum_wall={sum(r.get('wall') or 0 for r in recs.values()):.0f}s")
        print("   fails:", fails)
        if tag != tags[0]:
            print("   output diffs vs", tags[0], ":", diffs)
        if "gc_peak_used_mb" in next(iter(recs.values())):
            top = sorted(recs.values(), key=lambda r: -(r.get("gc_peak_used_mb") or 0))[:15]
            for r in top:
                print(f"   gc {r['id']} used={r['gc_peak_used_mb']} after={r['gc_max_after_mb']} hwm={r['peak_java_hwm_mb']} "
                      f"wall={r['wall']} pages={r['n_pages']} {r['status']} "
                      + json.dumps({k: (v['n_gc'], v['n_full'], v['max_committed_mb']) for k, v in r['gclog'].items()}))
    # heaviest normal docs by baseline RSS
    print("== heaviest normal (baseline):")
    for r in sorted((r for d, r in base.items() if d != "KCI_FI001238691"), key=lambda r: -(r.get("peak_java_hwm_mb") or 0))[:15]:
        line = f"   {r['id']} pages={r['n_pages']} hwm={r['peak_java_hwm_mb']} wall={r['wall']}"
        for tag in tags[1:]:
            x = load(tag).get(r["id"])
            if x:
                line += f" | {tag}: {outcome(x)} hwm={x.get('peak_java_hwm_mb')} wall={x.get('wall')}"
        print(line)


if __name__ == "__main__":
    main()
