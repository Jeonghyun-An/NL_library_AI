"""
reranker.py — Cross-Encoder 리랭킹 (Jina Reranker v2)

- 모델: jinaai/jina-reranker-v2-base-multilingual
- 다국어(한국어 포함) 최적화, 8192 토큰 컨텍스트
- ~278M 파라미터, GPU에서 20개 청크 ~0.3초
- FastAPI 기동 시 임베딩 모델과 함께 메모리에 로드
"""
import logging
from dataclasses import dataclass
from functools import lru_cache

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

RERANKER_MAX_LENGTH = cfg.RERANKER_MAX_LENGTH   # 청크가 길 수 있으므로 넉넉하게
RERANKER_BATCH_SIZE = cfg.RERANKER_BATCH_SIZE

_tokenizer = None
_model = None
_device = None


def _load_model():
    global _tokenizer, _model, _device

    if _model is not None:
        return

    model_name = cfg.RERANKER_MODEL_NAME
    log.info(f"리랭커 모델 로딩: {model_name}")

    _tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    _model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=torch.float16,
    )
    _model.eval()

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _model = _model.to(_device)
    log.info(f"리랭커 로드 완료 ({_device}, {model_name})")


def warmup():
    """FastAPI startup 시 호출"""
    _load_model()
    scores = compute_scores("테스트 쿼리", ["테스트 문서"])
    log.info(f"리랭커 워밍업 완료 (더미 점수: {scores})")


@dataclass
class RerankResult:
    index: int
    score: float
    text: str


def compute_scores(query: str, documents: list[str]) -> list[float]:
    """
    쿼리-문서 쌍의 관련성 점수 계산

    Returns:
        각 문서의 관련성 점수 리스트 (높을수록 관련)
    """
    _load_model()

    if not documents:
        return []

    pairs = [[query, doc] for doc in documents]
    all_scores = []

    for i in range(0, len(pairs), RERANKER_BATCH_SIZE):
        batch = pairs[i : i + RERANKER_BATCH_SIZE]

        inputs = _tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=RERANKER_MAX_LENGTH,
            return_tensors="pt",
        ).to(_device)

        with torch.no_grad():
            outputs = _model(**inputs)
            scores = torch.sigmoid(outputs.logits.view(-1))

        all_scores.extend(scores.cpu().tolist())

    return all_scores


def rerank(
    query: str,
    documents: list[str],
    top_k: int | None = None,
) -> list[RerankResult]:
    """
    리랭킹: 관련성 점수 계산 → 상위 top_k개 반환

    Args:
        query: 검색 쿼리
        documents: 후보 문서 리스트
        top_k: 상위 N개만 반환 (None이면 전체)

    Returns:
        점수 내림차순 정렬된 RerankResult 리스트
    """
    scores = compute_scores(query, documents)

    results = [
        RerankResult(index=i, score=s, text=doc)
        for i, (s, doc) in enumerate(zip(scores, documents))
    ]
    results.sort(key=lambda x: x.score, reverse=True)

    if top_k:
        results = results[:top_k]

    return results