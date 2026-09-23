docker exec -i -e JOB="$JOB" -e PYTHONPATH=/app -w /app nl-lib-fastapi python - <<'PY'
import asyncio, base64, gzip, logging, os, types, uuid
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
SYN, PRM = un("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"), un("H4sIAIg7s2oC/21U3U/aUBR/5684qa+TMPGJd1/2sD3s0RhTtUuI8jEKiwvDIJatsSyrE6SaltSIqxiXdAOkZjztz+k9/R927i1MzPbU9txzfx/no0W5pCqlDBT35Gw+UZRLck7NJABy8v5mubCr5NUMrKZSKQqVlVxRKcnlSknJQCqZTqjvVYpl4MMynTLjAQ0XnTqE4++sMYKoc466y5pTdhego1FCn13dsOM2YNcPx3eAjTvUbOw1maHTYRJQt9A7YaYN4WQa/vCZ10J7yi5tYMNROHR5tmMRsA3o6hwT24ezywmSQEHWIv6JjQ/n3MQyhexwOH6ExK5J9B+5CtKIFwOBcuqjVwfm6agFeNEmJfdtDC5/T9CZMt/Co0M0HPo6D9h9nVLpC8JAp7ekYIlNcjJ2O6A8t449k55dn33R2PWU9Ae8Cpz8Xy7DxuN+1CRvI+AWCb9r0gugd4juCTC3xT63o85gbpVTzipE2OgQziDquMA6LW5sfS29AZHViY5EuTjVrz7VcqFagB2N9SwuiDUstG6A/dQjKxBZpDCWJoio2tRQPBvxPjyt94vXr17SuUUQ4uK9zdxr+n68XpWy+XKpIGVA4u74ma2hp8+KQd0SzYznIXJM9k0TDdH67LbJkcnOysEqT+9dJyF+kiFSQDaXNkAU1xjPREnPiBMktZLLyaWsohJvVVpb4vThJID5LI4IaITdT5wqOtNpshYCeDUljpibd2rlIB3TSrUY/U2FbwBhrlelsrJf5uiscSMmfzilGRADGt8RIpNSbaPG6/VXFzk2xQgafXRa89pzKw8ueiYN6KxavDntAUSNvtgC7Yr2Ia4uOatCUaaF3MzuqFCrPcWnvof+1znN4nj+f+DjZXg6JIQYewUO8vwgHfoL25qoiP+G2P35QovGCmVvK4pazhbysbDFvotjtbK1mMEnpQrKu+yOkt9WNrf2Ctu7PP4HBKj7dZ0EAAA=")

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
PY
