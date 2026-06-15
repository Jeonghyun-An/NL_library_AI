"""
domains/base.py — 도메인 프로파일 계약(contract)

코어 파이프라인은 이 인터페이스만 알고, 도메인별 구현(파서·프롬프트·분류 규칙)은
domains/{name}/ 패키지에 둔다. 새 도메인 = 새 패키지 + DOMAIN_PROFILE 설정.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol, runtime_checkable


# ── 카탈로그 코어 필드 (모든 도메인 공통) ────────────────────────
# 이 목록에 없는 파싱 결과 키는 도메인 확장(extra JSONB)으로 분류된다.
CORE_CATALOG_FIELDS = {
    "cnts_id", "title", "title_remainder",
    "personal_author", "corporate_author",
    "publisher", "pub_place", "pub_date",
    "language", "abstract", "keyword", "subject",
    "url", "genre", "source_format", "doc_type",
}


@dataclass
class ParsedRecord:
    """파서 플러그인의 표준 출력. core는 공통 카탈로그 필드, extra는 도메인 확장."""
    source_id: str                                   # 카탈로그 PK (cnts_id)
    core: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)
    source_format: str = ""                          # "MARC" | "MODS" | "KCI" | ...


def split_core_extra(parsed: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """파서 출력 dict를 (core, extra)로 분류. None 값은 버린다."""
    core: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for k, v in parsed.items():
        if v is None:
            continue
        (core if k in CORE_CATALOG_FIELDS else extra)[k] = v
    return core, extra


@runtime_checkable
class CatalogLoader(Protocol):
    """메타데이터 파일(xlsx/csv 등) → ParsedRecord 스트림."""
    loader_id: str

    def detect(self, file_path: str, headers: list[str]) -> bool:
        """이 로더가 해당 파일을 처리할 수 있는지 (헤더 기반 판별)."""
        ...

    def load(self, file_path: str) -> Iterator[ParsedRecord]: ...


@dataclass(frozen=True)
class MilvusScalarField:
    """도메인별 Milvus 스칼라 필터 필드 선언 (v1은 VARCHAR만 지원)."""
    name: str
    max_length: int = 512
    source: str = ""    # Book 속성명 또는 "ext.<key>" (비어있으면 name과 동일)

    @property
    def source_attr(self) -> str:
        return self.source or self.name


def build_scalar_meta(book, scalar_fields: list["MilvusScalarField"]) -> dict[str, str]:
    """Book + 프로파일 스칼라 필드 정의 → Milvus 스칼라 값 dict.

    source 가 'ext.<key>' 면 book.extra 에서, 아니면 getattr(book, source). None → "".
    doc_type 은 모든 도메인 공통 코어 스칼라 — 항상 포함한다.
    """
    meta: dict[str, str] = {}
    for f in scalar_fields:
        src = f.source_attr
        if src.startswith("ext."):
            extra = getattr(book, "extra", None) or {}
            val = extra.get(src[4:])
        else:
            val = getattr(book, src, None)
        meta[f.name] = str(val) if val is not None else ""
    doc_type = getattr(book, "doc_type", None)
    meta["doc_type"] = str(doc_type) if doc_type is not None else ""
    return meta


@dataclass
class DomainProfile:
    name: str
    doc_types: list[str]
    default_doc_type: str
    detect_doc_type: Callable[[dict[str, Any]], str]
    milvus_scalar_fields: list[MilvusScalarField]
    prompts_path: Path
    # 파서 플러그인은 임포트 비용(pymarc/lxml/openpyxl)이 있어 지연 로딩
    loaders_factory: Callable[[], list[CatalogLoader]] = lambda: []

    @property
    def loaders(self) -> list[CatalogLoader]:
        return self.loaders_factory()
