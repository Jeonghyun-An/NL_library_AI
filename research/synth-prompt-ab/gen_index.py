"""생성 원문(gen_*) 목록 — 원문 JSON 은 근거 대목·모델 원문이 들어 있고 커서 저장소에 넣지 않는다. 대신 파일마다 무엇을 돌렸고
형식이 어땠는지 한 줄씩 남긴다.

사용: PYTHONIOENCODING=utf-8 python gen_index.py <폴더 기준> <파일 또는 폴더> [...] > gen_index.tsv
  예) python gen_index.py <scratchpad>/prompt_ab <scratchpad>/prompt_ab/gen_ab <scratchpad>/prompt_ab/gen_r2 …
- run_ab.py 출력(잡 하나 = 객체)과 run_prompt.py 출력(회차 목록 = 배열) 둘 다 읽는다. 배열이면 회차마다 한 줄.
- 열: 파일(폴더 기준 상대 경로)·변형·보고서·회차·코드(run_ab.py 2차부터 기록)·yaml(파일 이름만)·절·호출·재시도(호출−절)·
  형식 문제 호출·형식 문제 내용·finish_reason 이 stop 아닌 호출·잡 오류·걸린 초·바이트.
"""
import json
import sys
from pathlib import Path

base = Path(sys.argv[1]).resolve()
paths: list[Path] = []
for a in sys.argv[2:]:
    p = Path(a).resolve()
    paths += sorted(p.glob("*.json")) if p.is_dir() else [p]

cols = ["file", "variant", "tag", "run", "code_head", "yaml", "sections", "calls", "retries", "bad_calls", "issues",
        "finish_not_stop", "error", "elapsed_s", "bytes"]
print("\t".join(cols))
for p in paths:
    data = json.loads(p.read_text(encoding="utf-8"))
    runs = data if isinstance(data, list) else [data]
    for r in runs:
        calls = r.get("calls") or []
        secs = r.get("sections") or []
        bad = [c for c in calls if c.get("issues")]
        row = {
            "file": p.relative_to(base).as_posix() + (f"#{runs.index(r)}" if isinstance(data, list) else ""),
            "variant": r.get("variant", ""), "tag": r.get("tag", ""), "run": r.get("run", ""),
            "code_head": r.get("code_head", ""), "yaml": Path(r["yaml"]).name if r.get("yaml") else "",
            "sections": len(secs), "calls": len(calls), "retries": len(calls) - len(secs), "bad_calls": len(bad),
            "issues": "; ".join(i for c in bad for i in c["issues"]),
            "finish_not_stop": sum(1 for c in calls if c.get("finish") not in (None, "stop")),
            "error": r.get("error") or "", "elapsed_s": r.get("elapsed", ""), "bytes": p.stat().st_size,
        }
        print("\t".join(str(row[c]) for c in cols))
