"""핑크 테마용 스피너 160×160 만들기 (1회성 — 결과는 frontend/public/ 에 들어 있다).

핑크(라이트) 테마에서 기본 스피너(skovix-spinner-clean-160.gif)가 거무튀튀해 보였다(사용자 2026-10-26). 원인은 둘이다.
  ① GIF 는 알파가 1비트라 가장자리를 0.5 로 끊는다 — 어두운 바탕에서는 티가 안 나지만 밝은 분홍 위에서는 계단진 회색 테두리로 보인다.
  ② 원본 색이 아주 옅은 살구색(평균 #f7d9d2)이라 분홍 바탕과 대비가 없어 흐릿하다.
그래서 핑크 테마만 따로 만든다.
  - 알파를 그대로 두는 애니메이션 WebP(가장자리가 매끈하다). 축소는 make_160.py 와 같이 알파를 곱한 색으로 한다.
  - 색은 밝기를 핑크 테마의 자두색(#7a3f5c, --skx-teal-ink) → 장밋빛(#de96af) 그라데이션에 옮긴다 — 음영은 그대로 남는다.
    살구·산호 쪽은 피했다(핑크 테마에서 웜톤이 튄다는 사용자 지적 2026-10-26).
  - 완료 로고(skovix-spinner-front.png)도 같은 색으로 바꾼 PNG.

실행: python make_pink.py <원본 폴더> <출력 폴더>
  원본: skovix-spinner-transparent.gif(800px·96프레임) · skovix-spinner-front.png(800px) — 메인 폴더 frontend/public/ 의 untracked 파일
  출력: skovix-spinner-pink-160.webp · skovix-spinner-front-pink-160.png
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SIZE = 160
DARK = (122, 63, 92)  # #7a3f5c
LIGHT = (222, 150, 175)  # #de96af
# 원본 밝기 범위(불투명 픽셀 R 191~254) — 이 구간을 그라데이션 양 끝에 맞춘다
LUM_LO, LUM_HI = 0.78, 0.99


def shrink(frame: Image.Image) -> np.ndarray:
    """RGBA 한 장을 160px 로 — 알파를 곱한 색으로 줄여 가장자리 색 번짐을 막고, 알파는 끊지 않는다."""
    a = np.asarray(frame.convert("RGBA")).astype(np.float32) / 255
    premult = np.concatenate([a[..., :3] * a[..., 3:4], a[..., 3:4]], -1)
    small = Image.fromarray((premult * 255 + 0.5).astype(np.uint8), "RGBA").resize((SIZE, SIZE), Image.LANCZOS)
    s = np.asarray(small).astype(np.float32) / 255
    alpha = s[..., 3:4]
    color = np.where(alpha > 0, s[..., :3] / np.maximum(alpha, 1e-6), 0)
    return np.clip(np.concatenate([color, alpha], -1), 0, 1)


def recolor(arr: np.ndarray) -> Image.Image:
    lum = arr[..., 0] * 0.3 + arr[..., 1] * 0.59 + arr[..., 2] * 0.11
    t = np.clip((lum - LUM_LO) / (LUM_HI - LUM_LO), 0, 1)[..., None]
    color = np.array(DARK) / 255 * (1 - t) + np.array(LIGHT) / 255 * t
    out = np.concatenate([color, arr[..., 3:4]], -1)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


def main(src_dir: Path, out_dir: Path) -> None:
    im = Image.open(src_dir / "skovix-spinner-transparent.gif")
    frames: list[Image.Image] = []
    durations: list[int] = []
    for i in range(im.n_frames):
        im.seek(i)
        durations.append(int(im.info.get("duration", 40)))
        frames.append(recolor(shrink(im.copy())))
    frames[0].save(
        out_dir / "skovix-spinner-pink-160.webp",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        quality=90,
        method=6,
        lossless=False,
    )
    front = Image.open(src_dir / "skovix-spinner-front.png")
    recolor(shrink(front)).save(out_dir / "skovix-spinner-front-pink-160.png", optimize=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
