"""스피너 축소본 160×160 만들기 (1회성 — 결과는 frontend/public/ 에 들어 있다).

원본(메인 폴더 frontend/public/ 의 untracked 파일, 저장소에는 올리지 않는다) → 160px 축소본:
  skovix-spinner-transparent.gif (800px·96프레임, 가는 선 '깔끔')  → skovix-spinner-clean-160.gif
  skovix-ai-loading.gif          (512px·80프레임, 두꺼운 음영 '뚱뚱 입체') → skovix-spinner-bold-160.gif
  skovix-spinner-front.png       (800px, 완료 로고)               → skovix-spinner-front-160.png

원본의 프레임 시간·반복(무한)·투명 배경을 그대로 둔다. GIF 는 알파가 1비트라 축소 때 가장자리가 계단져 보이거나
검은 테두리가 생기기 쉽다 — 그래서 ① 알파를 곱한(premultiplied) 색으로 줄여 투명 쪽 색이 번지지 않게 하고
② 줄인 알파를 0.5 로 끊고 ③ 모든 프레임이 같은 전체 팔레트(색 255개 + 투명 1개)를 쓰게 한다(프레임 사이 색 깜빡임 방지).

실행: python make_160.py <원본 폴더> <출력 폴더>
"""
import sys
from pathlib import Path

from PIL import Image

SIZE = 160
TRANSPARENT_INDEX = 255

JOBS = [
    ("skovix-spinner-transparent.gif", "skovix-spinner-clean-160.gif"),
    ("skovix-ai-loading.gif", "skovix-spinner-bold-160.gif"),
]


def shrink_rgba(frame: Image.Image) -> Image.Image:
    """RGBA 한 장을 160px 로 — 알파를 곱한 색으로 줄여 가장자리 색 번짐을 막는다."""
    rgba = frame.convert("RGBA")
    alpha = rgba.getchannel("A")
    premult = Image.merge(
        "RGBA",
        [
            Image.composite(ch, Image.new("L", rgba.size, 0), alpha)
            for ch in rgba.split()[:3]
        ]
        + [alpha],
    )
    small = premult.resize((SIZE, SIZE), Image.LANCZOS)
    r, g, b, a = small.split()
    # 곱해진 색을 되돌린다(알파가 0 이 아닌 곳만)
    px = small.load()
    out = Image.new("RGBA", small.size)
    ox = out.load()
    for y in range(SIZE):
        for x in range(SIZE):
            pr, pg, pb, pa = px[x, y]
            if pa == 0:
                ox[x, y] = (0, 0, 0, 0)
            else:
                k = 255.0 / pa
                ox[x, y] = (min(255, int(pr * k + 0.5)), min(255, int(pg * k + 0.5)), min(255, int(pb * k + 0.5)), pa)
    return out


def make_gif(src: Path, dst: Path) -> None:
    im = Image.open(src)
    frames: list[Image.Image] = []
    durations: list[int] = []
    for i in range(im.n_frames):
        im.seek(i)
        durations.append(int(im.info.get("duration", 40)))
        frames.append(shrink_rgba(im.copy()))

    # 전체 팔레트 — 불투명 픽셀만 모아 만든 견본에서 색 255개를 뽑는다
    sample = Image.new("RGB", (SIZE * 8, SIZE * 1))
    step = max(1, len(frames) // 8)
    for n, fr in enumerate(frames[::step][:8]):
        rgb = Image.new("RGB", fr.size, (0, 0, 0))
        rgb.paste(fr.convert("RGB"), mask=fr.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
        sample.paste(rgb, (n * SIZE, 0))
    palette_img = sample.quantize(colors=TRANSPARENT_INDEX, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)

    out: list[Image.Image] = []
    for fr in frames:
        mask = fr.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
        rgb = Image.new("RGB", fr.size, (0, 0, 0))
        rgb.paste(fr.convert("RGB"), mask=mask)
        p = rgb.quantize(palette=palette_img, dither=Image.Dither.NONE)
        # 투명 칸은 마지막 색 번호로 — 팔레트에서 그 번호는 쓰이지 않는다(위에서 255 색만 뽑았다)
        inv = mask.point(lambda v: 255 if v == 0 else 0)
        p.paste(TRANSPARENT_INDEX, mask=inv)
        out.append(p)

    out[0].save(
        dst,
        save_all=True,
        append_images=out[1:],
        duration=durations,
        loop=0,
        disposal=2,
        transparency=TRANSPARENT_INDEX,
        optimize=False,
    )


def make_png(src: Path, dst: Path) -> None:
    shrink_rgba(Image.open(src)).save(dst, optimize=True)


def main(src_dir: str, dst_dir: str) -> None:
    s, d = Path(src_dir), Path(dst_dir)
    for a, b in JOBS:
        make_gif(s / a, d / b)
        print(f"{a} {(s / a).stat().st_size:,} B -> {b} {(d / b).stat().st_size:,} B")
    make_png(s / "skovix-spinner-front.png", d / "skovix-spinner-front-160.png")
    print(f"skovix-spinner-front.png {(s / 'skovix-spinner-front.png').stat().st_size:,} B -> skovix-spinner-front-160.png {(d / 'skovix-spinner-front-160.png').stat().st_size:,} B")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
