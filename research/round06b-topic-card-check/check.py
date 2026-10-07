r"""check.py — 주제 카드 모델 재비교 (round06b, 1회성 — 계획 정함 6)

06a Qwen 표본(research/round06-qwen-check/)은 초안 프롬프트로 주제 카드를 Qwen 9 · gemma 4 로 봤지만, gemma 실패
대부분이 근거 칸에 논문 제목을 넣은 실수였다. 06b 는 정식 실행기(services.research_work.topic_card)가 그 실수를
코드로 되돌리고(정함 5) 수치 문장을 코드 틀로 만들며(정함 3) 근거 칩을 2개 이상으로 본다(정함 4). 같은 고정 질문의
갈래 0 잡(run_pair.py 출력 JSON)에 정식 실행기를 Qwen·gemma 에 똑같이 보내 out/<질문키>.md 와 out/summary.md 에
나란히 쓴다.
  - 카드 입력은 이어가기가 넣는 것 그대로다 — seeds.pick_seeds(report, limit=TOPIC_SEED_SLOTS) → seeds.topic_input.
  - 요청은 topic_card.EXECUTOR.build(research_topic_card.yaml 렌더와 LLM 파라미터), 응답은 EXECUTOR.parse → bind
    → check 로 읽는다. 재시도·넘김 없이 모델마다 한 번 부른다(두 모델의 첫 답을 견준다).
vLLM 을 HTTP 로 직접 부른다(round06-qwen-check/check.py 의 call 과 같다). DB 를 읽지도 쓰지도 않는다.
엔드포인트는 인자가 없으면 운영 생성이 부르는 곳(services.research_work.routing.endpoint)이다.

실행 (서버 — research/ 는 앱 이미지에 없다. 이 폴더를 /data/nl-lib/data/round06b-topic-card-check/ 로 옮긴다):
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round06b-topic-card-check/check.py \
    --api http://localhost:8000/api --pairs /app/data/research_eval/$RUN.json
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))   # 개발 PC 에서 돌릴 때 — 컨테이너는 PYTHONPATH=/app

_FIGURE = re.compile(r"\[(F\d+)\]")


def endpoints(args: argparse.Namespace) -> dict[str, tuple[str, str]]:
    """{"Qwen": (base_url, model), "gemma": (base_url, model)} — 인자가 없으면 운영 생성이 부르는 곳."""
    given = (args.qwen_url, args.qwen_model, args.gemma_url, args.gemma_model)
    if all(given):
        qwen_url, qwen_model, gemma_url, gemma_model = given
    else:
        from services.research_work.routing import GEMMA, QWEN, endpoint

        (cfg_qwen_url, cfg_qwen_model), (cfg_gemma_url, cfg_gemma_model) = endpoint(QWEN), endpoint(GEMMA)
        qwen_url, qwen_model = args.qwen_url or cfg_qwen_url, args.qwen_model or cfg_qwen_model
        gemma_url, gemma_model = args.gemma_url or cfg_gemma_url, args.gemma_model or cfg_gemma_model
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
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
        # 한 호출의 이상한 응답이 전체 실행을 멈추지 않게 표에 오류로 남긴다
        content, finish, error = "", None, f"{type(e).__name__}: {e}"
    return {"content": content, "finish": finish, "seconds": time.monotonic() - started, "error": error}


def card_inputs(job: dict) -> list[tuple[dict, dict]]:
    """이어가기가 넣는 카드 입력 그대로 — (씨앗, topic_input). topic_id 자리에는 카드 번호(1~)를 둔다."""
    from services.research_work.seeds import pick_seeds, topic_input
    from services.research_work.shapes import TOPIC_SEED_SLOTS

    report = job.get("report") or {}
    return [(seed, topic_input(job["question"], seed, report, n))
            for n, seed in enumerate(pick_seeds(report, limit=TOPIC_SEED_SLOTS), start=1)]


def judge(run: dict, card_input: dict) -> dict:
    """정식 실행기와 같은 순서로 읽는다 — parse → bind → check. 형식 통과 = check 통과(근거 칩 2개 이상)."""
    from services.research_work.shapes import MIN_TOPIC_EVIDENCE
    from services.research_work.topic_card import EXECUTOR, evidence_ids

    parsed = EXECUTOR.parse(run["content"]) if not run["error"] else None
    card = EXECUTOR.bind(parsed, card_input)["card"] if parsed is not None else None
    passed = card is not None and EXECUTOR.check({"card": card})
    problems: list[str] = []
    if run["error"]:
        problems.append("호출 실패")
    elif parsed is None:
        problems.append("JSON 아님")
    elif card is None:
        problems.append("제목·질문 없음")
    elif not passed:
        problems.append(f"근거 {len(card['evidence'])}개({MIN_TOPIC_EVIDENCE}개 미만)")
    dropped = 0
    if parsed is not None:
        found, _ = evidence_ids(parsed["evidence"], card_input["papers"])
        dropped = len(parsed["evidence"]) - len(found)
    return {**run, "card": card, "passed": passed, "dropped": dropped, "problems": problems}


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _table(names: list[str], rows: list[tuple[str, list[str]]]) -> list[str]:
    lines = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    lines += [f"| {label} | " + " | ".join(_cell(v) for v in values) + " |" for label, values in rows]
    return lines


def _timing(run: dict) -> str:
    if run["error"]:
        return f"오류 {run['error']}"
    return f"{run['seconds']:.1f}초 · {run['finish']}"


def _sentence(card: dict | None) -> str:
    """수치 문장의 [F#] 자리에 값을 넣어 읽기 좋게(화면 칩·Word 와 같은 값)."""
    if not card or not card.get("figure_sentence"):
        return ""
    values = {f["id"]: f["value"] for f in card.get("figures") or []}
    return _FIGURE.sub(lambda m: values.get(m.group(1), m.group(0)), card["figure_sentence"])


def _evidence(card: dict | None, card_input: dict) -> str:
    if not card:
        return ""
    by_cnts = {p["cnts_id"]: p for p in card_input["papers"]}
    return "<br>".join(f"[{by_cnts[c]['eid']}] {by_cnts[c]['title']}" for c in card["evidence"] if c in by_cnts)


def tally(results: list[dict[str, dict]], names: list[str]) -> dict[str, dict]:
    """모델별 셈 — 카드 수·형식 통과·근거 3개 이상·되돌린 근거·확인 필요 숫자가 있는 카드·바꾼 단정 표현·시간."""
    out = {}
    for name in names:
        runs = [r[name] for r in results]
        cards = [r["card"] for r in runs if r["card"]]
        out[name] = {
            "cards": len(runs),
            "passed": sum(1 for r in runs if r["passed"]),
            "three": sum(1 for c in cards if len(c["evidence"]) >= 3),
            "recovered": sum(c["checks"]["recovered"] for c in cards),
            "numbers": sum(1 for c in cards if c["checks"]["numbers"]),
            "softened": sum(c["checks"]["softened"] for c in cards),
            "seconds": sum(r["seconds"] for r in runs),
        }
    return out


def _summary_rows(t: dict[str, dict], names: list[str]) -> list[tuple[str, list[str]]]:
    def avg(name):
        n = t[name]["cards"]
        return f"{t[name]['seconds'] / n:.1f}초" if n else "-"

    return [
        ("형식 통과(근거 2개 이상)", [f"{t[n]['passed']}/{t[n]['cards']}" for n in names]),
        ("근거 3개 이상", [f"{t[n]['three']}/{t[n]['cards']}" for n in names]),
        ("제목에서 되돌린 근거", [str(t[n]["recovered"]) for n in names]),
        ("확인 필요 숫자가 있는 카드", [str(t[n]["numbers"]) for n in names]),
        ("바꾼 단정 표현", [str(t[n]["softened"]) for n in names]),
        ("평균 시간", [avg(n) for n in names]),
    ]


def render_markdown(key: str, job: dict, eps: dict[str, tuple[str, str]],
                    cards: list[tuple[dict, dict, dict[str, dict]]]) -> str:
    names = list(eps)
    lines = [f"# {key} - {job['question']}", "",
             f"- 잡: `{job['job_id']}` (run_pair.py 의 갈래 0)"]
    lines += [f"- {name}: `{model}` @ {url}" for name, (url, model) in eps.items()]
    lines += ["- 카드 입력: 이어가기와 같은 씨앗(seeds.pick_seeds, 최대 4장) · 정식 실행기(topic_card.EXECUTOR —"
              " research_topic_card.yaml)의 build·parse·bind·check, 재시도 없이 모델마다 한 번",
              "- 사람이 볼 것: 제목·연구 질문이 원 질문의 대상·맥락 안에 있는가, 고른 근거가 그 주제를 직접 받치는가,"
              " 씨앗을 베끼지 않고 구체적인가",
              "", "## 요약", ""]
    lines += _table(names, _summary_rows(tally([runs for _, _, runs in cards], names), names))
    for n, (seed, card_input, runs) in enumerate(cards, start=1):
        lines += ["", f"## 카드 {n} - 「{seed['heading']}」 ({seed['key']})", "",
                  f"- 씨앗: {seed['text']}", "- 근거 후보:"]
        lines += [f"  - [{p['eid']}] {p['title']} ({p['year'] or '연도 미상'})" for p in card_input["papers"]]
        lines.append("")
        lines += _table(names, [
            ("제목", [(r["card"] or {}).get("title", "") for r in runs.values()]),
            ("연구 질문", [(r["card"] or {}).get("question", "") for r in runs.values()]),
            ("근거", [_evidence(r["card"], card_input) for r in runs.values()]),
            ("수치 문장(코드)", [_sentence(r["card"]) for r in runs.values()]),
            ("형식 검사", [" · ".join(r["problems"]) or "통과" for r in runs.values()]),
            ("근거 수·되돌림·버림", [
                f"{len(r['card']['evidence'])}개 · 되돌림 {r['card']['checks']['recovered']} · 버림 {r['dropped']}"
                if r["card"] else f"- · 버림 {r['dropped']}" for r in runs.values()]),
            ("확인 필요 숫자", [", ".join((r["card"] or {}).get("checks", {}).get("numbers") or []) or "없음"
                           for r in runs.values()]),
            ("시간·끝난 이유", [_timing(r) for r in runs.values()]),
        ])
        lines += ["", "<details><summary>원문</summary>", ""]
        for name, run in runs.items():
            lines += [f"**{name}**", "", "````text", run["content"] or "(빈 응답)", "````", ""]
        lines.append("</details>")
    return "\n".join(lines) + "\n"


def render_summary(eps: dict[str, tuple[str, str]], per_key: dict[str, dict[str, dict]]) -> str:
    names = list(eps)
    lines = ["# 주제 카드 재비교 요약 (Qwen · gemma)", "",
             "판정 규칙(계획 정함 6): ① 형식 통과(근거 칩 2개 이상) 카드 수가 많은 쪽 ② 그 차이가 2장 이하이면 질문별"
             " out/<질문키>.md 를 읽은 내용 판정에서 다섯 질문 중 셋 이상 나은 쪽.", "",
             "| 질문키 | " + " | ".join(f"{n} 형식 통과" for n in names) + " | "
             + " | ".join(f"{n} 근거 3개 이상" for n in names) + " |",
             "|---|" + "---|" * (2 * len(names))]
    totals = {n: {"passed": 0, "three": 0, "cards": 0} for n in names}
    for key, t in per_key.items():
        for n in names:
            for k in totals[n]:
                totals[n][k] += t[n][k]
        lines.append(f"| {key} | " + " | ".join(f"{t[n]['passed']}/{t[n]['cards']}" for n in names) + " | "
                     + " | ".join(f"{t[n]['three']}/{t[n]['cards']}" for n in names) + " |")
    lines.append("| 합계 | " + " | ".join(f"{totals[n]['passed']}/{totals[n]['cards']}" for n in names) + " | "
                 + " | ".join(f"{totals[n]['three']}/{totals[n]['cards']}" for n in names) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description="주제 카드 모델 재비교 (1회성, DB 를 쓰지 않는다)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--pairs", required=True, type=Path, help="scripts/research_eval/run_pair.py 출력(갈래 0 잡을 읽는다)")
    ap.add_argument("--out-dir", type=Path, default=HERE / "out")
    ap.add_argument("--qwen-url")
    ap.add_argument("--qwen-model")
    ap.add_argument("--gemma-url")
    ap.add_argument("--gemma-model")
    args = ap.parse_args(argv)

    api = args.api.rstrip("/")
    eps = endpoints(args)
    names = list(eps)
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    per_key: dict[str, dict[str, dict]] = {}
    try:
        for key, arms in pairs.items():
            try:
                res = client.get(f"{api}/research/{arms['0']}")
                res.raise_for_status()
                job = res.json()
            except httpx.HTTPError as e:
                # 한 질문의 조회 실패로 남은 질문을 버리지 않는다
                print(f"[{key}] 잡 {arms['0']} 을 읽지 못했다({type(e).__name__}: {e}) - 건너뛴다")
                continue
            if job.get("status") != "completed" or not job.get("report"):
                print(f"[{key}] 잡 {arms['0']} 이 완료되지 않았다({job.get('status')}) - 건너뛴다")
                continue
            from services.research_work.topic_card import EXECUTOR

            cards = []
            for seed, card_input in card_inputs(job):
                messages, params = EXECUTOR.build(card_input)
                runs = {name: judge(call(client, url, model, messages, params), card_input)
                        for name, (url, model) in eps.items()}
                cards.append((seed, card_input, runs))
            per_key[key] = tally([runs for _, _, runs in cards], names)
            path = args.out_dir / f"{key}.md"
            path.write_text(render_markdown(key, job, eps, cards), encoding="utf-8")
            print(f"[{key}] 카드 {len(cards)}장 -> {path} "
                  + " · ".join(f"{n} 통과 {per_key[key][n]['passed']}" for n in names))
    finally:
        if own:
            client.close()
    summary = args.out_dir / "summary.md"
    summary.write_text(render_summary(eps, per_key), encoding="utf-8")
    print(f"요약 -> {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
