# round06e — 논문 키워드 채움률 (1회성)

06e '제목 고르기'(spec D23·§12-4)의 키워드 후보는 두 원천을 코드로 합친다(계획 06e 정함 14 — §12-11 '키워드 후보 원천' 권고).

1. **LLM 후보** — 키워드 생성(kind `concepts`, gemma)이 원 질문·하위질문에서 중요한 순서대로 낸 키워드.
2. **채택 논문의 소장 키워드** — 이어가기 때 FastAPI 가 채택 논문의 `library_catalog.keyword`(653 $a — 구분자로 이은 글)를 나눈 것과 `extra.keywords`(적재 enrichment 가 뽑은 배열)의 **문서 빈도**(그 키워드를 가진 논문 수)를 세어 생성 input 의 `paper_keywords` 에 싣는다(`app/services/research_work/keywords.py` 의 `paper_keyword_counts`).

논문 쪽 원천이 얼마나 차 있는지 몰라 착수 전에 한 번 잰다(spec §12-4 '논문 키워드 채움률은 착수 전에 한 번 잰다 — 낮으면 보조로 둔다').

## 판정 규칙

- 기준은 ② **최근 이어간 연구 20건의 채택 논문 중 키워드(653 또는 추출)가 하나라도 있는 논문의 비율**이다. 소장 전체(①)가 아니라 실제로 후보가 될 논문(채택 근거)을 본다.
  - **50% 이상** → `PAPER_KEYWORD_MIN_N = 1` — 논문에만 있는 후보도 1편부터 후보에 든다(구현 기본값).
  - **50% 미만** → `PAPER_KEYWORD_MIN_N = 2` — 보조로만: 2편 이상 겹친 논문 키워드만 후보에 든다(LLM 후보와 겹친 것은 편수와 상관없이 출처 'AI · 논문 n편'으로 남는다).
- ③ 의 원문 표본으로 `split_catalog_keywords` 의 구분자(기본 `;`·`,`, NFKC 뒤 앞뒤 공백 정리)가 맞는지 본다. 다른 구분자(예: `/`·`|`)가 보이면 그 정규식을 고친다.
- ④ 는 판정이 2 일 때 연구마다 남는 논문 후보 수를 가늠하는 참고다(서버 SQL 의 `lower(btrim())` 은 코드의 `keyword_key`(NFKC → 공백 제거 → casefold)보다 느슨하다 — 띄어쓰기만 다른 같은 말은 둘로 센다).

### SQL 이 피하는 함정

- **함정 10** — `extra->'keywords'` 가 '비지 않음'은 jsonb `?`(키 있음)로 세지 않는다. 빈 배열이 '있음'으로 든다. `jsonb_typeof(…) = 'array'` 이고 `jsonb_array_length(…) > 0` 일 때만 센다(길이는 `CASE` 안에서만 부른다 — 배열이 아닌 값에 부르면 오류이고, Postgres 는 AND 의 계산 순서를 보장하지 않는다). `keyword` 칼럼은 `keyword IS NOT NULL AND btrim(keyword) <> ''`. ② 의 '키워드가 하나라도 있음'도 같은 두 조건의 OR 이다.
- **함정 11** — ③ 의 원문 표본은 정렬 걸린 `LIMIT` 이 아니라 `ORDER BY random() LIMIT 20` 이다(앞부분 편중을 피한다).
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

(서버 실행 뒤 채운다 — `out/fill_rate.md` 의 ①·② 합계 줄·판정 줄·③ 에서 본 구분자, 그리고 그에 따른 결정: `PAPER_KEYWORD_MIN_N` 을 1 로 둘지 2 로 바꿀지, `split_catalog_keywords` 구분자를 고칠지. 바꾸면 그 커밋 해시를 적는다.)
