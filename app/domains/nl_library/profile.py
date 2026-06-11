"""nl_library — 국립중앙도서관 타깃 도메인 프로파일 (SKOVIX V1)."""
from pathlib import Path

from domains.base import DomainProfile, MilvusScalarField
from domains.nl_library.doc_types import detect_doc_type


def _loaders():
    # 파서 의존성(pymarc/lxml/openpyxl)은 사용 시점에 로드
    from domains.nl_library.loaders import build_loaders

    return build_loaders()


PROFILE = DomainProfile(
    name="nl_library",
    doc_types=["book", "paper", "literature", "policy"],
    default_doc_type="book",
    detect_doc_type=detect_doc_type,
    milvus_scalar_fields=[
        MilvusScalarField("publisher", max_length=512),
        MilvusScalarField("corporate_author", max_length=512),
        MilvusScalarField("pub_date", max_length=32),
        MilvusScalarField("kdc", max_length=32),
    ],
    prompts_path=Path(__file__).parent / "prompts",
    loaders_factory=_loaders,
)
