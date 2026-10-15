"""measure_g2.py 결과(measure_g2.json — 생성 원문이 들어 있어 저장소에는 넣지 않았다)를 짧게 줄인다.

사용: PYTHONIOENCODING=utf-8 python summarize_g2.py <measure_g2.json> > measure_g2_out.txt
- 첫 두 줄은 measure_g2.py 가 화면에 찍는 요약과 같은 꼴이다(변형마다 8회 중 해당 회수).
- 이어서 회차마다 '본/이 연구·논문'(SELF) 이 걸린 자리의 앞뒤 몇 글자를 싣는다 — 근거 논문을 '본 연구'로 불렀는지,
  계획서 자신을 '본 연구'로 불렀는지(새 프롬프트가 허용한 쓰임)는 이것으로 눈으로 가른다.
"""
import json
import re
import sys

SELF = re.compile(r"(?:본|이)\s*(?:연구|논문)")

d = json.load(open(sys.argv[1], encoding="utf-8"))
for name, runs in d.items():
    def rate(key: str) -> str:
        return f"{sum(1 for r in runs if r[key])}/{len(runs)}"
    print(f"{name}: 원문 [F#] 있음 {rate('raw_any_f')} · 원문 떨어진 [F#] {rate('raw_loose_f')} · "
          f"원문 본/이 연구 {rate('raw_self')} · 저장 떨어진 [F#] {rate('stored_loose_f')} · "
          f"저장 본/이 연구 {rate('stored_self')} · 검사 통과 {rate('check_ok')} · "
          f"원문 문단 수 {[r['raw_paragraphs'] for r in runs]} · 저장 문단 수 {[r['stored_paragraphs'] for r in runs]}")
print()
for name, runs in d.items():
    for i, r in enumerate(runs):
        hits = [r["raw"][max(0, m.start() - 12):m.end() + 14].replace("\n", " ") for m in SELF.finditer(r["raw"])]
        print(f"{name} {i}: " + " | ".join(hits))
