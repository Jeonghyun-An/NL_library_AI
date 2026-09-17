#!/bin/sh
# pg_backup.sh — nl_lib Postgres 정기 백업 (호스트 cron 에서 실행)
#
# 2026-09-14 library_catalog 이 통째로 비워져 고아 문서 72,601 건이 발생했다.
# 복구가 가능했던 건 원본 카탈로그 파일이 uploads/ 에 남아있고 초록이 Milvus 청크에
# 남아있었기 때문이지 설계된 안전장치 덕이 아니었다. 그래서 백업을 붙인다.
#
# 두 단계로 나눈다 (실측: DB 4.8GB, library_catalog 381MB, book_sections 4.1GB):
#   daily  — library_catalog 만. 작아서 매일 돌려도 부담이 없고, 실제로 날아간 것이 이 테이블이다.
#   weekly — 전체 DB. book_sections(원문 100만행 이상)까지 포함해 무겁지만,
#            원문은 재추출에 OCR 비용이 들어 반드시 지켜야 한다.
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
set -eu

BACKUP_DIR="${NL_LIB_BACKUP_DIR:-/data/nl-lib/backup}"
CONTAINER="${NL_LIB_PG_CONTAINER:-nl-lib-postgres}"
DB="${NL_LIB_PG_DB:-nl_lib}"
DB_USER="${NL_LIB_PG_USER:-admin}"
KEEP_DAILY="${NL_LIB_KEEP_DAILY:-14}"
KEEP_WEEKLY="${NL_LIB_KEEP_WEEKLY:-4}"

ts="$(date +%Y%m%dT%H%M%S)"
mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

# 임시 파일에 받고 성공했을 때만 제자리로 옮긴다 — 중단된 덤프가 백업인 척하면 안 된다.
dump() {
  target="$2"
  tmp="$target.part"
  if docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB" --format=custom $1 > "$tmp"; then
    mv "$tmp" "$target"
    echo "$(date -Is) OK   $target ($(du -h "$target" | cut -f1))"
  else
    rm -f "$tmp"
    echo "$(date -Is) FAIL $target"
    return 1
  fi
}

dump "-t library_catalog" "$BACKUP_DIR/daily/library_catalog_$ts.dump"

# 일요일에만 전체 덤프
if [ "$(date +%u)" = "7" ]; then
  dump "" "$BACKUP_DIR/weekly/nl_lib_full_$ts.dump"
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
prune "$BACKUP_DIR/weekly" "nl_lib_full_*.dump" "$KEEP_WEEKLY"
