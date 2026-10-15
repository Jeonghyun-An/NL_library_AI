# 딥리서치 종합 프롬프트 A/B (2026-10-14)

딥리서치 보고서의 절(하위질문 하나)마다 도입·논문별 요약·향후 과제를 쓰는 종합 프롬프트
`app/domains/nl_library/prompts/research_synthesize.yaml` 을 운영 보고서 4건으로 다시 만들어 견준 1회성 실험이다.
운영 DB 에는 쓰지 않았고 운영 API 에는 보고서를 받는 GET 만 보냈다. 다시 만들기는 운영과 같은 vLLM(gemma-3-12b)에 직접 보냈다.

결론:

- **1차 — focus 채택.** base(당시 프롬프트) 대비 블라인드 판정 **10승 0패 2무**(r0 회차만 — 보고서 4건 4짝 × 판정자 3 = 12판정),
  자동 지표 기준(보고서 4건 × 2회)도 통과한 것은 셋 가운데 focus 하나다 → `fd360d1`. attrib·concise 는 판정 기준은
  넘었지만 자동 지표 기준(무효 인용 / 형식 문제·빈 요약)에서 떨어졌다.
- **2차 — focus2 미채택.** focus 대비 판정 **15승 7패 2무**(보고서 4건 × 2회 = 8짝 × 판정자 3) 였지만 형식 문제 호출 0→1·
  빈 요약 0→1(같은 한 건)로 자동 지표 기준에서 떨어졌고, 요약을 게재 학술지 이름으로 채우는 군말이 0→19편 나왔다.
- A/B 에서 드러난 결함 가운데 셋은 프롬프트 대신 코드로 막았다: 대목 속 남의 번호 인용 지우기(`73feb90` — 1차에서 드러남),
  요약 빠지면 재요청·도입 있는 응답 우선(`8511fca`·`24ac620`), 모델에 넘기는 대목을 400자 안 문장 끝에서 자르기
  (`4998487`·`a818aa1`·`4bd51b0`).
- 이 모두가 dev `f06b814`(브랜치 `fix/round06-live-check`)에 머지됐고 **운영 배포됨(2026-10-15, 사용자 — 어느 컨테이너까지
  했는지는 사용자 확인 전)**. 서버의 이미지 digest·확인 grep 출력도 아직 받지 않았다 — 아래 '반영'.

수치의 범위: 자동 지표는 운영 보고서 4건(보고서마다 6절) × 2회(r0·r1)다. 판정은 1차가 r0 회차만(후보마다 4짝 × 판정자 3),
2차가 4건 × 2회 = 8짝 × 판정자 3 이다. 생성 모델은 gemma-3-12b(temperature 0.3), 판정자는 사람이 아닌 LLM 에이전트 셋이다.
운영 화면에서 다시 잰 값이 아니다(한계 절).

## 왜

운영 E2E 확인(10-14)에서 보고서 절 도입이 '꾸준히 진행되어 왔다' 류 분야 일반론이나 하위질문 문구 되받기로 시작하고,
근거 표시 없는 문장과 절 사이 되풀이가 많았다. 대목 고르기(`7546348`)·되풀이 문장 지우기(`40877dd`) 같은 코드 쪽 수정은
3차(dev `cb12bcb`)에 넣었고, 남은 것은 프롬프트 문구였다. 그래서 프롬프트만 바꾼 변형 셋을 같은 코드·같은 입력으로 겨뤘다.

## 방법

### 입력 — 운영 보고서 4건

| 태그 | job_id | 질문 | 절 | 근거 논문 |
|---|---|---|---|---|
| 630e (다문화) | `630e0d65-bd09-4429-9eda-e00d85dbff6b` | 다문화가정 아동의 언어 발달에 관한 연구 동향을 알려줘 | 6 | 13 |
| d60a (노인-동향) | `d60a5dc1-76a4-4506-88ec-dfbfa49f93f7` | 노인의 우울과 사회적 지지에 관한 연구 동향을 알려줘 | 6 | 12 |
| 85d2 (도서관) | `85d2bc0e-541d-4d27-a98f-c0b8fe262701` | 공공도서관 서비스 품질 평가 연구를 정리해 줘 | 6 | 13 |
| 9ba1 (노인-궁금) | `9ba10849-36e2-417a-bc59-abec8e002c2c` | 노인의 우울과 사회적 지지에 관한 연구가 궁금해 | 6 | 14 |

`rebuild.py` 가 GET `/api/research/{job_id}` 응답의 `report`(절의 하위질문·절별 대목 매핑·근거 청크)로 `ResearchState` 를
다시 만든다. 탐색은 다시 하지 않는다 — 네 변형이 같은 근거·같은 대목을 받는다.

### 생성 — `run_ab.py`

- 실제 `synthesize()` 코드를 그대로 돌리고, synthesizer 모듈의 `get_prompt` 이름 하나만 잡마다 변형 yaml 로 갈아 끼운다
  (contextvar). LLM 호출은 gemma 에 직접 보내며 절마다 원문·형식 문제를 기록한다. 코드는 1차 `0262673`
  (= `fd360d1` 의 코드 — `fd360d1` 은 yaml·테스트만 바꿨다), 2차 `3555e82`(그때 브랜치 HEAD — 테스트만 바꾼 커밋이고, 바로 앞
  `73feb90` 의 번호 인용 지우기가 2차 코드에 들어 있다).
- 보고서 4건 × 2회(r0·r1) × 변형. 1차 4변형 32잡(192호출), 2차 2변형 16잡(96호출). 동시 요청 4 이하.
- `run_prompt.py` 는 변형을 만들며 630e 한 건으로 형식만 확인한 설계 단계 도구다(`variants.md`).

### 변형

| 변형 | 파일 | 방향 |
|---|---|---|
| base | `base.yaml` | 당시 저장소 프롬프트(`0262673` 의 `research_synthesize.yaml` 과 바이트 단위로 같다) |
| **focus** (A) | `variant_focus.yaml` | 절은 하위질문 하나에 답하는 자리 — intro 를 '답 문단'으로 못박고 첫 문장부터 구체적 발견 + [E#], 일반론·되받기·예고·중요성 맺음 금지, 도입 4문장 상한. **채택본 — 지금 저장소 yaml 과 바이트 단위로 같다** |
| attrib (B) | `variant_attrib.yaml` | 출처 정확성 — 재인용(저자·연도로 전한 남의 결과)을 근거 논문 결과로 쓰지 않기, 모든 문장에 번호 |
| concise (C) | `variant_concise.yaml` | 간결 학술 요약체 — 근거 편수 n 에 비례한 문장 수 상한(Jinja), 한 문장 한 주장 |
| focus2 (2차) | `variant_focus2.yaml` | focus + 재인용·한 논문 일반화 규칙, 도입 3~4문장 상한, 요약 2~3문장, 남의 번호 옮기지 않기 (system 1,250→2,119자) |

변형마다 바꾼 문구·초안 경과·630e 형식 확인 숫자는 `variants.md`(설계 기록). 남은 초안은 `variant_focus_draft1.yaml`·
`variant_concise_draft1.yaml`·`variant_concise_draft2.yaml` 뿐이다.

### 블라인드 판정 — `make_judge.py`·`make_judge_r2.py`

- 짝마다 변형 이름을 지우고 X·Y 로 둔다. 배정은 보고서별 고정 시드, 짝 순서도 고정 시드로 섞는다. 짝↔변형 대응
  (`judge_key.json`·`r2_key.json`)은 판정자에게 주지 않았다.
- 판정자에게 준 묶음: 연구 질문, 절마다 하위질문·근거 서지·모델이 실제로 읽은 대목 창·X 출력·Y 출력(화면에 나가는 최종 절 —
  도입·요약·향후 과제). 한계 섹션은 싣지 않았다(자동 지표를 드러내므로).
- 판정자 셋 — reader(읽는 사람)·fact(근거 대목과 사실 대조)·editor(편집) — 은 역할 지시를 달리 받은 LLM 에이전트다. 짝마다
  X·Y·비김 중 하나를 골랐다(`tally/votes*.json`).
- 1차: r0 회차만, 후보마다 보고서 4건에 1짝(후보 대 base) = 12짝 × 3명. 2차: 보고서 4건 × 2회 = 8짝 × 3명이고,
  보고서마다 한 회차는 focus 를 X 에, 다른 회차는 Y 에 둬 위치 편향을 상쇄했다.

### 자동 지표 — `ab_metrics.py`(v1, `--v2`)·`r2_metrics.py`

생성 원문과 최종 절에서 센다: 무효 인용(입력에 없는 [E#])·형식 문제 호출·빈 요약·재시도·실패 절·길이 잘림, 근거 표시 없는 문장,
첫 문장/도입 일반론(v1·v2 정규식), 하위질문 되받기, 절 사이 유사도(0.7 이상 쌍), 남의 번호 인용 '[3]', 재인용 옮김·오귀속 의심,
도입·요약 문장 수, 게재지 군말(`tally/journal_r2.py`) 등. 모두 정규식·difflib 유사도 근사치다.

### 채택 기준 — 두 관문을 모두 넘어야 채택

1. **판정 기준** — 1차: 승 ≥ 패 × 2, 그리고 사실 검증자(fact)에게 진 수가 이긴 수보다 많지 않을 것.
   2차: 승 > 패, 같은 fact 조건.
2. **자동 지표 기준** — 무효 인용·형식 문제 호출·빈 요약·재시도·실패 절·근거 표시 없는 문장이 비교 대상(1차 base,
   2차 focus)보다 나쁘지 않을 것(변형마다 8잡 합). 경계에서도 글자 그대로 적용했다.

1차에서 둘 이상이 두 관문을 넘으면 합친 yaml 을 시험할 계획이었으나 넘은 것은 focus 하나였다.

## 결과

### 1차 — 후보 대 base (`result.md`, `tally/tally_out.txt`, `metrics_table.txt`)

| 변형 | 판정 합계 (승-패-비김) | fact | 판정 기준 | 무효 인용 (8잡 합) | 형식 문제 호출 | 빈 요약 | 근거 표시 없는 문장 (8잡 합) | 자동 지표 기준 | 결론 |
|---|---|---|---|---|---|---|---|---|---|
| base | — | — | — | 2 | 1 | 1 | 28 | — | — |
| **focus** | **10-0-2** | 2-0-2 | 통과 | 0 | 0 | 0 | 6 | 통과 | **채택** |
| attrib | 9-2-1 | 4-0-0 | 통과 | **4** | 0 | 0 | 3 | 미달 | 미채택 |
| concise | 10-1-1 | 4-0-0 | 통과 | 2 | **2** | **2** | 2 | 미달 | 미채택 |

focus 대 base, 보고서 1건(6절)당 평균(4건 × 2회 — 보고서마다 회차 평균을 낸 뒤 4건 평균, `metrics_table.txt`·`metrics_v2.txt`):

| 지표 | base | focus |
|---|---|---|
| 근거 표시 없는 문장 | 3.5 | 0.8 |
| 첫 문장이 일반론인 절 (v1 / v2 정규식) | 3.8 / 3.9 | 0 / 0.6 |
| 도입의 일반론 문장 (v1) | 5.4 | 0.4 |
| '본 절에서는' 류 군말 (원출력) | 1.0 | 0 |
| 절 사이 0.7 이상 쌍 / 그중 일반론 | 1.8 / 1.2 | 0.9 / 0 |
| 무효 인용 / 형식 문제 호출 | 0.2 / 0.1 | 0 / 0 |
| 도입 문장/절 · 도입 4문장 초과 절 비율 | 3.3 · 4% | 4.3 · **42%** |
| 요약 문장/편 · 1문장 요약 비율 | 2.1 · 7% | 1.6 · **45%** |
| 재인용 오귀속 의심 | 6.1 | 6.4 |

### 2차 — focus2 대 focus (`result_r2.md`, `tally/tally_r2_out.txt`·`gate_r2_out.txt`·`journal_r2_out.txt`, `r2_metrics.txt`)

| 항목 | focus | focus2 |
|---|---|---|
| 판정 합계 (focus2 기준 승-패-비김) | — | **15-7-2** (reader 5-3-0 · fact 4-3-1 · editor 6-1-1) → 판정 기준 통과 |
| 형식 문제 호출 / 빈 요약 (8잡 합) | 0/48 · 0 | **1/48 · 1** (85d2 r1 3절이 summaries 에서 E11 을 빠뜨림) → 자동 지표 기준 미달 |
| 1문장 요약 (8잡 합) | 109/236 (46%) | 76/235 (32%) |
| 도입 4문장 초과 절 | 17/48 (35%) | 6/48 (12%) |
| 게재지 군말 요약 ('○○ 학술지에 게재된 연구로' 꼴) | 0/236 | **19/236** |

보고서별로 갈렸다 — focus2 를 다듬을 때 쓴 630e·9ba1 에서는 5-6-1(630e 는 1-4-1), 안 본 d60a·85d2 에서는 10-1-1.
630e 에서 진 까닭은 게재지 군말과 그로 인한 오독(fact·editor 지적)이다.

### 채택하지 않은 까닭 요약

- attrib: 무효 인용 2→4(모두 9ba1). 재인용 지표도 base 보다 나빴다(재인용 옮김 8.2→10.9, 오귀속 의심 6.1→8.4).
- concise: 빈 요약 1→2 — 48호출 중 1건 차의 경계지만 기준을 글자 그대로 적용했다. 절이 얇아진다는 판정 지적도 있었다.
- focus2: 위 형식 문제 1건이 기준 미달이고, 기준 밖 결함(게재지 군말 19편, 도입 끝에 [E#] 만 남는 꼴)도 같은 쪽을 가리켰다.
  쓸 만한 부분(도입 상한·요약 길이)은 다시 시험하지 않았다.

### 남은 약점 (focus, 지금 운영 후보)

도입 4문장 초과 42%·1문장 요약 45%(규칙은 2~3문장), 한 논문의 표본을 분야 전체로 넓히는 일반화(630e 3절 'E18 의 2~6세
765명' 을 '주요 연구 대상 집단' 으로 — 모든 변형·초안에서 나옴), 재인용 오귀속(6.1→6.4 그대로). 참고문헌뿐인 대목에서 결과를
지어내는 문제는 프롬프트가 아니라 대목 고르기·참고문헌 조각 판정(`research/bibliography-chunk-filter/`) 쪽이다.

## 반영 — 운영 배포(10-15)

| 차수 | dev 머지 | 내용 | 다시 만들 컨테이너 | 이미지 | 배포 |
|---|---|---|---|---|---|
| 3차 | `cb12bcb` | 이어가기 묶음 최소 2편·연구 공백 절 씨앗·한계 줄 짧게·짧은 참고문헌 조각 판정·카드 키워드 강조(무른 검사 settle)·절 생성 대목을 논문마다 서술 대목으로·절 사이 되풀이 지움(drop_repeats) | fastapi·celery-research·celery-research-plan | fastapi `sha256:99c360b2…` | 운영 배포됨(2026-10-15, 사용자 — 어느 컨테이너까지 했는지는 사용자 확인 전) |
| 4차 | `f06b814` | 이 실험: focus 프롬프트(`fd360d1`)·남의 번호 인용 지우기(`73feb90`)·요약 재요청(`8511fca`·`24ac620`)·대목 문장 끝 자르기(`4998487`·`a818aa1`·`4bd51b0`) | celery-research (3차를 안 올렸으면 위 셋) | fastapi `sha256:b8dd67fb…` | 운영 배포됨(2026-10-15, 사용자 — 어느 컨테이너까지 했는지는 사용자 확인 전) |

배포는 사용자가 2026-10-15 11:13 KST 에 '배포 했어'라고 답한 것이다 — 표의 '다시 만들 컨테이너' 가운데 어느 것까지
다시 만들었는지는 사용자 확인 전이다. 서버에서 낸 이미지 digest·확인 grep(`research_synthesize.yaml` 의 '하위질문에 대한 답',
`citations.py` 의 `strip_numbered_refs`) 출력은 아직 받지 않았다.

yaml 은 볼륨이 아니라 이미지(`landsoftdocker/nl-lib-fastapi`)에 들어 있어 이미지를 다시 빌드해야 한다. 인덱싱이 도는 중에는
올리지 않는다(`docs/ops/recurring-gotchas.md` 16번 — 같은 이미지를 쓰는 적재 워커 재생성).

## 1회성 확인 (`checks/`)

### `checks/excerpt-cut/` — 대목을 문장 끝에서 자르기 전후 (`4998487`·`a818aa1`·`4bd51b0`)

운영 4건의 대목으로 예전 규칙(400자에서 그냥 자르기)과 지금 `excerpt_text`·`_narrative` 를 견준다.
`compare.txt` 는 지금 코드(dev `f06b814` 와 같은 app — 마지막 규칙 변경 `4bd51b0`)로 다시 센 것이다.

- 모델이 읽은 대목 77건 중 400자를 넘는 61건: 59건은 문장 끝에서, 2건(표·목차)은 400자에서 잘렸다. 글자 합 29,118→25,130.
- 근거 대목 125건 중 서술 판정이 바뀐 것은 1건(`KCI_FI002267397__0003` — 저작권 고지 대목, 논문 서술이 아니다).
- `short.txt`: 자르지 않는 400자 이하 대목 43건 중 문장 끝으로 끝나지 않는 것 4건(목차·참고문헌 조각).
- 대목 끝에 붙은 저자 이메일은 `<이메일>` 로 가렸다(`compare.py` 가 쓸 때 가린다).

### `checks/figleak/` — 이어가기 절 수치 칩 새기·'본 연구' 지칭 (2차 `45f0d00`·`ce9bd3f`·`780bf13`·`b2aa84e`)

운영 이어가기 보고서 d60a5dc1 의 절 prior.g2(논문 1편, gen 102)에서 gemma 가 수치 목록을 문장으로 옮겨 값 칩
'1·2017·198,518' 이 글에 박히고, 근거 논문을 '본 연구' 로 불렀다. 같은 입력으로 고치기 전 프롬프트(`prior_before.yaml` =
`1c0b0a6` 의 `research_section_prior.yaml`)와 고친 뒤를 8회씩 불러 견줬다(`measure_g2_out.txt`).
'고친 뒤' 는 `b2aa84e` 의 app 이다 — 측정(10-14 18:04)은 이 커밋(17:58, `research_section_prior.yaml`·`markers.py` 를 바꿈) 뒤에
했고, dev 머지 `65907eb` 는 측정이 쓰는 파일(프롬프트·`section.py`·`section_input.py`·`markers.py`)이 이것과 같다.
`measure_g2.py` 는 '뒤' 프롬프트·채점(`EXECUTOR`)·입력 함수를 **돌리는 폴더의 app** 에서 가져오므로 재현은 이 커밋으로 못박는다(재현 8).
보관하며 확인한 것(10-15): `b2aa84e`·`65907eb`·지금 app(dev `f06b814` 와 같은 내용)에서 이 입력으로 만든 앞·뒤 프롬프트가
같고, 10-14 생성 원문을 다시 채점한 값도 `measure_g2.json` 과 같았다(그 뒤 `da9e9cd` 가 `section_input.py`·`section.py` 를
바꿨지만 이 입력에는 닿지 않았다 — 다른 입력·다른 커밋에서도 같다는 뜻은 아니다).

- 원문에 [F#] 가 나온 회차 0/8 → 0/8 — 운영의 새기는 고치기 전에도 8회 안에서 다시 나오지 않아, 프롬프트만으로 막았다고 볼
  근거는 없다. 새기는 생성 뒤 검사(`45f0d00`)가 따로 막는다.
- 원문 문단 수 3 → 2(8회 모두 — 논문 1편이면 1~2문단).
- 근거 논문을 '본/이 연구' 로 부른 회차 8/8 → 1/8. 나머지 7회의 '본 연구' 는 계획서 자신을 가리킨다(허용한 쓰임).
  `measure_g2_out.txt` 의 앞뒤 글자를 보고 눈으로 가른 것이다.
- `proposal.json` 은 GET `/api/research/d60a5dc1-…/proposal` 응답에서 `measure_g2.py` 가 읽는 키만 남긴 사본이다.
  `src_g2.json` 은 GET `…/sections/prior.g2/sources?gen=102` 응답(초록·대목)이다.

## 파일

| 파일 | 역할 |
|---|---|
| `rebuild.py` | 운영 보고서 JSON → `ResearchState`. 경로는 환경 변수 `SYNTH_AB_APP`·`SYNTH_AB_JOBS`(아래 '재현') |
| `run_ab.py` | A/B 생성 하네스(1차·2차). `--out`·`--yaml 변형=경로|repo` |
| `run_prompt.py` | 설계 단계 — yaml 하나를 630e 로 N회 돌려 형식 확인 |
| `base.yaml`·`variant_*.yaml` | 변형(초안 3벌 포함) |
| `variants.md` | 변형 설계 기록 — 바꾼 문구, 630e 형식 확인, 초안 경과 |
| `ab_metrics.py` | 1차 지표. 인자 없으면 v1 표를 화면에(= `metrics_table.txt`), `--v2` 면 `metrics_v2.txt`·`ab_metrics_v2.json` |
| `r2_metrics.py` | 2차 지표 → `r2_metrics.txt`·`r2_metrics.json` |
| `make_judge.py`·`make_judge_r2.py` | 블라인드 판정 묶음·짝 키 만들기 |
| `judge_key.json`·`r2_key.json` | 짝 → 보고서·회차·X/Y 변형·원본 파일·시드 |
| `judge_pairs.slim.json`·`r2_pairs.slim.json` | 판정자에게 준 묶음에서 대목 원문을 `chunk_id`·글자 수로 바꾼 사본(`slim_pairs.py`) |
| `tally/` | 투표(`votes*.json`)와 집계·자동 지표 관문·게재지 군말 스크립트와 그 출력(`*_out.txt`) |
| `result.md`·`result_r2.md` | 1·2차 판정 집계와 반영 기록(10-14 당시 그대로, 경로만 고침) |
| `gen_index.py`·`gen_index.tsv` | 넣지 않은 생성 원문 123개 회차의 목록(변형·보고서·회차·형식 문제·걸린 초·바이트) |
| `jobs.sha256` | 10-14 에 받은 운영 보고서 JSON 4건의 sha256 |
| `checks/` | 위 '1회성 확인' |
| `.gitignore` | 재현하며 생기는 `jobs/`·`gen_ab/`·`gen_r2/`·설계 단계 `gen_*.json`·`focus2/`·`--dump` 덤프(`dump*.txt`·`*_dump*`)·원본 판정 묶음 등을 커밋하지 않게 한다 |
| `.gitattributes` | `jobs.sha256` 을 늘 LF 로 받게 한다 — Windows(`core.autocrlf=true`)에서 CRLF 로 풀리면 `sha256sum -c` 가 파일 이름 끝의 `\r` 때문에 4건 모두 실패한다(재현 1 은 `tr -d '\r'` 로도 막는다) |

표 머리의 `prompt_ab/` 는 당시 이 폴더의 이름이다(scratchpad).

## 넣지 않은 것

| 무엇 | 크기 | 까닭 · 대신 |
|---|---|---|
| 운영 보고서 원본 `jobs/job_*.json` 4건 | 약 520KB | 논문 대목 원문이 대부분이고 대목 끝 저자 연락처가 있다. GET 으로 다시 받는다(재현 1) — `jobs.sha256` 으로 같은지 확인 |
| 생성 원문 `gen_ab/`(32잡)·`gen_r2/`(16잡)·설계 단계 `gen_*.json`(19개)·focus2 초안 `focus2/gen/`(52회차) | 약 2.9MB·1.5MB·0.9MB·4.8MB | 대목 원문(입력)과 모델 원문이 들어 있고 크다. 회차마다 한 줄은 `gen_index.tsv`, 판정자가 본 최종 출력은 `*.slim.json` 에 있다 |
| 판정 묶음 원본 `judge_pairs.json`·`r2_pairs.json` | 776KB·524KB | 대목 원문(1차 133,746자·2차 89,164자)을 뺀 `*.slim.json` 만 넣었다 |
| `ab_metrics.json`(v1 잡별 상세) | 340KB | 재생성된다(재현 4) |
| focus2 초안 yaml 30벌(`draft1~11`·`x_*`)과 그 스크립트, `ab_metrics_v1.py`·`run_ab_r1.py`(옛 사본), `concise_stats.py`·`_concise_driver.sh`, 덤프(`dump_*.txt`·`excerpts_all.txt`), 실행 로그(`run_*.log` — 잡마다 걸린 초·형식 문제는 `gen_index.tsv` 에 같은 값이 있다) | — | 설계 단계 도구·옛 사본·대목 원문 덤프·로그. 숫자는 `variants.md`·`result*.md` 에 남아 있다 |
| figleak 의 `measure_g2.json`(생성 원문)·덤프·시제품 | 36KB 등 | 줄인 결과 `measure_g2_out.txt`(`summarize_g2.py`) |
| 3차 확인(`groupsize/` — 묶음 최소 2편 `MIN_GROUP_PAPERS` 의 근거 `748b9f2`, `synth_impl/` 의 현행 출력 분석) | — | 운영 proposal·생성 원문이 대부분. 결과는 해당 커밋 메시지에만 있고 **저장소만으로는 다시 셀 수 없다** |

**설계 단계 수치는 저장소만으로 다시 셀 수 없다.** `variants.md` 의 형식 확인·'참고 지표'(첫 문장이 일반론인 절 15/18 → 2/12,
concise 의 도입·과제 무표기 문장 9 → 1, focus draft3 의 1문장 요약 60편 중 47편, attrib 의 '저자(연도)' 표기 0 → 6 등)와
`result_r2.md` 4절의 설계 단계 수치(focus2 반복 루프 절 2/44, 학술지명 출현 0→6)는 넣지 않은 스크립트(`synth_impl/analyze.py`·
`concise_stats.py`, `focus2/` 의 `f2_metrics.py`·`firsts.py`·`sumdist.py`·`run_f2.py` 등)가 넣지 않은
생성 원문(현행 3회 `synth_impl/gen_new.json`·설계 단계 `gen_*.json`·`focus2/gen/`)을 읽어 낸 값이다. 생성은 temperature 0.3 이라
같은 값으로 다시 나오지 않는다. **이 수치들은 저장소만으로는 재현할 수 없다** — 설계 단계 탐색값이라 변형을 다듬는 데만 썼고,
채택 판단은 위 '결과' 의 A/B 표(자동 지표 4건 × 2회, 판정 1차 r0 4짝·2차 8짝 × 판정자 3)로 했다.

## 재현

모든 명령은 이 폴더에서, `PYTHONIOENCODING=utf-8 python …` 으로 돌린다. 운영 DB 에는 쓰지 않는다.

1. **운영 보고서 받기(GET 만)** — 저장소의 다른 기록과 같은 주소다.

   ```bash
   mkdir -p jobs
   for id in 630e0d65-bd09-4429-9eda-e00d85dbff6b d60a5dc1-76a4-4506-88ec-dfbfa49f93f7 \
             85d2bc0e-541d-4d27-a98f-c0b8fe262701 9ba10849-36e2-417a-bc59-abec8e002c2c; do
     curl -s "http://192.168.12.57:92/api/research/$id" -o "jobs/job_$id.json"
   done
   tr -d '\r' < jobs.sha256 | sha256sum -c   # 다르면 그 뒤 보고서가 바뀐 것이다(다시 생성·재시도)
   ```

   다른 폴더에 두면 `SYNTH_AB_JOBS=<폴더>`. `tr -d '\r'` 은 `jobs.sha256` 이 CRLF 로 풀린 체크아웃(`.gitattributes` 가 들어오기
   전에 Windows `core.autocrlf=true` 로 받은 것 등)에서도 파일 이름 끝의 `\r` 없이 읽게 한다.
2. **코드** — `SYNTH_AB_APP` 이 없으면 이 저장소의 `app/` 를 쓴다. 측정 당시 코드로 돌리려면
   `git archive 0262673 app | tar -x -C /tmp/ab-1` (1차) 또는 `3555e82` (2차 측정 코드 HEAD — 테스트 보강 커밋이고 번호 인용
   지우기는 그 앞 `73feb90`) 로 푼 뒤 `SYNTH_AB_APP=/tmp/ab-1/app`.
   (`run_ab.py` 는 그 폴더의 git HEAD 를 `code_head` 로 남기는데, 푼 폴더에는 git 이 없어 `?` 로 남는다.)
3. **생성** — LLM 주소는 `SYNTH_AB_LLM_URL`(기본 운영 vLLM `http://192.168.12.57:18080/v1/chat/completions`, 모델 `gemma-3-12b`).
   운영과 같은 vLLM 에 동시 4요청을 보내므로 사람이 확인하고 돌린다.
   - 1차: `python run_ab.py 2` → `gen_ab/`
   - 2차: `python run_ab.py 2 focus focus2 --out gen_r2 --yaml focus=repo` → `gen_r2/`
   - temperature 0.3 이라 생성은 같은 값으로 다시 나오지 않는다. 아래 4~6 은 10-14 생성 원문으로 다시 돌리면 같은 출력이 나온다.
4. **지표** — `python ab_metrics.py > metrics_table.txt`(v1, `ab_metrics.json` 도 씀) · `python ab_metrics.py --v2` ·
   `python r2_metrics.py`.
5. **판정 묶음** — `python make_judge.py`·`python make_judge_r2.py`(원본 묶음과 짝 키) →
   `python slim_pairs.py judge_pairs.json judge_key.json . judge_pairs.slim.json`(2차도 같은 꼴).
6. **집계** — `python tally/tally.py > tally/tally_out.txt` · `tally/tally_r2.py` · `tally/gate_r2.py`(`r2_metrics.json` 을 읽음) ·
   `tally/journal_r2.py`(`gen_r2/` 를 읽음). 투표 파일만 있으면 1~3 없이도 판정 집계는 나온다.
7. **생성 원문 목록** — 생성 폴더에서 `python <이 폴더>/gen_index.py . gen_ab gen_r2 gen_*.json focus2/gen > gen_index.tsv`.
8. **checks** — `python checks/excerpt-cut/compare.py jobs checks/excerpt-cut/compare.txt` ·
   `python checks/excerpt-cut/short.py jobs checks/excerpt-cut/short.txt`.
   figleak 은 '뒤' 를 측정 때 코드인 `b2aa84e` 의 app(위 figleak 절)으로 못박는다 — 그 뒤 `da9e9cd` 등에서
   `section_input.py`·`section.py` 가 또 바뀌었으므로 지금 `app/` 로 돌리지 않는다. 운영 vLLM 에 16번 POST 하므로 사람이 확인하고 돌린다.

   ```bash
   # 저장소 루트에서
   mkdir -p /tmp/figleak-after && git archive b2aa84e app | tar -x -C /tmp/figleak-after
   cd /tmp/figleak-after/app
   PYTHONIOENCODING=utf-8 python <이 폴더>/checks/figleak/measure_g2.py \
     --base-url http://192.168.12.57:18080/v1 --model gemma-3-12b -n 8      # → checks/figleak/measure_g2.json
   cd <이 폴더> && PYTHONIOENCODING=utf-8 python checks/figleak/summarize_g2.py checks/figleak/measure_g2.json \
     > checks/figleak/measure_g2_out.txt
   ```

보관하며 확인한 것(10-15): 10-14 의 생성 원문·보고서 JSON 과 지금 `app/`(dev `f06b814` 와 같은 내용)으로 4·5·6·7 과
`checks/excerpt-cut` 을 다시 돌려 이 폴더의 표·집계·짝 키·`*.slim.json`·`gen_index.tsv`, 그리고 10-14 원본 판정 묶음이
줄바꿈 말고는 같게 나왔다. `ab_metrics_v2.json`·`r2_metrics.json` 은 값이 같고 합계 키의 순서만 실행마다 다르다(집합 순회).

## 한계

- **표본이 작다.** 보고서 4건이고 그중 둘은 같은 주제(노인 우울·사회적 지지)다. 회차 2, temperature 0.3.
  1차 판정은 r0 만 — 후보마다 4짝 × 3명 = 12판정이다. 2차 판정(8짝 × 3명)은 대부분 '근소' 였다.
- **사람 검증이 없다.** 판정자 셋은 LLM 에이전트다. 2차 fact 판정자는 작업 지시문에 X/Y 배정표가 들어 있어 엄밀한 블라인드가
  아니었을 수 있다고 적었다(fact 를 빼도 reader+editor 11-4-1 로 결론은 같다). editor 는 일부 절만 원문과 대조했다.
- **자동 지표는 근사치다.** 일반론·되받기·오귀속·게재지 군말은 정규식, 절 사이 겹침은 difflib 유사도다. 사람 라벨로 맞춰 보지 않았다.
- **설계에 쓴 보고서가 시험에도 들어 있다.** focus 의 형식 확인은 630e 로, focus2 다듬기는 630e·9ba1 로 했다.
- **경계 결정이 둘이다.** concise·focus2 는 48호출 중 1건 차로 떨어졌다.
- **생성 모델은 gemma-3-12b 하나다.** 실패 시 다른 모델로 넘어가는 경로는 보지 않았다.
- **운영 효과는 확인 중이다.** 3·4차는 배포됐고(2026-10-15, 사용자 — 어느 컨테이너까지 했는지는 사용자 확인 전) 운영 새 연구로
  확인 중이다. 배포 뒤 새 연구로 다시 잰 값은 아직 없다.
- **설계 단계 수치는 다시 셀 수 없다.** 위 '넣지 않은 것' 아래 문단.
