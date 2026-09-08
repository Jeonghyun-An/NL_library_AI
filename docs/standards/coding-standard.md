# 코딩 표준

두 가지를 구분한다 — **이미 일관되게 지켜지는 패턴**(새 코드는 그대로 따른다)과 **지향점**(아직 안 지키는 기존 코드가 있음 — 새 코드부터 적용, 기존 코드는 별도 리팩터 백로그).

## 계층과 의존 방향 (실측 import 그래프 기준)

```
api/ ─┬─→ services/ → repositories/ → models/
      └─────────────→ repositories/, models/ (일부 라우터는 services/를 우회)
domains/ ←── repositories/, services/ (예: catalog_bulk.py·services/ingestion/stages.py가 domains.base를 씀 — domains/는 어디도 의존하지 않는 leaf)
schemas/: api/·services/·repositories/ 여러 곳에서 경계 타입으로 공용
core/·db/·workers/: 여러 계층에서 횡단 참조(예: core.config)
```

- **지향점**: `api/`는 얇게, 검증·조합은 `services/`에 위임한다. 실측: `api/admin.py`(668줄)·`api/book.py`(688줄)는 라우터 안에서 SQLAlchemy를 직접 쓰고 트랜잭션을 관리한다(예: `admin.py`가 핸들러에서 `TRUNCATE ... CASCADE`를 직접 실행) — 아직 지켜지지 않는 기존 코드. `health.py`(7줄, 로직 없음)는 위임 패턴을 보여줄 수 없는 예이니 "얇은 라우터"의 근거로 인용하지 않는다. 새 엔드포인트는 이 목표를 따른다.
- `services/`: 유스케이스 로직(`chat/`·`ingestion/`·`search/`).
- `repositories/`: DB 접근. **지향점 — ORM 모델을 밖으로 안 내보내고 스키마로 변환해 반환**한다. 실측 준수 예: `BookRepository`(`repositories/book.py`)는 어느 메서드도 ORM(`Book`)을 반환하지 않는다(`BookOut`류 또는 `None`) — 새 리포지토리는 이 패턴을 그대로 따른다. 실측 위반 예(백로그): `SectionRepository`(`repositories/section.py`)는 대응 스키마가 없어 `BookSection` ORM을 그대로 반환하고, `catalog_bulk.py`는 bare `dict`를 반환한다.
- `schemas/`: Pydantic v2 모델. `model_dump()`/`model_validate()`로 ORM ↔ 스키마 변환.
- `models/`: SQLAlchemy ORM 모델.

## LLM/OCR 호출 — 지향점: `llm_client.py`로 격리

`app/services/llm_client.py`가 있지만 실측으로는 `services/chat/`·`services/ingestion/`·`services/search/`·`workers/job_runtime.py`의 여러 모듈(예: `search/curator.py`)이 `httpx`로 LLM을 직접 호출한다. 새 코드는 `llm_client.py`를 거친다 — 기존 직접 호출은 별도 리팩터 백로그.

## 타입힌트

- **준수 예 — 이 패턴을 새 코드의 기준으로 삼는다**: `repositories/book.py`의 각 조회·변경 메서드가 인자·반환 타입을 명시하고 `list[str]`·`dict[str, BookOut]`·`X | None` 같은 최신 문법을 쓴다(생성자처럼 반환값이 자명한 경우의 `-> None` 생략은 관례로 허용).
- 비동기 I/O는 `async def` + `AsyncSession`을 쓴다. 예외(백로그): `catalog_bulk.py`는 인자 미표기·`-> dict` 반환·완전 동기(`db.execute`/`db.commit`)로 이 계층의 기준을 따르지 않는다.

## 주석·docstring

- 기본은 주석 없음. 왜(why)가 non-obvious할 때만 한 줄 docstring을 단다(`get_by_cnts_ids`의 `"""cnts_id 목록 조회 → {cnts_id: BookOut}"""`처럼 반환 형태가 함수명만으로 안 드러날 때).
- 무엇을 하는지 설명하는 주석, 현재 작업/이슈 번호를 참조하는 주석은 쓰지 않는다. (예외: `catalog_bulk.py`에 모듈 docstring과 무엇을-설명하는 주석이 남아있다 — 새 코드에는 적용하지 않는다.)

## 에러 처리 — 지향점

- 시스템 경계(API 입력, 외부 서비스 응답)에서만 검증한다. 내부 계층 간 호출은 서로를 신뢰한다.
- 발생할 수 없는 상황에 대한 방어 코드를 넣지 않는다.
- 실측 반례(백로그): `services/search/pipeline.py`·`paper_summary.py`는 넓은 `except Exception`으로 여러 실패를 뭉뚱그려 삼키고, `catalog_bulk.py`는 `NOT NULL` 제약을 코드에서 기본값으로 조용히 메운다(`row.setdefault("title", ...)`). 새 코드는 이렇게 하지 않는다 — 구체적 예외를 잡고, 제약 위반은 검증 단계에서 드러낸다.

## 테스트

- `app/tests/`에 pytest 사용 중. 다만 실측으로는 리포지토리·서비스 계층에 대한 **비동기 세션 테스트가 아직 없다** — 현재 테스트는 동기·mock 기반이다(`test_curate_books.py`·`test_scenario.py`가 `httpx.AsyncClient`를 patch하는 방식).
- **지향점**: 새 리포지토리/서비스 테스트는 실제 비동기 세션으로 작성하고, 외부 LLM/OCR 호출만 mock한다 — mock 범위를 넓히지 않는다.
- 새 기능은 실패하는 테스트 → 최소 구현 → 통과 순서(TDD)로 진행한다.

## 네이밍

- 파일·함수: `snake_case`. 클래스: `PascalCase`(`BookRepository`).
- 1회성 실험 스크립트와 운영 스크립트를 구분해 위치시킨다(`CLAUDE.md` §1 — `scripts/` vs `research/`).
