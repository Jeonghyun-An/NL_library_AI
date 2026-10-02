"""concepts.py — 핵심 개념 생성(kind=concepts, Qwen) — spec §5-2

입력은 원 질문 + 하위질문(승인된 계획) + 보고서 절 제목, 출력은 원 질문의 핵심 개념 2~5개.
개수·중복은 모델에 맡기지 않고 코드가 자르고 지운다(함정 15). 끝내 2개를 못 얻으면 비운 채
done 이고, 화면은 '핵심 개념 넣기' 입력을 보인다(사용자가 PATCH .../work 로 넣는다).
"""
from services.prompts import get_prompt
from services.research.llm_json import extract_json
from services.research_work.generate import Executor

MIN_CONCEPTS, MAX_CONCEPTS, MAX_CONCEPT_LEN = 2, 5, 40


def clean_concepts(raw: object) -> list[str]:
    """문자열만, 공백 정리, 1~40자, 대소문자·공백 무시 중복 제거, 앞에서 5개.

    사용자가 고친 칩(PATCH .../work)도 같은 규칙으로 정리한다.
    """
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split())
        if not 1 <= len(text) <= MAX_CONCEPT_LEN:
            continue
        key = "".join(text.split()).casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) == MAX_CONCEPTS:
            break
    return out


def concepts_input(job) -> dict:
    """완료된 딥리서치 잡(ResearchJob) → 생성 입력. research_generations.input 에 그대로 담긴다."""
    report = job.report if isinstance(job.report, dict) else {}
    headings = []
    for sec in report.get("sections") or []:
        heading = sec.get("heading") if isinstance(sec, dict) else None
        if isinstance(heading, str) and heading.strip():
            headings.append(heading.strip())
    return {
        "question": job.question,
        "subquestions": [s for s in (job.plan or []) if isinstance(s, str)],
        "headings": headings,
    }


def _lines(items: list[str]) -> str:
    return "\n".join(f"- {s}" for s in items) or "(없음)"


def _build(input: dict) -> tuple[list[dict], dict]:
    system, user, params = get_prompt("research_concepts").render(
        question=input["question"],
        subquestions=_lines(input.get("subquestions") or []),
        headings=_lines(input.get("headings") or []),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], params


def _parse(raw: str) -> dict | None:
    data = extract_json(raw)
    if data is None or not isinstance(data.get("concepts"), list):
        return None
    return {"concepts": clean_concepts(data["concepts"])}


EXECUTOR = Executor(
    kind="concepts",
    build=_build,
    parse=_parse,
    check=lambda output: len(output["concepts"]) >= MIN_CONCEPTS,
    empty=lambda input: {"concepts": []},
)
