"""compare_driver.py - run round07's real extract_text on opendataloader-pdf 2.5.0 and 2.5.9 and compare.

One-off experiment. Orchestrator mode (no args) spawns one worker process per (document, version, mode)
with PYTHONPATH = "<odl dir for the version>;<code/app>" so the extractor's ODL child (which inherits the
environment) imports exactly that package version. Workers:
  - wrap extractor.extract_text_opendataloader with a recorder (the real function runs once; its raw result is kept)
  - stub extractor._extract_with_vlm (no network; returns "OCR_STUB")
  - keep ODL's temp output dirs (extractor.shutil.rmtree -> move into compare_runs/odl_out) for later analysis
  - capture the extractor logger's INFO/WARNING/ERROR lines
Usage:
  python compare_driver.py                 # run everything that is not in compare_results.jsonl yet, then summarize
  python compare_driver.py summarize       # summarize only
  python compare_driver.py worker VER ID MODE OUT   # internal
"""
import asyncio
import difflib
import hashlib
import importlib.metadata
import inspect
import json
import logging
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import traceback
import types
from pathlib import Path

BASE = Path(__file__).resolve().parent
OLD = Path(r"C:/Users/LANDSOFT/AppData/Local/Temp/claude/c--Users-LANDSOFT-mygit-NL-library-AI/ac2847f8-32b7-46ce-8254-e87152398b72/scratchpad/odl259")  # 2026-10-02 첫 비교 폴더 — ODL 두 버전·pydeps·sample.json 을 그대로 쓴다
PY = r"C:/Users/LANDSOFT/AppData/Local/Temp/claude/C--Users-LANDSOFT-mygit-NL-library-AI/ac2847f8-32b7-46ce-8254-e87152398b72/scratchpad/draft_D/venv124/Scripts/python.exe"
APP = BASE / "code" / "app"  # round07 405eaf5 (git archive) — 비교 중 worktree 를 고쳐도 흔들리지 않게
ODL_DIRS = {"2.5.0": OLD / "odl250", "2.5.9": OLD / "odl259"}
VERSIONS = ["2.5.0", "2.5.9"]
PDF_DIR = Path("D:/SKOVIX/KCI/pdf")
RUNS = BASE / "compare_runs"
RESULTS = BASE / "compare_results.jsonl"
SUMMARY = BASE / "compare_summary.json"
EMBEDDED_IDS = [
    "KCI_FI001930485", "KCI_FI000858284", "KCI_FI002990049", "KCI_FI003011274", "KCI_FI002029401",
    # 4 more from the sample: scan with <br> table grid, 30 image pages, image pages kept as ODL, <br> CMap case
    "KCI_FI000897237", "KCI_FI001314298", "KCI_FI002961735", "KCI_FI001343547",
]
VERSION_CMD = "import importlib.metadata as m; print(m.version('opendataloader-pdf'))"
OCR_RE = re.compile(r"p\.(\d+) → OCR 보완 \((.*), engine=\w+\)$")


# The shared venv's httpcore/h11/sniffio files were deleted at 11:20 on 2026-10-02 (dirs left, .py gone) by
# something outside this experiment; httpx then fails to import. Same versions are installed into pydeps/
# (pip --target, --no-deps) and appended LAST so they only fill that hole. opendataloader-pdf has no deps,
# so the ODL dir (first entry) alone still decides which package version the ODL child imports.
PYDEPS = OLD / "pydeps"


def env_for(ver: str) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{ODL_DIRS[ver]};{APP};{PYDEPS}"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


# ───────────────────────────── worker ─────────────────────────────
def worker(ver: str, doc_id: str, mode: str, out: str) -> None:
    rec: dict = {"id": doc_id, "ver": ver, "mode": mode, "pythonpath": os.environ.get("PYTHONPATH")}
    try:
        # child-version check: same interpreter, same inherited env as the extractor's ODL child
        cp = subprocess.run(
            [sys.executable, "-c",
             "import importlib.metadata as m, opendataloader_pdf as o; print(m.version('opendataloader-pdf')); print(o.__file__)"],
            capture_output=True, text=True,
        )
        lines = cp.stdout.split()
        rec["child_version"] = lines[0] if lines else None
        rec["child_odl_file"] = lines[1] if len(lines) > 1 else None
        if cp.returncode:
            rec["child_version_err"] = cp.stderr[-500:]

        import opendataloader_pdf
        rec["parent_odl_version"] = importlib.metadata.version("opendataloader-pdf")
        rec["parent_odl_file"] = opendataloader_pdf.__file__

        import fitz
        from services.ingestion import extractor, page_routing
        rec["extractor_file"] = extractor.__file__
        rec["fitz_version"] = fitz.VersionBind
        cfg = extractor.cfg
        if mode == "embedded":
            cfg.ODL_IMAGE_OUTPUT = "embedded"
        rec["cfg"] = {k: getattr(cfg, k) for k in (
            "ODL_IMAGE_OUTPUT", "ODL_TIMEOUT_BASE_SECONDS", "ODL_TIMEOUT_PER_PAGE_SECONDS", "INGEST_EXTRACT_DEADLINE",
            "OCR_ENGINE", "VLM_MAX_PAGES_PER_DOC", "EXTRACT_MIN_CHARS_PER_PAGE", "SCAN_MIN_PAGES",
            "SCAN_SHORT_PAGE_RATIO", "SCAN_REPEAT_LINE_RATIO")}

        # logging capture
        logs: list[dict] = []

        class _H(logging.Handler):
            def emit(self, r):
                logs.append({"level": r.levelname, "msg": r.getMessage()})

        lg = logging.getLogger(extractor.__name__)
        lg.setLevel(logging.INFO)
        lg.addHandler(_H(level=logging.INFO))
        lg.propagate = False

        # 1. recorder around the real tier-1 function
        real_odl = extractor.extract_text_opendataloader
        captured: list = []

        async def rec_odl(*a, **kw):
            r = await real_odl(*a, **kw)
            captured.append((r, {k: v for k, v in kw.items() if k != "file_bytes"}))
            return r

        extractor.extract_text_opendataloader = rec_odl

        # 2. VLM stub with the real signature
        real_vlm_sig = str(inspect.signature(extractor._extract_with_vlm))
        stub_calls: list[int] = []

        async def stub_vlm(page, client, *, prompt_type: str = "ocr", render_lock=None):
            stub_calls.append(page.number)
            return extractor.PageResult(page_num=page.number, text="OCR_STUB", method="vlm", confidence=0.9)

        async def no_surya(*a, **kw):
            raise RuntimeError("surya must not be called in this experiment")

        extractor._extract_with_vlm = stub_vlm
        extractor._extract_with_surya = no_surya
        rec["vlm_signature_real"] = real_vlm_sig
        rec["vlm_signature_stub"] = str(inspect.signature(stub_vlm))

        # keep ODL output dirs instead of deleting them (rename on the same volume; outside the timed section)
        arch = RUNS / "odl_out" / f"{doc_id}__{ver}__{mode}"
        if arch.exists():
            shutil.rmtree(arch, ignore_errors=True)
        arch.mkdir(parents=True, exist_ok=True)
        attempt = [0]

        def keep_rmtree(path, ignore_errors=False, **kw):
            attempt[0] += 1
            dst = arch / f"attempt{attempt[0]}"
            try:
                shutil.move(str(path), str(dst))
            except Exception:
                shutil.rmtree(path, ignore_errors=True)

        extractor.shutil = types.SimpleNamespace(rmtree=keep_rmtree)

        pdf = PDF_DIR / f"{doc_id}.pdf"
        t0 = time.monotonic()
        res = asyncio.run(extractor.extract_text(str(pdf), doc_id))
        rec["extract_wall"] = round(time.monotonic() - t0, 3)

        if len(captured) != 1:
            rec["recorder_warning"] = f"extract_text_opendataloader called {len(captured)} times"
        odl, odl_kwargs = captured[0]
        rec["odl_call_kwargs"] = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in odl_kwargs.items()}
        rec["odl_pages"] = [p.page_num for p in odl.pages]
        rec["odl_page_info"] = {
            str(p.page_num): {"sha1": sha1(p.text), "len": len(p.text), "body_len": page_routing.body_len(p.text),
                              "method": p.method}
            for p in odl.pages
        }
        rec["odl_total_pages"] = odl.total_pages
        rec["table_fill_ratios"] = {str(k): v for k, v in sorted(odl.table_fill_ratios.items())}
        rec["odl_errors"] = odl.errors
        rec["odl_fallback"] = odl.odl_fallback
        rec["odl_seconds"] = round(odl.odl_seconds, 3)
        rec["odl_figures"] = len(odl.figures)

        # final result
        rec["total_pages"] = res.total_pages
        rec["final_methods"] = {str(p.page_num): p.method for p in res.pages}
        rec["vlm_pages"] = sorted(p.page_num for p in res.pages if p.method == "vlm")
        rec["stub_calls"] = sorted(stub_calls)
        for k in ("short_kept", "ocr_errors", "ocr_rejected", "vlm_truncated", "render_errors", "deadline_hit",
                  "vlm_capped"):
            rec[k] = getattr(res, k)
        rec["final_errors"] = res.errors
        rec["final_odl_fallback"] = res.odl_fallback
        rec["logs"] = logs
        reasons = {}
        for e in logs:
            m = OCR_RE.search(e["msg"])
            if m:
                reasons[m.group(1)] = m.group(2)
        rec["ocr_reasons"] = reasons

        # fitz lengths (same formula as extract_text) to explain non-OCR decisions
        fitz_texts = []
        with fitz.open(str(pdf)) as d:
            for p in d:
                try:
                    fitz_texts.append(extractor._clean_text(p.get_text()))
                except Exception:
                    fitz_texts.append("")
        repeated = page_routing.repeated_lines(fitz_texts, cfg.SCAN_REPEAT_LINE_RATIO)
        rec["fitz_raw_lens"] = [page_routing.body_len(t) for t in fitz_texts]
        rec["fitz_stripped_lens"] = [page_routing.body_len(page_routing.strip_lines(t, repeated)) for t in fitz_texts]
        scan_line = [e["msg"] for e in logs if "스캔본 문서로 보고" in e["msg"]]
        rec["doc_is_scan"] = bool(scan_line)

        # ODL json stats from the kept output (last attempt that has a json)
        json_stats = {}
        jfiles = sorted(arch.glob("attempt*/*.json"))
        if jfiles:
            jf = jfiles[-1]
            with open(jf, encoding="utf-8") as f:
                jd = json.load(f)
            for el in jd.get("kids", []):
                pn = str(el.get("page number", 1) - 1)
                st = json_stats.setdefault(pn, {"types": {}, "hf": []})
                st["types"][el.get("type")] = st["types"].get(el.get("type"), 0) + 1
                if el.get("type") in ("header", "footer"):
                    st["hf"].extend(extractor._collect_content_strings(el))
            rec["json_file"] = str(jf.relative_to(BASE))
        rec["json_stats"] = json_stats
        rec["odl_attempt_dirs"] = sorted(str(p.relative_to(BASE)) for p in arch.glob("attempt*"))

        # page texts (raw ODL and final) for diffs
        tdir = RUNS / "texts"
        tdir.mkdir(parents=True, exist_ok=True)
        with open(tdir / f"{doc_id}__{ver}__{mode}.json", "w", encoding="utf-8") as f:
            json.dump({"odl": {str(p.page_num): p.text for p in odl.pages},
                       "final": {str(p.page_num): p.text for p in res.pages}}, f, ensure_ascii=False)
        rec["ok"] = True
    except BaseException as e:  # noqa: BLE001
        rec["ok"] = False
        rec["exception"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()[-3000:]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)


# ───────────────────────────── orchestrator ─────────────────────────────
def java_pids() -> set[int]:
    cp = subprocess.run(["tasklist", "/FI", "IMAGENAME eq java.exe", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True, encoding="mbcs", errors="replace")
    pids = set()
    for line in cp.stdout.splitlines():
        parts = [x.strip('"') for x in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == "java.exe":
            try:
                pids.add(int(parts[1]))
            except ValueError:
                pass
    return pids


def kill_orphan_java(doc_id: str) -> list[str]:
    """java started from OUR odl250/odl259 dirs for this doc that outlived the worker (Windows: _kill_process_group
    can only kill the child python)."""
    # NOTE (after the run): the doc-id condition misses the java converting the fitz-resaved temp copy
    # (tmpXXXX.pdf) — runs are sequential, so matching our jar dirs alone would have been enough.
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='java.exe'\" | "
        "Where-Object { $_.CommandLine -like '*" + doc_id + "*' -and ($_.CommandLine -like '*odl250*' -or "
        "$_.CommandLine -like '*odl259\\odl259*' -or $_.CommandLine -like '*odl259/odl259*') } | "
        "ForEach-Object { $_.ProcessId }"
    )
    cp = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    killed = []
    for tok in cp.stdout.split():
        if tok.isdigit():
            subprocess.run(["taskkill", "/T", "/F", "/PID", tok], capture_output=True)
            killed.append(tok)
    return killed


def load_results() -> list[dict]:
    if not RESULTS.exists():
        return []
    with open(RESULTS, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_worker(doc_id: str, ver: str, mode: str, pages: int) -> dict:
    rdir = RUNS / "rec"
    ldir = RUNS / "logs"
    rdir.mkdir(parents=True, exist_ok=True)
    ldir.mkdir(parents=True, exist_ok=True)
    out = rdir / f"{doc_id}__{ver}__{mode}.json"
    if out.exists():
        out.unlink()
    odl_timeout = max(10.0, pages * 1.5)
    wtimeout = 2 * odl_timeout + 240
    before = java_pids()
    t0 = time.monotonic()
    with open(ldir / f"{doc_id}__{ver}__{mode}.log", "w", encoding="utf-8") as lf:
        p = subprocess.Popen([PY, str(Path(__file__).resolve()), "worker", ver, doc_id, mode, str(out)],
                             env=env_for(ver), cwd=str(BASE), stdout=lf, stderr=subprocess.STDOUT)
        timed_out = False
        try:
            p.wait(wtimeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
            p.wait()
    wall = time.monotonic() - t0
    if out.exists():
        with open(out, encoding="utf-8") as f:
            rec = json.load(f)
    else:
        tail = (ldir / f"{doc_id}__{ver}__{mode}.log").read_text(encoding="utf-8", errors="replace")[-2000:]
        rec = {"id": doc_id, "ver": ver, "mode": mode, "ok": False,
               "exception": "worker timeout" if timed_out else f"worker exit {p.returncode} without record",
               "worker_log_tail": tail}
    rec["worker_wall"] = round(wall, 3)
    rec["worker_returncode"] = p.returncode
    rec["pages_hint"] = pages
    rec["other_java_before"] = len(before)
    rec["java_after"] = len(java_pids())
    if timed_out or any("초 초과" in e for e in rec.get("odl_errors", []) or []):
        rec["orphan_java_killed"] = kill_orphan_java(doc_id)
    with open(RESULTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def child_version_proof() -> dict:
    proof = {}
    for ver in VERSIONS:
        cp = subprocess.run([PY, "-c", VERSION_CMD], env=env_for(ver), cwd=str(BASE), capture_output=True, text=True)
        proof[ver] = {"pythonpath": env_for(ver)["PYTHONPATH"], "stdout": cp.stdout.strip(),
                      "stderr": cp.stderr.strip()[-500:], "returncode": cp.returncode}
    return proof


def run_all() -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    proof = child_version_proof()
    with open(RUNS / "child_version_proof.json", "w", encoding="utf-8") as f:
        json.dump(proof, f, ensure_ascii=False, indent=1)
    print("child version proof:", {v: proof[v]["stdout"] for v in proof}, flush=True)
    for v in VERSIONS:
        assert proof[v]["stdout"] == v, proof
    sample = json.load(open(OLD / "sample.json", encoding="utf-8"))
    pages_of = {e["id"]: int(re.search(r"pages=(\d+)", e["why"]).group(1)) for e in sample}
    done = {(r["id"], r["ver"], r["mode"]) for r in load_results() if r.get("ok")}
    for i, e in enumerate(sample, 1):
        for ver in VERSIONS:
            if (e["id"], ver, "off") in done:
                continue
            r = run_worker(e["id"], ver, "off", pages_of[e["id"]])
            print(f"[{i}/{len(sample)}] {e['id']} {ver} off ok={r.get('ok')} child={r.get('child_version')} "
                  f"odl={r.get('odl_seconds')}s pages={len(r.get('odl_pages', []))} vlm={len(r.get('vlm_pages', []))} "
                  f"fb={r.get('odl_fallback')} err={r.get('exception') or r.get('odl_errors')}", flush=True)
    for doc_id in EMBEDDED_IDS:
        if (doc_id, "2.5.9", "embedded") in done:
            continue
        r = run_worker(doc_id, "2.5.9", "embedded", pages_of[doc_id])
        print(f"[emb] {doc_id} 2.5.9 embedded ok={r.get('ok')} odl={r.get('odl_seconds')}s "
              f"pages={len(r.get('odl_pages', []))} vlm={len(r.get('vlm_pages', []))} figs={r.get('odl_figures')}",
              flush=True)


# ───────────────────────────── comparison ─────────────────────────────
def _ws(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _struct(s: str) -> str:
    s = s.replace("[그림]", "")
    s = re.sub(r"<br\s*/?>", "", s, flags=re.I)
    return s.translate(str.maketrans("", "", "|-: \t\n\r"))


def classify(a: str, b: str, hf: set[str]) -> str:
    if a == b:
        return "identical"
    if _ws(a) == _ws(b):
        return "whitespace"
    if _struct(a) == _struct(b):
        return "table formatting/markup (<br>, |, -, [그림])"
    if sorted(_ws(a)) == sorted(_ws(b)):
        return "reading order (same characters, different order)"
    la, lb = a.split("\n"), b.split("\n")
    sa, sb = set(la), set(lb)
    only_a = [x.strip() for x in la if x not in sb and x.strip()]
    only_b = [x.strip() for x in lb if x not in sa and x.strip()]
    if (only_a or only_b) and all(x in hf for x in only_a + only_b):
        return "header-footer (only lines that ODL json marks header/footer differ)"
    ca, cb = len(_struct(a)), len(_struct(b))
    if not only_b and only_a:
        return f"text missing in 2.5.9 ({ca}->{cb} struct chars)"
    if not only_a and only_b:
        return f"text added in 2.5.9 ({ca}->{cb} struct chars)"
    return f"content differs ({ca}->{cb} struct chars, {len(only_a)} lines only in 2.5.0, {len(only_b)} only in 2.5.9)"


def load_texts(doc_id: str, ver: str, mode: str) -> dict:
    p = RUNS / "texts" / f"{doc_id}__{ver}__{mode}.json"
    if not p.exists():
        return {"odl": {}, "final": {}}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def page_decision(r: dict, pg: int) -> str:
    """'OCR: reason' from the log, or why the page was kept (recomputed from recorded lengths)."""
    k = str(pg)
    if k in r.get("ocr_reasons", {}):
        return "OCR: " + r["ocr_reasons"][k]
    info = r.get("odl_page_info", {}).get(k)
    fitz_raw = r.get("fitz_raw_lens", [])
    f = fitz_raw[pg] if pg < len(fitz_raw) else None
    if info is None:
        return f"kept? (no ODL page, fitz {f})"
    b = info["body_len"]
    fr = r.get("table_fill_ratios", {}).get(k)
    return f"kept ODL (body {b}, fitz {f}, fill {fr}, final method {r.get('final_methods', {}).get(k)})"


def compare_pair(a: dict, b: dict, la: str, lb: str, hf_from_both: bool = True, ignore_markers: bool = False) -> dict:
    out: dict = {"id": a["id"]}
    pa, pb = a.get("odl_pages", []), b.get("odl_pages", [])
    out["pages_equal"] = pa == pb
    if pa != pb:
        out["pages_only_" + la] = sorted(set(pa) - set(pb))
        out["pages_only_" + lb] = sorted(set(pb) - set(pa))
        out["page_count"] = {la: len(pa), lb: len(pb)}
    ia, ib = a.get("odl_page_info", {}), b.get("odl_page_info", {})
    ta = load_texts(a["id"], a["ver"], a["mode"])["odl"]
    tb = load_texts(b["id"], b["ver"], b["mode"])["odl"]
    hf: set[str] = set()
    for r in (a, b):
        for st in r.get("json_stats", {}).values():
            hf.update(st.get("hf", []))
    diff_pages = []
    body_deltas = {}
    natures = {}
    for k in sorted(set(ia) | set(ib), key=int):
        if k in ia and k in ib and ia[k]["sha1"] == ib[k]["sha1"]:
            continue
        x, y = ta.get(k, ""), tb.get(k, "")
        if ignore_markers and _struct(x) == _struct(y) and ia.get(k, {}).get("body_len") == ib.get(k, {}).get("body_len"):
            natures[k] = "markers only (<br>/[그림]/table chars)"
            diff_pages.append(int(k))
            continue
        diff_pages.append(int(k))
        body_deltas[k] = {la: ia.get(k, {}).get("body_len"), lb: ib.get(k, {}).get("body_len")}
        natures[k] = classify(x, y, hf) if (k in ia and k in ib) else ("page only in " + (la if k in ia else lb))
    out["text_identical"] = not diff_pages and pa == pb
    out["diff_pages"] = diff_pages
    if diff_pages:
        out["body_len_by_diff_page"] = {k: v for k, v in body_deltas.items()}
        out["body_len_changed_pages"] = {k: v for k, v in body_deltas.items() if v[la] != v[lb]}
        out["nature_by_page"] = natures
        k0 = str(diff_pages[0])
        ud = list(difflib.unified_diff(ta.get(k0, "").split("\n"), tb.get(k0, "").split("\n"),
                                       f"{la} p{k0}", f"{lb} p{k0}", n=1, lineterm=""))
        out["first_diff_page"] = int(k0)
        out["first_diff_sample"] = [line[:200] for line in ud[:40]]
        out["total_body_len"] = {la: sum(v["body_len"] for v in ia.values()), lb: sum(v["body_len"] for v in ib.values())}
    fa, fb = a.get("table_fill_ratios", {}), b.get("table_fill_ratios", {})
    fdiff = {}
    for k in sorted(set(fa) | set(fb), key=int):
        va, vb = fa.get(k), fb.get(k)
        if va is None or vb is None or abs(va - vb) > 0.01:
            fdiff[k] = {la: va, lb: vb}
    out["fill_ratio_keys_equal"] = set(fa) == set(fb)
    out["fill_ratio_diffs"] = fdiff
    out["fill_ratio_max_absdiff"] = max([abs(fa[k] - fb[k]) for k in fa if k in fb] or [0.0])
    va_, vb_ = set(a.get("vlm_pages", [])), set(b.get("vlm_pages", []))
    out["ocr_set_equal"] = va_ == vb_
    out["ocr_count"] = {la: len(va_), lb: len(vb_)}
    out["ocr_decision_diffs"] = [
        {"page": pg, la: page_decision(a, pg), lb: page_decision(b, pg)} for pg in sorted(va_ ^ vb_)
    ]
    out["ocr_reason_text_diffs"] = [
        {"page": int(k), la: a["ocr_reasons"][k], lb: b["ocr_reasons"][k]}
        for k in sorted(set(a.get("ocr_reasons", {})) & set(b.get("ocr_reasons", {})), key=int)
        if a["ocr_reasons"][k] != b["ocr_reasons"][k]
    ]
    out["odl_fallback"] = {la: a.get("odl_fallback"), lb: b.get("odl_fallback")}
    out["odl_errors"] = {la: a.get("odl_errors"), lb: b.get("odl_errors")}
    out["errors_equal"] = a.get("odl_errors") == b.get("odl_errors") and a.get("odl_fallback") == b.get("odl_fallback")
    for k in ("short_kept", "ocr_errors", "vlm_truncated", "render_errors", "deadline_hit", "vlm_capped", "doc_is_scan",
              "total_pages"):
        if a.get(k) != b.get(k):
            out.setdefault("count_diffs", {})[k] = {la: a.get(k), lb: b.get(k)}
    out["odl_seconds"] = {la: a.get("odl_seconds"), lb: b.get("odl_seconds")}
    if a.get("odl_seconds") and b.get("odl_seconds"):
        out["time_ratio"] = round(b["odl_seconds"] / a["odl_seconds"], 3)
    return out


NOTES = [
    "Exported code = 1f4954b. The round07 worktree HEAD has since moved to 741219f; extractor.py, page_routing.py and "
    "requirements.txt are byte-identical (CRLF-normalised) between the two, config.py only gains a deadline "
    "model_validator, so the extraction path tested is the current one.",
    "The shared venv (draft_D/venv124) lost the .py files of httpcore/h11/sniffio/colorama at 11:20 (outside this "
    "experiment); httpx failed to import. httpcore 1.0.9, h11 0.16.0, sniffio 1.3.1 were pip --target installed into "
    "odl259/pydeps and appended LAST to PYTHONPATH. The venv was not touched.",
    "Windows caveat confirmed: on a round07 ODL timeout _kill_process_group only kills the child python; the java "
    "grandchild keeps running. KCI_FI001238691 (2.5.0) left a java on the fitz-resaved temp copy running from 11:31 to "
    "11:38 (~394 CPU-s, 8.4 GB) until it was killed by hand; the orphan filter matched only java whose command line "
    "had the doc id, so it missed the resaved temp path. Timings of KCI_FI001238691 2.5.9 onward (docs 42-45 and the "
    "embedded runs) ran next to that orphan; timing_repeat.json re-measures the outliers without it.",
    "No ODL json in the sample (either version) had header/footer elements, so the header/footer strip path "
    "(_clean_text strip_lines) was not exercised by real data.",
]


def _side_checks() -> dict:
    extra = {}
    for name in ("classify_diffs.json", "timing_repeat.json"):
        p = BASE / name
        if p.exists():
            with open(p, encoding="utf-8") as f:
                extra[name] = json.load(f)
    for p in sorted(BASE.glob("slow_doc_probe_*.json")):
        with open(p, encoding="utf-8") as f:
            extra[p.name] = json.load(f)
    p = BASE / "slow_doc_probe_259_full.txt"
    if p.exists():
        extra[p.name] = [line for line in p.read_text(encoding="utf-8", errors="replace").splitlines()
                         if "Exception" in line or "Error" in line][:5]
    return extra


def summarize() -> dict:
    recs = load_results()
    latest: dict = {}
    for r in recs:  # last record per (id, ver, mode) wins
        latest[(r["id"], r["ver"], r["mode"])] = r
    sample = json.load(open(OLD / "sample.json", encoding="utf-8"))
    proof_p = RUNS / "child_version_proof.json"
    proof = json.load(open(proof_p, encoding="utf-8")) if proof_p.exists() else None
    failures = []
    for r in latest.values():
        bad = not r.get("ok") or r.get("odl_fallback") or r.get("odl_errors")
        if bad:
            failures.append({"id": r["id"], "ver": r["ver"], "mode": r["mode"], "ok": r.get("ok"),
                             "exception": r.get("exception"), "odl_fallback": r.get("odl_fallback"),
                             "odl_errors": r.get("odl_errors"), "odl_seconds": r.get("odl_seconds")})
    child_versions = sorted({(r["ver"], r.get("child_version")) for r in latest.values()})
    child_mismatch = [f"{r['id']} {r['ver']} {r['mode']} child={r.get('child_version')}" for r in latest.values()
                      if r.get("child_version") != r["ver"]]
    per_doc = []
    missing = []
    for e in sample:
        a, b = latest.get((e["id"], "2.5.0", "off")), latest.get((e["id"], "2.5.9", "off"))
        if not (a and b and a.get("ok") and b.get("ok")):
            missing.append(e["id"])
            continue
        c = compare_pair(a, b, "2.5.0", "2.5.9")
        c["group"] = e["group"]
        per_doc.append(c)
    emb = []
    for doc_id in EMBEDDED_IDS:
        a, b = latest.get((doc_id, "2.5.9", "off")), latest.get((doc_id, "2.5.9", "embedded"))
        if not (a and b and a.get("ok") and b.get("ok")):
            emb.append({"id": doc_id, "missing": True})
            continue
        c = compare_pair(a, b, "off", "embedded", ignore_markers=True)
        bl_a = {k: v["body_len"] for k, v in a["odl_page_info"].items()}
        bl_b = {k: v["body_len"] for k, v in b["odl_page_info"].items()}
        c["body_len_per_page_equal"] = bl_a == bl_b
        c["body_len_per_page_diffs"] = {k: [bl_a.get(k), bl_b.get(k)] for k in sorted(set(bl_a) | set(bl_b), key=int)
                                        if bl_a.get(k) != bl_b.get(k)}
        c["figures_embedded"] = b.get("odl_figures")
        emb.append(c)
    ratios = [c["time_ratio"] for c in per_doc if "time_ratio" in c]
    t250 = [c["odl_seconds"]["2.5.0"] for c in per_doc]
    t259 = [c["odl_seconds"]["2.5.9"] for c in per_doc]
    summ = {
        "commit_tested": "1f4954b7a9b12eba4afc20ba6081d50d707e16a7 (exported code/app)",
        "child_version_proof": proof,
        "child_versions_seen": [f"{v}->{c}" for v, c in child_versions],
        "child_version_mismatch": child_mismatch,
        "docs_in_sample": len(sample),
        "docs_compared": len(per_doc),
        "docs_missing_or_failed": missing,
        "docs_identical_text": sum(1 for c in per_doc if c["text_identical"]),
        "docs_pages_equal": sum(1 for c in per_doc if c["pages_equal"]),
        "docs_fill_equal": sum(1 for c in per_doc if not c["fill_ratio_diffs"] and c["fill_ratio_keys_equal"]),
        "docs_ocr_set_equal": sum(1 for c in per_doc if c["ocr_set_equal"]),
        "docs_errors_equal": sum(1 for c in per_doc if c["errors_equal"]),
        "docs_with_text_diff": [
            {"id": c["id"], "diff_pages": c["diff_pages"], "natures": sorted(set(c.get("nature_by_page", {}).values())),
             "body_len_changed_pages": c.get("body_len_changed_pages"), "total_body_len": c.get("total_body_len")}
            for c in per_doc if not c["text_identical"]
        ],
        "fill_ratio_diffs": {c["id"]: c["fill_ratio_diffs"] for c in per_doc if c["fill_ratio_diffs"]},
        "ocr_decision_diffs": {c["id"]: c["ocr_decision_diffs"] for c in per_doc if c["ocr_decision_diffs"]},
        "ocr_reason_text_diffs": {c["id"]: c["ocr_reason_text_diffs"] for c in per_doc if c["ocr_reason_text_diffs"]},
        "count_diffs": {c["id"]: c["count_diffs"] for c in per_doc if c.get("count_diffs")},
        "failures": failures,
        "timing": {
            "odl_seconds_median": {"2.5.0": statistics.median(t250) if t250 else None,
                                   "2.5.9": statistics.median(t259) if t259 else None},
            "odl_seconds_max": {"2.5.0": max(t250) if t250 else None, "2.5.9": max(t259) if t259 else None},
            "odl_seconds_total": {"2.5.0": round(sum(t250), 1), "2.5.9": round(sum(t259), 1)},
            "ratio_259_over_250_median": statistics.median(ratios) if ratios else None,
            "ratio_259_over_250_max": max(ratios) if ratios else None,
            "ratio_259_over_250_min": min(ratios) if ratios else None,
            "ratio_max_doc": max(per_doc, key=lambda c: c.get("time_ratio", 0))["id"] if ratios else None,
        },
        "embedded_vs_off_259": emb,
        "side_checks": _side_checks(),
        "notes": NOTES,
        "per_doc": per_doc,
    }
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summ, f, ensure_ascii=False, indent=1)
    return summ


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(*sys.argv[2:6])
    elif len(sys.argv) > 1 and sys.argv[1] == "summarize":
        s = summarize()
        print(json.dumps({k: v for k, v in s.items() if k not in ("per_doc", "embedded_vs_off_259")},
                         ensure_ascii=False, indent=1)[:6000])
    else:
        run_all()
        s = summarize()
        print(json.dumps({k: v for k, v in s.items() if k not in ("per_doc", "embedded_vs_off_259")},
                         ensure_ascii=False, indent=1)[:6000])
