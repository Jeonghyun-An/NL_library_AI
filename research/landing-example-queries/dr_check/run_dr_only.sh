#!/usr/bin/env bash
# 랜딩 논문 예시 문장으로 딥리서치만(이어가기 없이) — 계획·보고서가 나오는지와 자동 지표
set -u
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
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
run chip_elder "노인의 사회적 지지가 우울에 미치는 영향은?"
run chip_multicultural "다문화가정 아동의 언어 발달은 또래와 어떻게 다를까?"
run chip_library "공공도서관 서비스 품질 평가 지표"
