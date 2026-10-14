"""bibliography_chunks.py — 참고문헌 목록 판정 테스트가 함께 쓰는 운영 청크 원문(fixtures/bibliography_chunks.json).

딥리서치 보고서 48개의 근거 청크(운영 GET)에서 골랐다. expect 가 "bibliography" 면 논문 끝 참고문헌 목록 조각이라
원문 대목에서 빠져야 하고, "body" 면 서지 꼴이 섞였어도 본문이라 남아야 한다. 판정이 길이·밀도를 보므로 원문을 자르지
않고 그대로 둔다(저자 이메일만 지웠다).
"""
import json
from pathlib import Path

CASES: list[dict] = json.loads(
    (Path(__file__).parent / "fixtures" / "bibliography_chunks.json").read_text(encoding="utf-8"))
_BY_ID = {c["chunk_id"]: c for c in CASES}


def chunk(chunk_id: str) -> dict:
    return _BY_ID[chunk_id]
