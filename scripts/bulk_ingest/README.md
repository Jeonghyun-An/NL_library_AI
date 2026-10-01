# 대량 반입 도구 (bulk_ingest)

로컬 PC에 크롤링된 PDF + 엑셀 메타데이터를 서버(MinIO)로 올리고, 인덱싱 잡을 생성하기 위한 도구.

## 전체 흐름

```
[로컬 PC]
  1) build_manifest.py   엑셀 ↔ PDF 매칭 → manifest.jsonl + validation_report.json
  2) 검증 리포트 확인     누락/중복/0바이트 점검
  3) rclone copy         PDF → MinIO originals/{id}/{id}.pdf
  4) rclone copy         manifest.jsonl → MinIO manifests/{job}/
[서버]
  5) 잡 생성 API         POST /api/admin/ingest-jobs  (manifest_key 지정)
  6) 잡 시작             POST /api/admin/ingest-jobs/{id}/start
  7) 대시보드 모니터링   /admin/jobs
```

## 1) 매니페스트 생성

```bash
python build_manifest.py \
  --excel meta1.xlsx meta2.xlsx \
  --pdf-dir "D:/crawled/pdfs" \
  --out "./out/round1" \
  --match-by kci_fi_id \
  --deep-check          # PDF 헤더 매직바이트 검사 (선택)
```

- 매칭 규칙: PDF 파일명(stem) → 정규화(`strip` + 끝 `_` 제거) → 엑셀 ID 컬럼과 매칭
- `--match-by`: `kci_fi_id`(기본) | `arti_id` | `contents_id`
- 출력:
  - `manifest.jsonl` — 1행 = `{book_id, file, object_key, size, title}`
  - `validation_report.json` — `matched / meta_without_pdf / pdf_without_meta / duplicates / zero_size / unreadable_pdf`

**object_key는 `originals/{book_id}/{book_id}.pdf` 구조**입니다. 썸네일 폴백(`get_book_thumbnail`)이 이 prefix를 스캔하므로 플랫 키(`originals/{id}.pdf`)는 쓰지 마세요.

## 2) 검증 리포트 점검

`validation_report.json`에서 다음을 확인:
- `meta_without_pdf` — 메타는 있는데 PDF가 없는 ID (크롤링 누락)
- `pdf_without_meta` — PDF는 있는데 메타가 없는 ID (메타 누락)
- `duplicates` — 같은 ID로 PDF가 2개 이상 (첫 번째만 매니페스트에 포함됨)
- `zero_size` / `unreadable_pdf` — 손상 파일

## 3) PDF를 MinIO로 적재

매니페스트의 `object_key`는 **평탄 키** `originals/{id}.pdf` 입니다. 파일명이 곧 ID이므로
PDF 폴더를 `originals/` 아래로 그대로 미러링하면 키가 일치합니다. (썸네일·PDF 뷰어
엔드포인트가 폴더형/평탄형 둘 다 지원하도록 폴백되어 있어 평탄 키로 동작합니다.)

### 권장: 서버로 PDF 이송 후 `mc mirror` (서버→MinIO 로컬, 가장 빠르고 재개 가능)

데이터가 로컬 PC, MinIO가 원격일 때는 PDF를 먼저 서버로 옮긴 뒤(디스크/rsync/scp),
서버에서 MinIO로 로컬 적재하는 것이 286GB급에 가장 빠르다.

```bash
# 서버에서 (mc = MinIO Client)
mc alias set local http://127.0.0.1:9000 <ACCESS_KEY> <SECRET_KEY>
mc mirror --overwrite /data/kci/pdf/  local/nl-lib-bucket/originals/
#   → originals/KCI_FI....pdf (평탄 키). 중단되면 같은 명령 재실행 시 이어서 진행.
```

> `mc mirror`는 매니페스트와 무관하게 PDF만 올린다. 메타 없는 PDF(28k)도 함께 올라가지만
> 잡 생성 시 자동 제외되므로 무방하다. 매칭된 것만 올리려면 아래 upload_from_manifest 사용.

### 대안: 원격 MinIO 직접 전송 (이 PC에서 MinIO 접근 가능할 때)

```bash
# 매니페스트의 file → object_key 로 멀티스레드 업로드 (rename 처리 포함)
python upload_from_manifest.py \
  --manifest <out>/manifest.jsonl \
  --endpoint <서버IP>:21000 \
  --access-key <MINIO_ACCESS_KEY> --secret-key <MINIO_SECRET_KEY> \
  --bucket nl-lib-bucket --workers 16
```

### 매니페스트 업로드 (잡 생성에 필요)

```bash
# 서버에서 mc 로 (또는 이 PC에서 rclone/upload 스크립트로)
mc cp <out>/pilot.jsonl local/nl-lib-bucket/manifests/pilot/pilot.jsonl       # 파일럿
mc cp <out>/manifest.jsonl local/nl-lib-bucket/manifests/round1/manifest.jsonl # 본가동
```

→ 잡 생성 시 `manifest_key = manifests/pilot/pilot.jsonl` (또는 round1) 로 지정.

## 4) 잡 생성 & 시작

```bash
# 잡 생성 (dry-run 검증 후 status='ready')
curl -X POST http://<서버IP>/api/admin/ingest-jobs \
  -H "Content-Type: application/json" \
  -d '{
        "name": "papers-round1",
        "manifest_key": "manifests/round1/manifest.jsonl",
        "params": {"skip_cover": true, "doc_type": "paper", "high_water": 32}
      }'

# 시작
curl -X POST http://<서버IP>/api/admin/ingest-jobs/<job_id>/start
```

진행 현황은 `/admin/jobs` 대시보드 또는 `GET /api/admin/ingest-jobs/{id}`로 확인합니다.

## 5) 재처리·카나리 도구 (서버에서, DB 읽기 전용)

둘 다 앱 모듈(`db.postgres`)을 쓰므로 서버의 `/data/nl-lib/data/round07/` 에 복사해 `nl-lib-fastapi` 안에서
`docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round07/<스크립트> …` 로 돌린다
(`docs/ops/recurring-gotchas.md` 4번). 인자·출력은 각 파일 머리말, 배포 순서 안의 쓰임은
`docs/ops/bulk_ingest_runbook.md` §9.

| 스크립트 | 하는 일 | 쓰는 것 |
|---|---|---|
| `select_near_empty_items.py` | done 이고 8쪽 이상인데 쪽당 본문 글자 수가 150자 미만인 아이템 | CSV(사람이 본다) + retry API 본문 JSON |
| `build_canary_manifest.py` | 본 잡에서 문제 유형별 50건(스캔본 20·표 10·잘게 쪼개짐 5·섹션 40개 초과 5·보통 10) | 매니페스트 JSONL — 업로드·잡 생성·시작 명령은 출력만 |
