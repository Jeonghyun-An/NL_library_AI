"""드라이런 명령 생성기 — 워킹트리의 synthesizer.py·프롬프트를 gzip+base64 로 박아 넣는다."""
import base64
import gzip
import pathlib
import sys

repo = pathlib.Path(sys.argv[1])
out = pathlib.Path(__file__).parent


def pack(rel):
    return base64.b64encode(gzip.compress((repo / rel).read_bytes())).decode()


TEMPLATE = r'''import asyncio, base64, gzip, logging, os, types, uuid
import yaml
from sqlalchemy import select
from db.postgres import AsyncSessionLocal
from models.research import ResearchJob
from services.prompts import PromptTemplate
from services.research.state import restore_state

logging.basicConfig(level=logging.INFO, format="%(message)s")
for noisy in ("httpx", "httpcore", "sqlalchemy"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

un = lambda s: gzip.decompress(base64.b64decode(s)).decode("utf-8")
SYN, PRM = un("@@SYN@@"), un("@@PRM@@")

d = yaml.safe_load(PRM)
tpl = PromptTemplate(name="research_synthesize", system=str(d["system"]).rstrip("\n"),
                     user=str(d["user"]).rstrip("\n"), parser=d.get("parser", "plain"),
                     params=d.get("params") or {})
mod = types.ModuleType("synth_new")
exec(compile(SYN, "synthesizer_new.py", "exec"), mod.__dict__)
_orig = mod.get_prompt
mod.get_prompt = lambda name, *a, **k: tpl if name == "research_synthesize" else _orig(name, *a, **k)


async def main():
    jid = os.environ["JOB"]
    async with AsyncSessionLocal() as db:
        job = (await db.execute(
            select(ResearchJob).where(ResearchJob.id == uuid.UUID(jid)))).scalar_one()
        snap = job.state_snapshot
    if not snap:
        print("state_snapshot 없음 — 이 잡으로는 드라이런 불가")
        return
    st = restore_state(jid, snap)
    r = await mod.synthesize(st)          # DB 에 쓰지 않는다
    cited = {e for s in r["sections"] for p in s["papers"] for e in p["evidence"]}
    print()
    print("절", len(r["sections"]), "| 근거", len(r["evidence"]), "| 논문으로 실린 근거", len(cited))
    for s in r["sections"]:
        filled = sum(1 for p in s["papers"] if p["summary"])
        print()
        print("===", s["heading"], "| 논문", len(s["papers"]), "(요약", filled, ") | 향후", len(s["future"]))
        print("도입:", s["intro"])
        for p in s["papers"]:
            print("  -", p["evidence"][0], (p["summary"] or "(요약 없음)")[:120])
        for f in s["future"]:
            print("  >", f["text"])
    print()
    for line in r["limitations"]:
        print("한계:", line)


asyncio.run(main())
'''

body = (TEMPLATE
        .replace("@@SYN@@", pack("app/services/research/synthesizer.py"))
        .replace("@@PRM@@", pack("app/domains/nl_library/prompts/research_synthesize.yaml")))
sh = ("docker exec -i -e JOB=\"$JOB\" -e PYTHONPATH=/app -w /app nl-lib-fastapi python - <<'PY'\n"
      + body + "PY\n")
(out / "synth_dryrun_body.py").write_text(body, encoding="utf-8", newline="\n")
(out / "synth_dryrun.sh").write_text(sh, encoding="utf-8", newline="\n")
print(len(sh))
