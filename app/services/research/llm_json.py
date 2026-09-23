"""llm_json.py — LLM 이 산문에 섞어 내보낸 JSON 을 꺼낸다

critic 과 synthesizer 가 같은 일을 하므로 한 곳에 둔다. 마커 정규식을
두 곳에 두면 갈라지는 것과 같은 이유다.

raw_decode 를 쓰는 이유: `body[index("{"):rindex("}")+1]` 는 JSON 뒤에
`}` 를 포함한 산문이 붙으면 그 끝까지 먹어 파싱이 깨진다. raw_decode 는
첫 유효 JSON 에서 멈춘다.
"""
import json
import re

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def extract_json(raw: str) -> dict | None:
    """첫 유효 JSON 객체를 반환한다. 못 찾으면 None."""
    body = raw or ""
    m = _FENCE.search(body)
    if m:
        body = m.group(1)

    start = body.find("{")
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(body[start:])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None
