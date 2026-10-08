"""smoke_check.py — check.py 를 가짜 API·가짜 vLLM 으로 한 번 돌려 본다 (네트워크·DB 없음, 1회성)

운영에서 돌리기 전에 개발 PC 에서 카드 입력 만들기(이어가기와 같은 씨앗·정식 실행기의 요청)·응답 읽기(parse →
bind → check)·마크다운과 요약 쓰기가 끝까지 도는지만 본다. 품질은 운영 실행 결과(out/)를 사람이 본다.
사용법(저장소 루트에서): python research/round06b-topic-card-check/smoke_check.py  → 마지막 줄 'smoke OK'
"""
import json
import sys
import tempfile
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check  # noqa: E402

JOB = {
    "job_id": "job-1", "question": "컴퓨팅 자원에 대한 연구가 궁금해", "status": "completed",
    "plan": ["그리드 컴퓨팅의 자원 관리 기법", "분산 컴퓨팅 표준화 동향", "클라우드 자원 스케줄링",
             "고성능 컴퓨팅 활용 분야"],
    "report": {
        "question": "컴퓨팅 자원에 대한 연구가 궁금해",
        "range": {"from": "1998", "to": "2013", "n_papers": 125000},
        "sections": [
            {"heading": "그리드 컴퓨팅의 자원 관리 기법",
             "papers": [{"cnts_id": c} for c in ("A", "B", "C", "D")],
             "future": [{"text": "그리드 자원의 동적 배분을 실증할 필요가 있다 [E2]", "evidence": ["E2"]}]},
            {"heading": "클라우드 자원 스케줄링",
             "papers": [{"cnts_id": c} for c in ("E", "A", "D")],
             "future": [{"text": "가상화 환경의 스케줄링 비용을 비교해야 한다 [E5][E1]", "evidence": ["E5", "E1"]}]},
            # 향후 과제는 있지만 근거 후보가 1편 — 근거 2개를 받칠 수 없어 씨앗이 되지 않는다
            {"heading": "고성능 컴퓨팅 활용 분야", "papers": [{"cnts_id": "C"}],
             "future": [{"text": "고성능 계산 수요를 분야별로 조사해야 한다 [E3]", "evidence": ["E3"]}]},
        ],
        "evidence": {
            "E1": {"cnts_id": "A", "meta": {"title": "그리드 컴퓨팅 자원 관리", "pub_date": "2009-05"}},
            "E2": {"cnts_id": "B", "meta": {"title": "동적 자원 배분 기법", "pub_date": "2011"}},
            "E3": {"cnts_id": "C", "meta": {"title": "고성능 계산 환경 구축", "pub_date": "2004"}},
            "E4": {"cnts_id": "D", "meta": {"title": "분산 작업 스케줄러", "pub_date": None}},
            "E5": {"cnts_id": "E", "meta": {"title": "가상 머신 배치 최적화", "pub_date": "2013-02"}},
        },
        # 근거가 없어 절이 되지 않은 하위질문이 가운데 끼어 있다 — 씨앗은 소제목으로 trail 과 잇는다
        "trail": [{"subquestion": "그리드 컴퓨팅의 자원 관리 기법", "evidence_count": 15, "verdict": "sufficient"},
                  {"subquestion": "분산 컴퓨팅 표준화 동향", "evidence_count": 0, "verdict": "insufficient",
                   "note": "표준화 연구를 찾지 못했다"},
                  {"subquestion": "클라우드 자원 스케줄링", "evidence_count": 9, "verdict": "sufficient"},
                  {"subquestion": "고성능 컴퓨팅 활용 분야", "evidence_count": 1, "verdict": "insufficient",
                   "note": "활용 분야 연구가 적다"}],
    },
}
QWEN_CARD = {"title": "그리드 자원 동적 배분의 실증", "question": "동적 배분은 작업 대기 시간을 줄이는가?",
             "evidence": ["E1", "E2", "E3"]}
# gemma 카드 1 — 근거 칸에 논문 제목(06a 표본의 같은 실수) → 코드가 번호로 되돌린다
GEMMA_TITLES = {"title": "그리드 자원 배분 기법 비교", "question": "어떤 배분 기법이 효율적인가?",
                "evidence": ["동적 자원 배분 기법", "그리드 컴퓨팅 자원 관리 (2009)"]}
# gemma 카드 2 — 근거 1개(형식 미달)·제목에 숫자·단정 표현
GEMMA_THIN = {"title": "2013년 이후 최초의 가상화 비용 비교", "question": "비용은 어떻게 다른가?",
              "evidence": ["E1", "없는 논문"]}


def main() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.test":
            if request.url.path.endswith("/job-1"):
                return httpx.Response(200, json=JOB)
            return httpx.Response(404, json={"detail": "job not found"})
        requests.append(request)
        user = json.loads(request.content)["messages"][-1]["content"]
        first = "그리드 자원의 동적 배분" in user
        if request.url.host == "qwen.test":
            card = QWEN_CARD
        else:
            card = GEMMA_TITLES if first else GEMMA_THIN
        content = json.dumps(card, ensure_ascii=False)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})

    with tempfile.TemporaryDirectory() as tmp:
        pairs = Path(tmp) / "pairs.json"
        pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"},
                                     "library": {"0": "job-9", "1": "job-10"}}), encoding="utf-8")
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            rc = check.main(["--api", "http://api.test/api", "--pairs", str(pairs), "--out-dir", tmp,
                             "--qwen-url", "http://qwen.test/v1", "--qwen-model", "qwen-test",
                             "--gemma-url", "http://gemma.test/v1", "--gemma-model", "gemma-test"],
                            client=client)
        md = (Path(tmp) / "computing.md").read_text(encoding="utf-8")
        summary = (Path(tmp) / "summary.md").read_text(encoding="utf-8")
        library_written = (Path(tmp) / "library.md").exists()

    def expect(ok: bool, what: str) -> None:
        if not ok:
            raise SystemExit(f"smoke FAIL: {what}\n---\n{md}\n---\n{summary}")

    expect(rc == 0, "check.main 반환값 0")
    hosts = [r.url.host for r in requests]
    expect(hosts.count("qwen.test") == 2 and hosts.count("gemma.test") == 2, "모델마다 카드 2장 — 재시도 없음")
    bodies = [json.loads(r.content) for r in requests]
    expect({b["model"] for b in bodies} == {"qwen-test", "gemma-test"}, "모델 이름")
    expect(all(b.get("max_tokens") == 400 for b in bodies), "research_topic_card.yaml 의 LLM 파라미터")
    user = next(b for b in bodies if "그리드 자원의 동적 배분" in b["messages"][-1]["content"])["messages"][-1]["content"]
    expect("원 질문: 컴퓨팅 자원에 대한 연구가 궁금해" in user and "보고서 절(하위질문): 그리드 컴퓨팅의 자원 관리 기법" in user,
           "카드 요청에 원 질문·절 소제목")
    expect("향후 과제(씨앗): 그리드 자원의 동적 배분을 실증할 필요가 있다" in user, "씨앗에서 [E#] 표기를 걷어 낸다")
    expect("[E1] 동적 자원 배분 기법 (2011)" in user and "[E4] 분산 작업 스케줄러 (연도 미상)" in user,
           "씨앗 근거(E2→B)가 먼저, 그 절 논문이 뒤에 로컬 [E#] 로")
    expect("[F" not in user and "125,000" not in user and "125000" not in user, "카드 요청에 수치를 주지 않는다(정함 3)")
    expect(not library_written, "조회에 실패한 질문은 건너뛴다")
    expect("# computing - 컴퓨팅 자원에 대한 연구가 궁금해" in md, "머리")
    expect("## 카드 1 - 「그리드 컴퓨팅의 자원 관리 기법」 (future:0:0)" in md
           and "## 카드 2 - 「클라우드 자원 스케줄링」 (future:1:0)" in md and "## 카드 3" not in md,
           "근거 후보가 2편 이상인 씨앗 둘만 카드")
    expect("| 형식 통과(근거 2개 이상) | 2/2 | 1/2 |" in md, "요약 — 형식 통과")
    expect("| 근거 3개 이상 | 2/2 | 0/2 |" in md, "요약 — 근거 3개 이상")
    expect("| 제목에서 되돌린 근거 | 0 | 2 |" in md, "요약 — 제목에서 되돌린 근거")
    expect("| 확인 필요 숫자가 있는 카드 | 0 | 1 |" in md, "요약 — 확인 필요 숫자")
    expect("| 근거 수·되돌림·버림 | 3개 · 되돌림 0 · 버림 0 | 2개 · 되돌림 2 · 버림 0 |" in md, "카드 1 근거 셈")
    expect("| 형식 검사 | 통과 | 근거 1개(2개 미만) |" in md, "카드 2 형식 검사")
    expect("| 근거 수·되돌림·버림 | 3개 · 되돌림 0 · 버림 0 | 1개 · 되돌림 0 · 버림 1 |" in md, "카드 2 근거 셈")
    expect("| 확인 필요 숫자 | 없음 | 2013 |" in md, "카드 2 의 [F#] 밖 숫자")
    expect("이 하위질문에서 채택한 논문은 15편이다." in md and "수치는 소장 KCI 적재분 125,000편 기준이다." in md,
           "수치 문장은 코드 틀 — 값을 넣어 보인다")
    expect("[E1] 동적 자원 배분 기법<br>[E2] 그리드 컴퓨팅 자원 관리" in md, "근거는 번호·제목으로")
    expect("| computing | 2/2 | 1/2 | 2/2 | 0/2 |" in summary and "| 합계 | 2/2 | 1/2 | 2/2 | 0/2 |" in summary,
           "요약 파일 — 질문별·합계")
    print("smoke OK")


if __name__ == "__main__":
    main()
