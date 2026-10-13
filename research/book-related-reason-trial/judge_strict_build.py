"""엄격 판정자(근거 이탈) 점수 → judge_strict.json. 문장은 고치지 않고 매기기만 한다.

판정 기준(이 판정자의 해석):
- bland 0: 두 자료가 실제로(또는 문장이 주장하기로) 함께 가진 구체적 항목을 이름으로 짚음
           (세태소설 개념, 2003년, 신분제 동요, 이광수, 특정 작품·기관 등). 이름이 거짓 공유여도 구체성은 0.
  bland 1: 주제·분야 수준 공통점(조선후기 소설과 사회 배경, 예산 편성·집행 분석, 근대시 연구 등)
  bland 2: 어느 학위논문 쌍에도 붙일 빈말(기존 연구 한계 지적·새 방향 제시·다양한 요소의 영향)
- grounded: 각 사실 주장이 두 자료의 제목·서버 발췌(앞 400자, collected.json server_excerpt =
  generated.json user 프롬프트 '초록:' 줄)에서 확인되면 true. 한쪽에만 있는 내용을 '두 논문 모두'로
  씌우면(pooling) false, 본문과 어긋나면 false.
- form_ok: 소장자료 화면 카드(RelatedCard.vue — 평문 보간, 마크다운 렌더 없음)에 그대로 내도
  어색하지 않은가. 정책 보고서(질의 2 — 기획예산처·재정경제부)를 '논문'으로 부름, 프롬프트 내부 이름
  ('원본 논문/연관 논문') 노출, 마크다운(**) 노출, 비문, '~ 내용이 유사합니다' 형식 이탈이면 false.
  질의 1·3 자료는 실제 대학 학위논문(doc_type=literature)이라 '논문' 호칭 자체는 false 로 치지 않았다.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
gen = json.load(open(os.path.join(HERE, "generated.json"), encoding="utf-8"))

# (bland, grounded, form_ok, why) — 쌍 번호 1~12, 변형 A / A_replay / B / C
J = {
    1: {
        "A": (0, True, True, "세태소설 개념 재정립과 시대 차(조선후기/1930년대)를 정확히 짚음. 다만 '사회·문화적 맥락과 연관 지어 분석'은 연관 자료(양식론) 쪽 근거가 약함"),
        "A_replay": (0, True, True, "A와 거의 같은 문장 — 세태소설 개념 재정립·시대 차 확인됨(둘째 문장의 사회·문화 맥락은 연관 쪽 근거 약함)"),
        "B": (0, False, True, "'사회 변화와 문학의 연관성을 분석'을 두 자료 공통으로 씀 — 1930年代 世態小說 硏究 발췌는 양식(시간 구조·서술자·영화 기법) 분석이고 사회 변화 분석이 없음"),
        "C": (0, False, True, "둘째 문장이 원본의 '사회경제적 변화와 예술계의 변화가 세태소설 형성에 미친 영향'을 '두 논문 모두'로 돌림 — 연관 발췌에 없음"),
    },
    2: {
        "A": (1, True, True, "세태·가정소설 장르 형성의 사회 배경·시대 변화라는 주제 수준 공통점, 두 발췌에서 대체로 확인('개념 정립'은 연관의 '실상·위상 규명'을 넓게 읽음)"),
        "A_replay": (1, True, True, "A와 같은 내용 + '좁은 시야 벗어남' — 두 발췌의 기존 연구 비판과 맞음. 주제 수준"),
        "B": (1, True, True, "A와 같은 주제 수준 공통점. '사회경제적'은 연관(적서 차별·축첩제 등 사회 요인) 쪽에서 다소 넓게 씀"),
        "C": (1, True, True, "조선후기 고전소설 장르 + 조선시대 사회 배경이 소설 형성에 준 영향 — 확인되나 '둘 다 고전소설' 수준"),
    },
    3: {
        "A": (1, False, True, "둘째 문장 '두 논문 모두 … 예술계의 변화가 문학 작품 형성에 미친 영향 분석'은 원본에만 있음 — 우화소설 발췌엔 없음"),
        "A_replay": (1, True, True, "조선후기 사회 부조리·욕망 풍자라는 공통점, 세태·우화소설 장르 차이도 구분 — 두 발췌에서 확인"),
        "B": (0, True, True, "신분제의 동요·사회 부조리·인간의 욕망을 공통점으로 짚음 — 원본(신분제 동요·허위의식)과 연관(계층 갈등·몰락사족/요호부민·권력 욕망)에서 확인"),
        "C": (0, False, True, "'두 논문 모두 다룸 구조·생애자랑·<노섬상좌기>·<두껍전> 등을 언급' — 연관 발췌에만 있는 작품·개념을 원본에도 있다고 지어냄"),
    },
    4: {
        "A": (2, False, True, "'기존 연구 한계·새 방향·다양한 요소의 영향'은 빈말이고, '넓은 맥락에서 소설사를 고찰할 필요성'은 연관 쪽 주장을 원본에도 씌움. 조선후기/조선 초기 시기 차도 놓침"),
        "A_replay": (2, False, True, "A와 같은 빈말 + 같은 '소설사 고찰' 공유 주장(원본 발췌에 없음)"),
        "B": (1, True, True, "형성 요인을 자료별로 나눠(세태소설=사회경제적 배경, 초기 소설=갈래 교섭) 정확히 적음. 공통점은 '소설 형성 요인 분석' 주제 수준"),
        "C": (1, False, False, "'두 논문 모두 사회경제적 배경 … 분석'은 원본에만 해당하고 '장르 개념 명확화'도 연관 발췌와 다름. **세태소설** 마크다운이 평문 카드에 그대로 노출"),
    },
    5: {
        "A": (1, False, False, "연관(기획예산처 재정 역할 재정립) 발췌엔 재정 건전성·예산 집행 문제점 진단이 없음 — 원본 내용을 두 쪽에 씌움. 정책 보고서를 '해당 논문들은'으로 부름"),
        "A_replay": (1, False, False, "투명성·성과 중심 운영은 두 발췌에 있으나 '두 논문 모두 재정 건전성 확보'는 연관 발췌에 없음. 보고서를 '논문'으로 부름"),
        "B": (1, False, False, "'두 논문 모두 재정 건전성·거시경제 정책 효율성' — 연관 발췌에 없음. '공통의 목표를 가지고 유사합니다' 비문, 보고서를 '논문'으로 부름"),
        "C": (0, False, False, "'두 논문은 기획예산처의 재정 역할 재정립 노력…' — 기획예산처 재정립은 연관에만, 재정 건전성은 원본에만 있는데 공통점으로 묶음. 보고서를 '논문'으로 부름"),
    },
    6: {
        "A": (1, True, False, "2003 IMF 보고서/1999년 시점 구분은 정확, 공통점은 '한국 경제 진단·개선' 주제 수준. '원본 논문은…, 연관 논문은…' 프롬프트 내부 이름이 그대로 나오고 백서를 '논문'으로 부름"),
        "A_replay": (1, True, False, "A와 같은 문장 — 근거는 맞으나 '원본 논문/연관 논문' 노출, 백서를 '논문'으로 부름"),
        "B": (1, False, False, "'위기 극복'(백서에만)과 '재정 운영의 문제점'(원본에만)을 공통점으로 합침. 보고서를 '두 논문'으로 부름"),
        "C": (1, False, False, "'두 자료 모두 구조조정·재정 건전성' — 구조조정은 백서에만, 재정 건전성은 원본에만. '주요 규율 대상' 같은 요약 틀 용어가 새어 어색"),
    },
    7: {
        "A": (0, True, False, "'2003년'이라는 같은 시점과 재정 운영 진단을 짚음 — 두 발췌에서 확인. 보고서를 '해당 논문들은'·'두 논문'으로 부름"),
        "A_replay": (0, False, False, "2003년 시점은 맞으나 '두 논문 모두 재정 정책의 효율성을 높이는 데 초점' — 효율성은 원본에만, 연관은 신축적 대응·안정성장. '논문' 호칭"),
        "B": (0, False, False, "'예산 편성 및 집행의 효율성 평가'를 공통으로 돌림 — 연관(경제동향·2003 재정운영) 발췌엔 없음. '두 논문' 호칭"),
        "C": (0, True, False, "2003년 경제 진단·재정 운영이라는 공통점은 확인. 그러나 '주요 규정 사항으로 다루며' 요약 틀 용어 노출, 보고서를 '두 논문'으로 부름"),
    },
    8: {
        "A": (1, False, False, "'두 논문 모두 … 개선 방안을 모색' — 예산개요 참고자료는 현황 자료라 개선 방안이 없음. '원 논문/연관 논문' 노출, 보고서를 '논문'으로 부름"),
        "A_replay": (1, True, False, "예산 집행 투명성·효율성 목표 공유는 두 발췌에서 확인. 그러나 '원본 논문/연관 논문' 노출, 대비('반면')를 '유사성'으로 맺는 어색한 문장"),
        "B": (1, True, False, "A_replay와 같은 내용·근거 확인. '원본 논문/연관 논문' 노출, '내용이 유사합니다' 두 번 반복"),
        "C": (1, True, False, "예산개요의 세입세출 규모 등 사실은 맞음. 그러나 '~ 내용이 유사합니다' 형식 없이 연관 자료 소개 + '논문과 연관성을 갖습니다'로 끝나 형식 위반, 원본 보고서를 '논문'으로 부름"),
    },
    9: {
        "A": (1, False, True, "'두 논문 모두 … 시대적 고뇌와 인간 내면의 심리를 파악'은 연관(세계 상실·내면 심리)에만, '이데올로기의 영향'은 원본에만 — 서로의 내용을 두 쪽에 씌움"),
        "A_replay": (1, False, True, "A와 같은 공유 주장(내면 심리·이데올로기) — 근거 이탈"),
        "B": (1, True, True, "1920·1930년대 근대시, 시대의 사회·문화 상황이 시인 사상·작품에 준 영향이라는 주제 수준 공통점 — 두 발췌에서 대체로 확인"),
        "C": (1, False, False, "표현론(원본)·세계 상실(연관) 귀속은 맞으나 '각 시대 … 시인들의 내면 심리를 연결'은 원본 발췌에 없음. **시론**·**표현론** 마크다운 노출"),
    },
    10: {
        "A": (1, True, True, "'특정 사조·경향에 갇히지 않는 다각적 시각', 사상과 사회·문화 맥락 — 두 발췌에서 확인('1920~30년대'는 연관 발췌의 '일제강점기'를 좁혀 씀)"),
        "A_replay": (1, True, True, "A와 같음 + 이데올로기 영향 — 연관의 민족적 사상·사상적 경향과 맞음"),
        "B": (1, False, True, "'1920년대'를 辛夕汀 연구에도 씌우고, '인간의 내면적 성찰'은 두 발췌 어디에도 뚜렷하지 않음 — 양쪽 용어를 섞은 문장"),
        "C": (0, False, True, "'梁柱東의 개성론(원본에만)·萬海의 민족적 사상(연관에만)을 분석하는 내용이 유사' — 한쪽에만 있는 인물을 공통점으로 묶음"),
    },
    11: {
        "A": (0, False, True, "'김병택 논문이 시론을 통해 … 이광수의 문학사상과 작품에 대한 균형 잡힌 이해를 촉구' — 원본은 이광수 효용론을 여러 이론 중 하나로 다룰 뿐. '1920년대 이론가 주장 분석'도 연관 발췌에 없음"),
        "A_replay": (1, False, True, "'두 논문 모두 1920년대 이론가들의 주장을 분석' — 연관(이광수 소설 비평)에 시기·이론가 분석 없음. '작품 가치 재평가'는 원본에 없음"),
        "B": (0, False, True, "'특히 이광수와 관련된 이론 및 작품' — 원본에서 이광수는 여러 이론가 중 한 명. '작품의 가치를 새롭게 평가'도 원본에 없음"),
        "C": (0, False, True, "'두 자료 모두 梁柱東·김억·박영희·이광수의 주장을 다룸' — 연관 발췌엔 이광수(와 김동인)뿐, 나머지 셋은 원본에만"),
    },
    12: {
        "A": (1, False, True, "시기 구분(1920년대 시론/개화기 신소설)은 정확하나 '두 논문 모두 서구 문학 영향 속 독자성 주목'은 연관에만 — 원본의 '모방론'은 서구 모방이 아니라 문학 이론 용어"),
        "A_replay": (1, False, True, "A와 같은 '서구 영향 + 민족의식' 공유 주장 — 원본 발췌에 없음"),
        "B": (1, False, True, "'두 논문 모두 서구 문학의 영향 속 독자적인 민족적 사유'를 분석 대상으로 — 원본 발췌에 없음"),
        "C": (1, False, True, "'김교봉의 논문은 1920년대 신소설' — 발췌는 개화기 신소설이라 시기를 틀리게 적음(원본 시기를 연관에 씌움)"),
    },
}

VARIANTS = ["A", "A_replay", "B", "C"]
QSHORT = {"조선시대": "Q1 고전소설", "국가 재정": "Q2 재정", "한국 현대": "Q3 현대시"}


def qlabel(q):
    for k, v in QSHORT.items():
        if q.startswith(k):
            return v
    return q


items = []
for i, pair in enumerate(gen, start=1):
    for v in VARIANTS:
        b, g, f, why = J[i][v]
        items.append({
            "pair": i,
            "query": pair["query"],
            "query_label": qlabel(pair["query"]),
            "source_title": pair["source"]["title"],
            "related_title": pair["related"]["title"],
            "screen_equivalent": bool(pair["related"].get("screen_equivalent")),
            "variant": v,
            "text": pair[v],
            "bland": b,
            "grounded": g,
            "form_ok": f,
            "why": why,
        })


def agg(rows):
    n = len(rows)
    if not n:
        return None
    usable = [r for r in rows if r["grounded"] and r["form_ok"] and r["bland"] <= 1]
    return {
        "n": n,
        "bland_mean": round(sum(r["bland"] for r in rows) / n, 3),
        "bland_dist": {str(k): sum(1 for r in rows if r["bland"] == k) for k in (0, 1, 2)},
        "grounded_rate": round(sum(r["grounded"] for r in rows) / n, 3),
        "grounded_count": sum(r["grounded"] for r in rows),
        "form_ok_rate": round(sum(r["form_ok"] for r in rows) / n, 3),
        "form_ok_count": sum(r["form_ok"] for r in rows),
        "shippable_as_is_count": len(usable),
        "shippable_as_is_pairs": [r["pair"] for r in usable],
    }


per_variant = {}
for v in VARIANTS:
    rows = [r for r in items if r["variant"] == v]
    per_variant[v] = {
        "all_12": agg(rows),
        "screen_9": agg([r for r in rows if r["screen_equivalent"]]),
        "by_query": {ql: agg([r for r in rows if r["query_label"] == ql]) for ql in QSHORT.values()},
    }

# A 와 A_replay(같은 프롬프트) 의 판정이 갈린 쌍
flip = [i for i in range(1, 13) if J[i]["A"][1] != J[i]["A_replay"][1]]

out = {
    "judge": "strict_grounding",
    "judged_at": "2026-10-13",
    "inputs": ["collected.json", "generated.json"],
    "basis": "각 문장을 두 자료의 제목 + 서버 발췌(앞 400자, '…'로 잘림)와 대조. 발췌는 적재 때 LLM 이 만든 summary 필드(15권 모두 abstract 비어 있음, '초록 없음' 0건).",
    "criteria": {
        "bland": "0=구체적 공통 항목을 이름으로(거짓 공유여도 구체성은 0), 1=주제·분야 수준, 2=어느 쌍에도 붙일 빈말",
        "grounded": "한쪽에만 있는 내용을 '두 논문 모두'로 씌우거나(pooling) 발췌와 어긋나면 false",
        "form_ok": "평문 카드(RelatedCard.vue)에 그대로 내도 되는가 — 보고서를 '논문'으로 부름, '원본 논문/연관 논문' 노출, ** 마크다운, 비문, 형식 이탈이면 false. 질의1·3 자료는 실제 대학 학위논문이라 '논문' 호칭만으로는 false 아님",
    },
    "items": items,
    "per_variant": per_variant,
    "a_vs_a_replay_grounded_flips": flip,
    "observations": [
        "15권 모두 본문(summary)이 있어 '초록 없음'에서 지어내는 경우는 이번 표본으로 시험되지 않았다(C 의 '초록 없음' 분기도 미시험).",
        "근거 이탈의 거의 전부가 pooling — 한쪽 발췌에만 있는 내용(예술계 변화, 재정 건전성, 내면 심리, 梁柱東·萬海, 서구 영향)을 '두 논문 모두'로 씌운다. 빈 본문 때문이 아니라 '유사점을 말하라'는 과제 자체가 만든다.",
        "C(구체 항목을 이름으로 들라)는 밋밋함을 낮췄지만(bland 평균 0.50) 근거율을 가장 낮췄다(3/12) — 한쪽의 작품·인물·기관 이름을 공통점으로 끌어오고(쌍 3·5·10·11), 쌍 12 는 신소설 시기를 1920년대로 바꿔 적었다. ** 마크다운도 2건.",
        "질의 2(재정 보고서 4쌍)는 네 변형 모두 form_ok 0/4 — B·C 도 시스템 프롬프트의 '두 논문의 연구적 유사성'과 사용자 프롬프트의 '원본 논문/연관 논문/초록'이 남아 '두 논문'이라 부르고, A·A_replay·B 는 '원본 논문/연관 논문'을 그대로 노출한다.",
        "질의 2 의 연관 1위(더 나은 미래를 위한 재정의 역할과 과제) 발췌엔 질의어와 같은 '국가재정운용계획'이 있는데 어느 변형도 짚지 않았다.",
        "같은 프롬프트(A 서버 경로 vs A_replay 직접)인데 근거 판정이 쌍 3·7·8 에서 갈렸다 — temperature 0.2 에서도 둘째 문장의 pooling 여부가 표본마다 바뀐다.",
        "화면에 실제로 뜨는 9쌍만 보면 그대로 내보낼 만한 문장(grounded·form_ok·bland≤1)은 A 2, A_replay 2, B 1, C 0 이다.",
    ],
    "verdict": "",
}

# verdict 는 아래에서 채운다
out["verdict"] = (
    "지금 형태로는 사용자에게 보여 줄 만하지 않다. 네 변형 모두 근거율이 25~50%(A 5/12, A_replay 6/12, B 5/12, C 3/12)이고, "
    "틀린 문장의 대부분은 빈 본문 때문이 아니라 한쪽에만 있는 내용을 '두 논문 모두'로 씌우는 pooling 이다 — 화면에서는 근거 있는 추천 사유처럼 보여 오히려 해롭다. "
    "밋밋함은 생각보다 덜하다(대부분 bland 1, 빈말 2점은 쌍 4 의 A·A_replay 뿐). 구체성을 요구한 C 는 밋밋함을 줄이는 대신 이름을 지어내 근거율이 가장 낮다. "
    "정책 보고서(질의 2)에는 네 변형 모두 형식이 맞지 않는다('논문' 호칭·내부 이름 노출). 넣으려면 프롬프트만 바꾸는 것으로는 부족하고 "
    "(1) '논문' 낱말을 사용자 프롬프트까지 걷어내고 (2) 공유 주장을 두 발췌 모두에 있는 낱말로 묶는 사후 검증이나, 자료별로 따로 말하게 하는 구조(B 쌍 4 처럼)가 먼저 필요하다."
)

with open(os.path.join(HERE, "judge_strict.json"), "w", encoding="utf-8") as fp:
    json.dump(out, fp, ensure_ascii=False, indent=1)

for v in VARIANTS:
    a = per_variant[v]
    print(v, "all", {k: a["all_12"][k] for k in ("bland_mean", "grounded_count", "form_ok_count", "shippable_as_is_pairs")},
          "| screen9", {k: a["screen_9"][k] for k in ("bland_mean", "grounded_count", "form_ok_count", "shippable_as_is_pairs")})
    for ql, s in a["by_query"].items():
        print("   ", ql, s["bland_mean"], s["grounded_count"], s["form_ok_count"])
print("flips", flip)
