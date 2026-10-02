r"""check.py — Qwen 한국어 품질 표본 확인 (round06a, 1회성)

연구 어시스턴트는 핵심 개념·주제 카드를 Qwen(qwen3-vl-8b)으로 만든다(spec D10, WORK_MODEL_ROUTES). 대회 전에
Qwen 의 한국어 출력이 쓸 만한지 사람이 본다(spec §8 'Qwen 한국어 품질'). 고정 질문의 갈래 0 잡(run_pair.py
출력 JSON)을 HTTP 로 읽어 두 프롬프트를 Qwen 과 gemma 에 똑같이 보내고 out/<질문키>.md 에 나란히 쓴다.
  (a) 핵심 개념 — 연구 어시스턴트가 실제로 보내는 요청 그대로다(services.research_work.concepts 의
      concepts_input → EXECUTOR.build: research_concepts.yaml 렌더와 LLM 파라미터). 응답은 EXECUTOR.parse·check 로 읽는다.
  (b) 주제 카드 초안 — 이 폴더의 topic_card_draft.yaml(06b 가 정식 프롬프트로 옮긴다). 보고서 절의 첫 향후 과제
      (sections[].future)를 씨앗으로, 그 절의 논문을 로컬 [E#] 로, 코드가 센 수치를 [F#] 로 준다. 서로 다른 절에서
      앞에서부터 --cards 장(절 논문이 3편 미만인 절은 건너뛴다 — 근거 3개 이상 규칙을 지킬 수 없다).
vLLM 을 HTTP 로 직접 부른다(scripts/eval_answer_quality.py 의 _chat 방식, 재시도 없음 — 실패는 표에 남긴다).
DB 를 읽지도 쓰지도 않는다. 미달이면 그 작업을 gemma 로 돌린다(라우팅 상수 한 줄 — spec §8).

실행 (서버 — research/ 는 앱 이미지에 없다. 이 폴더를 /data/nl-lib/data/round06-qwen-check/ 로 옮긴다):
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round06-qwen-check/check.py \
    --api http://localhost:8000/api --pairs /app/data/research_eval/pairs.json
  --qwen-url·--qwen-model·--gemma-url·--gemma-model 을 주지 않으면 앱 설정(VLM_BASE_URL·VLM_MODEL·LLM_BASE_URL·LLM_MODEL)을 쓴다.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))   # 개발 PC 에서 돌릴 때 — 컨테이너는 PYTHONPATH=/app

PAPERS_PER_CARD = 5
MIN_CARD_EVIDENCE = 3
_YEAR = re.compile(r"(?:19|20)\d{2}")
_FIGURE = re.compile(r"\[F(\d+)\]")
_ABSOLUTE = re.compile(r"전무|최초|연구가 없|연구되지 않")


def endpoints(args: argparse.Namespace) -> dict[str, tuple[str, str]]:
    """{"Qwen": (base_url, model), "gemma": (base_url, model)} — 인자가 없으면 앱 설정."""
    given = (args.qwen_url, args.qwen_model, args.gemma_url, args.gemma_model)
    if all(given):
        qwen_url, qwen_model, gemma_url, gemma_model = given
    else:
        from core.config import get_settings

        cfg = get_settings()
        qwen_url, qwen_model = args.qwen_url or cfg.VLM_BASE_URL, args.qwen_model or cfg.VLM_MODEL
        gemma_url, gemma_model = args.gemma_url or cfg.LLM_BASE_URL, args.gemma_model or cfg.LLM_MODEL
    return {"Qwen": (qwen_url.rstrip("/"), qwen_model), "gemma": (gemma_url.rstrip("/"), gemma_model)}


def call(client: httpx.Client, base_url: str, model: str, messages: list[dict], params: dict) -> dict:
    """llm_client.chat_full 의 openai 본문과 같은 모양으로 한 번 부른다(재시도 없음)."""
    from services.research_work.generate import CALL_TIMEOUT

    started = time.monotonic()
    try:
        res = client.post(f"{base_url}/chat/completions",
                          json={"model": model, "messages": messages, **params}, timeout=CALL_TIMEOUT)
        res.raise_for_status()
        choice = res.json()["choices"][0]
        content, finish, error = (choice["message"]["content"] or "").strip(), choice.get("finish_reason"), None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        content, finish, error = "", None, f"{type(e).__name__}: {e}"
    return {"content": content, "finish": finish, "seconds": time.monotonic() - started, "error": error}


def _job_view(job: dict) -> SimpleNamespace:
    """concepts_input 은 ResearchJob 을 받는다 — GET /api/research/{id} 응답에서 같은 이름의 속성만 옮긴다."""
    return SimpleNamespace(id=job["job_id"], question=job["question"], plan=job.get("plan") or [],
                           report=job.get("report") or {})


def concepts_request(job: dict) -> tuple[list[dict], dict]:
    from services.research_work.concepts import EXECUTOR, concepts_input

    return EXECUTOR.build(concepts_input(_job_view(job)))


def read_concepts(run: dict) -> dict:
    from services.research_work.concepts import EXECUTOR

    out = EXECUTOR.parse(run["content"]) if not run["error"] else None
    return {**run, "concepts": None if out is None else out["concepts"],
            "check": out is not None and EXECUTOR.check(out)}


def _year(pub_date: str | None) -> int | None:
    m = _YEAR.search(pub_date or "")
    return int(m.group(0)) if m else None


def card_seeds(report: dict, limit: int) -> list[dict]:
    """서로 다른 절의 첫 향후 과제를 앞 절부터 limit 개. 그 절의 논문(앞 5편)이 로컬 [E#], 수치가 [F#].

    절 논문이 MIN_CARD_EVIDENCE 편 미만인 절은 건너뛴다 — 근거 3개 이상 규칙을 어느 모델도 지킬 수 없어
    형식 검사가 두 모델을 가르지 못한다(목록에 없는 번호를 지어내게 부추기기도 한다).
    근거가 없는 하위질문은 절이 되지 않아 절 순번과 trail 순번이 어긋난다 — 채택 수는 소제목(= 하위질문)으로 찾는다.
    """
    from services.research.citations import strip_markers

    evidence = report.get("evidence") or {}
    meta = {e["cnts_id"]: e.get("meta") or {} for e in evidence.values()}
    adopted = {t.get("subquestion"): t.get("evidence_count") for t in report.get("trail") or []}
    corpus = report.get("range") or {}
    seeds = []
    for idx, sec in enumerate(report.get("sections") or []):
        futures = [f for f in sec.get("future") or [] if (f.get("text") or "").strip()]
        if not futures:
            continue
        cnts = [p["cnts_id"] for p in sec.get("papers") or [] if p["cnts_id"] in meta][:PAPERS_PER_CARD]
        if len(cnts) < MIN_CARD_EVIDENCE:
            continue
        papers = [{"id": f"E{n}", "title": meta[c].get("title") or "", "year": _year(meta[c].get("pub_date"))}
                  for n, c in enumerate(cnts, start=1)]
        facts = []
        if adopted.get(sec.get("heading")) is not None:
            facts.append(f"이 하위질문에서 채택한 논문 수: {adopted[sec['heading']]}편")
        years = [p["year"] for p in papers if p["year"]]
        if years:
            facts.append(f"근거 논문 중 가장 최근 연도: {max(years)}년")
        if corpus.get("n_papers"):
            facts.append(f"소장 KCI 적재분: {corpus['n_papers']:,}편({corpus.get('from')}~{corpus.get('to')}년)")
        seeds.append({
            "section": idx + 1, "heading": sec.get("heading", ""),
            "seed": strip_markers(futures[0]["text"]),
            "papers": papers,
            "figures": [{"id": f"F{n}", "text": t} for n, t in enumerate(facts, start=1)],
        })
        if len(seeds) >= limit:
            break
    return seeds


def card_request(seed: dict) -> tuple[list[dict], dict]:
    from services.prompts import PromptLibrary

    system, user, params = PromptLibrary(HERE).get("topic_card_draft").render(
        seed=seed["seed"],
        evidence_list="\n".join(f"[{p['id']}] {p['title']} ({p['year'] or '연도 미상'})" for p in seed["papers"]),
        figure_list="\n".join(f"[{f['id']}] {f['text']}" for f in seed["figures"]),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], params


def card_problems(card: dict | None, seed: dict) -> list[str]:
    """형식 검사 — 근거는 문자열·3개 이상·목록 안 번호, [F#] 사용·[F#] 밖 숫자·단정 표현."""
    if card is None:
        return ["JSON 아님"]
    problems = [f"{key} 없음" for key in ("title", "question", "figure_sentence")
                if not isinstance(card.get(key), str) or not card[key].strip()]
    local = {p["id"] for p in seed["papers"]}
    raw = card.get("evidence") if isinstance(card.get("evidence"), list) else []
    # 모델이 [{"id": "E1"}] 처럼 문자열이 아닌 항목을 내면 집합에 넣을 수 없다 — 빼고 문제로 남긴다
    cited = [e for e in raw if isinstance(e, str)]
    if len(cited) < len(raw):
        problems.append(f"문자열이 아닌 근거 {len(raw) - len(cited)}개")
    valid = {e for e in cited if e in local}
    if len(valid) < MIN_CARD_EVIDENCE:
        problems.append(f"유효 근거 {len(valid)}개({MIN_CARD_EVIDENCE}개 미만)")
    stray = [str(e) for e in cited if e not in local]
    if stray:
        problems.append(f"없는 근거 번호 {', '.join(stray)}")
    sentence = card.get("figure_sentence") if isinstance(card.get("figure_sentence"), str) else ""
    used = {f"F{n}" for n in _FIGURE.findall(sentence)}
    if not used:
        problems.append("[F#] 없음")
    unknown = used - {f["id"] for f in seed["figures"]}
    if unknown:
        problems.append(f"없는 수치 번호 {', '.join(sorted(unknown))}")
    if re.search(r"\d", _FIGURE.sub("", sentence)):
        problems.append("[F#] 밖의 숫자")
    texts = " ".join(str(card.get(k) or "") for k in ("title", "question", "figure_sentence"))
    if _ABSOLUTE.search(texts):
        problems.append("단정 표현")
    return problems


def read_card(run: dict, seed: dict) -> dict:
    from services.research.llm_json import extract_json

    card = extract_json(run["content"]) if not run["error"] else None
    return {**run, "card": card, "problems": card_problems(card, seed)}


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _timing(run: dict) -> str:
    if run["error"]:
        return f"오류 {run['error']}"
    return f"{run['seconds']:.1f}초 · {run['finish']}"


def _table(names: list[str], rows: list[tuple[str, list[str]]]) -> list[str]:
    lines = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    lines += [f"| {label} | " + " | ".join(_cell(v) for v in values) + " |" for label, values in rows]
    return lines


def _raw(runs: dict[str, dict]) -> list[str]:
    lines = ["", "<details><summary>원문</summary>", ""]
    for name, run in runs.items():
        lines += [f"**{name}**", "", "````text", run["content"] or "(빈 응답)", "````", ""]
    return lines + ["</details>", ""]


def render_markdown(key: str, job: dict, eps: dict[str, tuple[str, str]], concepts: dict[str, dict],
                    cards: list[tuple[dict, dict[str, dict]]]) -> str:
    names = list(eps)
    lines = [f"# {key} - {job['question']}", "",
             f"- 잡: `{job['job_id']}` (run_pair.py 의 갈래 0)"]
    lines += [f"- {name}: `{model}` @ {url}" for name, (url, model) in eps.items()]
    lines += ["- 사람이 볼 것: 한국어가 자연스러운가, 개념이 원 질문의 핵심인가, 카드의 제목·연구 질문을 고른 근거가 받치는가",
              "", "## 핵심 개념 (research_concepts.yaml)", ""]
    lines += _table(names, [
        ("개념", [" · ".join(r["concepts"]) if r["concepts"] else ("읽지 못함" if r["concepts"] is None else "(빈 목록)")
                for r in concepts.values()]),
        ("내용 검사(2개 이상)", ["통과" if r["check"] else "미달" for r in concepts.values()]),
        ("시간·끝난 이유", [_timing(r) for r in concepts.values()]),
    ])
    lines += _raw(concepts)
    for n, (seed, runs) in enumerate(cards, start=1):
        lines += [f"## 주제 카드 초안 {n} - 절 {seed['section']} 「{seed['heading']}」", "",
                  f"- 씨앗: {seed['seed']}", "- 근거 논문:"]
        lines += [f"  - [{p['id']}] {p['title']} ({p['year'] or '연도 미상'})" for p in seed["papers"]]
        lines += ["- 수치:"] + [f"  - [{f['id']}] {f['text']}" for f in seed["figures"]] + [""]

        def field(run: dict, key: str) -> str:
            card = run["card"] or {}
            value = card.get(key)
            return ", ".join(map(str, value)) if isinstance(value, list) else str(value or "")

        lines += _table(names, [
            ("제목", [field(r, "title") for r in runs.values()]),
            ("연구 질문", [field(r, "question") for r in runs.values()]),
            ("근거", [field(r, "evidence") for r in runs.values()]),
            ("수치 문장", [field(r, "figure_sentence") for r in runs.values()]),
            ("형식 검사", [" · ".join(r["problems"]) or "통과" for r in runs.values()]),
            ("시간·끝난 이유", [_timing(r) for r in runs.values()]),
        ])
        lines += _raw(runs)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description="Qwen 한국어 품질 표본 확인 (1회성, DB 를 쓰지 않는다)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--pairs", required=True, type=Path, help="scripts/research_eval/run_pair.py 출력(갈래 0 잡을 읽는다)")
    ap.add_argument("--out-dir", type=Path, default=HERE / "out")
    ap.add_argument("--cards", type=int, default=3, help="잡마다 주제 카드 초안 수(서로 다른 절)")
    ap.add_argument("--qwen-url")
    ap.add_argument("--qwen-model")
    ap.add_argument("--gemma-url")
    ap.add_argument("--gemma-model")
    args = ap.parse_args(argv)

    api = args.api.rstrip("/")
    eps = endpoints(args)
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        for key, arms in pairs.items():
            res = client.get(f"{api}/research/{arms['0']}")
            res.raise_for_status()
            job = res.json()
            if job.get("status") != "completed" or not job.get("report"):
                print(f"[{key}] 잡 {arms['0']} 이 완료되지 않았다({job.get('status')}) - 건너뛴다")
                continue
            messages, params = concepts_request(job)
            concepts = {name: read_concepts(call(client, url, model, messages, params))
                        for name, (url, model) in eps.items()}
            cards = []
            for seed in card_seeds(job["report"], args.cards):
                messages, params = card_request(seed)
                cards.append((seed, {name: read_card(call(client, url, model, messages, params), seed)
                                     for name, (url, model) in eps.items()}))
            path = args.out_dir / f"{key}.md"
            path.write_text(render_markdown(key, job, eps, concepts, cards), encoding="utf-8")
            print(f"[{key}] 개념 1 + 카드 {len(cards)} -> {path}")
    finally:
        if own:
            client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
