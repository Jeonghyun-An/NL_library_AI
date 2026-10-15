"""참고문헌 판정 규칙을 바꾸기 전·후로 운영 근거 청크를 다시 판정해 달라진 청크를 원문째 보인다 (1회성, 읽기 전용).

입력은 두 가지 GET 응답을 모은 폴더다 — /api/research/{job_id}(보고서 근거 청크, job_id.json)와
/api/research/{job_id}/sections/{key}/sources(이어가기 절 생성에 넘긴 대목, src_{job_id 앞 8자}_{key}.json).
--fetch 를 주면 job_ids.txt·job_ids_1015.txt 의 잡과 sources.txt 의 (잡, 절) 을 그 주소에서 GET 으로 받아 폴더에 먼저
저장한다(운영에는 GET 만 보낸다).

    python compare_rules.py <응답 폴더> [--fetch http://<서버>] [--old-rev c21ce10] > result_thesis_tail.txt

옛 규칙은 git show <old-rev>:app/services/research/bibliography.py 로, 새 규칙은 작업 트리의 같은 파일로 불러 쓴다.
보이는 것: 새로 걸린 청크·풀려난 청크(원문 전체), 새 규칙의 strip_reference_tail 이 뗀 청크(뗀 자리 앞뒤).
절 대목(sources)은 400자로 잘린 글이라, 같은 청크가 보고서 근거에도 있으면 보고서 쪽 원문으로 판정한다.
"""
import argparse
import importlib.util
import json
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULE = "app/services/research/bibliography.py"


def _load(name: str, source: str):
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, f"{name}.py", "exec"), module.__dict__)
    return module


def _get(url: str, sid: str) -> bytes:
    req = urllib.request.Request(url, headers={"x-session-id": sid})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def fetch(base: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    base, sid = base.rstrip("/"), str(uuid.uuid4())
    jobs = [j for f in ("job_ids.txt", "job_ids_1015.txt") for j in (HERE / f).read_text(encoding="utf-8").split()]
    for job_id in dict.fromkeys(jobs):
        (out / f"{job_id}.json").write_bytes(_get(f"{base}/api/research/{job_id}", sid))
    for line in (HERE / "sources.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            job_id, key = line.split()
            (out / f"src_{job_id[:8]}_{key}.json").write_bytes(
                _get(f"{base}/api/research/{job_id}/sections/{key}/sources", sid))


def collect(folder: Path) -> dict[str, dict]:
    """청크 ID → {text, where}. 보고서 근거 청크가 먼저, 절 대목은 보고서에 없던 청크만 400자 글로 더한다."""
    chunks: dict[str, dict] = {}
    for path in sorted(folder.glob("*.json")):
        if path.name.startswith("src_"):
            continue
        job = json.loads(path.read_text(encoding="utf-8"))
        for eid, ev in (((job.get("report") or {}).get("evidence")) or {}).items():
            for c in ev.get("chunks") or []:
                chunks.setdefault(c["chunk_id"], {"text": c["text"], "where": []})["where"].append(
                    f"{path.stem[:8]}:{eid}")
    for path in sorted(folder.glob("src_*.json")):
        for eid, src in json.loads(path.read_text(encoding="utf-8")).items():
            ex = (src or {}).get("excerpt") or {}
            if ex.get("chunk_id") and ex.get("text"):
                chunks.setdefault(ex["chunk_id"], {"text": ex["text"], "where": []})["where"].append(
                    f"{path.stem[4:]}:{eid}")
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--fetch")
    ap.add_argument("--old-rev", default="c21ce10")
    args = ap.parse_args()
    if args.fetch:
        fetch(args.fetch, args.folder)
    sys.stdout.reconfigure(encoding="utf-8")

    old_src = subprocess.run(["git", "show", f"{args.old_rev}:{MODULE}"], cwd=ROOT, check=True,
                             capture_output=True).stdout.decode("utf-8")
    old = _load("bibliography_old", old_src)
    new = _load("bibliography_new", (ROOT / MODULE).read_text(encoding="utf-8"))

    chunks = collect(args.folder)
    was = {cid: old.looks_like_bibliography(c["text"]) for cid, c in chunks.items()}
    now = {cid: new.looks_like_bibliography(c["text"]) for cid, c in chunks.items()}
    added = sorted(cid for cid in chunks if now[cid] and not was[cid])
    released = sorted(cid for cid in chunks if was[cid] and not now[cid])
    cut = {cid: new.strip_reference_tail(c["text"]) for cid, c in chunks.items() if not now[cid]}
    cut = {cid: out for cid, out in cut.items() if out != chunks[cid]["text"]}

    print(f"서로 다른 근거 청크 {len(chunks)} · 참고문헌 {sum(was.values())} → {sum(now.values())}"
          f" (새로 걸림 {len(added)} · 풀려남 {len(released)}) · 본문 끝 참고문헌 꼬리를 뗀 청크 {len(cut)}"
          f" — 옛 규칙 {args.old_rev}")
    for title, ids in (("새로 걸림", added), ("풀려남", released)):
        print(f"\n## {title} {len(ids)}")
        for cid in ids:
            c = chunks[cid]
            print(f"\n### {cid} ({len(c['text'])}자 · {', '.join(c['where'][:4])})\n{c['text']}")
    print(f"\n## 꼬리를 뗀 청크 {len(cut)} — 남는 글의 끝 60자 ‖ 뗀 글의 앞 80자")
    for cid, out in sorted(cut.items()):
        text = chunks[cid]["text"]
        print(f"\n{cid} ({len(text)}자 → {len(out)}자 · {', '.join(chunks[cid]['where'][:3])})\n"
              f"  …{' '.join(out[-60:].split())} ‖ {' '.join(text[len(out):len(out) + 80].split())}")


if __name__ == "__main__":
    main()
