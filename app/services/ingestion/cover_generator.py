"""
도서 표지 자동 생성 모듈.

흐름:
  ① 사진 종류·색 보정·구도는 코드가 자료 id 로 고른다(cover_art.art_direction — 실사풍)
  ② LLM 은 '카메라가 무엇을 찍는지' 한 문장만 쓴다(cover_scene). 장면에 금지어가 있으면 걸린 말을 알려 다시 쓰게 하고(두 번까지),
     그래도 남은 문학 아닌 자료는 표지를 만들지 않는다(재난 자료의 배·물에 뜬 물건 같은 아픈 그림을 내보내지 않는다)
  ③ 코드가 '사진 종류: 장면 구도 색 보정. 글자 없는 장면' 한 줄로 조립해 FLUX.1-dev 서버에 보내 표지 이미지(JPEG) 생성
  ④ MinIO 업로드 후 key 반환
2026-10-23 전에는 LLM 이 화풍까지 한 번에 썼다 — 재정 보고서 표지가 톱니·도시·빛줄기로 모였다(cover_art 머리말)

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
async def _ask(name: str, timeout: float, **vars) -> str:
    """프롬프트 하나로 LLM 에 한 번 묻고 장면 한 문장으로 다듬는다(cover_art.clean_scene)."""
    from services.ingestion.cover_art import clean_scene
    from services.llm_client import chat
    from services.prompts import get_prompt

    system, user, params = get_prompt(name).render(**vars)
    text = await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        params=params,
        timeout=timeout,
    )
    return clean_scene(text or "")


# 표지 한 장에 LLM 을 부르는 최대 횟수 — 장면 → (금지어면) 다시 → (그래도면) 한 번 더.
# 적재 마무리의 시간 예산(stages._reduce_budget_seconds)이 이만큼을 표지 몫으로 남긴다
COVER_PROMPT_MAX_CALLS = 3


async def compose_cover(
    title: str,
    author: str,
    kdc: str,
    themes: str,
    introduction: str,
    summary: str,
    *,
    book_id: str = "",
    doc_type: str | None = "book",
    avoid: list[str] | None = None,
) -> tuple[str, str] | None:
    """자료 메타로 (FLUX 프롬프트 한 줄, 장면 한 문장)을 만든다 — 아트 디렉션은 코드, 장면은 LLM. 못 만들면 None.

    avoid 는 같은 묶음에서 방금 쓴 장면 핵심어(다시 만들기 스크립트가 넘긴다 — 되풀이를 막는다). 장면을 따로 돌려주는 것은
    스크립트가 다음 표지의 avoid 를 장면에서 뽑게 하려고다(사진 종류 문구에 ': ' 가 있을 수 있어 완성 줄에서 장면을 잘라 내지 않는다).
    다시 쓰기 호출이 실패하면 그 앞 장면으로 판단을 이어 간다 — 첫 장면이 멀쩡하면 버리지 않는다.
    """
    from services.ingestion import cover_art

    cfg = get_settings()
    timeout = cfg.COVER_PROMPT_TIMEOUT
    ad = cover_art.art_direction(book_id or title or "", doc_type, title or "", themes or "", summary or "")
    scene_vars = dict(doc_type=doc_type or "", title=title or "Untitled", author=author or "Unknown", kdc=kdc or "N/A",
                      themes=themes or "N/A", summary=(summary or introduction or "")[:1500],
                      scale=cover_art.SCALE_TEXT[ad.scale], avoid=", ".join((avoid or [])[-12:]))
    scene = await _ask("cover_scene", timeout, **scene_vars, retry_from="", retry_hits="")
    hits = cover_art.banned_terms(scene, title or "")
    for _ in range(COVER_PROMPT_MAX_CALLS - 1):
        if not (scene and hits):
            break
        try:
            again = await _ask("cover_scene", timeout, **scene_vars, retry_from=scene, retry_hits=", ".join(hits))
        except Exception as e:  # 다시 쓰기가 실패하면 앞 장면으로 판단을 이어 간다
            log.warning(f"[{book_id}] 표지 장면 다시 쓰기 실패: {e}")
            break
        again_hits = cover_art.banned_terms(again, title or "")
        if again and len(again_hits) <= len(hits):
            scene, hits = again, again_hits
    if scene and hits:
        log.warning(f"[{book_id}] 표지 장면에 금지어가 남았다: {hits} — {scene[:120]}")
        # 문학이 아니면(정책 보고서·일반 도서) 표지를 만들지 않는다 — 글자가 생기는 사물·재난의 아픈 그림을 내보내지 않는다
        # (다시 만들기 스크립트는 그 자료의 옛 표지를 그대로 두고 기록에 남긴다). 문학은 장면을 그대로 둔다
        if ad.genre == "policy":
            return None
    if not scene:
        return None
    return cover_art.assemble(ad, scene), scene


async def generate_cover_prompt(
    title: str,
    author: str,
    kdc: str,
    themes: str,
    introduction: str,
    summary: str,
    *,
    book_id: str = "",
    doc_type: str | None = "book",
    avoid: list[str] | None = None,
) -> str | None:
    """자료 메타로 FLUX 영문 프롬프트 한 줄 — compose_cover 의 프롬프트만. 못 만들면 None."""
    made = await compose_cover(title, author, kdc, themes, introduction, summary,
                               book_id=book_id, doc_type=doc_type, avoid=avoid)
    return made[0] if made else None


# 표지가 "정책보고서"처럼 사실적/건조하게 나오는 걸 막기 위한 기본 negative prompt.
# cover_prompt.yaml이 일러스트 계열 스타일을 유도해도 FLUX 자체는 사실적 렌더링 쪽으로
# 치우치는 경향이 있어, 서버가 받아주는 negative_prompt로 보정한다.
DEFAULT_NEGATIVE_PROMPT = (
    "photorealistic, photograph, stock photo, documentary photo, "
    "corporate report, bureaucratic, PowerPoint, infographic, slide deck, "
    "office scene, conference room, plain portrait, text, watermark, logo, "
    "low quality, blurry"
)


# ── FLUX 이미지 생성 ────────────────────────────────────────
async def render_cover_image(
    prompt: str,
    negative_prompt: str | None = None,
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    guidance: float | None = None,
    seed: int | None = None,
) -> bytes | None:
    """FLUX 서버에 프롬프트 전송 → 표지 JPEG 바이트 반환. 미지정 시 env 기본값."""
    cfg = get_settings()
    body = {
        "prompt": prompt,
        "negative_prompt": negative_prompt if negative_prompt is not None else DEFAULT_NEGATIVE_PROMPT,
        "width":  width if width is not None else cfg.FLUX_WIDTH,
        "height": height if height is not None else cfg.FLUX_HEIGHT,
        "num_inference_steps": steps if steps is not None else cfg.FLUX_STEPS,
        "guidance_scale": guidance if guidance is not None else cfg.FLUX_GUIDANCE,
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
    doc_type: str | None = "book",
    avoid: list[str] | None = None,
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
            book_id=book_id, doc_type=doc_type, avoid=avoid,
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
