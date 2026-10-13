# report.md 를 만든다 — 문장은 generated.json 에서 그대로, 수치는 judge_strict.json·judge_reader.json 의 items 에서 직접 센다.
# 실행: PYTHONIOENCODING=utf-8 python build_report.py
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
G = json.loads((HERE / "generated.json").read_text(encoding="utf-8"))
C = json.loads((HERE / "collected.json").read_text(encoding="utf-8"))
JS = json.loads((HERE / "judge_strict.json").read_text(encoding="utf-8"))
JR = json.loads((HERE / "judge_reader.json").read_text(encoding="utf-8"))

V = ["A", "A_replay", "B", "C"]
VNAME = {"A": "A", "A_replay": "A′(재생성)", "B": "B", "C": "C"}
S = {(i["pair"], i["variant"]): i for i in JS["items"]}
R = {(i["pair"], i["variant"]): i for i in JR["items"]}
assert len(S) == len(R) == 48
for (p, v), it in S.items():
    assert it["text"] == G[p - 1][v] and R[(p, v)]["text"] == G[p - 1][v], (p, v)

PAIRS = list(range(1, 13))
SCREEN = [p for p in PAIRS if G[p - 1]["related"]["screen_equivalent"]]
LIT = [p for p in PAIRS if p not in (5, 6, 7, 8)]
POL = [5, 6, 7, 8]


def esc(t: str) -> str:
    """마크다운이 문장을 바꿔 그리지 않게 기호만 이스케이프(글자는 그대로)."""
    return re.sub(r"([\\*_<>|~`\[\]#])", r"\\\1", t).replace("\n", " ")


def ox(b: bool) -> str:
    return "O" if b else "X"


def trip(i) -> str:
    return f"{i['bland']}·{ox(i['grounded'])}·{ox(i['form_ok'])}"


def judge_cell(p, v) -> str:
    a, b = S[(p, v)], R[(p, v)]
    if trip(a) == trip(b):
        return trip(a)
    return f"엄 {trip(a)} / 독 {trip(b)}"


def ship(i) -> bool:
    return i["grounded"] and i["form_ok"] and i["bland"] <= 1


def agg(J, v, ps):
    it = [J[(p, v)] for p in ps]
    n = len(it)
    return {
        "n": n,
        "bm": sum(i["bland"] for i in it) / n,
        "bd": [sum(1 for i in it if i["bland"] == k) for k in (0, 1, 2)],
        "g": sum(1 for i in it if i["grounded"]),
        "f": sum(1 for i in it if i["form_ok"]),
        "ship": [i["pair"] for i in it if ship(i)],
        "spec": [i["pair"] for i in it if i["grounded"] and i["bland"] == 0],
    }


def two(a, b, fmt=str) -> str:
    return fmt(a) if fmt(a) == fmt(b) else f"{fmt(a)} / {fmt(b)}"


# ── 책 정보 ───────────────────────────────────────────────
BOOK = {}
for q in C["queries"]:
    for t in [q["top1"], *q["related"], *q["related_supplement"]]:
        BOOK[t["cnts_id"]] = t


def book_line(cid) -> str:
    t = BOOK[cid]
    who = t.get("personal_author") or t.get("corporate_author") or "-"
    year = t.get("pub_date") if t.get("pub_date") and t["pub_date"] != "----" else "연도 없음"
    kind = {"literature": "학위논문", "policy": "정책 보고서"}.get(t["doc_type"], t["doc_type"])
    return f"{who} · {t.get('publisher') or '-'} · {year} · {kind}"


QLABEL = {1: "질의 1", 2: "질의 2", 3: "질의 3"}
out: list[str] = []
w = out.append

# ── 머리 ─────────────────────────────────────────────────
w("# 소장자료 관련 자료 '비교 사유' 시험 보고")
w("")
w("2026-10-13 · 코드 머지 없이 시험 · 운영 서버에는 읽기성 호출만 했다(검색 API 가 스스로 남기는 검색 기록 7줄은 예외 — 아래 '시험 방식')")
w("")
w("> **한 줄 결론** — 지금 프롬프트(A·B·C 어느 것)로는 도서 카드에 넣지 않는다. 넣으려면 **B 를 바탕으로** "
  "①시스템·사용자 프롬프트 전체에서 '논문'·'초록' 낱말을 걷어내고 ②한쪽에만 있는 내용을 '두 자료 모두'로 씌우지 못하게 고친 뒤, "
  "③**국문학 학위논문(literature) 짝에만** 보이고 **재정 보고서(policy) 짝과 본문이 빈 자료는 사유를 숨겨(지금의 'AI 요약' 유지)** 다시 시험해 정한다.")
w("")

# 한눈에
a = {v: (agg(S, v, PAIRS), agg(R, v, PAIRS), agg(S, v, SCREEN), agg(R, v, SCREEN)) for v in V}
w("**한눈에** (엄 = 엄격 판정자 / 독 = 독자 판정자, 같으면 한 값)")
w("")
w("| | A | A′ | B | C |")
w("|---|---|---|---|---|")
w("| 그대로 낼 만함 (12쌍) | " + " | ".join(two(len(a[v][0]['ship']), len(a[v][1]['ship'])) for v in V) + " |")
w("| 화면에 뜨는 9쌍 중 | " + " | ".join(two(len(a[v][2]['ship']), len(a[v][3]['ship'])) for v in V) + " |")
w("| 근거 맞음 (12쌍) | " + " | ".join(two(a[v][0]['g'], a[v][1]['g']) for v in V) + " |")
w("| 형식 맞음 (12쌍) | " + " | ".join(two(a[v][0]['f'], a[v][1]['f']) for v in V) + " |")
w("| 재정 보고서 4쌍 형식 | " + " | ".join(two(agg(S, v, POL)['f'], agg(R, v, POL)['f']) for v in V) + " |")
w("| 밋밋함 평균 (0~2) | " + " | ".join(two(a[v][0]['bm'], a[v][1]['bm'], lambda x: f"{x:.2f}") for v in V) + " |")
w("")
w("- **밋밋함은 걱정보다 덜하다** — 대부분 주제 수준(1점)이고 빈말(2점)은 쌍 4 의 A·A′ 두 건뿐.")
w("- **문제는 지어냄인데, 빈 본문 탓이 아니다** — 15권 모두 본문(summary)이 있었다. 틀린 문장 대부분은 한쪽에만 있는 내용을 '두 논문 모두'로 씌운 **교차 귀속**이다.")
w("- **C(구체 항목 강제)가 가장 위험** — 덜 밋밋하지만 한쪽의 작품·인물 이름을 공통점으로 끌어오고 시기까지 바꿨다.")
w("- **A 와 B 는 내용 품질이 사실상 같다** — 근거 맞음 차이(엄 5→5, 독 6→8)가 같은 프롬프트를 다시 돌린 A→A′ 차이(엄 5→6, 독 6→9) 안쪽이다. B 를 바탕으로 삼는 이유는 호칭('해당 자료는')뿐이고, 프롬프트 나머지의 '논문'을 그대로 둬서 그마저 반쪽이다.")
w("- B·C 도 실제로 돌렸다(운영과 같은 vLLM 에 직접). 네 변형 48문장 모두 정상 종료 — 서버에서 따로 돌릴 명령은 없다.")
w("")

# ── 변형·판정 기준 ──────────────────────────────────────────
w("## 변형과 판정 기준")
w("")
w("| 변형 | 무엇 |")
w("|---|---|")
w("| A | 운영 `POST /api/papers/related-reason/stream` 그대로 — 시스템 '학술 논문 전문가 … 해당 논문은 ~ 한 내용이 유사합니다' |")
w("| A′ | A 와 같은 프롬프트를 같은 모델에 한 번 더(재현성 대조) |")
w("| B | 시스템 프롬프트 두 곳만 '소장 자료(도서·학위논문·보고서) 전문가', '해당 자료는' 으로. 시스템의 '두 논문의'와 사용자 메시지의 '원본 논문/연관 논문/초록'은 그대로 |")
w("| C | B + '두 자료가 함께 다루는 대상·시기·작품·제도·방법을 이름으로 하나 이상, 본문에 없는 내용 금지, 초록 없음이면 제목 공통점만' |")
w("")
w("공통: gemma-3-12b · temperature 0.2 · max_tokens 200 · 본문 = abstract → summary → introduction 중 첫 값의 앞 400자(서버 규칙 그대로).")
w("")
w("판정 칸은 **밋밋·근거·형식** 순. 두 판정자가 다르면 `엄 …/독 …` 로 둘 다 적었다.")
w("")
w("- 밋밋 0 = 공통 항목을 이름으로 짚음(틀려도 0) · 1 = 주제 수준 · 2 = 아무 짝에나 붙는 빈말")
w("- 근거 X = 한쪽에만 있는 내용을 두 자료 공통으로 씌우거나 발췌와 어긋남")
w("- 형식 X = 평문 카드에 그대로 못 냄: 정책 보고서를 '논문'이라 부름, '원본/연관 논문' 노출, `**` 마크다운, 비문, 요약 틀말('규율 대상' 등)")
w("- 국문학 짝은 실제 학위논문이라 '논문' 호칭만으로는 X 로 치지 않았다(두 판정자 같음). 일반도서였다면 A 는 틀린 호칭")
w("- **그대로 낼 만함** = 근거 O · 형식 O · 밋밋 ≤ 1")
w("- 엄격 판정자는 발췌와 낱말 단위로 대조, 독자 판정자는 심사위원·이용자 눈높이로 따로 매겼다")
w("")

# ── 질의별 표 ─────────────────────────────────────────────
w("## 질의별 문장과 판정")
w("")
w("문장은 generated.json 원문 그대로다(마크다운 기호 `*` `<` `~` 만 화면에 그대로 보이게 이스케이프).")
w("")
pair = 0
for qi, q in enumerate(C["queries"], start=1):
    top = q["top1"]
    w(f"### {QLABEL[qi]} · {q['query']}")
    w("")
    w(f"**1위** {top['title']} — {book_line(top['cnts_id'])}")
    w("")
    w("| 쌍 | 관련 자료 | 저자·발행·연도·유형 | 화면 |")
    w("|---|---|---|---|")
    rels = [*q["related"], *q["related_supplement"]]
    first_pair = pair + 1
    for k, r in enumerate(rels):
        scr = f"관련 {r['display_rank']}위" if r in q["related"] else "화면 밖(보충)"
        w(f"| {first_pair + k} | {r['title']} | {book_line(r['cnts_id'])} | {scr} |")
    w("")
    if qi == 1:
        w("질의 1 은 관련 자료 API 가 1권만 준다(두 번 보내도 같음). 쌍 2~4 는 메인 검색 2~4위로 채운 **화면에 안 나오는 짝**이다.")
        w("")
    for k, r in enumerate(rels):
        pair += 1
        gi = G[pair - 1]
        assert gi["related"]["id"] == r["cnts_id"], (pair, r["cnts_id"])
        w(f"**쌍 {pair} · {gi['source']['title']} ↔ {gi['related']['title']}**")
        w("")
        w("| 변형 | 문장 | 밋밋·근거·형식 |")
        w("|---|---|---|")
        for v in V:
            w(f"| {VNAME[v]} | {esc(gi[v])} | {judge_cell(pair, v)} |")
        w("")

# ── 변형별 집계 ────────────────────────────────────────────
w("## 변형별 집계")
w("")
w("판정 파일의 48문항에서 직접 셌다. 값은 `엄 / 독`, 같으면 한 값.")
w("")
w("**전체 12쌍**")
w("")
w("| 변형 | 밋밋 평균 | 밋밋 0·1·2 | 근거 O | 형식 O | 구체·근거 | 그대로 낼 만함 |")
w("|---|---|---|---|---|---|---|")
for v in V:
    s, r = agg(S, v, PAIRS), agg(R, v, PAIRS)
    w(f"| {VNAME[v]} | {two(s['bm'], r['bm'], lambda x: f'{x:.2f}')} | "
      f"{two(s['bd'], r['bd'], lambda x: '·'.join(map(str, x)))} | {two(s['g'], r['g'])} | {two(s['f'], r['f'])} | "
      f"{two(len(s['spec']), len(r['spec']))} | {two(s['ship'], r['ship'], lambda x: f'{len(x)} (쌍 ' + ','.join(map(str, x)) + ')' if x else '0')} |")
w("")
w("구체·근거 = 밋밋 0 이면서 근거 O. 실제로 짚은 공통점은 세태소설 개념 재정립(쌍 1), 신분제 동요(쌍 3), 2003년 재정 운영(쌍 7), 이광수(쌍 11, 독자 판정자만 인정)뿐이다.")
w("")
w("**화면에 실제로 뜨는 9쌍**(쌍 1, 5~12)")
w("")
w("| 변형 | 근거 O | 형식 O | 그대로 낼 만함 |")
w("|---|---|---|---|")
for v in V:
    s, r = agg(S, v, SCREEN), agg(R, v, SCREEN)
    w(f"| {VNAME[v]} | {two(s['g'], r['g'])} | {two(s['f'], r['f'])} | "
      f"{two(s['ship'], r['ship'], lambda x: f'{len(x)} (쌍 ' + ','.join(map(str, x)) + ')' if x else '0')} |")
w("")
w("**자료 성격별** — 칸 값은 `근거 O / 형식 O / 낼 만함`")
w("")
w("| 변형 | 국문학 8쌍 · 엄 | 국문학 8쌍 · 독 | 재정 4쌍 · 엄 | 재정 4쌍 · 독 |")
w("|---|---|---|---|---|")
for v in V:
    cells = []
    for J in (S, R):
        x = agg(J, v, LIT)
        cells.append(f"{x['g']} / {x['f']} / {len(x['ship'])}")
    pol = []
    for J in (S, R):
        x = agg(J, v, POL)
        pol.append(f"{x['g']} / {x['f']} / {len(x['ship'])}")
    w(f"| {VNAME[v]} | {cells[0]} | {cells[1]} | {pol[0]} | {pol[1]} |")
w("")
w("재정 보고서 4쌍은 두 판정자 모두 네 변형 형식 0/4 — 보고서를 '두 논문'이라 부르고(B·C 포함), '원본/연관 논문'을 그대로 노출하며(A·A′ 쌍 6·8, B 쌍 8), C 는 요약 틀말('주요 규율 대상'·'주요 규정 사항', 쌍 6·7)이 샌다. 쌍 5 의 연관 자료 본문에 질의어와 같은 '국가재정운용계획'이 있는데 어느 변형도 짚지 않았다.")
w("")

# 형식 새는 것 집계
leak = {}
for v in V:
    leak[v] = {
        "논문": sum(1 for x in G if "논문" in x[v]),
        "원본연관": [i + 1 for i, x in enumerate(G) if re.search(r"(원본|연관|원) 논문", x[v])],
        "md": [i + 1 for i, x in enumerate(G) if "**" in x[v]],
        "틀말": [i + 1 for i, x in enumerate(G) if re.search(r"규율 대상|규정 사항", x[v])],
        "기존": sum(1 for x in G if "기존" in x[v]),
        "끝": sum(1 for x in G if x[v].rstrip().endswith("유사합니다.")),
    }
w("**형식이 새는 곳** (generated.json 에서 셈, 12문장 중)")
w("")
w("| 변형 | '논문' 들어간 문장 | '원본/연관 논문' 노출 | `**` 마크다운 | 요약 틀말 | '기존 …' 틀말 | '유사합니다.'로 끝남 |")
w("|---|---|---|---|---|---|---|")
fmtp = lambda xs: ("쌍 " + ",".join(map(str, xs))) if xs else "0"
for v in V:
    L = leak[v]
    w(f"| {VNAME[v]} | {L['논문']} | {fmtp(L['원본연관'])} | {fmtp(L['md'])} | {fmtp(L['틀말'])} | {L['기존']} | {L['끝']} |")
w("")
w("B·C 도 '논문'이 남는 것은 시스템의 '두 논문의 연구적 유사성'과 사용자 메시지의 '원본 논문/연관 논문'을 그대로 둬서다. 네 변형 모두 거의 매번 둘째 문장을 덧붙여 '~ 유사합니다.' 한 문장 형식을 벗어난다(두 판정자 모두 이것만으로는 형식 X 로 치지 않음). 카드는 `{{ reason }}` 평문이라 `**` 가 그대로 보인다.")
w("")

# 판정자 어긋남
w("### 두 판정자가 어긋난 곳")
w("")
db = [(p, v) for p in PAIRS for v in V if S[(p, v)]["bland"] != R[(p, v)]["bland"]]
dg = [(p, v) for p in PAIRS for v in V if S[(p, v)]["grounded"] != R[(p, v)]["grounded"]]
df = [(p, v) for p in PAIRS for v in V if S[(p, v)]["form_ok"] != R[(p, v)]["form_ok"]]
assert all(not S[k]["grounded"] and R[k]["grounded"] for k in dg)
w(f"48문항 중 형식 {48 - len(df)}/48 일치, 밋밋 {48 - len(db)}/48 일치, 근거 {48 - len(dg)}/48 일치. "
  f"근거가 갈린 {len(dg)}건은 **모두 엄격 X · 독자 O** — 독자 판정자는 막연한 바꿔 말하기를 통과시키고, 엄격 판정자는 한쪽만의 주장이면 깎았다.")
w("")
WHY = {
    (1, "B"): "연관(1930년대) 발췌는 양식 분석뿐이라 '사회 변화와 문학의 연관성'이 없다 ↔ '사회 비판적 성격'은 연관의 '사회의 어두운 단면'으로 확인된다",
    (4, "A"): "'넓은 맥락에서 소설사 고찰'은 연관(갈래 교섭) 쪽 주장을 원본에도 씌운 것 ↔ 빈말이라 근거 문제로 보지 않음(밋밋 2 로 깎음)",
    (4, "A_replay"): "A 와 같음",
    (4, "C"): "'사회경제적 배경 분석'은 원본에만 있다 ↔ 주제 수준이라 통과(형식은 `**` 로 둘 다 X)",
    (6, "B"): "'위기 극복'(백서)과 '재정 운영 문제점'(원본)을 합쳐 공통점으로 만듦 ↔ 주제 수준 묶음으로 봄",
    (7, "A_replay"): "'두 논문 모두 효율성'은 원본에만 있다 ↔ 2003년 공통 시점을 맞게 짚음",
    (9, "C"): "'시인들의 내면 심리'는 원본 발췌에 없다 ↔ 표현론(원본)·세계 상실(연관)을 각자 것으로 바르게 나눔",
    (11, "A_replay"): "연관(이광수 소설 비평)에 1920년대 이론가 분석이 없다 ↔ 이광수 공통점을 맞게 짚음",
    (11, "B"): "원본에서 이광수는 여러 이론가 중 한 명이고 '작품 가치 재평가'는 원본에 없다 ↔ 실제 공통 인물(이광수)을 짚은, 가장 쓸 만한 문장",
}
w("| 쌍·변형 | 엄 / 독 | 갈린 이유 (엄격 ↔ 독자) |")
w("|---|---|---|")
for k in dg:
    w(f"| {k[0]} {VNAME[k[1]]} | {trip(S[k])} / {trip(R[k])} | {WHY[k]} |")
for k in db:
    if k in dg:
        continue
    note = {
        (5, "A_replay"): "'투명성·성과 중심 운영'을 구체 공통점으로 볼지",
        (5, "C"): "'기획예산처'·'재정 건전성'을 이름으로 짚은 것으로 볼지(둘 다 근거 X)",
    }.get(k, "")
    w(f"| {k[0]} {VNAME[k[1]]} | {trip(S[k])} / {trip(R[k])} | 밋밋만 갈림 — {note} |")
w("")
fs = [p for p in PAIRS if S[(p, "A")]["grounded"] != S[(p, "A_replay")]["grounded"]]
fr = [p for p in PAIRS if R[(p, "A")]["grounded"] != R[(p, "A_replay")]["grounded"]]
w(f"**같은 프롬프트도 매번 다르다** — A 와 A′ 의 근거 판정이 엄격 기준 쌍 {','.join(map(str, fs))}, 독자 기준 쌍 {','.join(map(str, fr))} 에서 갈렸다(12쌍 중 3쌍). temperature 0.2 에서도 둘째 문장이 한쪽 내용을 양쪽에 씌우는지가 표본마다 바뀐다.")
w("")

# ── 본문 빈 자료 ───────────────────────────────────────────
books = list(BOOK.values())
n = len(books)
abs_n = sum(1 for t in books if t["body_fields"]["abstract"]["len_stripped"] > 0)
sum_n = sum(1 for t in books if t["body_fields"]["summary"]["len_stripped"] > 0)
intro_n = sum(1 for t in books if t["body_fields"]["introduction"]["len_stripped"] > 0)
empty_n = sum(1 for t in books if t["body_all_empty"])
sl = [t["body_fields"]["summary"]["len"] for t in books]
pick = {}
for t in books:
    pick[t["server_pick_field"]] = pick.get(t["server_pick_field"], 0) + 1
empty_pairs = [i + 1 for i, x in enumerate(G) if x["body_empty"]["source"] or x["body_empty"]["related"]]
w("## 본문이 빈 자료")
w("")
w(f"| 필드 | 채워진 자료 ({n}권 중) | 비고 |")
w("|---|---|---|")
w(f"| abstract | {abs_n} | 모두 비어 있음 |")
w(f"| summary | {sum_n} | {min(sl)}~{max(sl)}자, 적재 때 LLM 이 만든 요약. 서버가 {pick.get('summary', 0)}권 모두 이것을 골라 400자에서 문장 중간에 자름 |")
w(f"| introduction | {intro_n} | 사서 소개글('안녕하세요, 도서관을 찾아주신…' 말투) |")
w(f"| 셋 다 빈 자료 | {empty_n} | → '초록 없음'으로 나간 문장 {len(empty_pairs)}건 |")
w("")
w("- **본문이 빈 자료에서 지어내는지는 이번 표본으로 시험되지 않았다**(C 의 '초록 없음이면 제목만' 분기도 미시험).")
nx = {v: (12 - agg(S, v, PAIRS)["g"], 12 - agg(R, v, PAIRS)["g"]) for v in V}
w("- 대신 본문이 있어도 지어냈다. 근거 X 문장 수(엄 / 독): " + ", ".join(f"{VNAME[v]} {two(*nx[v])}" for v in V)
  + ". 거의 전부가 한쪽에만 있는 내용을 '두 논문 모두'로 씌운 교차 귀속이다.")
w("  - C 쌍 3: 우화소설 쪽에만 있는 '\<노섬상좌기\>' 등 작품명을 두 논문 모두 언급한다고 씀")
w("  - C 쌍 10·11: 원본에만 있는 梁柱東·김억·박영희, 연관에만 있는 萬海를 공통 분석으로 씀")
w("  - C 쌍 12: 본문의 '개화기' 신소설을 '1920년대 신소설'로 바꿈")
w("  - A 쌍 3 · C 쌍 1: 원본에만 있는 '예술계의 변화'를 두 논문 공통으로 씀")
w("- 본문 자체가 AI 요약의 앞 400자라, 사유는 원문이 아니라 'AI 요약끼리의 비교'다. summary 가 비면 서버는 사서 소개글(introduction)로 넘어가는데 그 경우도 시험되지 않았다.")
w("- 다음 시험용으로 본문 빈 소장자료 수를 세는 읽기 쿼리(이번엔 실행 안 함):")
w("")
w("```sql")
w("SELECT doc_type,")
w("       count(*) FILTER (WHERE coalesce(btrim(abstract),'')='' AND coalesce(btrim(summary),'')='') AS no_abs_no_summary,")
w("       count(*) FILTER (WHERE coalesce(btrim(abstract),'')='' AND coalesce(btrim(summary),'')=''")
w("                          AND coalesce(btrim(introduction),'')='') AS body_empty,")
w("       count(*) AS total")
w("FROM library_catalog WHERE is_embedded AND doc_type <> 'paper' GROUP BY doc_type;")
w("```")
w("")

# ── 구현한다면 ─────────────────────────────────────────────
w("## 구현한다면 필요한 것")
w("")
w("**서버**")
w("")
w("- 엔드포인트는 이미 도서 ID 로도 돈다(A 가 그 경로로 12/12 성공 — `BookRepository.get_by_cnts_id` 공용). 도서용 프롬프트 분기만 더하면 된다.")
w("- 도서용 프롬프트: 시스템·사용자 메시지 **양쪽 모두**에서 '논문'·'초록'·'원본/연관'을 빼고('자료 1/자료 2', '내용 요약') '해당 자료는 ~ 한 내용이 유사합니다.' 한 문장으로.")
w("- 교차 귀속 막기: 자료별로 따로 말하게 하거나(B 쌍 4 처럼 '세태소설의 경우 …, 초기 소설의 경우 …'), 생성 뒤 공통이라 쓴 고유명사가 두 발췌에 모두 있는지 검사해 실패하면 숨긴다.")
w("- 본문 없음: abstract·summary 가 둘 다 비면 LLM 을 부르지 않고 빈 응답 → 카드는 지금의 AI 요약/'요약 정보가 없습니다.' 유지.")
w("- doc_type=policy 짝은 사유를 내지 않는다(두 판정자 모두 형식 0/4).")
w("- `_clean_excerpt` 가 `## …` 머리와 `**` 를 지우게(경제백서 1999 요약에 남아 있음), 출력에서도 `**` 제거.")
w("- 비용: 논문 상세는 로드 때 관련 4건을 한꺼번에 스트리밍한다. 도서도 같으면 상세 1회에 LLM 4호출이 적재·검색과 같은 GPU 에 더해진다.")
w("")
w("**프론트** (`frontend/pages/books/[cnts_id].vue`)")
w("")
w("- 관련 카드 상자는 지금 'AI 요약' 하나다. 사유를 넣으면 요약과 사유 중 무엇을 상자에 둘지 기획 결정이 필요하다(논문 화면은 'AI 추천 사유' + 팝업 'AI 추천 사유 & 유사점 분석').")
w("- 논문 화면의 `streamRelatedReason`(sessionStorage 캐시·로딩 표시)을 그대로 옮기고, 사유가 비면 AI 요약으로 대신한다.")
w("- 별건: 질의 1 처럼 관련 자료 검색(1위 제목으로 검색)이 1권만 주는 경우가 있다 — 비교 사유보다 먼저 손볼 일.")
w("")

# ── 시험 방식 ─────────────────────────────────────────────
w("## 시험 방식")
w("")
w("- **코드 머지·저장소 수정 없음.** 저장소(.worktrees/fix-live)는 읽기만 했고, 변형 프롬프트는 시험 스크립트 안에서만 만들었다.")
w("- **운영 서버(:92)에는 읽기성 호출만**: 상세 `GET /api/books/{id}` 15권, `POST /api/books/search` 7회, `POST /api/papers/related-reason/stream` 12회(A). "
  "단, 검색 API 는 서버가 호출마다 search_history 에 한 줄씩 남긴다(7줄, x-session-id=trial-book-related-20261013) — 피할 수 없는 기록이다.")
w("- A′·B·C 36문장은 운영 fastapi 가 쓰는 같은 vLLM(gemma-3-12b, :18080)에 직접 보냈다. 모두 정상 종료(200토큰에 안 잘림), 호출당 0.7~1.8초.")
w("- 호출은 순차로, 사이마다 1초 쉬었다. 연구 생성·승인·삭제·DB 쓰기·컨테이너 조작은 하지 않았다.")
w("- 표본 한계: 짝 12개(국문학 8 · 재정 4), 쌍마다 1회 생성. 질의 1 의 쌍 2~4 는 화면에 안 나오는 보충 짝.")
w("")
w("## 파일")
w("")
w("같은 폴더 `scratchpad/book_related_trial/`")
w("")
w("| 파일 | 내용 |")
w("|---|---|")
w("| collected.json | 질의·1위·관련 자료·본문 필드·서버 발췌 |")
w("| generated.json | 12쌍 × 4변형 문장과 프롬프트 |")
w("| judge_strict.json · judge_reader.json | 두 판정자의 48문항 판정 |")
w("| build_report.py | 이 보고서를 만든 스크립트(수치는 판정 파일에서 직접 셈) |")
w("")

(HERE / "report.md").write_text("\n".join(out), encoding="utf-8")
print("ok", len("\n".join(out)), "chars")
