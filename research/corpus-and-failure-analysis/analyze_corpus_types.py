"""analyze_corpus_types.py — 자료 유형별 라우팅 규칙 감사 결과 비교.

학술논문(KCI)·정책재정자료·문학(스캔본) 세 코퍼스에 동일한 판정 공식을 적용한 결과를
한 표로 모은다. 재배정률이 자료 유형에 얼마나 의존하는지, 즉 학술논문 표본만으로
실패 규모를 판단할 수 있는지를 보기 위한 것이다.

분모 규약 (논문과 동일하게 맞춘 것 — 섞으면 같은 코퍼스에 두 값이 나온다):
  재배정률  = 재배정 쪽 / ODL이 산출한 쪽.   판정이 존재하는 쪽만 분모에 넣는다.
  폴백 필요 = (본문<50 쪽 + ODL 미산출 쪽) / PDF 전체 쪽(fitz 집계).
              ODL이 페이지를 못 낸 쪽도 폴백 대상이므로 분자·분모 양쪽에 포함한다.
"""
import io, json, os, statistics, sys

MIN_CHARS = 50
CORPORA = [
    ("학술논문",      "scripts/audit_routing_fix_result100.json", "scripts/fitz_lengths_result100.json"),
    ("정책·재정자료", "scripts/audit_routing_policy200.json",     "scripts/fitz_lengths_policy200.json"),
    ("문학(스캔)",    "scripts/audit_routing_lit100.json",        "scripts/fitz_lengths_lit100.json"),
]

def load(path, key):
    """감사 결과는 리스트(문학·정책) 또는 per_document 를 감싼 딕트(KCI) 두 형태다."""
    if not os.path.exists(path):
        return None
    d = json.load(io.open(path, encoding="utf-8"))
    if isinstance(d, dict):
        d = d.get("per_document", [])
    return [r for r in d if key in r]

def nm(r):
    """감사 결과는 file, fitz 결과는 path 를 쓴다."""
    return os.path.basename(r.get("file") or r.get("path"))

rows = []
for label, apath, fpath in CORPORA:
    a, f = load(apath, "all_pages"), load(fpath, "pages")
    if not a or not f:
        print("[skip] %s — 결과 파일 없음" % label, file=sys.stderr); continue
    ak = {(nm(r), p["page"]): p for r in a for p in r["all_pages"]}
    fl = {(nm(r), p["page"]): (p["fitz_len"] or 0) for r in f for p in r["pages"]}
    miss = len(set(fl) - set(ak))
    rer = [p for p in ak.values() if p["rerouted"]]
    nv = sum(1 for p in ak.values() if p["new_route"] == "vlm")
    ov = sum(1 for p in ak.values() if p["old_route"] == "vlm")
    fz = [fl.get(k, 0) for k, p in ak.items() if p["rerouted"]]
    rows.append({
        "label": label, "docs": len(a), "pdf_pages": len(fl), "odl_pages": len(ak),
        "odl_missing": miss, "reroute": len(rer),
        "reroute_pct": len(rer) / len(ak) * 100,
        "fallback_new_pct": (nv + miss) / len(fl) * 100,
        "fallback_old_pct": (ov + miss) / len(fl) * 100,
        "fitz_short_pct": sum(1 for v in fl.values() if v < MIN_CHARS) / len(fl) * 100,
        "reroute_fitz_mean": (sum(fz) / len(fz)) if fz else 0,
        "reroute_fitz_max": max(fz) if fz else 0,
        "reroute_fitz_ge200": sum(1 for v in fz if v >= 200),
    })

W = 100
print("=" * W)
print("%-14s %5s %8s %8s %7s %7s %9s %10s" %
      ("자료 유형", "문서", "PDF쪽", "ODL쪽", "미산출", "재배정", "재배정률", "폴백 필요"))
print("=" * W)
for r in rows:
    print("%-14s %5d %8d %8d %7d %7d %8.2f%% %9.1f%%" %
          (r["label"], r["docs"], r["pdf_pages"], r["odl_pages"], r["odl_missing"],
           r["reroute"], r["reroute_pct"], r["fallback_new_pct"]))
print("=" * W)

base = next((r for r in rows if r["label"] == "학술논문"), None)
if base and base["reroute_pct"]:
    print("\n학술논문 기준 재배정률 배수:")
    for r in rows:
        print("  %-14s %5.1f배" % (r["label"], r["reroute_pct"] / base["reroute_pct"]))

print("\n재배정된 쪽의 실제 본문량 (fitz 텍스트 레이어 = 정답지):")
for r in rows:
    if r["reroute"]:
        print("  %-14s 평균 %4.0f자 / 최대 %4d자 / 200자 이상 %d쪽" %
              (r["label"], r["reroute_fitz_mean"], r["reroute_fitz_max"],
               r["reroute_fitz_ge200"]))

json.dump(rows, io.open("scripts/corpus_type_comparison.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n저장: scripts/corpus_type_comparison.json")
