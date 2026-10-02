"""one.py - one production ODL conversion (round07 extract_text_opendataloader) with java memory sampling.

One-off experiment (odl_heap). Runs inside landsoftdocker/nl-lib-fastapi:latest with round07 /app mounted.
usage: python /w/one.py DOC_ID TAG
JAVA_TOOL_OPTIONS is whatever this process inherited (docker -e or the driver); the conversion's child python and java
inherit it exactly as in production (create_subprocess_exec with env=None).
Prints one JSON line on stdout.
"""
import asyncio
import hashlib
import json
import logging
import os
import resource
import sys
import threading
import time

sys.path.insert(0, "/app")
PDF = "/pdf"


def _status_kb(pid):
    hwm = rss = None
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmHWM:"):
                    hwm = int(line.split()[1])
                elif line.startswith("VmRSS:"):
                    rss = int(line.split()[1])
    except OSError:
        pass
    return hwm, rss


def java_pids():
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/comm") as f:
                if f.read().strip() == "java":
                    out.append(int(d))
        except OSError:
            pass
    return out


def cg_current():
    try:
        with open("/sys/fs/cgroup/memory.current") as f:
            return int(f.read())
    except OSError:
        return None


class Sampler(threading.Thread):
    """Polls every java process in the container: per-pid max VmHWM / VmRSS, peak of the summed VmRSS."""

    def __init__(self, period=0.02):
        super().__init__(daemon=True)
        self.period = period
        self.stop_flag = False
        self.per = {}  # pid -> dict
        self.peak_total_rss_kb = 0
        self.peak_cg = 0
        self.t0 = time.monotonic()
        self.max_concurrent = 0

    def run(self):
        while not self.stop_flag:
            now = round(time.monotonic() - self.t0, 2)
            tot = 0
            pids = java_pids()
            self.max_concurrent = max(self.max_concurrent, len(pids))
            for pid in pids:
                hwm, rss = _status_kb(pid)
                if hwm is None:
                    continue
                e = self.per.setdefault(pid, {"pid": pid, "hwm_kb": 0, "rss_max_kb": 0, "first": now, "last": now})
                e["hwm_kb"] = max(e["hwm_kb"], hwm)
                e["rss_max_kb"] = max(e["rss_max_kb"], rss or 0)
                e["last"] = now
                tot += rss or 0
            self.peak_total_rss_kb = max(self.peak_total_rss_kb, tot)
            c = cg_current()
            if c:
                self.peak_cg = max(self.peak_cg, c)
            time.sleep(self.period)


def classify(err):
    if "OutOfMemoryError" in err:
        return "oom"
    if "초 초과" in err:
        return "timeout"
    if "SIGKILL" in err or "exit -9" in err:
        return "killed"
    return "other"


def main():
    did, tag = sys.argv[1], sys.argv[2]
    from services.ingestion import extractor

    logs = []

    class _H(logging.Handler):
        def emit(self, r):
            logs.append(r.getMessage())

    lg = logging.getLogger(extractor.__name__)
    lg.setLevel(logging.INFO)
    lg.addHandler(_H(level=logging.INFO))
    lg.propagate = False

    s = Sampler()
    s.start()
    t0 = time.monotonic()
    r = asyncio.run(extractor.extract_text_opendataloader(f"{PDF}/{did}.pdf", did))
    wall = time.monotonic() - t0
    time.sleep(0.1)
    s.stop_flag = True
    s.join()
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    attempts = [e for e in r.errors if e.startswith("ODL 실패(")]
    if not r.errors and r.odl_fallback is None:
        status = "ok"
    elif r.odl_fallback == "resaved":
        status = "resaved:" + classify(attempts[0]) if attempts else "resaved"
    elif r.odl_fallback == "fitz":
        status = "fitz:" + "+".join(classify(a) for a in attempts)
    else:
        status = "error"
    pages = {str(p.page_num): hashlib.sha1(p.text.encode("utf-8")).hexdigest() for p in r.pages}
    per = sorted(s.per.values(), key=lambda e: e["first"])
    out = {
        "id": did,
        "tag": tag,
        "jto": os.environ.get("JAVA_TOOL_OPTIONS"),
        "status": status,
        "attempt_kinds": [classify(a) for a in attempts],
        "wall": round(wall, 2),
        "odl_seconds": round(r.odl_seconds, 2),
        "errors": r.errors,
        "fallback": r.odl_fallback,
        "total_pages": r.total_pages,
        "n_pages": len(r.pages),
        "methods": sorted({p.method for p in r.pages}),
        "page_sha1": pages,
        "all_sha1": hashlib.sha1(json.dumps([[p.page_num, p.text] for p in r.pages], ensure_ascii=False).encode()).hexdigest(),
        "fill": {str(k): v for k, v in sorted(r.table_fill_ratios.items())},
        "java_runs": [{"pid": e["pid"], "hwm_mb": round(e["hwm_kb"] / 1024), "rss_max_mb": round(e["rss_max_kb"] / 1024),
                       "first_s": e["first"], "last_s": e["last"]} for e in per],
        "peak_java_hwm_mb": round(max([e["hwm_kb"] for e in per] or [0]) / 1024),
        "peak_java_total_rss_mb": round(s.peak_total_rss_kb / 1024),
        "rusage_children_maxrss_mb": round(ru.ru_maxrss / 1024),
        "peak_cgroup_mb": round(s.peak_cg / 2**20),
        "java_left": java_pids(),
        "logs": logs,
    }
    print(json.dumps(out, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
