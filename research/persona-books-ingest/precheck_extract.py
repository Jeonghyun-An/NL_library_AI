"""페르소나 책 14권 v2 — 다시 적재하기 전에 운영 추출기로 OCR 로 가는 쪽이 있는지 본다 (1회성, 2026-10-23).

적재의 추출 단계와 같은 컨테이너(nl-lib-celery-cpu — 운영 ODL 버전, 함정 22)에서 extract_text 만 부른다. DB·MinIO·Milvus 에는
쓰지 않는다. Qwen VLM 이 꺼져 있어 OCR 로 가는 쪽이 있으면 그 쪽은 ocr_errors 로 잡힌다 — 모두 0 이어야 적재가 OCR 없이
끝난다(로컬 ODL 2.5.0 점검에서는 14권 모두 0, 표지 쪽은 '원래 짧은 쪽'이거나 ODL 채택).

    docker exec -w /app -e PYTHONPATH=/app nl-lib-celery-cpu python /app/data/persona_books/v2/precheck_extract.py
"""
import asyncio
import sys
from pathlib import Path

from services.ingestion.extractor import extract_text

HERE = Path(__file__).resolve().parent
IDS = ("PSN-MANSEJEON", "PSN-SONAGI", "PSN-JEOKBIN", "PSN-CHUNHYANG", "PSN-HEOSAENG", "PSN-BEAUTY-BEAST", "PSN-RED-CAP",
       "PSN-STUDY-SCARLET", "PSN-DOG-FLANDERS", "PSN-ROBIN-HOOD", "PSN-BULFINCH", "PSN-ANDERSEN", "PSN-DADDY-LONG-LEGS",
       "PSN-PERRAULT")
sys.stdout.reconfigure(encoding="utf-8")


async def main() -> None:
    bad = []
    for cid in IDS:
        r = await extract_text(str(HERE / "pdf" / f"{cid}.pdf"), cid)
        p0 = next((p for p in r.pages if p.page_num == 0), None)
        note = any(n in (p.text or "") for p in r.pages for n in ("SKOVIX 소장자료", "페르소나 에이전트"))
        methods = sorted({p.method for p in r.pages})
        # OCR(vlm·surya)로 간 쪽·요청 실패·거절·렌더 실패·데드라인·ODL 폴백 중 하나라도 있으면 첫 적재와 다른 길이라 멈춘다
        if (note or r.errors or r.ocr_errors or r.ocr_rejected or r.render_errors or r.deadline_hit or r.vlm_capped
                or r.odl_fallback or methods != ["opendataloader"]):
            bad.append(cid)
        print(f"{cid:20} 쪽 {r.total_pages} 채택 {len(r.pages)} 방식 {methods} ocr_errors={r.ocr_errors} "
              f"rejected={r.ocr_rejected} errors={len(r.errors)} short_kept={r.short_kept} 폴백={r.odl_fallback} "
              f"문구={note} 1쪽={(p0.text if p0 else None)!r:.60}", flush=True)
    print("모두 OCR 없이 추출 — 다시 적재해도 된다" if not bad else f"!! 멈춤 — 확인 필요: {bad}")


asyncio.run(main())
