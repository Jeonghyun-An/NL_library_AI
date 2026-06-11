"""
도서 표지 자동 생성 모듈.

흐름:
  ① LLM에게 표지 이미지 생성용 영문 프롬프트를 만들어달라고 요청
     (책 소개·테마·장르를 시각적 장면으로 변환)
  ② FLUX.1-dev 서버에 프롬프트를 보내 표지 이미지(JPEG) 생성
  ③ MinIO 업로드 후 key 반환

외부 의존:
  - LLM_BASE_URL (기존 vLLM 서버)
  - FLUX_BASE_URL (이번에 추가된 FLUX 서버)
  - MinIO
"""
import io
import logging
import httpx

from core.config import get_settings

log = logging.getLogger(__name__)


# ── 표지 프롬프트 생성 ──────────────────────────────────────
async def generate_cover_prompt(
    title: str,
    author: str,
    kdc: str,
    themes: str,
    introduction: str,
    summary: str,
) -> str | None:
    """책 메타·소개를 받아 FLUX용 영문 프롬프트를 LLM으로 생성."""
    from services.prompts import get_prompt

    cfg = get_settings()
    system, user, params = get_prompt("cover_prompt").render(
        title=title or "Untitled",
        author=author or "Unknown",
        kdc=kdc or "N/A",
        themes=themes or "N/A",
        introduction=(introduction or "")[:1500],
        summary=(summary or "")[:1500],
    )
    payload = {
        "model": cfg.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **params,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{cfg.LLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
    if not text:
        return None
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()
    return text


# ── FLUX 이미지 생성 ────────────────────────────────────────
async def render_cover_image(
    prompt: str,
    width: int = 768,
    height: int = 1152,
    steps: int = 28,
    guidance: float = 3.5,
    seed: int | None = None,
) -> bytes | None:
    """FLUX 서버에 프롬프트 전송 → 표지 JPEG 바이트 반환."""
    cfg = get_settings()
    body = {
        "prompt": prompt,
        "width":  width,
        "height": height,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "seed": seed,
    }
    async with httpx.AsyncClient(timeout=cfg.FLUX_TIMEOUT) as client:
        resp = await client.post(f"{cfg.FLUX_BASE_URL}/generate", json=body)
        resp.raise_for_status()
        return resp.content or None


# ── MinIO 업로드 + 동기 래퍼 ────────────────────────────────
def upload_cover_to_minio(book_id: str, image_bytes: bytes, minio_client) -> str:
    """MinIO에 표지 업로드. covers/{book_id}.jpg 키 반환."""
    cfg = get_settings()
    key = f"covers/{book_id}.jpg"
    minio_client.put_object(
        cfg.MINIO_BUCKET,
        key,
        io.BytesIO(image_bytes),
        length=len(image_bytes),
        content_type="image/jpeg",
    )
    return key


async def generate_and_store_cover(
    book_id: str,
    title: str,
    author: str,
    kdc: str,
    themes: str,
    introduction: str,
    summary: str,
    minio_client,
) -> tuple[str | None, str | None]:
    """
    표지 프롬프트 생성 → 이미지 생성 → MinIO 업로드 일괄 수행.
    returns (minio_key, prompt). 실패 시 (None, prompt or None).
    """
    if not (introduction or summary or themes):
        log.info(f"[{book_id}] 표지 생성 스킵: 소개/요약/테마 모두 없음")
        return None, None

    try:
        prompt = await generate_cover_prompt(
            title=title, author=author, kdc=kdc,
            themes=themes, introduction=introduction, summary=summary,
        )
    except Exception as e:
        log.warning(f"[{book_id}] 표지 프롬프트 생성 실패: {e}")
        return None, None

    if not prompt:
        log.warning(f"[{book_id}] 표지 프롬프트 비어있음")
        return None, None

    # LoRA 트리거 워드 주입 (EBook-Creative-Cover-Flux-LoRA: "BOOK")
    # FLUX_LORA_ID 가 설정된 경우에만 적용
    import os
    if os.environ.get("FLUX_LORA_ID", ""):
        trigger = os.environ.get("FLUX_LORA_TRIGGER", "BOOK")
        if trigger and not prompt.upper().startswith(trigger.upper()):
            prompt = f"{trigger}, {prompt}"

    log.info(f"[{book_id}] 표지 프롬프트: {prompt[:120]}...")

    try:
        img_bytes = await render_cover_image(prompt)
    except Exception as e:
        log.warning(f"[{book_id}] FLUX 이미지 생성 실패: {e}")
        return None, prompt

    if not img_bytes:
        return None, prompt

    try:
        key = upload_cover_to_minio(book_id, img_bytes, minio_client)
        log.info(f"[{book_id}] 표지 MinIO 업로드 완료 → {key} ({len(img_bytes)/1024:.1f}KB)")
        return key, prompt
    except Exception as e:
        log.warning(f"[{book_id}] 표지 MinIO 업로드 실패: {e}")
        return None, prompt
