import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

HistoryKind = Literal["book", "paper", "research"]

# 검색어·연구 질문. 딥리서치 질문 상한(api/research.py ResearchCreate)과 맞춘다.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
RefId = Annotated[str, StringConstraints(max_length=64)]

IMPORT_MAX_ITEMS = 100


class HistoryItemIn(BaseModel):
    kind: HistoryKind
    title: Title
    params: dict = Field(default_factory=dict)
    snapshot: dict | None = None
    ai: dict | None = None
    ref_id: RefId | None = None

    @model_validator(mode="after")
    def _research_needs_ref(self):
        # 딥리서치 기록은 ref_id(job_id)로 보고서를 연다. 없으면 사이드바에서 눌러도 갈 곳이 없다.
        if self.kind == "research" and not self.ref_id:
            raise ValueError("research 기록에는 ref_id 가 필요하다")
        return self


class HistoryItemPatch(BaseModel):
    title: Title | None = None
    params: dict | None = None
    snapshot: dict | None = None
    ai: dict | None = None

    @model_validator(mode="after")
    def _required_columns_stay_set(self):
        # snapshot·ai 는 null 로 비울 수 있지만 title·params 는 NOT NULL 칸이다
        for name in ("title", "params"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} 은 null 로 바꿀 수 없다")
        return self


class ResearchStatus(BaseModel):
    status: str
    stage: str
    # 아래 셋은 [이 연구 이어가기] 로 연구 행(research_works)이 생긴 잡에만 값이 있다
    phase: str | None = None
    progress: dict | None = None
    # 진행 중 생성(queued·running)이 있는가 — 사이드바가 폴링을 이어갈지 정한다(06d)
    generating: bool = False


class HistoryItemOut(BaseModel):
    id: uuid.UUID
    kind: HistoryKind
    title: str
    params: dict
    ref_id: str | None = None
    created_at: datetime
    updated_at: datetime
    has_snapshot: bool
    has_ai: bool
    research: ResearchStatus | None = None


class HistoryItemDetail(HistoryItemOut):
    snapshot: dict | None = None
    ai: dict | None = None


class HistoryListOut(BaseModel):
    items: list[HistoryItemOut]
    next_cursor: str | None = None


class HistoryImportItem(HistoryItemIn):
    id: uuid.UUID | None = None
    legacy_id: Annotated[str, StringConstraints(min_length=1, max_length=64)] | None = None
    created_at: datetime | None = None

    @field_validator("created_at")
    @classmethod
    def _assume_utc(cls, value: datetime | None) -> datetime | None:
        # 시간대 없는 시각을 timestamptz 에 넣으면 DB 세션 시간대로 읽혀 순서가 어긋난다
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class HistoryImportIn(BaseModel):
    items: list[HistoryImportItem] = Field(max_length=IMPORT_MAX_ITEMS)


class HistoryImportOut(BaseModel):
    imported: int
    skipped: int
    id_map: dict[str, str]
