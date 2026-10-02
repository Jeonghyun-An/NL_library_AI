#!/bin/sh
# pg_backup.sh — nl_lib Postgres 정기 백업 (호스트 cron 에서 실행)
#
# 2026-09-14 library_catalog 이 통째로 비워져 고아 문서 72,601 건이 발생했다.
# 복구가 가능했던 건 원본 카탈로그 파일이 uploads/ 에 남아있고 초록이 Milvus 청크에
# 남아있었기 때문이지 설계된 안전장치 덕이 아니었다. 그래서 백업을 붙인다.
#
# 두 단계로 나눈다 (실측: DB 4.8GB, library_catalog 381MB, book_sections 4.1GB):
#   daily  — library_catalog 만. 작아서 매일 돌려도 부담이 없고, 실제로 날아간 것이 이 테이블이다.
#            연구 테이블(research_*)과 history_items 도 따로 받는다(research_<ts>.dump) — 사용자가
#            쌓은 연구·기록이라 다시 만들 수 없다. paper_facets(다시 만들 수 있는 캐시)는 weekly 에 맡긴다.
#   weekly — 전체 DB. book_sections(원문 100만행 이상)까지 포함해 무겁지만,
#            원문은 재추출에 OCR 비용이 들어 반드시 지켜야 한다.
# 한 덤프가 실패해도 나머지 덤프·정리는 돌고, 끝에서 1 로 끝난다(cron 로그에 FAIL 줄이 남는다).
#
# 인증: postgres 컨테이너가 로컬 소켓 접속을 신뢰하므로 비밀번호가 필요 없다.
# 백업 위치는 Postgres 볼륨 바깥이어야 한다 — 볼륨이 날아갈 때 같이 죽으면 의미가 없다.
#
# 설치:
#   sudo install -m 755 pg_backup.sh /usr/local/bin/nl-lib-pg-backup
#   sudo crontab -e
#     30 4 * * * /usr/local/bin/nl-lib-pg-backup >> /var/log/nl-lib-backup.log 2>&1
#
# 복원 (반드시 한 번은 연습할 것 — 복원해 본 적 없는 백업은 백업이 아니다):
#   docker exec -i nl-lib-postgres pg_restore -U admin -d nl_lib --clean --if-exists \
#     -t library_catalog < /data/nl-lib/backup/daily/library_catalog_<타임스탬프>.dump
# 연구 덤프는 테이블끼리 외래 키로 묶여 있어 통째로 되돌린다 — 한 테이블만 -t 로 --clean 하면 그 테이블을
# 가리키는 다른 연구 테이블 때문에 DROP 이 막힌다. 되돌리는 동안 이 테이블들에 쓰는 컨테이너를 먼저 멈추고
# 끝나면 다시 올린다(nl-lib-fastapi·nl-lib-celery-research·nl-lib-celery-research-plan·nl-lib-celery-control — 돌고 있으면 잠금에
# 걸리거나 도중에 쓴 행을 잃는다):
#   docker exec -i nl-lib-postgres pg_restore -U admin -d nl_lib --clean --if-exists \
#     < /data/nl-lib/backup/daily/research_<타임스탬프>.dump
# 한 테이블만 꺼내 볼 때는 운영 DB 를 건드리지 않고 빈 DB 에 푼다:
#   docker exec nl-lib-postgres createdb -U admin nl_lib_restore_check
#   docker exec -i nl-lib-postgres pg_restore -U admin -d nl_lib_restore_check \
#     -t research_works < /data/nl-lib/backup/daily/research_<타임스탬프>.dump
set -eu

# 공유 서버라 로컬 계정 누구나 접근 가능 — weekly 전체 덤프에는
# search_history.query(사용자 검색어 원문)가 그대로 들어있어 소유자만 읽게 한다.
umask 077

BACKUP_DIR="${NL_LIB_BACKUP_DIR:-/data/nl-lib/backup}"
CONTAINER="${NL_LIB_PG_CONTAINER:-nl-lib-postgres}"
DB="${NL_LIB_PG_DB:-nl_lib}"
DB_USER="${NL_LIB_PG_USER:-admin}"
KEEP_DAILY="${NL_LIB_KEEP_DAILY:-14}"
KEEP_WEEKLY="${NL_LIB_KEEP_WEEKLY:-4}"

ts="$(date +%Y%m%dT%H%M%S)"
mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

# 임시 파일에 받고 성공했을 때만 제자리로 옮긴다 — 중단된 덤프가 백업인 척하면 안 된다.
# 첫 인자는 받을 파일, 나머지는 pg_dump 에 그대로 넘긴다("$@" — 'research_*' 같은 패턴이 셸 glob 으로
# 풀리지 않고 pg_dump 의 -t 패턴으로 간다).
dump() {
  target="$1"
  shift
  tmp="$target.part"
  if docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB" --format=custom "$@" > "$tmp"; then
    mv "$tmp" "$target"
    echo "$(date -Is) OK   $target ($(du -h "$target" | cut -f1))"
  else
    rm -f "$tmp"
    echo "$(date -Is) FAIL $target"
    return 1
  fi
}

# 앞 덤프가 실패해도 뒤 덤프·정리는 돈다 — 실패는 rc 에 모았다가 끝에서 알린다
rc=0
dump "$BACKUP_DIR/daily/library_catalog_$ts.dump" -t library_catalog || rc=1
# 패턴은 따옴표째 넘긴다 — pg_dump 가 research_jobs·research_steps·research_works 등과 그 시퀀스를 고른다
dump "$BACKUP_DIR/daily/research_$ts.dump" -t 'research_*' -t history_items || rc=1

# 일요일에만 전체 덤프
if [ "$(date +%u)" = "7" ]; then
  dump "$BACKUP_DIR/weekly/nl_lib_full_$ts.dump" || rc=1
fi

# 최신 N 개만 남긴다. 패턴을 따옴표 없이 둬야 셸이 glob 을 확장한다
# (ls "pattern*" 는 ls 가 글로빙을 하지 않아 동작하지 않는다).
prune() {
  dir="$1"
  pat="$2"
  keep="$3"
  cd "$dir" || return 0
  ls -1t $pat 2>/dev/null | tail -n "+$((keep + 1))" | while read -r f; do
    rm -f "$dir/$f"
    echo "$(date -Is) prune $f"
  done
}

prune "$BACKUP_DIR/daily" "library_catalog_*.dump" "$KEEP_DAILY"
prune "$BACKUP_DIR/daily" "research_*.dump" "$KEEP_DAILY"
prune "$BACKUP_DIR/weekly" "nl_lib_full_*.dump" "$KEEP_WEEKLY"

exit "$rc"
