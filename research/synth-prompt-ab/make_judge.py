"""블라인드 판정 묶음 — 보고서마다 base 와 각 후보(focus·attrib·concise)의 run0 출력을 짝지어 변형 이름을 지우고 X/Y 로 표시한다.

사용: PYTHONIOENCODING=utf-8 python make_judge.py
- judge_pairs.json(판정자에게 준다): 짝마다 연구 질문, 절마다 하위질문·근거 대목 원문(모델이 실제로 읽은 400자 창, 서지)·X 출력·Y 출력.
  출력은 화면에 나가는 최종 절(도입·대표 논문 요약·향후 과제, 인용 표기 [E#] 포함)이다. 한계 섹션은 싣지 않는다(탐색 단계 산물이 대부분이고,
  종합 관련 줄은 무표기 수 등 자동 지표를 드러낸다).
- judge_key.json(판정자에게 주지 않는다): 짝 번호 → 보고서·X/Y 변형·원본 파일·시드.
- X/Y 배정은 보고서별 고정 시드(random.Random(f"judge-{job_id}")), 짝 번호 순서는 고정 시드("judge-order")로 섞는다.
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
CANDS = ["focus", "attrib", "concise"]
RUN = 0


def load(variant, tag):
    return json.loads((HERE / "gen_ab" / f"{variant}_{tag}_r{RUN}.json").read_text(encoding="utf-8"))


def render(r, by_cnts):
    out = []
    for s in r["sections"]:
        out.append({
            "intro": s["intro"],
            "summaries": [{"id": by_cnts[p["cnts_id"]], "text": p["summary"]} for p in s["papers"]],
            "future": [f["text"] for f in s["future"]],
        })
    return out


def main():
    pairs, key = [], {}
    for tag in TAGS:
        j, st = rebuild.state_of(tag)
        by_cnts = {ev.cnts_id: eid for eid, ev in st.evidence.items()}
        base = load("base", tag)
        rng = random.Random(f"judge-{j['job_id']}")
        for cand in CANDS:
            other = load(cand, tag)
            assert [s["heading"] for s in base["sections"]] == [s["heading"] for s in other["sections"]]
            x_is_base = rng.random() < 0.5
            X, Y = (base, other) if x_is_base else (other, base)
            rx, ry = render(X, by_cnts), render(Y, by_cnts)
            sections = []
            for k, s in enumerate(base["sections"]):
                h = s["heading"]
                ex_x, ex_y = X["excerpts"][h], Y["excerpts"][h]
                ev = []
                for p in s["papers"]:
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
                "tag": tag, "job_id": j["job_id"], "candidate": cand,
                "X": X["variant"], "Y": Y["variant"],
                "X_file": f"gen_ab/{X['variant']}_{tag}_r{RUN}.json", "Y_file": f"gen_ab/{Y['variant']}_{tag}_r{RUN}.json",
                "seed": f"judge-{j['job_id']}"}})
    random.Random("judge-order").shuffle(pairs)
    out = []
    for i, p in enumerate(pairs, 1):
        pid = f"P{i:02d}"
        key[pid] = p.pop("_key")
        out.append({"pair_id": pid, **p})
    doc = {
        "about": ("딥리서치 보고서 종합 단계 출력 두 벌(X·Y)을 절마다 나란히 둔 판정 묶음. 같은 근거 대목(모델이 실제로 읽은 창)을 받아 "
                  "같은 하위질문으로 쓴 절이다. 출력의 [E#] 는 그 절 evidence 의 id 를 가리킨다. summaries 는 논문(id)마다 붙는 요약으로 "
                  "화면에서는 그 논문의 서지 아래에 실린다. intro 는 절 첫 문단, future 는 향후 과제 목록이다."),
        "pairs": out,
    }
    (HERE / "judge_pairs.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "judge_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    for pid, k in key.items():
        print(pid, k["tag"], k["candidate"], "X=" + k["X"], "Y=" + k["Y"])


main()
