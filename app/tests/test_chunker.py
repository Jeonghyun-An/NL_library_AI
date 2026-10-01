"""chunker.semantic_chunk — 문장 5개 이하 분기 크기 상한·줄바꿈 폴백.

임베딩 모델 없이 돈다. embed_fn 자리에 결정적인 가짜 임베딩을 넣는다.
- _hash_embed: 문장마다 md5 로 만든 벡터 — 실제 모델처럼 이웃 유사도가 제각각이라 경계가 고르게 난다.
- _topic_embed: 문장에 든 주제어로 정한 one-hot — 같은 주제 안은 유사도가 똑같아 주제가 바뀌는 곳에서만 경계가 난다.
- _flat_embed: 모든 문장이 같은 벡터 — 의미 경계가 하나도 안 나는 최악의 경우.
"""
import collections
import hashlib

import numpy as np

from services.ingestion import chunker
from services.ingestion.chunker import MAX_CHUNK_BYTES, _normalize_linebreaks, semantic_chunk

SECTION = dict(min_tokens=800, max_tokens=5000, apply_byte_guard=False)   # stages.split_into_sections 와 같은 값
SEARCH = dict(min_tokens=128, max_tokens=1024, apply_byte_guard=True)     # stages.run_embed_index(검색 청크) 기본값


def _hash_embed(sentences):
    return np.array([[b - 127.5 for b in hashlib.md5(s.encode("utf-8")).digest()] for s in sentences])


_TOPICS = ("서론", "선행연구", "연구방법", "분석결과", "논의", "결론")


def _topic_embed(sentences):
    vecs = []
    for s in sentences:
        v = [0.0] * (len(_TOPICS) + 1)
        v[next((i for i, t in enumerate(_TOPICS) if t in s), len(_TOPICS))] = 1.0
        vecs.append(v)
    return np.array(vecs)


def _flat_embed(sentences):
    return np.ones((len(sentences), 8))


def _page_map(pages):
    """stages.split_into_sections 와 같은 방식: 쪽 텍스트를 "\\n\\n" 으로 잇고 글자 위치 → 쪽 번호."""
    page_map, cursor = {}, 0
    for no, t in enumerate(pages, start=1):
        for i in range(len(t)):
            page_map[cursor + i] = no
        cursor += len(t) + 2
    return "\n\n".join(pages), page_map


def _wrap(text, width=48):
    """PDF 컬럼 줄넘김 흉내 — 단락 안을 width 글자마다 홑줄바꿈으로 끊는다."""
    return "\n".join(text[i:i + width] for i in range(0, len(text), width))


def _prose_document(table_rows=0):
    """마침표가 충분한 일반 논문 본문 — 주제 6개, 제목 줄, 단락 구분(빈 줄), PDF 줄넘김(홑줄바꿈), 10쪽.
    '분석결과' 는 섹션 상한(7,500자)을 넘게 길어 섹션·검색 청크 모두 크기 분할을 탄다.
    table_rows 를 주면 '분석결과' 단락 사이에 마침표 없는 표(행은 홑줄바꿈)를 끼운다 — 정규화하면
    검색 청크 상한(1,536자)을 넘는 '문장' 하나가 된다. 실제 논문의 표·참고문헌 덩어리가 이렇다."""
    sizes = {"서론": 30, "선행연구": 40, "연구방법": 25, "분석결과": 200, "논의": 35, "결론": 15}
    numerals = ("Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ")
    paragraphs = []
    for numeral, topic in zip(numerals, _TOPICS):
        sents = []
        for k in range(sizes[topic]):
            n, d = (k * 37) % 500 + 20, (k * 7) % 30 + 1
            sents.append((
                f"{topic}에서는 {k}번째 쟁점으로 표본 {n}명의 응답 분포를 정리하였다.",
                f"{topic}의 {k}번째 관찰은 집단 간 차이가 {d}점 수준으로 나타났다는 점이다.",
                f"이와 관련하여 {topic} {k}항은 측정 도구의 신뢰도와 타당도를 함께 점검하였다.",
                f"{topic} {k}항에서는 조사 대상 기관 {n}곳의 운영 자료를 연도별로 비교하고, "
                f"그 변화가 정책 환경과 어떻게 맞물리는지 검토하였다.",
            )[k % 4])
        paragraphs.append(f"{numeral}. {topic}")
        for i in range(0, len(sents), 5):
            paragraphs.append(_wrap(" ".join(sents[i:i + 5])))
            if topic == "분석결과" and table_rows and i == 10:
                paragraphs.append("분석결과 표 3 지역별 응답 분포\n" + "\n".join(
                    f"지역{r:03d} {r * 13 % 97} {r * 7 % 89} {r * 5 % 83}" for r in range(table_rows)))
    pages, cur = [], []
    for p in paragraphs:
        cur.append(p)
        if sum(len(x) for x in cur) > 1800:
            pages.append("\n\n".join(cur))
            cur = []
    if cur:
        pages.append("\n\n".join(cur))
    return _page_map(pages)


def _stat_table_document(n_pages=100, rows_per_page=50):
    """마침표 없는 통계표 약 14만 자 — 쪽마다 표 제목 줄 + 행(홑줄바꿈), 쪽 사이는 빈 줄.
    소수점(56.7)은 있지만 뒤에 공백이 없어 문장 분리에 안 걸린다 — 정규화 뒤 '문장' 1개."""
    pages, rows = [], []
    for p in range(n_pages):
        page_rows = [
            f"|{p * rows_per_page + r:05d}|지역{(p * 7 + r) % 17:02d}|{2000 + r % 20}"
            f"|{(p * 31 + r * 17) % 9973}|{(r * 13) % 101}.{p % 10}|"
            for r in range(rows_per_page)
        ]
        rows += page_rows
        pages.append("\n".join([f"표 {p + 1} 지역별 연도별 통계 (단위 천 명)"] + page_rows))
    text, page_map = _page_map(pages)
    return text, page_map, rows


def _fingerprint(chunks):
    """(청크마다 (글자 수, 시작 쪽, 끝 쪽), 전체 텍스트 sha1 앞 16자리)"""
    return (
        [(len(c.text), c.page_start, c.page_end) for c in chunks],
        hashlib.sha1("\x1e".join(c.text for c in chunks).encode("utf-8")).hexdigest()[:16],
    )


# ── 일반 본문: 고치기 전과 같은 경계 (회귀) ──────────────────────────────
# 문장 5개 이하 분기 상한·줄바꿈 폴백을 넣기 전 chunker.py(5a7613b)로 뽑은 지문이다. 고치기 전에도
# 통과하고(현재 동작 고정) 고친 뒤에도 그대로 통과해야 한다. '분석결과' 섹션(7,663자 = 5,108토큰)이
# 상한을 조금 넘는 것도 지금 동작이다 — 문장마다 내림한 추정치를 더하는 묶기 규칙 때문이고 손대지 않는다.
_GOLDEN_TOPIC_SECTION = (
    [(1460, 1, 1), (2063, 1, 2), (1233, 2, 3), (7663, 3, 8), (2817, 3, 8), (2413, 8, 10)],
    "579b8cef380708da",
)
_GOLDEN_TOPIC_SEARCH = (
    [(1460, 1, 1), (1572, 1, 2), (490, 1, 2), (1233, 2, 3), (1569, 3, 8), (1573, 3, 8),
     (1579, 3, 8), (1544, 3, 8), (1560, 3, 8), (1521, 3, 8), (1129, 3, 8), (1578, 8, 9),
     (834, 8, 10)],
    "f1c7ea92096c1a29",
)
_GOLDEN_HASH_SECTION = (
    [(1219, 1, 1), (1889, 1, 2), (1441, 2, 3), (1316, 3, 3), (1751, 4, 4), (2069, 4, 5),
     (1213, 5, 6), (1307, 6, 7), (1476, 7, 7), (1979, 7, 9), (1984, 9, 10)],
    "c71aec9d5c8fc4ef",
)
# 표가 낀 본문의 검색 청크 — 상한을 넘는 '문장'(표 1,850자)을 지금처럼 글자 수 지점(1,536자)에서
# 자르는지 본다. 그 자리를 경계 찾기(_split_by_chars)로 바꾸면 뒤 문장들의 묶음까지 밀려
# (1536, 1559) → (1534, 1561) 처럼 일반 본문 경계가 달라진다. 실제 KCI 논문 488편 중 45편이 그랬다.
_GOLDEN_TABLE_SEARCH = (
    [(1460, 1, 1), (1572, 1, 2), (490, 1, 2), (1233, 2, 3), (784, 3, 9), (1536, 3, 9),
     (1559, 3, 9), (1579, 3, 9), (1569, 3, 9), (1565, 3, 9), (1552, 3, 9), (1561, 3, 9),
     (544, 3, 9), (1578, 9, 10), (834, 9, 10)],
    "0b572f5a680e59be",
)


def test_prose_boundaries_unchanged():
    text, page_map = _prose_document()
    assert _fingerprint(semantic_chunk(text, _topic_embed, page_map=page_map, **SECTION)) == _GOLDEN_TOPIC_SECTION
    assert _fingerprint(semantic_chunk(text, _topic_embed, page_map=page_map, **SEARCH)) == _GOLDEN_TOPIC_SEARCH
    assert _fingerprint(semantic_chunk(text, _hash_embed, page_map=page_map, **SECTION)) == _GOLDEN_HASH_SECTION
    text, page_map = _prose_document(table_rows=120)
    assert _fingerprint(semantic_chunk(text, _topic_embed, page_map=page_map, **SEARCH)) == _GOLDEN_TABLE_SEARCH


# ── 문장 5개 이하 분기에도 크기 상한 ─────────────────────────────────


def test_few_giant_sentences_are_capped():
    """문장 3개짜리 12만 자(줄바꿈 없음) — 지금은 문장 5개 이하 분기가 크기를 안 보고 한 덩어리로
    내보낸다(섹션 하나 = 8만 토큰). 바이트 가드를 켜든 끄든 상한 이하로 나뉘고 내용은 그대로여야 한다."""
    def sentence(k):
        return f"제{k}판독문 " + " ".join(f"항목{k}{i:05d} 수치 {i * 7 % 997}" for i in range(2600)) + "로 기록되었다."

    text = " ".join(sentence(k) for k in range(3))
    for params in (SECTION, SEARCH):
        out = semantic_chunk(text, _hash_embed, page_map={}, **params)
        assert len(out) > 1
        assert max(c.token_count for c in out) <= params["max_tokens"]
        assert [c.chunk_idx for c in out] == list(range(len(out)))
        assert "".join(c.text for c in out).replace(" ", "") == text.replace(" ", "")   # 버린 글자 없음
    search = semantic_chunk(text, _hash_embed, page_map={}, **SEARCH)
    assert max(len(c.text.encode("utf-8")) for c in search) <= MAX_CHUNK_BYTES


def _nonspace(s: str) -> str:
    return "".join(s.split())


def test_few_sentences_over_cap_keep_short_fragments_and_merge_the_tail():
    """문장 5개 이하인데 상한을 넘는 본문 — 잘라도 문장 분리가 버리는 5자 이하 조각('2.'·'3.' 같은 번호·'끝')까지
    글자가 하나도 빠지지 않아야 하고, 상한 근처에서 자른 뒤 남은 자투리(min_tokens 미만)는 혼자 섹션·청크가
    되지 않고 이웃 조각에 붙는다(본 경로의 재병합과 같다)."""
    for params in (SECTION, SEARCH):
        max_chars = int(params["max_tokens"] * 1.5)
        numbered = "1. " + "가나다라마바사 " * 700 + "2. 3. 4. " + "아자차카타파하 " * 700 + "5. 끝"
        just_over = "가나다라 " * (max_chars // 5 + 2) + "2. 3. 4. 끝"      # 한 조각을 조금 넘는다
        for text in (numbered, just_over):
            out = semantic_chunk(text, _hash_embed, page_map={}, **params)
            assert _nonspace("".join(c.text for c in out)) == _nonspace(text), params["max_tokens"]
            assert all(c.token_count >= params["min_tokens"] for c in out), [c.token_count for c in out]
            assert max(c.token_count for c in out) <= params["max_tokens"] + params["min_tokens"]
            assert [c.chunk_idx for c in out] == list(range(len(out)))
    # 본문 전체가 min_tokens 보다 작으면 그대로 한 덩어리다
    tiny = "1. 서론에서는 연구 배경을 다룬다. 2. 3. 끝"
    for params in (SECTION, SEARCH):
        assert [c.text for c in semantic_chunk(tiny, _hash_embed, page_map={}, **params)] == [tiny]


def test_period_free_table_is_capped():
    """마침표 없는 표·통계 14만 자 — 지금은 '문장' 1개로 잡혀 섹션 하나(약 9.4만 토큰)가 되고,
    섹션 요약이 앞 12,000자(SUMMARIZER_MAX_SECTION_CHARS)만 읽는다. 상한 이하 여러 개여야 한다."""
    text, page_map, _ = _stat_table_document()
    assert len(text) > 140_000
    sections = semantic_chunk(text, _hash_embed, page_map=page_map, **SECTION)
    assert len(sections) > 1
    assert max(c.token_count for c in sections) <= SECTION["max_tokens"]
    chunks = semantic_chunk(text, _hash_embed, page_map=page_map, **SEARCH)
    assert max(c.token_count for c in chunks) <= SEARCH["max_tokens"]
    # 의미 경계가 하나도 안 나는 최악의 경우 — 크기 분할 뒤 자투리 재병합(_merge_small_chunks)이 상한을 넘길 수
    # 있다. min_tokens 미만 조각이 다음 조각(≤ max_tokens)을 흡수하면 < max + min, 그 뒤 끝 자투리(< min)를 다시
    # 앞에 붙이면 < max + 2·min 이다(추정치 내림 오차 몇 토큰 제외). 섹션 설정이면 5,000 + 2 × 800 = 6,600토큰
    # ≈ 9,900자라 섹션 요약 입력 상한(SUMMARIZER_MAX_SECTION_CHARS 12,000자) 아래다.
    worst = semantic_chunk(text, _flat_embed, page_map=page_map, **SECTION)
    assert len(worst) > 1
    assert max(c.token_count for c in worst) <= SECTION["max_tokens"] + 2 * SECTION["min_tokens"]
    assert max(len(c.text) for c in worst) <= 12_000


def test_split_by_chars_prefers_boundaries_and_loses_nothing():
    s = "가나다라 " * 1000                      # 5,000자, 공백 경계만 있음
    parts = chunker._split_by_chars(s, 700)
    assert "".join(parts) == s
    assert all(len(p) <= 700 for p in parts)
    assert all(p.endswith(" ") for p in parts[:-1])   # 글자 중간이 아니라 공백에서 끊었다
    assert chunker._split_by_chars("가" * 1500, 700) == ["가" * 700, "가" * 700, "가" * 100]   # 경계가 없으면 글자 수에서


# ── 줄바꿈 폴백 — 정규화 전 원문을 줄 단위로(정규화가 홑줄바꿈을 먼저 공백으로 바꾼다) ──


def test_line_split_keeps_table_rows_whole():
    """마침표 없는 표는 줄(행) 단위로 나뉜다 — 섹션·청크의 줄 하나하나가 표의 온전한 행이고, 모든 행이
    정확히 한 번 나온다. 정규화 뒤에 나누면 홑줄바꿈이 공백이 돼 한 쪽의 행이 한 줄로 뭉치고 행 중간에서 끊긴다."""
    text, page_map, rows = _stat_table_document()
    for embed in (_hash_embed, _flat_embed):
        for params in (SECTION, SEARCH):
            seen = collections.Counter()
            for c in semantic_chunk(text, embed, page_map=page_map, **params):
                for line in c.text.split("\n"):
                    if not line.startswith("표 "):        # 쪽마다 붙은 표 제목 줄은 빼고 센다
                        seen[line] += 1
            assert seen == collections.Counter(rows), (embed.__name__, params["max_tokens"])


def test_line_mode_resolves_pages():
    """줄 단위 위치는 원문 기준이라 page_map 과 맞는다 — 섹션마다 쪽 범위가 붙고 1쪽부터 100쪽까지 순서대로 이어진다."""
    text, page_map, _ = _stat_table_document()
    pages = [(c.page_start, c.page_end) for c in semantic_chunk(text, _hash_embed, page_map=page_map, **SECTION)]
    assert all(s is not None and s <= e for s, e in pages)
    assert pages[0][0] == 1 and pages[-1][1] == 100
    assert [s for s, _ in pages] == sorted(s for s, _ in pages)


def test_split_lines_keeps_short_lines_with_raw_offsets():
    """5자 이하 줄(합계·셀 하나)은 버리지 않고 다음 줄과 묶고, 끝에 남으면 앞 단위에 붙인다.
    줄 안의 연속 공백만 줄이고, start/end 는 원문 위치다."""
    raw = "합계\n|001|가|\n\n  |002|  나|  \n12"
    units = chunker._split_lines_with_offsets(raw)
    assert units == [
        {"text": "합계\n|001|가|", "start": 0, "end": 10},
        {"text": "|002| 나|\n12", "start": 12, "end": 28},
    ]
    assert raw[0:10] == "합계\n|001|가|" and raw[12:28] == "  |002|  나|  \n12"


def test_line_fallback_skips_text_within_cap():
    """상한 안에 드는 짧은 본문(문장 5개 이하 초록·작은 표)은 줄바꿈 폴백 없이 지금처럼 정규화한 한 덩어리다."""
    abstract = "본 연구는 지역 도서관의\n이용 실태를 조사하였다. 표본은 전국 30개 관\n이다. 그 결과 이용률이 높아졌다."
    small_table = "\n".join(f"|{r:03d}|지역{r % 5}|{r * 3}|" for r in range(20))
    for t in (abstract, small_table):
        for params in (SECTION, SEARCH):
            out = semantic_chunk(t, _hash_embed, page_map={}, **params)
            assert [c.text for c in out] == [_normalize_linebreaks(t)]
