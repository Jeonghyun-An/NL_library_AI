"""2차 블라인드 판정 묶음 — focus 대 focus2. 보고서마다 r0·r1 두 회차를 짝으로 쓰고, 한 회차는 focus 를 X 에,
다른 회차는 Y 에 둔다(위치 편향 상쇄). 짝 8개 = 보고서 4건 × 회차 2.

사용: PYTHONIOENCODING=utf-8 python make_judge_r2.py
- r2_pairs.json(판정자에게 준다): make_judge.py(1차)와 같은 모양 — 짝마다 연구 질문, 절마다 하위질문·근거 대목 원문(모델이 실제로
  읽은 창, 서지)·X 출력·Y 출력. 출력은 화면에 나가는 최종 절(도입·대표 논문 요약·향후 과제, [E#] 포함). 한계 섹션은 싣지 않는다.
- r2_key.json(판정자에게 주지 않는다): 짝 번호 → 보고서·회차·X/Y 변형·원본 파일·시드.
- 어느 회차에서 focus 가 X 인지는 보고서별 고정 시드(random.Random(f"r2-judge-{job_id}")), 짝 순서는 고정 시드("r2-judge-order")로 섞는다.
"""
import json
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # rebuild.py(같은 폴더)
import rebuild  # noqa: E402

rebuild.JOBS.update({
    "85d2": rebuild.SD + "job_85d2bc0e-541d-4d27-a98f-c0b8fe262701.json",
    "9ba1": rebuild.SD + "job_9ba10849-36e2-417a-bc59-abec8e002c2c.json",
})
TAGS = ["630e", "d60a", "85d2", "9ba1"]
GEN = "gen_r2"
A, B = "focus", "focus2"


def load(variant, tag, run):
    return json.loads((HERE / GEN / f"{variant}_{tag}_r{run}.json").read_text(encoding="utf-8"))


def render(r, by_cnts):
    return [{"intro": s["intro"],
             "summaries": [{"id": by_cnts[p["cnts_id"]], "text": p["summary"]} for p in s["papers"]],
             "future": [f["text"] for f in s["future"]]} for s in r["sections"]]


def main():
    pairs, key = [], {}
    for tag in TAGS:
        j, st = rebuild.state_of(tag)
        by_cnts = {ev.cnts_id: eid for eid, ev in st.evidence.items()}
        seed = f"r2-judge-{j['job_id']}"
        focus_x_run = random.Random(seed).choice([0, 1])
        for run in (0, 1):
            a, b = load(A, tag, run), load(B, tag, run)
            assert not a["error"] and not b["error"], (tag, run, a["error"], b["error"])
            X, Y = (a, b) if run == focus_x_run else (b, a)
            hx = [s["heading"] for s in X["sections"]]
            assert hx == [s["heading"] for s in Y["sections"]], (tag, run)
            rx, ry = render(X, by_cnts), render(Y, by_cnts)
            sections = []
            for k, (sx, sy) in enumerate(zip(X["sections"], Y["sections"])):
                assert [p["cnts_id"] for p in sx["papers"]] == [p["cnts_id"] for p in sy["papers"]], (tag, run, k)
                h = sx["heading"]
                ex_x, ex_y = X["excerpts"][h], Y["excerpts"][h]
                ev = []
                for p in sx["papers"]:
                    e = by_cnts[p["cnts_id"]]
                    meta = st.evidence[e].meta
                    item = {"id": e, "title": meta.get("title"), "pub_date": meta.get("pub_date"),
                            "series": meta.get("series_title"), "excerpt": ex_x[e]["text"] if e in ex_x else ""}
                    # 두 출력이 읽은 대목이 다르면(앞 절 실패로 고르는 대목이 갈린 경우) 둘 다 싣는다
                    if e in ex_y and ex_y[e]["chunk_id"] != ex_x.get(e, {}).get("chunk_id"):
                        item["excerpt_X"] = item.pop("excerpt")
                        item["excerpt_Y"] = ex_y[e]["text"]
                    ev.append(item)
                sections.append({"no": k + 1, "subquestion": h, "evidence": ev, "X": rx[k], "Y": ry[k]})
            pairs.append({"question": j["question"], "sections": sections, "_key": {
                "tag": tag, "job_id": j["job_id"], "run": run, "X": X["variant"], "Y": Y["variant"],
                "X_file": f"{GEN}/{X['variant']}_{tag}_r{run}.json", "Y_file": f"{GEN}/{Y['variant']}_{tag}_r{run}.json",
                "seed": seed, "focus_is_X_in_run": focus_x_run}})
    random.Random("r2-judge-order").shuffle(pairs)
    out = []
    for i, p in enumerate(pairs, 1):
        pid = f"Q{i:02d}"
        key[pid] = p.pop("_key")
        out.append({"pair_id": pid, **p})
    # 위치 균형 확인 — 보고서마다 focus 가 X 1번·Y 1번
    for tag in TAGS:
        xs = [k["X"] for k in key.values() if k["tag"] == tag]
        assert sorted(xs) == sorted([A, B]), (tag, xs)
    doc = {
        "about": ("딥리서치 보고서 종합 단계 출력 두 벌(X·Y)을 절마다 나란히 둔 판정 묶음. 같은 근거 대목(모델이 실제로 읽은 창)을 받아 "
                  "같은 하위질문으로 쓴 절이다. 출력의 [E#] 는 그 절 evidence 의 id 를 가리킨다. summaries 는 논문(id)마다 붙는 요약으로 "
                  "화면에서는 그 논문의 서지 아래에 실린다. intro 는 절 첫 문단, future 는 향후 과제 목록이다. "
                  "같은 연구 질문이 짝 두 개에 나온다(생성 회차가 다르다) — 짝마다 따로 판정한다."),
        "pairs": out,
    }
    (HERE / "r2_pairs.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "r2_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    for pid, k in key.items():
        print(pid, k["tag"], f"r{k['run']}", "X=" + k["X"], "Y=" + k["Y"])


main()
