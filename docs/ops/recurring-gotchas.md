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
