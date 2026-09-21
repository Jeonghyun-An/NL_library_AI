# 반복 함정 (Recurring Gotchas)

라이브(docker·실데이터)에서만 드러나는 패턴을 기록한다. 겪을 때마다 아래에 `## N. 제목` 섹션을 추가한다 — 라운드 문서가 아니라 상시 갱신 문서다. 표가 아니라 산문 섹션인 이유: 항목 하나가 원인 여러 개·하위 절차·쉘 명령(`|` 포함)을 가지는 경우가 흔한데, 표 셀에는 이게 안 들어간다.

각 섹션 구성: 증상 · 원인 · 해결 · 재발 방지.

## 1. dev 스택 코드 변경이 반영 안 됨 — 이미지가 registry pull 방식이라

- **날짜**: 2026-09-04 (round01)
- **증상**: `app/` 코드를 고치고 `docker compose -f docker-compose.dev.yml up -d`를 실행해도 변경이 반영되지 않는다.
- **원인**: `fastapi-dev`·celery 워커 4종+`celery-beat-dev`·`nuxt-dev`는 전부 `build:` 키가 없고 `image: landsoftdocker/nl-lib-fastapi:dev`처럼 registry에서 미리 빌드된 이미지를 pull한다. `up -d`는 이미지를 새로 빌드하지 않는다.
- **해결**: `bash scripts/build_dev_images.sh`로 이미지를 다시 빌드+push한 뒤, Portainer에서 `nl-lib-dev` 스택을 Pull & Redeploy한다.
- **재발 방지**: dev 스택에서 코드 반영이 안 될 때 가장 먼저 "이미지를 다시 빌드했는가"부터 확인한다. `docker compose config`는 이 문제를 못 잡는다(파싱만 하지 이미지 소스는 안 봄).

## 2. dev 스택은 Windows 개발 PC에서 직접 못 띄운다

- **날짜**: 2026-09-04 (round01)
- **증상**: `docker compose -f docker-compose.dev.yml up -d`가 볼륨/네트워크 오류로 실패하거나, 뜨더라도 `fastapi-dev`가 GPU를 못 잡고 죽는다.
- **원인**: 볼륨 5종(`nl_lib_dev_etcd_data` 등)과 `nl-lib-net`이 전부 `external: true`라 prod 스택이 먼저 떠 있어야 하고, `fastapi-dev`는 NVIDIA GPU를 예약하며 `/data/models/.hf-cache`·`/data/nl-lib/dev-data` 같은 Linux 경로를 바인드마운트한다.
- **해결**: dev 스택은 GPU 서버에서만 띄운다. 개발 PC(Windows 등)에서는 코드만 수정하고, 반영은 위 1번 절차(빌드+push → Portainer redeploy)로 한다.
- **재발 방지**: "왜 로컬에서 dev 스택이 안 뜨지?"라는 질문 자체가 잘못된 전제다 — 애초에 로컬에서 띄우는 스택이 아니다.

## 3. 운영 스택에 코드가 반영 안 됨 — build_dev_images.sh 는 `:dev` 태그만 만든다

- **날짜**: 2026-09-17 (round03)
- **증상**: 재빌드·푸시·재배포를 마쳤는데 `docker exec nl-lib-fastapi python -c "from workers.tasks import <신규함수>"` 가 `ImportError` 로 죽는다.
- **원인**: `scripts/build_dev_images.sh` 는 `landsoftdocker/nl-lib-fastapi:dev` 를 빌드·푸시한다. 운영 스택(`docker-compose.yml`)은 `:latest` 를 쓴다. 새 코드가 `:dev` 이미지에만 들어가고 운영 컨테이너는 옛 `:latest` 그대로다.
- **해결**: `NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi` 로 태그를 override 한 뒤 운영 스택을 Pull & Redeploy 한다.
- **재발 방지**: 1번 함정의 연장이다. "빌드했는가" 다음에 **"어느 태그로 빌드했는가"** 를 확인한다. 배포 없이 급히 돌려야 하면 `docker exec -i <컨테이너> python - <<'PY'` 로 단독 스크립트를 stdin 에 먹이면 이미지 변경이 필요 없다.

## 4. 스크립트를 파일 경로로 실행하면 앱 모듈을 못 찾는다

- **날짜**: 2026-09-16 (round03)
- **증상**: `docker exec nl-lib-fastapi python /app/data/recovery/foo.py` 가 `ModuleNotFoundError: No module named 'core'` 로 죽는다. 같은 코드를 `python -c` 로 넣으면 된다.
- **원인**: 파이썬은 스크립트를 경로로 실행하면 `sys.path[0]` 을 **스크립트가 있는 디렉터리**로 잡는다(`/app/data/recovery`). `python -c` 나 `python -`(stdin) 은 cwd(`/app`, 이미지의 WORKDIR)가 들어와 앱 모듈이 보인다.
- **해결**: `docker exec -e PYTHONPATH=/app ...` 를 붙이거나, `docker cp` 로 `/app/` 밑에 두고 실행한다.
- **재발 방지**: `/app/data/` 바인드 마운트는 앱 이미지에 `scripts/` 가 없어 쓰는 통로다. 그 경로에서 실행할 땐 `PYTHONPATH=/app` 이 기본이라고 생각한다.

## 5. KCI 로더는 xlsx 전용 — CSV 를 넣으면 죽는다

- **날짜**: 2026-09-16 (round03)
- **증상**: KCI 카탈로그 CSV 적재가 `openpyxl.utils.exceptions.InvalidFileException: openpyxl does not support .csv file format` 으로 실패한다.
- **원인**: `domains/nl_library/loaders/kci_xlsx.py` 의 `load_kci_xlsx()` 가 `load_workbook()` 직결이다. NL MARC/MODS 로더는 `_read_rows()` 로 xlsx·CSV 를 모두 처리하는데 KCI 만 다르다. 헤더 판별용 `read_headers()` 는 CSV 를 읽으므로 **자동 판별은 통과하고 본 적재에서 죽는다** — 더 헷갈린다.
- **해결**: xlsx 를 쓰거나, 같은 매핑을 재사용하는 별도 경로(`scripts/recovery/load_kci_csv.py`)로 적재한다.
- **재발 방지**: 로더가 포맷을 지원하는지는 `detect()` 가 아니라 `load()` 구현을 봐야 안다.

## 6. Milvus 메타청크의 구분자 ` | ` 가 값 안에도 들어있다

- **날짜**: 2026-09-16 (round03)
- **증상**: 메타청크를 `split(" | ")` 로 파싱하면 저자·주제가 두 동강 난다.
- **원인**: 메타청크는 `제목: … | 저자: … | 출판사: …` 형태인데, MARC 다중값 필드 자체가 ` | ` 로 이어져 있다. 실측: `저자: 柳在元 | 林慧俊`, `주제: 인연 | 덫 | 사랑`.
- **해결**: 알려진 라벨 집합(`제목`·`기관`·`저자`·`출판사`·`발행년도`·`KDC분류`·`주제`·`키워드`·`초록`)과 `": "` 가 이어지는 경계로만 자른다. `scripts/recovery/restore_from_milvus_meta.py` 참고.
- **재발 방지**: 구분자가 값에 나타날 수 있는 포맷은 라벨 경계로 파싱한다.

## 7. SQLAlchemy `text()` 는 바인드 파라미터 뒤의 `::` 캐스트를 못 넘긴다

- **날짜**: 2026-09-17 (round03)
- **증상**: `UPDATE ... SET extra = coalesce(extra,'{}'::jsonb) || :e::jsonb` 가 `psycopg2.errors.SyntaxError: syntax error at or near ":"` 로 죽는다. 같은 쿼리의 다른 파라미터(`:a`, `:i`)는 `%(a)s` 로 정상 변환된다.
- **원인**: 파라미터 바로 뒤에 PostgreSQL 캐스트 `::` 가 붙으면 SQLAlchemy 가 그 파라미터를 바인딩하지 못하고 SQL 에 그대로 흘려보낸다.
- **해결**: `CAST(:e AS jsonb)` 로 쓴다. 값이 없는 `'{}'::jsonb` 같은 리터럴 캐스트는 문제없다.
- **재발 방지**: `text()` 안에서 `:param::type` 패턴을 쓰지 않는다.

## 8. `NOT IN (서브쿼리)` 가 데이터가 늘면 급격히 느려진다

- **날짜**: 2026-09-16 (round03)
- **증상**: 고아 문서 조회가 즉시 끝나다가, 카탈로그 복구 후 5분 넘게 멈춘다.
- **원인**: `WHERE book_id NOT IN (SELECT cnts_id FROM library_catalog)` 는 NULL 의미론 때문에 안티조인으로 풀리지 않는다. 대상이 246행일 땐 티가 안 나다가 24만 행이 되자 드러났다.
- **해결**: `WHERE NOT EXISTS (SELECT 1 FROM library_catalog c WHERE c.cnts_id = d.book_id)` 로 바꾼다. distinct 를 먼저 줄이면 더 빠르다.
- **재발 방지**: 진단 쿼리도 데이터 규모가 바뀌면 성능이 뒤집힌다. `NOT IN` 서브쿼리는 처음부터 `NOT EXISTS` 로 쓴다.

## 9. 표지가 보인다고 DB 가 멀쩡한 게 아니다

- **날짜**: 2026-09-15 (round03)
- **증상**: `library_catalog` 이 통째로 비었는데도 검색 결과의 표지 이미지는 정상 표시돼, 피해 범위를 과소평가하게 만든다.
- **원인**: 썸네일 엔드포인트(`app/api/book.py:368`)가 ① DB `cover_image_key` → ② MinIO 캐시 → ③ 원본 PDF 1페이지 즉석 렌더 순으로 폴백한다. DB 행이 없어도 ③ 으로 그려진다.
- **해결**: 데이터 유실을 의심할 땐 화면이 아니라 저장소별 건수를 직접 센다(`library_catalog` · `book_sections` · Milvus · MinIO).
- **재발 방지**: 폴백이 촘촘한 화면은 진단 지표로 쓰지 않는다.

## 10. jsonb `?` 는 키 존재만 본다 — 빈 배열이 "값 있음"으로 새어든다

- **날짜**: 2026-09-18 (round03)
- **증상**: (이번엔 터지지 않았다 — 잠복 함정으로 기록한다.) 참고문헌 복구 스크립트의 대상 선정과 검증 쿼리가 모두 `extra ? 'references'` 를 썼다. 이 조건은 값이 `[]` 인 문서를 "참고문헌 있음"으로 세고 복구 대상에서도 뺀다.
- **원인**: 적재 파이프라인(`app/services/ingestion/stages.py`)이 초록·목차·키워드 중 하나만 있어도 `extra["references"]` 를 **빈 리스트째로** 기록한다. jsonb `?` 는 키 존재만 본다.
- **실측**: 운영에서는 빈 배열이 **0건**이었다. 파이프라인이 쓴 `extra` 는 2026-09-14 카탈로그 전멸 때 행과 함께 사라졌고, 이후 `extra` 를 채운 복구 스크립트는 `if not refs: continue` 로 빈 결과를 쓰지 않아 빈 배열이 생길 경로가 없었다. 재인덱싱이 돌면 다시 생긴다.
- **해결**: 존재가 아니라 길이로 판정한다 — `jsonb_array_length(coalesce(extra->'references','[]'::jsonb)) = 0`.
- **재발 방지**: jsonb 배열·객체 필드에 `?` 를 쓸 땐 "키가 있는가"와 "값이 비었는가"가 다른 질문임을 먼저 확인한다. 그리고 **코드 경로가 있다고 그 경로를 탄 데이터가 있는 것은 아니다** — 영향 범위는 세어서 확정한다.

## 11. 정렬이 걸린 `LIMIT` 은 표본이 아니다

- **날짜**: 2026-09-17 (round03)
- **증상**: 참고문헌 재추출 dry-run 500건에서 25.4% 가 나와 전체 41,399건에 약 1만 건을 기대했으나, 실제 실행은 16.7%(6,931건)였다.
- **원인**: dry-run 대상이 `ORDER BY cnts_id LIMIT 500` 으로 뽑혀 ID 앞쪽에 몰렸고, 그 구간에 추출 성공률이 높은 문서가 편중돼 있었다.
- **해결**: 비율을 외삽할 목적이면 `ORDER BY random() LIMIT n` 을 쓴다.
- **재발 방지**: dry-run 결과를 전체에 곱하기 전에 그 표본이 어떻게 뽑혔는지 먼저 본다. 정렬된 앞부분은 모집단을 대표하지 않는다.

## 12. Portainer 이미지 Pull 이 수 GB 이미지에서 타임아웃한다

- **날짜**: 2026-09-17 (round03)
- **증상**: Portainer 스택 Redeploy 시 `context deadline exceeded` 로 실패한다. 같은 이미지를 서버 셸에서 받으면 정상이다.
- **원인**: Portainer 의 Docker API 클라이언트 타임아웃이 CUDA 포함 수 GB 이미지 pull 시간을 못 견딘다.
- **해결**: 서버에서 `docker pull <이미지>` 로 먼저 받아두고, Portainer 에서는 Redeploy 만 누른다(이미 로컬에 있으면 즉시 끝난다).
- **재발 방지**: 큰 이미지를 새로 빌드한 배포는 Portainer 에 맡기지 말고 pull 을 분리한다.

## 13. `services.search.pipeline` 을 모듈 최상단에서 import 하면 로컬 테스트가 통째로 죽는다

- **날짜**: 2026-09-21 (round04a)
- **증상**: 새 모듈이 `from services.search.pipeline import search` 를 최상단에 넣자 `pytest` 가 `ModuleNotFoundError: No module named 'torch'` 로 **collection 단계에서 중단**된다. 그 모듈의 테스트뿐 아니라 세션 전체가 0건이 된다.
- **원인**: `pipeline.py` → `reranker.py` → `import torch` 인데, **torch 는 로컬 venv 에 의도적으로 없다.** `requirements.txt` 에도 없고 Dockerfile 에서 CUDA 버전으로 따로 설치한다(`reranker.py` 주석 참고).
- **해결**: torch 를 끌어오는 모듈(`pipeline`·`reranker`·`embedder`)은 **함수 본문 안에서 import 한다.** 이미 코드베이스의 관례다 — `app/api/book.py:619`, `app/main.py:53`, `app/services/ingestion/stages.py:87` 이 전부 그렇게 한다.
- **재발 방지**: 검색·임베딩·리랭킹을 쓰는 새 모듈을 만들 때 최상단 import 를 쓰지 않는다. 순수 계산 부분을 같은 파일에 두고 싶다면 더더욱 — 그 순수 함수 테스트까지 같이 죽는다.

