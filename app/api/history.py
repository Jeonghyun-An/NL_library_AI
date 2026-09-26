"""history.py — 사이드바 기록 API

모든 요청은 x-session-id(브라우저 ID)로 소유를 가른다. 남의 기록과 없는 기록은 똑같이
404 다 — 구분하면 id 만으로 남의 기록이 있는지 떠볼 수 있다.

쓰기는 응답 전에 커밋한다. get_db 의 마무리 커밋에 맡기면 커밋이 실패해도 화면은 이미
성공 응답을 받아 outbox 에 다시 넣지 않는다.
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_browser_id, get_db
from repositories.history import HistoryRepository, InvalidCursor
from schemas.history import (
    HistoryImportIn, HistoryImportItem, HistoryImportOut, HistoryItemDetail, HistoryItemIn,
    HistoryItemPatch, HistoryKind, HistoryListOut,
)

router = APIRouter(prefix="/api/history", tags=["history"])

# snapshot 은 목록 카드를 다시 그릴 만큼만 담는 칸이다. 결과 전체(청크 원문)를 넣으면 행
# 하나가 수 MB 가 되고, 사이드바를 여는 것만으로 그만큼을 읽게 된다.
SNAPSHOT_MAX_BYTES = 200 * 1024
# 검색 조건(등재구분 등) 몇 개다.
PARAMS_MAX_BYTES = 8 * 1024
# 도서 {intro, items}·논문 {text, refs} 요약. 실제로는 수 KB 다.
AI_MAX_BYTES = 64 * 1024

# 인증 없는 요청이 한 칸이라도 상한 없이 쓰면 행마다 수십 MB 를 쌓을 수 있다 — JSON 칸은 모두 잰다.
# 세 번째 값은 import 가 넘친 칸을 비울 때 넣는 값이다(params 는 NOT NULL 칸이라 빈 조건).
_JSON_FIELD_LIMITS = (
    ("snapshot", SNAPSHOT_MAX_BYTES, None),
    ("params", PARAMS_MAX_BYTES, {}),
    ("ai", AI_MAX_BYTES, None),
)
_TOO_LARGE_DETAIL = {
    "snapshot": "snapshot 은 200KB 까지다 — 목록 카드 필드만 담는다",
    "params": "params 는 8KB 까지다 — 검색 조건만 담는다",
    "ai": "ai 는 64KB 까지다 — AI 요약만 담는다",
}


def _json_bytes(value: dict | None) -> int:
    # 한글은 UTF-8 로 3바이트다. ensure_ascii 로 재면 \uXXXX 6바이트가 되어 상한이 절반으로 엄격해진다.
    if value is None:
        return 0
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _oversized_fields(req: HistoryItemIn | HistoryItemPatch) -> list[str]:
    return [
        name for name, limit, _ in _JSON_FIELD_LIMITS
        if _json_bytes(getattr(req, name)) > limit
    ]


def _reject_large_fields(req: HistoryItemIn | HistoryItemPatch) -> None:
    oversized = _oversized_fields(req)
    if oversized:
        raise HTTPException(status_code=413, detail=_TOO_LARGE_DETAIL[oversized[0]])


def _drop_large_fields(item: HistoryImportItem) -> HistoryImportItem:
    oversized = set(_oversized_fields(item))
    if not oversized:
        return item
    return item.model_copy(update={
        name: empty for name, _, empty in _JSON_FIELD_LIMITS if name in oversized
    })


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="기록을 찾을 수 없다")


@router.get("", response_model=HistoryListOut)
async def list_history(
    kind: HistoryKind | None = None,
    limit: int = Query(30, ge=1, le=100),
    before: str | None = None,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        items, next_cursor = await HistoryRepository(db).list(browser_id, kind, limit, before)
    except InvalidCursor:
        raise HTTPException(status_code=400, detail="before 형식이 올바르지 않다")
    return HistoryListOut(items=items, next_cursor=next_cursor)


@router.post("/import", response_model=HistoryImportOut)
async def import_history(
    req: HistoryImportIn,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    # 이전은 한 건이라도 413 이면 묶음 전체가 매번 실패해 영영 옮겨지지 않는다. 상한을 넘은
    # 칸(결과·검색 조건·AI 요약)만 비우고 기록은 옮긴다 — 원본은 브라우저의 백업 키에 남아 있다.
    items = [_drop_large_fields(item) for item in req.items]
    out = await HistoryRepository(db).import_items(browser_id, items)
    await db.commit()
    return out


@router.get("/{item_id}", response_model=HistoryItemDetail)
async def get_history_item(
    item_id: uuid.UUID,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    item = await HistoryRepository(db).get(browser_id, item_id)
    if item is None:
        raise _not_found()
    return item


@router.put("/{item_id}", response_model=HistoryItemDetail)
async def put_history_item(
    item_id: uuid.UUID,
    req: HistoryItemIn,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    _reject_large_fields(req)
    item = await HistoryRepository(db).upsert(browser_id, item_id, req)
    if item is None:
        raise _not_found()
    await db.commit()
    return item


@router.patch("/{item_id}", response_model=HistoryItemDetail)
async def patch_history_item(
    item_id: uuid.UUID,
    req: HistoryItemPatch,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    _reject_large_fields(req)
    item = await HistoryRepository(db).patch(browser_id, item_id, req)
    if item is None:
        raise _not_found()
    await db.commit()
    return item


@router.delete("/{item_id}", status_code=204, response_class=Response)
async def delete_history_item(
    item_id: uuid.UUID,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    if not await HistoryRepository(db).soft_delete(browser_id, item_id):
        raise _not_found()
    await db.commit()
    return Response(status_code=204)


@router.delete("", status_code=204, response_class=Response)
async def delete_history_kind(
    # 종류를 빠뜨린 요청이 기록 전체를 지우지 않게 필수로 둔다
    kind: HistoryKind = Query(...),
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    await HistoryRepository(db).soft_delete_kind(browser_id, kind)
    await db.commit()
    return Response(status_code=204)
