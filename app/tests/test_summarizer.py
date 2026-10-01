"""_combine_sections — 입력 상한 + 전체 균등 샘플링 (재귀/앞부분편향 회귀 방지)."""
import asyncio
import re
import time

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


# ── reduce_section_summaries (2단계 계층 요약) ──────────────────────
# 섹션 요약을 이어 붙인 길이가 상한을 넘으면 _combine_sections 는 균등 샘플링으로 일부 섹션을
# 버린다(마지막 섹션이 늘 빠진다). 그 전에 연속 섹션끼리 묶어 중간 요약으로 줄인다.
class _ReduceCfg:
    def __init__(self, cap, concurrency=4):
        self.SUMMARIZER_MAX_INPUT_CHARS = cap
        self.SUMMARIZER_BOOK_TIMEOUT = 240
        self.LLM_SECTION_CONCURRENCY = concurrency


def _patch_reduce(monkeypatch, cap, fake_chat, concurrency=4):
    captured = {"prompt_names": [], "render_kw": []}

    class _Tpl:
        parser = "plain"
        params = {"max_tokens": 2048}

        def render(self, **kw):
            captured["render_kw"].append(kw)
            return ("sys", f"user::{kw['section_summaries']}", dict(self.params))

    def fake_get_prompt(name, doc_type=None):
        captured["prompt_names"].append(name)
        return _Tpl()

    monkeypatch.setattr(summarizer, "get_settings", lambda: _ReduceCfg(cap, concurrency))
    monkeypatch.setattr(summarizer, "_normalize_doc_type", lambda d: d or "book")
    monkeypatch.setattr(summarizer, "get_prompt", fake_get_prompt)
    monkeypatch.setattr(summarizer, "_chat_completion", fake_chat)
    return captured


def _items(n, filler=80):
    return [f"섹션요약{i:03d} " + "가" * filler for i in range(n)]


def _ranges(text):
    return [(int(a), int(b)) for a, b in re.findall(r"\[섹션 (\d+)~(\d+)\]", text)]


def test_reduce_under_cap_is_combine_sections_without_llm(monkeypatch):
    """상한 이하면 LLM 없이 지금 _combine_sections 와 같은 텍스트 — 대부분 문서는 그대로."""
    async def fake_chat(*a, **kw):
        raise AssertionError("상한 이하인데 LLM 호출됨")

    _patch_reduce(monkeypatch, 10000, fake_chat)
    items = ["가나다", "", "라마바"]
    out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items))
    assert out == summarizer._combine_sections(items) == "[섹션 1] 가나다\n\n[섹션 2] 라마바"
    assert asyncio.run(summarizer.reduce_section_summaries("제목", "저자", [])) == ""


def test_reduce_over_cap_covers_every_section_in_order(monkeypatch):
    """넘으면 연속한 섹션끼리 묶어 중간 요약 — 버리는 섹션 없이(마지막 섹션 포함) 순서대로 한 번씩."""
    prompts = []

    async def fake_chat(system, user, params, timeout):
        prompts.append(user)
        return f"중간요약{len(prompts):02d}"

    captured = _patch_reduce(monkeypatch, 1000, fake_chat)
    items = _items(40)                                   # 40 × 약 100자 ≈ 4,400자 > 1,000
    out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items))

    assert set(captured["prompt_names"]) == {"section_group_summary"}
    assert all(kw["title"] == "제목" and kw["author"] == "저자" for kw in captured["render_kw"])
    for i in range(40):                                  # 모든 섹션이 정확히 한 묶음에 한 번씩
        assert sum(f"섹션요약{i:03d}" in p for p in prompts) == 1, i
    for p in prompts:                                    # 묶음 하나는 이어진 섹션들
        nums = [int(n) for n in re.findall(r"섹션요약(\d{3})", p)]
        assert nums == list(range(nums[0], nums[0] + len(nums)))
    assert len(out) <= 1000
    ranges = _ranges(out)
    assert ranges[0][0] == 1 and ranges[-1][1] == 40     # 첫 섹션부터 마지막 섹션까지
    assert all(b[0] == a[1] + 1 for a, b in zip(ranges, ranges[1:]))   # 빈틈없이 이어진다


def test_reduce_second_level_when_intermediates_still_over_cap(monkeypatch):
    """중간 요약을 이어 붙여도 넘으면 중간 요약끼리 한 단계 더 묶는다(2단계)."""
    prompts = []

    async def fake_chat(system, user, params, timeout):
        prompts.append(user)
        return "요" * 200

    _patch_reduce(monkeypatch, 1000, fake_chat)
    out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", _items(60, filler=90)))

    assert any(re.search(r"\[섹션 \d+~\d+\]", p) for p in prompts)   # 2단계 입력 = 1단계 중간 요약
    assert len(out) <= 1000
    assert _ranges(out)[0][0] == 1 and _ranges(out)[-1][1] == 60


def test_reduce_falls_back_to_sampling_when_a_group_fails(monkeypatch):
    """중간 요약이 하나라도 실패하면(예외·빈 응답) 지금의 균등 샘플링으로 돌아간다."""
    items = _items(40)

    async def raising(system, user, params, timeout):
        if "섹션요약000" in user:
            raise RuntimeError("LLM 다운")
        return "중간요약"

    _patch_reduce(monkeypatch, 1000, raising)
    assert asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items)) == summarizer._combine_sections(items)

    async def blank(system, user, params, timeout):
        return "  " if "섹션요약039" in user else "중간요약"

    _patch_reduce(monkeypatch, 1000, blank)
    assert asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items)) == summarizer._combine_sections(items)


def test_reduce_falls_back_when_still_over_cap_after_two_levels(monkeypatch):
    """중간 요약이 줄지 않아 2단계 뒤에도 넘으면 균등 샘플링(상한 준수)으로 돌아간다."""
    async def fake_chat(system, user, params, timeout):
        return "요" * 900

    _patch_reduce(monkeypatch, 1000, fake_chat)
    items = _items(60, filler=90)
    out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items))
    assert out == summarizer._combine_sections(items)
    assert len(out) <= 1000


def test_reduce_runs_groups_concurrently_within_semaphore(monkeypatch):
    """중간 요약은 묶음끼리 동시에 부르되 LLM_SECTION_CONCURRENCY 를 넘지 않는다."""
    state = {"active": 0, "peak": 0}

    async def fake_chat(system, user, params, timeout):
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        await asyncio.sleep(0.02)
        state["active"] -= 1
        return "중간"

    _patch_reduce(monkeypatch, 1000, fake_chat, concurrency=2)
    asyncio.run(summarizer.reduce_section_summaries("제목", "저자", _items(60)))
    assert state["peak"] == 2


def test_reduce_pairs_up_large_summaries(monkeypatch):
    """섹션 요약이 커서 고르게 나누면 하나짜리 묶음만 생길 때도 둘 이상씩 묶어 실제로 줄인다
    (하나짜리 묶음은 다시 요약해도 줄지 않아, 그대로 두면 2단계 뒤 균등 샘플링으로 떨어진다)."""
    async def fake_chat(system, user, params, timeout):
        return "중" * 1000

    _patch_reduce(monkeypatch, 14000, fake_chat)
    items = ["가" * 6000, "나" * 6000, "다" * 6000]         # 18,000자 > 14,000
    groups = summarizer._group_for_reduce([(i + 1, i + 1, s) for i, s in enumerate(items)], 14000)
    assert any(len(g) >= 2 for g in groups)
    out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items))
    assert len(out) <= 14000 and "중" * 1000 in out
    assert out != summarizer._combine_sections(items)      # 샘플링으로 떨어지지 않았다


# ── combined_text — 마무리 단계가 한 번 만든 입력을 넷이 같이 쓴다 ──────
class _AllCfg(_FakeCfg):
    def __init__(self, cap):
        super().__init__(cap)
        self.SUMMARIZER_BOOK_TIMEOUT = 120
        self.SUMMARIZER_INTRO_TIMEOUT = 120


def test_generators_use_given_combined_text(monkeypatch):
    """combined_text 를 주면 _combine_sections 를 다시 부르지 않고 그 입력을 프롬프트에 넣는다."""
    users = []

    async def fake_chat(system, user, params, timeout):
        users.append(user)
        return "본문"

    def no_combine(_):
        raise AssertionError("combined_text 가 있는데 _combine_sections 를 불렀다")

    monkeypatch.setattr(summarizer, "get_settings", lambda: _AllCfg(10000))
    monkeypatch.setattr(summarizer, "_normalize_doc_type", lambda d: d or "book")
    monkeypatch.setattr(summarizer, "get_prompt", lambda name, doc_type=None: _FakeTpl())
    monkeypatch.setattr(summarizer, "_chat_completion", fake_chat)
    monkeypatch.setattr(summarizer, "_combine_sections", no_combine)

    given = "[섹션 1~40] 미리 합친 입력"
    sums = ["섹션 요약"]
    asyncio.run(summarizer.summarize_book_from_sections("제목", "저자", sums, "book", combined_text=given))
    asyncio.run(summarizer.generate_book_introduction("제목", "저자", "출판사", "2020", sums, "book", combined_text=given))
    asyncio.run(summarizer.generate_book_plot("제목", "저자", sums, "book", combined_text=given))
    asyncio.run(summarizer.generate_read_effect("제목", "저자", sums, "book", combined_text=given))
    assert len(users) == 4 and all(given in u for u in users)


def test_generators_without_combined_text_still_combine(monkeypatch):
    """combined_text 없이 부르는 기존 호출(백필 태스크)은 지금처럼 _combine_sections 로 합친다."""
    users = []

    async def fake_chat(system, user, params, timeout):
        users.append(user)
        return "본문"

    monkeypatch.setattr(summarizer, "get_settings", lambda: _AllCfg(10000))
    monkeypatch.setattr(summarizer, "_normalize_doc_type", lambda d: d or "book")
    monkeypatch.setattr(summarizer, "get_prompt", lambda name, doc_type=None: _FakeTpl())
    monkeypatch.setattr(summarizer, "_chat_completion", fake_chat)

    asyncio.run(summarizer.generate_book_introduction(
        title="제목", author="저자", publisher="출판사", pub_date="2020",
        section_summaries=["가나다", "라마바"], doc_type="book",
    ))
    asyncio.run(summarizer.summarize_book_from_sections(
        title="제목", author="저자", section_summaries=["가나다", "라마바"], doc_type="book",
    ))
    assert users == ["user::[섹션 1] 가나다\n\n[섹션 2] 라마바"] * 2


# ── reduce_section_summaries — 묶음 하나 실패 시 남은 호출 취소·바깥 취소 전파·실행 기록 ──────
# 한 묶음이 실패하면 그 단계 결과는 어차피 버려지므로 남은 호출을 바로 끊는다.
# 마무리 단계의 시간 예산(asyncio.wait_for)이 바깥에서 취소할 때도 호출이 남지 않아야 한다.
def _leftover_tasks():
    """지금 도는 태스크(현재 것 제외) — reduce 가 끝난 뒤 남은 중간 요약 호출이 없어야 한다."""
    return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]


def _n_groups(items, cap):
    return len(summarizer._group_for_reduce([(i + 1, i + 1, s) for i, s in enumerate(items)], cap))


def test_reduce_cancels_remaining_groups_when_one_group_fails(monkeypatch):
    """묶음 하나가 실패하면 남은 호출(진행 중이거나 세마포어를 기다리는 것)을 바로 취소하고 균등 샘플링으로 돌아간다 —
    어차피 그 단계 결과는 버리므로, 응답 없는 장애에서 시간과 gemma 자리를 아낀다."""
    items = _items(60)                                   # 묶음 여러 개, 동시 호출은 2개까지
    state = {"started": 0, "cancelled": 0}

    async def fake_chat(system, user, params, timeout):
        state["started"] += 1
        if "섹션요약000" in user:                         # 첫 묶음은 곧바로 실패
            await asyncio.sleep(0.01)
            raise RuntimeError("LLM 다운")
        try:
            await asyncio.sleep(30)                      # 나머지는 응답이 없다
        except asyncio.CancelledError:
            state["cancelled"] += 1
            raise
        return "중간요약"

    _patch_reduce(monkeypatch, 1000, fake_chat, concurrency=2)
    stats = summarizer.ReduceStats()

    async def scenario():
        out = await summarizer.reduce_section_summaries("제목", "저자", items, stats=stats)
        return out, _leftover_tasks()

    t0 = time.monotonic()
    out, leftover = asyncio.run(scenario())

    assert time.monotonic() - t0 < 5                     # 30초 응답을 기다리지 않았다
    assert out == summarizer._combine_sections(items)
    assert state["started"] < _n_groups(items, 1000)     # 세마포어를 기다리던 묶음은 시작도 못 했다
    assert state["cancelled"] == state["started"] - 1    # 시작한 나머지 호출은 모두 취소됐다
    assert leftover == []                                # 취소된 호출이 루프 밖에 남지 않았다
    assert stats.fallback is True and stats.levels == 1


def test_reduce_outer_cancellation_propagates_and_cancels_calls(monkeypatch):
    """바깥이 reduce 를 취소하면 CancelledError 를 삼키지 않고 올리며, 진행 중인 호출도 모두 취소된다."""
    state = {"started": 0, "cancelled": 0}

    async def fake_chat(system, user, params, timeout):
        state["started"] += 1
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            state["cancelled"] += 1
            raise
        return "중간요약"

    _patch_reduce(monkeypatch, 1000, fake_chat)

    async def scenario():
        task = asyncio.ensure_future(summarizer.reduce_section_summaries("제목", "저자", _items(60)))
        await asyncio.sleep(0.05)                        # 호출이 나가도록 기다린 뒤 취소
        task.cancel()
        outcome = "returned"
        try:
            await task
        except asyncio.CancelledError:
            outcome = "cancelled"
        return outcome, _leftover_tasks()

    outcome, leftover = asyncio.run(scenario())
    assert outcome == "cancelled"                        # 폴백으로 돌아가며 삼키지 않았다
    assert state["started"] > 0 and state["cancelled"] == state["started"]
    assert leftover == []


def test_reduce_wait_for_timeout_leaves_no_calls_running(monkeypatch):
    """마무리 단계가 쓰는 방식 그대로 asyncio.wait_for 로 감싸 시간이 다 되면 TimeoutError 가 나고 호출이 남지 않는다."""
    state = {"started": 0, "cancelled": 0}

    async def fake_chat(system, user, params, timeout):
        state["started"] += 1
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            state["cancelled"] += 1
            raise
        return "중간요약"

    _patch_reduce(monkeypatch, 1000, fake_chat)
    stats = summarizer.ReduceStats()

    async def scenario():
        outcome = "returned"
        try:
            await asyncio.wait_for(
                summarizer.reduce_section_summaries("제목", "저자", _items(60), stats=stats), timeout=0.1)
        except asyncio.TimeoutError:
            outcome = "timeout"
        return outcome, _leftover_tasks()

    t0 = time.monotonic()
    outcome, leftover = asyncio.run(scenario())
    assert outcome == "timeout" and time.monotonic() - t0 < 5
    assert state["started"] > 0 and state["cancelled"] == state["started"]
    assert leftover == []
    assert stats.levels == 1 and stats.groups > 0        # 끊기기 전까지의 기록이 남는다(fallback 표시는 호출자 몫)


def test_reduce_stats_report_levels_groups_and_fallback(monkeypatch):
    """실행 기록 — 마무리 단계가 meta 에 싣는다. levels 0 = 합치기만, 시작한 중간 요약 단계까지 센다(실패한 단계 포함)."""
    assert (summarizer.ReduceStats().levels, summarizer.ReduceStats().groups,
            summarizer.ReduceStats().fallback) == (0, 0, False)

    async def short(system, user, params, timeout):
        return "요" * 200

    def run(cap, chat, items):
        _patch_reduce(monkeypatch, cap, chat)
        stats = summarizer.ReduceStats()
        out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items, stats=stats))
        return stats, out

    # 상한 이하 — 합치기만
    stats, _ = run(10000, short, _items(5))
    assert (stats.levels, stats.groups, stats.fallback) == (0, 0, False)

    # 1단계에서 상한 안으로
    items = _items(40)
    stats, out = run(1000, short, items)
    n1 = _n_groups(items, 1000)
    assert (stats.levels, stats.groups, stats.fallback) == (1, n1, False) and len(out) <= 1000

    # 중간 요약을 이어도 넘어 2단계까지
    items = _items(60, filler=90)
    stats, out = run(1000, short, items)
    assert stats.levels == 2 and stats.groups > _n_groups(items, 1000) and stats.fallback is False
    assert len(out) <= 1000

    # 묶음 하나가 실패 → 1단계에서 샘플링으로
    async def failing(system, user, params, timeout):
        raise RuntimeError("LLM 다운")

    items = _items(40)
    stats, out = run(1000, failing, items)
    assert (stats.levels, stats.groups, stats.fallback) == (1, n1, True)
    assert out == summarizer._combine_sections(items)

    # 2단계 뒤에도 상한 초과 → 샘플링
    async def long(system, user, params, timeout):
        return "요" * 900

    items = _items(60, filler=90)
    stats, out = run(1000, long, items)
    assert stats.levels == 2 and stats.fallback is True
    assert out == summarizer._combine_sections(items)

    # 섹션 요약이 없으면 아무것도 하지 않는다
    stats, out = run(1000, short, [])
    assert out == "" and (stats.levels, stats.groups, stats.fallback) == (0, 0, False)
