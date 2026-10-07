"""paragraph_edit.py — 사용자가 고친 절 문단 받아들이기 (순수) — spec §3·§5-5 문단 상태, 정함 17.

PUT .../sections/{key} 의 문단 목록을 저장된 문단과 맞대어 상태를 서버가 정한다. 화면이 보낸 state 는
AI 제안 ↔ 수락(proposed ↔ accepted) 사이만 믿는다 — 수락만 한 문단도 AI 작성으로 센다(spec §3):
  새 문단(id 없음·저장되지 않은 id)  → authored(사용자 작성), 새 id = 저장된 가장 큰 p<n> 다음
  글이 바뀐 문단                      → 저장된 상태가 authored 면 그대로, 아니면 edited(사용자가 고침)
  글이 같은 문단                      → proposed·accepted 사이만 요청대로, edited·authored 는 그대로
  목록에 없는 저장 문단               → 지운다
순서는 요청 순서다. 그 뒤 revalidate 가 절의 evidence 지도·수치로 생성 때와 같은 검사(markers.check_paragraph)를
다시 거친다 — 사용자가 쓴 글도 틀린 [E#]·[F#] 는 지워지고 [F#] 밖 숫자는 '확인 필요'로 센다(정함 9).
"""
import re

from services.research_work.markers import check_paragraph

_AI_STATES = ("proposed", "accepted")
_PID = re.compile(r"p(\d+)")


def merge_paragraphs(stored: list[dict], incoming: list[dict]) -> list[dict]:
    """정함 17 전이. incoming 원소 = {"id": str | None, "text": str, "state": str}. 저장된 id 가 두 번 오면 ValueError."""
    by_id = {p["id"]: p for p in stored if p.get("id")}
    known = [item.get("id") for item in incoming if item.get("id") in by_id]
    if len(known) != len(set(known)):
        raise ValueError("같은 문단 id 가 두 번 있습니다")
    last = max((int(m.group(1)) for p in stored if (m := _PID.fullmatch(str(p.get("id") or "")))), default=0)
    merged: list[dict] = []
    for item in incoming:
        old = by_id.get(item.get("id"))
        if old is None:
            last += 1
            merged.append({"id": f"p{last}", "text": item["text"], "state": "authored", "cites": [],
                           "checks": {}, "gen_id": None})
            continue
        if item["text"] != old.get("text"):
            state = "authored" if old.get("state") == "authored" else "edited"
        elif old.get("state") in _AI_STATES and item.get("state") in _AI_STATES:
            state = item["state"]
        else:
            state = old.get("state")
        merged.append({**old, "text": item["text"], "state": state})
    return merged


def revalidate(section: dict, paragraphs: list[dict]) -> list[dict]:
    """절의 evidence 지도·수치로 문단마다 check_paragraph 를 다시 — text·cites·checks 를 새로 쓴다. 검사 뒤 글이
    비는 문단(근거 번호만 있던 문단)은 뺀다."""
    evidence = dict(section.get("evidence") or {})
    valid_f = {f["id"] for f in section.get("figures") or []}
    out: list[dict] = []
    for p in paragraphs:
        text, cites, checks = check_paragraph(p["text"], valid_e=set(evidence), valid_f=valid_f,
                                              evidence=evidence)
        if not text.strip():
            continue
        out.append({**p, "text": text, "cites": cites, "checks": checks})
    return out
