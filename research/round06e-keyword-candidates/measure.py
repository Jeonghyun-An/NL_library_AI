r"""measure.py — 논문 키워드 채움률 1회성 측정 (round06e Task K1 — spec §12-4 '논문 키워드 채움률은 착수 전에 한 번 잰다')

06e 의 키워드 후보는 LLM 후보(개념 생성을 넓힘)에 채택 논문의 소장 키워드 문서 빈도를 코드로 합친다(계획 06e 정함 14).
논문 쪽 원천은 library_catalog.keyword(653 $a — 구분자로 이은 글)와 extra.keywords(적재 enrichment 가 뽑은 배열)다.
채움률이 낮으면 논문 키워드는 보조로만 둔다 — 2편 이상 겹친 것만 후보에 든다(keywords.PAPER_KEYWORD_MIN_N = 2).

읽기 전용이다 — SELECT 만 하고 트랜잭션을 READ ONLY 로 연다. 출력은 markdown 표(stdout).
  ① 소장 논문 전체(doc_type='paper')의 653 키워드·추출 키워드·둘 중 하나가 있는 비율
  ② 최근 이어간 연구 RECENT_WORKS 건(research_works 최근순)의 채택 논문(research_reading origin evidence) 중
     키워드가 하나라도 있는 비율과 연구별 분포 — 판정의 기준
  ③ 653 키워드 원문 표본 SAMPLE_SIZE 개(ORDER BY random() — 함정 11) — 구분자 확인용
  ④ ② 의 연구별로 서로 다른 키워드 수(1편 이상·2편 이상) — 판정이 2 일 때 남는 후보 수를 가늠한다
함정 10: extra->'keywords' 를 jsonb ? 로 세지 않는다(빈 배열이 '있음'으로 든다) — 배열이고 길이가 0 보다 클 때만 센다.
Postgres 는 AND 의 계산 순서를 보장하지 않아 jsonb_array_length 는 CASE 안에서만 부른다(배열이 아니면 오류).

실행(서버 — research/ 는 앱 이미지에 없다, 함정 4): README.md '실행'. 개발 PC 에서는 --dry-run 만 돌린다(SQL 만 찍는다).
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))   # 개발 PC 에서 돌릴 때 — 컨테이너는 PYTHONPATH=/app

RECENT_WORKS = 20     # 판정 대상 — 표본이 아니라 '시연·실사용에 가까운 최근 연구'라는 정의다(ORDER BY created_at DESC 그대로)
SAMPLE_SIZE = 20      # 653 키워드 원문 표본 — 구분자를 눈으로 본다(ORDER BY random())
THRESHOLD = 0.5       # ② 의 비율이 이 값 이상이면 PAPER_KEYWORD_MIN_N = 1, 아래면 2

HAS_CATALOG = "(lc.keyword IS NOT NULL AND btrim(lc.keyword) <> '')"
HAS_EXTRACTED = ("(CASE WHEN jsonb_typeof(lc.extra->'keywords') = 'array' "
                 "THEN jsonb_array_length(lc.extra->'keywords') ELSE 0 END > 0)")
HAS_ANY = f"({HAS_CATALOG} OR {HAS_EXTRACTED})"
RECENT = f"""
recent AS (
  SELECT id, created_at FROM research_works
  WHERE deleted_at IS NULL AND is_example = false
  ORDER BY created_at DESC
  LIMIT {RECENT_WORKS}
)"""

SQL_CATALOG = f"""
SELECT count(*) AS papers,
       count(*) FILTER (WHERE {HAS_CATALOG}) AS catalog_keyword,
       count(*) FILTER (WHERE {HAS_EXTRACTED}) AS extracted_keywords,
       count(*) FILTER (WHERE {HAS_ANY}) AS any_keyword
FROM library_catalog lc
WHERE lc.doc_type = 'paper'"""

SQL_RECENT = f"""
WITH {RECENT.strip()}
SELECT CAST(r.id AS text) AS work_id, r.created_at,
       count(rr.cnts_id) AS papers,
       count(rr.cnts_id) FILTER (WHERE {HAS_ANY}) AS any_keyword
FROM recent r
LEFT JOIN research_reading rr ON rr.work_id = r.id AND rr.origin = 'evidence'
LEFT JOIN library_catalog lc ON lc.cnts_id = rr.cnts_id
GROUP BY r.id, r.created_at
ORDER BY r.created_at DESC"""

SQL_SAMPLE = f"""
SELECT lc.cnts_id, lc.keyword
FROM library_catalog lc
WHERE lc.doc_type = 'paper' AND {HAS_CATALOG}
ORDER BY random()
LIMIT {SAMPLE_SIZE}"""

SQL_OVERLAP = f"""
WITH {RECENT.strip()},
words AS (
  SELECT rr.work_id, rr.cnts_id, lower(btrim(k.word)) AS word
  FROM recent r
  JOIN research_reading rr ON rr.work_id = r.id AND rr.origin = 'evidence'
  JOIN library_catalog lc ON lc.cnts_id = rr.cnts_id
  CROSS JOIN LATERAL regexp_split_to_table(coalesce(lc.keyword, ''), '[;,]') AS k(word)
  UNION
  SELECT rr.work_id, rr.cnts_id, lower(btrim(k.word))
  FROM recent r
  JOIN research_reading rr ON rr.work_id = r.id AND rr.origin = 'evidence'
  JOIN library_catalog lc ON lc.cnts_id = rr.cnts_id
  CROSS JOIN LATERAL jsonb_array_elements_text(
    CASE WHEN jsonb_typeof(lc.extra->'keywords') = 'array' THEN lc.extra->'keywords'
         ELSE CAST('[]' AS jsonb) END) AS k(word)
),
counted AS (
  SELECT work_id, word, count(DISTINCT cnts_id) AS n FROM words WHERE word <> '' GROUP BY work_id, word
)
SELECT CAST(work_id AS text) AS work_id,
       count(*) AS words_n1,
       count(*) FILTER (WHERE n >= 2) AS words_n2
FROM counted
GROUP BY work_id
ORDER BY work_id"""

QUERIES = (
    ("① 소장 논문 전체의 키워드 채움", SQL_CATALOG),
    (f"② 최근 이어간 연구 {RECENT_WORKS}건의 채택 논문 — 판정 기준", SQL_RECENT),
    (f"③ 653 키워드 원문 표본 {SAMPLE_SIZE}개 — 구분자 확인", SQL_SAMPLE),
    ("④ 연구별 서로 다른 키워드 수(1편 이상·2편 이상)", SQL_OVERLAP),
)


def _cell(value) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[tuple]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def _rate(part: int, whole: int) -> str:
    return f"{part / whole:.1%}" if whole else "—"


def _default_url() -> str:
    from core.config import get_settings     # 컨테이너 env(DB_*)로 만든 동기 URL(psycopg2 — 앱 이미지에 있다)

    return get_settings().DATABASE_URL_SYNC


def report(conn) -> str:
    from sqlalchemy import text

    out: list[str] = ["# round06e 논문 키워드 채움률", ""]
    (papers, catalog, extracted, any_kw), = conn.execute(text(SQL_CATALOG)).all()
    out += [f"## {QUERIES[0][0]}", "", _table(
        ["논문 수", "653 키워드", "추출 키워드", "둘 중 하나", "비율"],
        [(papers, catalog, extracted, any_kw, _rate(any_kw, papers))]), ""]

    rows = conn.execute(text(SQL_RECENT)).all()
    total = sum(r.papers for r in rows)
    with_any = sum(r.any_keyword for r in rows)
    out += [f"## {QUERIES[1][0]}", "", _table(
        ["연구", "이어간 시각", "채택 논문", "키워드 있음", "비율"],
        [(r.work_id, r.created_at, r.papers, r.any_keyword, _rate(r.any_keyword, r.papers)) for r in rows]
        + [("합계", "", total, with_any, _rate(with_any, total))]), ""]
    if total:
        decided = 1 if with_any / total >= THRESHOLD else 2
        out += [f"판정: 비율 {_rate(with_any, total)} — 기준 {THRESHOLD:.0%} {'이상' if decided == 1 else '미만'} "
                f"→ PAPER_KEYWORD_MIN_N = {decided}", ""]
    else:
        out += ["판정: 이어간 연구의 채택 논문이 없다 — 기본값 PAPER_KEYWORD_MIN_N = 1 그대로", ""]

    sample = conn.execute(text(SQL_SAMPLE)).all()
    out += [f"## {QUERIES[2][0]}", "", _table(["cnts_id", "keyword 원문"], [tuple(r) for r in sample]), ""]

    overlap = conn.execute(text(SQL_OVERLAP)).all()
    out += [f"## {QUERIES[3][0]}", "", _table(
        ["연구", "키워드(1편 이상)", "키워드(2편 이상)"], [tuple(r) for r in overlap]), ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="논문 키워드 채움률 1회성 측정(읽기 전용)")
    ap.add_argument("--dry-run", action="store_true", help="DB 에 붙지 않고 SQL 만 찍는다")
    ap.add_argument("--db", default=None, help="동기 DB URL(postgresql://…) — 없으면 core.config 의 DATABASE_URL_SYNC")
    args = ap.parse_args(argv)
    # 표는 파일로 받아 커밋한다(out/fill_rate.md) — Windows 콘솔(cp949)·python -I(PYTHONIOENCODING 무시)에서도 UTF-8 로 쓴다
    sys.stdout.reconfigure(encoding="utf-8")
    if args.dry_run:
        for title, sql in QUERIES:
            print(f"-- {title}\n{sql.strip()};\n")
        return 0
    from sqlalchemy import create_engine, text

    engine = create_engine(args.db or _default_url())
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout = '120s'"))
            print(report(conn))
            conn.rollback()
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
