# critic 두 갈래 판정 도구 (research_eval)

딥리서치 critic 의 기준 스위치(잡 파라미터 `critic_scope` — 0 = 지금 기준, 1 = 원 질문 기준)를 켤지 정하는 도구다. 고정 질문 5개를 운영에서 두 갈래로 돌리고, 사람이 단 라벨로 합격선을 센다(spec `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` D11·§8). 06a 배포 당일과 리허설(10/23~25)에 다시 돈다. LLM 심판은 쓰지 않는다.

**합격선(질문·갈래마다):** ① 보고서 절(`sections[].papers`)마다 '무관' 라벨 1편 이하 ② 과잉 제외 10% 이하 — 제외된 서로 다른 논문(`trail[].excluded_papers`) 중 '관련' 라벨 비율(라벨 칸이 빈 논문은 분모에서 뺀다). 라벨 칸이 빈 논문이 남은 갈래는 '판정 보류'로 합격에 세지 않고(① 을 이미 넘겼으면 '불합격'), '합격 질문' 의 분모는 채점하지 못한 질문까지 넣은 질문 수 전체다. 갈래 1 이 다섯 질문 모두 합격하면 `DEFAULT_PARAMS["critic_scope"]` 기본값을 1 로 바꾸는 작은 커밋을 하고, 하나라도 미달이면 0 으로 둔 채 계획 프롬프트 수정 여부를 사용자에게 묻는다.

| 파일 | 하는 일 | DB |
|---|---|---|
| `questions.json` | 고정 질문 5개 `[{key, question}]` — `key` 가 라벨 파일 이름이 된다 | — |
| `run_pair.py` | 질문마다 갈래 0·1 잡을 만들고(갈래 1 은 갈래 0 의 계획으로 승인) 완료까지 기다려 `{key: {"0": 잡 id, "1": 잡 id}}` 를 쓴다 | 안 씀(HTTP) |
| `make_labels.py` | 두 갈래 보고서의 절 논문·제외 논문을 합쳐 `labels/<key>.csv`(`cnts_id,title,authors,label`)를 쓴다. 이미 단 라벨은 남긴다 | 안 씀(HTTP) |
| `score.py` | 라벨과 보고서를 맞대어 갈래마다 절별 무관 수·과잉 제외 비율·판정(합격·불합격·판정 보류)을 찍는다 | 안 씀(HTTP) |
| `mark_example.py` | 연구를 예시 연구로 지정·해제(`research_works.is_example`) — `--yes` 없으면 할 일만 찍는다 | 씀(`--yes` 일 때만) |
| `labels/<key>.csv` | 사람이 단 라벨(질문 단위 — 두 갈래에 함께 나온 논문은 한 줄). `*.csv` 는 `.gitignore` 대상이라 `git add -f` 로 올린다 | — |

## 흐름

1. **질문 확인.** `questions.json` 의 5개를 쓴다. 첫 질문(`computing`)은 운영 잡 `2a56f8b6` 의 질문이다. 질문을 바꾸면 라벨 파일도 새로 만든다.
2. **서버로 옮기기.** `scripts/` 는 앱 이미지에 없다(함정 4번). 이 폴더를 서버의 `/data/nl-lib/data/research_eval/` 로 옮긴다(scp 등 평소 쓰는 방법). 컨테이너 안에서는 `/app/data/research_eval/` 이다.
3. **두 갈래 실행.** 실행 워커가 하나라 잡 10개가 차례로 돈다(잡 하나 약 2분 — 25분 안팎). 끊기지 않게 tmux 같은 세션에서 돌린다.
   ```bash
   RUN=pairs_$(date +%Y%m%d)
   docker exec nl-lib-fastapi python /app/data/research_eval/run_pair.py \
     --api http://localhost:8000/api --out /app/data/research_eval/$RUN.json
   ```
   마지막 줄이 `실패한 질문 …` 이면 그 줄의 `--only …` 를 붙여 다시 돌린다(완료된 질문의 기록은 남는다). 4·6 은 같은 `RUN` 을 쓴다 — 셸을 새로 열었으면 `ls /data/nl-lib/data/research_eval/` 로 이름을 보고 `RUN` 을 다시 넣는다.
4. **라벨 파일 만들기.**
   ```bash
   docker exec nl-lib-fastapi python /app/data/research_eval/make_labels.py \
     --api http://localhost:8000/api --pairs /app/data/research_eval/$RUN.json \
     --out-dir /app/data/research_eval/labels
   ```
5. **라벨 달기(기획자).** 서버의 `/data/nl-lib/data/research_eval/labels/<key>.csv` 의 `label` 칸에 `관련`·`무관` 만 쓴다. 기준은 **원 질문**이다 — 하위질문에서 벗어났어도 원 질문의 주제를 다루면 `관련`, 같은 단어를 다른 뜻으로 쓴 논문을 포함해 원 질문과 무관하면 `무관`. 엑셀로 열어도 된다(BOM 이 붙어 있다 — 저장할 때 'CSV UTF-8' 로).
6. **채점.**
   ```bash
   docker exec nl-lib-fastapi python /app/data/research_eval/score.py \
     --api http://localhost:8000/api --pairs /app/data/research_eval/$RUN.json \
     --labels-dir /app/data/research_eval/labels
   ```
   `합격 질문: 갈래 0 a/5 · 갈래 1 b/5` 줄과 질문별 줄을 기록한다. `판정 보류`·`라벨 칸이 빈 논문이 …` 가 나오면 5 로 돌아가 마저 단다. `채점하지 못한 질문 …` 이 나오면 그 질문의 라벨 파일(4)이나 잡(3, `--only`)부터 다시 한다.
7. **기록.** 라벨 파일을 저장소의 `scripts/research_eval/labels/` 로 옮겨 `git add -f` 로 커밋하고(리허설 때 다시 쓴다), 실행 JSON 의 잡 id 와 채점 결과는 라운드 완료노트에 적는다.
8. **예시 연구 지정(리허설).** 미리 돌려 이어간 연구를 예시로 보이려면 먼저 `--yes` 없이 보고 지정한다.
   ```bash
   docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/research_eval/mark_example.py --work <연구 id> --on
   docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/research_eval/mark_example.py --work <연구 id> --on --yes
   ```

## 테스트

`app/tests/test_research_eval.py` — `cd app && python -m pytest tests/test_research_eval.py -q -p no:cacheprovider`. HTTP 는 `httpx.MockTransport`, DB 는 `db.postgres` 대역이라 운영에 닿지 않는다.
