"""판정 묶음(make_judge*.py 출력)에서 근거 대목 원문을 빼고 청크 id 만 남긴 사본을 만든다 — 저장소 보관용.

사용: PYTHONIOENCODING=utf-8 python slim_pairs.py <판정 묶음 json> <짝 키 json> <gen 폴더들의 부모> <출력 json>
  예) python slim_pairs.py judge_pairs.json judge_key.json . judge_pairs.slim.json
- 판정자가 본 X·Y 출력(도입·요약·향후 과제)과 연구 질문·하위질문·근거 서지(id·제목·발행·게재지)는 그대로 둔다.
- 근거 대목 원문(excerpt·excerpt_X·excerpt_Y — 모델이 읽은 400자 창)은 chunk_id(·chunk_id_X·chunk_id_Y)로 바꾼다.
  청크 id 는 짝 키의 X_file·Y_file(run_ab.py 출력)의 excerpts[하위질문][E#] 에서 읽고, 그 text 가 묶음의 원문과 글자까지
  같은지 확인한다(다르면 멈춘다).
- 원문 창은 운영 보고서 JSON(jobs/)의 report.evidence[E#].chunks 에서 그 chunk_id 의 text 를 당시 코드의
  synthesizer.excerpt_text 로 자르면 다시 나온다(1차 0262673, 2차 3555e82 — README '재현').
"""
import json
import sys
from pathlib import Path

src, key_path, gen_root, out = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4]
doc = json.loads(Path(src).read_text(encoding="utf-8"))
key = json.loads(Path(key_path).read_text(encoding="utf-8"))
_gen: dict[str, dict] = {}


def gen(rel: str) -> dict:
    if rel not in _gen:
        _gen[rel] = json.loads((gen_root / rel).read_text(encoding="utf-8"))
    return _gen[rel]


removed = 0
for pair in doc["pairs"]:
    k = key[pair["pair_id"]]
    gx, gy = gen(k["X_file"]), gen(k["Y_file"])
    for sec in pair["sections"]:
        h = sec["subquestion"]
        for ev in sec["evidence"]:
            e = ev["id"]
            for field, g in (("excerpt", gx), ("excerpt_X", gx), ("excerpt_Y", gy)):
                if field not in ev:
                    continue
                text = ev.pop(field)
                rec = g["excerpts"][h].get(e)
                if text == "" and rec is None:
                    cid = None            # 그 출력이 이 논문 대목을 읽지 않았다(make_judge 가 빈 글로 둔 경우)
                else:
                    assert rec is not None and rec["text"] == text, (pair["pair_id"], h, e, field)
                    cid = rec["chunk_id"]
                ev[field.replace("excerpt", "chunk_id")] = cid
                ev[field.replace("excerpt", "excerpt_chars")] = len(text)
                removed += len(text)
doc["about"] += (" [저장소 사본] 근거 대목 원문(excerpt)은 빼고 chunk_id·글자 수만 남겼다 — 원문은 운영 보고서 JSON 의 "
                 "report.evidence 청크에서 다시 얻는다(slim_pairs.py 머리글).")
Path(out).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{src} → {out}: 짝 {len(doc['pairs'])}개, 뺀 대목 글자 {removed:,}")
