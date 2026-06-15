"""파서 플러그인 (CatalogLoader) + core/extra 분류 테스트."""
from pathlib import Path

import pytest
from openpyxl import Workbook

from domains.base import ParsedRecord, split_core_extra


# ── core/extra 분류 ──────────────────────────────────────────
def test_split_core_extra():
    parsed = {
        "title": "테스트",
        "personal_author": "홍길동",
        "kdc": "800",
        "isbn": "1234",
        "grade": "KCI등재",
        "publisher": None,        # None은 버림
    }
    core, extra = split_core_extra(parsed)
    assert core == {"title": "테스트", "personal_author": "홍길동"}
    assert extra == {"kdc": "800", "isbn": "1234", "grade": "KCI등재"}


# ── KCI 로더 ─────────────────────────────────────────────────
@pytest.fixture
def kci_xlsx(tmp_path: Path) -> str:
    wb = Workbook()
    ws = wb.active
    ws.append(["KCI_FI_ID", "ARTI_ID", "GRADE", "TITLE_KR", "TITLE_EN",
               "AUTHORS", "INSTITUTION", "JOURNAL", "VOL_ISSUE", "PAGES",
               "YEAR_MONTH", "KCI_CITATIONS", "WOS_CITATIONS"])
    ws.append(["KCI_FI001", "ART001", "KCI등재", "한국어 제목", "English Title",
               "김저자", "한국대학교", "한국학술지", "20(2)", "1-15",
               "202403", "5", "2"])
    path = tmp_path / "kci.xlsx"
    wb.save(path)
    return str(path)


def test_kci_loader_detect_and_load(kci_xlsx):
    from domains.nl_library.loaders.kci_xlsx import KciXlsxLoader

    loader = KciXlsxLoader()
    assert loader.detect(kci_xlsx, ["KCI_FI_ID", "TITLE_KR"]) is True
    assert loader.detect(kci_xlsx, ["CONTENTS_ID", "MARC"]) is False

    records = list(loader.load(kci_xlsx))
    assert len(records) == 1
    rec = records[0]
    assert isinstance(rec, ParsedRecord)
    assert rec.source_id == "KCI_FI001"
    assert rec.source_format == "KCI"
    assert rec.core["title"] == "한국어 제목"
    assert rec.core["pub_date"] == "202403"
    assert rec.core["personal_author"] == "김저자"
    assert rec.core["genre"] == "paper"
    # 레거시 컬럼 오버로딩 보존 (동작 불변)
    assert rec.core["title_remainder"] == "English Title"
    assert rec.extra["series_title"] == "한국학술지"
    # 본래 의미 이름으로도 extra에 기록
    assert rec.extra["title_en"] == "English Title"
    assert rec.extra["journal"] == "한국학술지"
    assert rec.extra["pages"] == "1-15"
    assert rec.extra["kci_citations"] == 5


# ── MARC/MODS 로더 ───────────────────────────────────────────
@pytest.fixture
def marc_mods_xlsx(tmp_path: Path) -> str:
    wb = Workbook()
    ws = wb.active
    ws.append(["CONTENTS_ID", "TITLE_INFO", "MARC", "MODS"])
    ws.append(["CNTS-001", "제목만 있는 도서", "", ""])   # MARC/MODS 없음 → title만
    path = tmp_path / "catalog.xlsx"
    wb.save(path)
    return str(path)


def test_marc_mods_loader_detect_and_load(marc_mods_xlsx):
    from domains.nl_library.loaders.marc_mods_xlsx import MarcModsXlsxLoader

    loader = MarcModsXlsxLoader()
    assert loader.detect(marc_mods_xlsx, ["CONTENTS_ID", "MARC", "MODS"]) is True
    assert loader.detect(marc_mods_xlsx, ["KCI_FI_ID"]) is False

    records = list(loader.load(marc_mods_xlsx))
    assert len(records) == 1
    rec = records[0]
    assert rec.source_id == "CNTS-001"
    assert rec.core["title"] == "제목만 있는 도서"
    assert rec.source_format == "NONE"


# ── 프로파일 로더 레지스트리 + 자동 판별 ─────────────────────
def test_profile_loaders_and_autodetect(kci_xlsx):
    from domains import get_active_profile
    from domains.nl_library.loaders import resolve_loader

    profile = get_active_profile()
    ids = [ld.loader_id for ld in profile.loaders]
    assert "nl_marc_mods_xlsx" in ids
    assert "kci_xlsx" in ids

    loader = resolve_loader(kci_xlsx)
    assert loader is not None
    assert loader.loader_id == "kci_xlsx"


# ── 이동된 파서의 기존 임포트 경로 호환 (shim) ────────────────
def test_legacy_parser_import_paths_still_work():
    from services.ingestion.marc_parser import parse as parse_marc  # noqa: F401
    from services.ingestion.mods_parser import parse as parse_mods  # noqa: F401
    from services.ingestion.kci_loader import load_kci_xlsx  # noqa: F401
    from services.ingestion.xlsx_loader import load_xlsx  # noqa: F401
