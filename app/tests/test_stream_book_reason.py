"""test_stream_book_reason.py — SSE 델타 스트림 상태 머신 단위 테스트."""
import asyncio
import pytest

from services.search.sse_helpers import process_reason_deltas, EFFECT_DELIM


# ── 헬퍼 ─────────────────────────────────────────────────────────

async def _make_deltas(chunks: list[str]):
    for c in chunks:
        yield c


async def _empty_deltas():
    return
    yield  # pragma: no cover


async def _collect(gen) -> list[dict]:
    return [e async for e in gen]


# ── 기본 흐름 ─────────────────────────────────────────────────────

def test_kw_then_text_then_effect():
    """#KW: → text → ###EFFECT### → effect 기본 흐름."""
    chunks = [
        "#KW: 생명, 소중함\n",
        "추천 이유입니다.",
        "\n" + EFFECT_DELIM + "\n",
        "읽고 난 후 효과입니다.",
    ]
    events = asyncio.run(_collect(process_reason_deltas(_make_deltas(chunks), [])))
    types = [next(iter(e)) for e in events]
    assert types[0] == "keywords"
    assert "text" in types
    assert "effect" in types
    text_i = next(i for i, e in enumerate(events) if "text" in e)
    effect_i = next(i for i, e in enumerate(events) if "effect" in e)
    assert text_i < effect_i


def test_keywords_values_parsed():
    """#KW: 줄에서 정확한 키워드 목록 추출."""
    chunks = ["#KW: 사랑, 이별, 성장\n", "본문."]
    events = asyncio.run(_collect(process_reason_deltas(_make_deltas(chunks), [])))
    kw_events = [e for e in events if "keywords" in e]
    assert len(kw_events) == 1
    assert kw_events[0]["keywords"] == ["사랑", "이별", "성장"]


# ── 구분자 토큰 분리 ──────────────────────────────────────────────

def test_delimiter_split_across_chunks():
    """###EFFECT### 가 여러 청크에 걸쳐 오면 올바르게 감지."""
    chunks = [
        "#KW: 테스트\n",
        "추천 이유 텍스트.",
        "\n###",
        "EFFECT",
        "###\n",
        "독후 효과 텍스트.",
    ]
    events = asyncio.run(_collect(process_reason_deltas(_make_deltas(chunks), [])))
    all_text = "".join(e.get("text", "") for e in events)
    all_effect = "".join(e.get("effect", "") for e in events)
    assert "추천 이유" in all_text
    assert EFFECT_DELIM not in all_text
    assert "독후 효과" in all_effect
    assert EFFECT_DELIM not in all_effect


def test_delimiter_not_emitted_in_text():
    """구분자 자체가 {text} 이벤트로 나오지 않는다."""
    chunks = ["#KW: A\n", "앞부분.", EFFECT_DELIM, "뒷부분."]
    events = asyncio.run(_collect(process_reason_deltas(_make_deltas(chunks), [])))
    combined = "".join(e.get("text", "") + e.get("effect", "") for e in events)
    assert EFFECT_DELIM not in combined


# ── MARC 키워드 ───────────────────────────────────────────────────

def test_marc_keywords_skips_kw_parsing():
    """MARC 키워드 있으면 _process_deltas는 keywords 이벤트를 emit하지 않는다."""
    chunks = ["추천 이유.", "\n" + EFFECT_DELIM + "\n", "독후 효과."]
    events = asyncio.run(
        _collect(process_reason_deltas(_make_deltas(chunks), ["생명", "소중함"]))
    )
    assert not any("keywords" in e for e in events)
    all_text = "".join(e.get("text", "") for e in events)
    all_effect = "".join(e.get("effect", "") for e in events)
    assert "추천 이유" in all_text
    assert "독후 효과" in all_effect


def test_marc_keywords_immediate_effect_delim():
    """MARC 키워드 있을 때 첫 델타가 곧바로 ###EFFECT### 이면 동작."""
    chunks = [EFFECT_DELIM + "\n", "효과 내용."]
    events = asyncio.run(
        _collect(process_reason_deltas(_make_deltas(chunks), ["키워드"]))
    )
    assert not any("text" in e for e in events)  # 텍스트 구간 없음
    assert any("effect" in e for e in events)


# ── 구분자 없음 ───────────────────────────────────────────────────

def test_no_effect_delimiter_all_text():
    """###EFFECT### 없으면 모두 text로 emit."""
    chunks = ["#KW: 테스트\n", "추천 이유만 있습니다."]
    events = asyncio.run(_collect(process_reason_deltas(_make_deltas(chunks), [])))
    assert not any("effect" in e for e in events)
    assert any("text" in e for e in events)


# ── 빈 입력 ───────────────────────────────────────────────────────

def test_empty_stream():
    """빈 델타 스트림은 이벤트 없이 종료."""
    events = asyncio.run(_collect(process_reason_deltas(_empty_deltas(), [])))
    assert events == []


# ── 텍스트 완결성 ─────────────────────────────────────────────────

def test_text_before_and_after_delimiter_complete():
    """구분자 앞뒤 텍스트가 유실 없이 전달된다."""
    before = "이 책은 생명의 소중함을 이야기합니다."
    after = "이 책을 읽으면 마음이 따뜻해집니다."
    chunks = ["#KW: A\n", before, "\n" + EFFECT_DELIM + "\n", after]
    events = asyncio.run(_collect(process_reason_deltas(_make_deltas(chunks), [])))
    all_text = "".join(e.get("text", "") for e in events)
    all_effect = "".join(e.get("effect", "") for e in events)
    assert before in all_text
    assert after in all_effect
