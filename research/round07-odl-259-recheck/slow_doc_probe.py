"""slow_doc_probe.py - run ODL convert (same kwargs as round07 _run_odl) on one PDF per version with a long timeout.

One-off: tells whether a document that hits round07's page-scaled timeout finishes at all, and how 2.5.0 / 2.5.9 compare.
Usage: python slow_doc_probe.py <KCI id> <timeout s>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
PY = r"C:/Users/LANDSOFT/AppData/Local/Temp/claude/C--Users-LANDSOFT-mygit-NL-library-AI/ac2847f8-32b7-46ce-8254-e87152398b72/scratchpad/draft_D/venv124/Scripts/python.exe"
ODL_DIRS = {"2.5.0": BASE / "odl250", "2.5.9": BASE / "odl259"}
CHILD = "import json, sys, opendataloader_pdf; opendataloader_pdf.convert(**json.loads(sys.argv[1]))"


def main(doc_id: str, timeout: float) -> None:
    out = {}
    for ver, d in ODL_DIRS.items():
        od = tempfile.mkdtemp()
        kw = {"input_path": f"D:/SKOVIX/KCI/pdf/{doc_id}.pdf", "output_dir": od, "format": ["markdown", "json"],
              "image_output": "off", "image_format": "jpeg", "table_method": "cluster",
              "markdown_page_separator": "\n<<<ODL_PAGE_BREAK_%page-number%>>>\n", "keep_line_breaks": False,
              "quiet": True}
        env = dict(os.environ, PYTHONPATH=str(d))
        t0 = time.monotonic()
        p = subprocess.Popen([PY, "-c", CHILD, json.dumps(kw)], env=env, stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE)
        try:
            _, err = p.communicate(timeout=timeout)
            status = f"exit {p.returncode}"
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
            _, err = p.communicate()
            status = "timeout"
        secs = time.monotonic() - t0
        files = sorted(os.listdir(od))
        md = [f for f in files if f.endswith(".md")]
        pages = None
        if md:
            txt = open(os.path.join(od, md[0]), encoding="utf-8").read()
            pages = txt.count("<<<ODL_PAGE_BREAK_")
        out[ver] = {"status": status, "seconds": round(secs, 1), "files": files, "md_page_breaks": pages,
                    "stderr_tail": err.decode("utf-8", "replace")[-600:]}
        print(ver, out[ver], flush=True)
        shutil.rmtree(od, ignore_errors=True)
    with open(BASE / f"slow_doc_probe_{doc_id}.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]))
