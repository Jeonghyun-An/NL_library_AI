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
import types
from unittest.mock import MagicMock

import pytest

from services.research.critic import Verdict
from services.research.runner import explore_subquestion
from services.research.state import ResearchState, SubQuestion, merge_params


class _FakeCritic:
    """항상 부족을 반환하는 critic — 루프 상한을 검증한다. 제안은 매번 새 검색어다."""

    def __init__(self):
        self.calls = 0
        self.seen: list[list] = []

    async def __call__(self, subq, evidence, *, params):
        self.calls += 1
        self.seen.append(evidence)
        return Verdict("insufficient", note="부족", new_queries=[f"다른 검색어 {self.calls}"])


class _SuggestingCritic:
    """정해진 제안 목록을 매번 그대로 내는 critic — 중복 제안 처리를 검증한다."""

    def __init__(self, suggestions):
        self.calls = 0
        self._suggestions = suggestions

    async def __call__(self, subq, evidence, *, params):
        self.calls += 1
        return Verdict("insufficient", note="부족", new_queries=list(self._suggestions))


class _FakeDb:
    """runner 가 읽기 트랜잭션을 언제 닫는지만 기록한다."""

    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


class _ParseFailedCritic:
    """판정을 못 읽은 critic — `critic._failed()` 가 내는 형태 그대로다."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, subq, evidence, *, params):
        self.calls += 1
        return Verdict("sufficient", note="자동 점검을 완료하지 못했다", parse_failed=True)


def _hits(cnts_ids, *, query="q", scores=None):
    scores = scores or [0.9] * len(cnts_ids)
    hits = [
        {"book_id": cid, "chunk_id": f"{cid}-c-{query}", "text": f"{cid} 의 '{query}' 대목",
         "page_start": 1, "page_end": 1, "score": s, "rank_score": s}
        for cid, s in zip(cnts_ids, scores)
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
        assert sq.queries == ["하위질문", "다른 검색어 1", "다른 검색어 2"]
        assert sq.verdict == "insufficient"
        assert sq.note == "부족"            # note 가 그대로 보고서의 한계 문장이 된다

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

    def test_critique_event_carries_unchecked_and_capped_flags(self):
        """'모델이 충분하다고 판단'과 '판정을 못 받음'을 note 문자열 없이 가를 수 있어야 한다."""
        events = []

        async def _emit(kind, payload):
            events.append((kind, payload))

        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=None, explore_fn=_fake_explore,
            critique_fn=_ParseFailedCritic(), emit=_emit,
        ))
        critique = dict(events)["critique"]
        assert critique["parse_failed"] is True
        assert critique["capped"] == 0


class TestReadTransaction:
    def test_read_transaction_is_closed_before_critic_waits_on_llm(self):
        """워커 세션이 LLM 대기 내내 library_catalog 공유 잠금을 쥐면, FastAPI
        기동 시 ALTER TABLE library_catalog 가 막히고 그 뒤 모든 조회가 줄 선다."""
        db = _FakeDb()
        commits_at_critic = []

        async def _critic(subq, evidence, *, params):
            commits_at_critic.append(db.commits)
            return Verdict("sufficient", note="충분")

        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=db, explore_fn=_fake_explore,
            critique_fn=_critic, emit=None,
        ))
        assert commits_at_critic == [1]


class TestRequery:
    def test_already_tried_suggestion_is_skipped_for_the_next_one(self):
        """첫 제안이 이미 시도한 검색어면 같은 검색이 한 번 더 돌고 두 번째 제안은 버려진다."""
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 1}))
        sq = SubQuestion(idx=0, text="공공도서관 서비스 품질")
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_fake_explore,
            critique_fn=_SuggestingCritic(["공공도서관  서비스 품질", "LibQUAL+ 적용 사례"]),
            emit=None,
        ))
        assert sq.queries == ["공공도서관 서비스 품질", "LibQUAL+ 적용 사례"]

    def test_loop_stops_when_every_suggestion_was_tried(self):
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 3}))
        sq = SubQuestion(idx=0, text="AI 윤리")
        critic = _SuggestingCritic(["ai 윤리", " AI  윤리 "])
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_fake_explore, critique_fn=critic, emit=None,
        ))
        assert sq.queries == ["AI 윤리"]
        assert critic.calls == 1


class TestEvidenceOrder:
    """evidence_ids 는 critic(20편)과 절(5편)이 앞에서 자른다 — 순서가 곧 선택이다."""

    def _run(self, rounds, *, max_recheck):
        async def _explore(query, *, params, db):
            ids, scores = rounds[query]
            return _hits(ids, query=query, scores=scores)

        class _Critic:
            def __init__(self):
                self.calls = 0

            async def __call__(self, subq, evidence, *, params):
                self.calls += 1
                return Verdict("insufficient", note="시기 편중",
                               new_queries=[f"r{self.calls + 1}"])

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": max_recheck}))
        sq = SubQuestion(idx=0, text="r1")
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_explore,
                                        critique_fn=_Critic(), emit=None))
        return st, sq

    def _cnts(self, st, ids):
        return [st.evidence[e].cnts_id for e in ids]

    def test_best_new_paper_of_each_research_round_gets_a_front_seat(self):
        """점수만으로 자르면 자기점검이 부족하다고 해서 찾은 보완 논문이 절에서 빠진다.

        라운드마다 검색어가 달라 점수를 그대로 비교할 수도 없다.
        """
        rounds = {
            "r1": (["A", "B", "C", "D", "E", "F"], [0.95, 0.94, 0.93, 0.92, 0.91, 0.90]),
            "r2": (["G"], [0.40]),
        }
        st, sq = self._run(rounds, max_recheck=1)
        assert "G" in self._cnts(st, sq.evidence_ids[:5])
        assert self._cnts(st, sq.evidence_ids[:2]) == ["A", "G"]

    def test_rest_is_ordered_by_score_across_rounds(self):
        rounds = {
            "r1": (["A", "B", "C"], [0.50, 0.30, 0.20]),
            "r2": (["D", "E", "F"], [0.90, 0.80, 0.70]),
        }
        st, sq = self._run(rounds, max_recheck=1)
        assert self._cnts(st, sq.evidence_ids) == ["A", "D", "E", "F", "B", "C"]

    def test_round_leader_skips_papers_already_linked(self):
        # 2라운드 1위가 1라운드에서 이미 채택한 논문이면, 2라운드가 새로 보탠 것 중 1위가 자리를 받는다
        rounds = {
            "r1": (["A", "B", "C"], [0.9, 0.8, 0.7]),
            "r2": (["A", "D"], [0.95, 0.3]),
        }
        st, sq = self._run(rounds, max_recheck=1)
        assert self._cnts(st, sq.evidence_ids[:2]) == ["A", "D"]

    def test_critic_sees_ranked_order(self):
        rounds = {
            "r1": (["A", "B"], [0.5, 0.2]),
            "r2": (["C", "D"], [0.9, 0.8]),
        }

        async def _explore(query, *, params, db):
            ids, scores = rounds[query]
            return _hits(ids, query=query, scores=scores)

        critic = _FakeCritic()
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 1}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="r1"), db=None, explore_fn=_explore,
            critique_fn=_CriticWithQueries(critic, ["r2"]), emit=None,
        ))
        assert [e.cnts_id for e in critic.seen[-1]] == ["A", "C", "D", "B"]


class _CriticWithQueries:
    """_FakeCritic 의 기록은 그대로 두고 제안 검색어만 정해 준다."""

    def __init__(self, inner, queries):
        self._inner = inner
        self._queries = list(queries)

    async def __call__(self, subq, evidence, *, params):
        await self._inner(subq, evidence, params=params)
        q = self._queries.pop(0) if self._queries else "다른 검색어"
        return Verdict("insufficient", note="부족", new_queries=[q])


class TestSubquestionChunks:
    def test_reused_paper_uses_the_chunk_matched_in_this_subquestion(self):
        """재사용 근거의 발췌가 첫 하위질문 대목으로 고정되면, 다른 하위질문의
        critic 판정과 절 요약이 그 하위질문과 무관한 대목으로 만들어진다."""
        async def _explore(query, *, params, db):
            return _hits(["P"], query=query)

        critic = _FakeCritic()
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        sq1, sq2 = SubQuestion(idx=0, text="품질 측정"), SubQuestion(idx=1, text="만족도")
        asyncio.run(explore_subquestion(st, sq1, db=None, explore_fn=_explore,
                                        critique_fn=critic, emit=None))
        asyncio.run(explore_subquestion(st, sq2, db=None, explore_fn=_explore,
                                        critique_fn=critic, emit=None))

        assert list(st.evidence) == ["E1"]
        assert sq1.evidence_chunks == {"E1": ["P-c-품질 측정"]}
        assert sq2.evidence_chunks == {"E1": ["P-c-만족도"]}
        assert {c.chunk_id for c in st.evidence["E1"].chunks} == {"P-c-품질 측정", "P-c-만족도"}
        assert critic.seen[1][0].chunks[0].text == "P 의 '만족도' 대목"

    def test_better_chunk_in_later_round_replaces_within_subquestion(self):
        by_query = {"가": 0.3, "다른 검색어 1": 0.9}

        async def _explore(query, *, params, db):
            return _hits(["P"], query=query, scores=[by_query[query]])

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 1, "chunks_per_evidence": 1}))
        sq = SubQuestion(idx=0, text="가")
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_explore,
                                        critique_fn=_FakeCritic(), emit=None))
        assert sq.evidence_chunks == {"E1": ["P-c-다른 검색어 1"]}


class TestEvidenceCap:
    def _by_query(self, table):
        async def _explore(query, *, params, db):
            return _hits(table.get(query, []), query=query)
        return _explore

    def test_candidates_blocked_by_cap_are_counted(self):
        """상한에 막힌 것을 기록하지 않으면 보고서가 '근거를 찾지 못했다'(코퍼스 빈틈)로 쓴다."""
        explore = self._by_query({"가": ["A"], "나": ["B", "C", "A"]})
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 0, "max_evidence": 1}))
        sq1, sq2 = SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(st, sq1, db=None, explore_fn=explore,
                                        critique_fn=critic, emit=None))
        asyncio.run(explore_subquestion(st, sq2, db=None, explore_fn=explore,
                                        critique_fn=critic, emit=None))
        assert sq1.capped == 0
        assert sq2.capped == 2
        assert sq2.evidence_ids == ["E1"]

    def test_starved_subquestion_is_reported_as_capped_not_missing(self):
        from services.research.synthesizer import build_limitations

        explore = self._by_query({"가": ["A"], "나": ["B", "C"]})
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2, "max_evidence": 1}))
        st.subquestions = [SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")]
        critic = _FakeCritic()
        for sq in st.subquestions:
            asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=explore,
                                            critique_fn=critic, emit=None))
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "'나'" in x)
        assert "근거 상한(1편)" in line and "근거를 찾지 못했다" not in line
        assert critic.calls == 2                # 상한 뒤로는 어느 하위질문도 재검색하지 않는다

    def test_research_stops_once_cap_is_reached(self):
        """상한에 닿으면 새 근거가 생길 수 없다 — 재검색은 검색·LLM 호출만 태운다."""
        async def _many(query, *, params, db):
            return _hits([f"{query}-{i}" for i in range(3)], query=query)

        critic = _FakeCritic()
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 3, "max_evidence": 2}))
        sq = SubQuestion(idx=0, text="가")
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_many,
                                        critique_fn=critic, emit=None))
        assert critic.calls == 1
        assert sq.queries == ["가"]
        assert sq.capped == 1


_RELAY = "services.research.relay"


def _forget_on_teardown(monkeypatch, name: str) -> None:
    """name 을 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 원래 있던 키만 되돌린다. 원래 없던 키는 기록이 남지 않아
    여기서 새로 import 한 모듈(더미 redis 에 묶인 채)이 teardown 뒤에도 남는다.
    setitem·setattr 은 원래 없던 키·속성이면 되돌릴 때 지우므로, 값을 한 번 꽂아 기록을
    남긴 뒤 뺀다. 부모 속성까지 되돌리는 이유: `from pkg import mod` 와 문자열 경로
    monkeypatch 는 sys.modules 보다 부모 속성을 먼저 본다.
    """
    parent, _, child = name.rpartition(".")
    monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
    monkeypatch.setitem(sys.modules, name, None)
    del sys.modules[name]


def _load_relay(monkeypatch):
    """`redis` 미설치 환경에서만 더미를 꽂아 relay 를 새로 import 한다. 앞 테스트가 남긴
    relay 를 물려받지 않고, 끝나면 import 전 그대로 되돌린다(_forget_on_teardown)."""
    for name in ("redis", "redis.asyncio"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    _forget_on_teardown(monkeypatch, _RELAY)
    return importlib.import_module(_RELAY)


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


class TestRelayLoaderIsolation:
    """_load_relay 가 끝나면 sys.modules·부모 패키지 속성이 import 전 그대로여야 한다 —
    더미 redis 에 묶인 relay 가 남으면 뒤에 도는 테스트가 그것을 물려받는다."""

    def test_module_that_was_absent_is_gone_afterwards(self):
        parent = importlib.import_module("services.research")
        with pytest.MonkeyPatch.context() as outer:
            outer.delitem(sys.modules, _RELAY, raising=False)
            outer.delattr(parent, "relay", raising=False)
            with pytest.MonkeyPatch.context() as mp:
                _load_relay(mp)
            assert _RELAY not in sys.modules
            assert not hasattr(parent, "relay")

    def test_module_that_was_loaded_comes_back(self):
        parent = importlib.import_module("services.research")
        original = types.ModuleType(_RELAY)
        with pytest.MonkeyPatch.context() as outer:
            outer.setitem(sys.modules, _RELAY, original)
            outer.setattr(parent, "relay", original, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                assert _load_relay(mp) is not original
            assert sys.modules[_RELAY] is original
            assert parent.relay is original


class TestSharedChunkScore:
    """두 하위질문이 같은 청크를 매칭하면, 뒤 하위질문의 재검색은 그 청크를 자기 점수로 비교한다."""

    def test_research_does_not_swap_out_a_better_passage(self):
        table = {"A": [("P-c1", 0.2)], "B": [("P-c1", 0.95)], "B2": [("P-c2", 0.5)]}

        async def _explore(query, *, params, db):
            hits = [{"book_id": "P", "chunk_id": cid, "text": cid, "page_start": 1,
                     "page_end": 1, "score": s, "rank_score": s} for cid, s in table[query]]
            return hits, {"P": {"title": "P"}}

        class _Once:
            def __init__(self, new_queries):
                self.calls = 0
                self._new = new_queries

            async def __call__(self, subq, evidence, *, params):
                self.calls += 1
                if self.calls == 1 and self._new:
                    return Verdict("insufficient", note="부족", new_queries=self._new)
                return Verdict("sufficient")

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 1, "chunks_per_evidence": 1}))
        a, b = SubQuestion(idx=0, text="A"), SubQuestion(idx=1, text="B")
        st.subquestions = [a, b]
        asyncio.run(explore_subquestion(st, a, db=None, explore_fn=_explore,
                                        critique_fn=_Once([]), emit=None))
        asyncio.run(explore_subquestion(st, b, db=None, explore_fn=_explore,
                                        critique_fn=_Once(["B2"]), emit=None))

        assert b.evidence_chunks == {"E1": ["P-c1"]}
        assert b.chunk_scores == {"P-c1": 0.95}
        assert a.chunk_scores == {"P-c1": 0.2}
