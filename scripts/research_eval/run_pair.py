r"""run_pair.py — critic 기준 스위치 두 갈래 실행 (HTTP 만, DB 를 읽지도 쓰지도 않는다)

고정 질문(questions.json)마다 딥리서치 잡 두 개를 만든다.
  갈래 0 — params {"critic_scope": 0}(지금 기준). 계획이 나오면 그 계획 그대로 승인한다.
  갈래 1 — params {"critic_scope": 1}(원 질문 기준). 같은 질문으로 만들고 승인 본문 plan 에 갈래 0 의
           계획을 넘긴다 — 같은 하위질문으로 돌려 두 갈래의 차이가 critic 하나뿐이게 한다.
두 잡 모두 x-session-id 를 보내지 않는다(created_by NULL — 브라우저당 실행 제한 밖). 실행 워커가 하나라
잡은 줄을 서서 차례로 돈다. 둘 다 completed 가 될 때까지 기다리고 {질문키: {"0": 잡 id, "1": 잡 id}} 를
--out JSON 에 질문마다 덧쓴다. 이미 있는 다른 질문의 기록은 남긴다 — 실패한 질문만 --only 로 다시 돌린다.
잡 id 는 만들자마자 찍고(실패해도 남은 잡을 찾을 수 있게), 상태 조회의 일시 오류는 몇 번 다시 조회한다.
전제: 운영 RESEARCH_QUEUE 가 딥리서치 전용 큐(q_research)여야 한다 — 적재 큐를 나눠 쓰는 모드면 갈래 0 이 도는
동안 갈래 1 승인이 429 shared_queue 로 막힌다.

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
TRANSIENT_RETRIES = 3


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


def _transient(e: httpx.HTTPError) -> bool:
    """잠깐 뒤 다시 조회하면 나을 수 있는 오류 — 연결·읽기 실패와 5xx(게이트웨이·재기동 중)."""
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return isinstance(e, httpx.TransportError)


def wait_for(client: httpx.Client, api: str, job_id: str, status: str, *, poll: float, timeout: float,
             sleep=time.sleep, clock=time.monotonic) -> dict:
    """잡이 status 가 될 때까지 poll 초마다 조회한다. 다른 종료 상태로 끝나거나 timeout 을 넘기면 예외.

    조회 한 번의 일시 오류(_transient)는 deadline 안에서 연달아 TRANSIENT_RETRIES 번까지 다시 조회한다 — 한 번의
    끊김으로 수 분 돈 질문을 잃지 않게. 그 밖의 HTTP 오류(4xx)는 바로 올린다.
    """
    deadline = clock() + timeout
    errors = 0
    while True:
        try:
            job = get_job(client, api, job_id)
        except httpx.HTTPError as e:
            errors += 1
            if not _transient(e) or errors > TRANSIENT_RETRIES or clock() >= deadline:
                raise
            print(f"  조회 일시 오류({errors}/{TRANSIENT_RETRIES}) {job_id}: {_reason(e)} - 다시 조회한다", flush=True)
            sleep(poll)
            continue
        errors = 0
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
    # 만들자마자 찍는다 — 이 뒤에 실패해도 어느 잡이 남았는지 안다
    print(f"  갈래 0 {arm0}", flush=True)
    plan = wait_for(client, api, arm0, "awaiting_approval", **wait)["plan"]
    approve(client, api, arm0)
    arm1 = create_job(client, api, question, 1)
    print(f"  갈래 1 {arm1}", flush=True)
    wait_for(client, api, arm1, "awaiting_approval", **wait)
    approve(client, api, arm1, plan)
    for job_id in (arm0, arm1):
        wait_for(client, api, job_id, "completed", **wait)
    return {"0": arm0, "1": arm1}


def load_pairs(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_pairs(path: Path, pairs: dict) -> None:
    """임시 파일에 쓰고 바꿔 끼운다 — 쓰는 도중에 끊겨도 앞서 완료한 질문의 기록이 깨지지 않는다."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(pairs, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


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
    # 첫 질문(약 4분)을 다 돌린 뒤에야 FileNotFoundError 가 나지 않게 시작할 때 만든다
    args.out.parent.mkdir(parents=True, exist_ok=True)
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
