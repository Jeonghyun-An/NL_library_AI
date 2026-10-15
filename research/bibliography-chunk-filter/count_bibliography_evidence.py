"""운영 딥리서치 보고서의 근거 청크 가운데 참고문헌 목록 조각으로 판정되는 것을 센다 (1회성, 읽기 전용).

입력은 GET /api/research/{job_id} 응답 JSON 을 job_id.json 으로 모은 폴더다. --fetch 를 주면 job_ids.txt 의 잡을
그 주소에서 GET 으로 받아 폴더에 먼저 저장한다(운영에는 GET 만 보낸다).

    python count_bibliography_evidence.py <응답 폴더> [--fetch https://<서버>] > result.txt

판정은 저장소의 app/services/research/bibliography.py 를 그대로 불러 쓴다 — 배포될 규칙과 같은 것을 센다.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))

from services.research.bibliography import looks_like_bibliography  # noqa: E402


def fetch(base: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for job_id in (HERE / "job_ids.txt").read_text(encoding="utf-8").split():
        with urllib.request.urlopen(f"{base.rstrip('/')}/api/research/{job_id}", timeout=30) as res:
            (out / f"{job_id}.json").write_bytes(res.read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--fetch")
    args = ap.parse_args()
    if args.fetch:
        fetch(args.fetch, args.folder)
    sys.stdout.reconfigure(encoding="utf-8")

    reports = evidence = top_bib = all_bib = occurrences = bib_occurrences = 0
    unique: dict[str, tuple[bool, str]] = {}
    for path in sorted(args.folder.glob("*.json")):
        job = json.loads(path.read_text(encoding="utf-8"))
        items = ((job.get("report") or {}).get("evidence")) or {}
        if not items:
            continue
        reports += 1
        for ev in items.values():
            chunks = ev.get("chunks") or []
            if not chunks:
                continue
            flags = [looks_like_bibliography(c["text"]) for c in chunks]
            evidence += 1
            occurrences += len(flags)
            bib_occurrences += sum(flags)
            top_bib += flags[0]
            all_bib += all(flags)
            for c, flag in zip(chunks, flags):
                unique[c["chunk_id"]] = (flag, c["text"])

    flagged = sorted(cid for cid, (flag, _) in unique.items() if flag)
    print(f"보고서 {reports} · 인용 근거 {evidence} · 첫 대목이 참고문헌 {top_bib} ({top_bib / evidence:.0%})"
          f" · 대목 전부 참고문헌 {all_bib} ({all_bib / evidence:.0%})")
    print(f"청크(근거마다 셈) {occurrences} 중 참고문헌 {bib_occurrences} ({bib_occurrences / occurrences:.0%})"
          f" · 서로 다른 청크 {len(unique)} 중 참고문헌 {len(flagged)}")
    print()
    for cid in flagged:
        print(f"{cid:24s} | {' '.join(unique[cid][1][:70].split())}")


if __name__ == "__main__":
    main()
