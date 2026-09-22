"""test_research_runner.py — 단계 오케스트레이션

async 테스트는 `asyncio.run` 으로 돈다. `@pytest.mark.asyncio` 를 쓰면 안
된다 — `pytest-asyncio` 가 이 저장소에 설치돼 있지 않고, 플러그인이 없으면
pytest 는 코루틴을 **실행하지 않고 경고만 남긴 뒤 통과로 처리한다.** 초록불인
채로 아무것도 검증하지 않는 테스트가 되므로 관례(`test_research_explorer.py`)
를 그대로 따른다.

relay 는 모듈 최상단에서 import 하지 않는다. `redis` 는 requirements 에만
있고 로컬 venv 에는 없어서, 최상단 import 는 수집 단계에서 세션을 통째로
죽인다(`docs/ops/recurring-gotchas.md` 13번의 torch 와 같은 함정).
"""
import asyncio
import importlib
import json
import sys
from unittest.mock import MagicMock

from services.research.critic import Verdict
from services.research.runner import explore_subquestion
from services.research.state import ResearchState, SubQuestion, merge_params


class _FakeCritic:
    """항상 부족을 반환하는 critic — 루프 상한을 검증한다."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, subq, evidence, *, params):
        self.calls += 1
        return Verdict("insufficient", note="부족", new_queries=["다른 검색어"])


class _ParseFailedCritic:
    """판정을 못 읽은 critic — `critic._failed()` 가 내는 형태 그대로다."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, subq, evidence, *, params):
        self.calls += 1
        return Verdict("sufficient", note="자동 점검을 완료하지 못했다", parse_failed=True)


def _hits(cnts_ids, *, query="q"):
    hits = [
        {"book_id": cid, "chunk_id": f"{cid}-c-{query}", "text": "본문",
         "page_start": 1, "page_end": 1, "score": 0.9}
        for cid in cnts_ids
    ]
    meta = {
        cid: {"title": f"논문 {cid}", "pub_date": "2008-06", "kci_citations": 3}
        for cid in cnts_ids
    }
    return hits, meta


async def _fake_explore(query, *, params, db):
    return _hits(["A"], query=query)


async def _empty_explore(query, *, params, db):
    return [], {}


class TestExploreSubquestion:
    def test_always_insufficient_stops_at_max_recheck(self):
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="하위질문")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_fake_explore, critique_fn=critic, emit=None,
        ))
        assert critic.calls == 3            # 최초 1 + 재검색 2
        assert len(sq.queries) == 3
        assert sq.verdict == "insufficient"
        assert sq.note == "부족"            # note 가 그대로 보고서의 한계 문장이 된다
        assert st.recheck_count == 2        # 잡 전체 재검색 횟수 — 탐색 경로에 실린다

    def test_no_hits_records_no_evidence(self):
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        sq = SubQuestion(idx=0, text="하위질문")
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_empty_explore,
            critique_fn=_FakeCritic(), emit=None,
        ))
        assert sq.evidence_ids == []

    def test_same_paper_in_two_subquestions_reuses_one_evidence(self):
        """한 논문이 두 하위질문에서 나와도 근거는 하나다.

        중복 생성하면 같은 출처가 E1 과 E2 로 갈라져 인용칩이 어긋난다.
        """
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        sq1, sq2 = SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(st, sq1, db=None, explore_fn=_fake_explore,
                                        critique_fn=critic, emit=None))
        asyncio.run(explore_subquestion(st, sq2, db=None, explore_fn=_fake_explore,
                                        critique_fn=critic, emit=None))
        assert len(st.evidence) == 1
        assert sq1.evidence_ids == sq2.evidence_ids == ["E1"]
        assert len({ev.cnts_id for ev in st.evidence.values()}) == 1

    def test_recheck_does_not_duplicate_same_paper(self):
        """재검색에서 같은 논문이 또 나와도 evidence_ids 에 두 번 들어가지 않는다."""
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="가")
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_fake_explore,
                                        critique_fn=_FakeCritic(), emit=None))
        assert sq.evidence_ids == ["E1"]

    def test_max_evidence_caps_growth(self):
        async def _many(query, *, params, db):
            return _hits([f"B{i}" for i in range(10)], query=query)

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 0, "max_evidence": 4}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=None,
            explore_fn=_many, critique_fn=_FakeCritic(), emit=None,
        ))
        assert len(st.evidence) == 4

    def test_cap_reached_still_links_already_adopted_paper(self):
        """상한에 닿은 뒤 나온 후보도 '이미 있는 근거'면 링크는 붙는다.

        상한 검사를 break 로 끊으면 그 뒤 후보를 아예 보지 못하고 지나가서,
        다른 하위질문에서 이미 채택된 논문인데도 이 하위질문만 링크를 잃는다.
        재사용은 총량을 늘리지 않으므로 상한과 무관한 손실이다.
        """
        by_query = {"가": ["A"], "나": ["B", "C", "A"]}

        async def _by_query(query, *, params, db):
            return _hits(by_query[query], query=query)

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 0, "max_evidence": 2}))
        sq1, sq2 = SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(st, sq1, db=None, explore_fn=_by_query,
                                        critique_fn=critic, emit=None))
        asyncio.run(explore_subquestion(st, sq2, db=None, explore_fn=_by_query,
                                        critique_fn=critic, emit=None))
        assert sq1.evidence_ids == ["E1"]
        assert sq2.evidence_ids == ["E2", "E1"]     # B 는 새로, C 는 상한에 막히고, A 는 재사용
        assert len(st.evidence) == 2

    def test_parse_failed_verdict_propagates_to_subquestion(self):
        """판정 파싱 실패 표시가 하위질문까지 올라와야 한다.

        `synthesizer.build_limitations` 는 `sq.parse_failed` 만 본다. 여기서
        옮기지 않으면 자기점검이 전부 실패해도 보고서가 "한계 없음"이 된다.
        """
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="가")
        critic = _ParseFailedCritic()
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_fake_explore,
                                        critique_fn=critic, emit=None))
        assert sq.parse_failed is True
        # 파싱 실패는 verdict="sufficient" 로 떨어지므로 루프가 한 바퀴에 끝난다 —
        # 그래서 마지막 라운드의 값만 옮겨도 표시가 유실되지 않는다.
        assert critic.calls == 1

    def test_emit_is_called_for_progress(self):
        events = []

        async def _emit(kind, payload):
            events.append((kind, payload))

        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=None, explore_fn=_fake_explore,
            critique_fn=_FakeCritic(), emit=_emit,
        ))
        kinds = [k for k, _ in events]
        assert "search" in kinds and "critique" in kinds
        by_kind = dict(events)
        assert by_kind["search"] == {"subq_idx": 0, "query": "가", "found": 1}
        assert by_kind["critique"]["verdict"] == "insufficient"
        assert by_kind["critique"]["adopted"] == 1


def _load_relay(monkeypatch):
    """`redis` 미설치 환경에서만 더미를 꽂아 relay import 를 통과시킨다.

    더미를 물린 relay 가 sys.modules 에 남으면 뒤에 도는 테스트가 Mock 을
    물려받으므로 monkeypatch.delitem 으로 지워 둔다
    (`test_embed_index_guard.py` 와 같은 방식).
    """
    for name in ("redis", "redis.asyncio"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    monkeypatch.delitem(sys.modules, "services.research.relay", raising=False)
    return importlib.import_module("services.research.relay")


class _FakeRedis:
    def __init__(self, publish_error=None):
        self.published = []
        self.closed = False
        self._publish_error = publish_error

    async def publish(self, channel, data):
        if self._publish_error is not None:
            raise self._publish_error
        self.published.append((channel, data))

    async def aclose(self):
        self.closed = True


class TestRelayPublish:
    def test_publishes_kind_and_payload_to_job_channel(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        client = _FakeRedis()
        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: client)

        asyncio.run(relay.publish("job-1", "search", {"subq_idx": 0, "query": "한글"}))

        channel, data = client.published[0]
        assert channel == "research:job-1"
        assert json.loads(data) == {"kind": "search", "subq_idx": 0, "query": "한글"}
        assert "한글" in data              # ensure_ascii=False — 로그·SSE 에서 읽혀야 한다
        assert client.closed is True

    def test_publish_error_is_swallowed_and_client_closed(self, monkeypatch):
        """중계는 장식이고 보고서는 아니다 — publish 실패가 잡을 죽이면 안 된다."""
        relay = _load_relay(monkeypatch)
        client = _FakeRedis(publish_error=RuntimeError("연결 끊김"))
        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: client)

        assert asyncio.run(relay.publish("job-1", "search", {})) is None
        assert client.closed is True

    def test_connect_error_is_swallowed(self, monkeypatch):
        relay = _load_relay(monkeypatch)

        def _boom(url):
            raise OSError("redis 없음")

        monkeypatch.setattr(relay.aioredis, "from_url", _boom)
        assert asyncio.run(relay.publish("job-1", "done", {})) is None
