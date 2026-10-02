r"""run_pair.py — critic 기준 스위치 두 갈래 실행 (HTTP 만, DB 를 읽지도 쓰지도 않는다)

고정 질문(questions.json)마다 딥리서치 잡 두 개를 만든다.
  갈래 0 — params {"critic_scope": 0}(지금 기준). 계획이 나오면 그 계획 그대로 승인한다.
  갈래 1 — params {"critic_scope": 1}(원 질문 기준). 같은 질문으로 만들고 승인 본문 plan 에 갈래 0 의
           계획을 넘긴다 — 같은 하위질문으로 돌려 두 갈래의 차이가 critic 하나뿐이게 한다.
두 잡 모두 x-session-id 를 보내지 않는다(created_by NULL — 브라우저당 실행 제한 밖). 실행 워커가 하나라
잡은 줄을 서서 차례로 돈다. 둘 다 completed 가 될 때까지 기다리고 {질문키: {"0": 잡 id, "1": 잡 id}} 를
--out JSON 에 질문마다 덧쓴다. 이미 있는 다른 질문의 기록은 남긴다 — 실패한 질문만 --only 로 다시 돌린다.

실행 (서버 — scripts/ 는 앱 이미지에 없어 데이터 바인드 마운트로 넣는다. 함정 4번):
  docker exec nl-lib-fastapi python /app/data/research_eval/run_pair.py \
    --api http://localhost:8000/api --out /app/data/research_eval/pairs.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "questions.json"
TERMINAL = ("completed", "failed", "canceled")


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def create_job(client: httpx.Client, api: str, question: str, critic_scope: int) -> str:
    res = client.post(f"{api}/research",
                      json={"question": question, "params": {"critic_scope": critic_scope}})
    res.raise_for_status()
    return res.json()["job_id"]


def get_job(client: httpx.Client, api: str, job_id: str) -> dict:
    res = client.get(f"{api}/research/{job_id}")
    res.raise_for_status()
    return res.json()


def approve(client: httpx.Client, api: str, job_id: str, plan: list[str] | None = None) -> None:
    """plan 이 None 이면 본문 없이 — 잡이 세운 계획 그대로 승인한다."""
    res = client.post(f"{api}/research/{job_id}/approve", json=None if plan is None else {"plan": plan})
    res.raise_for_status()


def wait_for(client: httpx.Client, api: str, job_id: str, status: str, *, poll: float, timeout: float,
             sleep=time.sleep, clock=time.monotonic) -> dict:
    """잡이 status 가 될 때까지 poll 초마다 조회한다. 다른 종료 상태로 끝나거나 timeout 을 넘기면 예외."""
    deadline = clock() + timeout
    while True:
        job = get_job(client, api, job_id)
        if job["status"] == status:
            return job
        if job["status"] in TERMINAL:
            raise RuntimeError(f"{job_id} 가 {job['status']} 로 끝났다: {job.get('last_error')}")
        if clock() >= deadline:
            raise TimeoutError(f"{job_id} 가 {timeout:.0f}초 안에 {status} 가 되지 않았다(지금 {job['status']})")
        sleep(poll)


def run_question(client: httpx.Client, api: str, question: str, *, poll: float, timeout: float,
                 sleep=time.sleep, clock=time.monotonic) -> dict[str, str]:
    """한 질문의 두 갈래를 만들어 승인하고 둘 다 completed 가 될 때까지 기다린다."""
    wait = {"poll": poll, "timeout": timeout, "sleep": sleep, "clock": clock}
    arm0 = create_job(client, api, question, 0)
    plan = wait_for(client, api, arm0, "awaiting_approval", **wait)["plan"]
    approve(client, api, arm0)
    arm1 = create_job(client, api, question, 1)
    wait_for(client, api, arm1, "awaiting_approval", **wait)
    approve(client, api, arm1, plan)
    for job_id in (arm0, arm1):
        wait_for(client, api, job_id, "completed", **wait)
    return {"0": arm0, "1": arm1}


def load_pairs(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_pairs(path: Path, pairs: dict) -> None:
    path.write_text(json.dumps(pairs, ensure_ascii=False, indent=1), encoding="utf-8")


def _reason(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code} {e.request.url} {e.response.text[:300]}"
    return str(e)


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description="critic 기준 스위치 두 갈래 실행 (HTTP 만)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--out", required=True, type=Path, help="{질문키: {\"0\": 잡 id, \"1\": 잡 id}} 를 덧쓸 JSON")
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    ap.add_argument("--only", default="", help="이 질문키만(쉼표로 이음). 실패한 질문을 다시 돌릴 때")
    ap.add_argument("--poll", type=float, default=5.0, help="상태 조회 간격(초)")
    ap.add_argument("--timeout", type=float, default=3600.0, help="잡 하나가 한 상태에 이르기까지 기다릴 초")
    args = ap.parse_args(argv)

    api = args.api.rstrip("/")
    questions = load_questions(args.questions)
    only = {k for k in args.only.split(",") if k}
    unknown = only - {q["key"] for q in questions}
    if unknown:
        print(f"모르는 질문키: {', '.join(sorted(unknown))}")
        return 2
    if only:
        questions = [q for q in questions if q["key"] in only]

    own = client is None
    client = client or httpx.Client(timeout=30.0)
    failed: list[str] = []
    try:
        for q in questions:
            print(f"[{q['key']}] {q['question']}", flush=True)
            try:
                pair = run_question(client, api, q["question"], poll=args.poll, timeout=args.timeout)
            except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
                failed.append(q["key"])
                print(f"  실패: {_reason(e)}", flush=True)
                continue
            pairs = load_pairs(args.out)
            pairs[q["key"]] = pair
            save_pairs(args.out, pairs)
            print(f"  완료: 갈래 0 {pair['0']} · 갈래 1 {pair['1']}", flush=True)
    finally:
        if own:
            client.close()
    if failed:
        print(f"실패한 질문 {len(failed)}개 - --only {','.join(failed)} 로 다시 돌린다")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
