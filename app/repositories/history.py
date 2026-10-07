import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.history import HistoryItem
from models.research import ResearchJob
from models.research_work import GEN_OPEN_STATUSES, ResearchGeneration, ResearchWork
from schemas.history import (
    HistoryImportItem, HistoryImportOut, HistoryItemDetail, HistoryItemIn,
    HistoryItemOut, HistoryItemPatch, HistoryKind, ResearchStatus,
)

_LIST_COLUMNS = (
    HistoryItem.id, HistoryItem.kind, HistoryItem.title, HistoryItem.params,
    HistoryItem.ref_id, HistoryItem.created_at, HistoryItem.updated_at,
    # 목록은 무거운 칸을 읽지 않고 있는지만 본다
    HistoryItem.snapshot.is_not(None).label("has_snapshot"),
    HistoryItem.ai.is_not(None).label("has_ai"),
)
_DETAIL_COLUMNS = (*_LIST_COLUMNS, HistoryItem.snapshot, HistoryItem.ai)
_ITEM_FIELDS = {"kind", "title", "params", "snapshot", "ai", "ref_id"}


def legacy_history_id(v1: str) -> uuid.UUID:
    """v1 기록 id(Date.now 13자리) → v2 id. 이전을 몇 번 해도 같은 id 가 나와야 중복이 쌓이지 않는다."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"nl-lib-history-v1:{v1}")


class InvalidCursor(ValueError):
    pass


def encode_cursor(created_at: datetime, item_id: uuid.UUID) -> str:
    return f"{created_at.isoformat()}|{item_id}"


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    at, sep, raw_id = cursor.rpartition("|")
    if not sep:
        raise InvalidCursor(cursor)
    try:
        # 인코딩하지 않은 "+"(시간대 오프셋)는 쿼리스트링에서 공백으로 풀린다. ISO 시각에는 공백이 없다.
        return datetime.fromisoformat(at.replace(" ", "+")), uuid.UUID(raw_id)
    except ValueError as e:
        raise InvalidCursor(cursor) from e


def _as_uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


class HistoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(
        self, session_id: uuid.UUID, kind: HistoryKind | None, limit: int, before: str | None,
    ) -> tuple[list[HistoryItemOut], str | None]:
        """최신순 한 쪽과 다음 쪽 커서. 커서가 틀리면 InvalidCursor."""
        stmt = select(*_LIST_COLUMNS).where(
            HistoryItem.session_id == session_id, HistoryItem.deleted_at.is_(None),
        )
        if kind is not None:
            stmt = stmt.where(HistoryItem.kind == kind)
        if before is not None:
            at, item_id = decode_cursor(before)
            # created_at 이 같은 행이 쪽 경계에 걸려도 빠지거나 겹치지 않게 id 로 한 번 더 가른다
            stmt = stmt.where(or_(
                HistoryItem.created_at < at,
                and_(HistoryItem.created_at == at, HistoryItem.id < item_id),
            ))
        stmt = stmt.order_by(HistoryItem.created_at.desc(), HistoryItem.id.desc()).limit(limit + 1)
        rows = (await self.db.execute(stmt)).all()
        page = rows[:limit]
        statuses = await self._research_statuses(r.ref_id for r in page if r.kind == "research")
        items = [
            HistoryItemOut.model_validate({**r._mapping, "research": self._research_of(r, statuses)})
            for r in page
        ]
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        return items, next_cursor

    async def get(self, session_id: uuid.UUID, item_id: uuid.UUID) -> HistoryItemDetail | None:
        row = (await self.db.execute(
            select(*_DETAIL_COLUMNS).where(
                HistoryItem.id == item_id,
                HistoryItem.session_id == session_id,
                HistoryItem.deleted_at.is_(None),
            )
        )).first()
        if row is None:
            return None
        statuses = await self._research_statuses([row.ref_id] if row.kind == "research" else [])
        return HistoryItemDetail.model_validate(
            {**row._mapping, "research": self._research_of(row, statuses)}
        )

    async def upsert(
        self, session_id: uuid.UUID, item_id: uuid.UUID, data: HistoryItemIn,
    ) -> HistoryItemDetail | None:
        """다른 브라우저의 행이면 None — 덮어쓰지 않는다.

        같은 브라우저가 다시 보내면 목록 맨 위로 올린다(created_at 갱신). 지운 기록이면
        되살린다. 요청에 빠진 snapshot·ai·ref_id 는 기존 값을 지킨다 — 재전송이나 중복
        병합이 이미 받은 결과·AI 요약을 지우지 않게.
        """
        stmt = insert(HistoryItem).values(id=item_id, session_id=session_id, **data.model_dump())
        stmt = stmt.on_conflict_do_update(
            index_elements=[HistoryItem.id],
            set_={
                "kind": stmt.excluded.kind,
                "title": stmt.excluded.title,
                "params": stmt.excluded.params,
                "snapshot": func.coalesce(stmt.excluded.snapshot, HistoryItem.snapshot),
                "ai": func.coalesce(stmt.excluded.ai, HistoryItem.ai),
                "ref_id": func.coalesce(stmt.excluded.ref_id, HistoryItem.ref_id),
                "created_at": func.now(),
                "updated_at": func.now(),
                "deleted_at": None,
            },
            where=HistoryItem.session_id == stmt.excluded.session_id,
        ).returning(HistoryItem.id)
        if (await self.db.execute(stmt)).first() is None:
            return None
        return await self.get(session_id, item_id)

    async def patch(
        self, session_id: uuid.UUID, item_id: uuid.UUID, data: HistoryItemPatch,
    ) -> HistoryItemDetail | None:
        res = await self.db.execute(
            update(HistoryItem)
            .where(
                HistoryItem.id == item_id,
                HistoryItem.session_id == session_id,
                HistoryItem.deleted_at.is_(None),
            )
            .values(**data.model_dump(exclude_unset=True), updated_at=func.now())
        )
        if res.rowcount == 0:
            return None
        return await self.get(session_id, item_id)

    async def soft_delete(self, session_id: uuid.UUID, item_id: uuid.UUID) -> bool:
        """이 브라우저의 행이면 True. 이미 지운 행도 True — 재전송된 삭제가 404 로 되돌아오지 않게."""
        res = await self.db.execute(
            update(HistoryItem)
            .where(HistoryItem.id == item_id, HistoryItem.session_id == session_id)
            # 처음 지운 시각을 지킨다
            .values(deleted_at=func.coalesce(HistoryItem.deleted_at, func.now()))
        )
        return res.rowcount == 1

    async def soft_delete_kind(self, session_id: uuid.UUID, kind: HistoryKind) -> int:
        res = await self.db.execute(
            update(HistoryItem)
            .where(
                HistoryItem.session_id == session_id,
                HistoryItem.kind == kind,
                HistoryItem.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
        return res.rowcount

    async def import_items(
        self, session_id: uuid.UUID, items: Sequence[HistoryImportItem],
    ) -> HistoryImportOut:
        """이미 있는 id 는 건너뛴다 — 지운 기록을 되살리지도, 남의 기록을 덮지도 않는다.

        id_map 은 건너뛴 항목까지 담는다. 두 번째 이전에서도 옛 ?restore= 주소를 새 id 로
        찾아야 하기 때문이다.
        """
        rows: dict[uuid.UUID, dict] = {}
        id_map: dict[str, str] = {}
        now = datetime.now(timezone.utc)
        for item in items:
            if item.id is not None:
                item_id = item.id
            elif item.legacy_id is not None:
                item_id = legacy_history_id(item.legacy_id)
            else:
                item_id = uuid.uuid4()
            if item.legacy_id is not None:
                id_map[item.legacy_id] = str(item_id)
            # 목록은 created_at 내림차순이다 — 시계가 앞선 브라우저나 조작한 요청의 미래 시각을 믿으면
            # 그 항목이 이후에 새로 저장한 기록보다 계속 위에 고정된다. 과거 시각은 옛 순서대로 지킨다
            created_at = min(item.created_at or now, now)
            rows.setdefault(item_id, {
                "id": item_id, "session_id": session_id,
                **item.model_dump(include=_ITEM_FIELDS),
                "created_at": created_at, "updated_at": created_at,
            })
        if not rows:
            return HistoryImportOut(imported=0, skipped=0, id_map={})
        inserted = (await self.db.execute(
            insert(HistoryItem).values(list(rows.values()))
            .on_conflict_do_nothing(index_elements=[HistoryItem.id])
            .returning(HistoryItem.id)
        )).all()
        return HistoryImportOut(
            imported=len(inserted), skipped=len(items) - len(inserted), id_map=id_map,
        )

    async def _research_statuses(self, refs: Iterable[str | None]) -> dict[uuid.UUID, ResearchStatus]:
        # ref_id = research_jobs.id::text 로 조인하면 PK 인덱스를 못 쓰고, ref_id 를 uuid 로
        # 캐스팅해 조인하면 형식이 틀린 값 하나에 조회 전체가 실패한다. 한 쪽(최대 100건)의
        # job id 만 모아 PK 로 한 번 더 읽는다.
        # 이어간 연구의 단계·진행 요약은 같은 PK 조회에 research_works 를 id 로 붙여 읽는다
        # (연구 id = 잡 id). 진행 중 생성은 행을 늘리지 않게 EXISTS 로 센다.
        # deleted_at 이 찬 연구는 붙이지 않는다 — 이어가지 않은 딥리서치로 보인다(spec §6-1: 연구 삭제는 기록
        # 삭제를 따르고 deleted_at 은 자리만). 생성 여부도 붙은 연구 행으로 세어 함께 빠진다.
        job_ids = {jid for jid in map(_as_uuid, refs) if jid is not None}
        if not job_ids:
            return {}
        generating = exists().where(
            ResearchGeneration.work_id == ResearchWork.id,
            ResearchGeneration.status.in_(GEN_OPEN_STATUSES),
        )
        rows = (await self.db.execute(
            select(ResearchJob.id, ResearchJob.status, ResearchJob.stage,
                   ResearchWork.phase, ResearchWork.progress,
                   generating.label("generating"))
            .select_from(ResearchJob)
            .outerjoin(ResearchWork, and_(ResearchWork.id == ResearchJob.id,
                                          ResearchWork.deleted_at.is_(None)))
            .where(ResearchJob.id.in_(job_ids))
        )).all()
        return {
            r.id: ResearchStatus(status=r.status, stage=r.stage, phase=r.phase,
                                 progress=r.progress, generating=bool(r.generating))
            for r in rows
        }

    @staticmethod
    def _research_of(row, statuses: dict[uuid.UUID, ResearchStatus]) -> ResearchStatus | None:
        if row.kind != "research":
            return None
        job_id = _as_uuid(row.ref_id)
        return statuses.get(job_id) if job_id is not None else None
