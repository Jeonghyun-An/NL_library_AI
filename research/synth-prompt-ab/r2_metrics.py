"""2차 A/B(focus 대 focus2) 지표 — gen_r2/*.json 을 ab_metrics.py(v2)의 job_metrics 로 센다.

사용: PYTHONIOENCODING=utf-8 python r2_metrics.py [--dump 일반화|되받기|일반론|재인용|요약1|첫문장]
  → r2_metrics.txt(표)·r2_metrics.json(수치 전부)
- ab_metrics.py 는 고치지 않고 가져다 쓴다(입력 폴더만 다르다). 집계 방식도 같다: 보고서마다 회차 평균 → 보고서 4건 평균.
- 참고 열 'focus@1차' = gen_ab/focus_*(fd360d1 코드, 번호 인용 후처리 전) — 같은 프롬프트의 회차 간 흔들림을 보려고 싣는다.
- 여기서 더한 지표(ab_metrics 에 없는 것):
  · single_src_general — 도입 문장 중 '주로·대부분·주요·주된·대다수·일반적으로·공통적으로·많은 연구' 처럼 연구 전체를 말하는
    표현이 있는데 [E#] 가 하나뿐인 문장(검토 지적 ③ '한 논문 표본을 분야 전체로' 의 대리 지표). 범위(N편·기간)를 밝힌 문장도 든다
    — 여러 연구를 분석한 논문이면 정당하므로 수치는 '의심' 이다.
  · raw_foreign_ref — 모델 원문(JSON 문자열 전체)에 든 남의 번호 인용 '[3]'·'[3, 4]' 수. 최종본은 73feb90 후처리가 지우므로
    프롬프트가 옮기기 자체를 줄였는지는 원문으로만 보인다.
"""
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import ab_metrics as am  # noqa: E402  (fix-live/app 경로·rebuild.JOBS 4건을 갖춘다)
from ab_metrics import syn, strip_markers  # noqa: E402

HERE = Path(__file__).resolve().parent
GEN = HERE / "gen_r2"
VARIANTS = ["focus", "focus2"]
REF = ("focus@1차", HERE / "gen_ab", "focus")
TAGS = am.TAGS

_GENERALIZE = re.compile(r"주로|대부분|주요|주된|대다수|일반적으로|공통적으로|많은\s?연구|대체로|전반적으로")
_MARK = re.compile(r"\[E(\d+)\]")


def extra_metrics(r: dict) -> dict:
    secs = r["sections"] or []
    m, gl = {}, []
    for k, s in enumerate(secs):
        for i, x in enumerate(syn._sentences(s["intro"])):
            ids = set(_MARK.findall(x))
            if _GENERALIZE.search(strip_markers(x)) and len(ids) == 1:
                gl.append((k + 1, i + 1, x))
    m["single_src_general"] = len(gl)
    m["_single_src_general"] = gl
    m["raw_foreign_ref"] = sum(len(am._FOREIGN_REF.findall(c["raw"] or "")) for c in r["calls"])
    m["_first"] = [(k + 1, s["heading"], (syn._sentences(s["intro"]) or [""])[0]) for k, s in enumerate(secs)]
    m["_summ_one"] = [(k + 1, p["cnts_id"], p["summary"]) for k, s in enumerate(secs) for p in s["papers"]
                      if p["summary"] and len(syn._sentences(p["summary"])) == 1]
    return m


def collect(folder: Path, variants, label=None):
    states = {t: am.rebuild.state_of(t)[1] for t in TAGS}
    rows = defaultdict(list)
    for f in sorted(folder.glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        if r["variant"] not in variants:
            continue
        m = am.job_metrics(r, states[r["tag"]])
        m.update(extra_metrics(r))
        m["code_head"] = r.get("code_head", "fd360d1(1차)")
        rows[(label or r["variant"], r["tag"])].append((r["run"], m))
    return rows


COLS = [
    (None, "[1차 자동 지표 기준 — focus2 가 focus 보다 나쁘지 않을 것]", 0),
    ("invalid_cites", "무효 인용(원출력)", 2), ("format_bad_calls", "형식 문제 호출", 2), ("empty_summaries", "빈 요약", 2),
    ("unmarked", "근거 표시 없는 문장", 2), ("retries", "재시도", 1), ("failed_sections", "실패 절", 1), ("truncated", "길이 잘림", 1),
    (None, "[① 요약 길이]", 0),
    ("summ_sent_per_paper", "요약 문장/편", 2), ("summ_one", "1문장 요약(편)", 1), ("summ_one_ratio", "  1문장 요약 비율", 2),
    (None, "[② 도입 상한]", 0),
    ("intro_sent_per_sec", "도입 문장/절", 2), ("intro_over4", "도입 4문장 초과 절", 2), ("intro_over4_ratio", "  초과 비율", 2),
    ("intro_max", "도입 최대 문장", 1),
    (None, "[③ 한 논문 → 분야 일반화]", 0),
    ("single_src_general", "단일 근거 일반화 의심(도입)", 2),
    (None, "[④ 남의 번호 인용]", 0),
    ("raw_foreign_ref", "원문 '[3]' 꼴 수", 2), ("foreign_ref", "최종본 '[3]' 문장", 2),
    (None, "[⑤ 향후 과제]", 0),
    ("future_per_sec", "향후 과제/절", 2), ("future_zero", "향후 과제 0개 절", 2),
    (None, "[⑥ 재인용]", 0),
    ("recite_used", "재인용 문장을 옮김", 2), ("recite_suspect", "오귀속 의심", 2), ("recite_suspect_strong", "  그중 저자·연도형", 2),
    ("recite_suspect_summary", "  그중 요약", 2), ("recite_marked_out", "출처를 밝힌 문장", 2),
    (None, "[⑦ 일반론·되받기]", 0),
    ("generic_first", "첫문장 일반론 v1", 2), ("generic_first_v2", "첫문장 일반론 v2", 2),
    ("generic_all", "도입 일반론 v1", 2), ("generic_all_v2", "도입 일반론 v2", 2),
    ("echo_first", "첫문장 하위질문 되받기", 2), ("echo_generic", "  그중 일반론 v2", 2),
    ("meta_raw", "군말(원출력)", 2), ("meta_final", "군말(최종)", 2),
    (None, "[겹침·분량]", 0),
    ("xsec_max_sim", "절간 최대 유사도", 2), ("xsec_pairs_07", "0.7 이상 쌍", 2), ("xsec_pairs_07_generic_v2", "  그중 일반론 v2", 2),
    ("same_paper_summ_pairs_07", "같은 논문 요약 0.7↑", 2), ("drop_repeats_removed", "drop_repeats 삭제", 2),
    ("sent_per_sec", "절당 문장", 2), ("chars_per_sec", "절당 글자", 0),
    ("biblio_summ", "참고문헌꼴 요약(편)", 2),
]
POOLED = [
    ("summ_one", "summ_total", "1문장 요약(편)"), ("intro_over4", "n_sections", "도입 4문장 초과(절)"),
    ("future_zero", "n_sections", "향후 과제 0개(절)"), ("single_src_general", None, "단일 근거 일반화 의심(문장)"),
    ("raw_foreign_ref", None, "원문 '[3]' 꼴"), ("foreign_ref", None, "최종본 '[3]' 문장"),
    ("recite_used", None, "재인용 옮김"), ("recite_suspect", None, "오귀속 의심"),
    ("generic_first_v2", "n_sections", "첫문장 일반론 v2(절)"), ("echo_first", "n_sections", "첫문장 되받기(절)"),
    ("generic_all_v2", None, "도입 일반론 v2(문장)"),
    ("invalid_cites", None, "무효 인용"), ("format_bad_calls", "calls", "형식 문제 호출"), ("empty_summaries", None, "빈 요약"),
    ("unmarked", None, "근거 표시 없는 문장"),
]
PER_REPORT = ["summ_one_ratio", "intro_over4", "single_src_general", "raw_foreign_ref", "future_zero", "recite_suspect",
              "generic_all_v2", "echo_first", "unmarked", "invalid_cites", "xsec_pairs_07"]


def main():
    dump = sys.argv[sys.argv.index("--dump") + 1] if "--dump" in sys.argv else None
    rows = collect(GEN, VARIANTS)
    rows.update(collect(REF[1], [REF[2]], label=REF[0]))
    cols = [c for c, _, _ in COLS if c]
    labels = [*VARIANTS, REF[0]]
    agg = {(v, t): {c: statistics.mean(m[c] for _, m in lst) for c in cols} for (v, t), lst in rows.items()}
    by_v = {v: {c: statistics.mean(agg[(v, t)][c] for t in TAGS) for c in cols} for v in labels}
    pooled = {}
    for v in labels:
        jobs = [m for (vv, _), lst in rows.items() if vv == v for _, m in lst]
        pooled[v] = {k: sum(m[k] for m in jobs) for k in {*(a for a, _, _ in POOLED), *(b for _, b, _ in POOLED if b)}}
        pooled[v]["intro_max"] = max(m["intro_max"] for m in jobs)
        pooled[v]["jobs"] = len(jobs)
        pooled[v]["code"] = sorted({m["code_head"] for m in jobs})

    def fmt(x, d):
        return f"{x:.{d}f}" if isinstance(x, float) else str(x)

    W = 30
    out = ["# 종합 프롬프트 2차 A/B 지표 — focus(저장소 yaml) vs focus2(variant_focus2.yaml), 2026-10-14",
           f"# 코드: fix-live {pooled['focus']['code']} (번호 인용 후처리 73feb90 포함) · gemma-3-12b · temperature 0.3",
           "# 스크립트: prompt_ab/r2_metrics.py (ab_metrics.py v2 의 job_metrics + 이 파일의 일반화·원문 번호 인용)",
           f"# 잡 수: focus {pooled['focus']['jobs']} · focus2 {pooled['focus2']['jobs']} · 참고 {REF[0]} {pooled[REF[0]]['jobs']}"
           f" (코드 {pooled[REF[0]]['code']}, 번호 인용 후처리 전)",
           "",
           "== 변형별 평균 — 보고서 1건(6절)당, 보고서 4건 × 2회(보고서마다 회차 평균을 낸 뒤 4건 평균)",
           "지표".ljust(W) + "".join(v.rjust(12) for v in labels)]
    for c, name, d in COLS:
        if c is None:
            out.append(name)
            continue
        out.append(("  " + name).ljust(W) + "".join(fmt(by_v[v][c], d).rjust(12) for v in labels))
    out += ["", "== 합산 — 변형마다 8잡 전부(분모가 있으면 비율)", "지표".ljust(W) + "".join(v.rjust(18) for v in labels)]
    for num, den, name in POOLED:
        cells = []
        for v in labels:
            p = pooled[v]
            cells.append((f"{p[num]}/{p[den]} ({p[num] / p[den]:.0%})" if den else str(p[num])).rjust(18))
        out.append(("  " + name).ljust(W) + "".join(cells))
    out.append(("  도입 최대 문장").ljust(W) + "".join(str(pooled[v]["intro_max"]).rjust(18) for v in labels))
    names = {c: n.strip() for c, n, _ in COLS if c}
    digits = {c: d for c, _, d in COLS if c}
    out += ["", "== 보고서별(회차 평균) — 630e·9ba1 은 focus2 를 다듬을 때 쓴 보고서, d60a·85d2 는 다듬을 때 안 본 보고서",
            "보고서 변형       " + " | ".join(names[k] for k in PER_REPORT)]
    for t in TAGS:
        for v in labels:
            out.append(f"{t} {v:10}  " + " | ".join(fmt(agg[(v, t)][k], digits[k]).rjust(len(names[k])) for k in PER_REPORT))
    text = "\n".join(out)
    print(text)
    (HERE / "r2_metrics.txt").write_text(text + "\n", encoding="utf-8")
    (HERE / "r2_metrics.json").write_text(json.dumps({
        "per_job": {f"{v}_{t}_r{run}": {k: val for k, val in m.items() if not k.startswith("_")}
                    for (v, t), lst in rows.items() for run, m in lst},
        "per_report_variant": {f"{v}_{t}": a for (v, t), a in agg.items()},
        "per_variant": by_v, "pooled": pooled}, ensure_ascii=False, indent=1, default=list), encoding="utf-8")

    if dump:
        for t in TAGS:
            for v in VARIANTS:
                for run, m in sorted(rows[(v, t)], key=lambda x: x[0]):
                    tag = f"{v} {t} r{run}"
                    if dump == "일반화":
                        for k, i, x in m["_single_src_general"]:
                            print(f"[일반화] {tag} s{k}.{i}: {x[:150]}")
                    if dump == "첫문장":
                        for k, h, x in m["_first"]:
                            print(f"[첫문장] {tag} s{k} {h[:40]} → {x[:130]}")
                    if dump == "요약1":
                        for k, c, x in m["_summ_one"]:
                            print(f"[요약1] {tag} s{k} {c}: {x[:130]}")
                    if dump == "일반론":
                        for k, i, x in m["_generic_v2"]:
                            print(f"[일반론v2] {tag} s{k}.{i}: {x[:130]}")
                    if dump == "되받기":
                        for k, cov, h, x in m["_echo"]:
                            print(f"[되받기] {tag} s{k} cov{cov}: {h[:40]} → {x[:110]}")
                    if dump == "재인용":
                        for x in m["_recite"]:
                            if not x["attributed"]:
                                print(f"[오귀속의심{x['kind']}] {tag} s{x['sec']} {x['field']} {x['eid']} cov{x['cover']}: "
                                      f"{x['sentence'][:120]}\n      ← {x['src'][:140]}")


if __name__ == "__main__":
    main()
