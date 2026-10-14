# 도서 관련 자료 비교 사유 시험 — 생성 단계.
# 입력: collected.json(수집 단계 산출). 출력: generated.json(쌍 목록), generated_run.json(실행 정보), generated_view.txt(사람이 읽는 표).
#
# 변형
#   A        : 운영 POST /api/papers/related-reason/stream {source_id, related_id} 를 그대로 — SSE text 를 이어 붙인다
#   A_replay : (대조군) A 와 같은 프롬프트를 코드에서 그대로 만들어 운영 LLM 에 직접 보낸다 — 서버 경로와 직접 경로가 같은지 확인용
#   B        : 도서용 최소 변형 — 시스템 프롬프트에서 '학술 논문'→'소장 자료(도서·학위논문·보고서)', 틀 '해당 논문은'→'해당 자료는' 만
#   C        : B + 구체 대상 이름 들기·본문 밖 내용 금지·'초록 없음'이면 제목 공통점만 짧게
# 직접 호출은 app/services/search/paper_summary.py stream_related_reason 와 같은 payload
#   (model=gemma-3-12b, temperature 0.2, max_tokens 200, stream=True, 초록 = _truncate(_clean_excerpt(x), 400) 또는 '초록 없음').
# 초록 줄 값은 collected.json 의 server_excerpt(수집 때 GET /api/books/{id} 원문에 paper.py _get_abstract 순서
#   abstract→summary→introduction 와 같은 _clean_excerpt·_truncate 를 적용한 값)를 그대로 쓴다.
# 운영 공유 GPU — 모든 호출 순차, 호출 사이 1초 쉼.
import json
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
IN = HERE / "collected.json"
OUT = HERE / "generated.json"
RUN = HERE / "generated_run.json"
VIEW = HERE / "generated_view.txt"

API = "http://192.168.12.57:92/api/papers/related-reason/stream"
LLM_BASE = "http://192.168.12.57:18080/v1"
MODEL = "gemma-3-12b"
PAUSE = 1.0
SERVER_ERROR_TEXT = "유사성 분석 중 오류가 발생했습니다."

# ── 프롬프트 ────────────────────────────────────────────────
SYSTEM_A = (
    "당신은 학술 논문 전문가입니다. "
    "두 논문의 연구적 유사성을 1~2문장으로 간결하게 설명하세요. "
    "반드시 '해당 논문은 ~ 한 내용이 유사합니다.' 형식으로 작성하세요."
)
# B: 지시대로 시스템 프롬프트의 두 곳만 바꾼다('두 논문의 연구적 유사성'·사용자 프롬프트는 그대로)
SYSTEM_B = (
    "당신은 소장 자료(도서·학위논문·보고서) 전문가입니다. "
    "두 논문의 연구적 유사성을 1~2문장으로 간결하게 설명하세요. "
    "반드시 '해당 자료는 ~ 한 내용이 유사합니다.' 형식으로 작성하세요."
)
SYSTEM_C = SYSTEM_B + (
    " 두 자료가 함께 다루는 구체적인 대상·시기·작품·제도·방법 중 본문(각 자료의 '초록:' 줄)에 적힌 것을 "
    "하나 이상 이름으로 드세요. 본문에 없는 내용은 쓰지 마세요. "
    "본문이 '초록 없음'이면 제목에서 확인되는 공통점만 짧게 쓰세요."
)


def user_msg(src_title: str, src_excerpt: str, rel_title: str, rel_excerpt: str) -> str:
    # paper_summary.py stream_related_reason 의 user_msg 그대로(A·B·C 공통)
    return (
        f"원본 논문: {src_title}\n초록: {src_excerpt}\n\n"
        f"연관 논문: {rel_title}\n초록: {rel_excerpt}\n\n"
        "두 논문이 유사한 이유를 설명하세요."
    )


# ── 호출 ────────────────────────────────────────────────────
def call_server(source_id: str, related_id: str) -> dict:
    t0 = time.time()
    out = {"text": None, "ok": False, "error": None, "http_status": None, "events": 0, "elapsed_s": None}
    try:
        with requests.post(
            API, json={"source_id": source_id, "related_id": related_id},
            headers={"Accept": "text/event-stream"}, stream=True, timeout=(10, 90),
        ) as r:
            out["http_status"] = r.status_code
            r.raise_for_status()
            parts = []
            done = False
            for raw in r.iter_lines(decode_unicode=False):
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace")
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    done = True
                    break
                out["events"] += 1
                try:
                    j = json.loads(data)
                except Exception:
                    continue
                if "text" in j:
                    parts.append(j["text"])
            text = "".join(parts)
            out["text"] = text
            out["got_done"] = done
            if text.strip() == SERVER_ERROR_TEXT:
                out["error"] = "server_swallowed_llm_error (서버가 LLM 실패를 잡아 오류 문구를 흘림)"
            elif not text.strip():
                out["error"] = "empty_text"
            else:
                out["ok"] = True
    except Exception as e:  # 타임아웃·연결 실패 그대로 기록
        out["error"] = f"{type(e).__name__}: {e}"
    out["elapsed_s"] = round(time.time() - t0, 2)
    return out


def call_llm(system: str, user: str) -> dict:
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": 200,
        "temperature": 0.2,
        "stream": True,
    }
    t0 = time.time()
    out = {"text": None, "ok": False, "error": None, "http_status": None, "finish_reason": None, "elapsed_s": None}
    try:
        with requests.post(f"{LLM_BASE}/chat/completions", json=payload, stream=True, timeout=(10, 60)) as r:
            out["http_status"] = r.status_code
            r.raise_for_status()
            parts = []
            for raw in r.iter_lines(decode_unicode=False):
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace")
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    j = json.loads(data)
                    ch = j["choices"][0]
                except Exception:
                    continue
                delta = (ch.get("delta") or {}).get("content") or ""
                if delta:
                    parts.append(delta)
                if ch.get("finish_reason"):
                    out["finish_reason"] = ch["finish_reason"]
            out["text"] = "".join(parts)
            out["ok"] = bool(out["text"].strip())
            if not out["ok"]:
                out["error"] = "empty_text"
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    out["elapsed_s"] = round(time.time() - t0, 2)
    return out


# ── 쌍 만들기 ───────────────────────────────────────────────
def build_pairs(d: dict) -> list[dict]:
    pairs = []
    for q in d["queries"]:
        src = q["top1"]
        rels = [(r, True) for r in q["related"]] + [(r, False) for r in q.get("related_supplement", [])]
        for slot, (r, on_screen) in enumerate(rels[:4], start=1):
            rel_meta = {
                "id": r["cnts_id"],
                "title": r["title"],
                "rank": slot,
                "screen_equivalent": on_screen,
            }
            if on_screen:
                rel_meta["display_rank"] = r["display_rank"]
                rel_meta["related_api_rank"] = r["related_api_rank"]
            else:
                rel_meta["note"] = r.get("source")
                rel_meta["main_search_rank"] = r.get("main_search_rank")
            rel_meta["best_score"] = r.get("best_score")
            pairs.append({
                "query": q["query"],
                "source": {"id": src["cnts_id"], "title": src["title"], "best_score": src.get("best_score")},
                "related": rel_meta,
                "body_empty": {"source": src["body_all_empty"], "related": r["body_all_empty"]},
                "body_field": {"source": src["server_pick_field"], "related": r["server_pick_field"]},
                "_src_excerpt": src["server_excerpt"],
                "_rel_excerpt": r["server_excerpt"],
            })
    return pairs


def main() -> None:
    d = json.loads(IN.read_text(encoding="utf-8"))
    pairs = build_pairs(d)
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    results = []
    first = True
    for i, p in enumerate(pairs, start=1):
        src_ex, rel_ex = p.pop("_src_excerpt"), p.pop("_rel_excerpt")
        u = user_msg(p["source"]["title"], src_ex, p["related"]["title"], rel_ex)
        p["prompts"] = {
            "user": u,
            "user_note": "A·A_replay·B·C 공통 — paper_summary.py stream_related_reason 의 user_msg 그대로. A 의 실제 값은 서버가 같은 규칙으로 만든다(여기 값은 코드로 재구성)",
            "A_system": SYSTEM_A,
            "B_system": SYSTEM_B,
            "C_system": SYSTEM_C,
            "params": {"model": MODEL, "temperature": 0.2, "max_tokens": 200, "stream": True, "excerpt_rule": "_truncate(_clean_excerpt(abstract or summary or introduction), 400) else '초록 없음'"},
        }
        meta = {}
        print(f"[{i}/{len(pairs)}] {p['source']['title']} ↔ {p['related']['title']}", flush=True)

        for key, fn in (
            ("A", lambda: call_server(p["source"]["id"], p["related"]["id"])),
            ("A_replay", lambda: call_llm(SYSTEM_A, u)),
            ("B", lambda: call_llm(SYSTEM_B, u)),
            ("C", lambda: call_llm(SYSTEM_C, u)),
        ):
            if not first:
                time.sleep(PAUSE)
            first = False
            res = fn()
            p[key] = res["text"] if res["ok"] else None
            meta[key] = {k: v for k, v in res.items() if k != "text"}
            if not res["ok"]:
                meta[key]["raw_text"] = res["text"]
            print(f"   {key}: ok={res['ok']} {res['elapsed_s']}s {res.get('finish_reason') or ''} {res['error'] or ''}", flush=True)
        p["meta"] = meta
        results.append(p)
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    failures = {k: sum(1 for p in results if not p["meta"][k]["ok"]) for k in ("A", "A_replay", "B", "C")}
    length_cut = {k: sum(1 for p in results if p["meta"][k].get("finish_reason") == "length") for k in ("A_replay", "B", "C")}
    run = {
        "started_at": started,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pairs": len(results),
        "screen_pairs": sum(1 for p in results if p["related"]["screen_equivalent"]),
        "variants": ["A", "A_replay", "B", "C"],
        "failures": failures,
        "finish_reason_length": length_cut,
        "server_api": API,
        "llm_base_url": LLM_BASE,
        "model": MODEL,
        "pause_s": PAUSE,
        "notes": [
            "질의 1 은 화면 관련 자료가 1권뿐이라 rank 2~4 는 메인 검색 2~4위 보충 후보(screen_equivalent=false) — 화면에 나오지 않는 짝",
            "A 는 운영 서버 경로, A_replay·B·C 는 같은 vLLM 인스턴스(:18080)에 직접 — temperature 0.2 라 같은 프롬프트도 표본마다 조금 다를 수 있다(쌍마다 1회씩만 생성)",
            "B 는 지시대로 시스템 프롬프트 두 곳('학술 논문'·'해당 논문은')만 바꿨다 — '두 논문의 연구적 유사성'과 사용자 프롬프트의 '원본 논문/연관 논문/초록/두 논문이'는 그대로",
            "C 의 '본문' 은 사용자 프롬프트에 '초록:' 줄로 들어가므로 '본문(각 자료의 '초록:' 줄)' 로 짚었다",
        ],
    }
    RUN.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    for p in results:
        lines.append("=" * 100)
        tag = "" if p["related"]["screen_equivalent"] else "  [보충·화면과 다름]"
        lines.append(f"Q {p['query']}")
        lines.append(f"  원본 {p['source']['id']} {p['source']['title']}")
        lines.append(f"  연관#{p['related']['rank']} {p['related']['id']} {p['related']['title']}{tag}")
        lines.append(f"  body_empty={p['body_empty']} field={p['body_field']}")
        for k in ("A", "A_replay", "B", "C"):
            m = p["meta"][k]
            txt = p[k] if p[k] is not None else f"<실패: {m['error']}>"
            fr = f" [{m['finish_reason']}]" if m.get("finish_reason") else ""
            lines.append(f"  {k:8s}{fr} {txt.strip()}")
    lines.append("")
    lines.append(json.dumps(run, ensure_ascii=False, indent=1))
    VIEW.write_text("\n".join(lines), encoding="utf-8")
    print("done", json.dumps({"failures": failures, "length": length_cut}, ensure_ascii=False))


if __name__ == "__main__":
    main()
