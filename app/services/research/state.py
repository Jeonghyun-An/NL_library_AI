"""state.py — 딥리서치 실행 상태

각 단계는 ResearchState 를 받아 갱신해 돌려준다. Celery·Redis·Milvus 없이
테스트되고, 나중에 다른 오케스트레이션 런타임으로 옮겨도 그대로 쓴다.
"""
from dataclasses import dataclass, field

# 깊이 파라미터 — research_jobs.params 로 덮어쓴다.
# 시연 직전에 값만 바꿔 짧게 돌릴 수 있어야 하므로 하드코딩하지 않는다.
DEFAULT_PARAMS: dict = {
    "max_subquestions": 6,
    "max_recheck": 3,
    "max_evidence": 60,
    "per_subq_top_k": 12,
    "chunks_per_evidence": 2,
    "citation_weight": 0.2,
    "min_evidence_per_subq": 5,
}


def merge_params(override: dict | None) -> dict:
    """기본값에 override 를 얹는다. 모르는 키는 거부한다."""
    merged = dict(DEFAULT_PARAMS)
    for key, value in (override or {}).items():
        if key not in DEFAULT_PARAMS:
            raise ValueError(f"알 수 없는 파라미터: {key}")
        merged[key] = value
    return merged


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


@dataclass
class SubQuestion:
    idx: int
    text: str
    queries: list[str] = field(default_factory=list)   # 시도한 검색어 (재검색 이력)
    evidence_ids: list[str] = field(default_factory=list)
    verdict: str = "pending"                            # pending|sufficient|insufficient
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
