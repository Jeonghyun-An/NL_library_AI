# round01 — 개발 체계 도입 (museum 스타일 이식) 설계

작성일: 2026-09-04
상태: 설계 확정 (구현 미착수)

## Context

museum(`Habonit/20260601-museum-platform`) 프로젝트는 `CLAUDE.md`를 진입점으로 round 기반 워크플로우·문서 지도·산출물 위치 규칙을 갖추고 있고, 이를 본 저장소(NL-Lib)에도 도입하고 싶다는 요청에서 시작됐다. NL-Lib은 이미 실서비스 코드(`app/`·`frontend/`·`infra/`)와 `docs/superpowers/`(brainstorming spec/plan)를 부분적으로 쓰고 있었지만:

- 루트에 "어디를 보나"를 알려주는 진입점 문서가 없다(`README.md`는 기능 설명 위주).
- 브랜치가 개인명(`SKOVIX-JeongHyun`) 기준이고 작업 단위·종료 조건 개념이 없다.
- 루트 16개·`scripts/` 79개 파일이 실험 산출물과 운영 스크립트가 뒤섞인 채 누적돼 있다.
- GitHub 리모트 1개만 존재(museum과 달리 GitLab 이원화 없음).
- 협업자 없이 혼자 개발한다.
- `docker-compose.dev.yml`이 이미 prod와 데이터 계층을 분리한 단일 서버 구조를 갖고 있다(museum의 Node A/B 2노드 구조와는 다름).

이 spec은 museum의 체계를 그대로 복제하지 않고 위 차이를 반영해 이식하는 방법을 정의한다. round01은 이 이식 작업 자체다.

## 핵심 결정

| 항목 | 결정 |
|---|---|
| 디렉토리 물리 이동 | **하지 않는다.** `app/`·`frontend/`·`infra/`는 이름 유지, 문서로만 "이 구조가 정본"이라 규정 (docker-compose·Dockerfile·alembic 참조 경로 보존) |
| 리뷰 게이트 | 팀 PR 리뷰 대신 **자가 점검 체크리스트**(테스트 green + 수동 스모크 + 문서 갱신). 단, 작업 브랜치→dev, dev→main 머지는 지금처럼 **사용자 채팅 승인 필수** — 유지, 승인 방식만 변경 |
| 라운드 문서 수준 | museum과 동일한 풀세트: spec + 완료노트 + 교본(전체 코드 수록 + 면접 Q&A) |
| 원격 push | `origin`(GitHub) 단일 push. GitLab 관련 절차 전부 제외 |
| 역할·상태 문서 | museum의 `00_orchestrator.md`~`05_*.md` 6분할 대신 **솔로용 단일 문서** `docs/roadmap/00_status.md` |
| ADR | 이번 라운드는 **생략**. README에 이미 설계 근거가 있어 중복 — 다음에 새 큰 결정이 생기면 그때 `docs/adr/ADR-001-*.md` 시작 |
| 디자인 트랙 | 미도입이지만 **Figma 연동 훅만 남긴다** — `docs/design/README.md` 스텁 + 완료노트 「디자인 참조」4항목 유지(기본값 "해당 없음") |
| 산출물 위치 규칙 | 신규 최상위 `research/<주제>/` — "재실행 가능성"으로 `scripts/`(운영)와 구분. 기존 95개 파일도 **이번 라운드에서 실제 이동** |
| 기존 브랜치 | `SKOVIX-JeongHyun`(main 대비 35커밋 선행)·`feat/search-session-history`(1커밋 선행)는 라운드 체계 도입 **이전의 정상 작업**으로 간주해 `main`에 먼저 캐치업 병합. 현재 미커밋 변경은 확인 결과 실험 코드라 폐기 대상(실행 직전 목록 재확인) |
| round 번호 | 이 캐치업 이후 `main`에서 `dev`를 새로 만들고 **round01부터 시작** |

## 1. 문서 체계

| 파일 | 역할 |
|---|---|
| `CLAUDE.md` (신규) | 진입점. §0 병렬 작업 원칙(백엔드/프론트/리서치 독립 트랙은 서브에이전트 병행) · §1 산출물 위치 규칙 · §2 round 어휘 · §3 "어디를 보나" 지도 |
| `GIT_WORKFLOW.md` (신규) | 브랜치 모델 · 라운드 생애주기 · 커밋 규칙(Co-Authored-By 트레일러 미사용, museum과 동일 관행) · 개발 환경(prod 공유 GPU + dev 전용 데이터 계층, `docker-compose.dev.yml` 기준 서술) |
| `docs/roadmap/00_status.md` (신규) | 현재 상태·다음 할 일. 라운드가 끝날 때마다 갱신 |
| `docs/roadmap/_ROUND_COMPLETE_TEMPLATE.md` (신규) | 완료노트 템플릿(디자인 참조 4항목 포함) |
| `docs/roadmap/round01-완료노트.md` (라운드 말미 작성) | round01 결과 기록 |
| `docs/guides/_TEMPLATE.md` (신규) | 라운드 교본 템플릿 |
| `docs/guides/round01/00-체계도입.md` (신규) | round01 교본 — 사용자 프롬프트 paraphrase + 이 라운드에서 만든 모든 문서/스킬/에이전트 전문 수록(발췌 금지) + 면접 Q&A |
| `docs/standards/coding-standard.md` (신규) | 지금 `app/`가 이미 쓰는 계층(api/domains/repositories/services/schemas) 컨벤션을 성문화 — 새 규칙이 아니라 기존 관행의 문서화. 타입힌트·계층 간 의존 방향·에러 처리·네이밍 포함 |
| `docs/ops/recurring-gotchas.md` (신규, 빈 템플릿) | 날짜/증상/원인/해결/재발방지 컬럼. 겪을 때마다 추가 |
| `docs/design/README.md` (신규, 스텁) | 디자인 트랙 미도입 명시 + Figma 연동 시 museum의 버전 폴더 방식(`publish-v1`·`publish-v2`처럼 덮어쓰지 않고 새 폴더로 쌓기)을 따른다는 원칙만 기록 |
| `docs/specs/`, `docs/superpowers/` | 기존 유지 — **역할 분리**: `docs/specs/`·`docs/superpowers/specs/`=brainstorming 설계 산출물, `docs/superpowers/plans/`=writing-plans 산출물, `docs/guides/`=라운드 완료 후 클론코딩 교본(신규 도입) |

`CLAUDE.md`의 "어디를 보나" 표에 `docs/design/`을 "미도입 — 스텁"으로 표기한다.

## 2. Git 브랜치·라운드 워크플로우

### 0단계 — 캐치업 (라운드 체계 시작 전, 1회성)

1. 현재 브랜치(`SKOVIX-JeongHyun`)의 미커밋 변경(`build_wikisource_manifest.py` 수정, `audit_routing_fix_result.json`·`fitz_lengths_result.json` 삭제, `odl_lengths_result.json` 수정)은 실험 코드로 확인됨 — 실행 직전 `git status`로 재확인 후 폐기(discard).
2. `SKOVIX-JeongHyun`(main 대비 35커밋)을 `main`에 병합.
3. `feat/search-session-history`(main 대비 1커밋)는 내용 검토 후 병합 여부 결정.
4. 캐치업된 `main`에서 `dev` 브랜치 생성.
5. `dev`에서 `feat/round01-dev-system-bootstrap` 브랜치 분기 — 이하 모든 작업은 이 브랜치에서.

### 브랜치 모델

```
dev ─분기→ <type>/round<NN>-<설명> ─개발·커밋─→ [사용자 승인] ─merge→ dev ─[라운드 종료 승인]→ main ─push→ GitHub(origin)
```

- `main`: 평소 직접 작업 금지, 라운드 종료 시에만 병합.
- `dev`: 통합 브랜치.
- 브랜치명: 영문 kebab-case만 사용(`feat/round01-dev-system-bootstrap`) — 한글 브랜치명은 Windows·CI 호환성 문제로 사용하지 않는다(museum 선례).
- 작업 브랜치→`dev` 머지, `dev`→`main` 머지 모두 **사용자 채팅 승인 필수**(변경 없음). 승인 근거가 팀 PR 리뷰가 아니라 자가 점검 체크리스트로 바뀔 뿐이다.

### `.claude/skills/round-finish/SKILL.md` (신규)

museum 버전에서 GitLab 관련 단계·museum 전용 "디자인 대응 이력 표 갱신" 단계를 제거한 축소판:
1. 검증 재확인(테스트 green + 관련 파이프라인 수동 스모크)
2. 완료노트 「디자인 참조」 필드 확인(미도입이면 "해당 없음")
3. `dev → main` 머지
4. `git push origin main && git push origin dev`
5. 작업 복귀: `git checkout dev`

### `.claude/agents/code-reviewer.md` (신규)

museum 버전의 프로젝트 맥락을 NL-Lib로 교체:
- 하이브리드 검색(BGE-M3 Dense+Sparse)·Milvus 스칼라 필터·메타데이터 이중 전략·OCR 라우팅(VLM/Surya/Tesseract/fitz) 등 README에 서술된 아키텍처를 판단 기준으로 명시.
- `docs/standards/coding-standard.md`·`docs/ops/recurring-gotchas.md` 참조.
- museum의 "Node A/B" 관련 문구는 전부 제외(해당 없음).
- 점검 항목·보고 형식(severity/location/issue/suggestion)은 museum 그대로 유지.

## 3. 산출물 위치 규칙 — `research/`

**규칙**: "실행해서 파일을 만들어내는 1회성 스크립트는 항상 대응하는 `research/<주제>/`에 산출물과 함께 둔다. 코드와 산출물을 분리하지 않는다(재현 가능성 유지)."

**분류 기준**: 지금도 파이프라인이 호출하거나 반복 실행되는 운영 도구 → `scripts/` 잔류. 특정 질문 하나에 답하고 끝난 1회성 분석 → `research/<주제>/`로 이동.

### `scripts/`에 잔류 (운영 도구)

- `bulk_ingest/`(하위 디렉토리 전체)
- `build_gongu_manifest.py`, `build_wikisource_manifest.py`, `crawler.py`, `build_dev_images.sh`

### `research/`로 이동 — 주제별 매핑

| 대상 폴더 | 포함 파일 (scripts/ 기준, 확장자 생략 시 .py) |
|---|---|
| `research/ocr-extraction-comparison/` | compare_extraction_methods, compare_vlm, dump_odl_text, fitz_lengths_lit(.py/100.json), fitz_lengths_policy(.py/200.json), fitz_lengths_result100.json, fitz_nospace_policy(.py/.json), fitz_pages.txt, tesseract_born_psm11(.py/.json), tesseract_extract, tesseract_psm_sweep(.py/.json), tesseract_lengths_result(.json/100.json), tesseract_p7_KCI_FI002529577.txt, run_easyocr_born, easyocr_born_result.json, run_surya_paddle_born, surya_paddle_born_result.json, space_stats_full, odl_lengths_result(.json/100.json/70.json), odl_p7_KCI_FI002529577.txt, odl_table_sample.json, odl_text_dump.json, odl_vs_fitz_lengths.txt, compare_summary.json, four_way_comparison(.json/100.json), three_way_comparison.json, hf_test_bodypage(.txt/2.txt), hf_test_p0.txt, hyeol_subpage.txt, rep_check.txt, verify_ws001.txt, exp1_recomputed.txt |
| `research/vlm-routing-policy/` | analyze_vlm_policy, audit_routing_fix, audit_routing_lit, audit_routing_policy, reextract_vlm_raw_flagged, run_vlm_batch, run_vlm_batch2, run_vlm_policy, audit_result.txt, audit_routing_fix_result100.json, audit_routing_fix_result_orig5.json, audit_routing_lit100.json, audit_routing_policy200.json, vlm_lengths_result(.json/100.json), vlm_policy_merged.json, missing_vlm_files.txt, policy_sample200.txt, vlm_raw100/(디렉토리) + 루트 `vlm_sample.json`, `quality_extra.json` |
| `research/table-cell-fill/` | cell_fill_analysis, cell_stats_full, json_cell_stats, json_cell_stats2, cell_fill.json, cell_stats_policy(.json/2.json), json_cell_stats(.json/2.json) |
| `research/font-and-layout-forensics/` | font_forensics, glyph_recovery_gap, xobject_hypothesis, page_geometry_features, font_forensics.json, font_targets.json, glyph_gap.json, xobject_check.json, page_geometry_policy.json |
| `research/corpus-and-failure-analysis/` | analyze_corpus_types, cluster_failures, failure_taxonomy, output_doctype, corpus_type_comparison.json, failure_features.json, failure_taxonomy.json, output1_doctype(.json/.txt), output_doctype.json, stratified_page_selection.json, suspect_books.txt, tess_inspect_targets.json, sample_book_ids.txt, item14016_status.json, fail_check2.json + 루트 `failures_out.json` |
| `research/kci-paper-samples/` | kci_sample.txt, kci_sample100.txt, kci_sample70.txt, kci_sample_comparison.json, kci_sample_section2.txt, kci_sample_section3.txt, kci_FI000921643_full.txt, kci_stall_check.json, lit_sample100.txt, test_plain_sample.txt, paper_draft.txt + 루트 `kci_FI000865437_sections.json`, `paper_chunk_sample.json`, `summary_sample.json` |
| `research/gongu-wikisource-manifest-check/` | ws_doctype_check.json, ws_fail.json, ws9_fail.json, ws_search_test.json, ws_status.json |

### ⚠ 확인 필요 (실행 단계에서 사용자에게 보여주고 결정)

- `build_vlm_policy_selection.py` — "운영 도구"(정책 산출물을 파이프라인이 계속 참조)인지 "1회성 연구"인지 애매. → 이동 직전 용도 재확인.
- 루트 `claim17_xml.txt`·`claim2_xml.txt`·`editor_note_heading.txt`·`editor_note_xml.txt`·`effect_close_xml.txt`·`effect_last_para.txt` — 특허 청구항(claim) 성격의 파일로 보이는데 도서관 검색 도메인과의 연관이 spec 작성자(Claude) 기준으로 불명확. → 사용자에게 용도 확인 후 적절한 `research/` 하위 폴더 배정 또는 별도 폴더 신설.

### 제외 (건드리지 않음)

- 루트 `package-lock.json` — npm 의존성 락 파일, 실험 산출물 아님.

### 디버그 로그 — `.gitignore` 추가 후 저장소에서 제거

- 루트: `soffice_log2.txt`, `scripts_debug_out.txt`, `scripts_debug_out2.txt`
- `scripts/`: `debug_raw.txt`
- 참고(이번 라운드 범위 밖, 추가 발견): `app/odl_stderr.log`(8MB)·`app/audit_stderr.log`는 git 미추적 상태 확인됨 — 당장 정리 대상은 아니지만 `.gitignore`에 `*.log` 패턴을 추가해 향후 실수 커밋을 예방한다.

## 4. round01 실행 순서

1. **0단계 캐치업**(위 §2) 수행.
2. `feat/round01-dev-system-bootstrap` 브랜치에서 §1의 문서·스킬·에이전트 파일 생성.
3. §3 규칙에 따라 `research/` 생성 및 `git mv`로 파일 이동. ⚠ 표시 항목은 이동 직전 사용자 확인.
4. `.gitignore`에 로그 패턴 추가, 이미 추적 중인 디버그 로그가 있다면 `git rm --cached`.
5. `docs/guides/round01/00-체계도입.md` 작성(이 라운드의 모든 산출물을 클론코딩 가능하게 수록 + 면접 Q&A).
6. `docs/roadmap/round01-완료노트.md` 작성(디자인 참조 = 해당 없음).
7. 자가 점검 체크리스트 통과 확인:
   - `git status`로 의도한 파일만 변경됐는지 확인
   - 이동된 스크립트 중 하나 이상을 실제로 실행해 경로 참조 깨짐이 없는지 스모크 확인
   - `docker-compose.yml`·`docker-compose.dev.yml`·`alembic.ini`가 이번 변경으로 영향받지 않았는지 확인(물리 이동 없음이므로 정상적으로 영향 없어야 함)
8. 사용자 승인 → `dev` 머지.
9. `/round-finish` 실행 → `dev→main` 병합 + `git push origin main && git push origin dev`.

## 검증 기준 (이 라운드가 끝났다고 말할 수 있는 조건)

- `CLAUDE.md`만 읽고 새 세션이 "무엇을 어디서 보는지" 판단할 수 있다.
- 루트·`scripts/`에 정체불명 실험 파일이 하나도 남아있지 않다(⚠ 확인 필요 항목은 사용자와 합의된 위치로 이동 완료).
- `docker compose config`(또는 최소 `docker-compose.yml`·`docker-compose.dev.yml` 파싱)가 이번 변경 전후로 동일하게 성공한다 — 물리 경로를 건드리지 않았음을 실증.
- `/round-finish` 스킬로 실제 `dev→main`+push까지 한 번 완주된다.

## Out of scope (다음 라운드 이월)

- `docs/adr/ADR-001-*.md` 작성 — 다음 큰 결정 시점에.
- 디자인/Figma 트랙 실제 도입 — 스텁만 유지.
- `app/` 내부 대용량 미추적 로그 파일(`odl_stderr.log` 등) 정리 — 이번 스코프(루트+scripts) 밖.
- `scripts/build_vlm_policy_selection.py`의 최종 배치(⚠ 확인 필요 항목)는 사용자 확인 후 즉시 처리하되, 만약 결론이 나지 않으면 다음 라운드로 이월 가능.
