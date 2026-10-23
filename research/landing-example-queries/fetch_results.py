"""랜딩 예시 질의 후보를 운영 검색에 화면과 같은 인자로 넣고 상위 10건을 저장한다 (1회성).

도서 패널: POST /api/books/search {mode: book, top_k: 10, use_rewrite: true, use_rerank: true}(pages/index.vue)
논문 패널: POST /api/papers/search {mode: book, top_k: 20, use_rewrite: false, use_rerank: true}(pages/papers/index.vue)
도서 검색은 검색 기록을 남긴다 — 이 실험 전용 세션 id 를 쓴다. 상위 10건은 화면 기본 순서(응답 순서) 그대로.

    python fetch_results.py [_r2]   → results/<topic>.json · judge/<topic>.json(질의 문장을 가린 판정 묶음) · judge_key.json
"""
import hashlib
import json
import random
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "http://192.168.12.57:92"
SESSION = "7a3e9c21-5b4d-4f6e-8a1b-2c9d0e7f6a54"
TOP = 10
BODY = {
    "book": ("/api/books/search", {"mode": "book", "top_k": 10, "use_rewrite": True, "use_rerank": True}),
    "paper": ("/api/papers/search", {"mode": "book", "top_k": 20, "use_rewrite": False, "use_rerank": True}),
}


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(BASE + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
                                 headers={"Accept": "application/json", "Content-Type": "application/json; charset=utf-8",
                                          "x-session-id": SESSION})
    with urllib.request.urlopen(req, timeout=180) as res:
        return json.loads(res.read().decode("utf-8"))


def slim(item: dict) -> dict:
    b = item.get("book_info") or {}
    return {"title": " ".join(x for x in (b.get("title"), b.get("title_remainder")) if x),
            "author": b.get("personal_author") or b.get("corporate_author"), "year": b.get("pub_date"),
            "publisher": b.get("publisher") or b.get("series_title"), "kdc": b.get("kdc"),
            "subject": b.get("subject") or b.get("keyword"), "abstract": (b.get("abstract") or "")[:400]}


def main() -> None:
    import sys
    tag = sys.argv[1] if len(sys.argv) > 1 else ""
    cands = json.loads((HERE / f"candidates{tag}.json").read_text(encoding="utf-8"))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "judge").mkdir(exist_ok=True)
    key = {}
    for topic, c in cands.items():
        path, extra = BODY[c["panel"]]
        runs = []
        for q in c["variants"]:
            t0 = time.time()
            data = post(path, {"query": q, **extra})
            runs.append({"query": q, "rewritten_query": data.get("rewritten_query"), "n": len(data.get("books") or []),
                         "ms": int((time.time() - t0) * 1000), "top": [slim(x) for x in (data.get("books") or [])[:TOP]]})
            print(topic, len(runs), runs[-1]["n"], runs[-1]["ms"], "ms |", q, "→", data.get("rewritten_query"))
        (HERE / "results" / f"{topic}.json").write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")
        rng = random.Random(int(hashlib.sha256(topic.encode()).hexdigest(), 16))
        order = list(range(len(runs)))
        rng.shuffle(order)
        lists = {f"R{i + 1}": runs[j]["top"] for i, j in enumerate(order)}
        key[topic] = {f"R{i + 1}": runs[j]["query"] for i, j in enumerate(order)}
        (HERE / "judge" / f"{topic}.json").write_text(json.dumps(
            {"topic": topic, "panel": c["panel"], "intent": c["intent"], "lists": lists}, ensure_ascii=False, indent=1),
            encoding="utf-8")
    (HERE / f"judge_key{tag}.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
