# CLAUDE.md — 개발 운영 진입점

> Claude가 이 프로젝트에서 어떻게 작동하고 어떤 작업에 어디를 보는지의 단일 진입점.
> 상세는 각 문서로 링크(중복 금지). 충돌 시 이 파일이 우선.

## 0. 병렬 작업 원칙
- 독립적인 작업(백엔드 API ↔ 프론트 ↔ 리서치 분석)은 가능하면 서브에이전트로 병행한다. 순차 진행은 의존성이 있을 때만.

## 1. 산출물 위치 규칙 (불변)
- 루트에는 운영 파일(`CLAUDE.md`·`GIT_WORKFLOW.md`·`README.md`·`.gitignore`·`docker-compose*.yml` 등 설정)만 둔다. 그 외 루트에 남아있는 개별 파일(예: `INDEX.README.md`·`inspect_odl.py`·`migrate_add_*.sql`)은 round01 스코프 밖의 기존 잔재로, 정리는 다음 라운드로 이월한다.
- `app/`·`frontend/`·`infra/` = 실제 서비스 코드/배포 설정의 정본. 이름을 바꾸지 않는다.
- `docs/` = 문서 전용.
- `scripts/` = **재실행되는 운영 도구**만 둔다 — 파이프라인이 지금도 호출하거나 반복 실행하는 것(`scripts/bulk_ingest/`, 매니페스트 빌더 등).
- `research/` = **1회성 실험**(스크립트 + 그 산출물)만 둔다. "이 스크립트를 다시 실행할 일이 있는가"가 `scripts/`와의 구분 기준이다. 코드와 산출물은 분리하지 않는다(재현 가능성 유지) — 실행해서 파일을 만들어내는 1회성 스크립트는 항상 대응하는 `research/<주제>/`에 산출물과 함께 둔다.
- 디버그 로그(`*.log`, `*_debug_out*.txt` 등)는 커밋하지 않는다(`.gitignore`).

## 2. 개발 어휘 — round
- **round**: 사용자 프롬프트 1개 → 구현 → 리뷰 → dev 머지(사용자 승인) → dev→main 머지 + push까지가 한 라운드. 라운드당 spec 1(브레인스토밍) + 완료노트 1 + 교본(가이드) 1권.
- 라운드 번호는 2자리(`round01`, `round02`…). 성격이 다른 여러 덩어리로 쪼개지면 소문자 접미(`round01a`, `round01b`…)를 붙인다. 접미는 성격 라벨이며 실행 순서가 아니다.
- 브랜치명은 영문 kebab-case만 사용한다(Windows·CI 호환성 — 한글 브랜치명 금지).
- 생애주기·브랜치 모델 상세: `GIT_WORKFLOW.md`.

## 3. 세션 시작 시 확인
- 새 세션(=새 라운드)을 열면 먼저 `docs/roadmap/00_status.md`(현재 상태·다음 할 일)와 직전 라운드 완료노트(`docs/roadmap/round<NN>-완료노트.md`)를 읽어 맥락을 이어받는다.
- 문서와 코드가 어긋나면 코드가 실제이니 문서를 고친다.

## 4. 어디를 보나
| 알고 싶은 것 | 위치 |
|---|---|
| 브랜치·커밋·라운드 생애주기·개발 환경 | `GIT_WORKFLOW.md` |
| 현재 상태·다음 할 일 | `docs/roadmap/00_status.md` |
| 라운드 완료 기록 | `docs/roadmap/round<NN>-완료노트.md` |
| 라운드 교본(클론코딩 + 면접 Q&A) | `docs/guides/round<NN>/` |
| 기능 설계(브레인스토밍 spec) | `docs/specs/` · `docs/superpowers/specs/` |
| 구현 계획(writing-plans) | `docs/superpowers/plans/` |
| 코딩 표준 | `docs/standards/coding-standard.md` |
| 반복 함정(라이브에서만 드러나는 버그) | `docs/ops/recurring-gotchas.md` |
| 대량 인덱싱 배포·검증 런북 | `docs/bulk_ingest_runbook.md` |
| 디자인 정본(미도입 — 스텁) | `docs/design/README.md` |
| 시스템 아키텍처 다이어그램 | `docs/architecture.drawio` |
| 라운드 종료 절차 자동화 | `.claude/skills/round-finish/SKILL.md` |
| 정적 코드 리뷰 서브에이전트 | `.claude/agents/code-reviewer.md` |
| 기능·아키텍처 설명·다음 개선 백로그(§10 로드맵) | `README.md` |
