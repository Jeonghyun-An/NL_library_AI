"""routing.py — 생성 종류(kind)별 모델 (spec §6-3 모델 라우팅)

읽고 고르는 일(핵심 개념·주제 카드·자식 카드·특징 추출)은 Qwen, 계획서를 쓰는 일(목차·절·문단)은
gemma 다. 딥리서치의 계획·critic·종합은 여기를 거치지 않는다(지금처럼 gemma). Qwen 품질이 모자라면
그 kind 를 GEMMA 로 바꾸는 한 줄로 돌린다(Qwen 표본 확인 — spec §8).
엔드포인트는 호출할 때 설정에서 읽는다 — 테스트·운영 env 가 바꾼 값을 그대로 따른다.
"""
from core.config import get_settings

QWEN, GEMMA = "qwen", "gemma"

WORK_MODEL_ROUTES: dict[str, str] = {
    "concepts": QWEN, "topic_card": QWEN, "refine": QWEN, "facet": QWEN,
    "outline": GEMMA, "section": GEMMA, "paragraph": GEMMA,
}


def endpoint(name: str) -> tuple[str, str]:
    """모델 이름 → (base_url, model). Qwen 은 VLM_*, gemma 는 LLM_* 설정이다."""
    cfg = get_settings()
    if name == QWEN:
        return cfg.VLM_BASE_URL, cfg.VLM_MODEL
    if name == GEMMA:
        return cfg.LLM_BASE_URL, cfg.LLM_MODEL
    raise ValueError(f"알 수 없는 모델 이름: {name!r}")


def other(name: str) -> str:
    """넘길 모델 — 주 모델이 끝내 답하지 못하면 다른 쪽에 한 번 묻는다."""
    if name == QWEN:
        return GEMMA
    if name == GEMMA:
        return QWEN
    raise ValueError(f"알 수 없는 모델 이름: {name!r}")
