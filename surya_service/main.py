"""Surya OCR 마이크로서비스.

전용 문서 OCR 모델(Surya)을 별도 컨테이너로 격리해 제공한다.
- 본 서비스의 transformers(5.x)는 인덱싱 본체(transformers 4.44)와 충돌하므로 분리 운영.
- 인덱싱 파이프라인(extractor)이 페이지 이미지를 base64 PNG로 보내면 텍스트를 반환.

엔드포인트:
  GET  /health  → 상태
  POST /ocr     → {"image_b64": "..."} → {"text": "...", "n_blocks": N}
"""
import base64
import io
import logging
import os
import re

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("surya_service")

app = FastAPI(title="Surya OCR Service")

_TAG_RE = re.compile(r"<[^>]+>")
_rec = None  # RecognitionPredictor 싱글턴 (로딩 비쌈)


def _get_predictor():
    global _rec
    if _rec is None:
        from surya.recognition import RecognitionPredictor
        log.info("Surya RecognitionPredictor 로딩 중...")
        _rec = RecognitionPredictor()
        log.info("Surya 로딩 완료")
    return _rec


class OCRRequest(BaseModel):
    image_b64: str


@app.on_event("startup")
def _warmup():
    # 첫 요청 지연 방지 — 기동 시 모델 미리 로드
    try:
        _get_predictor()
    except Exception as e:  # 기동은 계속, 첫 요청에서 재시도
        log.warning(f"warmup 실패(첫 요청 시 재시도): {e}")


@app.get("/health")
def health():
    return {"status": "ok", "loaded": _rec is not None}


@app.post("/ocr")
def ocr(req: OCRRequest):
    from PIL import Image

    img = Image.open(io.BytesIO(base64.b64decode(req.image_b64))).convert("RGB")
    res = _get_predictor()([img], full_page=True)[0]

    lines = []
    for blk in res.blocks:
        html = getattr(blk, "html", "") or ""
        txt = _TAG_RE.sub("", html).strip()
        if txt:
            lines.append(txt)

    return {"text": "\n".join(lines), "n_blocks": len(lines)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
