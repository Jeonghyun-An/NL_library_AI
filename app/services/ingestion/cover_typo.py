"""
정책 보고서의 '목업 표지' — 그림을 생성하지 않고 제목·발행처·연도를 조판한 표지(JPEG)를 그린다.

2026-10-23 사용자 결정: 정책 보고서는 목업 표지, 문학·도서는 그림 표지(cover_art — 실사풍). 블라인드 평가(대표·사서·위험 세 관점,
v8·v9 두 차례)에서 보고서 그림은 판마다 '제목과 상관없다'(예산편성지침에 서버실, 기금운용계획에 공장)가 되풀이됐다 —
보고서 제목에는 그릴 대상이 없다. 실제 백서·연감처럼 제목을 조판하면 주제가 바로 읽히고 가짜 간판 글자·서양풍 인물 위험이 없다
(후배 제안 — 고대구로병원 브로셔풍 단색 표지).
정책 보고서도 그림 표지를 함께 만들어 두고(cover_generator.POLICY_COVER 가 어느 쪽을 보일지 정한다) 다시 그리지 않고 바꿀 수 있다.

색은 자료 id 해시로 8가지 중 하나, 판형은 셋(위 색 띠 band · 전면 색 classic · 연도 크게 year — 제목에 연도가 하나뿐일 때만).
같은 자료는 늘 같은 표지다. 글꼴은 Pretendard(화면과 같은 글꼴, SIL OFL — app/assets/fonts/OFL.txt)를 함께 싣는다.
Pretendard 에는 한자가 없어(리뷰 지적 2026-10-23 — '2006年度 基金現況' 이 네모 상자로 찍혔다) 제목·발행처에 Pretendard 에 없는
글자가 있으면 그 표지 전체를 한자가 있는 CJK 글꼴(운영 이미지의 Noto Sans CJK KR)로 그린다. 그 글꼴도 없으면 그리지 않는다
(MissingGlyphs — 호출 쪽이 그림 표지로 넘어간다).
"""
from __future__ import annotations

import hashlib
import io
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
# Pretendard 에 없는 글자(한자 등)를 그릴 글꼴 후보 — 운영 이미지(fonts-noto-cjk), 그다음 로컬 Windows(테스트)
FALLBACK_FONTS: list[str] = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/malgunbd.ttf",
]
W, H = 768, 1152          # 그림 표지(FLUX_WIDTH·FLUX_HEIGHT)와 같은 판
MARGIN = 84
PALETTES: list[tuple[str, str, str]] = [  # (바탕, 글자, 강조)
    ("#7B1531", "#FFFFFF", "#E9B9C4"),
    ("#13294B", "#FFFFFF", "#9DB7E0"),
    ("#1E4636", "#FFFFFF", "#A9CDB8"),
    ("#2A2D31", "#FFFFFF", "#C9B27C"),
    ("#0F5257", "#FFFFFF", "#9BD0CF"),
    ("#8C5A16", "#FFFFFF", "#F1D39B"),
    ("#3B4A63", "#FFFFFF", "#C3CEE0"),
    ("#4A2445", "#FFFFFF", "#D9B4D2"),
]
PAPER = "#F3EFE6"          # band 판형의 아래 종이색
BAND = 0.56                # band 판형의 색 띠 높이(판 높이 비율)
# 연도 — 다른 숫자에 붙은 것('120000')·금액·수량('2000억')은 빼고, 뒤에 붙은 '년도·년'까지 한 덩어리
_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)(?!\s*(?:억|만|천|원|달러|명|개|호|%))\s*(?:년도|년)?")
# 기간·회계연도('2006~2010', '2003/04') — 연도를 하나만 크게 찍으면 나머지가 '~ 계획'·'/04' 로 깨진다
_YEAR_SPAN = re.compile(r"(?<!\d)(?:19|20)\d{2}\s*[~\-–—/]\s*\d")
_NOTDEF = "\uffff"         # 어느 글꼴에도 없는 글자 — 이것과 똑같이 그려지면 글꼴에 없는 글자(.notdef 상자)다


class MissingGlyphs(ValueError):
    """제목·발행처에 그릴 글꼴이 없는 글자가 있다 — 목업을 만들지 않는다."""


@lru_cache(maxsize=4)
def _fallback_spec() -> tuple[str, int] | None:
    """한자가 있는 대체 글꼴 (경로, ttc 안 번호) — 모음 글꼴(.ttc)은 한국어 판(이름이 KR 로 끝나는 것)을 고른다."""
    for path in FALLBACK_FONTS:
        if not Path(path).is_file():
            continue
        if not path.lower().endswith(".ttc"):
            return path, 0
        for index in range(16):
            try:
                family = ImageFont.truetype(path, 20, index=index).getname()[0] or ""
            except OSError:
                break
            if family.endswith(" KR"):
                return path, index
    return None


@lru_cache(maxsize=128)
def _font(weight: str, size: int, family: str = "pretendard") -> ImageFont.FreeTypeFont:
    if family == "pretendard":
        return ImageFont.truetype(str(FONT_DIR / f"Pretendard-{weight}.otf"), size)
    spec = _fallback_spec()
    if spec is None:
        raise MissingGlyphs("한자가 있는 대체 글꼴이 없다")
    return ImageFont.truetype(spec[0], size, index=spec[1])   # 대체 글꼴은 굵은 한 벌로 모든 굵기를 쓴다


@lru_cache(maxsize=8192)
def _glyph(family: str, ch: str) -> bytes:
    font = _font("ExtraBold", 40, family)
    im = Image.new("L", (80, 80), 0)
    ImageDraw.Draw(im).text((10, 10), ch, font=font, fill=255)
    return im.tobytes()


def missing_chars(text: str, family: str = "pretendard") -> set[str]:
    """그 글꼴에 없는 글자들(공백 빼고)."""
    notdef = _glyph(family, _NOTDEF)
    return {ch for ch in set(text or "") if not ch.isspace() and _glyph(family, ch) == notdef}


def family_for(text: str) -> str:
    """제목·발행처를 그릴 글꼴 — Pretendard 에 없는 글자가 있으면 대체 글꼴, 그것으로도 안 되면 MissingGlyphs."""
    if not missing_chars(text):
        return "pretendard"
    if _fallback_spec() is None:
        raise MissingGlyphs(f"Pretendard 에 없는 글자({''.join(sorted(missing_chars(text)))})를 그릴 대체 글꼴이 없다")
    still = missing_chars(text, "fallback")
    if still:
        raise MissingGlyphs(f"대체 글꼴에도 없는 글자: {''.join(sorted(still))}")
    return "fallback"


def _pick(book_id: str, salt: str, n: int) -> int:
    return int(hashlib.sha1(f"{salt}:{book_id}".encode()).hexdigest(), 16) % n


def split_title(title: str) -> tuple[str, str]:
    """'(부제)본제' → (본제, 부제). 괄호로 시작하지 않으면 부제는 빈 문자열."""
    t = (title or "").strip()
    m = re.match(r"^\((.+?)\)\s*(.+)$", t)
    return (m.group(2).strip(), m.group(1).strip()) if m else (t, "")


def single_year(title: str) -> str | None:
    """크게 찍을 연도 — 제목에 연도가 꼭 하나이고 기간·회계연도 꼴이 아닐 때만."""
    years = _YEAR.findall(title or "")
    if len(years) != 1 or _YEAR_SPAN.search(title or ""):
        return None
    return years[0].strip()[:4]


def layout_of(book_id: str, title: str) -> str:
    """판형 — 연도가 하나뿐인 제목만 year 판형을 쓸 수 있다."""
    layouts = ["classic", "band"] + (["year"] if single_year(title) else [])
    return layouts[_pick(book_id, "layout", len(layouts))]


def palette_of(book_id: str) -> tuple[str, str, str]:
    return PALETTES[_pick(book_id, "palette", len(PALETTES))]


def _pieces(text: str) -> list[tuple[str, bool]]:
    """줄을 끊을 수 있는 조각들 (조각, 앞 조각에 붙여 쓰나) — 낱말 사이와, 붙여 쓴 '재정운영·공공개혁' 의 '·' 뒤."""
    out: list[tuple[str, bool]] = []
    for word in (text or "").split():
        out += [(part, k > 0) for k, part in enumerate(re.split(r"(?<=·)(?=\S)", word))]
    return out


def wrap(text: str, font, width: int) -> tuple[list[str], bool]:
    """조각 단위로 줄을 나눈다(_pieces). 한 조각이 폭보다 길면 글자 단위로 자른다 — (줄들, 낱말을 잘랐나)."""
    lines: list[str] = []
    cur, broke = "", False
    for word, glued in _pieces(text):
        trial = (cur + ("" if glued else " ") + word) if cur else word
        if font.getlength(trial) <= width:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = ""
        broke = broke or font.getlength(word) > width
        for ch in word:
            if font.getlength(cur + ch) > width:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
    if cur:
        lines.append(cur)
    return lines, broke


def fit(text: str, weight: str, width: int, start: int, max_lines: int, floor: int = 40, family: str = "pretendard"):
    """줄 수 안에 들고 낱말이 잘리지 않는 가장 큰 크기 → (글꼴, 줄들). 없으면 줄 수만 맞는 크기, 그것도 없으면 floor."""
    fallback = None
    for size in range(start, floor - 1, -4):
        font = _font(weight, size, family)
        lines, broke = wrap(text, font, width)
        if len(lines) <= max_lines:
            if not broke:
                return font, lines
            fallback = fallback or (font, lines)
    if fallback:
        return fallback
    font = _font(weight, floor, family)
    return font, wrap(text, font, width)[0]


def _draw_lines(d: ImageDraw.ImageDraw, lines: list[str], font, x: int, y: int, fill: str, gap: float = 1.18) -> int:
    for line in lines:
        d.text((x, y), line, font=font, fill=fill)
        y += int(font.size * gap)
    return y


def _spine(img: Image.Image) -> Image.Image:
    """왼쪽 책등 그늘과 접힌 자리의 밝은 선 — 제본된 책처럼 보이게."""
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    for x in range(30):
        d.line([(x, 0), (x, H)], fill=(0, 0, 0, int(70 * (1 - x / 30))))
    d.line([(31, 0), (31, H)], fill=(255, 255, 255, 40))
    return Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")


def render_typo_cover(book_id: str, title: str, publisher: str = "") -> bytes:
    """목업 표지 JPEG 바이트. 같은 (id, 제목, 발행처)면 늘 같은 그림이다. 그릴 글꼴이 없는 글자가 있으면 MissingGlyphs."""
    publisher = "" if publisher in (None, "None") else publisher.strip()
    title = title or book_id
    family = family_for(title + publisher)
    main, sub = split_title(title)
    bg, fg, accent = palette_of(book_id)
    layout = layout_of(book_id, title)
    width = W - 2 * MARGIN

    def font(weight: str, size: int):
        return _font(weight, size, family)

    if layout == "band":
        img = Image.new("RGB", (W, H), PAPER)
        d = ImageDraw.Draw(img)
        band = int(H * BAND)
        d.rectangle([0, 0, W, band], fill=bg)
        tf, lines = fit(main, "ExtraBold", width, 84, 4, family=family)
        _draw_lines(d, lines, tf, MARGIN, band - MARGIN - int(tf.size * 1.18) * len(lines), fg)
        if publisher:
            d.text((MARGIN, MARGIN), publisher, font=font("SemiBold", 24), fill=accent)
            d.text((MARGIN, H - MARGIN - 30), publisher, font=font("SemiBold", 28), fill=bg)
        if sub:
            sf, sl = fit(sub, "SemiBold", width, 34, 3, 26, family=family)
            _draw_lines(d, sl, sf, MARGIN, band + 48, bg, 1.35)
    else:
        img = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(img)
        text, y = main, 170
        if layout == "year":
            d.text((MARGIN - 8, 120), single_year(title), font=font("Black", 210), fill=accent)
            y = 370
            # 크게 찍은 연도 하나만 본제에서 뺀다(기간·두 해 제목은 year 판형에 오지 않는다 — single_year)
            text = _YEAR.sub(" ", main, count=1).strip() or main
        elif publisher:
            d.text((W - MARGIN, MARGIN), publisher, font=font("SemiBold", 22), fill=accent, anchor="ra")
        tf, lines = fit(text, "ExtraBold", width, 92 if layout == "classic" else 76, 5, family=family)
        y = _draw_lines(d, lines, tf, MARGIN, y, fg)
        d.line([(MARGIN, y + 26), (MARGIN + 120, y + 26)], fill=accent, width=4)
        if sub:
            sf, sl = fit(sub, "SemiBold", width, 34, 3, 26, family=family)
            _draw_lines(d, sl, sf, MARGIN, y + 58, accent, 1.35)
        if publisher:
            pf = font("SemiBold", 26)
            if layout == "year":
                d.line([(MARGIN, H - MARGIN - 56), (W - MARGIN, H - MARGIN - 56)], fill=accent, width=1)
                d.text((MARGIN, H - MARGIN - 30), publisher, font=pf, fill=fg)
            else:
                d.text((W // 2, H - MARGIN), publisher, font=pf, fill=fg, anchor="ms")

    buf = io.BytesIO()
    _spine(img).save(buf, format="JPEG", quality=92)
    return buf.getvalue()
