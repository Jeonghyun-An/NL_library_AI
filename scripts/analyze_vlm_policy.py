"""analyze_vlm_policy.py — 재배정 쪽에 대한 VLM 회복량 분석.

처리군(재배정 100쪽)과 대조군(두 규칙이 모두 "본문 충분"으로 일치 판정한 86쪽)을
ODL 감사 결과와 fitz 추출량에 병합한다. 확인할 것:
  1. 처리군 회복량 — 오판으로 버려진 쪽에서 VLM이 되찾는 분량
  2. 대조군 타당성 — fitz 대비 1.0배 근처인가 (VLM이 무조건 부풀리는 것이 아님)
  3. fitz로 측정 불가했던 쪽(레이어 없음/손상)의 손실 크기
"""
import io, json, os, statistics

VLM = "C:/Users/LANDSOFT/Desktop/SKOVIX/vlm_policy/vlm_policy_result.json"
AUDIT = "scripts/audit_routing_policy200.json"
FITZ = "scripts/fitz_lengths_policy200.json"
REP_THRESHOLD = 10   # 같은 줄이 10회 이상 반복되면 디코딩 반복 루프 의심

def main():
    a = json.load(io.open(AUDIT, encoding="utf-8"))
    f = json.load(io.open(FITZ, encoding="utf-8"))
    v = json.load(io.open(VLM, encoding="utf-8"))

    # 감사·fitz 는 "폴더/파일.pdf" 상대경로, VLM 결과는 파일명만 쓴다
    aud = {(os.path.basename(r["file"]), p["page"]): p
           for r in a if "all_pages" in r for p in r["all_pages"]}
    fz = {(os.path.basename(r["file"]), p["page"]): (p["fitz_len"] or 0)
          for r in f if "pages" in r for p in r["pages"]}

    rows = []
    for r in v:
        for p in r["pages"]:
            k = (r["doc"], p["page"])
            au = aud.get(k)
            rows.append({"doc": r["doc"], "page": p["page"], "kind": p["kind"],
                         "vlm": p["vlm_len"], "rep": p["max_repeat_count"],
                         "sec": p["elapsed_sec"],
                         "fitz": fz.get(k), "old": au and au["old_len"],
                         "new": au and au["new_len"]})
    missing = [r for r in rows if r["new"] is None or r["fitz"] is None]
    print("병합: %d쪽 (감사·fitz 매칭 실패 %d쪽)" % (len(rows), len(missing)))

    # ── 1) 반복 루프 오염 점검 ────────────────────────────────
    bad = [r for r in rows if r["rep"] >= REP_THRESHOLD]
    print("\n[1] 디코딩 반복 루프 의심(같은 줄 %d회 이상): %d쪽" % (REP_THRESHOLD, len(bad)))
    for r in sorted(bad, key=lambda x: -x["rep"])[:8]:
        print("    %-24s p.%-4d %s  %5d자  반복 %d회" %
              (r["doc"][:24], r["page"], r["kind"], r["vlm"], r["rep"]))
    clean = [r for r in rows if r["rep"] < REP_THRESHOLD]
    print("    → 오염 제외 %d쪽으로 이하 집계" % len(clean))

    def stat(xs, lab):
        if not xs: print("    %s: 없음" % lab); return
        print("    %-34s n=%3d  중앙값 %5.0f  평균 %6.0f  최대 %5.0f" %
              (lab, len(xs), statistics.median(xs), sum(xs)/len(xs), max(xs)))

    tre = [r for r in clean if r["kind"] == "reroute"]
    ctl = [r for r in clean if r["kind"] == "control"]

    # ── 2) 대조군 타당성 ──────────────────────────────────────
    print("\n[2] 대조군 %d쪽 — VLM 이 분량을 부풀리는지 검증" % len(ctl))
    cb = [r for r in ctl if r["fitz"] >= 200]      # 레이어 온전한 쪽만 비율 계산 가능
    ratios = [r["vlm"]/r["fitz"] for r in cb]
    stat([r["vlm"] for r in ctl], "VLM 추출량")
    stat([r["fitz"] for r in ctl], "fitz 추출량")
    if ratios:
        print("    레이어 온전한 %d쪽의 VLM/fitz 비율: 중앙값 %.2f배 / 평균 %.2f배" %
              (len(cb), statistics.median(ratios), sum(ratios)/len(ratios)))

    # ── 3) 처리군 회복량 ──────────────────────────────────────
    print("\n[3] 처리군 %d쪽 — 오판으로 버려진 쪽의 회복량" % len(tre))
    stat([r["new"] for r in tre], "개선 후 본문 길이 (판정 근거)")
    stat([r["vlm"] for r in tre], "VLM 추출량")
    gain = [r["vlm"] - r["new"] for r in tre]
    stat(gain, "회복량 (VLM − 본문 길이)")
    print("    회복 총량: %d자" % sum(gain))
    for th in (200, 500, 1000):
        print("      VLM %4d자 이상 회복: %2d쪽" % (th, sum(1 for g in gain if g >= th)))

    # ── 4) fitz 로 측정 불가했던 쪽 ───────────────────────────
    hi = [r for r in tre if r["fitz"] >= 200]
    lo = [r for r in tre if r["fitz"] < 50]
    print("\n[4] fitz 상태별 처리군 (fitz 는 레이어 온전할 때만 정답지)")
    print("    fitz 200자 이상 %d쪽 — 직접 측정 가능했던 구간" % len(hi))
    stat([r["fitz"] for r in hi], "  fitz")
    stat([r["vlm"] for r in hi], "  VLM")
    if hi:
        rr = [r["vlm"]/r["fitz"] for r in hi]
        print("      VLM/fitz 비율 중앙값 %.2f배" % statistics.median(rr))
    print("    fitz 50자 미만 %d쪽 — fitz 로는 측정 불가였던 구간" % len(lo))
    stat([r["vlm"] for r in lo], "  VLM")

    json.dump(rows, io.open("scripts/vlm_policy_merged.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n저장: scripts/vlm_policy_merged.json")

if __name__ == "__main__":
    main()
