"""scoring.py — 근거 순위 계산 (순수 함수)

피인용을 생값으로 쓰면 오래된 논문이 항상 이긴다. now_year 기준 2002년
논문은 25년간(+1, 발행연도 포함) 쌓았고 2024년 논문은 3년이다. 연간
피인용으로 정규화해야 "최근 동향" 질문에서 2000년대 초 논문만 올라오지
않는다.

화면에는 생값(피인용 41회)을 그대로 보여준다 — 정규화는 순위에만 쓴다.
"""
import math
import re

_YEAR = re.compile(r"(19|20)\d{2}")


def parse_pub_year(pub_date: str | None) -> int | None:
    """'2008-06' · '200806' · '2008' → 2008. 해석 불가면 None."""
    m = _YEAR.search(pub_date or "")
    return int(m.group(0)) if m else None


def impact_per_year(kci_citations: int | None, pub_year: int | None, *, now_year: int) -> float:
    """연간 피인용. 연도를 모르거나 피인용이 없으면 0."""
    if kci_citations is None or kci_citations <= 0 or pub_year is None:
        return 0.0
    years = max(1, now_year - pub_year + 1)
    return kci_citations / years


def blend_score(rerank_score: float, *, impact: float, weight: float) -> float:
    """리랭킹 점수를 주로 하고 영향력을 보조 가중으로 얹는다.

    log1p 로 감쇠시키는 이유: 영향력이 100배여도 점수가 100배가 되면
    의미 유사도가 의미를 잃고 "많이 인용된 논문 목록"이 되어버린다.
    """
    return rerank_score * (1.0 + weight * math.log1p(impact))
