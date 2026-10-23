"""비교 입력 — 운영 딥리서치 보고서를 GET 으로 받아 jobs/job_<id>.json 에 둔다(운영에는 GET 만). jobs/ 는 커밋하지 않고
jobs.sha256 에 해시만 남긴다(synth-prompt-ab 와 같다).

    python fetch_jobs.py [--base http://192.168.12.57:92]
"""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://192.168.12.57:92")
    args = ap.parse_args()
    out = HERE / "jobs"
    out.mkdir(exist_ok=True)
    lines = []
    for tag, jid in json.loads((HERE / "jobs.json").read_text(encoding="utf-8")).items():
        req = urllib.request.Request(f"{args.base}/api/research/{jid}", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as res:
            body = res.read()
        report = json.loads(body).get("report") or {}
        path = out / f"job_{jid}.json"
        path.write_bytes(body)
        lines.append(f"{hashlib.sha256(body).hexdigest()}  jobs/{path.name}")
        print(tag, jid[:8], "sections", len(report.get("sections") or []), "evidence", len(report.get("evidence") or {}))
    (HERE / "jobs.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
