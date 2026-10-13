"""scripts/eval_brochure_search.py — BM25·지표·통계·판정 파싱·리포트, 그리고 가짜 백엔드로 전 구간 흐름."""
import asyncio
import logging
import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts import eval_brochure_search as ev


# ── BM25 ─────────────────────────────────────────────────────
def test_tokenize_makes_in_word_bigrams():
    assert ev.tokenize("지방재정에") == ["지방", "방재", "재정", "정에"]
    assert ev.tokenize("AI 가") == ["ai", "가"]


def test_bm25_ranks_matching_doc_first():
    idx = ev.BM25Index(
        ["a", "b", "c"],
        ["저출산 고령화가 지방재정에 미치는 영향", "기후변화와 농업 생산성", "인공지능 윤리 가이드라인"],
    )
    assert idx.search("지방재정 영향", 3)[0][0] == "a"
    assert idx.search("농업 생산성", 3)[0][0] == "b"


def test_bm25_unknown_terms_return_empty():
    idx = ev.BM25Index(["a"], ["저출산 연구"])
    assert idx.search("zzzzqq", 5) == []


def test_bm25_is_robust_to_particles():
    idx = ev.BM25Index(["a", "b"], ["연구를 수행한 결과", "전혀 다른 주제의 글"])
    assert idx.search("연구", 2)[0][0] == "a"


# ── 지표 ─────────────────────────────────────────────────────
def test_rank_and_metrics():
    assert ev.rank_of(["x", "y", "z"], "y") == 2
    assert ev.rank_of(["x"], "q") is None
    assert ev.recall_at(3, 10) == 1.0 and ev.recall_at(11, 10) == 0.0 and ev.recall_at(None, 10) == 0.0
    assert ev.reciprocal_rank(4) == 0.25 and ev.reciprocal_rank(None) == 0.0
    assert ev.ndcg_at(1) == 1.0
    assert ev.ndcg_at(3) == pytest.approx(0.5)
    assert ev.ndcg_at(11) == 0.0


def test_bootstrap_ci_is_deterministic_and_brackets_mean():
    v = [1, 0, 1, 1, 0, 1, 0, 1, 1, 1]
    ci = ev.bootstrap_ci(v, seed=1)
    assert ci == ev.bootstrap_ci(v, seed=1)
    assert ci[0] <= np.mean(v) <= ci[1]
    assert ev.bootstrap_ci([]) is None


def test_sign_test_and_kappa():
    assert ev.sign_test_p(0, 0) == 1.0
    assert ev.sign_test_p(5, 5) == 1.0
    assert ev.sign_test_p(0, 12) < 0.001
    assert ev.cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == pytest.approx(1.0)
    assert ev.cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == pytest.approx(0.0)
    assert ev.cohen_kappa([], []) is None


# ── 질문 합성 · 판정 파싱 ────────────────────────────────────
def test_clean_question():
    assert ev.clean_question('질문: "지방 재정이 어려워지는 이유가 뭐예요?"\n설명') == "지방 재정이 어려워지는 이유가 뭐예요?"
    assert ev.clean_question("") == ""


def test_shares_substring_ignores_spacing_and_punctuation():
    assert ev.shares_substring("저출산·고령화가 지방 재정에", "저출산 고령화가 지방재정에 미치는 영향", 6)
    assert not ev.shares_substring("아이 적게 낳는 현상", "저출산 고령화가 지방재정에 미치는 영향", 6)


def test_reject_reason():
    row = {"title": "저출산 고령화가 지방재정에 미치는 영향", "body": "본 연구는 지방자치단체의 재정 건전성을 분석한다. " * 5}
    assert ev.reject_reason("", row) == "empty"
    assert ev.reject_reason("짧음", row) == "length"
    assert ev.reject_reason("저출산 고령화가 지방재정에 미치는 영향이 궁금해요", row) == "title_copy"
    assert ev.reject_reason("본 연구는 지방자치단체의 재정 건전성을 분석한다 알려줘", row) == "body_copy"
    assert ev.reject_reason("아이를 적게 낳으면 시골 살림이 어떻게 되나요?", row) is None


def test_parse_judgment():
    ok = ev.parse_judgment('생각: ...\n{"reason":"직접 다룸","on_topic":1,"score":0.9}')
    assert ok == {"on_topic": 1, "score": 0.9, "reason": "직접 다룸"}
    assert ev.parse_judgment('{"on_topic":2,"score":0.9}') is None
    assert ev.parse_judgment('{"on_topic":1,"score":1.7}') is None
    assert ev.parse_judgment("판정 불가") is None
    last = ev.parse_judgment('{"on_topic":0,"score":0.2} 수정: {"on_topic":1,"score":0.8}')
    assert last["on_topic"] == 1


def test_is_on_topic_needs_both_binary_and_score():
    assert ev.is_on_topic({"on_topic": 1, "score": 0.5})
    assert not ev.is_on_topic({"on_topic": 1, "score": 0.49})
    assert not ev.is_on_topic({"on_topic": 0, "score": 0.9})


def test_judge_prompt_contains_guards():
    assert "키워드 일치는 주제 일치가 아닙니다" in ev._JUDGE_SYS
    assert "primarily about" in ev._JUDGE_SYS
    assert ev._JUDGE_SYS.count('"on_topic"') >= 4  # few-shot 예시(근거 포함)
    p = ev.judge_user_prompt("질의", {"title": "T", "keyword": "k", "body": "x" * 2000})
    assert len(p) < 900


# ── 집계 ─────────────────────────────────────────────────────
def _synthetic():
    queries = [{"qid": f"q{i}", "qtype": "nl", "scope": "paper", "query": "q", "expected_id": f"d{i}",
                "lex_coverage": i / 40} for i in range(40)]
    runs, judgments = {}, {}
    for i, q in enumerate(queries):
        sk = [f"d{i}"] + [f"x{j}" for j in range(9)]                     # SKOVIX: 항상 1위
        bm = [f"x{j}" for j in range(9)] + [f"d{i}"] if i % 2 else [f"x{j}" for j in range(10)]  # BM25: 절반만 10위
        runs[q["qid"]] = {"bm25_meta": {"ids": bm, "ms": 1.0}, "skovix_full": {"ids": sk, "ms": 100.0 + i}}
        for d in sk + bm:
            judgments[ev.pair_key(q["qid"], d)] = {"on_topic": 1 if d == f"d{i}" else 0, "score": 0.9, "reason": ""}
    return queries, runs, judgments


def test_summarize_group_and_deltas():
    queries, runs, judgments = _synthetic()
    g = ev.summarize_group(queries, runs, judgments, seed=0)
    assert g["arms"]["skovix_full"]["r1"]["mean"] == 1.0
    assert g["arms"]["bm25_meta"]["r1"]["mean"] == 0.0
    assert g["arms"]["bm25_meta"]["r10"]["mean"] == 0.5
    d = g["deltas"]["skovix_full"]
    assert d["r10"]["mean"] == pytest.approx(0.5)
    assert d["r10_only_arm"] == 20 and d["r10_only_baseline"] == 0
    assert d["r10_sign_p"] < 0.001
    assert g["arms"]["skovix_full"]["otr"]["mean"] == pytest.approx(0.1)
    assert g["arms"]["skovix_full"]["latency_p50_ms"] is not None


def test_otr_counts_missing_pairs_instead_of_dropping_silently():
    j = {"q|a": {"on_topic": 1, "score": 0.9}, "q|b": {"failed": True, "tail": "x"}}
    val, judged, missing = ev._query_otr("q", ["a", "b", "c"], j)
    assert (val, judged, missing) == (1.0, 1, 2)


def test_build_report_adds_low_coverage_stratum():
    queries, runs, judgments = _synthetic()
    rep = ev.build_report(queries, runs, judgments)
    assert "paper|nl" in rep and "paper|nl_low_coverage" in rep
    assert rep["paper|nl_low_coverage"]["n"] < rep["paper|nl"]["n"]


def test_markdown_carries_claim_guards():
    queries, runs, judgments = _synthetic()
    md = ev.render_markdown(ev.build_report(queries, runs, judgments), {"created": "2026-10-13"}, {"judges": "vlm"})
    assert "실사용자 질의가 아니며" in md
    assert "자연어 검색 정확도로 표기하지 않는다" in md
    assert "하한" in md and "측정하지 않았다" in md


# ── 가짜 백엔드로 전 구간 ────────────────────────────────────
class FakeBackend:
    TOPICS = ["저출산", "기후변화", "인공지능", "고령화", "미세먼지", "청년실업", "부동산", "교육격차",
              "반도체", "재생에너지", "공공의료", "난민정책", "해양오염", "전자상거래", "문화유산", "도시재생"]

    def __init__(self):
        self.docs = [
            {"cnts_id": f"KCI_FI{i:03d}", "title": f"연구 {t} 사례 {i}", "keyword": f"{t}, 정책",
             "body": (f"{t}에 관한 사회 전반의 쟁점과 제도 변화를 폭넓게 검토하고 정책 대안을 제시한다. " * 6)}
            for i, t in enumerate(self.TOPICS)
        ]
        self.calls = {"gen": 0, "vlm": 0}

    async def model_label(self, role):
        return "fake-" + role + " (서빙 모델: fake-" + role + "-30b)"

    async def close(self):
        pass

    async def count_docs(self, scope):
        return len(self.docs)

    async def sample_docs(self, scope, n, seed):
        return self.docs[:n]

    async def catalog(self, scope):
        return self.docs

    async def doc_infos(self, ids):
        return {d["cnts_id"]: d for d in self.docs if d["cnts_id"] in ids}

    async def search(self, arm, query, scope):
        scored = sorted(self.docs, key=lambda d: -sum(w in (d["title"] + d["body"]) for w in query.split()))
        return {"ids": [d["cnts_id"] for d in scored][:10], "ms": 5.0, "rewritten": query}

    async def chat(self, role, messages, *, max_tokens, temperature):
        self.calls[role] += 1
        user = messages[-1]["content"]
        if role == "gen":
            topic = next(t for t in self.TOPICS if t in user)
            # 첫 문서는 제목을 그대로 베끼게 해 탈락 경로를 확인한다
            if topic == self.TOPICS[0]:
                return f"연구 {topic} 사례 0 알려줘요"
            return f"{topic} 때문에 생기는 변화가 어떤지 알고 싶어요 어디서 찾죠"
        q = user.split("[검색어] ")[1].split("\n")[0]
        doc = user.split("[문서]")[1]
        topic = next(t for t in self.TOPICS if t in q)
        on = topic in doc
        return json.dumps({"reason": "fake", "on_topic": int(on), "score": 0.9 if on else 0.1}, ensure_ascii=False)


def _args(parser, *argv, workdir):
    return parser.parse_args(["--workdir", str(workdir), *argv])


def test_full_flow_with_fake_backend(tmp_path):
    be, parser = FakeBackend(), ev.make_parser()

    meta = asyncio.run(ev.stage_build(_args(parser, "build", "--n-papers", "8", "--n-books", "0", workdir=tmp_path), be, tmp_path))
    assert meta["n_queries"] == 8
    assert meta["dropped"].get("title_copy") == 1          # 제목을 베낀 질문은 탈락
    qs = json.loads((tmp_path / "queries.json").read_text(encoding="utf-8"))["queries"]
    assert all("lex_coverage" in q for q in qs)

    asyncio.run(ev.stage_run(_args(parser, "run", "--arms", "bm25_meta,skovix_full", workdir=tmp_path), be, tmp_path))
    runs = json.loads((tmp_path / "runs.json").read_text(encoding="utf-8"))
    assert set(runs[qs[0]["qid"]]) == {"bm25_meta", "skovix_full"}

    asyncio.run(ev.stage_judge(_args(parser, "judge", "--judge", "vlm", workdir=tmp_path), be, tmp_path))
    first_calls = be.calls["vlm"]
    assert first_calls > 0
    asyncio.run(ev.stage_judge(_args(parser, "judge", "--judge", "vlm", workdir=tmp_path), be, tmp_path))
    assert be.calls["vlm"] == first_calls                  # 두 번째는 캐시로 건너뜀(재개 가능)

    ev.stage_report(_args(parser, "report", workdir=tmp_path), tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    g = summary["groups"]["paper|nl"]
    assert g["arms"]["bm25_meta"]["r10"]["mean"] == 1.0    # 어휘가 겹치는 합성 코퍼스라 기준선도 찾는다
    assert g["arms"]["bm25_meta"]["otr"]["judged_pairs"] > 0
    assert "paper|nl_low_coverage" not in summary["groups"]  # 표본이 20 미만이면 층화하지 않음
    assert (tmp_path / "brochure_table.md").read_text(encoding="utf-8").startswith("# 브로셔용")


def test_review_sheet_and_agreement(tmp_path):
    be, parser = FakeBackend(), ev.make_parser()
    asyncio.run(ev.stage_build(_args(parser, "build", "--n-papers", "8", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_run(_args(parser, "run", "--arms", "bm25_meta", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_judge(_args(parser, "judge", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_review_sheet(_args(parser, "review-sheet", "--n", "10", workdir=tmp_path), be, tmp_path))

    sheet = tmp_path / "review_sheet.csv"
    key = json.loads((tmp_path / "review_key.json").read_text(encoding="utf-8"))
    assert "llm" not in sheet.read_text(encoding="utf-8-sig").lower()    # LLM 판정은 가려져 있다
    import csv
    rows = list(csv.reader(sheet.open(encoding="utf-8-sig", newline="")))
    for r in rows[1:]:
        r[5] = str(key[r[0]]["llm"])                                       # 사람이 LLM 과 전부 같게 답한 경우
    with sheet.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)

    ev.stage_agreement(_args(parser, "agreement", "--sheet", str(sheet), workdir=tmp_path), tmp_path)
    res = json.loads((tmp_path / "human_agreement.json").read_text(encoding="utf-8"))
    assert res["agreement"] == 1.0 and res["n"] == len(rows) - 1


def test_run_rejects_unknown_arm(tmp_path):
    be, parser = FakeBackend(), ev.make_parser()
    asyncio.run(ev.stage_build(_args(parser, "build", "--n-papers", "3", workdir=tmp_path), be, tmp_path))
    with pytest.raises(SystemExit):
        asyncio.run(ev.stage_run(_args(parser, "run", "--arms", "nope", workdir=tmp_path), be, tmp_path))


# ── 판정 실패 경로: 조용히 0 으로 세면 안 되고, 결측으로 남겨 보고해야 한다 ──
class FlakyJudgeBackend(FakeBackend):
    """한 문서는 판정 모델이 끝까지 JSON 을 못 내고, 다른 문서는 첫 시도만 실패한다."""

    def __init__(self):
        super().__init__()
        self.seen: dict[str, int] = {}

    async def chat(self, role, messages, *, max_tokens, temperature):
        if role == "vlm":
            doc = messages[-1]["content"].split("[문서]")[1]
            if self.docs[1]["title"] in doc:
                return "판정할 수 없습니다"                     # 영구 실패
            if self.docs[2]["title"] in doc:
                q = messages[-1]["content"].split("[검색어] ")[1].split("\n")[0]
                self.seen[q] = self.seen.get(q, 0) + 1
                if self.seen[q] == 1:
                    return "음… 잠시만요"                       # 첫 시도만 실패 → 재시도로 복구돼야 함
        return await super().chat(role, messages, max_tokens=max_tokens, temperature=temperature)


def test_judge_failures_are_recorded_as_missing_not_zero(tmp_path):
    be, parser = FlakyJudgeBackend(), ev.make_parser()
    asyncio.run(ev.stage_build(_args(parser, "build", "--n-papers", "8", "--n-books", "0", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_run(_args(parser, "run", "--arms", "bm25_meta", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_judge(_args(parser, "judge", workdir=tmp_path), be, tmp_path))

    j = json.loads((tmp_path / "judgments_vlm.json").read_text(encoding="utf-8"))
    failed = [k for k, v in j.items() if v.get("failed")]
    assert failed and all(k.endswith(be.docs[1]["cnts_id"]) for k in failed)       # 영구 실패만 failed
    recovered = [v for k, v in j.items() if k.endswith(be.docs[2]["cnts_id"])]
    assert recovered and not any(v.get("failed") for v in recovered)               # 첫 시도 실패는 재시도로 복구

    ev.stage_report(_args(parser, "report", workdir=tmp_path), tmp_path)
    otr = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["groups"]["paper|nl"]["arms"]["bm25_meta"]["otr"]
    assert otr["missing_pairs"] == len(failed)
    assert otr["judged_pairs"] + otr["missing_pairs"] == sum(
        len(v["bm25_meta"]["ids"][:10]) for v in json.loads((tmp_path / "runs.json").read_text(encoding="utf-8")).values())


# ── 서빙 모델 표기 · 로그 캡처 · 단계별 기여 · audit ───────────
def test_label_from_models_reports_real_model_behind_alias():
    data = [{"id": "qwen3-vl-8b", "root": "Qwen/Qwen3-VL-30B-A3B-Instruct-FP8"}]
    assert ev.label_from_models(data, "qwen3-vl-8b") == "qwen3-vl-8b (서빙 모델: Qwen/Qwen3-VL-30B-A3B-Instruct-FP8)"
    assert ev.label_from_models([{"id": "gemma-3-12b", "root": "gemma-3-12b"}], "gemma-3-12b") == "gemma-3-12b"
    assert ev.label_from_models([{"id": "other"}], "gemma-3-12b") == "gemma-3-12b"
    assert ev.label_from_models([], "x") == "x"


def test_capture_logs_collects_child_logger_messages_and_restores_level():
    parent = logging.getLogger("services.search")
    before = parent.level
    with ev.capture_logs() as logs:
        logging.getLogger("services.search.pipeline").info("쿼리 재작성: 'a' → 'b'")
        logging.getLogger("services.search.metadata_filter").warning("메타데이터 필터 추출 실패: x")
        logging.getLogger("other.module").info("무관")
    assert logs == ["쿼리 재작성: 'a' → 'b'", "메타데이터 필터 추출 실패: x"]
    assert parent.level == before and not parent.handlers


def test_arm_flags_cover_all_skovix_arms_and_only_full_uses_filter():
    assert set(ev._ARM_FLAGS) == {a for a in ev.ARMS if a != ev.BASELINE}
    assert [a for a, (_, _, mf) in ev._ARM_FLAGS.items() if mf] == ["skovix_full"]
    assert [a for a, (rw, _, _) in ev._ARM_FLAGS.items() if rw] == ["skovix_rewrite", "skovix_full"]


def _ladder_runs():
    """정답 순위: bm25=없음, hybrid=5, rerank=1, rewrite=1, full=없음(필터가 정답을 거른 경우)."""
    queries = [{"qid": f"q{i}", "qtype": "nl", "scope": "paper", "query": f"질문{i}", "expected_id": f"d{i}"}
               for i in range(10)]
    others = [f"x{j}" for j in range(9)]
    runs = {}
    for i, q in enumerate(queries):
        d = f"d{i}"
        runs[q["qid"]] = {
            "bm25_meta": {"ids": others + ["z"], "ms": 1},
            "skovix_hybrid": {"ids": others[:4] + [d] + others[4:], "ms": 5},
            "skovix_rerank": {"ids": [d] + others, "ms": 9},
            "skovix_rewrite": {"ids": [d] + others, "ms": 20, "log": [f"쿼리 재작성: '질문{i}' → '키워드{i}'"]},
            "skovix_full": {"ids": others + ["z"], "ms": 25,
                            "log": [f"쿼리 재작성: '질문{i}' → '키워드{i}'", "메타데이터 필터 감지: pub_year_from=1801"]},
        }
    return queries, runs


def test_steps_attribute_the_regression_to_the_step_that_causes_it():
    queries, runs = _ladder_runs()
    g = ev.summarize_group(queries, runs, {}, seed=0)
    assert g["steps"]["skovix_hybrid"]["prev"] == "bm25_meta"
    assert g["steps"]["skovix_hybrid"]["r10"]["mean"] == pytest.approx(1.0)       # BM25 0% → hybrid 100%
    assert g["steps"]["skovix_rerank"]["r10"]["mean"] == pytest.approx(0.0)       # 이미 10위 안 → Recall@10 불변
    assert g["steps"]["skovix_rewrite"]["r10"]["mean"] == pytest.approx(0.0)
    full = g["steps"]["skovix_full"]
    assert full["prev"] == "skovix_rewrite" and full["r10"]["mean"] == pytest.approx(-1.0)   # 필터 단계에서 전부 잃음
    assert full["r10_only_baseline"] == 10 and full["r10_only_arm"] == 0


def test_markdown_shows_step_lines_and_flags_the_negative_step():
    queries, runs = _ladder_runs()
    md = ev.render_markdown(ev.build_report(queries, runs, {}), {"created": "2026-10-13"}, {"judges": "vlm=x"})
    assert "단계별: SKOVIX + 질의 재작성 → **SKOVIX 전체(재작성+메타필터, 운영 기본)**: Recall@10 -100.0%p" in md
    assert "SKOVIX + 질의 재작성" in md


def test_audit_shows_rank_per_arm_and_the_filter_that_was_applied(tmp_path):
    queries, runs = _ladder_runs()
    (tmp_path / "queries.json").write_text(json.dumps({"meta": {}, "queries": queries}), encoding="utf-8")
    (tmp_path / "runs.json").write_text(json.dumps(runs), encoding="utf-8")
    parser = ev.make_parser()
    out = ev.stage_audit(_args(parser, "audit", workdir=tmp_path), tmp_path)
    assert "q0  [bm25_meta=- sk_hybrid=5 sk_rerank=1 sk_rewrite=1 sk_full=-]" in out
    assert "skovix_full: 메타데이터 필터 감지: pub_year_from=1801" in out
    assert (tmp_path / "audit.txt").exists()

    out = ev.stage_audit(_args(parser, "audit", "--only-differ", "skovix_rerank,skovix_rewrite", workdir=tmp_path), tmp_path)
    assert out == "(해당하는 질의 없음)"                                      # 두 방식 순위가 같은 질의는 숨긴다
    out = ev.stage_audit(_args(parser, "audit", "--only-differ", "skovix_rewrite,skovix_full", workdir=tmp_path), tmp_path)
    assert out.count("질문:") == 10


def test_judge_model_label_is_recorded_and_shown_in_report(tmp_path):
    be, parser = FakeBackend(), ev.make_parser()
    asyncio.run(ev.stage_build(_args(parser, "build", "--n-papers", "8", "--n-books", "0", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_run(_args(parser, "run", "--arms", "bm25_meta", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_judge(_args(parser, "judge", workdir=tmp_path), be, tmp_path))
    models = json.loads((tmp_path / "judge_models.json").read_text(encoding="utf-8"))
    assert "30b" in models["vlm"]["label"]                                   # 별칭 뒤의 실제 모델이 기록된다
    ev.stage_report(_args(parser, "report", workdir=tmp_path), tmp_path)
    md = (tmp_path / "brochure_table.md").read_text(encoding="utf-8")
    assert "vlm=fake-vlm (서빙 모델: fake-vlm-30b)" in md
    meta = json.loads((tmp_path / "queries.json").read_text(encoding="utf-8"))["meta"]
    assert "서빙 모델" in meta["question_model"]

    asyncio.run(ev.stage_judge(_args(parser, "judge", "--model-label", "Qwen3-VL-30B-A3B-FP8", workdir=tmp_path), be, tmp_path))
    models = json.loads((tmp_path / "judge_models.json").read_text(encoding="utf-8"))
    assert models["vlm"]["label"] == "Qwen3-VL-30B-A3B-FP8"                   # 직접 지정이 우선


# ── 시간 표현 질문 제외 · 리포트의 순환/절대값 경고 ──────────
@pytest.mark.parametrize("q", [
    "요즘 독일어 교육은 어떻게 변화하고 있고 어떤 학습 방법이 쓰이나요?",   # 스모크에서 sort_by=recent 를 켰던 질문
    "최근 청소년 우울증 연구는 무엇을 다루나요 궁금합니다",
    "2020년 이후 지방재정 문제를 다룬 논문이 있나요 알려주세요",
])
def test_questions_with_date_or_recency_words_are_rejected(q):
    row = {"title": "무관한 제목입니다", "body": "무관한 본문 " * 20}
    assert ev.reject_reason(q, row) == "time_expr"


def test_era_expressions_are_allowed_because_they_do_not_create_a_filter():
    row = {"title": "무관한 제목입니다", "body": "무관한 본문 " * 20}
    assert ev.reject_reason("17세기 말 가문 안의 분쟁을 다룬 소설의 사상적 배경이 궁금합니다", row) is None
    assert "요즘" in ev._QGEN_SYS and "연도" in ev._QGEN_SYS      # 생성 단계에서도 금지를 알린다


def test_report_warns_about_circularity_only_when_gemma_judged():
    queries, runs = _ladder_runs()
    rep = ev.build_report(queries, runs, {})
    gemma = ev.render_markdown(rep, {"created": "x"}, {"judges": "llm=gemma", "judge_names": ["llm"]})
    qwen = ev.render_markdown(rep, {"created": "x"}, {"judges": "vlm=qwen", "judge_names": ["vlm"]})
    assert "순환 가능성" in gemma and "순환 가능성" not in qwen
    assert "절대값을 '정확도'로 읽지 않는다" in gemma and "절대값을 '정확도'로 읽지 않는다" in qwen   # 판정자와 무관하게 항상


def test_report_flow_records_judge_names_for_the_circularity_warning(tmp_path):
    be, parser = FakeBackend(), ev.make_parser()
    asyncio.run(ev.stage_build(_args(parser, "build", "--n-papers", "8", "--n-books", "0", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_run(_args(parser, "run", "--arms", "bm25_meta", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_judge(_args(parser, "judge", "--judge", "llm", workdir=tmp_path), be, tmp_path))
    ev.stage_report(_args(parser, "report", "--judges", "llm", workdir=tmp_path), tmp_path)
    assert "순환 가능성" in (tmp_path / "brochure_table.md").read_text(encoding="utf-8")
    ev.stage_report(_args(parser, "report", "--judges", "vlm", workdir=tmp_path), tmp_path)    # 판정 파일 없음 → 경고도 없음
    assert "순환 가능성" not in (tmp_path / "brochure_table.md").read_text(encoding="utf-8")


# ── 실제 질문 목록에서 정규식이 놓쳤던 시간 표현 · 필터가 걸린 질의를 가르는 층 ──
@pytest.mark.parametrize("q", [
    "762년에 세워진 비문에 나타난 '말갈국'이라는 표현은 어떤 의미일까?",          # 세 자리 연도 (nl-p-0092)
    "1960~70년대 과학 잡지에서 나타난 과학 소설들은 어떤 특징을 가지고 있나요?",   # 연대 범위 (nl-p-0140)
    "1920~30년대 문학가들의 사회 비판 활동과 문학 이념 관계를 찾고 있습니다",      # 연대 범위 (nl-b-0016)
])
def test_time_expr_catches_three_digit_years_and_decade_ranges(q):
    assert ev.reject_reason(q, {"title": "무관한 제목입니다", "body": "무관한 본문 " * 20}) == "time_expr"


@pytest.mark.parametrize("q", [
    "18세기 후반 윌리엄 블레이크 시에서 시간과 공간이 뒤섞이는 모습은 무엇을 의미하나요?",
    "냉전 이후 일본이 동아시아 지역 협력 구축에 적극적으로 나선 배경은 무엇인가요?",
    "6·25 전쟁 이후 혼란스러운 시대에 인간의 고뇌와 구원을 다룬 한국 소설 연구 자료가 있을까요?",
    "초등학생들이 수학 문제를 2~3개월 동안 풀면서 어려움을 느끼는 이유가 궁금합니다",
])
def test_time_expr_does_not_overreject_era_or_relative_words(q):
    assert ev.reject_reason(q, {"title": "무관한 제목입니다", "body": "무관한 본문 " * 20}) is None


def test_unfiltered_stratum_excludes_queries_where_a_date_filter_was_applied():
    queries, runs = _ladder_runs()
    for q in queries[:4]:       # 앞 4개는 필터 감지 로그가 있고, 나머지는 필터 줄이 없다
        runs[q["qid"]]["skovix_full"]["log"] = ["쿼리 재작성: 'a' → 'b'", "메타데이터 필터 감지: MetadataFilter(sort_by='recent')"]
    for q in queries[4:]:
        runs[q["qid"]]["skovix_full"]["log"] = ["쿼리 재작성: 'a' → 'b'"]
    rep = ev.build_report(queries, runs, {})
    assert rep["paper|nl"]["n"] == 10
    assert rep["paper|nl_unfiltered"]["n"] == 6 and rep["paper|nl_unfiltered"]["n_excluded_filtered"] == 4
    md = ev.render_markdown(rep, {"created": "x"}, {"judges": "vlm=x"})
    assert "제외 4건" in md and "날짜 필터·정렬이 걸리지 않은 질의" in md


def test_unfiltered_stratum_absent_when_no_filter_or_everything_filtered():
    queries, runs = _ladder_runs()
    for q in queries:
        runs[q["qid"]]["skovix_full"]["log"] = ["쿼리 재작성: 'a' → 'b'"]
    assert "paper|nl_unfiltered" not in ev.build_report(queries, runs, {})        # 필터가 하나도 없으면 층을 만들지 않음
    for q in queries:
        runs[q["qid"]]["skovix_full"]["log"] = ["메타데이터 필터 감지: x"]
    assert "paper|nl_unfiltered" not in ev.build_report(queries, runs, {})        # 전부 걸렸으면 빈 층을 만들지 않음


# ── 논문 범위만 내기(--scopes) ────────────────────────────────
def _two_scope_flow(tmp_path):
    be, parser = FakeBackend(), ev.make_parser()
    asyncio.run(ev.stage_build(_args(parser, "build", "--n-papers", "8", "--n-books", "6", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_run(_args(parser, "run", "--arms", "bm25_meta", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_judge(_args(parser, "judge", workdir=tmp_path), be, tmp_path))
    return be, parser


def test_report_scopes_paper_drops_book_groups_and_book_corpus_count(tmp_path):
    _, parser = _two_scope_flow(tmp_path)
    ev.stage_report(_args(parser, "report", workdir=tmp_path), tmp_path)             # 기본은 전부
    both = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert "paper|nl" in both["groups"] and "book|nl" in both["groups"]

    ev.stage_report(_args(parser, "report", "--scopes", "paper", workdir=tmp_path), tmp_path)
    only = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert list(g for g in only["groups"] if g.startswith("book")) == []
    assert "paper|nl" in only["groups"] and only["groups"]["paper|nl"]["n"] == both["groups"]["paper|nl"]["n"]
    assert "book" not in only["meta"]["corpus_docs"] and "paper" in only["meta"]["corpus_docs"]
    md = (tmp_path / "brochure_table.md").read_text(encoding="utf-8")
    assert "도서" not in md.split("---")[0] and "'book'" not in md


def test_report_scopes_without_matching_queries_stops_loudly(tmp_path):
    _, parser = _two_scope_flow(tmp_path)
    with pytest.raises(SystemExit):
        ev.stage_report(_args(parser, "report", "--scopes", "nothing", workdir=tmp_path), tmp_path)


def test_review_sheet_scopes_samples_only_requested_scope(tmp_path):
    be, parser = _two_scope_flow(tmp_path)
    qmap = {q["qid"]: q["scope"] for q in json.loads((tmp_path / "queries.json").read_text(encoding="utf-8"))["queries"]}
    asyncio.run(ev.stage_review_sheet(_args(parser, "review-sheet", "--n", "10", "--scopes", "paper", workdir=tmp_path), be, tmp_path))
    key = json.loads((tmp_path / "review_key.json").read_text(encoding="utf-8"))
    assert key and {qmap[v["pair"].split("|", 1)[0]] for v in key.values()} == {"paper"}
    asyncio.run(ev.stage_review_sheet(_args(parser, "review-sheet", "--n", "40", workdir=tmp_path), be, tmp_path))     # 기본은 섞여 나온다
    key_all = json.loads((tmp_path / "review_key.json").read_text(encoding="utf-8"))
    assert {qmap[v["pair"].split("|", 1)[0]] for v in key_all.values()} == {"paper", "book"}


# ── 시트를 사람이 아닌 채점자(다른 LLM)가 채운 경우 '사람 검증'으로 표기하지 않는다 ──
def _fill_sheet_like_llm(sheet: Path, key: dict) -> None:
    import csv
    rows = list(csv.reader(sheet.open(encoding="utf-8-sig", newline="")))
    for r in rows[1:]:
        r[5] = str(key[r[0]]["llm"])
    with sheet.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)


def test_non_human_rater_is_reported_as_cross_check_not_human_validation(tmp_path):
    be, parser = FakeBackend(), ev.make_parser()
    asyncio.run(ev.stage_build(_args(parser, "build", "--n-papers", "8", "--n-books", "0", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_run(_args(parser, "run", "--arms", "bm25_meta", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_judge(_args(parser, "judge", workdir=tmp_path), be, tmp_path))
    asyncio.run(ev.stage_review_sheet(_args(parser, "review-sheet", "--n", "10", workdir=tmp_path), be, tmp_path))
    sheet = tmp_path / "review_sheet.csv"
    _fill_sheet_like_llm(sheet, json.loads((tmp_path / "review_key.json").read_text(encoding="utf-8")))

    ev.stage_agreement(_args(parser, "agreement", "--sheet", str(sheet), "--rater", "Claude", workdir=tmp_path), tmp_path)
    ev.stage_report(_args(parser, "report", workdir=tmp_path), tmp_path)
    md = (tmp_path / "brochure_table.md").read_text(encoding="utf-8")
    assert "사람 검증: 미실시" in md                                   # 사람이 한 것이 아니므로 사람 검증은 여전히 미실시
    assert "다른 LLM 교차 확인(사람 아님): Claude" in md

    ev.stage_agreement(_args(parser, "agreement", "--sheet", str(sheet), workdir=tmp_path), tmp_path)    # 사람이 채운 경우
    ev.stage_report(_args(parser, "report", workdir=tmp_path), tmp_path)
    md = (tmp_path / "brochure_table.md").read_text(encoding="utf-8")
    assert "사람 검증: 10쌍" in md and "교차 확인" not in md
