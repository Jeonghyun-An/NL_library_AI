"""driver.py - sequential per-document runs of one.py for one JAVA_TOOL_OPTIONS setting.

One-off experiment (odl_heap). usage: python /w/driver.py TAG [--gc] [--ids-file F] [--ids ID ...]
  TAG    label written into every record (out/<TAG>.jsonl)
  --gc   append a G1 log (-Xlog:gc,gc+heap+exit:file=...) to the inherited JAVA_TOOL_OPTIONS and summarise
         peak heap used / after-GC / committed per JVM into the record (raw logs copied to /w/gc/<TAG>/)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

W = "/w"


def parse_gc(path):
    before = after = committed = exit_used = exit_total = 0
    n = full = 0
    using = None
    pat = re.compile(r"GC\(\d+\) (Pause .*?) (\d+)M->(\d+)M\((\d+)M\)")
    for line in open(path, errors="replace"):
        if "Using " in line and using is None:
            m = re.search(r"Using (\S+)", line)
            using = m.group(1) if m else None
        m = pat.search(line)
        if m:
            n += 1
            if "Full" in m.group(1):
                full += 1
            b, a, c = int(m.group(2)), int(m.group(3)), int(m.group(4))
            before, after, committed = max(before, b), max(after, a), max(committed, c)
        if "gc,heap,exit" in line:
            m2 = re.search(r"total (\d+)K, used (\d+)K", line)
            if m2:
                exit_total, exit_used = int(m2.group(1)) // 1024, int(m2.group(2)) // 1024
    return {"gc": using, "n_gc": n, "n_full": full, "max_before_mb": before, "max_after_mb": after,
            "max_committed_mb": max(committed, exit_total), "exit_used_mb": exit_used,
            "peak_used_mb": max(before, exit_used)}


def main():
    tag = sys.argv[1]
    args = sys.argv[2:]
    gc = "--gc" in args
    ids = None
    if "--ids-file" in args:
        ids = json.load(open(args[args.index("--ids-file") + 1]))
    if "--ids" in args:
        ids = args[args.index("--ids") + 1:]
    if ids is None:
        ids = [d["id"] for d in json.load(open(f"{W}/docs.json", encoding="utf-8"))]
    os.makedirs(f"{W}/out", exist_ok=True)
    outp = open(f"{W}/out/{tag}.jsonl", "a", encoding="utf-8")
    base = os.environ.get("JAVA_TOOL_OPTIONS")
    print("tag", tag, "JAVA_TOOL_OPTIONS", repr(base), "gc", gc, "docs", len(ids), flush=True)
    for did in ids:
        env = dict(os.environ)
        gdir = f"/tmp/gc/{tag}/{did}"
        if gc:
            os.makedirs(gdir, exist_ok=True)
            env["JAVA_TOOL_OPTIONS"] = ((base + " ") if base else "") + f"-Xlog:gc,gc+heap+exit:file={gdir}/%p.log"
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, f"{W}/one.py", did, tag], env=env, capture_output=True, text=True)
        line = (p.stdout.strip().splitlines() or [""])[-1]
        try:
            rec = json.loads(line)
        except ValueError:
            rec = {"id": did, "tag": tag, "status": "driver_error", "rc": p.returncode, "stderr": p.stderr[-2000:]}
        rec["one_wall"] = round(time.monotonic() - t0, 2)
        if gc:
            gcs = {}
            for fn in sorted(os.listdir(gdir)):
                gcs[fn] = parse_gc(os.path.join(gdir, fn))
            rec["gclog"] = gcs
            rec["gc_peak_used_mb"] = max([g["peak_used_mb"] for g in gcs.values()] or [0])
            rec["gc_max_after_mb"] = max([g["max_after_mb"] for g in gcs.values()] or [0])
            dst = f"{W}/gc/{tag}/{did}"
            os.makedirs(dst, exist_ok=True)
            for fn in os.listdir(gdir):
                shutil.copy(os.path.join(gdir, fn), dst)
        outp.write(json.dumps(rec, ensure_ascii=False) + "\n")
        outp.flush()
        print(did, rec.get("status"), "wall", rec.get("wall"), "odl_s", rec.get("odl_seconds"), "hwm", rec.get("peak_java_hwm_mb"),
              "ru", rec.get("rusage_children_maxrss_mb"), "gc_used", rec.get("gc_peak_used_mb", "-"),
              "n_pages", rec.get("n_pages"), flush=True)


if __name__ == "__main__":
    main()
