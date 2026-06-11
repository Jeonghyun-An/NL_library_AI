"""kci_loader.py — 호환 shim. 구현은 domains/nl_library/loaders/kci_xlsx.py 로 이동."""
from domains.nl_library.loaders.kci_xlsx import load_kci_xlsx as _load_kci_xlsx  # noqa: F401


def load_kci_xlsx(file_path: str) -> list[dict]:
    """레거시 API — 내부 dual-write용 _true_names 키는 제거하고 반환."""
    records = _load_kci_xlsx(file_path)
    for rec in records:
        rec.pop("_true_names", None)
    return records
