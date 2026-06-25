"""_combine_sections — 입력 상한 + 전체 균등 샘플링 (재귀/앞부분편향 회귀 방지)."""
import asyncio

from services.ingestion import summarizer
from services.ingestion.summarizer import _parse_summary_themes


# ── _parse_summary_themes — 마크다운 볼드 라벨 누수 방지 ──────────

def test_parse_plain_labels():
    s, t = _parse_summary_themes("SUMMARY: 본문 요약.\nTHEMES: 가, 나, 다")
    assert s == "본문 요약."
    assert t == ["가", "나", "다"]


def test_parse_bold_labels_stripped():
    """gemma가 **SUMMARY:** / **THEMES:** 로 감싸도 라벨·별표가 새지 않는다."""
    raw = "**SUMMARY:** 본 연구는 변동성을 분석한다.\n\n**THEMES:** 코스닥, 변동성, VAR"
    s, t = _parse_summary_themes(raw)
    assert "SUMMARY" not in s and "*" not in s
    assert s == "본 연구는 변동성을 분석한다."
    assert t == ["코스닥", "변동성", "VAR"]
    assert all("*" not in x for x in t)


def test_parse_no_labels_passthrough():
    s, t = _parse_summary_themes("그냥 요약 문장입니다.")
    assert s == "그냥 요약 문장입니다."
    assert t == []


class _FakeCfg:
    def __init__(self, cap):
        self.SUMMARIZER_MAX_INPUT_CHARS = cap
        self.SUMMARIZER_PLOT_TIMEOUT = 120
        self.SUMMARIZER_READ_EFFECT_TIMEOUT = 120


def test_no_truncation_when_under_cap(monkeypatch):
    monkeypatch.setattr(summarizer, "get_settings", lambda: _FakeCfg(10000))
    out = summarizer._combine_sections(["가나다", "라마바", "사아자"])
    assert "[섹션 1] 가나다" in out
    assert "[섹션 3] 사아자" in out  # 마지막 섹션 포함


def test_caps_and_samples_across_whole_book(monkeypatch):
    """초과 시 앞만 자르지 않고 전체에 걸쳐 샘플링 — 후반 섹션도 대표로 포함."""
    monkeypatch.setattr(summarizer, "get_settings", lambda: _FakeCfg(80))
    items = [f"섹션내용{i:03d}" for i in range(100)]  # 100개 → 반드시 초과
    out = summarizer._combine_sections(items)
    assert len(out) <= 80                      # 상한 준수
    assert out.count("섹션내용") >= 2          # 여러 구간 샘플됨 (앞만 아님)


def test_terminates_no_recursion(monkeypatch):
    """자기 자신을 호출하던 무한재귀 회귀 가드 — 호출이 반환되면 통과."""
    monkeypatch.setattr(summarizer, "get_settings", lambda: _FakeCfg(50))
    assert isinstance(summarizer._combine_sections([f"x{i}" for i in range(200)]), str)


def test_empty_input(monkeypatch):
    monkeypatch.setattr(summarizer, "get_settings", lambda: _FakeCfg(100))
    assert summarizer._combine_sections([]) == ""
    assert summarizer._combine_sections([None, ""]) == ""


# ── generate_book_plot (줄거리 사전 생성) ────────────────────
class _FakeTpl:
    parser = "plain"
    params = {"max_tokens": 1500, "temperature": 0.4}

    def render(self, **kw):
        return ("sys", f"user::{kw.get('section_summaries', '')}", dict(self.params))


def test_generate_book_plot_empty_returns_none(monkeypatch):
    """섹션 요약이 없으면 LLM 호출 없이 None."""
    monkeypatch.setattr(summarizer, "get_settings", lambda: _FakeCfg(10000))
    assert asyncio.run(summarizer.generate_book_plot("제목", "저자", [])) is None


def test_generate_book_plot_uses_doc_type_prompt(monkeypatch):
    """doc_type 별 plot 프롬프트를 조회하고 섹션 요약을 프롬프트에 주입한다."""
    captured = {}

    def fake_get_prompt(name, doc_type=None):
        captured["name"] = name
        captured["doc_type"] = doc_type
        return _FakeTpl()

    async def fake_chat(system, user, params, timeout):
        captured["user"] = user
        captured["timeout"] = timeout
        return "줄거리 본문"

    monkeypatch.setattr(summarizer, "get_settings", lambda: _FakeCfg(10000))
    monkeypatch.setattr(summarizer, "_normalize_doc_type", lambda d: d or "book")
    monkeypatch.setattr(summarizer, "get_prompt", fake_get_prompt)
    monkeypatch.setattr(summarizer, "_chat_completion", fake_chat)

    out = asyncio.run(summarizer.generate_book_plot(
        "제목", "저자", ["가나다", "라마바"], doc_type="literature",
    ))
    assert out == "줄거리 본문"
    assert captured["name"] == "plot"
    assert captured["doc_type"] == "literature"
    assert captured["timeout"] == 120
    assert "가나다" in captured["user"]  # 섹션 요약이 프롬프트에 주입됨


# ── generate_read_effect (독후 효과 사전 생성) ────────────────
def test_generate_read_effect_empty_returns_none(monkeypatch):
    """섹션 요약이 없으면 LLM 호출 없이 None."""
    monkeypatch.setattr(summarizer, "get_settings", lambda: _FakeCfg(10000))
    assert asyncio.run(summarizer.generate_read_effect("제목", "저자", [])) is None


def test_generate_read_effect_uses_doc_type_prompt(monkeypatch):
    """doc_type 별 read_effect 프롬프트를 조회하고 섹션 요약을 프롬프트에 주입한다."""
    captured = {}

    def fake_get_prompt(name, doc_type=None):
        captured["name"] = name
        captured["doc_type"] = doc_type
        return _FakeTpl()

    async def fake_chat(system, user, params, timeout):
        captured["timeout"] = timeout
        captured["user"] = user
        return "독후 효과 본문"

    monkeypatch.setattr(summarizer, "get_settings", lambda: _FakeCfg(10000))
    monkeypatch.setattr(summarizer, "_normalize_doc_type", lambda d: d or "book")
    monkeypatch.setattr(summarizer, "get_prompt", fake_get_prompt)
    monkeypatch.setattr(summarizer, "_chat_completion", fake_chat)

    out = asyncio.run(summarizer.generate_read_effect(
        "제목", "저자", ["가나다", "라마바"], doc_type="literature",
    ))
    assert out == "독후 효과 본문"
    assert captured["name"] == "read_effect"
    assert captured["doc_type"] == "literature"
    assert captured["timeout"] == 120
    assert "가나다" in captured["user"]
