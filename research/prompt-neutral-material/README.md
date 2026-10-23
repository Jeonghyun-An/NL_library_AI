# 소장자료 생성 글이 자료를 '책·소설'로 단정하던 것 (2026-10-23)

사용자 지적: 책·소설이 아닌 자료에도 "이 책은…"이 나온다. 소장자료에는 고전·현대 소설과 시집뿐 아니라 국문학
학위논문(KDC 8xx 라 doc_type literature)·정부 재정 보고서(policy)·학술서가 섞여 있는데, 프롬프트가 '이 책이 …',
'"이 책을 읽으면 …" 형식으로'를 지시했다. 화면의 '추천 이유'·'읽고 난 후'와 상세의 소개·줄거리가 학위논문·보고서도 '이 책'이라 불렀다.

## 바꾼 것

자료를 '이 자료'로 부르고 종류(책·소설·작품·논문)를 단정하지 않게 했다 — 규칙 한 줄을 각 생성 프롬프트에 더하고 지시문의
'책·도서·작품'을 '자료'로.

- 검색 때 바로 쓰는 것(fastapi): `recommendation.yaml`(추천 이유·읽고 난 후), `book_chat.yaml`(소장자료 DeepRead),
  `curation.yaml`, `scenario_recommend.yaml`, 그리고 코드가 붙이는 문맥 라벨(`[자료 요약]`·`[자료 줄거리]`·`[자료 N]`).
- 적재·백필 때 저장되는 것(워커): `introduction.yaml`, `plot.{book,literature}.yaml`, `read_effect.{book,literature,policy}.yaml`,
  `book_summary.{book,literature,policy}.yaml`.
- 그대로 둔 것: `section_summary.*`(화면에 나오지 않고 청크 임베딩 앞머리에 들어간다 — 바꾸면 이미 적재된 자료와 새 자료의
  임베딩 성격이 갈라지고, literature 판은 회귀 테스트가 문자열을 지킨다), `query_rewrite.yaml`(내부), `*.paper.yaml`.

## 견준 결과 (`compare_reason.py`, `out.json`)

운영 자료 6건(학위논문 2·정부 보고서 1·고전소설·시집·영어 소설)의 추천 이유를 같은 입력으로 바꾸기 전·후 프롬프트에 3회씩
운영 LLM(Gemma 4)에 보냈다. 입력은 운영 API 의 자료 정보와 검색 대목으로 `stream_book_reason` 과 같은 모양으로 만들었다.

| 자료 | 전: 자료를 '책'으로 부름(회/답) | 후 | 후: '이 자료' | 형식(###EFFECT###) |
|---|---|---|---|---|
| 학위논문 2 | 2.0 | **0** | 3.2 | 6/6 |
| 정부 보고서 | 1.7 | **0** | 3.3 | 3/3 |
| 고전소설(구운몽) | 1.7 | **0** | 3.0 | 3/3 |
| 시집(진달래꽃) | 1.0 | **0** | 4.0 | 3/3 |
| 영어 소설(Little Women) | 2.0 | **0** | 2.3 | 3/3 |

학위논문 답의 '소설'·'작품'(후 3.3·1.8회)은 논문이 다룬 연구 대상(세태소설·작품군)을 가리킨다 — 자료 자체를 부른 것이 아니다.
'이 자료'가 한 답에 3~4번 되풀이되는 건 조금 딱딱하다.

## 남는 것

- 이미 저장된 소개·줄거리·읽고 난 후(비논문 약 910건)는 옛 프롬프트로 써서 '이 책'이 남아 있다 — 표본 6건 중 5건의 소개글에
  2~6번. 새 프롬프트가 든 워커에서 백필(force)로 다시 쓰면 바뀐다(`/api/admin/backfill/summary` doc_types
  literature·book·policy, `/backfill/plot`, `/backfill/read-effect` — 둘 다 book·literature·policy 만 대상).
- 화면 글자: `frontend/pages/index.vue` 의 '왜 이 책인가'·'이 책에서 얻을 수 있는 것'·'SKOVIX 추천 1권', `recommend/[id].vue` 의
  '이 책들을…'(프론트 세션).
- 국문학 학위논문이 KDC 8xx 라 literature 로 분류돼 문학 프롬프트(인물·갈등·줄거리)를 받는 것은 문구가 아니라 분류 문제다.
