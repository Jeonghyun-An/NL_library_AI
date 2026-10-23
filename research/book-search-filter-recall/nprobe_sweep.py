"""Milvus 필터 검색의 nprobe 별 재현율 — 운영 컬렉션에서 읽기만 한다 (1회성, 2026-10-23 작성, 대회 뒤 실행용).

IVF_FLAT 은 질의에 가까운 nprobe 개 클러스터만 열고 그 안에서 조건식을 거른다. 조건에 맞는 청크가 그 클러스터에
드물면 결과가 limit 보다 적거나 더 가까운 청크를 놓친다. 운영 API 로는 nprobe 를 못 바꿔서, 여기서는 FastAPI 컨테이너
안에서 같은 컬렉션을 dense 검색만으로 nprobe 를 바꿔 가며 부르고, nprobe = nlist(모든 클러스터 — IVF_FLAT 에서는 전수)
결과를 정답으로 겹침을 잰다. 쓰기·인덱스 변경·load/release 는 하지 않는다. BGE-M3 는 CPU 로 올린다(GPU 예산을 쓰지
않는다 — 질의 수십 개라 CPU 로 충분하다).

    docker cp nprobe_sweep.py nl-lib-fastapi:/tmp/nprobe_sweep.py
    docker exec -w /app nl-lib-fastapi python /tmp/nprobe_sweep.py > sweep.json

보는 것
- counts: 컬렉션 청크 수와 도서 조건(_BOOK_EXPR)에 맞는 청크 수
- scope book: 소장자료 검색과 같은 조건·limit 300 — nprobe 별 결과 수, 정답과 겹침, 지연
- scope book+date: 도서 조건에 발행 연도 한 해를 더한 조건(날짜 필터가 걸린 소장자료 검색)
- book_id: DeepRead 와 같은 조건(book_id == X)·limit 6 과 30
"""
import json
import os
import sys
import time

os.environ["CUDA_VISIBLE_DEVICES"] = ""   # torch 를 올리기 전에 — BGE-M3 를 CPU 로

from FlagEmbedding import BGEM3FlagModel  # noqa: E402
from pymilvus import Collection, connections  # noqa: E402

sys.path.insert(0, "/app")
from core.config import get_settings  # noqa: E402
from services.search.pipeline import _BOOK_EXPR, _PAPER_EXPR  # noqa: E402

cfg = get_settings()
LIMIT_BOOK = 300   # top_k 10 × BOOK_MODE_FETCH_MULTIPLIER 3 × HYBRID_SEARCH_CHUNK_LIMIT_MULT 10

# research/book-search-filter-recall/queries.json 의 제목 질의와 같은 것 — 목표 도서
TITLE_QUERIES = [
    ("무정", "WS_001"), ("진달래꽃", "WS_002"), ("운수 좋은 날", "WS_004"), ("태평천하", "WS_007"),
    ("상록수", "WS_008"), ("날개", "WS_011"), ("구운몽", "WS_014"), ("감자", "WS_018"), ("동백꽃", "GM_001"),
    ("돈키호테", "LIT-GUTENBERG-996"), ("드라큘라", "LIT-GUTENBERG-345"), ("레 미제라블", "LIT-GUTENBERG-135"),
    ("위대한 유산", "LIT-GUTENBERG-1400"), ("올리버 트위스트", "LIT-GUTENBERG-730"),
    ("이상한 나라의 앨리스", "LIT-GUTENBERG-11"), ("두 도시 이야기", "LIT-GUTENBERG-98"),
    ("Oliver Twist", "LIT-GUTENBERG-730"), ("Great Expectations", "LIT-GUTENBERG-1400"),
    ("셜록 홈즈 같은 추리소설", None), ("조선시대 고전소설을 연구한 자료", None), ("노인의 사회적 지지와 우울", None),
]
DATE_QUERIES = [("1984", "1984"), ("이광수 소설 연구", "1984"), ("한국 근대소설", "1992"), ("고전소설", "1988")]
DEEPREAD_QUESTIONS = ["이 연구의 목적은 무엇인가", "연구 방법과 대상", "주요 결과와 결론", "선행연구와의 차이"]


def nlist_of(col: Collection) -> int:
    for idx in col.indexes:
        if idx.field_name == "embedding":
            return int(idx.params.get("params", {}).get("nlist") or idx.params.get("nlist"))
    raise RuntimeError("embedding 인덱스 없음")


def dense_search(col, vec, expr, limit, nprobe):
    t0 = time.perf_counter()
    res = col.search(data=[vec], anns_field="embedding", limit=limit, expr=expr,
                     param={"metric_type": "COSINE", "params": {"nprobe": nprobe}},
                     output_fields=["book_id"], timeout=120)
    ms = (time.perf_counter() - t0) * 1000
    return [(h.id, h.entity.get("book_id"), h.distance) for h in res[0]], ms


def sweep(col, vec, expr, limit, probes, exact):
    truth, truth_ms = dense_search(col, vec, expr, limit, exact)
    truth_ids = {h[0] for h in truth}
    out = {"exact": {"n": len(truth), "ms": round(truth_ms), "books": len({h[1] for h in truth})}}
    for p in probes:
        hits, ms = dense_search(col, vec, expr, limit, p)
        out[p] = {"n": len(hits), "ms": round(ms), "books": len({h[1] for h in hits}),
                  "recall": round(len({h[0] for h in hits} & truth_ids) / max(1, len(truth_ids)), 3)}
    return out, truth


def book_rank(hits, target):
    seen = []
    for _, b, _ in hits:
        if b not in seen:
            seen.append(b)
    return seen.index(target) + 1 if target in seen else None


def main() -> None:
    connections.connect(host=cfg.MILVUS_HOST, port=cfg.MILVUS_PORT)
    col = Collection(cfg.MILVUS_COLLECTION)   # 이미 load 된 운영 컬렉션 — load/release 하지 않는다
    exact = nlist_of(col)
    probes = sorted({cfg.MILVUS_NPROBE, 256, 1024} - {exact})
    report = {"nlist": exact, "nprobe_now": cfg.MILVUS_NPROBE, "probes": probes, "counts": {}, "book": [],
              "book_date": [], "book_id": []}
    for name, expr in (("all", None), ("book", _BOOK_EXPR), ("paper", _PAPER_EXPR)):
        q = col.query(expr=expr or "", output_fields=["count(*)"], timeout=120)
        report["counts"][name] = q[0]["count(*)"]

    model = BGEM3FlagModel(cfg.EMBEDDING_MODEL_NAME, use_fp16=False)

    def emb(texts):
        return model.encode(texts, return_dense=True, return_sparse=False)["dense_vecs"].tolist()

    for (query, target), vec in zip(TITLE_QUERIES, emb([q for q, _ in TITLE_QUERIES])):
        res, truth = sweep(col, vec, _BOOK_EXPR, LIMIT_BOOK, probes, exact)
        now, _ = dense_search(col, vec, _BOOK_EXPR, LIMIT_BOOK, cfg.MILVUS_NPROBE)
        report["book"].append({"query": query, "target": target, "sweep": res,
                               "target_rank_exact": book_rank(truth, target) if target else None,
                               "target_rank_now": book_rank(now, target) if target else None})

    for (query, year), vec in zip(DATE_QUERIES, emb([q for q, _ in DATE_QUERIES])):
        expr = f'{_BOOK_EXPR} && pub_date >= "{year}" && pub_date < "{int(year) + 1}"'
        res, _ = sweep(col, vec, expr, LIMIT_BOOK, probes, exact)
        report["book_date"].append({"query": query, "year": year, "sweep": res})

    # DeepRead 대상 — 노인 우울 질의로 찾은 논문 5편(전수 검색)
    seed, _ = dense_search(col, emb(["노인의 사회적 지지와 우울"])[0], _PAPER_EXPR, 200, exact)
    papers = list(dict.fromkeys(b for _, b, _ in seed))[:5]
    q_vecs = emb(DEEPREAD_QUESTIONS)
    for cnts_id in papers:
        for question, vec in zip(DEEPREAD_QUESTIONS, q_vecs):
            for limit in (cfg.BOOK_CHAT_SEARCH_TOP_K, 30):
                res, _ = sweep(col, vec, f'book_id == "{cnts_id}"', limit, probes, exact)
                report["book_id"].append({"cnts_id": cnts_id, "question": question, "limit": limit, "sweep": res})

    json.dump(report, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
