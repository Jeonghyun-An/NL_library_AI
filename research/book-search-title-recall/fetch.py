"""소장자료 검색 — 질의마다 운영 API 를 재작성 켬·끔 두 번 부른다 (1회성, 2026-10-23).

화면과 같은 인자(mode book · top_k 10 · rerank 켬)로 POST /api/books/search 를 부르고, 응답의 도서마다 content_score·
title_score·best_score·제목을 남긴다. 재작성은 gemma temperature 0 이라 같은 질의면 같은 문장이다. 이 API 는 부를 때마다
search_history 에 한 줄을 쓴다 — 화면에 보이지 않는 고정 세션 id 로 보낸다.

    python fetch.py            # raw/<번호>.json — 있으면 건너뛴다
"""
import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://skovix.landsoft.co.kr"
SESSION = {"x-session-id": "00000000-0000-4000-8000-00000000d1a9"}


def queries() -> list[dict]:
    q = json.loads((HERE / "queries.json").read_text(encoding="utf-8"))
    out = []
    for kind in ("title_kr", "title_en_kr", "title_en", "title_in_question"):
        out += [{"kind": kind, "query": t, "targets": [i]} for t, i in q[kind]]
    out += [{"kind": "author", "query": t, "targets": ids} for t, ids in q["author"]]
    out += [{"kind": "judged", "query": t, "targets": []} for t in q["judged"]]
    return out


def call(query: str, rewrite: bool) -> dict:
    t0 = time.time()
    r = httpx.post(f"{BASE}/api/books/search", headers=SESSION, timeout=180, json={
        "query": query, "mode": "book", "top_k": 10, "use_rewrite": rewrite, "use_rerank": True})
    r.raise_for_status()
    d = r.json()
    books = [{"book_id": b["book_id"], "best": b.get("best_score"), "content": b.get("content_score"),
              "title_score": b.get("title_score"), "title": (b.get("book_info") or {}).get("title"),
              "title_remainder": (b.get("book_info") or {}).get("title_remainder"),
              "doc_type": (b.get("book_info") or {}).get("doc_type")} for b in d.get("books", [])]
    return {"rewritten": d.get("rewritten_query"), "elapsed_ms": d.get("elapsed_ms"),
            "wall_s": round(time.time() - t0, 2), "books": books}


def one(i: int, item: dict) -> str:
    path = HERE / "raw" / f"{i:03d}.json"
    if path.exists():
        return f"skip {i}"
    on = call(item["query"], True)
    off = call(item["query"], False)
    path.write_text(json.dumps({**item, "on": on, "off": off}, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"done {i} {item['query']} on={len(on['books'])} off={len(off['books'])}"


def main() -> None:
    (HERE / "raw").mkdir(exist_ok=True)
    items = queries()
    with cf.ThreadPoolExecutor(3) as ex:   # 운영 검색과 같은 서버라 동시 3 으로
        for msg in ex.map(lambda a: one(*a), enumerate(items)):
            print(msg)


if __name__ == "__main__":
    main()
