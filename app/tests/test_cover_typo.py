"""정책 보고서 목업 표지(cover_typo) — 제목·발행처를 조판한 표지. 2026-10-23 사용자 결정: 보고서는 목업, 문학·도서는 그림."""
import io

import pytest
from PIL import Image

from services.ingestion import cover_typo


def test_bundled_fonts_and_license_ship_with_the_app():
    for weight in ("Black", "ExtraBold", "SemiBold"):
        assert (cover_typo.FONT_DIR / f"Pretendard-{weight}.otf").is_file()
    assert (cover_typo.FONT_DIR / "OFL.txt").is_file()


@pytest.mark.parametrize("title, want", [
    ("(참여정부 100일)기획예산처의 역할과 성과", ("기획예산처의 역할과 성과", "참여정부 100일")),
    ("(2006년 지역별 경제전망과 한국의 대외경제정책 방향)EU", ("EU", "2006년 지역별 경제전망과 한국의 대외경제정책 방향")),
    ("2005 나라살림", ("2005 나라살림", "")),
    ("  ", ("", "")),
])
def test_split_title(title, want):
    assert cover_typo.split_title(title) == want


def test_fit_avoids_breaking_words_when_a_smaller_size_fits():
    font, lines = cover_typo.fit("(경제위기 이후 5년간의)재정운영·공공개혁 성과와 과제", "ExtraBold", 600, 92, 5)
    _, broke = cover_typo.wrap(" ".join(lines), font, 600)
    assert not broke and all(font.getlength(line) <= 600 for line in lines)
    # '·' 뒤는 끊을 자리 — 붙여 쓴 복합어도 낱말을 자르지 않고 나눈다
    _, lines = cover_typo.fit("재정운영·공공개혁 성과와 과제", "ExtraBold", 420, 92, 5)
    assert any(line.endswith("·") for line in lines) or len(lines) == 1


def test_layout_and_palette_are_stable_per_id_and_year_layout_needs_a_year():
    assert cover_typo.layout_of("CNTS-1", "2005 나라살림") == cover_typo.layout_of("CNTS-1", "2005 나라살림")
    no_year = {cover_typo.layout_of(f"C{n}", "개혁과 도약의 길") for n in range(200)}
    assert no_year == {"classic", "band"}
    with_year = {cover_typo.layout_of(f"C{n}", "2003년 기금운용계획") for n in range(200)}
    assert with_year == {"classic", "band", "year"}
    assert len({cover_typo.palette_of(f"C{n}") for n in range(200)}) == len(cover_typo.PALETTES)


@pytest.mark.parametrize("cid, title, publisher", [
    ("CNTS-00049655725", "2003년 기금운용계획 이렇게 만들었습니다", "기획예산처"),
    ("CNTS-00049655631", "(참여정부 100일)기획예산처의 역할과 성과", "기획예산처"),
    ("CNTS-00049662543", "2004 재난연감", "None"),
    ("CNTS-X", "", ""),
])
def test_render_gives_a_cover_sized_jpeg_and_is_deterministic(cid, title, publisher):
    data = cover_typo.render_typo_cover(cid, title, publisher)
    img = Image.open(io.BytesIO(data))
    assert img.format == "JPEG" and img.size == (cover_typo.W, cover_typo.H)
    assert data == cover_typo.render_typo_cover(cid, title, publisher)


def test_every_layout_renders():
    seen = set()
    for n in range(60):
        cid = f"L{n}"
        layout = cover_typo.layout_of(cid, "2003년도 예산배정계획 및 자금계획")
        if layout not in seen:
            seen.add(layout)
            assert cover_typo.render_typo_cover(cid, "2003년도 예산배정계획 및 자금계획", "기획예산처")
    assert seen == {"classic", "band", "year"}
