"""marc_parser.py — 호환 shim. 구현은 domains/nl_library/loaders/marc_parser.py 로 이동."""
from domains.nl_library.loaders.marc_parser import (  # noqa: F401
    parse,
    _parse_pymarc,
    _parse_marc_direct,
    _parse_regex,
    _restore_control_chars,
)
