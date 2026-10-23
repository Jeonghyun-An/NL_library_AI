"""운영 이어가기 연구의 연구 공백(gap) 절 생성 입력을 다시 맞춘다 (1회성, 운영에는 GET 만).

절 입력(research_generations.input)은 API 로 그대로 나오지 않는다. 같은 것을 GET 응답들로 다시 만든다.
- 질문·보고서: GET /api/research/{id}
- 목차(주제·연구 질문)·저장된 gap 절의 gen_id·evidence 지도: GET /api/research/{id}/proposal
- 고른 주제의 씨앗: GET /api/research/{id}/topics
- 서지(제목·발행일): GET /api/research/{id}/reading 의 items[].meta
- 모델에 넘긴 초록·대목: GET /api/research/{id}/sections/gap/sources?gen=<gap gen_id>
그 위에서 저장소의 section_input.gap_seeds·gap_input 을 그대로 부른다. 다시 만든 논문 순서(E#)가 저장된 gap 절의
evidence 지도와 같은지 확인하고, 다르면 그 연구는 뺀다.

    python fetch_inputs.py <job_id> [<job_id> ...]   → inputs/<job_id 앞 8자>.json
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))

from services.research_work.section_input import gap_input, gap_seeds  # noqa: E402

BASE = "http://192.168.12.57:92"
SESSION = "6f7d8c1e-0b7a-4c43-9d0f-3f2e5a1b9c20"   # 읽기 전용 GET 의 x-session-id(아무 uuid4)


def get(path: str, **params) -> dict:
    url = BASE + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "x-session-id": SESSION})
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read().decode("utf-8"))


def rebuild(job_id: str) -> dict:
    job = get(f"/api/research/{job_id}")
    proposal = get(f"/api/research/{job_id}/proposal")
    outline = proposal.get("outline") or {}
    section = (proposal.get("sections") or {}).get("gap") or {}
    gen_id = section.get("gen_id")
    topics = get(f"/api/research/{job_id}/topics")
    items = topics if isinstance(topics, list) else (topics.get("items") or topics.get("topics") or [])
    topic_id = (outline.get("topic") or {}).get("id")
    topic = next((t for t in items if t.get("id") == topic_id), None)
    reading = get(f"/api/research/{job_id}/reading")
    sources = get(f"/api/research/{job_id}/sections/gap/sources", gen=gen_id)

    books = {}
    for it in (reading.get("items") or []) + (reading.get("excluded") or []):
        meta = it.get("meta") or {}
        books[it["cnts_id"]] = SimpleNamespace(title=meta.get("title"), pub_date=meta.get("pub_date"), abstract=None)
    excerpts = {}
    for src in sources.values():
        cnts = src["cnts_id"]
        book = books.setdefault(cnts, SimpleNamespace(title=None, pub_date=None, abstract=None))
        book.abstract = src.get("abstract") or ""
        excerpts[cnts] = src.get("excerpt")

    seeds = gap_seeds(dict((topic or {}).get("seed") or {}), job.get("report") or {})
    inp = gap_input(question=job["question"], topic=dict(outline.get("topic") or {}),
                    research_question=outline.get("question") or (outline.get("topic") or {}).get("question") or "",
                    seeds=seeds, books=books, excerpts=excerpts)
    rebuilt = {p["eid"]: p["cnts_id"] for p in inp["papers"]}
    stored = section.get("evidence") or {}
    same = rebuilt == stored and {e: s["cnts_id"] for e, s in sources.items()} == stored
    missing_title = [p["cnts_id"] for p in inp["papers"] if p["title"] == p["cnts_id"]]
    return {"job_id": job_id, "gen_id": gen_id, "same_papers": same, "missing_title": missing_title,
            "stored_evidence": stored, "input": inp,
            "stored_paragraphs": [p["text"] for p in section.get("paragraphs") or []],
            "stored_checks": [p.get("checks") for p in section.get("paragraphs") or []]}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    out = HERE / "inputs"
    out.mkdir(exist_ok=True)
    for job_id in sys.argv[1:]:
        rec = rebuild(job_id)
        (out / f"{job_id[:8]}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        print(job_id[:8], "gen", rec["gen_id"], "papers", len(rec["input"]["papers"]), "same", rec["same_papers"],
              "missing_title", rec["missing_title"], "seeds", [s["text"][:50] for s in rec["input"]["seeds"]])


if __name__ == "__main__":
    main()
