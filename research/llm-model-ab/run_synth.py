"""딥리서치 종합 — 모델(팔) 비교. 운영 보고서를 ResearchState 로 다시 만들어(../synth-prompt-ab/rebuild.py) 저장소의 실제
synthesize 코드로 팔마다 다시 쓴다 (1회성, 운영 DB·API 에 쓰지 않음).

프롬프트·코드는 저장소 그대로다. 바꾸는 것은 synthesizer 모듈의 chat 하나 — 팔의 주소·모델 이름으로 보낸다(contextvar 로
잡마다 팔을 고른다). 호출마다 원문·걸린 시간·usage(토큰 수)·실패를 남긴다. 운영 llm_client 처럼 일시적 실패는 한 번 더 보낸다.

    python run_synth.py --arms arms_aa.json [--repeats 1] [--concurrency 2] [--out gen_synth]
결과 <out>/<팔>_<보고서 태그>_r<회>.json — 이미 있으면 건너뛴다(이어 돌리기).
"""
import argparse
import asyncio
import contextvars
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(HERE.parent / "synth-prompt-ab"))

import rebuild  # noqa: E402  (저장소 app/ 를 sys.path 에 넣는다)
import services.research.synthesizer as syn  # noqa: E402
from services.research.llm_json import extract_json  # noqa: E402

JOBS = json.loads((HERE / "jobs.json").read_text(encoding="utf-8"))
rebuild.JOBS = {tag: str(HERE / "jobs" / f"job_{jid}.json") for tag, jid in JOBS.items()}

arm_var: contextvars.ContextVar[str] = contextvars.ContextVar("arm")
rec_var: contextvars.ContextVar[dict] = contextvars.ContextVar("rec")
ARMS: dict[str, dict] = {}
_TRANSIENT = (httpx.TimeoutException, httpx.TransportError)


class Runtime:
    client: httpx.AsyncClient
    sem: asyncio.Semaphore


RT = Runtime()


async def arm_chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
    """synthesizer 가 부르는 chat 자리 — 지금 잡의 팔(arm_var)로 보낸다. 운영과 같은 timeout 을 쓴다."""
    arm = ARMS[arm_var.get()]
    call = {"raw": None, "finish": None, "error": None, "sec": None, "usage": None, "attempts": 0,
            "prompt_chars": sum(len(m["content"]) for m in messages)}
    rec_var.get()["calls"].append(call)
    body = {"model": arm["model"], "messages": messages, **(params or {}), **arm.get("extra", {})}
    t0 = time.time()
    try:
        for attempt in (1, 2):
            call["attempts"] = attempt
            try:
                async with RT.sem:
                    # 걸린 시간은 세마포어를 잡은 뒤부터 잰다 — 동시 칸을 기다린 시간은 모델 속도가 아니다
                    t0 = time.time()
                    resp = await RT.client.post(arm["url"], json=body, timeout=timeout)
                resp.raise_for_status()
                break
            except _TRANSIENT:
                if attempt == 2:
                    raise
        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        # reasoning parser 를 켠 모델(Gemma 4)은 답이 reasoning 칸으로 빠지면 content 가 None 이다 — 따로 남긴다
        call.update(raw=msg.get("content"), reasoning=msg.get("reasoning") or msg.get("reasoning_content"),
                    finish=choice.get("finish_reason"), usage=data.get("usage"))
        return call["raw"]
    except httpx.HTTPError as e:
        call["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        call["sec"] = round(time.time() - t0, 2)


syn.chat = arm_chat


def format_issues(raw: str | None, reasoning: str | None = None) -> list[str]:
    """한 호출 원문이 종합이 받는 모양인가(synth-prompt-ab/run_ab.py check_raw 의 줄인 판)."""
    if raw is None:
        return ["답이 reasoning 칸으로 감"] if reasoning else ["전송 오류"]
    data = extract_json(raw)
    if data is None:
        return ["JSON 파싱 실패"]
    issues = []
    if not isinstance(data.get("intro"), (str, list)):
        issues.append("intro 모양")
    if not isinstance(data.get("summaries"), dict):
        issues.append("summaries 모양")
    if not isinstance(data.get("future"), list):
        issues.append("future 모양")
    if syn._PLACEHOLDER in raw:
        issues.append("[E#] 자리표시자 그대로")
    return issues


async def one(arm: str, tag: str, run: int, out_dir: Path) -> str:
    path = out_dir / f"{arm}_{tag}_r{run}.json"
    if path.exists():
        return f"skip {path.name}"
    arm_var.set(arm)
    rec = {"calls": []}
    rec_var.set(rec)
    job, state = rebuild.state_of(tag)
    t0 = time.time()
    out = {"arm": arm, "model": ARMS[arm]["model"], "tag": tag, "job_id": job["job_id"], "question": job["question"],
           "run": run}
    try:
        report = await syn.synthesize(state)
        out.update(sections=report["sections"], limitations=report["limitations"], error=None)
    except Exception as e:  # 절이 전부 실패하면 ValueError — 기록하고 넘어간다
        out.update(sections=None, limitations=None, error=f"{type(e).__name__}: {e}")
    for c in rec["calls"]:
        c["issues"] = format_issues(c["raw"], c.get("reasoning"))
    out.update(calls=rec["calls"], elapsed=round(time.time() - t0, 1))
    # 근거 대목(chunks)은 판정 묶음이 jobs/ 에서 읽는다 — 결과 파일에는 싣지 않는다
    for s in out["sections"] or []:
        s.pop("chunk_scores", None)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    bad = sum(1 for c in rec["calls"] if c["issues"])
    return (f"done {path.name} {out['elapsed']}s 절 {len(out['sections'] or [])} 호출 {len(rec['calls'])} 형식문제 {bad}"
            + (f" ERR {out['error']}" if out["error"] else ""))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--concurrency", type=int, default=2, help="동시 요청 상한(운영 gemma 가 인덱싱도 받으면 낮게)")
    ap.add_argument("--out", default="gen_synth")
    ap.add_argument("--tags", default=",".join(JOBS))
    args = ap.parse_args()
    ARMS.update({k: v for k, v in json.loads(Path(args.arms).read_text(encoding="utf-8")).items() if not k.startswith("_")})
    out_dir = HERE / args.out
    out_dir.mkdir(exist_ok=True)
    RT.client = httpx.AsyncClient()
    RT.sem = asyncio.Semaphore(args.concurrency)
    # 회차 → 보고서 → 팔 순으로 섞어 넣는다 — 팔마다 서버 부하 조건이 비슷해지게
    jobs = [one(a, t, r, out_dir) for r in range(args.repeats) for t in args.tags.split(",") for a in ARMS]
    for fut in asyncio.as_completed(jobs):
        try:
            print(await fut, flush=True)
        except Exception as e:  # noqa: BLE001 — 한 잡 실패가 나머지를 막지 않게
            print("ERR", repr(e), flush=True)
    await RT.client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
