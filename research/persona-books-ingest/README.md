# 페르소나 에이전트 책 17권 — 소장자료 적재 (2026-10-23)

도서관 대회에 함께 나가는 페르소나 에이전트(인물 성격 RAG)와 같은 책을 우리 소장자료(문학·도서)에도 넣어 두 방식의 차이를
보이기 위한 1회성 적재. 원문은 `Downloads/20261020_책원문_보관본`(목록.md)과 카카오톡으로 받은 PDF 3개.

## 범위 (사용자 확정 2026-10-23)

- 운영에 이미 있는 28권(위키문헌·공유마당 한국 문학 8, 구텐베르크 영어 20)은 뺐다 — 겹침은 운영 DB 읽기 쿼리로 확인.
- 새로 넣는 17권(`books.json`): 한국 5(만세전·소나기·적빈·춘향전·허생전), 영어 txt 9(미녀와 야수·빨간 모자·주홍색 연구·
  플랜더스의 개·로빈 후드의 모험·불핀치의 신화·안데르센 동화집·키다리 아저씨·페로 동화집), PDF 3(금도끼·평원공주와 우온달·
  Corea, Without and Within). 소나기(황순원 2000 사망)·만세전(염상섭 1963 사망)은 저작권이 남았을 수 있다는 점을 알리고
  넣기로 했다. 03_제외_원문·04_장별_분리본은 쓰지 않는다.
- 분류: Griffis 『Corea, Without and Within』만 book(조선 역사·풍속·종교 논픽션 + 하멜 표류기 — 원본 청구기호 DS902 .G85),
  나머지는 literature. doc_type 은 카탈로그 행에 넣고 적재 작업 params 에는 넣지 않는다.
- 영어책은 title 을 한국어 제목, title_remainder 를 원제로 — 한국어 제목 검색이 되게(영어 원서는 한국어 제목이 데이터에 없으면
  못 찾는다 — research/book-search-title-recall).
- 파일과 내용이 다른 것: '인어공주' 파일은 『안데르센 동화집』 18편이고 「인어공주」는 없다(초록에 적었다). '빨간모자' 파일은
  그림 동화 한 편이다. 금도끼 PDF 의 2·3쪽은 위키문헌 라이선스라 1쪽만 넣는다.

## PDF 만들기 (`render_pdfs.py`)

적재 파이프라인은 PDF 만 받는다. txt 는 표지 쪽(제목·원제·저자·연도) + 본문 PDF 로 그린다(PyMuPDF Story, 맑은 고딕 — 원문의
한자·문장부호를 모두 가진 것을 확인). 섹션은 추출 뒤 의미 경계로 나뉘므로(`split_into_sections` → `semantic_chunk`) 장 제목은
원문 뷰어에서 읽기 좋게 굵게만 한다.

- 한국어 원문은 인쇄본을 옮겨 낱말 중간에서 줄이 끊겨 있다 — 이으면 낱말이 붙거나 갈려 줄을 그대로 둔다. 영어는 문단 안의 줄을 잇는다.
- 걷어 낸 것: 쪽 번호(`- 7 -`, 소나기·춘향전), 위키문헌 내보내기 머리(적빈), `[Illustration…]`·`* * *`(영어 3권).
- 춘향전의 사용자 정의 영역 글자(옛 한글 등 13자)는 그릴 수 없어 □ 로 바꿨다.
- **가운뎃점 '․'(U+2024)는 PDF 에서 다시 뽑으면 NUL(0x00)이 된다** — 만세전 1자·허생전 14자. NUL 이 든 본문은 DB 저장이
  실패한다(kci-full-236k 실패 'A string literal cannot contain NUL' 2건과 같은 종류). '·'(U+00B7)로 바꿔 그린다.

검증(`render_report.json`): txt 14권 모두 원문 40자 조각 300개가 PDF 글자에 그대로 있다(coverage 1.0, 공백 뺀 길이 비율 1.0),
제어 문자 0, 합자 0. Griffis 는 344쪽 스캔본으로 글자층이 없는 쪽 21쪽은 적재 때 VLM OCR 로 간다(문서당 60쪽 상한 안).

## 서버 절차

1. 백업 — `/usr/local/bin/nl-lib-pg-backup`.
2. `out/persona_books.tar.gz`(books.json·stage_books.py·pdf/ 17개, 16MB)를 서버 `/data/nl-lib/data/persona_books/` 에 푼다
   (fastapi 컨테이너 안에서는 `/app/data/persona_books/`).
3. 미리 보기 → `--apply`:
   `docker exec -w /app -e PYTHONPATH=/app nl-lib-fastapi python /app/data/persona_books/stage_books.py [--apply]`
   - 카탈로그는 새 ID 만 INSERT … ON CONFLICT DO NOTHING(같은 ID 의 다른 행이 있으면 멈춤 — upsert 는 덮어써서 쓰지 않는다).
   - MinIO 는 `originals/<id>/<id>.pdf` 가 없을 때만 올린다(크기가 다른 같은 키가 있으면 멈춤).
   - 적재 목록 `manifests/persona-books-20261023/canary.jsonl`(소나기·빨간 모자)·`main.jsonl`(나머지 15).
4. 카나리 작업(스크립트가 찍는 명령) → validation_report 의 to_ingest 2·missing 0·already_embedded 0 확인 → start → 끝나면
   섹션·요약·검색 확인 → main 작업.
5. params 에 `doc_type`·`reembed` 를 넣지 않는다. 작업 중에는 스택 업데이트·Recreate 를 하지 않는다(함정 16).

## 결과 (2026-10-23 운영)

카탈로그 새 행 17 INSERT(같은 ID 의 다른 행 0 — 기존 행은 건드리지 않음) → MinIO 17개 → 카나리 2권 completed → main 15권 completed
(작업 1afccd1d-884f-4905-a5a8-752decce3d04). 확인은 `verify_ingest.py`(운영 API 읽기만) → `verify_report.txt`.

- 17권 모두 적재·요약 칸(요약·소개·줄거리·읽기 효과·테마) 채워짐, '책' 단정 표현 0, 썸네일·원문 PDF 200.
- 소장자료 검색 30질의 중 28개가 1위. 빠진 둘: '셜록 홈즈와 왓슨의 첫 만남' 4위(1위가 이미 있던 『셜록 홈즈의 모험』 —
  틀린 답은 아니다), '성냥팔이 소녀' 12위(『안데르센 동화집』 18편 중 한 편이라 책 단위 요약에 잘 안 잡힌다).
- 딥리드(`/api/books/chat/{id}`) 몇 문항: Griffis '하멜 일행은 얼마나 머물렀고 어떻게 떠났나' → 쪽 인용과 함께 정확(p.118–119).
  영어 원문 책에 한국어 질문은 약하다 — 불핀치 '프로메테우스는 왜 벌을 받았나'는 못 찾았고 영어로 물으면 찾는다(p.15),
  '불을 준 이야기'로 바꿔 물으면 한국어로도 찾는다. 키다리 아저씨 '왜 키다리 아저씨라 부르나'는 한·영 모두 못 찾았다 — 답은
  원문 3·6쪽에 있으나 'Daddy-Long-Legs' 가 거의 모든 편지 머리에 나와 그 쪽이 검색에서 두드러지지 않는다. 적재 문제가 아니라
  이미 있던 구텐베르크 영어책과 같은 검색 성질이다.

## v2 — 표지 쪽 내부 문구 빼고 다시 적재 (2026-10-23 저녁, 사용자 결정)

부스 시연 질문을 운영에서 확인하다 txt 렌더본 14권의 1쪽(표지)에 넣은 출처 메모('SKOVIX 소장자료 원문 — 페르소나 에이전트
원문 보관본(2026-10-20)에서 옮김')가 원문 뷰어 1쪽과 검색 대목(청크)에 그대로 보이는 것을 찾았다. 표지에서 그 줄만 빼고(제목·
원제·저자·연도만) 다시 적재한다. 쪽 수는 같고 2쪽부터 글은 옛 판과 바이트까지 같다 — 답 글의 쪽 번호가 바뀌지 않는다.
금도끼·우온달·Griffis 는 PDF 를 그대로 옮겨 문구가 없어 다시 하지 않는다(Griffis 는 스캔본이라 Qwen 이 꺼진 지금 다시 하면
OCR 쪽 본문을 잃는다).

- `render_pdfs.py <14권>` → `bundle_v2.py`(out/v2/ — pdf 14·sha256s.txt·서버 스크립트, out/persona_books_v2.tar.gz).
- 서버 `/data/nl-lib/data/persona_books/v2/`:
  - `precheck_extract.py`(nl-lib-celery-cpu — 운영 ODL 로 추출만, OCR 로 가는 쪽이 0인지)
  - `restage_v2.py`(nl-lib-fastapi)
    - `snapshot`: 다시 적재 전 14행 요약 글 JSON — 마무리 단계는 summary·themes·introduction 을 무조건 덮고 LLM 이 실패하면 NULL
    - `report`: 카탈로그·섹션·Milvus 청크·원문·썸네일 캐시, 읽기만
    - `stage`: 옛 판을 `backup/persona-books-20261023-v1/` 에 올리고 해시 확인 뒤 같은 키에 덮기, 썸네일 캐시 치우기, 적재 목록
    - `thumbs`·`restore`
- 잡 params `{"reembed":true,"skip_cover":true,"high_water":1}`(카나리는 `max_attempts:1`) — reembed 가 없으면 14권이 모두
  already_embedded 로 빠진다. 잡의 지우기(Milvus 그 책 청크·book_sections)는 모두 book_id 로 좁혀져 있고, skip_cover 라 표지 칸
  (cover_image_key·cover_prompt)·covers/ 는 건드리지 않는다.
- 새 키(.v2.pdf)를 같은 폴더에 두지 않는다: 원문 뷰어·썸네일(`_resolve_original_key`)이 폴더의 첫 객체(사전순)를 열어 옛 판이
  열린다.
- 금지:
  - 옛 잡(v1 카나리·`1afccd1d`) retry 와 옛 `main.jsonl` 로 reembed — Griffis 가 섞인다
  - 백필 API(14권 밖까지 다시 쓴다)
  - 책 한 권 재시도 `POST /api/books/{id}/retry`(잡 파라미터 없이 돌아 표지를 새로 만든다)
  - 진행 중 스택 업데이트·Recreate·fastapi 재시작(함정 16·18·20). nuxt 단독 Recreate 는 괜찮다.
- 결과(2026-10-26 운영):
  - 사전 점검: 운영 ODL 로 14권 모두 OCR 0(전 쪽 opendataloader), MILVUS_RECREATE_ON_MISMATCH 는 embed·control·fastapi 모두
    false, PSN 옛 잡 모두 done.
  - 백업 `library_catalog_20261026T102538.dump`, `snapshot`(catalog_before.json, 14행 요약 빈 행 0).
  - 적용 전 report: 14권 모두 문구가 섹션 1·청크 1에 있었다.
  - 적재: 카나리(소나기) → 나머지 13권(잡 `38aed8f5-4c3d-4fd9-886f-5c4400cabdc8`). 아이템 14개 모두 done·finalized,
    sections_failed 0, ocr_errors 0, cover false.
  - 적용 뒤 report: 14권 모두 원문 v2, 섹션·청크 문구 0, 섹션 수 = 섹션 요약 수, 요약·테마·소개·줄거리·읽고 난 후 모두 채워짐.
    청크 수는 그대로이고 섹션은 빨간 모자 4→3, 안데르센 153→152 로 표지 쪽 경계만 달라졌다.
  - `verify_ingest.py` → `verify_report_v2.txt`: 17권 모두 '책' 0·빈칸 없음·썸네일/원문 200. 검색 30질의 중 28개 1위로
    10-23 과 같고, '성냥팔이 소녀' 만 12위 → 4위로 올랐다.
  - 부스 시연 질문의 쪽 번호는 그대로다(소나기 p.2·p.7–8, 불핀치 p.15–16, 플랜더스의 개 p.15). 출처를 펼친 조각 순서만
    바뀌었다(소나기 '이 바보' 3/3 → 1/3, 불핀치 조각 1 → 2개).
