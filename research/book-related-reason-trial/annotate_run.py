# generated_run.json 에 기계 집계(checks)와 사람이 본문 대조로 확인한 관찰(observations)을 더한다. generated.json 은 건드리지 않는다.
import difflib, json, re, sys
from pathlib import Path
HERE = Path(sys.argv[1])
g = json.loads((HERE / "generated.json").read_text(encoding="utf-8"))
run = json.loads((HERE / "generated_run.json").read_text(encoding="utf-8"))
checks = {}
for k in ("A", "A_replay", "B", "C"):
    T = [p[k] or "" for p in g]
    checks[k] = {
        "avg_chars": round(sum(map(len, T)) / len(T)),
        "starts_해당_논문들은": sum(t.strip().startswith("해당 논문들은") for t in T),
        "starts_해당_논문은": sum(t.strip().startswith("해당 논문은") for t in T),
        "starts_해당_자료는/자료들은": sum(t.strip().startswith(("해당 자료는", "해당 자료들은")) for t in T),
        "mentions_논문_count": sum(t.count("논문") for t in T),
        "has_markdown_bold": sum("**" in t for t in T),
        "has_기존연구_한계": sum(bool(re.search(r"기존\s*(소설\s*)?연구", t)) for t in T),
        "has_개선_방안": sum("개선 방안" in t for t in T),
        "leaks_법령식_틀어(규율 대상·규정 사항)": sum(bool(re.search("규율|규정 사항", t)) for t in T),
    }
checks["A_vs_A_replay_similarity"] = [round(difflib.SequenceMatcher(None, p["A"], p["A_replay"]).ratio(), 2) for p in g]
run["checks"] = checks
run["observations"] = [
    "실패 0 — A·A_replay·B·C 각 12/12 성공, 직접 호출은 모두 finish_reason=stop(200토큰에 안 잘림), 호출당 0.7~1.8초",
    "A_replay 는 A 와 요지가 같다(문자 유사도 0.56~1.0, temperature 0.2 표본 차이) — 서버 경로와 직접 경로가 같은 모델·같은 초록 줄을 쓴다는 대조 확인. B·C 와의 차이는 프롬프트 탓으로 볼 수 있다",
    "A 는 12/12 '해당 논문들은' 으로 시작하고 정책 보고서도 '연관 논문'이라 부른다(#6 경제백서 1999). 형식 끝 '유사합니다.' 로 끝나는 것은 0/12 — 두 번째 문장을 덧붙인다",
    "B 는 사실상 A 에서 낱말만 바뀐 문장 — 밋밋함·내용 차이 없음. 사용자 프롬프트('원본 논문/연관 논문/두 논문이')를 그대로 둬서 B 도 '두 논문 모두'를 쓴다(논문 낱말 12회)",
    "질의 2(재정) 4쌍은 A·B 모두 '재정 운영 문제점 진단·개선 방안 모색' 한 틀로 겹친다. #5 연관 자료 본문에 질의어 그대로인 '국가재정운용계획'이 있는데 A·B·C 어느 것도 들지 않는다",
    "C 는 이름을 들긴 하지만 한쪽 본문에만 있는 이름을 '두 자료 모두'의 공통점으로 내세운다: #3 '<노섬상좌기>·<녹처사연회>·<두껍전>·<서대주전>을 두 논문 모두 언급'(우화소설 쪽에만 있음), #10 梁柱東(원본에만)·萬海(연관에만)를 공통 분석으로, #11 이론가 목록(梁柱東·김억·박영희·이광수, 원본에만)을 공통으로, #1 '사회경제적 변화와 예술계의 변화'(원본에만)를 두 논문 모두로",
    "C 는 공통점을 만들려고 시기를 지어낸다: #12 '김교봉의 논문은 1920년대 신소설' — 본문은 '개화기'(A·B 는 '1920년대 시론 vs 개화기 신소설'로 바르게 구분). #1 에서도 A·B 가 밝힌 '조선후기와 1930년대 시대가 다를 뿐'을 C 는 지운다",
    "C 는 2/12 에 법령식 요약 틀 낱말이 샌다(#6 '주요 규율 대상', #7 '주요 규정 사항으로 다루며'), 2/12 에 ** 굵게 마크다운을 쓴다(#4·#9) — RelatedCard.vue 는 reason 을 {{ }} 평문으로 그려 ** 가 그대로 보인다",
    "A 도 왜곡이 있다: #11 '김병택 논문이 시론을 통해 … 이광수의 문학사상과 작품에 대한 균형 잡힌 이해를 촉구' — 원본은 1920년대 시론 연구이고 이광수는 효용론 한 줄로만 나온다",
    "질의 1 의 #2~#4 는 화면에 나오지 않는 보충 짝(screen_equivalent=false) — 화면 그대로면 질의 1 은 비교 사유 카드가 1장(시대가 다른 1930년대 세태소설)뿐이다",
]
(HERE / "generated_run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(checks, ensure_ascii=False, indent=1))
