"""timing_repeat.py - one-off: repeat ODL convert (round07 kwargs, image_output off) alternately per version to check
whether the largest 2.5.9/2.5.0 time ratios from compare_driver are stable. Writes timing_repeat.json."""
import json, os, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path
BASE = Path(__file__).resolve().parent
PY = r"C:/Users/LANDSOFT/AppData/Local/Temp/claude/C--Users-LANDSOFT-mygit-NL-library-AI/ac2847f8-32b7-46ce-8254-e87152398b72/scratchpad/draft_D/venv124/Scripts/python.exe"
ODL = {"2.5.0": BASE / "odl250", "2.5.9": BASE / "odl259"}
CHILD = "import json, sys, opendataloader_pdf; opendataloader_pdf.convert(**json.loads(sys.argv[1]))"
docs = sys.argv[2:] ; reps = int(sys.argv[1])
res = {}
for doc in docs:
    for rep in range(reps):
        for ver in ODL:
            od = tempfile.mkdtemp()
            kw = {"input_path": f"D:/SKOVIX/KCI/pdf/{doc}.pdf", "output_dir": od, "format": ["markdown", "json"],
                  "image_output": "off", "image_format": "jpeg", "table_method": "cluster",
                  "markdown_page_separator": "\n<<<ODL_PAGE_BREAK_%page-number%>>>\n", "keep_line_breaks": False, "quiet": True}
            t0 = time.monotonic()
            rc = subprocess.run([PY, "-c", CHILD, json.dumps(kw)], env=dict(os.environ, PYTHONPATH=str(ODL[ver])),
                                capture_output=True, timeout=300).returncode
            res.setdefault(doc, {}).setdefault(ver, []).append(round(time.monotonic() - t0, 3))
            shutil.rmtree(od, ignore_errors=True)
            assert rc == 0, (doc, ver, rc)
    m = {v: statistics.median(res[doc][v]) for v in ODL}
    print(doc, res[doc], "median ratio", round(m["2.5.9"] / m["2.5.0"], 3), flush=True)
json.dump(res, open(BASE / "timing_repeat.json", "w"), indent=1)
