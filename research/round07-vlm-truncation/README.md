# round07 — VLM 출력 한도(`VLM_MAX_TOKENS` 4096) 확인 (1회성, 2026-10-04~05)

카나리(2026-10-02)에서 OCR 402쪽 중 20쪽이 `VLM_MAX_TOKENS` 4096 에 닿았다(`meta.vlm_truncated`, 완료노트 §5-3). 빽빽한 본문이 4096 에서 잘린 것이면 한도를 올릴 근거가 되고, 모델이 같은 구절을 되풀이하는 고리에 빠진 것이면 올려도 소용없다. 그래서 운영 규모를 세고, 잘린 쪽을 한도를 올려 다시 물어 둘을 가렸다.

## 규모 (2026-10-04, 배포 뒤 `nl-lib-celery-cpu` 로그와 본 잡 `meta`)

| 지표 | 값 |
|---|---|
| OCR 한 쪽(`→ OCR 보완 (` 줄) | 41,744 |
| 4096 에 닿아 꼬리를 걷고 쓴 쪽(`VLM 응답이 max_tokens` 줄) | 1,731 |
| 걷고 나니 쓸 게 없어 ODL 결과로 대신한 쪽(`VLM 퇴화 출력` 줄) | 258 |
| 배포 뒤 끝난 문서 · 잘린 쪽이 있는 문서 | 10,806 · 1,188(11%) — `meta.vlm_truncated` 합 1,961쪽, 한 문서 최대 20쪽 |

잘린 쪽은 (1,731 + 258) ÷ 41,744 = 4.8% 로 카나리(약 5%)와 같다. 명령은 아래 '실행'의 ① 이다.

## 방법

`vlm_trunc_probe.py` 를 운영 `nl-lib-celery-cpu` 컨테이너 안에서 돌렸다.
- 배포 뒤 끝난 문서 가운데 `vlm_truncated` 가 가장 많은 40쪽 이하 문서 2개를 고른다.
- 운영과 같은 `extract_text` 로 다시 추출하며 VLM 응답을 모두 기록한다. `httpx.AsyncClient` 를 기록용 하위 클래스로 바꿔 끼운다.
- `finish_reason=length` 인 쪽은 같은 요청을 `max_tokens = min(8192, max_model_len − 그 쪽 입력 토큰 − 32)` 로 한 번 더 보낸다. 입력 + 출력이 `max-model-len`(16384)을 넘으면 vLLM 이 400 으로 거절하기 때문이다.
- 되풀이 판정은 운영과 같은 `page_routing.trim_repetition` 이다. 걷은 뒤 글자가 원래의 90% 아래면 '되풀이 꼬리', 퇴화 판정이면 '퇴화', 그 밖이면 '되풀이 없음'(본문이 잘렸을 수 있다)으로 나눈다.
- DB·MinIO 에는 쓰지 않는다. 운영 VLM 을 적재와 함께 쓴다(문서 2개에 약 15분).

## 실행 (서버, root 셸 — `JOB`·`PGU`·`PGD` 는 런북 §9 머리말)

```bash
# ① 규모
docker logs nl-lib-celery-cpu 2>&1 | grep -c '→ OCR 보완 ('
docker logs nl-lib-celery-cpu 2>&1 | grep -c 'VLM 응답이 max_tokens'
docker logs nl-lib-celery-cpu 2>&1 | grep -c 'VLM 퇴화 출력'
docker exec nl-lib-postgres psql -U "$PGU" -d "$PGD" -c "SELECT count(*) AS done_docs, count(*) FILTER (WHERE meta->>'extract_method' = 'vlm') AS vlm_docs, count(*) FILTER (WHERE (meta->>'vlm_truncated')::int > 0) AS docs_with_truncated, coalesce(sum((meta->>'vlm_truncated')::int), 0) AS truncated_pages, max((meta->>'vlm_truncated')::int) AS max_in_one_doc FROM ingest_job_items WHERE job_id = '$JOB' AND status = 'done' AND finished_at > '$(cat /data/nl-lib/data/round07/deployed_at.txt)'"
# ② 실험 — 이 폴더의 vlm_trunc_probe.py 를 서버의 /data/nl-lib/data/round07/ 에 두고
docker exec -e PYTHONPATH=/app -e JOB=$JOB -e DEP="$(cat /data/nl-lib/data/round07/deployed_at.txt)" nl-lib-celery-cpu python /app/data/round07/vlm_trunc_probe.py 2>/dev/null
```

`N_DOCS`·`HIGH_TOKENS` 환경 변수로 문서 수와 다시 물을 때의 상한을 바꾼다.

## 결과 (2026-10-05) — `out/probe_stdout.txt`

| | KCI_FI002078668(24쪽, 프랑스어 언어학 논문) | KCI_FI002028750(14쪽, 한문 원문) |
|---|---|---|
| 다시 추출할 때 4096 에서 잘린 쪽 | 12 — 모두 되풀이 꼬리(`linguistique linguistique…`, `{fonction} {fonction}…`) | 8 — 모두 되풀이 꼬리(`何如？何如？…`) |
| 그 쪽의 입력 토큰 | 4,834 | 5,932~6,112 |
| 8192 로 다시 물으면 | 11쪽이 또 8192 를 다 쓰며 되풀이, 1쪽(호출 10)만 702토큰에서 정상 종료 | 8쪽 모두 또 되풀이(1쪽은 퇴화) |
| 정상 종료한 쪽의 출력 토큰 | 중앙 826 · 최대 1,005 | 중앙 616 · 최대 772 |

- 잘린 20쪽이 모두 되풀이 고리였다. 4096 에서 잘린 빽빽한 본문은 없었다.
- 정상 쪽은 많아야 약 1,000토큰을 쓴다. 4096 은 이미 4배쯤 넉넉하다.
- 고리는 운에 따라 갈린다. 호출 10 은 다시 묻자 정상으로 끝났고(1,795자), 4096 응답에서 꼬리를 걷은 글(1,713자)이 거의 같았다. 다른 쪽은 걷고 남은 글이 25~502자라 그 쪽 본문 대부분을 잃는다.
- 두 문서 모두 한국어가 아닌 글(프랑스어 용어, 한문)이다.
- 한계: 고리가 가장 많은 문서 2개뿐인 표본이라, 다른 문서에서 본문이 잘리는 일이 전혀 없다고 단정할 수는 없다. 쪽별 기록(JSON)은 서버 `/data/nl-lib/data/round07/vlm_trunc_probe.json` 에만 있다 — 쪽 이미지가 든 요청은 남기지 않았다.

## 결론과 결정

- `VLM_MAX_TOKENS` 를 올려도 소용없다. 고리는 더 길게 되풀이할 뿐이고, VLM 시간만 더 쓴다. 입력이 큰 쪽(A4 300dpi 면 약 8,600토큰으로 추정)에서는 8192 가 `max-model-len` 16384 를 넘어 400 으로 거절될 수도 있다. 이 표본의 쪽은 입력이 4,834~6,112토큰이라 8192 가 들어갔다.
- 다른 처방은 실험하지 않았다 — 되풀이가 보이면 반복 억제 값(`repetition_penalty`)을 주고 한 번 더 묻기, 고리가 쓰는 시간을 줄이려 한도를 낮추기(정상 쪽이 2,000토큰을 넘지 않는지 VLM 서버의 `vllm:request_generation_tokens` 분포로 먼저 확인).
- **사용자 결정(2026-10-05): 그대로 둔다.** 지금 코드가 되풀이 꼬리를 걷어 색인 오염은 막는다. 대가로 고리 쪽(OCR 쪽의 약 4.8%)은 고리가 시작되기 전까지의 글만 남는다.
