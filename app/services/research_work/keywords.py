"""keywords.py — 제목 고르기의 키워드 후보 (순수 함수, round06e D23 — spec §12-4 '후보 키워드', 계획 06e 정함 14·15)

후보 = LLM 후보(개념 생성을 넓힌 것 — concepts.py) + 채택 논문의 소장 키워드(library_catalog.keyword 를 나눈 것 ∪
extra.keywords) 문서 빈도. 둘을 코드가 합쳐 출처(source)·편수(n)를 단다.
  - 순서: LLM 후보를 LLM 이 낸 순서대로 먼저, 논문 키워드에만 있는 후보는 편수 내림차순(같으면 먼저 나온 것)으로 뒤에.
    두 원천에 다 있으면 LLM 자리에 편수를 단다(source "both").
  - 개수는 코드가 자른다 — 상한 MAX_KEYWORD_CANDIDATES, 하한은 없다(있는 만큼). 프롬프트에는 개수를 적지 않는다(함정 15).
  - 일반어('연구 성과'·'국내 학술논문 코퍼스'·'연구 분야'·'발전 방향' 등 — 06b 운영 개념에 섞였다)는 GENERIC_KEYWORDS 로 거른다.
  - 위 PRESELECT 개를 미리 고른다 — research_works.concepts(고른 키워드)가 된다.
논문 키워드는 이어가기 때 FastAPI 가 읽어 개념 생성 input 의 paper_keywords 에 싣는다 — 워커는 DB 텍스트만 쓴다(§6-3).
같은 말 판정은 keyword_key(NFKC → 공백 제거 → casefold)다 — clean_concepts 의 중복 열쇠와 같다.
DB·LLM·무거운 import 가 없다(concepts.py 가 이 모듈을 import 한다 — 거꾸로 가져오지 않는다).
"""
import re
import unicodedata

MAX_KEYWORD_CANDIDATES = 10     # 후보 상한 — 하한은 없다
PRESELECT = 3                   # 처음에 미리 고르는 후보 수(후보가 적으면 모두)
MIN_PICKED_KEYWORDS = 2         # [이 키워드로 다시 만들기]의 최소 선택 수 — 선행연구 묶음 수 ≤ 키워드 수(membership)
PAPER_KEYWORDS_INPUT_MAX = 30   # 개념 생성 input 에 싣는 논문 키워드 수 상한(편수 많은 순)
PAPER_KEYWORD_MIN_N = 1         # 논문에만 있는 후보의 최소 편수 — Task K1 채움률 측정으로 1 또는 2(README '결과')
KEYWORD_LEN_MAX = 40            # 키워드 한 개 글자 상한 — 칩(concepts.MAX_CONCEPT_LEN)과 같다
# 어느 질문에나 붙는 일반어 — keyword_key 로 견준다(띄어쓰기·대소문자·전각 무시). 운영에서 더 나오면 여기에 더한다
GENERIC_KEYWORDS: frozenset[str] = frozenset({
    "연구 성과", "국내 학술논문 코퍼스", "국내 학술논문", "학술논문", "연구 분야", "발전 방향", "측정 및 평가",
    "연구 동향", "선행연구", "연구 방법", "개념 및 정의", "한계 및 과제", "적용 분야", "향후 과제",
})

_CATALOG_SEP = re.compile(r"[;,]")


def keyword_key(text: str) -> str:
    """같은 말 판정 열쇠 — NFKC 뒤 공백을 모두 지우고 casefold."""
    return "".join(unicodedata.normalize("NFKC", text).split()).casefold()


_GENERIC_KEYS = frozenset(keyword_key(w) for w in GENERIC_KEYWORDS)


def clean_keyword(raw: object) -> str | None:
    """문자열만, NFKC·공백 정리, 1~KEYWORD_LEN_MAX 자, 일반어가 아니면 정리한 글. 아니면 None."""
    if not isinstance(raw, str):
        return None
    text = " ".join(unicodedata.normalize("NFKC", raw).split())
    if not 1 <= len(text) <= KEYWORD_LEN_MAX or keyword_key(text) in _GENERIC_KEYS:
        return None
    return text


def split_catalog_keywords(raw: str | None) -> list[str]:
    """library_catalog.keyword(653 $a 를 이은 글) → 키워드 조각. NFKC 뒤 ';'·',' 로 나눈다(전각 '；'·'，' 도 NFKC 로
    같아진다). 빈 조각은 버린다 — 정리·일반어 거르기는 clean_keyword 의 몫이다."""
    if not isinstance(raw, str):
        return []
    return [p.strip() for p in _CATALOG_SEP.split(unicodedata.normalize("NFKC", raw)) if p.strip()]


def paper_keyword_counts(books: dict) -> list[dict]:
    """채택 논문의 서지({cnts_id: BookOut}) → [{"text", "n"}] — n 은 그 키워드를 가진 논문 수(문서 빈도).

    키워드는 keyword 를 나눈 것과 extracted_keywords 를 합친다. 한 논문 안에서 같은 말은 한 번만 센다. 정리·일반어를
    거른 뒤 편수 내림차순, 같으면 처음 나온 순(books 의 순서 — 부르는 쪽이 후보 순서로 넘긴다). 앞
    PAPER_KEYWORDS_INPUT_MAX 개만."""
    counts: dict[str, int] = {}
    shown: dict[str, str] = {}
    for book in books.values():
        seen: set[str] = set()
        raw = [*split_catalog_keywords(getattr(book, "keyword", None)),
               *(getattr(book, "extracted_keywords", None) or [])]
        for item in raw:
            text = clean_keyword(item)
            if text is None:
                continue
            key = keyword_key(text)
            if key in seen:
                continue
            seen.add(key)
            shown.setdefault(key, text)
            counts[key] = counts.get(key, 0) + 1
    order = sorted(counts, key=lambda k: -counts[k])       # 안정 정렬 — 같은 편수는 처음 나온 순 그대로
    return [{"text": shown[k], "n": counts[k]} for k in order[:PAPER_KEYWORDS_INPUT_MAX]]


def merge_candidates(llm: list[str], paper: list[dict]) -> list[dict]:
    """LLM 후보 + 논문 키워드 → [{"text", "source": "llm"|"paper"|"both", "n"}](앞 MAX_KEYWORD_CANDIDATES 개).

    LLM 후보를 낸 순서대로 먼저 — 논문에도 있으면 source both·n 편수, 없으면 llm·0. 그 뒤 논문에만 있고
    n >= PAPER_KEYWORD_MIN_N 인 것을 편수 내림차순(같으면 받은 순)으로. 같은 말(keyword_key)은 한 번만, 일반어는 뺀다.
    paper 의 원소는 개념 생성 input 에서 읽은 값이라 모양이 틀린 것(글이 아님·편수가 1 미만)은 건너뛴다."""
    papers: dict[str, dict] = {}
    for item in paper or []:
        if not isinstance(item, dict):
            continue
        text, n = clean_keyword(item.get("text")), item.get("n")
        if text is None or not isinstance(n, int) or isinstance(n, bool) or n < 1:
            continue
        papers.setdefault(keyword_key(text), {"text": text, "n": n})
    out: list[dict] = []
    used: set[str] = set()
    for raw in llm or []:
        text = clean_keyword(raw)
        if text is None:
            continue
        key = keyword_key(text)
        if key in used:
            continue
        used.add(key)
        hit = papers.get(key)
        out.append({"text": text, "source": "both" if hit else "llm", "n": hit["n"] if hit else 0})
    rest = [p for key, p in papers.items() if key not in used and p["n"] >= PAPER_KEYWORD_MIN_N]
    rest.sort(key=lambda p: -p["n"])
    out += [{"text": p["text"], "source": "paper", "n": p["n"]} for p in rest]
    return out[:MAX_KEYWORD_CANDIDATES]


def preselect(candidates: list[dict]) -> list[str]:
    """처음에 미리 고르는 키워드 — 후보 앞 PRESELECT 개(적으면 모두). 최소 선택 수(MIN_PICKED_KEYWORDS)는 보지 않는다."""
    return [c["text"] for c in candidates[:PRESELECT]]
