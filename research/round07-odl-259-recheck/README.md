# round07 — opendataloader-pdf 2.5.0 대 2.5.9 재검증 (1회성, 2026-10-02)

round07 의 ODL 관찰·구현 근거는 개발 PC 의 opendataloader-pdf 2.5.0 으로 냈는데, 운영이 적재해 온 버전은
2.5.9 다(`docker exec nl-lib-celery-cpu pip show opendataloader-pdf`, `app/requirements.txt` 를 `==2.5.9` 로 고정 —
fe1be0c). 같은 문서를 두 버전으로 돌려 round07 의 판정이 같은지 봤다. 런북 §9 의 "2.5.9 비교 전에는 카나리를
시작하지 않는다"의 근거가 이 폴더다.

## 방법

- 표본 `sample.json` 45건 — `make_sample.py` 가 `research/round07-ingest-regression/docs.csv` 에서 묶음별로 골랐다:
  이름 붙은 사례 10(병리·`<br>` CMap·그림 많은 문서 등)·디지털 본문 10·2005년 이전 8·앞쪽 짧은 쪽 8·10-01 실패
  블록 7·`<br>` 격자 2. 문서마다 고른 까닭이 `why` 에 있다.
- `compare_driver.py` — 이 PC(Windows, Java 18)에서 문서 × 버전마다 워커 프로세스를 띄우고 `PYTHONPATH` 맨 앞에
  그 버전의 패키지 폴더를 둬 round07 의 `extract_text` 를 그대로 부른다(VLM 은 "OCR_STUB" 로 막는다 — 네트워크
  없음). 자식이 실제로 어느 버전을 import 했는지 워커마다 확인한다(`child_versions_seen`). 쪽 수·쪽 본문·표 충전율·
  OCR 판정과 사유·오류·ODL 시간을 비교해 `compare_summary.json` 에 쓴다. `classify_diffs.py` 가 본문 차이를 종류별로
  나눈다(`norm.py` 는 비교용 공백 정규화).
- 스크립트의 `PY`(파이썬)·`PDF_DIR`·`ODL_DIRS`(두 버전의 pip --target 폴더) 상수는 이 PC 의 임시 폴더를 가리킨다 —
  다시 돌릴 때 바꾼다. 패키지 폴더·ODL 산출물(약 800MB)은 싣지 않는다.

## 결과

| | 1차 (1f4954b — 되돌리기 전) | 2차 (405eaf5 — 되돌리기·힙 3g 뒤) |
|---|---|---|
| 비교한 문서 | 45 | 45 |
| 쪽 수 같음 | 45 | 45 |
| 표 충전율 같음 | 45 | 45 |
| OCR 로 보낸 쪽 같음 | 45 | 45 |
| 오류 같음 | 45 | 44 (아래) |
| 쪽 본문이 모두 같음 | 26 | **35** |
| ODL 시간 합(2.5.0 / 2.5.9) | 167.8 / 165.3초 | 160.4 / 93.2초 |

- **1차의 본문 차이**(`first_run/classify_diffs.json`, 쪽 기준): HTML 이스케이프(`&lt; &gt; &amp;`) 123쪽, 쉼표·괄호 앞
  공백 8쪽, 목록 머리 `*`·`※` 빠짐(#648) 6쪽, 둘이 겹친 것 3쪽, 기타 3쪽. 이스케이프 때문에 ODL 본문 길이가 4~5배
  로 세져 판정 경계에 닿는 쪽이 생길 수 있었지만 이 표본에서는 판정이 바뀐 쪽이 없었다. OCR 사유 글자 수만
  1글자 다른 문서가 1건이다(`ocr_reason_text_diffs`).
- **2차**: 되돌리기(399ee25)로 이스케이프 차이가 사라져 본문이 같은 문서가 35건이 됐다. 남은 10건은 목록 기호·
  공백 1~2글자 차이다. 오류가 다른 1건은 병리 문서 `KCI_FI001238691` 이다 — 2.5.0 은 39초 시간 초과 두 번(78초),
  2.5.9 는 힙 상한 3g 에 걸려 메모리 부족 두 번(12.8초)으로 끝나고 둘 다 fitz 텍스트로 간다(결과는 같다). 2차는
  두 버전 모두 `ODL_JAVA_MAX_HEAP` 기본값 3g 아래에서 돌았다.
- 2.5.9 의 `image_output=embedded` 와 `off` 비교(9건): 쪽 수 같고 차이는 `<br>`·`[그림]`·표 격자 표시뿐이다.
- **이스케이프 범위**: `jar_entities.py`(`jar_entities.out`)가 두 jar 의 자체 클래스 상수를 읽었다 — 2.5.9 의
  `MarkdownGenerator` 에만 `&amp;`·`&lt;`·`&gt;` 가 있고 2.5.0 에는 없다. `MarkdownSyntax` 의 `&nbsp;` 는 두 버전 모두
  있지만 markdown 출력에는 나오지 않았다 — `entity_census.py`(`head_run/entity_census.json`)가 2차 실행의 원본
  markdown 을 세니 2.5.0 은 엔티티 0개, 2.5.9 는 `&lt;` 433·`&gt;` 248·`&amp;` 82 뿐이다. 그래서 되돌리기는 이 셋만 한다.
- **운영 이미지(Linux, OpenJDK 17)** — `prod_image/prod_check.py`: 같은 45건을 운영 이미지로 돌려 Windows 2.5.9
  결과와 쪽 본문·충전율·OCR 판정이 모두 같았고(`equiv_run.out`), 문서마다 남은 java·좀비·임시 파일이 없었다.
  시간 초과는 `killpg` 로 java 까지 끝나고(`kill_slow.out` — `java_after` 비어 있음), 부모가 먼저 죽어도 자식이 SIGALRM 으로 스스로 끝낸다
  (`alarm_KCI_FI001238691.json` — 기대 13초, 14.6초에 모두 사라짐). `quiet=True` 면 stdout·stderr 가 비어 있다
  (`quiet.json`). 메모리 20GB 로 묶은 컨테이너에서 병리 문서 4개를 동시에 돌리면 java 합계가 20.2GB 까지 차
  커널이 죽였다(`par4_slow_mem20.json`) — 힙 상한(`research/round07-odl-heap`)을 둔 까닭의 하나다.
- 머리말·꼬리말: 표본 45건의 ODL json 에는 header/footer 요소가 없어 `hf_probe/` 가 그런 요소가 있는 10건을 따로
  골라 두 버전의 요소 종류·쪽이 같은지 봤다(`hfprobe_*_B.json`).
- Windows 에서는 시간 초과 때 자식 파이썬만 끝나고 java 손자가 남는다(`_kill_process_group` 의 Windows 분기 —
  개발 PC 한정). 2차에서도 병리 문서의 2.5.0 재저장본 변환이 3.3GB 로 남아 손으로 끝냈다.

## 결론

round07 의 판정(쪽 수·OCR 라우팅·표 충전율)은 2.5.9 에서도 2.5.0 과 같다. markdown 이스케이프는 되돌리기로 맞췄고,
남은 차이는 목록 기호·공백 몇 글자다. 카나리를 시작해도 된다.
