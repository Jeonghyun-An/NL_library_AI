# NL-Lib — 국립중앙도서관 의미 기반 검색 시스템

**작성일:** 2026-04-15  
**작성자:** 안정현  
**프로젝트명:** NL-Lib (National Library - Semantic Search)

---

## 1. 프로젝트 개요

### 1.1 목적

국립중앙도서관의 기존 키워드 검색을 **의미 기반 RAG(Retrieval-Augmented Generation) 검색**으로 전환하는 프로덕션 레벨 시스템.

사용자가 "한강의 채식주의자와 비슷한 책 찾아줘"처럼 자연어로 검색하면 도서 원문을 이해하여 유사 도서를 추천하고, LLM이 생성한 추천 이유와 도서 요약을 함께 제공한다.

### 1.2 주요 기능

- **의미 기반 검색**: 키워드 매칭이 아닌 원문 임베딩 기반 유사도 검색
- **Contextual Chunking**: 각 청크에 섹션 요약을 앞에 붙여 임베딩 → BGE-M3의 512토큰 한계 내에서 문맥 있는 벡터 생성
- **계층적 요약**: 섹션별 LLM 요약 → 섹션 요약 합산 → 도서 전체 요약 (126K 컨텍스트 활용, 4000자 제한 없음)
- **문서 유형별 특화 요약**: KDC 코드 기반으로 문학(800~899) / 일반도서 / 정책·법령 문서를 자동 분류, 유형별 최적화된 프롬프트 적용
- **도서 추천 이유 생성**: 검색 시 저장된 도서 요약 + 상위 매칭 청크를 활용해 "왜 이 책인가"를 LLM이 실시간 생성
- **PDF 썸네일**: MinIO에서 PDF 1페이지를 fitz로 렌더링, 캐싱하여 제공
- **멀티모달 OCR**: 디지털 PDF → fitz, 스캔본 → Gemma 4 VLM fallback
- **쿼리 재작성**: 사용자 입력을 LLM으로 의미 확장 후 검색

### 1.3 아키텍처 방향

```
초기: MARC/MODS 메타데이터 요약 → 임베딩
현재: PDF 원문 OCR → 섹션 분할 → 섹션 요약(LLM) → Contextual 청킹 → 임베딩
```

원문 기반으로 전환하여 메타데이터에 없는 내용도 검색 가능. 섹션 요약을 청크 임베딩에 주입함으로써 "이 문단이 어떤 맥락에 있는지"를 벡터에 반영.

---

## 2. 기술 스택

| 구분          | 기술                                      | 역할                                                       |
| ------------- | ----------------------------------------- | ---------------------------------------------------------- |
| **LLM**       | Gemma 4 E4B (vLLM, 126K 컨텍스트)         | 섹션 요약, 도서 요약, 쿼리 재작성, 추천 이유 생성, VLM OCR |
| **Embedding** | BAAI/bge-m3 (FlagEmbedding, 1024차원)     | Contextual 텍스트 벡터화                                   |
| **Reranker**  | jinaai/jina-reranker-v2-base-multilingual | Cross-Encoder 리랭킹 (8K 컨텍스트)                         |
| **Vector DB** | Milvus 2.4.6                              | 청크 임베딩 저장·검색                                      |
| **RDB**       | PostgreSQL 16                             | 도서 메타데이터 + 섹션 원문 + 섹션 요약                    |
| **Queue**     | Redis 7 + Celery                          | 수집 비동기 처리                                           |
| **Storage**   | MinIO                                     | 원본 PDF + 썸네일 캐시                                     |
| **Backend**   | FastAPI                                   | REST API                                                   |
| **Frontend**  | Nuxt 3                                    | 검색 UI                                                    |
| **Gateway**   | Nginx                                     | 라우팅 (:92)                                               |
| **Infra**     | Docker + Portainer                        | 컨테이너 관리                                              |
| **Server**    | NVIDIA H200 140GB                         | GPU 서버                                                   |

### 2.1 리랭커 선정 근거 (Jina Reranker v2)

| 항목          | bge-reranker-v2-m3 | **Jina Reranker v2** |
| ------------- | ------------------ | -------------------- |
| 파라미터      | ~568M              | ~278M                |
| 컨텍스트      | 512 토큰           | **8192 토큰**        |
| 속도 (20청크) | ~0.5초             | ~0.3초               |
| VRAM          | ~1.5GB             | ~0.8GB               |

도서 원문 청크가 긴 경우가 많아 8K 컨텍스트 지원이 결정적 요인.

### 2.2 LLM 선정 근거 (Gemma 4 E4B)

- **126K 컨텍스트**: 섹션 전체를 LLM에 전달 가능, 섹션 요약 합산으로 도서 전체 요약 가능
- **멀티모달(비전+텍스트)**: 스캔 PDF VLM OCR fallback
- **4B 파라미터**: H200에서 다른 서비스와 GPU 공유 가능 (~22GB VRAM, `gpu_memory_utilization 0.3`)
- vLLM OpenAI 호환 API → 추후 한국어 특화 모델로 교체 용이

---

## 3. 시스템 아키텍처

### 3.1 전체 구성

```
사용자
  ↓
Nginx (Gateway :92)
  ├── /         → Nuxt 3 (검색 UI)
  └── /api/     → FastAPI (:18002)
                    ├── 검색 파이프라인 (실시간)
                    ├── 관리 API
                    └── 수집 파이프라인 (Celery 비동기)
```

### 3.2 데이터 수집 파이프라인

```
PDF 업로드 → MinIO 저장 (originals/{book_id}/)
  ↓
Celery Task: process_book_file
  │
  ├── ① 텍스트 추출
  │     fitz(PyMuPDF): 디지털 PDF (글자 수 > 50/페이지)
  │     Gemma 4 VLM: 스캔본 fallback
  │
  ├── ② 섹션 분할 (3000~5000 토큰 단위)
  │     → PostgreSQL book_sections 저장 (full_text, page_start/end, token_count)
  │
  ├── ②-b 섹션별 요약 병렬 생성 (asyncio.Semaphore(8), vLLM 동시 8개)
  │     문서 유형 자동 분류 (KDC + 제목 키워드):
  │       literature (KDC 800~899): 핵심 사건·인물 심리·문체·정서·상징
  │       book (기본값):            핵심 질문·주장·개념·연관 키워드
  │       policy (KDC 320~359):     조항 목적·규정·적용 범위·정의
  │     → 생성된 요약을 book_sections.summary에 저장
  │
  ├── ③ 시맨틱 청킹
  │     문장 분리 (정규식) → BGE-M3 임베딩 유사도로 의미 경계 감지
  │     → min 128 ~ max 1024 토큰 제약 → section_idx 매핑
  │
  ├── ④ Contextual 임베딩 → Milvus 저장
  │     embed("[섹션 요약] {section.summary}\n\n[본문] {chunk.text}")
  │     저장: 원본 chunk.text (표시용), 임베딩: contextual 텍스트
  │
  └── ⑤ 도서 요약 생성 (1회)
        섹션 요약 전체 합산 → Gemma 4 (126K 활용)
        → PostgreSQL library_catalog.summary 업데이트
```

### 3.3 RAG 검색 파이프라인 (book 모드)

```
사용자 입력: "한강의 채식주의자와 비슷한 책"
  ↓
① Query Rewriter (Gemma 4)
   → 의미 확장된 검색 쿼리 생성
  ↓
② Embedder (BGE-M3) → 쿼리 벡터화
  ↓
③ Milvus 벡터 검색 (COSINE, top_k × 8)
   → 도서별 청크 그룹핑 → 상위 top_k 도서 선별
  ↓
④ Reranker (Jina v2) — 도서별 청크 내부 리랭킹
  ↓
⑤ 추천 이유 생성 (상위 3권 병렬, asyncio.gather)
   DB에서 book.summary 조회 + 상위 매칭 청크 3개
   → Gemma 4: "왜 이 책이 이 질의에 적합한지" 2~3문장 생성
  ↓
결과 반환: 도서 정보 + 추천 이유 + 관련 구절
```

### 3.4 검색 모드

| 모드      | 설명                  | 반환                             |
| --------- | --------------------- | -------------------------------- |
| **book**  | 도서 단위 추천 (기본) | 도서별 청크 그룹 + LLM 추천 이유 |
| **chunk** | 관련 문단 직접 표시   | 청크 목록 + LLM 답변             |

### 3.5 Contextual Chunking 설계

BGE-M3의 512토큰 한계 안에서 문맥을 살리기 위해 임베딩 시 섹션 요약을 앞에 주입:

```
임베딩 입력:
  "[섹션 요약] 이 섹션은 주인공 영혜가 채식을 통해 가부장적 폭력에
   저항하는 과정을 다룸
   [본문] 채식주의자는 폭력에 맞서는 방식으로..."

→ "채식 레시피"가 아닌 "실존적 저항"으로 임베딩 정렬
→ "폭력에 저항하는 소설" 쿼리와 올바르게 매칭
```

저장은 원본 chunk.text로 유지 (표시·생성용). 임베딩만 contextual 텍스트 사용.

### 3.6 계층적 요약 구조

```
섹션 원문 (~3000~5000 토큰)
    ↓ LLM (병렬, Semaphore 8)
섹션 요약 (~300자) × N개 — book_sections.summary
    ↓ 청크 임베딩 시 prefix로 활용
    ↓ LLM (1회, 섹션 요약 전체 합산)
도서 요약 (~600자) — library_catalog.summary
    ↓ 검색 시 추천 이유 생성에 활용
```

---

## 4. 데이터 설계

### 4.1 PostgreSQL 테이블

**library_catalog** — 도서 메타데이터 (MARC 기준, MODS 보완)

| 필드                                        | 설명                                     |
| ------------------------------------------- | ---------------------------------------- |
| cnts_id                                     | PK (CSV 기준)                            |
| title, personal_author, publisher, pub_date | 서지 정보                                |
| kdc                                         | 한국십진분류 (문서 유형 판별 기준)       |
| subject, keyword                            | 주제·키워드                              |
| summary                                     | LLM 생성 도서 요약 (섹션 요약 합산 기반) |
| is_embedded                                 | 수집 완료 여부                           |

**book_sections** — 도서 원문 섹션

| 필드                  | 설명                                     |
| --------------------- | ---------------------------------------- |
| book_id               | = cnts_id                                |
| section_idx           | 섹션 순번                                |
| full_text             | 원문 전체                                |
| summary               | LLM 생성 섹션 요약 (Contextual 임베딩용) |
| page_start / page_end | 페이지 범위                              |
| token_count           | 토큰 수 (예산 계산용)                    |

### 4.2 Milvus 컬렉션 (nl_lib_embeddings)

| 필드                  | 타입               | 설명                            |
| --------------------- | ------------------ | ------------------------------- |
| chunk_id              | VARCHAR (PK)       | `{book_id}__{chunk_idx:04d}`    |
| book_id               | VARCHAR            | = cnts_id                       |
| chunk_idx             | INT16              | 청크 순번                       |
| section_idx           | INT16              | 소속 섹션 포인터                |
| text                  | VARCHAR            | 원본 청크 텍스트 (표시용)       |
| page_start / page_end | INT16              | 페이지 범위                     |
| embedding             | FLOAT_VECTOR(1024) | Contextual 텍스트 BGE-M3 임베딩 |

### 4.3 MinIO 버킷 구조 (nl-lib-bucket)

```
originals/{book_id}/{filename}.pdf   — 원본 PDF
thumbnails/{book_id}.jpg             — PDF 1페이지 썸네일 캐시
```

### 4.4 데이터 흐름

```
엑셀 (MARC/MODS)  →  library_catalog (cnts_id, summary)
                              ↑
원본 PDF  →  book_sections (full_text, summary)
                    ↑
              Milvus chunks (contextual 임베딩)
```

---

## 5. 프로젝트 구조

```
nl-lib/
├── docker-compose.yml
├── .env
├── infra/
│   └── vllm/Dockerfile              # 커스텀 vLLM (Gemma 4 지원)
│
├── app/                              # FastAPI 백엔드
│   ├── main.py                       # lifespan: DB 테이블 생성 + 컬럼 마이그레이션
│   ├── core/
│   │   ├── config.py
│   │   └── deps.py
│   ├── api/
│   │   ├── book.py                   # 검색 + 수집 + 썸네일 + CRUD
│   │   ├── admin.py                  # 현황 대시보드, 도서·섹션·청크 목록
│   │   └── health.py
│   ├── services/
│   │   ├── ingestion/
│   │   │   ├── extractor.py          # fitz → VLM fallback OCR
│   │   │   ├── chunker.py            # 시맨틱 청킹 (BGE-M3 유사도 경계)
│   │   │   ├── embedder.py           # BGE-M3 (FlagEmbedding)
│   │   │   ├── indexer.py            # Milvus 저장·검색
│   │   │   └── summarizer.py         # 섹션 요약 / 도서 요약 / 문서 유형 판별
│   │   └── search/
│   │       ├── query_rewriter.py     # 쿼리 의미 확장
│   │       ├── reranker.py           # Jina Reranker v2
│   │       ├── context_expander.py   # 원문 섹션 확장 (126K 예산)
│   │       └── pipeline.py           # 검색 파이프라인 + 추천 이유 생성
│   ├── models/
│   │   ├── book.py                   # library_catalog ORM
│   │   └── section.py                # book_sections ORM (summary 컬럼 포함)
│   ├── schemas/book.py
│   ├── repositories/
│   │   ├── book.py
│   │   └── section.py
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks.py                  # 수집 파이프라인 (섹션 요약 병렬 생성 포함)
│   └── db/postgres.py
│
└── frontend/                         # Nuxt 3
    ├── pages/index.vue               # 검색 메인 (랜딩 → 결과 페이지)
    └── components/
        ├── SearchInput.vue           # 검색 입력창
        ├── TopResult.vue             # Top 1 도서 (추천 이유 + 상세 정보)
        ├── BookCard.vue              # 추천 도서 카드 그리드
        └── BookCover.vue             # PDF 썸네일 (오류 시 placeholder)
```

---

## 6. API 엔드포인트

### 검색 / 도서

| Method | Path                           | 설명                               |
| ------ | ------------------------------ | ---------------------------------- |
| POST   | /api/books/search              | 의미 기반 검색 (chunk/book 모드)   |
| GET    | /api/books/{cnts_id}/thumbnail | PDF 1페이지 JPEG 반환 (MinIO 캐싱) |
| GET    | /api/books/{cnts_id}           | 도서 단건 조회                     |

### 수집

| Method | Path                           | 설명                        |
| ------ | ------------------------------ | --------------------------- |
| POST   | /api/books/ingest/upload       | 단일 PDF 업로드 → 수집      |
| POST   | /api/books/ingest/upload/batch | 복수 PDF 일괄 업로드 → 수집 |
| POST   | /api/books/ingest/batch        | MinIO 기존 파일 배치 수집   |
| POST   | /api/books/catalog/load        | 엑셀 메타데이터 적재        |
| GET    | /api/books/ingest/{task_id}    | Celery 태스크 상태 조회     |

### 관리

| Method | Path                                | 설명                               |
| ------ | ----------------------------------- | ---------------------------------- |
| GET    | /api/admin/status                   | 전체 현황 (도서·섹션·Milvus·MinIO) |
| GET    | /api/admin/books                    | 도서 목록 (페이지네이션)           |
| GET    | /api/admin/books/{cnts_id}/sections | 섹션 목록                          |
| GET    | /api/admin/books/{cnts_id}/chunks   | Milvus 청크 목록                   |
| GET    | /api/admin/minio/files              | MinIO 파일 목록                    |

---

## 7. 인프라 구성

### 7.1 Docker Compose 서비스

| 서비스   | 이미지                               | 호스트 포트  | 비고                      |
| -------- | ------------------------------------ | ------------ | ------------------------- |
| etcd     | quay.io/coreos/etcd:v3.5.0           | -            | Milvus 메타데이터         |
| minio    | minio/minio:latest                   | 21000, 21001 | 원본 파일 + 썸네일 캐시   |
| milvus   | milvusdb/milvus:v2.4.6               | -            | 벡터 DB                   |
| postgres | postgres:16-alpine                   | 15432        | RDB                       |
| redis    | redis:7-alpine                       | 16379        | 캐시/큐                   |
| vllm     | landsoftdocker/nl-lib-vllm:latest    | 18081        | Gemma 4 E4B               |
| fastapi  | landsoftdocker/nl-lib-fastapi:latest | 18002        | API 서버                  |
| celery   | landsoftdocker/nl-lib-fastapi:latest | -            | 수집 워커 (concurrency=2) |
| nuxt     | landsoftdocker/nl-lib-nuxt:latest    | -            | 프론트엔드                |
| gateway  | nginx:alpine                         | 92           | 라우팅                    |

> PaddleOCR은 현재 비활성화 (주석 처리). Gemma 4 VLM이 스캔본 OCR을 대체.

### 7.2 GPU 메모리 현황 (H200 140GB)

| 프로세스                            | VRAM              | 역할          |
| ----------------------------------- | ----------------- | ------------- |
| nl-lib vLLM (Gemma 4 E4B, util 0.3) | ~22GB             | LLM 서빙      |
| nl-lib FastAPI (BGE-M3 + Jina)      | ~2.4GB            | 임베딩·리랭킹 |
| nl-lib Celery (BGE-M3 + Jina)       | ~2.4GB            | 수집 워커     |
| 타 스택 (library-ragnet 등)         | ~35GB             | 병행 운용     |
| **합계**                            | **~62GB / 143GB** |               |

### 7.3 vLLM 주요 설정

```yaml
--max-model-len 126976   # 126K 컨텍스트
--gpu-memory-utilization 0.3
--max-num-seqs 16        # 동시 처리 (섹션 요약 Semaphore 8로 절반 사용)
--enforce-eager          # CUDA graph 비활성화 (메모리 절감)
```

---

## 8. 도커라이징 과정에서 해결한 문제들

### 8.1 Gemma 4 모델 아키텍처 미인식

**에러:** `Transformers does not recognize this architecture: gemma4`

**원인:** Gemma 4는 2025년 3~4월 공개 최신 모델로 vLLM 공식 이미지(v0.19.0)의 transformers에 미포함.

**해결:** 커스텀 vLLM Docker 이미지. transformers 소스 최신 설치:

```docker
FROM vllm/vllm-openai:latest
RUN pip install git+https://github.com/huggingface/transformers.git \
      tokenizers>=0.21 huggingface_hub>=0.30
```

### 8.2 transformers-vLLM 버전 충돌

**에러:** `Qwen2Tokenizer has no attribute all_special_tokens_extended`

**해결:** transformers + tokenizers + huggingface_hub만 업그레이드, vLLM 바이너리 유지.

### 8.3 pip 의존성 문제

| 패키지                      | 에러                              | 해결                      |
| --------------------------- | --------------------------------- | ------------------------- |
| hanja (kss 의존)            | `No module named 'pkg_resources'` | `--no-build-isolation`    |
| peft (FlagEmbedding 의존)   | `No module named 'peft'`          | requirements 추가         |
| marshmallow (pymilvus 의존) | `no attribute '__version_info__'` | 버전 고정                 |
| kss                         | `idioms.txt not found`            | kss 제거, 정규식 fallback |
| einops (Jina 의존)          | `No module named 'einops'`        | requirements 추가         |

---

## 9. 운영 스크립트

### 9.1 PDF 일괄 업로드 (PowerShell)

```powershell
$outputDir = "C:\Users\LANDSOFT\Downloads\output"
$apiUrl = "http://211.219.26.15:18002/api/books/ingest/upload"

$pdfs = Get-ChildItem -Path $outputDir -Recurse -Filter "*.pdf"
Write-Host "총 $($pdfs.Count)개 PDF 발견"

foreach ($pdf in $pdfs) {
    Write-Host "업로드 중: $($pdf.Name)"
    curl.exe -X POST $apiUrl -F "file=@$($pdf.FullName)" --silent --show-error
    Write-Host " → 완료"
}
```

### 9.2 재처리 (Milvus 컬렉션 초기화 후 전체 재수집)

```bash
# Milvus 컬렉션 드롭
docker exec nl-lib-fastapi python -c "
from pymilvus import connections, utility
connections.connect(host='milvus', port='19530')
utility.drop_collection('nl_lib_embeddings')
print('dropped')
"

# is_embedded 플래그 초기화
docker exec nl-lib-postgres psql -U admin -d nl_lib -c \
  "UPDATE library_catalog SET is_embedded = false;"

# 전체 재처리 디스패치
docker exec nl-lib-fastapi python -c "
from workers.tasks import process_from_minio
from db.postgres import SyncSessionLocal
from models.book import Book

db = SyncSessionLocal()
not_embedded = db.query(Book.cnts_id).filter(Book.is_embedded == False).all()
db.close()

print(f'재처리 대상: {len(not_embedded)}건')
for (cnts_id,) in not_embedded:
    minio_key = f'originals/{cnts_id}/{cnts_id}.pdf'
    task = process_from_minio.delay(cnts_id, minio_key)
    print(f'  {cnts_id} → {task.id}')
print('디스패치 완료')
"
```

---

## 10. 참고 자료

- Gemma 4 E4B: https://huggingface.co/google/gemma-4-E4B-it
- BGE-M3: https://huggingface.co/BAAI/bge-m3
- Jina Reranker v2: https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual
- vLLM: https://github.com/vllm-project/vllm
- Milvus: https://milvus.io
- 국립중앙도서관: https://www.nl.go.kr
