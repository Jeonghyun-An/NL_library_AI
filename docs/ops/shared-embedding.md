# 공용 임베딩 서버(bge-m3) 전환·되돌리기

2026-11-11. GPU 관리자 요청으로 서버에 따로 떠 있던 bge-m3 를 공용 서버 하나로 모았다. SKOVIX 는 `EMBEDDING_BACKEND` 하나로 예전 방식(프로세스 안)과 공용 서버를 오간다.

## 구성

| 갈래 | 동작 | GPU |
|---|---|---|
| `local`(기본) | 컨테이너마다 FlagEmbedding 으로 bge-m3 를 올린다 | 컨테이너마다 한 벌 |
| `http` | GPU 서버의 공용 bge-m3(vLLM) 두 개를 부른다 | SKOVIX 는 안 씀(리랭커 jina 만 남음) |

- **공용 서버**는 GPU 서버의 `~/models/bge-m3-dense.sh`·`bge-m3-sparse.sh`로 띄운다. 둘 다 vLLM `v0.33.0`, `nl-lib-net`에 붙어 있다.
  - dense: `bge-m3-dense:8000` `/v1/embeddings` — 다른 서비스도 같이 쓴다.
  - sparse: `bge-m3-sparse:8000` `/pooling`(task `token_classify`) — SKOVIX 하이브리드 검색용이다.
  - vLLM 은 서버 하나가 결과 한 종류만 내서 둘로 나뉜다.
- **sparse 조립**: sparse 서버는 토큰 위치마다 가중치만 주고 토큰 번호는 주지 않는다. `embedder.py`가 같은 토크나이저로 512 토큰까지 잘라 토큰 번호를 보내고, 받은 가중치를 그 번호와 짝지어 FlagEmbedding 과 같은 규칙으로 모은다. 받은 수가 맞지 않으면 그 자리에서 오류를 낸다 — 어긋난 채 넘어가면 오류 없이 검색 순위만 나빠진다.
- **장애**: 공용 서버에 닿지 못하거나 5xx·429 가 오면 `EmbeddingUnavailable`(ConnectionError)이다. 검색은 503, DeepRead 는 '자료를 찾지 못함', 딥리서치 개념 친밀도·대목 고르기는 대체 경로로 간다. fastapi 기동은 막지 않는다(경고만 남김).
  - 연결 거절·끊긴 재사용 연결·5xx·429 처럼 빨리 끝나는 일시 오류는 0.5초, 2초 쉬고 두 번 더 보낸다. 읽기 시간 초과(`EMBEDDING_HTTP_TIMEOUT`, 15초)는 다시 보내지 않는다.
- **기다리는 동안**: dense 서버는 다른 서비스도 같이 써서 앞 요청이 밀리면 기다릴 수 있다. 검색·관련 자료·DeepRead 는 이 기다림을 스레드에서 해서 fastapi(워커 1개)의 다른 요청을 막지 않는다(`offload_embed`).
- **dense 만 쓰는 곳**(의미 청킹·개념 친밀도)은 sparse 서버를 부르지 않는다. sparse 서버만 꺼져도 이 일들은 돈다.

## 값이 같은지 확인

전환 전, 그리고 공용 서버의 vLLM 이미지나 옵션을 바꾼 뒤에 돌린다. `EMBEDDING_BACKEND` 값과 상관없이 두 갈래를 모두 부른다.

```bash
docker exec -w /app nl-lib-fastapi python -m scripts.check_embedding_backend --n 50
```

- 저장된 메타 청크의 dense·sparse 와 지금 다시 낸 값을 비교하고, 같은 질의로 하이브리드 검색 상위 10 이 얼마나 겹치는지 본다.
- 맨 끝 '판정'이 모두 `통과`면 전환해도 된다. `확인 필요`가 있으면 숫자를 local 대 저장값 차이와 견준다.
- local 갈래 비교를 위해 이 프로세스에 bge-m3 를 한 벌 더 올린다(GPU 약 2~3GB, 끝나면 내려간다).
- 참고(2026-11-11, 개발 PC): 공용 서버 대 FlagEmbedding 은 dense 코사인 ≥ 0.999998, sparse 토큰 집합 일치, 가중치 차 ≤ 0.0006 이었다. fp32·fp16 끼리의 차이와 같은 크기다.

## 전환

전환과 되돌리기 모두 `x-common-env` 변경이라 적재 워커까지 다시 만들어진다 — 적재가 돌지 않을 때만 한다.

1. Portainer 스택 env 에 `EMBEDDING_BACKEND=http`를 넣고 스택을 업데이트한다. compose 에 `${EMBEDDING_BACKEND:-local}`로 선언돼 있어 스택 env 가 먹는다. 모델 이름(`EMBEDDING_SERVED_MODEL`)·주소·시간 한도도 같은 방식으로 바꿀 수 있다.
2. `x-common-env`를 쓰는 컨테이너가 모두 다시 만들어진다. 끝나면 gateway 를 재시작한다(옛 IP 로 가는 502 방지).
3. fastapi 로그에 `공용 임베딩 서버 응답 확인`이 찍히는지, `nvidia-smi`에서 fastapi·celery-research 가 줄었는지 본다.

## 되돌리기

스택 env 의 `EMBEDDING_BACKEND`를 `local`로 바꾸고(또는 지우고) 스택을 업데이트한 뒤 gateway 를 재시작한다. 이미지·데이터는 그대로다. 재색인은 필요 없다 — 두 갈래가 같은 값을 낸다.

- **먼저 GPU 여유를 본다**(`nvidia-smi`). local 은 fastapi·celery-research 에 bge-m3 를 다시 올린다(각 2~4GB). fastapi 는 모델을 못 올리면 기동을 멈추고, gateway 는 fastapi 가 떠야 뜬다 — 자리가 없으면 사이트 전체가 내려간다.
