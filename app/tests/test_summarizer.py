"""_combine_sections — 입력 상한 + 전체 균등 샘플링 (재귀/앞부분편향 회귀 방지)."""
from services.ingestion import summarizer


class _FakeCfg:
    def __init__(self, cap):
        self.SUMMARIZER_MAX_INPUT_CHARS = cap


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
