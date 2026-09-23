"""드라이런 본문을 DB 없이 검증 — main() 직전까지 실행하고 가짜 chat 으로 synthesize 를 돌린다."""
import asyncio
import json
import pathlib
import sys

body = (pathlib.Path(__file__).parent / "synth_dryrun_body.py").read_text(encoding="utf-8")
prefix = body.split("async def main():")[0]

sys.path.insert(0, sys.argv[1])
ns = {}
exec(compile(prefix, "dryrun_prefix", "exec"), ns)
mod = ns["mod"]

from services.research.state import restore_state  # noqa: E402

snap = {
    "question": "질문", "params": {}, "corpus_range": None,
    "subquestions": [
        {"idx": 0, "text": "하위1", "queries": [], "evidence_ids": ["E1", "E2"],
         "verdict": "insufficient", "parse_failed": False, "failed": False, "note": ""},
        {"idx": 1, "text": "하위2", "queries": [], "evidence_ids": ["E2"],
         "verdict": "sufficient", "parse_failed": False, "failed": False, "note": ""},
    ],
    "evidence": {
        f"E{i}": {"cnts_id": c, "meta": {"title": c},
                  "chunks": [{"chunk_id": "x", "text": "본문", "page_start": 1,
                              "page_end": 1, "score": 0.5}]}
        for i, c in ((1, "A"), (2, "B"))
    },
}
prompts = []


async def fake_chat(messages, *, params=None, timeout=None):
    prompts.append((messages[0]["content"], messages[1]["content"], params))
    return json.dumps({"intro": "도입 [E1].", "summaries": {"E1": "요약"},
                       "future": [{"text": "과제 [E1]."}]}, ensure_ascii=False)

mod.chat = fake_chat
r = asyncio.run(mod.synthesize(restore_state("j", snap)))
print("sections", [s["heading"] for s in r["sections"]])
print("limitations", r["limitations"])
print("prompt uses new template:", '"summaries"' in prompts[0][0], "| paper_ids:", "E1, E2" in prompts[0][0])
print("params:", prompts[0][2])
