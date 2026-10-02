"""side.py - side effects of JAVA_TOOL_OPTIONS on round07's ODL child (stderr temp file, exit codes, error excerpt).

One-off experiment (odl_heap). usage: python /w/side.py LABEL ID [ID ...]
JAVA_TOOL_OPTIONS comes from docker -e (as compose would set it). The only patch: extractor.tempfile.TemporaryFile is
swapped for a NamedTemporaryFile(delete=False) so the child's raw stderr file can be read back after _odl_convert
(contents and code path are otherwise unchanged). Also wraps _odl_convert to record the RuntimeError text and
asyncio's child returncode. Writes /w/out/side_<LABEL>.json.
"""
import asyncio
import json
import os
import sys
import tempfile
import types

sys.path.insert(0, "/app")
from services.ingestion import extractor  # noqa: E402

kept = []
proxy = types.SimpleNamespace(**{k: getattr(tempfile, k) for k in dir(tempfile) if not k.startswith("__")})


def _kept_tmpfile(*a, **kw):
    f = tempfile.NamedTemporaryFile(delete=False, prefix="odlerr_", dir="/tmp")
    kept.append(f.name)
    return f


proxy.TemporaryFile = _kept_tmpfile
extractor.tempfile = proxy

calls = []
_real_convert = extractor._odl_convert
_real_exec = asyncio.create_subprocess_exec


async def _spy_exec(*a, **kw):
    p = await _real_exec(*a, **kw)
    calls.append({"proc": p})
    return p


async def _spy_convert(kwargs, timeout):
    asyncio.create_subprocess_exec = _spy_exec
    n0 = len(kept)
    try:
        await _real_convert(kwargs, timeout)
        calls[-1]["exc"] = None
    except BaseException as e:
        calls[-1]["exc"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        asyncio.create_subprocess_exec = _real_exec
        p = calls[-1].pop("proc")
        calls[-1]["child_returncode"] = p.returncode
        path = kept[n0] if len(kept) > n0 else None
        raw = open(path, "rb").read().decode("utf-8", "replace") if path else None
        calls[-1]["stderr_file_bytes"] = len(raw) if raw is not None else None
        calls[-1]["stderr_file_lines"] = raw.splitlines()[:12] if raw else []
        calls[-1]["stderr_has_picked_up"] = bool(raw and "Picked up JAVA_TOOL_OPTIONS" in raw)
        calls[-1]["summary_now"] = extractor._odl_failure_summary(raw) if raw else ""
        calls[-1]["summary_without_picked_up_line"] = extractor._odl_failure_summary(
            "\n".join(l for l in raw.splitlines() if "Picked up JAVA_TOOL_OPTIONS" not in l)) if raw else ""


extractor._odl_convert = _spy_convert


def main():
    label, ids = sys.argv[1], sys.argv[2:]
    res = {"label": label, "jto": os.environ.get("JAVA_TOOL_OPTIONS"), "docs": []}
    for did in ids:
        calls.clear()
        if did == "BADPDF":  # junk bytes with a PDF header: fitz cannot open it, ODL is tried once and fails (not OOM)
            with open("/tmp/bad.pdf", "wb") as f:
                f.write(b"%PDF-1.4" + b" garbage" * 200)
            path = "/tmp/bad.pdf"
        else:
            path = f"/pdf/{did}.pdf"
        r = asyncio.run(extractor.extract_text_opendataloader(path, did))
        res["docs"].append({"id": did, "fallback": r.odl_fallback, "errors": r.errors, "n_pages": len(r.pages),
                            "attempts": list(calls)})
    print(json.dumps(res, ensure_ascii=False, indent=1))
    json.dump(res, open(f"/w/out/side_{label}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
