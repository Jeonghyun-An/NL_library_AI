# round06b — 주제 카드 모델 재비교 (1회성)

06a Qwen 표본(`research/round06-qwen-check/`)은 **초안** 카드 프롬프트로 Qwen 9 · gemma 4 · 무승부 2(형식 통과 Qwen 11/15 · gemma 4/15)였지만, gemma 실패 11건 중 10건이 근거 칸에 [E#] 대신 논문 제목을 넣은 같은 실수였고 내용은 gemma 가 더 구체적인 카드가 많았다. 그래서 주제 카드 모델은 Qwen 그대로 두고 06b 의 **정식 실행기**로 다시 비교한다(계획 `docs/superpowers/plans/2026-10-06-round06b-vertical-slice.md` 정함 6). 정식 실행기(`app/services/research_work/topic_card.py`)는 초안과 세 가지가 다르다.

1. 근거를 제목으로 낸 출력은 코드가 [E#] 로 되돌린다(정함 5) — 예시 한 줄은 넣지 않는다(함정 15).
2. 수치 문장은 모델이 쓰지 않는다 — 프롬프트에 수치를 주지 않고 코드 틀(`figure_sentence`)이 [F#] 를 넣는다(정함 3).
3. 근거 칩은 2개 이상(`MIN_TOPIC_EVIDENCE = 2`) — 직접 받치는 논문만, 받치지 않는 논문으로 채우지 않는다(정함 4).

## 방법

- 입력: 고정 질문 5개(`scripts/research_eval/questions.json`)의 **갈래 0** 잡 — 06b 배포 뒤 재판정(`RUN=pairs_<날짜>_d18`)의 `run_pair.py` 출력 JSON 의 `"0"`. DB 를 읽지도 쓰지도 않는다(잡은 `GET /api/research/{id}` 로 읽는다).
- 카드 입력은 이어가기가 넣는 것 그대로다 — `seeds.pick_seeds(report, limit=TOPIC_SEED_SLOTS)`(서로 다른 절 먼저, 최대 4장) → `seeds.topic_input`.
- 요청은 `topic_card.EXECUTOR.build`(`research_topic_card.yaml` 렌더와 LLM 파라미터), 응답은 `EXECUTOR.parse → bind → check` 로 읽는다. Qwen·gemma 에 똑같이, **재시도·넘김 없이 모델마다 한 번** 보낸다(운영의 3회 규칙을 빼고 첫 답을 견준다). 호출 상한은 생성과 같은 300초.
- 출력: `out/<질문키>.md`(요약 표 + 카드마다 두 모델을 한 표에, 원문은 접어 둔다)와 `out/summary.md`(질문별·합계 형식 통과와 근거 3개 이상).
  - 형식 통과 = `check` 통과(근거 칩 2개 이상). 근거 3개 이상 충족률을 함께 찍는다 — 정식 프롬프트로 3개 이상이 무관 없이 나오면 `MIN_TOPIC_EVIDENCE` 를 3 으로 되돌릴지 본다(정함 4).
  - 제목에서 되돌린 근거(`checks.recovered`)·버린 근거 표기·[F#] 밖 숫자(`checks.numbers`, '확인 필요')·바꾼 단정 표현(`checks.softened`)·시간을 적는다.

| 파일 | 역할 |
|---|---|
| `check.py` | 위 비교를 돌려 `out/` 에 쓴다 |
| `smoke_check.py` | 가짜 API·가짜 vLLM 으로 `check.py` 를 끝까지 돌려 본다(개발 PC, 네트워크 없음) — `python research/round06b-topic-card-check/smoke_check.py` → `smoke OK`(Git Bash 에서 한글이 깨지면 앞에 `PYTHONIOENCODING=utf-8`) |
| `out/<질문키>.md`·`out/summary.md` | 운영 실행 결과 |

## 판정 규칙 (정함 6)

1. 다섯 질문을 합친 **형식 통과 카드 수**가 많은 쪽.
2. 그 차이가 **2장 이하**이면 질문별 내용 판정 — Claude 판정자에게 질문별 `out/<질문키>.md` 를 따로 읽혀(06a 첫 판정과 같은 방식 — 서로 모르는 판정자 셋이 따로 판정하고 표가 갈린 것만 최종 판정, 이 방식으로 달았다고 아래 결과에 적고 사용자가 원하면 고친다) 제목·연구 질문이 원 질문의 대상·맥락 안에 있는가, 고른 근거가 그 주제를 직접 받치는가, 씨앗을 베끼지 않고 구체적인가를 보고, **다섯 질문 중 셋 이상** 나은 쪽.
3. gemma 로 정해지면 `app/services/research_work/routing.py` 의 `WORK_MODEL_ROUTES["topic_card"]` 값 한 칸만 `GEMMA` 로 바꾸는 작은 커밋 + 워커 재배포(계획 Task 37). 같은 줄의 refine·facet 은 그대로 둔다(줄을 통째로 바꾸면 함께 바뀐다).

## 실행 (서버 — `research/` 는 앱 이미지에 없다, 함정 4)

이 폴더를 `/data/nl-lib/data/round06b-topic-card-check/` 로 옮긴다(root 소유 폴더라 일반 계정 홈으로 받은 뒤 root 셸에서 `cp`). 정식 실행기는 06b 이미지에만 있으므로 **06b 배포 뒤** 돌린다.

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round06b-topic-card-check/check.py \
  --api http://localhost:8000/api --pairs /app/data/research_eval/$RUN.json
```

`RUN` 은 `scripts/research_eval/README.md` 의 재판정 이름이다. `--qwen-url`·`--qwen-model`·`--gemma-url`·`--gemma-model` 을 주지 않으면 운영 생성이 부르는 곳(`services.research_work.routing.endpoint` — `VLM_*`·`LLM_*` 설정)을 쓴다. 한 질문의 잡 조회가 실패하면 그 질문만 건너뛴다. 적재가 도는 동안의 시간 칸은 참고만 한다(Qwen 은 OCR 과 자리를 나눠 쓴다). 끝나면 서버의 `out/` 을 이 폴더로 가져와 커밋하고 아래 표를 채운다.

## 결과

운영에서 돌린 뒤 채운다(계획 Task 37).

| 질문키 | Qwen 형식 통과 | gemma 형식 통과 | Qwen 근거 3개 이상 | gemma 근거 3개 이상 | 내용 판정(나은 쪽) | 메모 |
|---|---|---|---|---|---|---|
| computing | | | | | | |
| library | | | | | | |
| elderly | | | | | | |
| multicultural | | | | | | |
| csr | | | | | | |

결정(사용자 확인): 주제 카드 → Qwen 유지 / gemma 로 · `MIN_TOPIC_EVIDENCE` → 2 유지 / 3 으로.
