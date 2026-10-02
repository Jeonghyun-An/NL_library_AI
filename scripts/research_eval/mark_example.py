r"""mark_example.py — 연구를 방문자용 예시 연구로 지정하거나 푼다 (research_works.is_example 만 바꾼다)

예시 연구는 미리 돌린 실제 기록이고 읽기 전용이다(쓰기 API 는 409 — spec §4 시연 정직성 규칙). API 로는
켜지 않고 이 스크립트로만 지정한다(spec §6-1). --yes 가 없으면 지금 값과 할 일만 찍고 아무것도 쓰지 않는다.

실행 (서버 — DB 에 쓴다. 먼저 --yes 없이 본다):
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/research_eval/mark_example.py --work <연구 id> --on
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/research_eval/mark_example.py --work <연구 id> --on --yes
연구 id 는 [이 연구 이어가기] 를 누른 딥리서치 잡 id 다.
"""
import argparse
import sys
import uuid

SELECT_SQL = "SELECT is_example FROM research_works WHERE id = CAST(:id AS uuid)"
UPDATE_SQL = ("UPDATE research_works SET is_example = :flag, updated_at = now() "
              "WHERE id = CAST(:id AS uuid)")


def _work_id(raw: str) -> str:
    return str(uuid.UUID(raw))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="예시 연구 지정·해제 (research_works.is_example)")
    ap.add_argument("--work", required=True, type=_work_id, help="연구 id(= 출발 딥리서치 잡 id)")
    flag = ap.add_mutually_exclusive_group(required=True)
    flag.add_argument("--on", action="store_true", help="예시 연구로 지정")
    flag.add_argument("--off", action="store_true", help="예시 연구 지정을 푼다")
    ap.add_argument("--yes", action="store_true", help="실제로 쓴다(없으면 할 일만 찍는다)")
    args = ap.parse_args(argv)
    target = bool(args.on)

    from sqlalchemy import text as sa_text

    from db.postgres import SyncSessionLocal

    db = SyncSessionLocal()
    try:
        current = db.execute(sa_text(SELECT_SQL), {"id": args.work}).scalar_one_or_none()
        if current is None:
            print(f"연구 {args.work} 가 없다 - [이 연구 이어가기] 를 누른 딥리서치 잡 id 인지 본다")
            return 1
        if current == target:
            print(f"연구 {args.work} 는 이미 is_example={current} - 바꿀 것이 없다")
            return 0
        print(f"할 일: 연구 {args.work} is_example {current} -> {target}")
        if not args.yes:
            print("쓰지 않았다 - 실제로 바꾸려면 --yes 를 붙여 다시 돌린다")
            return 0
        db.execute(sa_text(UPDATE_SQL), {"id": args.work, "flag": target})
        db.commit()
        print("바꿨다")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
