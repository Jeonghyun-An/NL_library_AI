"""운영 이미지에서 round07 의 extract_text_opendataloader 를 실제 ODL 로 — 힙 상한 전달과 엔티티 되돌리기 확인."""
import asyncio, json, os, sys, threading, time
sys.path.insert(0, "/app")
from services.ingestion import extractor
cfg = extractor.cfg

def java_peak():
    peak = 0
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if open(f"/proc/{d}/comm").read().strip() == "java":
                    for line in open(f"/proc/{d}/status"):
                        if line.startswith("VmHWM:"):
                            peak = max(peak, int(line.split()[1]) // 1024)
                    cmd = open(f"/proc/{d}/environ", "rb").read().split(b"\0")
                    jto = [c.decode() for c in cmd if c.startswith(b"JAVA_TOOL_OPTIONS=")]
                    seen_jto.update(jto)
            except OSError:
                pass
    return peak

seen_jto = set()
for did in sys.argv[1:]:
    peak = [0]
    stop = [False]
    def poll():
        while not stop[0]:
            peak[0] = max(peak[0], java_peak()); time.sleep(0.05)
    t = threading.Thread(target=poll, daemon=True); t.start()
    r = asyncio.run(extractor.extract_text_opendataloader(f"/pdf/{did}.pdf", did))
    stop[0] = True; t.join()
    text = "\n".join(p.text for p in r.pages)
    print(json.dumps({"id": did, "heap_cfg": cfg.ODL_JAVA_MAX_HEAP, "worker_jto": os.environ.get("JAVA_TOOL_OPTIONS"),
                      "java_jto": sorted(seen_jto), "fallback": r.odl_fallback, "java_peak_mb": peak[0],
                      "pages": len(r.pages), "n_lt_entity": text.count("&lt;"), "n_amp_entity": text.count("&amp;"),
                      "n_lt": text.count("<"), "sample": [l for l in text.splitlines() if "<" in l or "&" in l][:3],
                      "errors": [e[:120] for e in r.errors][:2]}, ensure_ascii=False))
    seen_jto.clear()
