"""xlsx_loader.py — 호환 shim. 구현은 domains/nl_library/loaders/marc_mods_xlsx.py 로 이동."""
from domains.nl_library.loaders.marc_mods_xlsx import (  # noqa: F401
    _read_rows,
    load_xlsx,
)
