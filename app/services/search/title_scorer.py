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
import unicodedata

# 한글/한자/영문/숫자만 남기고 공백·문장부호 제거 (표기 차이 무시). 한자를 지우면 국문학 학위논문처럼 한자가 많은
# 제목이 '1930年代 世態小說 硏究' → '1930' 으로 줄어, '1930' 이 든 질의마다 '제목 전체 포함'으로 1.0 이 됐다.
# NFKC 를 먼저 걸어 호환 한자(U+F900~)를 통합 한자로 맞춘다 — 한자가 이제 일치에 참여한다
_STRIP_RE = re.compile(r"[^0-9a-zA-Z가-힣\u3400-\u4dbf\u4e00-\u9fff]+")
_HANJA_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")

# 한자를 뺀 제목도 견주는 하한 — 남는 글자가 한자를 넣은 제목 길이의 이 비율 이상일 때만. "'월인천강지곡(月印千江之曲)'
# 연구"처럼 한글 제목에 한자를 덧붙인 꼴은 한글 질의와 그대로 맞고(8/14), 한자가 대부분인 제목에서 조각만 남은 꼴
# ('1930' 4/12 · '에나타난' 4/17)은 견주지 않는다
_HANGUL_FORM_MIN_RATIO = 0.5

# 질의 문장 안 제목 포함을 완전 일치로 인정할 최소 제목 길이
# ("밤", "봄" 같은 초단문 제목의 우연 매칭 방지)
_MIN_CONTAIN_LEN = 4


def _normalize(s: str | None) -> str:
    return _STRIP_RE.sub("", unicodedata.normalize("NFKC", s or "").lower())


def _title_forms(title: str | None) -> list[str]:
    """견줄 제목 꼴 — 정규화한 제목, 그리고 한자를 뺀 꼴이 충분히 남으면 그것도."""
    t = _normalize(title)
    if not t:
        return []
    bare = _HANJA_RE.sub("", t)
    if bare and bare != t and len(bare) >= len(t) * _HANGUL_FORM_MIN_RATIO:
        return [t, bare]
    return [t]


def _bigrams(s: str) -> set[str]:
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def _pair_score(q: str, t: str) -> float:
    """정규화한 질의 하나 ↔ 제목 꼴 하나."""
    # 완전 일치
    if q == t:
        return 1.0
    # 질의 문장 안에 제목 전체 포함 → 제목을 그대로 입력한 것으로 간주
    if len(t) >= _MIN_CONTAIN_LEN and t in q:
        return 1.0
    # 제목 일부만 입력 → 제목 커버리지 비율
    if q in t:
        return len(q) / len(t)
    # 부분 겹침 → 문자 bigram Dice 유사도
    qb, tb = _bigrams(q), _bigrams(t)
    if qb and tb:
        return 2 * len(qb & tb) / (len(qb) + len(tb))
    return 0.0


def title_match_score(queries: list[str], title: str) -> float:
    """질의 목록(원본+재작성) 대비 제목 일치율. 최고값 반환."""
    forms = _title_forms(title)
    if not forms:
        return 0.0

    best = 0.0
    for raw in queries:
        q = _normalize(raw)
        if not q:
            continue
        for t in forms:
            score = _pair_score(q, t)
            if score >= 1.0:
                return 1.0
            best = max(best, score)

    return round(min(best, 1.0), 4)


# 종합 시 보조 점수(낮은 쪽)가 관련도에 기여하는 비중
_SECONDARY_WEIGHT = 0.4


def combine_scores(title: float | None, content: float) -> float:
    """
    제목·내용 일치율 종합 → 연관도.

      연관도 = primary + (1 - primary) × secondary × 0.4
      (primary = 큰 쪽, secondary = 작은 쪽)

    - 한쪽이 100%면 그대로 100% (제목 완전 일치 시 연관도 100% 보장)
    - 두 점수가 모두 높으면 큰 쪽 단독보다 연관도가 올라감
      예) 제목 60% + 내용 60% → 연관도 70%
    - 한쪽이 0이면 다른 쪽 값 그대로
    """
    t = title or 0.0
    primary, secondary = max(t, content), min(t, content)
    return round(min(primary + (1.0 - primary) * secondary * _SECONDARY_WEIGHT, 1.0), 4)


def apply_title_scores(books, query: str, rewritten: str | None = None) -> None:
    """
    BookChunkGroup 리스트에 title_score / content_score를 채우고
    best_score(연관도)를 두 점수의 종합값으로 갱신한 뒤 재정렬한다.
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
        bg.best_score = combine_scores(bg.title_score, bg.content_score)

    books.sort(key=lambda b: b.best_score, reverse=True)
