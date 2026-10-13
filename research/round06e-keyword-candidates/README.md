# round06e — 논문 키워드 채움률 (1회성)

06e '제목 고르기'(spec D23·§12-4)의 키워드 후보는 두 원천을 코드로 합친다(계획 06e 정함 14 — §12-11 '키워드 후보 원천' 권고).

1. **LLM 후보** — 키워드 생성(kind `concepts`, gemma)이 원 질문·하위질문에서 중요한 순서대로 낸 키워드.
2. **채택 논문의 소장 키워드** — 이어가기 때 FastAPI 가 채택 논문의 `library_catalog.keyword`(653 $a — 구분자로 이은 글)를 나눈 것과 `extra.keywords`(적재 enrichment 가 뽑은 배열)의 **문서 빈도**(그 키워드를 가진 논문 수)를 세어 생성 input 의 `paper_keywords` 에 싣는다(`app/services/research_work/keywords.py` 의 `paper_keyword_counts`).

논문 쪽 원천이 얼마나 차 있는지 몰라 착수 전에 한 번 잰다(spec §12-4 '논문 키워드 채움률은 착수 전에 한 번 잰다 — 낮으면 보조로 둔다').

## 판정 규칙

- 기준은 ② **최근 이어간 연구 20건의 채택 논문 중 키워드(653 또는 추출)가 하나라도 있는 논문의 비율**이다. 소장 전체(①)가 아니라 실제로 후보가 될 논문(채택 근거)을 본다.
  - **50% 이상** → `PAPER_KEYWORD_MIN_N = 1` — 논문에만 있는 후보도 1편부터 후보에 든다(구현 기본값).
  - **50% 미만** → `PAPER_KEYWORD_MIN_N = 2` — 보조로만: 2편 이상 겹친 논문 키워드만 후보에 든다(LLM 후보와 겹친 것은 편수와 상관없이 출처 'AI · 논문 n편'으로 남는다).
- ③ 은 `split_catalog_keywords` 의 구분자(기본 `[;,]`, NFKC 뒤 앞뒤 공백 정리)를 정한다. `library_catalog.keyword` 의 구분자는 어느 경로로 채웠느냐에 따라 다르고, 두 가지는 코드로 이미 안다.
  - **MARC 로더 — ` | `**: 653 $a 를 ` | ` 로 잇는다(`app/domains/nl_library/loaders/marc_parser.py:118`·`:256`, 함정 6). source_format `MARC`·`MARC+MODS` 행이다. MARC+MODS 는 MARC 값이 MODS 를 덮고(`marc_mods_xlsx.py:103`) MODS genre 가 thesis·report 면 `doc_type='paper'`(`doc_types.py:38`)라, 딥리서치(`doc_scope="paper"` — `app/services/research/explorer.py:113`)의 채택 논문이 될 수 있다.
  - **적재 보강 — `, `**: 653 이 빈 논문에 `", ".join(추출 키워드)` 를 넣는다(`app/services/ingestion/stages.py:538-539`). KCI 로더는 keyword 를 채우지 않아(`kci_xlsx.py` `_COL_MAP`) KCI 행은 보강 몫뿐이다.
  - 보강으로 채운 `, ` 행이 많으면 무작위 표본에 ` | ` 행이 하나도 안 나올 수 있다. 그래서 표본이 아니라 **세어서** 판정한다(함정 10 의 교훈 — 코드 경로가 있다고 그 데이터가 있는 것은 아니다). ③ 첫 표는 ② 의 채택 논문과 소장 논문 전체에서 source_format 갈래마다 653 키워드가 있는 행과 그중 `|`·`,`·`;` 를 포함한 행을 센다.
  - **판정:** 첫 표의 `'|' 포함` 이 어느 범위에서든 0 보다 크면 `split_catalog_keywords` 에 `|` 를 더한다(Task Z1 Step 5). 0 이면 그대로. 스크립트가 표 아래에 이 판정 줄(`구분자 판정: …`)을 찍는다.
  - ③ 둘째 표(source_format 마다 10개 원문 표본)로는 그 밖의 구분자(예: `/`)가 있는지 눈으로 본다. 보이면 그 글자도 같은 식으로 더한다.
- ④ 는 판정이 2 일 때 연구마다 남는 논문 후보 수를 가늠하는 참고다. `;`·`,`·`|` 로 나눈다 — ③ 판정이 `|` 를 더하면 코드와 같고, `|` 행이 없으면 나누는 결과가 같다(서버 SQL 의 `lower(btrim())` 은 코드의 `keyword_key`(NFKC → 공백 제거 → casefold)보다 느슨하다 — 띄어쓰기만 다른 같은 말은 둘로 센다).

### SQL 이 피하는 함정

- **함정 10** — `extra->'keywords'` 가 '비지 않음'은 jsonb `?`(키 있음)로 세지 않는다. 빈 배열이 '있음'으로 든다. `jsonb_typeof(…) = 'array'` 이고 `jsonb_array_length(…) > 0` 일 때만 센다(길이는 `CASE` 안에서만 부른다 — 배열이 아닌 값에 부르면 오류이고, Postgres 는 AND 의 계산 순서를 보장하지 않는다). `keyword` 칼럼은 `keyword IS NOT NULL AND btrim(keyword) <> ''`. ② 의 '키워드가 하나라도 있음'도 같은 두 조건의 OR 이다.
- **함정 11** — ③ 의 원문 표본은 정렬 걸린 `LIMIT` 이 아니라 source_format 갈래마다 `row_number() OVER (PARTITION BY lc.source_format ORDER BY random())` 로 10개씩이다(앞부분 편중을 피하고, 한 갈래가 많아 다른 갈래가 표본에서 빠지는 일도 피한다).
- ② 의 '최근 20건'은 표본이 아니라 **대상의 정의**(시연·실사용에 가까운 최근 연구)라 `ORDER BY created_at DESC LIMIT 20` 그대로 둔다. 예시 연구(`is_example`)·지운 연구(`deleted_at`)는 뺀다.

## 실행

읽기 전용이다 — 트랜잭션을 `READ ONLY` 로 열고 `statement_timeout` 120초를 건다. 개발 PC 에서는 SQL 만 찍어 본다(운영 DB 에 붙지 않는다).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && python -I research/round06e-keyword-candidates/measure.py --dry-run
```

서버(사용자, root 셸 — `research/` 는 앱 이미지에 없다, 함정 4): 이 폴더를 `/data/nl-lib/data/round06e-keyword-candidates/` 로 옮긴 뒤(일반 계정 홈으로 받은 뒤 root 셸에서 `cp`)

```bash
mkdir -p /data/nl-lib/data/round06e-keyword-candidates/out
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round06e-keyword-candidates/measure.py \
  > /data/nl-lib/data/round06e-keyword-candidates/out/fill_rate.md
```

DB 주소는 컨테이너 env(`DB_*`)로 만든 `DATABASE_URL_SYNC`(psycopg2)다. 끝나면 서버의 `out/fill_rate.md` 를 이 폴더로 가져와 커밋하고 아래 '결과'를 채운다.

## 결과

(서버 실행 뒤 채운다 — `out/fill_rate.md` 의 ①·② 합계 줄·판정 줄·③ 구분자 판정 줄(범위별 `'|' 포함` 행 수)과 표본에서 본 그 밖의 구분자, 그리고 그에 따른 결정: `PAPER_KEYWORD_MIN_N` 을 1 로 둘지 2 로 바꿀지, `split_catalog_keywords` 구분자를 고칠지. 바꾸면 그 커밋 해시를 적는다.)
