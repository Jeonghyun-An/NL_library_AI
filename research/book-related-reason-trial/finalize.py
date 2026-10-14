# collected.json 에 (1) 질의 1 의 관련 자료 부족분 보충 후보(화면과 다름 표시), (2) LLM 직접 접근 정보, (3) 집계를 더한다.
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import BASE, describe, get_book  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "collected.json"
d = json.loads(OUT.read_text(encoding="utf-8"))

# (1) 화면 관련 자료가 4권이 안 되는 질의 — 메인 검색 결과 순서에서 1위·이미 고른 관련 자료를 빼고 채운다(화면에는 안 나오는 짝)
for q in d["queries"]:
    q["related_shortfall"] = max(0, 4 - len(q["related"]))
    q["related_supplement"] = []
    if not q["related_shortfall"]:
        continue
    used = {q["top1"]["cnts_id"], *(r["cnts_id"] for r in q["related"])}
    cands = [r for r in q["search_api"]["results"] if r["book_id"] not in used][: q["related_shortfall"]]
    for c in cands:
        time.sleep(1.0)
        det = get_book(c["book_id"])
        q["related_supplement"].append({
            **describe(det),
            "screen_equivalent": False,
            "source": f"메인 검색 결과 {c['api_rank']}위(관련 자료 API 는 이 책을 주지 않았다)",
            "main_search_rank": c["api_rank"],
            "best_score": c["best_score"],
        })

if d["queries"][0]["related_shortfall"]:
    retry = json.loads((HERE / "q1_related_retry.json").read_text(encoding="utf-8"))
    d["queries"][0]["related_api"]["retry_check"] = {
        "result_count": len(retry["results"]),
        "results": retry["results"],
        "note": "같은 요청을 한 번 더 보내도 2건(1위 자신 + 1권) — 우연이 아니라 재현된다. 제목 질의라 후보 청크가 1위 책 자신의 청크로 채워져 다른 책이 거의 안 들어온다(app/services/search/pipeline.py _search_book_mode: search_by_book 의 청크 풀 → 책 묶음)",
    }

# (2) LLM 직접 접근 — GET /v1/models 만 확인
models = requests.get("http://192.168.12.57:18080/v1/models", timeout=10).json()
d["llm"] = {
    "reachable": True,
    "base_url": "http://192.168.12.57:18080/v1",
    "model": models["data"][0]["id"],
    "model_root": models["data"][0].get("root"),
    "max_model_len": models["data"][0].get("max_model_len"),
    "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "evidence": [
        "GET http://192.168.12.57:18080/v1/models → 200, id=gemma-3-12b, root=google/gemma-3-12b-it, max_model_len=32768",
        "docker-compose.yml gemma 서비스(container nl-lib-gemma): command google/gemma-3-12b-it --served-model-name gemma-3-12b --port 8000, ports \"18080:8000\" (호스트에 공개), --max-num-seqs 16, --gpu-memory-utilization 0.30",
        "docker-compose.yml x-common-env(fastapi·celery 공통): LLM_BASE_URL ${LLM_BASE_URL:-http://gemma:8000/v1}, LLM_MODEL ${LLM_MODEL:-gemma-3-12b} — 운영 fastapi 가 쓰는 것과 같은 vLLM 인스턴스(컨테이너 안에서는 gemma:8000, 밖에서는 :18080)",
        "저장소 infra/conf.d/default.conf(운영은 /data/nl-lib/nginx/conf.d 를 마운트 — 저장소 사본 기준) 게이트웨이(:92)는 /api/→fastapi, /→nuxt 만 프록시 — LLM 은 게이트웨이로는 안 나가고 18080 직접 공개로만 닿는다",
        "GET http://192.168.12.57:18081/v1/models(VLM vllm 공개 포트)·:8000 은 연결 거부",
    ],
    "note": "같은 GPU 를 운영 적재(celery-llm)·검색 재작성·추천 이유가 함께 쓴다 — 변형 프롬프트는 순차로, 짝마다 쉬어 보낸다. stream_related_reason 과 같게 보내려면 POST {base_url}/chat/completions, model=gemma-3-12b, temperature 0.2, max_tokens 200, system/user 는 app/services/search/paper_summary.py 159-194행 그대로(초록 400자 _truncate(_clean_excerpt)). 각 자료의 server_excerpt 필드가 그 '초록:' 줄에 들어갈 값이다",
}

# (3) 집계
items = []
for q in d["queries"]:
    items.append(("top1", q["query"], q["top1"]))
    items += [("related", q["query"], r) for r in q["related"]]
supp = [r for q in d["queries"] for r in q["related_supplement"]]
d["summary"] = {
    "screen_items": len(items),
    "screen_items_note": "질의 1 의 관련 자료가 화면에 1권뿐이라 15권이 아니라 12권(1위 3 + 관련 9). 보충 후보 3권은 related_supplement 에 따로",
    "screen_body_all_empty": sum(1 for _, _, it in items if it["body_all_empty"]),
    "screen_pick_field_counts": {
        f: sum(1 for _, _, it in items if it["server_pick_field"] == f) for f in ("abstract", "summary", "introduction", "none")
    },
    "supplement_items": len(supp),
    "supplement_body_all_empty": sum(1 for it in supp if it["body_all_empty"]),
    "side_effect_note": "POST /api/books/search 는 서버가 매번 search_history 에 한 줄 INSERT 한다(app/api/book.py search_books — 피할 수 없음). 이 수집에서 7번 호출, x-session-id=trial-book-related-20261013 로 구분된다. 그 밖에 쓰기 호출은 없다",
}

OUT.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print("ok", d["summary"])
