"""
title_scorer.py — 제목 일치율 계산 및 연관도 보정

검색 파이프라인의 best_score는 본문 청크 유사도(내용 일치율)만 반영한다.
사용자가 제목을 그대로 검색해도 본문 매칭이 약하면 점수가 낮게 나오는 문제를
제목 일치율로 보정한다.

  title_score   = 질의 ↔ 제목 일치율 (0.0 ~ 1.0)
  content_score = 기존 청크 기반 best_score
  best_score    = max(title_score, content_score)   ← 프론트 "연관도"

제목 완전 일치(또는 질의 문장 안에 제목 전체 포함) 시 연관도 100%가 된다.
"""
import re

# 한글/영문/숫자만 남기고 공백·문장부호 제거 (표기 차이 무시)
_STRIP_RE = re.compile(r"[^0-9a-zA-Z가-힣]+")

# 질의 문장 안 제목 포함을 완전 일치로 인정할 최소 제목 길이
# ("밤", "봄" 같은 초단문 제목의 우연 매칭 방지)
_MIN_CONTAIN_LEN = 4


def _normalize(s: str | None) -> str:
    return _STRIP_RE.sub("", (s or "").lower())


def _bigrams(s: str) -> set[str]:
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def title_match_score(queries: list[str], title: str) -> float:
    """질의 목록(원본+재작성) 대비 제목 일치율. 최고값 반환."""
    t = _normalize(title)
    if not t:
        return 0.0

    best = 0.0
    for raw in queries:
        q = _normalize(raw)
        if not q:
            continue
        # 완전 일치
        if q == t:
            return 1.0
        # 질의 문장 안에 제목 전체 포함 → 제목을 그대로 입력한 것으로 간주
        if len(t) >= _MIN_CONTAIN_LEN and t in q:
            return 1.0
        # 제목 일부만 입력 → 제목 커버리지 비율
        if q in t:
            best = max(best, len(q) / len(t))
            continue
        # 부분 겹침 → 문자 bigram Dice 유사도
        qb, tb = _bigrams(q), _bigrams(t)
        if qb and tb:
            best = max(best, 2 * len(qb & tb) / (len(qb) + len(tb)))

    return round(min(best, 1.0), 4)


def apply_title_scores(books, query: str, rewritten: str | None = None) -> None:
    """
    BookChunkGroup 리스트에 title_score / content_score를 채우고
    best_score(연관도)를 max(제목, 내용)으로 갱신한 뒤 재정렬한다.
    book_info가 붙은 후에 호출해야 한다.
    """
    queries = [query]
    if rewritten and rewritten != query:
        queries.append(rewritten)

    for bg in books:
        bg.content_score = bg.best_score
        info = bg.book_info
        if not info or not info.title:
            continue
        titles = [info.title]
        if info.title_remainder:
            titles.append(f"{info.title} {info.title_remainder}")
        bg.title_score = max(title_match_score(queries, t) for t in titles)
        bg.best_score = max(bg.best_score, bg.title_score)

    books.sort(key=lambda b: b.best_score, reverse=True)
