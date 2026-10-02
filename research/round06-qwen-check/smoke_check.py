"""smoke_check.py — check.py 를 가짜 API·가짜 vLLM 으로 한 번 돌려 본다 (네트워크·DB 없음, 1회성)

운영에서 돌리기 전에 개발 PC 에서 요청 만들기(핵심 개념은 연구 어시스턴트의 실제 요청 그대로)·응답 읽기·
마크다운 쓰기가 끝까지 도는지만 본다. 품질은 운영 실행 결과(out/)를 사람이 본다.
사용법(저장소 루트에서): python research/round06-qwen-check/smoke_check.py  → 마지막 줄 'smoke OK'
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
            # 향후 과제는 있지만 절 논문이 3편 미만 — 근거 3개 이상 규칙을 지킬 수 없어 카드를 만들지 않는다
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
        # 근거가 없어 절이 되지 않은 하위질문이 가운데 끼어 있다 — 채택 수는 소제목으로 찾아야 한다
        "trail": [{"subquestion": "그리드 컴퓨팅의 자원 관리 기법", "evidence_count": 15},
                  {"subquestion": "분산 컴퓨팅 표준화 동향", "evidence_count": 0},
                  {"subquestion": "클라우드 자원 스케줄링", "evidence_count": 9},
                  {"subquestion": "고성능 컴퓨팅 활용 분야", "evidence_count": 4}],
    },
}
GOOD_CARD = {"title": "그리드 자원의 동적 배분 실증 연구", "question": "동적 배분은 작업 대기 시간을 줄이는가?",
             "evidence": ["E1", "E2", "E3"],
             "figure_sentence": "채택 논문 [F1] 가운데 가장 최근 연구는 [F2] 에 나왔다."}
BAD_CARD = {"title": "자원 관리", "question": "자원 관리 연구", "evidence": ["E1", "E9", {"id": "E2"}],
            "figure_sentence": "2013년까지 관련 연구가 전무하다."}


def main() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.test":
            return httpx.Response(200, json=JOB)
        requests.append(request)
        body = json.loads(request.content)
        is_card = "향후 과제" in body["messages"][-1]["content"]
        qwen = request.url.host == "qwen.test"
        if is_card:
            content = json.dumps(GOOD_CARD if qwen else BAD_CARD, ensure_ascii=False)
        else:
            content = '{"concepts": ["그리드 컴퓨팅", "자원 관리", "그리드  컴퓨팅"]}' if qwen else "개념을 찾지 못했습니다"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})

    with tempfile.TemporaryDirectory() as tmp:
        pairs = Path(tmp) / "pairs.json"
        pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"}}), encoding="utf-8")
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            rc = check.main(["--api", "http://api.test/api", "--pairs", str(pairs), "--out-dir", tmp,
                             "--qwen-url", "http://qwen.test/v1", "--qwen-model", "qwen-test",
                             "--gemma-url", "http://gemma.test/v1", "--gemma-model", "gemma-test"],
                            client=client)
        md = (Path(tmp) / "computing.md").read_text(encoding="utf-8")

    def expect(ok: bool, what: str) -> None:
        if not ok:
            raise SystemExit(f"smoke FAIL: {what}\n---\n{md}")

    expect(rc == 0, "check.main 반환값 0")
    bodies = [json.loads(r.content) for r in requests]
    expect([r.url.host for r in requests].count("qwen.test") == 3, "Qwen 요청 3번(개념 1 + 카드 2)")
    expect([r.url.host for r in requests].count("gemma.test") == 3, "gemma 요청 3번")
    expect({b["model"] for b in bodies} == {"qwen-test", "gemma-test"}, "모델 이름")
    concept = next(b for b in bodies if "향후 과제" not in b["messages"][-1]["content"])
    user = concept["messages"][-1]["content"]
    expect(all(s in user for s in [JOB["question"], *JOB["plan"]]), "개념 요청에 원 질문·하위질문")
    expect(concept.get("max_tokens") is not None, "개념 요청에 research_concepts.yaml 의 LLM 파라미터")
    card = next(b for b in bodies if "향후 과제" in b["messages"][-1]["content"])["messages"][-1]["content"]
    expect("그리드 자원의 동적 배분을 실증할 필요가 있다" in card and "[E2]" not in card.split("\n")[0],
           "씨앗에서 [E#] 표기를 걷어 낸다")
    expect("[E1] 그리드 컴퓨팅 자원 관리 (2009)" in card and "[E4] 분산 작업 스케줄러 (연도 미상)" in card,
           "절 논문을 로컬 [E#] 로")
    expect("[F3] 소장 KCI 적재분: 125,000편(1998~2013년)" in card, "적재분 수치 [F#]")
    expect("[F1] 이 하위질문에서 채택한 논문 수: 9편" in md, "절 2 의 채택 수를 소제목으로 찾는다")
    expect("# computing - 컴퓨팅 자원에 대한 연구가 궁금해" in md, "머리")
    expect("| 개념 | 그리드 컴퓨팅 · 자원 관리 | 읽지 못함 |" in md, "개념 표(중복 제거·못 읽음)")
    expect("## 주제 카드 초안 1" in md and "## 주제 카드 초안 2" in md and "초안 3" not in md,
           "향후 과제가 있고 절 논문이 3편 이상인 절 둘만 카드")
    expect("| 형식 검사 | 통과 |" in md, "Qwen 카드 형식 통과")
    for problem in ("유효 근거 1개(3개 미만)", "없는 근거 번호 E9", "문자열이 아닌 근거 1개", "[F#] 없음",
                    "[F#] 밖의 숫자", "단정 표현"):
        expect(problem in md, f"gemma 카드 문제 '{problem}'")
    print("smoke OK")


if __name__ == "__main__":
    main()
