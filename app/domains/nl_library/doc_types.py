"""
nl_library 문서 유형 판별 컴포넌트.
- KDC, 제목 키워드, PDF 자동추출 여부 등을 기반으로 문서 유형을 판별하여 이후 처리(챗봇 응답, 인덱싱 등)에 활용.

policy: 법령·행정·조달 문서 (예외적으로 섞이는 케이스)
book  : 그 외 모든 도서 (소설·학술·인문·과학 등) — 기본값
"""
import re
from typing import Any

_POLICY_KDC_RANGE = range(320, 360)  # 정치학·법학·행정학

_POLICY_TITLE_KEYWORDS = [
    "법", "령", "규정", "고시", "지침", "매뉴얼", "조달", "입찰",
    "계약", "공고", "훈령", "예규", "시행", "규칙", "조례",
]


def detect_doc_type(meta: dict[str, Any]) -> str:
    """
    문서 유형 판별.'
    

    meta 키: kdc, title, source_format, genre (모두 선택)

    Returns:
        "paper"      : 학술논문·학위논문·보고서 (PDF 자동추출 또는 genre 기반)
        "literature" : 문학 작품 (KDC 800~899)
        "policy"     : 법령·행정·조달 문서 (KDC 320~359 또는 제목 키워드)
        "book"       : 그 외 모든 도서 (기본값)
    """
    kdc = meta.get("kdc")
    title = meta.get("title")
    source_format = meta.get("source_format")
    genre = meta.get("genre")

    # PDF 자동추출 문서는 genre 값으로 판별
    if source_format == "PDF":
        if genre in ("paper", "thesis", "report"):
            return "paper"

    if kdc:
        digits = re.sub(r"[^0-9]", "", kdc)[:3]
        if digits:
            n = int(digits)
            if 800 <= n <= 899:
                return "literature"
            if n in _POLICY_KDC_RANGE:
                return "policy"

    if title and any(k in title for k in _POLICY_TITLE_KEYWORDS):
        return "policy"

    return "book"
