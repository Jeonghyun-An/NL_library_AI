"""
FLUX.1-dev 표지 이미지 생성 서버.

POST /generate { prompt, width, height, steps, guidance, seed } → image/jpeg
GET  /health                                                    → {"status": "ok"}
"""
import io
import os
import logging
import asyncio

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from diffusers import FluxPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("flux-server")

MODEL_ID = os.environ.get("FLUX_MODEL_ID", "black-forest-labs/FLUX.1-dev")
DTYPE_NAME = os.environ.get("FLUX_DTYPE", "bfloat16")
ENABLE_CPU_OFFLOAD = os.environ.get("FLUX_CPU_OFFLOAD", "true").lower() == "true"
LORA_ID = os.environ.get("FLUX_LORA_ID", "")          # e.g. prithivMLmods/EBook-Creative-Cover-Flux-LoRA
LORA_SCALE = float(os.environ.get("FLUX_LORA_SCALE", "0.85"))

app = FastAPI(title="FLUX.1-dev Cover Server")
_pipe: FluxPipeline | None = None
_lock = asyncio.Lock()


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="이미지 생성 영문 프롬프트")
    negative_prompt: str | None = None
    width: int = Field(768, ge=256, le=1536)
    height: int = Field(1152, ge=256, le=1536)
    num_inference_steps: int = Field(28, ge=4, le=50)
    guidance_scale: float = Field(3.5, ge=0.0, le=15.0)
    seed: int | None = None
    jpeg_quality: int = Field(92, ge=60, le=100)


@app.on_event("startup")
async def _load_pipeline():
    global _pipe
    dtype = {
        "bfloat16": torch.bfloat16,
        "float16":  torch.float16,
        "float32":  torch.float32,
    }.get(DTYPE_NAME, torch.bfloat16)

    log.info(f"FLUX 모델 로드 시작: {MODEL_ID} (dtype={DTYPE_NAME}, cpu_offload={ENABLE_CPU_OFFLOAD})")
    pipe = FluxPipeline.from_pretrained(MODEL_ID, torch_dtype=dtype)

    if ENABLE_CPU_OFFLOAD:
        pipe.enable_model_cpu_offload()
    else:
        pipe = pipe.to("cuda")

    if LORA_ID:
        log.info(f"LoRA 어댑터 로드: {LORA_ID} (scale={LORA_SCALE})")
        pipe.load_lora_weights(LORA_ID)
        pipe.fuse_lora(lora_scale=LORA_SCALE)
        log.info("LoRA 어댑터 로드 완료")

    _pipe = pipe
    log.info("FLUX 모델 로드 완료")


@app.get("/health")
def health():
    return {"status": "ok" if _pipe is not None else "loading"}


@app.post("/generate")
async def generate(req: GenerateRequest):
    if _pipe is None:
        raise HTTPException(status_code=503, detail="model not ready")

    width  = (req.width  // 16) * 16
    height = (req.height // 16) * 16

    async with _lock:
        try:
            generator = (
                torch.Generator(device="cuda").manual_seed(req.seed)
                if req.seed is not None else None
            )
            result = _pipe(
                prompt=req.prompt,
                negative_prompt=req.negative_prompt,
                width=width,
                height=height,
                num_inference_steps=req.num_inference_steps,
                guidance_scale=req.guidance_scale,
                generator=generator,
            )
            image = result.images[0]
        except torch.cuda.OutOfMemoryError as e:
            torch.cuda.empty_cache()
            raise HTTPException(status_code=507, detail=f"CUDA OOM: {e}")
        except Exception as e:
            log.exception("FLUX 생성 실패")
            raise HTTPException(status_code=500, detail=str(e))

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=req.jpeg_quality, optimize=True)
    return Response(content=buf.getvalue(), media_type="image/jpeg")
