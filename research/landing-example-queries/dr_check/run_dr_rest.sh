#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
# 끊긴 old_multicultural 은 잡이 이미 끝났다 — 결과만 받는다
(cd old_multicultural && timeout 600 python tools/s2_poll_job.py "$(tail -1 s1_out.txt)" 10 > s2_out.txt 2>&1; tail -1 s2_out.txt | cut -c1-120)
run() {
  name=$1; q=$2
  mkdir -p "$name" && cp -r ../e2e_api7/tools "$name/" && cd "$name"
  echo "=== $name $(date +%T) $q"
  job=$(timeout 600 python tools/s1_create.py "$q" 2>&1 | tee s1_out.txt | tail -1)
  grep -E "^[0-9] " s1_out.txt
  echo "job $job"; echo "$job" > job_id.txt
  timeout 1200 python tools/s2_poll_job.py "$job" 20 > s2_out.txt 2>&1; tail -1 s2_out.txt | cut -c1-200
  python tools/analyze_report5.py job_final.json 2>&1 | grep -E "^stats|looks_like_bibliography True|dup pairs|summaries total|^  (OK|BAD)|NREF total|has\[E#\]=False|generic=\['" | cut -c1-160
  cd ..
}
run old_library "공공도서관 서비스 품질 평가 연구가 궁금해"
run alt_multicultural "다문화가정 아동의 언어 발달에 영향을 주는 요인"
run alt_library "공공도서관 서비스 품질은 어떻게 평가할까?"
