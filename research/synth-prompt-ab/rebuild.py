"""운영 GET 응답(report)으로 ResearchState 를 다시 만든다 — 절 = 근거 있는 하위질문, 근거 대목 = report.evidence.

경로는 환경 변수로 바꾼다(README '재현' 절):
- SYNTH_AB_APP  — 코드를 읽을 app 폴더. 기본은 이 저장소의 app/(이 파일 기준 ../../app).
                  측정 당시 코드로 돌리려면 `git archive <커밋> app | tar -x -C <폴더>` 로 푼 <폴더>/app 을 준다.
- SYNTH_AB_JOBS — 운영 보고서 JSON(GET /api/research/{job_id} 응답을 job_<id>.json 으로 저장) 폴더. 기본은 이 폴더의 jobs/.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = os.environ.get("SYNTH_AB_APP") or str(HERE.parents[1] / "app")
sys.path.insert(0, WT)
from services.research.state import Chunk, Evidence, ResearchState, SubQuestion, merge_params  # noqa: E402

SD = str(Path(os.environ.get("SYNTH_AB_JOBS") or HERE / "jobs")) + os.sep
JOBS = {"630e": SD + "job_630e0d65-bd09-4429-9eda-e00d85dbff6b.json",
        "d60a": SD + "job_d60a5dc1-76a4-4506-88ec-dfbfa49f93f7.json",
        "85d2": SD + "job_85d2bc0e-541d-4d27-a98f-c0b8fe262701.json",
        "9ba1": SD + "job_9ba10849-36e2-417a-bc59-abec8e002c2c.json"}


def state_of(tag):
    j = json.load(open(JOBS[tag], encoding="utf-8"))
    r = j["report"]
    st = ResearchState(job_id=j["job_id"], question=j["question"], params=merge_params({}))
    st.evidence = {eid: Evidence(id=eid, cnts_id=e["cnts_id"], meta=e["meta"],
                                 chunks=[Chunk(**c) for c in e["chunks"]])
                   for eid, e in r["evidence"].items()}
    for idx, s in enumerate(r["sections"]):
        eids = [p["evidence"][0] for p in s["papers"]]
        st.subquestions.append(SubQuestion(idx=idx, text=s["heading"], evidence_ids=eids, verdict="sufficient",
                                           evidence_chunks={e: s["evidence_chunks"][e] for e in eids},
                                           chunk_scores=dict(s["chunk_scores"])))
    # 절의 앞 5편 밖에서 매칭된 대목 — 보고서 evidence 에 실렸으니 어느 하위질문이든 가리킨다. 절을 만들지 않는
    # 빈 하위질문에 매핑만 둔다(_borrowed 가 본다)
    mapped = {c for sq in st.subquestions for ids in sq.evidence_chunks.values() for c in ids}
    rest = {eid: [c.chunk_id for c in ev.chunks if c.chunk_id not in mapped] for eid, ev in st.evidence.items()}
    rest = {e: ids for e, ids in rest.items() if ids}
    if rest:
        st.subquestions.append(SubQuestion(idx=len(st.subquestions), text="(앞 5편 밖 매핑)", evidence_ids=[],
                                           verdict="sufficient", evidence_chunks=rest))
    return j, st
