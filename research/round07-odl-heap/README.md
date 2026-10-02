# round07 — ODL(java) 힙 상한 측정 (1회성, 2026-10-02)

opendataloader-pdf 2.5.9 는 PDF 를 java 로 변환한다. 운영(`nl-lib-celery-cpu`, 추출 4칸)에는 힙 상한이 없어
JVM 기본값(컨테이너가 보는 메모리의 1/4)까지 쓴다. 병리 문서 하나가 몇 초 만에 8GB 를 넘기는 것을 보고
`-Xmx` 를 얼마로 둘지 운영 이미지로 쟀다. 결과로 `ODL_JAVA_MAX_HEAP`(기본 3g — 사용자 결정 2026-10-02, 운영 서버 RAM 251GB·가용 131GB 라 4칸 최악 합계
약 13GB 를 감당한다)를 넣었다. 운영 서버에서 상한이 없으면 java 하나가 1/4 인 약 63GB 까지 쓸 수 있다.

## 방법

- 운영 이미지 `landsoftdocker/nl-lib-fastapi:latest`(Java 17, opendataloader-pdf 2.5.9 — 이 PC 캐시 이미지
  `sha256:d6d47828421e…`, 2026-09-30 받은 것)를 네트워크 없이 띄우고 round07 코드(측정 때 5ca8b68)를 `/app` 에 올려
  `extract_text_opendataloader` 를 그대로 부른다(`drun.sh`). PDF 는 `PDF_DIR`(기본 이 PC 의 `D:/SKOVIX/KCI/pdf`).
- `one.py` 가 문서 하나를 변환하며 컨테이너의 java 프로세스마다 VmHWM·VmRSS 를 20ms 간격으로 잰다.
  쪽 텍스트 sha1 로 상한 아래 추출 결과가 상한 없을 때와 같은지 본다. `driver.py` 가 문서 목록을 차례로 돈다.
- 문서 두 묶음
  - `docs.json` 61건 — 무거운 문서·실패 블록·2005년 이전·표 많은 문서 등 일부러 고른 표본(59건은 아래 docs.csv 에 있다)
  - `screen_ids.json` 688건 — `research/round07-ingest-regression/docs.csv`(이 PC 의 KCI PDF 752행, 고유 747건)에서
    61건 표본에 든 59건을 뺀 나머지 전부
- 실행(모두 `drun.sh` 로, 산출물은 `out/<TAG>.jsonl` 레코드와 `out/<TAG>.out` 한 줄 요약)
  - `run_all.sh` — 61건 × 상한 없음·3g·2g·1g, 상한 없음에 G1 로그
  - `run_bisect.sh` — 가장 무거운 정상 문서의 최소 힙과 무거운 문서 묶음의 384m~3g
  - `./drun.sh -Xmx2g /w/driver.py screen_xmx2g --gc --ids-file /w/screen_ids.json` — 688건
  - `./drun.sh - /w/driver.py recheck_nocap --ids KCI_FI000902436 KCI_FI002186558 KCI_FI002803488`와
    `./drun.sh -Xmx3g /w/driver.py recheck_xmx3g --ids …`(같은 3건) — 2g 화면 검사의 메모리 부족 3건 재측정
  - `side.py` — JAVA_TOOL_OPTIONS 부작용. `./drun.sh <JTO> /w/side.py <LABEL> <ID…>` 를 다섯 번:
    nojto(`-`, KCI_FI002029401·BADPDF), xmx2g(`-Xmx2g`, KCI_FI002029401·BADPDF·KCI_FI002990049),
    xmx1g(`-Xmx1g`, KCI_FI002990049), exitoom(`-Xmx1g -XX:+ExitOnOutOfMemoryError`, KCI_FI002990049),
    typo(`-Xmx2gb`, KCI_FI002029401). BADPDF 는 side.py 가 만드는 깨진 PDF. 결과는 `out/side_<LABEL>.json`
    (`.out` 은 실행 로그 뒤에 같은 JSON 을 찍은 것).
  - 요약은 `analyze.py`(두 실행 비교)와 `summarize_out.py`(아래 표·백분위). G1 원본 로그(`gc/*.log`)는 커밋하지 않는다
    (.gitignore) — 요약은 각 jsonl 레코드에 있다. `out/tiny_heap.out` 은 `-Xmx3m`·`64m`·`256m` 로 가벼운 문서 하나를 돌린 것.

## 결과

| 묶음 | 상한 없음 | 3g | 2g | 1g |
|---|---|---|---|---|
| 61건 성공 | 60 | 60 | 60 | 59 |
| 61건 추출 결과가 상한 없음과 같음 | — | 61 | 61 | 60 |
| 61건 걸린 시간 합(초) | 177.5 | 132.0 | 127.7 | 122.5 |

- 61건 중 실패 1건(`KCI_FI001238691` — 26쪽 문서다. 레코드의 `total_pages`·`n_pages` 1 은 메모리 부족 뒤 fitz 폴백 결과가 낸 값이다)은 상한이 없어도 10.5GB(이 PC 의 1/4)까지 쓰고 메모리 부족으로
  끝난다. 상한을 두면 같은 실패가 55초 → 17~21초로 빨리 끝난다.
- 정상 문서 중 가장 무거운 `KCI_FI002990049`(38쪽)는 1536m 에서 실패, 1664m 에서 성공(`run_bisect.sh`) —
  2g 는 이 문서보다 약 25% 여유, 3g 는 약 85% 여유.
- 688건(2g): 685 성공. java RSS 최고치(VmHWM — 힙 사용량 `gc_used` 가 아니다) 중앙값 140MB, p95 586MB, p99 806MB
  (`summarize_out.py`). 메모리 부족 3건을 다시 돌렸다
  (`out/recheck_*.out`):

  | 문서 | 상한 없음 | 3g | 2g |
  |---|---|---|---|
  | KCI_FI000902436 (9쪽) | 성공, 9.6GB | 메모리 부족 | 메모리 부족 |
  | KCI_FI002186558 (17쪽) | 10.6GB 쓰다 시간 초과 | 메모리 부족 | 메모리 부족 |
  | KCI_FI002803488 (41쪽) | 성공, 3.9GB | 성공(3.2GB) | 메모리 부족 |

  → 2g 와 3g 의 차이는 688건 중 1건. 메모리 부족 문서는 재저장본 재시도 뒤 fitz 텍스트로 간다(본문은 남고
  표 구조·머리말 제거를 잃는다).
- 부작용(`side_*.json`): `-Xmx2gb` 같은 오타면 JVM 이 뜨지 않아 **모든 문서가 fitz 텍스트로 조용히 떨어진다** →
  설정을 읽을 때 형식을 검사한다. `-Xmx` 만 주면 성공 때 stderr 는 비고 실패 요약에도 'Picked up' 줄이 끼지 않는다
  (ExitOnOutOfMemoryError 를 함께 주면 그 이름의 'Error' 때문에 요약에 낀다 — 쓰지 않는다).

## round07 에 반영

- `ODL_JAVA_MAX_HEAP`(config·`docker-compose.yml` x-common-env) — `^([1-9][0-9]*[mMgG])?$` 형식이고 1g 이상만 받는다
  (`3m`(`3g` 오타)이면 java 는 떠도 변환이 모두 실패한다 — `out/tiny_heap.out`. 1g 아래로는 무거운 문서부터 메모리
  부족이 는다 — 768m·512m 에서 가장 무거운 12건 중 2건, 384m 3건. 1g 는 상한 없을 때보다 61건 중 1건 더 실패). 빈 값 = 상한
  없음은 앱 설정에서만 된다 — compose 의 `${ODL_JAVA_MAX_HEAP:-3g}` 가 빈 스택 env 를 3g 로 채우므로 운영에서 풀려면
  `64g` 같은 큰 값(운영 서버의 JVM 기본값이 약 63GB)을 준다.
- `extractor._odl_child_env()` 가 ODL 자식의 환경에만 `JAVA_TOOL_OPTIONS=… -Xmx<값>` 을 붙인다(워커 환경은 그대로).
  java 의 RSS 는 힙 상한보다 0.2~0.3GB 크다(3g 에서 최고 3.29~3.38GB) — `celery-cpu` 4칸 최악 약 13GB. ODL 은
  `celery-worker`(동시 2)·`fastapi`(업로드)에서도 돈다.
- 확인: `check_round07.py` 를 운영 이미지로 돌려 java 가 `-Xmx2g`/`-Xmx3g` 를 받고 워커 환경은 비어 있음,
  `KCI_FI002803488` 이 2g 에서 fitz·3g 에서 정상(최고 3.2GB)임을 봤다. 함께 돌린 5건 모두 본문에 `&lt;`·`&amp;` 가
  남지 않았다(`<표 1>` 등 — 2.5.9 markdown 이스케이프 되돌리기). `drun.sh` 는 `ODL_JAVA_MAX_HEAP` 을 비우므로 이 확인은
  `docker run … -e ODL_JAVA_MAX_HEAP=2g … /w/check_round07.py KCI_FI002803488` 처럼 값을 직접 준다. 결과: `out/check_round07.out`.
