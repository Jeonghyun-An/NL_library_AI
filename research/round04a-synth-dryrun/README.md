# 종합 드라이런 (round04a, 2026-09-23)

운영 잡의 `state_snapshot`(탐색이 끝난 체크포인트)으로 **보고서 종합만** 다시 돌려, 같은 근거에서 종합 코드의 전후를 비교한 1회성 실험이다. DB 에 쓰지 않는다. 결과는 `docs/roadmap/round04a-완료노트.md` §3.

| 파일 | 역할 |
|---|---|
| `gen_dryrun.py` | 워킹트리의 `synthesizer.py`·`research_synthesize.yaml` 을 gzip+base64 로 박은 stdin 스크립트를 만든다. `python gen_dryrun.py <저장소 루트>` → 이 폴더에 `synth_dryrun.sh`·`synth_dryrun_body.py` |
| `smoke_dryrun.py` | 만든 본문을 DB 없이 가짜 LLM 으로 먼저 돌려 본다. `python smoke_dryrun.py <저장소>/app` |
| `synth_dryrun_2026-09-23.sh` | 실제로 서버에서 돌린 산출물(`b6360b8` 직전 코드). `JOB=<job_id>` 가 잡힌 셸에 붙여넣어 실행했다 |

**제약**: 박아 넣는 것은 `synthesizer.py` 와 프롬프트뿐이고 나머지 모듈(`citations`·`state`·`llm_json` 등)은 **서버 이미지의 것**을 쓴다. 종합이 새로 의존하는 함수가 이미지에 없으면(예: `2bac7ee` 이후의 `citations.chunks_for`) 임포트에서 실패하므로, 그때는 의존 모듈도 함께 박도록 `gen_dryrun.py` 를 고쳐야 한다.
