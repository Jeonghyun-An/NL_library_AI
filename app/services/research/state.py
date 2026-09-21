"""state.py — 딥리서치 실행 상태

각 단계는 ResearchState 를 받아 갱신해 돌려준다. Celery·Redis·Milvus 없이
테스트되고, 나중에 다른 오케스트레이션 런타임으로 옮겨도 그대로 쓴다.
"""
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypedDict

# 깊이 파라미터 — research_jobs.params 로 덮어쓴다.
# 시연 직전에 값만 바꿔 짧게 돌릴 수 있어야 하므로 하드코딩하지 않는다.
# MappingProxyType 로 감싼 이유: 워커 프로세스가 이 모듈 전역을 한 번이라도
# 실수로 mutate 하면 그 오염이 프로세스 수명 내내 남는다.
DEFAULT_PARAMS: MappingProxyType[str, int | float] = MappingProxyType({
    "max_subquestions": 6,
    "max_recheck": 3,
    "max_evidence": 60,
    "per_subq_top_k": 12,
    "chunks_per_evidence": 2,
    "citation_weight": 0.2,
    "min_evidence_per_subq": 5,
})

# (타입, 하한, 상한) — 상한 없음은 None.
# ResearchCreate.params: dict 가 값 타입을 검증하지 않으므로 여기가 유일한 검증 지점이다.
_PARAM_BOUNDS: dict[str, tuple[type, int | float, int | float | None]] = {
    "max_subquestions": (int, 1, None),
    "max_recheck": (int, 0, None),
    "max_evidence": (int, 1, None),
    "per_subq_top_k": (int, 1, None),
    "chunks_per_evidence": (int, 1, None),
    "citation_weight": (float, 0.0, 1.0),
    "min_evidence_per_subq": (int, 0, None),
}


def merge_params(override: dict | None) -> dict:
    """기본값에 override 를 얹는다. 모르는 키·타입·범위를 벗어난 값은 거부한다."""
    merged = dict(DEFAULT_PARAMS)
    for key, value in (override or {}).items():
        if key not in DEFAULT_PARAMS:
            raise ValueError(f"알 수 없는 파라미터: {key}")
        _validate_param(key, value)
        merged[key] = value
    return merged


def _validate_param(key: str, value: object) -> None:
    expected_type, lo, hi = _PARAM_BOUNDS[key]
    # bool 은 int 의 서브클래스라 isinstance(value, int) 를 그냥 쓰면 True 가 통과해버린다.
    if isinstance(value, bool):
        raise ValueError(f"파라미터 {key} 에 bool 값은 쓸 수 없다: {value!r}")
    if expected_type is int and not isinstance(value, int):
        raise ValueError(f"파라미터 {key} 는 int 여야 한다: {value!r}")
    if expected_type is float and not isinstance(value, (int, float)):
        raise ValueError(f"파라미터 {key} 는 float 여야 한다: {value!r}")
    if value < lo or (hi is not None and value > hi):
        raise ValueError(f"파라미터 {key} 가 허용 범위({lo}~{hi})를 벗어났다: {value!r}")


class HitRow(TypedDict):
    """검색 결과 1건 — Milvus 검색 계층(explore)이 만들어 citations.build_evidence 로 넘긴다."""
    book_id: str
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    score: float


@dataclass
class Chunk:
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    score: float


@dataclass
class Evidence:
    id: str                      # "E12" — 보고서 안에서만 유효한 지역 ID
    cnts_id: str
    meta: dict                   # 제목·저자·학술지·권호·연월·피인용·등재구분
    chunks: list[Chunk] = field(default_factory=list)


VERDICTS = ("pending", "sufficient", "insufficient")


@dataclass
class SubQuestion:
    idx: int
    text: str
    queries: list[str] = field(default_factory=list)   # 시도한 검색어 (재검색 이력)
    evidence_ids: list[str] = field(default_factory=list)
    verdict: str = "pending"
    note: str = ""                                      # 자기점검 판단 근거


@dataclass
class ResearchState:
    job_id: str
    question: str
    params: dict
    subquestions: list[SubQuestion] = field(default_factory=list)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    recheck_count: int = 0
    # 실행 시점의 수록 범위 — 코퍼스가 계속 자라므로 보고서에 고정 문구로
    # 박지 않고 매번 질의해 넣는다. {"from": "2002", "to": "2026", "n_papers": 72054}
    corpus_range: dict | None = None
    report: dict | None = None
