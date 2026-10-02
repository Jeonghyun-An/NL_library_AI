"""prod_check.py - run round07's extractor inside the cached production image (Linux, OpenJDK 17, Python 3.11, ODL 2.5.9).

One-off experiment. Mounts: /app = exported round07 code (ro), /pdf = KCI pdf dir (ro), /w = this dir (rw), /ref = compare_runs (ro).
Subcommands:
  equiv            run extract_text (VLM stubbed) on every sample id; compare ODL page texts / fill ratios / OCR pages
                   with the Windows (Java 18) 2.5.9-off record; check java/zombie/tmp leftovers after each doc
  slow  ID         extract_text_opendataloader on one doc with a java RSS sampler (timeout -> killpg path)
  alarm ID T       parent runs _odl_convert(timeout=T) and is SIGKILLed after 2s; see whether SIGALRM self-kill reaps java
  par N ID...      N concurrent processes each running extract_text_opendataloader; total java RSS sampler
  quiet ID...      call opendataloader_pdf.convert in-process with round07 kwargs and record captured stdout/stderr sizes
"""
import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "/app")
OUT = Path("/w/out")
OUT.mkdir(parents=True, exist_ok=True)
PDF = Path("/pdf")
REF = Path("/ref")


def procs():
    """[(pid, ppid, state, comm, rss_kb, cmdline)] from /proc."""
    res = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                st = f.read()
            comm = st[st.index("(") + 1: st.rindex(")")]
            rest = st[st.rindex(")") + 2:].split()
            state, ppid = rest[0], int(rest[1])
            rss = 0
            try:
                with open(f"/proc/{d}/status") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            rss = int(line.split()[1])
            except OSError:
                pass
            try:
                with open(f"/proc/{d}/cmdline", "rb") as f:
                    cmd = f.read().replace(b"\0", b" ").decode(errors="replace")[:200]
            except OSError:
                cmd = ""
            res.append((int(d), ppid, state, comm, rss, cmd))
        except (OSError, ValueError):
            pass
    return res


def javas():
    return [p for p in procs() if p[3] == "java"]


def zombies():
    return [p for p in procs() if p[2] == "Z"]


def tmp_listing():
    out = set()
    for root in ("/tmp", "/root", "/var/tmp"):
        for dp, dn, fn in os.walk(root):
            for n in dn + fn:
                out.add(os.path.join(dp, n))
    return out


class Sampler(threading.Thread):
    def __init__(self, period=0.25):
        super().__init__(daemon=True)
        self.period, self.stop_flag, self.samples = period, False, []

    def run(self):
        t0 = time.monotonic()
        while not self.stop_flag:
            js = javas()
            mem = {}
            try:
                with open("/sys/fs/cgroup/memory.current") as f:
                    mem["cg"] = int(f.read())
            except OSError:
                pass
            self.samples.append((round(time.monotonic() - t0, 2), len(js), sum(j[4] for j in js), mem.get("cg")))
            time.sleep(self.period)

    def summary(self):
        if not self.samples:
            return {}
        peak = max(self.samples, key=lambda s: s[2])
        cg = [s[3] for s in self.samples if s[3]]
        return {"peak_java_rss_mb": round(peak[2] / 1024), "peak_at_s": peak[0], "max_java_procs": max(s[1] for s in self.samples),
                "peak_cgroup_mb": round(max(cg) / 2**20) if cg else None,
                "trace": [(s[0], s[1], round(s[2] / 1024)) for s in self.samples[:: max(1, len(self.samples) // 40)]]}


def sha1(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def setup_extractor():
    import logging
    from services.ingestion import extractor
    logs = []

    class _H(logging.Handler):
        def emit(self, r):
            logs.append(r.getMessage())

    lg = logging.getLogger(extractor.__name__)
    lg.setLevel(logging.INFO)
    lg.addHandler(_H(level=logging.INFO))
    lg.propagate = False

    async def stub_vlm(page, client, *, prompt_type: str = "ocr", render_lock=None):
        return extractor.PageResult(page_num=page.number, text="OCR_STUB", method="vlm", confidence=0.9)

    async def no_surya(*a, **kw):
        raise RuntimeError("surya must not be called")

    extractor._extract_with_vlm = stub_vlm
    extractor._extract_with_surya = no_surya
    return extractor, logs


def cmd_equiv():
    extractor, logs = setup_extractor()
    import opendataloader_pdf, importlib.metadata as md
    print("odl", md.version("opendataloader-pdf"), opendataloader_pdf.__file__, "image_output", extractor.cfg.ODL_IMAGE_OUTPUT, flush=True)
    real = extractor.extract_text_opendataloader
    cap = []

    async def rec_odl(*a, **kw):
        r = await real(*a, **kw)
        cap.append(r)
        return r

    extractor.extract_text_opendataloader = rec_odl
    sample = json.load(open("/w/sample.json", encoding="utf-8"))
    base_tmp = tmp_listing()
    outf = open(OUT / "equiv.jsonl", "w", encoding="utf-8")
    for ent in sample:
        did = ent["id"]
        cap.clear(); logs.clear()
        t0 = time.monotonic()
        res = asyncio.run(extractor.extract_text(str(PDF / f"{did}.pdf"), did))
        wall = time.monotonic() - t0
        odl = cap[0]
        time.sleep(0.3)
        rec = {"id": did, "wall": round(wall, 2), "odl_seconds": round(odl.odl_seconds, 2), "odl_errors": odl.errors,
               "odl_fallback": odl.odl_fallback,
               "odl_pages": {str(p.page_num): p.text for p in odl.pages},
               "fill": {str(k): v for k, v in sorted(odl.table_fill_ratios.items())},
               "vlm_pages": sorted(p.page_num for p in res.pages if p.method == "vlm"),
               "final_errors": res.errors,
               "java_left": [j[:4] for j in javas()], "zombies": [z[:4] for z in zombies()],
               "new_tmp": sorted(tmp_listing() - base_tmp)[:20]}
        # compare with the Windows/Java18 2.5.9 off run
        wrec = json.load(open(REF / "rec" / f"{did}__2.5.9__off.json", encoding="utf-8"))
        wtxt = json.load(open(REF / "texts" / f"{did}__2.5.9__off.json", encoding="utf-8"))["odl"]
        mine = rec["odl_pages"]
        rec["cmp"] = {
            "page_set_same": sorted(mine) == sorted(wtxt),
            "text_diff_pages": sorted((k for k in set(mine) | set(wtxt) if mine.get(k) != wtxt.get(k)), key=int),
            "fill_same": rec["fill"] == {k: v for k, v in wrec["table_fill_ratios"].items()},
            "vlm_same": rec["vlm_pages"] == wrec["vlm_pages"],
            "fallback_same": odl.odl_fallback == wrec["odl_fallback"],
            "errors_same": odl.errors == wrec["odl_errors"],
            "win_odl_seconds": wrec["odl_seconds"],
        }
        print(did, json.dumps(rec["cmp"], ensure_ascii=False), "java_left", len(rec["java_left"]), "zombies",
              len(rec["zombies"]), "new_tmp", len(rec["new_tmp"]), flush=True)
        outf.write(json.dumps(rec, ensure_ascii=False) + "\n"); outf.flush()
        base_tmp = tmp_listing()


def cmd_slow(did):
    extractor, logs = setup_extractor()
    before_tmp = tmp_listing()
    s = Sampler(); s.start()
    t0 = time.monotonic()
    r = asyncio.run(extractor.extract_text_opendataloader(str(PDF / f"{did}.pdf"), did))
    wall = time.monotonic() - t0
    time.sleep(1.0)
    s.stop_flag = True; s.join()
    out = {"id": did, "wall": round(wall, 2), "errors": r.errors, "fallback": r.odl_fallback, "pages": len(r.pages),
           "odl_seconds": round(r.odl_seconds, 2), "java_after": [j[:4] for j in javas()], "zombies_after": [z[:4] for z in zombies()],
           "tmp_leftover": sorted(tmp_listing() - before_tmp), "logs": logs, **s.summary()}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    json.dump(out, open(OUT / f"slow_{did}.json", "w"), ensure_ascii=False, indent=1)


PARENT = r"""
import asyncio, json, sys
sys.path.insert(0, '/app')
from services.ingestion import extractor
kw = {"input_path": sys.argv[1], "output_dir": sys.argv[2], "format": ["markdown", "json"], "image_output": "off",
      "image_format": "jpeg", "table_method": "cluster", "markdown_page_separator": "\n<<<ODL_PAGE_BREAK_%page-number%>>>\n",
      "keep_line_breaks": False, "quiet": True}
asyncio.run(extractor._odl_convert(kw, float(sys.argv[3])))
"""


def cmd_alarm(did, timeout):
    os.makedirs("/tmp/alarm_out", exist_ok=True)
    before_tmp = tmp_listing()
    parent = subprocess.Popen([sys.executable, "-c", PARENT, str(PDF / f"{did}.pdf"), "/tmp/alarm_out", timeout])
    t0 = time.monotonic()
    time.sleep(2.0)
    js = javas()
    print("before parent kill: java", [j[:4] for j in js], flush=True)
    os.kill(parent.pid, signal.SIGKILL)
    parent.wait()
    print("parent killed at", round(time.monotonic() - t0, 2), flush=True)
    gone_at = None
    trace = []
    while time.monotonic() - t0 < float(timeout) + 30:
        js = javas()
        kids = [p for p in procs() if "opendataloader_pdf.convert" in p[5] or p[3] == "java"]
        trace.append((round(time.monotonic() - t0, 1), [(k[0], k[1], k[2], k[3]) for k in kids]))
        if not kids:
            gone_at = round(time.monotonic() - t0, 2)
            break
        time.sleep(0.5)
    time.sleep(1.0)
    out = {"id": did, "timeout": timeout, "expected_self_kill_at": int(float(timeout)) + 5, "java_and_child_gone_at": gone_at,
           "zombies_after": [z[:4] for z in zombies()], "tmp_leftover": sorted(tmp_listing() - before_tmp),
           "trace": trace[:: max(1, len(trace) // 15)]}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    json.dump(out, open(OUT / f"alarm_{did}.json", "w"), ensure_ascii=False, indent=1)


CHILD_ONE = r"""
import asyncio, json, sys, time
sys.path.insert(0, '/app')
from services.ingestion import extractor
t0 = time.monotonic()
r = asyncio.run(extractor.extract_text_opendataloader(sys.argv[1], sys.argv[2]))
print(json.dumps({"id": sys.argv[2], "wall": round(time.monotonic() - t0, 2), "errors": r.errors, "fallback": r.odl_fallback,
                  "pages": len(r.pages), "odl_seconds": round(r.odl_seconds, 2)}, ensure_ascii=False))
"""


def cmd_par(n, ids):
    before_tmp = tmp_listing()
    s = Sampler(0.5); s.start()
    ps = []
    for i in range(int(n)):
        did = ids[i % len(ids)]
        ps.append(subprocess.Popen([sys.executable, "-c", CHILD_ONE, str(PDF / f"{did}.pdf"), did], stdout=subprocess.PIPE, text=True))
    outs = [p.communicate()[0].strip() for p in ps]
    time.sleep(1.0)
    s.stop_flag = True; s.join()
    out = {"n": n, "ids": ids, "results": outs, "java_after": [j[:4] for j in javas()], "zombies_after": [z[:4] for z in zombies()],
           "tmp_leftover": sorted(tmp_listing() - before_tmp)[:30], **s.summary()}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    json.dump(out, open(OUT / f"par{n}.json", "w"), ensure_ascii=False, indent=1)


def cmd_quiet(ids):
    import subprocess as sp
    import opendataloader_pdf
    from opendataloader_pdf import runner
    real_run = sp.run
    sizes = []

    def spy(cmd, *a, **kw):
        t0 = time.monotonic()
        try:
            r = real_run(cmd, *a, **kw)
            sizes.append({"rc": r.returncode, "stdout": len(r.stdout or ""), "stderr": len(r.stderr or ""),
                          "stdout_head": (r.stdout or "")[:300], "stderr_head": (r.stderr or "")[:300], "s": round(time.monotonic() - t0, 2)})
            return r
        except sp.CalledProcessError as e:
            sizes.append({"rc": e.returncode, "stdout": len(e.stdout or ""), "stderr": len(e.stderr or ""),
                          "stderr_head": (e.stderr or "")[:500]})
            raise

    runner.subprocess.run = spy
    res = {}
    for did in ids:
        od = f"/tmp/q_{did}"
        os.makedirs(od, exist_ok=True)
        sizes.clear()
        try:
            opendataloader_pdf.convert(input_path=str(PDF / f"{did}.pdf"), output_dir=od, format=["markdown", "json"],
                                       image_output="off", image_format="jpeg", table_method="cluster",
                                       markdown_page_separator="\n<<<ODL_PAGE_BREAK_%page-number%>>>\n", keep_line_breaks=False, quiet=True)
        except Exception as e:
            sizes.append({"exc": repr(e)[:300]})
        res[did] = {"run": list(sizes), "out_files": {f: os.path.getsize(os.path.join(od, f)) for f in os.listdir(od)}}
        print(did, json.dumps(res[did], ensure_ascii=False)[:800], flush=True)
    json.dump(res, open(OUT / "quiet.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "equiv":
        cmd_equiv()
    elif c == "slow":
        cmd_slow(sys.argv[2])
    elif c == "alarm":
        cmd_alarm(sys.argv[2], sys.argv[3])
    elif c == "par":
        cmd_par(sys.argv[2], sys.argv[3:])
    elif c == "quiet":
        cmd_quiet(sys.argv[2:])
