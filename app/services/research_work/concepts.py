"""concepts.py — 키워드 후보 생성(kind=concepts, gemma) — spec §5-2, 06e §12-4 '후보 키워드'(D23)

06e 부터 이 생성은 '제목 고르기'의 키워드 후보를 낸다(생성 종류 이름 concepts·research_works.concepts 는 그대로 —
고른 키워드가 칩이고 목차 묶음 배정이 같은 값을 쓴다). 입력은 원 질문 + 하위질문(승인된 계획) + 채택 논문의 소장
키워드 문서 빈도(paper_keywords — 이어가기 때 FastAPI 가 싣는다), 출력은
{"concepts": [미리 고른 키워드], "candidates": [{"text", "source", "n"}]}. 후보를 합치는 규칙(순서·출처·편수·상한·
일반어·미리 고르기)은 keywords.py 에 있다. 모델은 키워드만 중요한 순서대로 내고, 개수는 프롬프트에 적지 않고 코드가
자른다(함정 15). 모델이 낸 후보가 일반어를 거른 뒤 하나도 없으면 내용 검사 미달로 다시 부르고, 끝내 없으면
논문 키워드만 후보로 둔 채 concepts 를 비워 done 이다(화면은 [다시]·직접 더하기를 보인다).
보고서 절 제목은 넣지 않는다 — 절 제목은 하위질문 글 그대로(synthesizer 의 heading = sq.text)라 새 정보가 없고,
측면 틀 낱말(정의·방법론·한계)의 무게만 두 배로 만든다(06a Qwen 표본에서 개념이 절 제목을 옮겼다). 06a 에 만든 생성
행의 input 에 남은 headings 키는 읽지 않는다. 06e 전에 만든 행(paper_keywords 없음)은 논문 후보 없이 돈다.
"""
import unicodedata

from services.prompts import get_prompt
from services.research.llm_json import extract_json
from services.research_work.generate import Executor
from services.research_work.keywords import clean_keyword, keyword_key, merge_candidates, preselect

# 칩(research_works.concepts) 규칙 — 사용자가 고른·고친 칩(PATCH .../work)의 개수·글자 상한.
# 글자 상한은 키워드 후보(keywords.KEYWORD_LEN_MAX)와 같다(test_research_work_keywords 가 고정)
MAX_CONCEPTS, MAX_CONCEPT_LEN = 5, 40


def clean_concepts(raw: object) -> list[str]:
    """문자열만, NFKC 정규화, 공백 정리, 1~40자, 대소문자·공백 무시 중복 제거, 앞에서 5개.

    NFKC 는 전각 영숫자·전각 공백·호환 문자(㈜ 등)를 보통 글자로 바꾼다 — 'ＡＩ 윤리' 와 'AI 윤리' 가 두 칩이
    되지 않고, 글자 수는 정규화한 뒤에 센다. 사용자가 고친 칩(PATCH .../work)도 같은 규칙으로 정리한다.
    """
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        text = " ".join(unicodedata.normalize("NFKC", item).split())
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


def concepts_input(job, paper_keywords: list[dict] | None = None) -> dict:
    """완료된 딥리서치 잡(ResearchJob) → 생성 입력. research_generations.input 에 그대로 담긴다.

    원 질문과 승인된 하위질문, 그리고 채택 논문의 키워드 문서 빈도(keywords.paper_keyword_counts — 이어가기가 읽어
    넘긴다)를 담는다. 보고서 절 제목을 넣지 않는 까닭은 모듈 docstring.
    """
    return {
        "question": job.question,
        "subquestions": [s for s in (job.plan or []) if isinstance(s, str)],
        "paper_keywords": list(paper_keywords or []),
    }


def _lines(items: list[str]) -> str:
    return "\n".join(f"- {s}" for s in items) or "(없음)"


def _build(input: dict) -> tuple[list[dict], dict]:
    system, user, params = get_prompt("research_concepts").render(
        question=input["question"],
        subquestions=_lines(input.get("subquestions") or []),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], params


def _parse(raw: str) -> dict | None:
    """원문 → {"llm": [모델이 낸 키워드 — 정리·일반어 거름·중복 제거, 낸 순서]}. 키는 keywords — 06e 전 프롬프트의
    concepts 키도 읽는다(배포 사이에 옛 워커가 넣은 행을 새 워커가 다시 부를 수 있다). 목록이 아니면 None."""
    data = extract_json(raw)
    if data is None:
        return None
    items = data.get("keywords")
    if items is None:
        items = data.get("concepts")
    if not isinstance(items, list):
        return None
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = clean_keyword(item)
        if text is None or keyword_key(text) in seen:
            continue
        seen.add(keyword_key(text))
        out.append(text)
    return {"llm": out}


def _bind(output: dict, input: dict) -> dict:
    """모델 후보 + 논문 키워드(input.paper_keywords) → {"concepts": 미리 고른 키워드, "candidates": 후보}."""
    candidates = merge_candidates(output.get("llm") or [], input.get("paper_keywords") or [])
    return {"concepts": preselect(candidates), "candidates": candidates}


def _check(output: dict) -> bool:
    """모델이 낸 후보가 하나라도 남았는가 — 논문 키워드만 남았으면 모델이 실패한 것이라 다시 부른다."""
    return any(c["source"] in ("llm", "both") for c in output.get("candidates") or [])


def _empty(input: dict) -> dict:
    """끝내 모델 후보를 못 얻은 결과 — 논문 키워드만 후보로 두고 미리 고르지 않는다(사용자가 고르거나 [다시])."""
    return {"concepts": [], "candidates": merge_candidates([], input.get("paper_keywords") or [])}


EXECUTOR = Executor(
    kind="concepts",
    build=_build,
    parse=_parse,
    check=_check,
    empty=_empty,
    bind=_bind,
    # 빈 결과로 끝난 done 은 다시 부를 수 있다(api/research_work._retryable — 06a 의 concepts 특례를 옮긴 것)
    is_empty=lambda output: not (output or {}).get("concepts"),
)
