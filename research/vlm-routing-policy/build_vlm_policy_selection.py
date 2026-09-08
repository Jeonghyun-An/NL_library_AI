"""build_vlm_policy_selection.py — VLM 대상 페이지 선정 + 전송용 PDF 스테이징.

처리군(reroute): 원시 길이 기반 판정이 "본문 충분"으로 오판해 1단계 출력을 그대로 쓴 쪽.
대조군(control): 같은 문서에서 두 규칙이 모두 "본문 충분"으로 일치 판정한 쪽을 같은 수만큼
                무작위로 뽑는다. VLM이 모든 쪽의 분량을 부풀리는 것이 아님을 보이기 위한 것.

산출물:
  scratchpad/vlm_policy/vlm_policy_selection.json  — 대상 페이지 목록
  scratchpad/vlm_policy/policy_pdfs/<문서>.pdf      — 전송할 PDF (재배정이 있는 문서만)
"""
import io, json, os, random, shutil, sys

AUDIT = "scripts/audit_routing_policy200.json"
FITZ = "scripts/fitz_lengths_policy200.json"
SRC = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
STAGE = ("C:/Users/LANDSOFT/AppData/Local/Temp/claude/"
         "C--Users-LANDSOFT-mygit-NL-library-AI/"
         "323fbef6-9ad8-4ae4-be15-9845224f185e/scratchpad/vlm_policy/")

random.seed(2026)

def main():
    a = json.load(io.open(AUDIT, encoding="utf-8"))
    ok = [r for r in a if "all_pages" in r]
    print("감사 결과: %d건 %d쪽" % (len(ok), sum(r["odl_pages"] for r in ok)), file=sys.stderr)

    sel, n_rer, n_ctl = {}, 0, 0
    for r in ok:
        rer = [p["page"] for p in r["all_pages"] if p["rerouted"]]
        if not rer:
            continue
        # 두 규칙이 모두 stage1(본문 충분)로 일치 판정한 쪽 = 정상 본문 쪽
        agree = [p["page"] for p in r["all_pages"]
                 if p["old_route"] == "stage1" and p["new_route"] == "stage1"]
        ctl = sorted(random.sample(agree, min(len(rer), len(agree))))
        sel[r["file"]] = {"reroute": sorted(rer), "control": ctl}
        n_rer += len(rer); n_ctl += len(ctl)

    os.makedirs(STAGE + "policy_pdfs", exist_ok=True)
    total_mb = 0
    for rel in sel:
        dst = os.path.join(STAGE, "policy_pdfs", os.path.basename(rel))
        if not os.path.exists(dst):
            shutil.copy2(SRC + rel, dst)
        total_mb += os.path.getsize(dst) / 1e6

    # 서버에서는 평평한 폴더로 두므로 키도 파일명만 남긴다
    flat = {os.path.basename(k): v for k, v in sel.items()}
    json.dump(flat, io.open(STAGE + "vlm_policy_selection.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    shutil.copy2("scripts/run_vlm_policy.py", STAGE + "run_vlm_policy.py")

    print("\n대상 문서 %d건 / 처리군 %d쪽 + 대조군 %d쪽 = %d쪽" %
          (len(sel), n_rer, n_ctl, n_rer + n_ctl))
    print("전송 용량: %.1f MB" % total_mb)
    print("스테이징: %s" % STAGE)

if __name__ == "__main__":
    main()
