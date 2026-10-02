"""par.py - N production conversions at once (each one.py = extract_text_opendataloader -> child python -> java).

One-off experiment (odl_heap). usage: python /w/par.py TAG ID [ID ...]
Container-level sampler sums VmRSS of every java process (20 ms) and reads the container cgroup memory.current /
memory.peak. JAVA_TOOL_OPTIONS is inherited from docker -e. Writes /w/out/par_<TAG>.json.
"""
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, "/w")
from one import java_pids, _status_kb, cg_current  # noqa: E402


def main():
    tag, ids = sys.argv[1], sys.argv[2:]
    samples = []
    per = {}
    stop = [False]
    t0 = time.monotonic()

    def run():
        while not stop[0]:
            tot = 0
            pids = java_pids()
            for pid in pids:
                hwm, rss = _status_kb(pid)
                if hwm is None:
                    continue
                per[pid] = max(per.get(pid, 0), hwm)
                tot += rss or 0
            samples.append((round(time.monotonic() - t0, 2), len(pids), tot, cg_current() or 0))
            time.sleep(0.02)

    th = threading.Thread(target=run, daemon=True)
    th.start()
    ps = [subprocess.Popen([sys.executable, "/w/one.py", did, tag], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
          for did in ids]
    outs = []
    for p in ps:
        o, e = p.communicate()
        try:
            outs.append(json.loads(o.strip().splitlines()[-1]))
        except (ValueError, IndexError):
            outs.append({"rc": p.returncode, "stderr": e[-1500:]})
    wall = time.monotonic() - t0
    time.sleep(0.2)
    stop[0] = True
    th.join()
    try:
        cg_peak = int(open("/sys/fs/cgroup/memory.peak").read())
    except OSError:
        cg_peak = None
    peak = max(samples, key=lambda s: s[2])
    res = {
        "tag": tag, "jto": os.environ.get("JAVA_TOOL_OPTIONS"), "ids": ids, "wall": round(wall, 2),
        "peak_total_java_rss_mb": round(peak[2] / 1024), "peak_at_s": peak[0], "java_at_peak": peak[1],
        "max_concurrent_java": max(s[1] for s in samples),
        "sum_per_java_hwm_mb": round(sum(per.values()) / 1024),
        "max_single_java_hwm_mb": round(max(per.values() or [0]) / 1024),
        "n_java_processes": len(per),
        "peak_cgroup_current_mb": round(max(s[3] for s in samples) / 2**20),
        "cgroup_memory_peak_mb": round(cg_peak / 2**20) if cg_peak else None,
        "results": [{k: o.get(k) for k in ("id", "status", "attempt_kinds", "wall", "odl_seconds", "fallback", "n_pages",
                                           "all_sha1", "fill", "peak_java_hwm_mb", "errors")} for o in outs],
        "trace": [(s[0], s[1], round(s[2] / 1024)) for s in samples[:: max(1, len(samples) // 60)]],
    }
    print(json.dumps({k: v for k, v in res.items() if k != "trace"}, ensure_ascii=False, indent=1))
    json.dump(res, open(f"/w/out/par_{tag}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
