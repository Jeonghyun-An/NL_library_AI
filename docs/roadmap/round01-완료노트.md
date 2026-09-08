# round01 완료노트

날짜: 2026-09-08
브랜치: `feat/round01-dev-system-bootstrap-wt`
spec: `docs/superpowers/specs/2026-09-04-round01-dev-system-bootstrap-design.md`
plan: `docs/superpowers/plans/2026-09-04-round01-dev-system-bootstrap.md`
교본: `docs/guides/round01/00-체계도입.md`

## 한 일
- `CLAUDE.md`·`GIT_WORKFLOW.md` 등 운영 진입점 문서 신설
- `docs/roadmap/`·`docs/guides/`·`docs/standards/`·`docs/ops/`·`docs/design/` 신설
- `.claude/skills/round-finish/`·`.claude/agents/code-reviewer.md`(model: opus 고정) 신설
- `research/` 7개 주제 폴더 신설, `scripts/`·루트에 흩어져 있던 실험 산출물을 주제별로 이동(최종 1,403개 파일 — `vlm-routing-policy/vlm_raw100/`의 VLM 원시 출력 1,284개 포함, `git ls-files research/<dir>` 실측, 교본 §2.9 표 참고). 이동 중 code-quality 리뷰로 오분류 5건을 발견해 재배치(파일명이 아니라 내용을 읽어야 정확한 주제 판단이 가능했음).
- 운영 도구 4개(`build_dev_images.sh`·`build_gongu_manifest.py`·`build_wikisource_manifest.py`·`crawler.py`)는 `scripts/`에 잔류(+ `scripts/bulk_ingest/`). `build_vlm_policy_selection.py`는 Task 12에서 연구용으로 확정돼 `research/vlm-routing-policy/`로 이동 — `scripts/`에는 남지 않았다.
- 추적된 디버그 로그 1개(`scripts/debug_raw.txt`) `git rm` + `.gitignore` 재발 방지 패턴 추가(`*_debug_out*.txt`·`soffice_log*.txt`·`debug_*.txt`). 미추적 디버그 로그 3개(`scripts_debug_out.txt`·`scripts_debug_out2.txt`·`soffice_log2.txt`)는 워크트리 격리로 공유 체크아웃에 남아있어 Task 15에서 정리 예정.
- README §5(프로젝트 구조)·§8.4(수동 컬럼 마이그레이션 명령)를 `docs/`·`scripts/`·`research/` 신설 반영해 갱신 — 실존하지 않는 `migrate_add_KCI.sql` 참조(두 곳 모두)를 실제 4개 파일(`migrate_add_book_figures.sql`·`migrate_add_cover_image.sql`·`migrate_add_introduction.sql`·`migrate_add_themes.sql`)로 정정
- (라운드 범위 밖, 착수 전 별도 조치) `.gitignore`의 `/docs`·`/scripts`·`.claude/` 오추적 제외 버그 수정, 밀린 문서 백업. `feat/search-session-history` 브랜치 삭제, `SKOVIX-JeongHyun`은 로컬 전용 커밋을 `main`에 합류(`5144cdd`) — 브랜치 자체는 로컬·원격에 남아있음(완전 병합 상태, 별도 삭제는 이번 스코프 밖)

## 결정
- 물리 디렉토리 이동 없음 — `app/`·`frontend/`·`infra/`는 이름 유지, 문서로만 정본화
- 리뷰 게이트는 (1) `code-reviewer` 서브에이전트(model: opus) 정적 리뷰 + (2) 자가 점검 체크리스트(협업자 없음)
- ADR 이번 라운드 생략(README에 이미 설계 근거 있음)
- 서브에이전트 실행은 격리 워크트리(`feat/round01-dev-system-bootstrap-wt`)에서 진행(GitHub Desktop 동시 사용 충돌 방지)
- 미출원 특허 청구항 초안 조각 6개는 `research/`가 아니라 저장소 밖(`C:\Users\LANDSOFT\patent-drafts-nllib-untracked\`)으로 완전히 이동 — 공지(공개) 시점 리스크 때문에 저장소 안 어디든 부적절 판단

## 디자인 참조
해당 없음 — 디자인 트랙 미도입(`docs/design/README.md`)

## 이월
- `docs/adr/ADR-001-*.md` — 다음 큰 결정 시점에 작성
- `app/odl_stderr.log`(8MB, 미추적) 등 `app/` 내부 대용량 로그 정리 — 이번 스코프 밖
- 루트의 `INDEX.README.md`·`inspect_odl.py`·`migrate_add_*.sql` — round01 스코프 밖(`CLAUDE.md` §1에 이월 명시)
- **[보안, 우선순위 높음] `app/api/admin.py:199,378,380` Milvus expression injection** — 인증 없는 엔드포인트에서 `cnts_id`가 검증 없이 f-string으로 `expr`에 삽입돼 임의 삭제가 가능하다. 2026-09-07 code-reviewer 에이전트 작성 중 발견·보고, 도서관 대회 시연(2026-09-07 기준 약 1개월 후) 우선으로 사용자가 명시적으로 이월 지시 + "DB 파괴 행위 절대 금지" 지시(기억에 저장됨). **대회 이후 최우선으로 별도 라운드에서 처리하며, 그 전까지는 이 이슈에 대한 어떤 수정 코드도 미리 만들지 않는다.**
- `research/`로 옮긴 스크립트 다수(Task 10·11 리뷰 기준 약 26개, 19개는 입력부터 못 찾아 실행 자체가 실패·7개는 산출물이 엉뚱한 곳에 다시 생기는 증상)가 입출력 경로를 여전히 옛 `scripts/...` 위치로 하드코딩하고 있다. `research/vlm-routing-policy/build_vlm_policy_selection.py`(Task 12에서 연구용으로 확정)도 같은 문제의 사례 — `scripts/audit_routing_policy200.json`·`scripts/fitz_lengths_policy200.json`·`scripts/run_vlm_policy.py`를 옛 경로로 참조한다. 코드 수정은 이번 라운드(파일 재배치) 스코프 밖 — 다음에 그 스크립트들을 실제로 재실행할 일이 생기면 그때 입출력 상수를 `Path(__file__).parent` 기준으로 고친다(다른 주제 폴더를 참조하는 20건은 자기 폴더 기준만으로는 부족).

## 다음 라운드 진입점
- 범위 미정 — `docs/roadmap/00_status.md`와 `README.md` §10 로드맵에서 확인

## 상태
- [x] code-reviewer 정적 리뷰 통과(발견 사항 반영 완료 — Task 1~14 전 태스크 spec-compliance + code-quality 2단계 서브에이전트 리뷰, 발견 시 즉시 수정)
- [x] 테스트 green (해당 변경 없음 — 문서/파일 이동만, 이동된 `.py` 전체 `py_compile` 검증 완료)
- [x] 수동 스모크 확인 (`docker-compose.yml`·`docker-compose.dev.yml` 양쪽 config 파싱 확인)
- [x] 문서 갱신(교본·00_status·`docs/ops/recurring-gotchas.md`에 dev 스택 함정 2건 반영)
- [ ] `dev` 머지 승인
- [ ] `dev→main` 머지 + push 완료
