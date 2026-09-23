"""state.py — 딥리서치 실행 상태

각 단계는 ResearchState 를 받아 갱신해 돌려준다. Celery·Redis·Milvus 없이
테스트되고, 나중에 다른 오케스트레이션 런타임으로 옮겨도 그대로 쓴다.
"""
import logging
import math
from dataclasses import asdict, dataclass, field, fields
from types import MappingProxyType
from typing import NotRequired, TypedDict

log = logging.getLogger(__name__)

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

# (타입, 하한, 상한). ResearchCreate.params: dict 가 값 타입을 검증하지
# 않으므로 여기가 유일한 검증 지점이다 — 상한이 없으면 per_subq_top_k 같은
# 값이 그대로 Milvus AnnSearchRequest(limit=...) 까지 흘러가 요청 하나로
# 워커를 묶는 자해 경로가 된다. 상한은 시연 현실치 기준.
_PARAM_BOUNDS: dict[str, tuple[type, int | float, int | float | None]] = {
    "max_subquestions": (int, 1, 12),
    "max_recheck": (int, 0, 10),
    "max_evidence": (int, 1, 200),
    "per_subq_top_k": (int, 1, 50),
    "chunks_per_evidence": (int, 1, 5),
    "citation_weight": (float, 0.0, 1.0),
    "min_evidence_per_subq": (int, 0, 50),
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
    # NaN 은 아래 범위 비교가 전부 False 라 그대로 통과한다. 표준 json.loads 가
    # NaN 리터럴을 받아들이므로 실제로 들어오고, JSONB 가 거부해 422 가 아니라 500 이 된다.
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"파라미터 {key} 는 유한한 수여야 한다: {value!r}")
    if value < lo or (hi is not None and value > hi):
        raise ValueError(f"파라미터 {key} 가 허용 범위({lo}~{hi})를 벗어났다: {value!r}")


class HitRow(TypedDict):
    """검색 결과 1건 — Milvus 검색 계층(explore)이 만들어 citations.build_evidence 로 넘긴다.

    score 와 rank_score 를 나눈 이유: 순위용 혼합값은 1.0 을 넘을 수 있어
    유사도로 표시하면 141% 같은 값이 나간다. score 는 생값 그대로 두고 순위는
    rank_score 로만 매긴다(explorer.rank_hits).
    """
    book_id: str
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    score: float                      # 리랭킹(없으면 RRF) 생값 — 화면에 유사도로 나간다
    rank_score: NotRequired[float]    # 피인용을 얹은 정렬용 값 — rank_hits 가 채운다


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
# LLM 이 낼 수 있는 판정 — pending 은 초기상태 전용이라 제외.
# VERDICTS[1:] 로 쓰면 순서만 바뀌어도 sufficient 가 빠져 모든 정상 판정이
# "알 수 없는 verdict" 로 떨어진다.
LLM_VERDICTS = tuple(v for v in VERDICTS if v != "pending")


@dataclass
class SubQuestion:
    idx: int
    text: str
    queries: list[str] = field(default_factory=list)   # 시도한 검색어 (재검색 이력)
    # 이 하위질문 안의 순위순 — critic(20편)과 절(5편)이 앞에서 자르므로 순서가 곧
    # 선택이다. runner 가 라운드마다 다시 정렬한다.
    evidence_ids: list[str] = field(default_factory=list)
    verdict: str = "pending"
    # 판정을 받지 못해(응답 해석 실패·호출 실패) 점검이 사실상 건너뛰어진 경우
    parse_failed: bool = False
    # 탐색이 예외로 중단됨 — "근거 없음"(연구 결과)과 구분한다. 구분이 없으면
    # 보고서가 시스템 장애를 "…에 대해서는 근거를 찾지 못했다"로 써서, 우리 쪽이
    # 터진 것을 코퍼스에 자료가 없는 것처럼 보이게 만든다.
    failed: bool = False
    note: str = ""                                      # 자기점검 판단 근거
    # max_evidence 상한 때문에 채택하지 못한 후보 논문 수. failed 와 같은 이유로
    # 따로 둔다 — 없으면 시스템 상한이 "근거를 찾지 못했다"(코퍼스 빈틈)로 보고된다.
    capped: int = 0
    # 근거 ID → 이 하위질문 검색에서 매칭된 청크 ID(점수순). 한 논문이 여러
    # 하위질문에서 재사용되면 Evidence.chunks 는 그 합집합이라, 이게 없으면 critic
    # 발췌·절 요약·호버가 처음 채택한 하위질문의 대목으로 고정된다.
    evidence_chunks: dict[str, list[str]] = field(default_factory=dict)
    # 청크 ID → 이 하위질문의 검색어로 받은 점수. 한 청크를 여러 하위질문이 매칭하면
    # Chunk.score 는 하나뿐이라, 이게 없으면 재검색 비교·발췌·절 호버가 다른 하위질문의
    # 점수로 돈다(0.95 로 찾은 대목이 남의 0.2 로 비교돼 밀려난다).
    chunk_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ResearchState:
    job_id: str
    question: str
    params: dict
    subquestions: list[SubQuestion] = field(default_factory=list)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    # 실행 시점의 수록 범위 — 코퍼스가 계속 자라므로 보고서에 고정 문구로
    # 박지 않고 매번 질의해 넣는다. {"from": "2002", "to": "2026", "n_papers": 72054}
    corpus_range: dict | None = None
    # 보고서는 여기에 두지 않는다. synthesize() 가 반환값으로 넘기고 Celery
    # 태스크가 research_jobs.report 에 바로 쓴다. 항상 None 인 report 필드를
    # 남겨두면 화면을 붙이는 쪽이 그걸 집어들고 조용히 빈 보고서를 그린다.


def snapshot_state(state: ResearchState) -> dict:
    """탐색이 끝난 상태를 JSONB 에 넣을 수 있는 형태로 만든다.

    필드를 손으로 나열하지 않고 asdict 로 담는다 — 필드를 추가하고 여기에
    빠뜨리면 재개한 잡에서만 그 값이 조용히 기본값으로 돌아간다. 이 모듈에서
    parse_failed·failed 로 실제로 반복된 실수다.
    """
    return {
        "question": state.question,
        "params": state.params,
        "corpus_range": state.corpus_range,
        "subquestions": [asdict(s) for s in state.subquestions],
        "evidence": {
            eid: {
                "cnts_id": ev.cnts_id, "meta": ev.meta,
                "chunks": [asdict(c) for c in ev.chunks],
            }
            for eid, ev in state.evidence.items()
        },
    }


def _known_fields(cls: type, raw: dict, where: str) -> dict:
    """스냅샷 한 항목에서 dataclass 가 아는 키만 남긴다.

    재개는 "종합 수정 → 배포 → 옛 잡 retry" 처럼 버전을 건너 쓰인다. 필드가
    빠지거나 이름이 바뀐 뒤 옛 스냅샷의 여분 키로 TypeError 가 나면 그 잡의
    체크포인트는 영구히 못 쓴다. 없는 키는 dataclass 기본값이 채운다.
    """
    names = {f.name for f in fields(cls)}
    extra = sorted(set(raw) - names)
    if extra:
        log.warning("[research] 스냅샷의 모르는 키를 무시한다 — %s: %s", where, extra)
    return {k: v for k, v in raw.items() if k in names}


def restore_state(job_id: str, snap: dict) -> ResearchState:
    """snapshot_state 의 역. 종합 단계부터 재개할 때 쓴다.

    parse_failed·failed 가 왕복에서 떨어지면 재개한 잡의 한계 섹션이 조용히
    비고, 보고서가 "한계 없음"으로 보인다.

    params 는 기본값에 다시 얹는다. 스냅샷 이후 추가된 파라미터를 읽는 쪽이
    KeyError 로 터지지 않게 하고, 없어진 파라미터는 merge_params 가 거부하기
    전에 걸러낸다.
    """
    raw_params = snap.get("params") or {}
    retired = sorted(set(raw_params) - set(DEFAULT_PARAMS))
    if retired:
        log.warning("[research] 스냅샷의 없어진 파라미터를 무시한다 — %s", retired)
    st = ResearchState(
        job_id=job_id, question=snap["question"],
        params=merge_params({k: v for k, v in raw_params.items() if k in DEFAULT_PARAMS}),
        corpus_range=snap.get("corpus_range"),
    )
    st.subquestions = [
        SubQuestion(**_known_fields(SubQuestion, sq, "subquestion"))
        for sq in snap["subquestions"]
    ]
    st.evidence = {
        eid: Evidence(
            id=eid, cnts_id=e["cnts_id"], meta=e["meta"],
            chunks=[Chunk(**_known_fields(Chunk, c, "chunk")) for c in e["chunks"]],
        )
        for eid, e in snap["evidence"].items()
    }
    return st
