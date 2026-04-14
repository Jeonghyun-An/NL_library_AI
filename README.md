# 국립중앙도서관 의미 기반 도서 검색 시스템

![image.png](attachment:ffe8aef4-f85a-4e4c-8707-8e7609c3e02f:image.png)

# 연구노트: NL-Lib 국립중앙도서관 의미 기반 도서 검색 시스템

**작성일:** 2025-04-13
**작성자:** 안정현
**프로젝트명:** NL-Lib (National Library - Semantic Search)

---

## 1. 프로젝트 개요

### 1.1 목적

국립중앙도서관의 기존 키워드 검색을 **의미 기반 RAG(Retrieval-Augmented Generation) 검색**으로 전환하는 프로덕션 레벨 시스템 개발.

사용자가 "한강의 채식주의자와 비슷한 책 찾아줘"와 같이 자연어로 검색했을 때, 도서의 실제 원문 내용을 이해하고 유사한 도서를 추천하며, 근거가 되는 원문 구절을 함께 제시하는 것이 목표이다.

### 1.2 주요 기능

- **의미 기반 검색:** 단순 키워드 매칭이 아닌, 도서 원문을 이해하여 유사한 책과 관련 구절을 반환
- **RAG 시스템:** 검색된 도서 구절을 기반으로 LLM이 상세
  답변 생성 (예: "한강의 채식주의자와 비슷한 책은 OOO입니다. 근거 구절: ...")
- **원문 기반 인덱싱:** 도서 메타데이터뿐만 아니라 실제 원문을 시맨틱 청킹하여 벡터화 → Milvus에 저장
- **멀티모달 OCR:** 디지털 PDF는 PyMuPDF로, 스캔본은 PaddleOCR로 텍스트 추출. OCR 실패 시 Gemma 4의 VLM으로 fallback
- **대규모 컨텍스트 활용:** Gemma 4 E4B의 126K 컨텍스트를 활용하여 청크를 인덱스 포인터로 사용하고, 실제 LLM에는 해당 청크가 속한 원문 섹션 전체를 전달하는 혁신적 설계

### 1.3 방향성 전환

초기에는 엑셀 메타데이터(MARC/MODS) 기반 요약 → 임베딩 방식이었으나, **원본 파일 직접 OCR → 시맨틱 청킹 → 임베딩**으로 전환하여 실제 도서 원문 기반의 RAG 시스템으로 변경하였다.

---

## 2. 기술 스택

### 2.1 확정 스택

| 구분          | 기술                                      | 역할                                           |
| ------------- | ----------------------------------------- | ---------------------------------------------- |
| **LLM**       | Gemma 4 E4B (vLLM 서빙)                   | 요약, 쿼리 재작성, 답변 생성, VLM OCR fallback |
| **Embedding** | BAAI/bge-m3 (FlagEmbedding)               | 텍스트 벡터화 (1024차원)                       |
| **Reranker**  | jinaai/jina-reranker-v2-base-multilingual | Cross-Encoder 리랭킹 (8K 컨텍스트)             |
| **Vector DB** | Milvus 2.4.6                              | 벡터 저장 및 유사도 검색                       |
| **RDB**       | PostgreSQL 16                             | 도서 메타데이터 + 원문 섹션 저장               |
| **Queue**     | Redis 7 + Celery                          | 비동기 수집 작업 처리                          |
| **Storage**   | MinIO                                     | 원본 파일 저장                                 |
| **OCR**       | PaddleOCR + fitz(PyMuPDF) + VLM fallback  | 3단계 텍스트 추출                              |
| **Backend**   | FastAPI                                   | REST API                                       |
| **Frontend**  | Nuxt 3                                    | 검색 UI (미착수)                               |
| **Gateway**   | Nginx                                     | 라우팅                                         |
| **Infra**     | Docker + Portainer                        | 컨테이너 관리                                  |
| **Server**    | NVIDIA H200 140GB                         | GPU 서버                                       |

### 2.2 리랭커 선정 근거

| 항목           | bge-reranker-v2-m3 | Jina Reranker v2 (선택) |
| -------------- | ------------------ | ----------------------- |
| 파라미터       | ~568M              | ~278M                   |
| 컨텍스트       | 512 토큰           | 8192 토큰               |
| 한국어         | 양호               | 양호 (다국어 최적화)    |
| 속도 (20 청크) | ~0.5초             | ~0.3초                  |
| VRAM           | ~1.5GB             | ~0.8GB                  |

도서 원문 기반 RAG에서 청크가 긴 경우가 많아 **8K 컨텍스트 지원**이 결정적 요인이었다. bge-reranker는 512 토큰에서 잘려 긴 문단의 정보를 잃는다.

### 2.3 LLM 선정 근거 (Gemma 4 E4B)

- **126K 컨텍스트 윈도우**: 청크를 인덱스로 활용하고 원문 섹션 전체를 LLM에 전달하는 설계에 적합
- **멀티모달(비전+텍스트)**: PaddleOCR 실패 시 VLM OCR fallback으로 활용 가능
- **4B 파라미터**: H200에서 다른 서비스와 GPU 공유 가능 (~22GB VRAM)
- 추후 EXAONE 등 한국어 특화 모델로 교체 가능 (vLLM OpenAI 호환 API 구조)

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
                    └── 수집 파이프라인 (Celery 비동기)
```

### 3.2 데이터 수집 파이프라인

```
원본 파일 업로드 (MinIO 저장)
  ↓
Celery Task: process_book_file
  ├── ① 텍스트 추출
  │     fitz(PyMuPDF) → PaddleOCR → VLM(Gemma 4) fallback
  │     글자수/페이지 > 50자 → 디지털 PDF → fitz 사용
  │     50자 미만 → 스캔본 → PaddleOCR
  │     PaddleOCR 신뢰도 < 0.7 → VLM 재처리
  │
  ├── ② 섹션 분할 (~3000 토큰 단위)
  │     → PostgreSQL book_sections 테이블에 원문 저장
  │
  ├── ③ 시맨틱 청킹
  │     문장 분리 (정규식, kss fallback)
  │     → 임베딩 유사도 기반 의미 경계 감지
  │     → min 128 ~ max 1024 토큰 제약
  │     → 각 청크에 section_idx 매핑
  │
  ├── ④ 청크별 임베딩 (BGE-M3) → Milvus 저장
  │
  └── ⑤ 도서 요약 생성 (Gemma 4) → PostgreSQL 업데이트
```

### 3.3 RAG 검색 파이프라인

```
사용자 입력: "한강의 채식주의자와 비슷한 책"
  ↓
① Query Rewriter (Gemma 4)
   → "한강, 채식주의자, 현대 문학, 식물, 인간성, 윤리적 딜레마"
  ↓
② Embedder (BGE-M3)
   → 쿼리 벡터화
  ↓
③ Retriever (Milvus COSINE 유사도)
   → 후보 청크 추출 (top_k × 4)
  ↓
④ Reranker (Jina Reranker v2)
   → Cross-Encoder로 관련성 재점수 → 상위 top_k개
  ↓
⑤ Context Expander
   → 히트된 청크의 section_idx로 PostgreSQL에서 원문 로드
   → 앞뒤 ±2 섹션 확장 (126K 토큰 예산 내)
  ↓
⑥ Answer Generator (Gemma 4, 126K 컨텍스트)
   → 확장된 원문 기반 상세 답변 생성
   → 출처(도서, 페이지) 표기
```

### 3.4 검색 모드

| 모드      | 설명                                       | 반환             |
| --------- | ------------------------------------------ | ---------------- |
| **chunk** | 관련 문단을 직접 보여주고 LLM이 답변 생성  | 청크 + LLM 답변  |
| **book**  | 관련 도서를 추천하고 근거 청크 묶어서 제공 | 도서별 청크 그룹 |

### 3.5 컨텍스트 확장 설계 (핵심)

기존 RAG는 청크 텍스트(~1024 토큰)만 LLM에 전달하여 문맥이 부족했다. Gemma 4의 126K 컨텍스트를 활용하여 **청크를 인덱스 포인터로만 사용**하고, 실제 LLM에는 해당 청크가 속한 원문 섹션 + 주변 섹션을 전달한다.

```
Milvus (검색용)                    PostgreSQL (원문 저장)
┌─────────────┐                   ┌──────────────────┐
│ chunk       │──section_idx────→│ book_sections     │
│ (인덱스)    │                   │ (원문 전체)       │
└─────────────┘                   └──────────────────┘
      ↓                                   ↓
  벡터 검색으로                    히트된 섹션 ± 2 확장
  관련 청크 히트                   (~100K 토큰 예산)
      ↓                                   ↓
      └──────────→ LLM (126K) ←────────────┘
```

---

## 4. 데이터 설계

### 4.1 PostgreSQL 테이블

**library_catalog** — 도서 메타데이터 (MARC 기준, MODS 보완)

주요 필드: cnts_id(PK), title, personal_author, publisher, pub_date, kdc, subject, keyword, summary, is_embedded, chunk_count, full_text_length

**book_sections** — 도서 원문 섹션

주요 필드: book_id(=cnts_id), section_idx, full_text, page_start, page_end, token_count

### 4.2 Milvus 컬렉션 (nl_lib_embeddings)

| 필드        | 타입               | 설명                               |
| ----------- | ------------------ | ---------------------------------- |
| chunk_id    | VARCHAR (PK)       | "{book_id}\_\_{chunk_idx:04d}"     |
| book_id     | VARCHAR            | = cnts_id                          |
| chunk_idx   | INT16              | 청크 순번                          |
| section_idx | INT16              | 소속 섹션 (원문 로드용 포인터)     |
| text        | VARCHAR            | 청크 텍스트 (검색 결과 미리보기용) |
| page_start  | INT16              | 시작 페이지                        |
| page_end    | INT16              | 종료 페이지                        |
| embedding   | FLOAT_VECTOR(1024) | BGE-M3 임베딩                      |

### 4.3 데이터 매핑 관계

```
엑셀 (MARC/MODS)  →  library_catalog (cnts_id)
                              ↑
원본 PDF  →  book_sections (book_id = cnts_id)
                    ↑
              Milvus chunks (book_id, section_idx)
```

---

## 5. 프로젝트 구조

```
nl-lib/
├── docker-compose.yml
├── .env
├── infra/
│   └── vllm/
│       └── Dockerfile              # 커스텀 vLLM (Gemma 4 지원)
│
├── app/                             # FastAPI 백엔드
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── core/
│   │   ├── config.py               # pydantic-settings 설정 중앙화
│   │   └── deps.py                 # get_db AsyncSession DI
│   ├── api/
│   │   ├── book.py                 # 통합 라우터 (검색 + 수집 + CRUD)
│   │   └── health.py               # 헬스체크
│   ├── services/
│   │   ├── ingestion/
│   │   │   ├── extractor.py        # 3단 fallback OCR
│   │   │   ├── chunker.py          # 시맨틱 청킹
│   │   │   ├── embedder.py         # BGE-M3 임베딩 (FlagEmbedding)
│   │   │   ├── indexer.py          # Milvus 저장/검색
│   │   │   ├── summarizer.py       # LLM 요약
│   │   │   ├── marc_parser.py      # MARC21 파싱 (pymarc)
│   │   │   ├── mods_parser.py      # MODS XML 파싱
│   │   │   └── xlsx_loader.py      # 엑셀 로드
│   │   └── search/
│   │       ├── query_rewriter.py   # 쿼리 의미 확장
│   │       ├── reranker.py         # Jina Reranker v2
│   │       ├── context_expander.py # 원문 컨텍스트 확장 (126K 활용)
│   │       └── pipeline.py         # 검색 파이프라인 조립
│   ├── models/
│   │   ├── book.py                 # SQLAlchemy ORM (library_catalog)
│   │   └── section.py              # SQLAlchemy ORM (book_sections)
│   ├── schemas/
│   │   └── book.py                 # Pydantic 스키마
│   ├── repositories/
│   │   ├── book.py                 # 도서 메타데이터 CRUD
│   │   └── section.py              # 섹션 원문 조회
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks.py                # 수집 비동기 작업
│   └── db/
│       └── postgres.py             # async + sync 엔진
│
└── frontend/                        # Nuxt 3 (미착수)
```

---

## 6. API 엔드포인트

| Method | Path                        | 설명                              |
| ------ | --------------------------- | --------------------------------- |
| GET    | /health                     | 헬스체크                          |
| POST   | /api/books/search           | 의미 기반 검색 (chunk/book 모드)  |
| POST   | /api/books/catalog/load     | 엑셀 → 메타데이터 적재            |
| POST   | /api/books/ingest/upload    | 파일 업로드 → OCR → 청킹 → 임베딩 |
| POST   | /api/books/ingest/batch     | 배치 수집                         |
| POST   | /api/books/ingest           | 메타데이터 기반 수집 (기존 호환)  |
| GET    | /api/books/ingest/{task_id} | Celery 태스크 상태 조회           |
| GET    | /api/books/{cnts_id}        | 도서 단건 조회                    |

---

## 7. 인프라 구성

### 7.1 Docker Compose 서비스

| 서비스    | 이미지                               | 호스트 포트  | 비고                |
| --------- | ------------------------------------ | ------------ | ------------------- |
| etcd      | quay.io/coreos/etcd:v3.5.0           | -            | Milvus 메타데이터   |
| minio     | minio/minio:latest                   | 21000, 21001 | 원본 파일 저장      |
| milvus    | milvusdb/milvus:v2.4.6               | -            | 벡터 DB             |
| postgres  | postgres:16-alpine                   | 15432        | RDB                 |
| redis     | redis:7-alpine                       | 16379        | 캐시/큐             |
| vllm      | landsoftdocker/nl-lib-vllm:latest    | 18081        | 커스텀 이미지       |
| paddleocr | landsoftdocker/clms-paddleocr:latest | 18003        | GPU OCR             |
| fastapi   | landsoftdocker/nl-lib-fastapi:latest | 18002        | API 서버            |
| celery    | landsoftdocker/nl-lib-fastapi:latest | -            | 비동기 워커         |
| nuxt      | landsoftdocker/nl-lib-nuxt:latest    | -            | 프론트엔드 (미배포) |
| gateway   | nginx:alpine                         | 92           | 라우팅              |

### 7.2 포트 매핑

contract 프로젝트(미사용) 포트를 재사용. library-ragnet 스택과 충돌 없음 (vLLM만 18080→18081로 변경).

### 7.3 GPU 메모리 현황 (H200 140GB)

| 프로세스                          | VRAM              | 역할                 |
| --------------------------------- | ----------------- | -------------------- |
| library-ragnet vLLM (Gemma 3 12B) | ~31GB             | 헌법재판소(기준)     |
| library-ragnet FastAPI (임베딩)   | ~3.4GB            | 헌법재판소           |
| nl-lib vLLM (Gemma 4 E4B)         | ~22GB             | gemma4 성능 테스트용 |
| nl-lib FastAPI (임베딩 + 리랭커)  | ~2.4GB            | 국립중앙도서관       |
| **합계**                          | **~59GB / 143GB** |                      |

---

## 8. 도커라이징 과정에서 해결한 문제들

### 8.1 Gemma 4 모델 아키텍처 미인식

**에러:** `Transformers does not recognize this architecture: gemma4`

**원인:** Gemma 4는 2025년 3~4월 공개 최신 모델로 vLLM 공식 이미지(v0.19.0)의 transformers에 미포함.

**해결:** **커스텀** vLLM Docker 이미지 빌드. 베이스 이미지 위에 transformers 소스 최신 설치.

```docker
FROM vllm/vllm-openai:latest
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    pip install git+https://github.com/huggingface/transformers.git \
      tokenizers>=0.21 huggingface_hub>=0.30
```

### 8.2 transformers-vLLM 버전 충돌

**에러:** `Qwen2Tokenizer has no attribute all_special_tokens_extended`

**원인:** transformers만 소스 최신으로 올리면 vLLM 내부 토크나이저 코드와 호환 깨짐.

**해결:** vLLM 소스 빌드 시도 → CUDA 컴파일 실패 → nightly wheel 시도 → C 라이브러리 심볼 충돌. 최종적으로 **transformers + tokenizers + huggingface_hub만 업그레이드하고 vLLM은 건드리지 않는 방식**으로 해결.

### 8.3 vLLM 소스 빌드 실패

**에러:** `cmake returned non-zero exit status 1`

**원인:** Docker 컨테이너 내부에 CUDA 컴파일 환경(cmake, ninja 등) 부족.

**해결:** 소스 빌드 대신 `pip install vllm --pre --extra-index-url https://wheels.vllm.ai/nightly`로 nightly wheel 사용 시도했으나 C 라이브러리 호환 문제 발생. 또한 nightly wheel의 컴파일된 바이너리가 베이스 이미지의 PyTorch/CUDA 버전과 불일치. 최종적으로 nightly wheel 방식 폐기, transformers만 업그레이드하는 최소 침습 방식으로 최종 확정.

### 8.4 GPU 메모리 부족

**에러:** `No available memory for the cache blocks`

**원인:** `gpu_memory_utilization: 0.1`이 4B 멀티모달 모델(비전 인코더 포함)에 부족. 다른 스택의 vLLM이 GPU를 점유 중.

**해결:** `gpu_memory_utilization: 0.15` + `--enforce-eager`(CUDA graph 비활성화)로 메모리 사용량 감소.

### 8.5 pip 의존성 문제들

| 패키지                      | 에러                                      | 해결                                 |
| --------------------------- | ----------------------------------------- | ------------------------------------ |
| hanja (kss 의존)            | `No module named 'pkg_resources'`         | `--no-build-isolation` 옵션으로 설치 |
| peft (FlagEmbedding 의존)   | `No module named 'peft'`                  | requirements에 추가                  |
| marshmallow (pymilvus 의존) | `no attribute '__version_info__'`         | environs, marshmallow 버전 고정      |
| kss                         | `idioms.txt not found` (assets 누락 버그) | kss 제거, 정규식 fallback 적용       |
| einops (Jina Reranker 의존) | `No module named 'einops'`                | requirements에 추가                  |

### 8.6 WSL 크래시

**증상:** vLLM 소스 빌드 중 WSL이 OOM으로 반복 종료.

**해결:** 서버(H200)에서 직접 Docker 빌드로 전환. 로컬에서는 `.wslconfig`으로 메모리 제한 상향 권장.

### 8.7 Docker 빌드 캐시 손상

**에러:** `parent snapshot does not exist: not found`

**원인:** WSL 크래시로 BuildKit 캐시 손상.

**해결:** `docker builder prune -af`로 캐시 정리 후 재빌드.

---

## 9. 코드 컨벤션 및 원칙

- **임포트:** `app.` 접두사 없이 상대 경로 사용 (모든 모듈이 `/app` 하위)
- **스키마 필드명:** `schemas/book.py` 기준으로 전체 파일 통일
- **기존 필드 보존:** 스키마 필드명을 함부로 변경하지 않음
- **모듈화:** api(라우터) → services(비즈니스 로직) → repositories(DB 접근) 레이어 분리
- **Docker:** 로컬에서 `build:` + `image:`, Portainer에서 `image:`만 사용하는 단일 compose 파일 운용
- **볼륨 마운트:** 불필요한 디렉토리 마운트 추가하지 않음

---

## 10. 현재 상태

### 10.1 정상 동작 확인

- [x] vLLM Gemma 4 E4B 서빙 정상 (커스텀 이미지)
- [x] FastAPI 기동 (임베딩 + 리랭커 + Milvus 컬렉션 로드)
- [x] 쿼리 재작성 동작 확인 ("한강의 채식주의자와 비슷한 책" → 의미 확장)
- [x] 헬스체크 `/health` 정상
- [x] 인프라 전체 정상 (PostgreSQL, Redis, Milvus, MinIO, PaddleOCR)
- [x] Milvus 컬렉션 스키마 재생성 (section_idx 포함)

### 10.2 미완료

- [ ] 빈 결과 처리 코드 배포
- [ ] 테스트 데이터 수집 (엑셀 메타데이터 + 원본 파일 업로드)
- [ ] E2E 검색 테스트
- [ ] 프론트엔드 (Nuxt 3) 개발
- [ ] Nginx 설정 파일 작성

---

## 11. 다음 단계 로드맵

| 단계 | 내용                                                          | 우선순위       |
| ---- | ------------------------------------------------------------- | -------------- |
| 1    | 빌드 & 배포 마무리 (health.py + 컬렉션 재생성 + 빈 결과 처리) | 즉시           |
| 2    | 테스트 데이터 수집 → E2E 검색 테스트                          | 즉시           |
| 3    | 프론트엔드 (Nuxt 3) 착수                                      | 다음           |
| 4    | Graph RAG 도입 (Neo4j 도서 관계망)                            | 품질 검증 후   |
| 5    | HNSW 인덱스 + Redis 캐싱 + 스케일 아웃                        | 데이터 증가 시 |

---

## 12. 참고 자료

- Gemma 4 E4B: https://huggingface.co/google/gemma-4-E4B-it
- vLLM에서 Gemma 4 실행: https://growup-lee.tistory.com/entry/gemma4-vllm-실행-방법
- BGE-M3: https://huggingface.co/BAAI/bge-m3
- Jina Reranker v2: https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual
- vLLM: https://github.com/vllm-project/vllm
- 국립중앙도서관: https://www.nl.go.kr
- 벤치마크 LikeSNU: https://likesnu.snu.ac.kr/usr/userMain.do

# 부록: PDF 파일 일괄 업로드 스크립트 (PowerShell)

$outputDir = "C:\Users\LANDSOFT\Downloads\output"
$apiUrl = "http://211.219.26.15:18002/api/books/ingest/upload"

$pdfs = Get-ChildItem -Path $outputDir -Recurse -Filter "\*.pdf"

Write-Host "총 $($pdfs.Count)개 PDF 발견"

foreach ($pdf in $pdfs) {
    Write-Host "업로드 중: $($pdf.Name)"

    curl.exe -X POST $apiUrl `
        -F "file=@$($pdf.FullName)" `
        --silent --show-error

    Write-Host " → 완료"

}

Write-Host "전체 업로드 완료: $($pdfs.Count)건"

# 부록: 재처리 스크립트 (PowerShell)

## Milvus 컬렉션 드롭 (스키마 변경했으니 필수)

docker exec nl-lib-fastapi python -c "
from pymilvus import connections, utility
connections.connect(host='milvus', port='19530')
utility.drop_collection('nl_lib_embeddings')
print('dropped')
"

## is_embedded 플래그 초기화 (전체 재처리 위해)

docker exec nl-lib-postgres psql -U admin -d nl_lib -c "UPDATE library_catalog SET is_embedded = false;"

## 재처리 스크립트 (PowerShell)

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
print(f' {cnts_id} → {task.id}')
print('전부 디스패치 완료')
"
