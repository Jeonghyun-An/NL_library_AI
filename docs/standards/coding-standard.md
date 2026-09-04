# 코딩 표준

지금 `app/`가 실제로 따르고 있는 관행을 성문화한 것 — 새 규칙이 아니라 기존 패턴의 문서화다.

## 계층과 의존 방향

```
api/  → services/ → domains/ → repositories/ → models/
              ↘ schemas/ (경계 입출력 타입)
```

- `api/`: FastAPI 라우터. 얇게 유지 — 검증·조합은 `services/`에 위임(`app/api/health.py` 참고).
- `services/`: 유스케이스 로직(`chat/`·`ingestion/`·`search/`). 외부 I/O(LLM·OCR)는 `llm_client.py`류로 격리.
- `domains/`: 도메인 규칙(`nl_library/`).
- `repositories/`: DB 접근만 담당. **ORM 모델을 밖으로 내보내지 않고 항상 스키마로 변환해 반환**한다(`repositories/book.py`의 `BookRepository`가 `Book`이 아닌 `BookOut`을 반환하는 패턴).
- `schemas/`: Pydantic v2 모델. `model_dump()`/`model_validate()`로 ORM ↔ 스키마 변환.
- `models/`: SQLAlchemy ORM 모델.

## 타입힌트

- 모든 함수 시그니처에 인자·반환 타입을 명시한다. `list[str]`·`dict[str, BookOut]`·`X | None` 같은 최신 문법을 쓴다(`repositories/book.py` 전체가 이 패턴).
- 비동기 I/O는 `async def` + `AsyncSession`을 일관되게 쓴다.

## 주석·docstring

- 기본은 주석 없음. 왜(why)가 non-obvious할 때만 한 줄 docstring을 단다(`get_by_cnts_ids`의 `"""cnts_id 목록 조회 → {cnts_id: BookOut}"""`처럼 반환 형태가 함수명만으로 안 드러날 때).
- 무엇을 하는지 설명하는 주석, 현재 작업/이슈 번호를 참조하는 주석은 쓰지 않는다.

## 에러 처리

- 시스템 경계(API 입력, 외부 서비스 응답)에서만 검증한다. 내부 계층 간 호출은 서로를 신뢰한다.
- 발생할 수 없는 상황에 대한 방어 코드를 넣지 않는다.

## 테스트

- `app/tests/`에 pytest. 새 기능은 실패하는 테스트 → 최소 구현 → 통과 순서(TDD)로 진행한다.
- 리포지토리·서비스 계층은 실제 비동기 세션으로 테스트하고, 외부 LLM/OCR 호출만 목(mock)한다 — 목 범위를 넓히지 않는다.

## 네이밍

- 파일·함수: `snake_case`. 클래스: `PascalCase`(`BookRepository`).
- 1회성 실험 스크립트와 운영 스크립트를 구분해 위치시킨다(`CLAUDE.md` §1 — `scripts/` vs `research/`).
