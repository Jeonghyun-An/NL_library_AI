"""route_compare.py — round07 짧은 쪽 라우팅, 옛 규칙 vs 새 규칙 실제 PDF 회귀 (1회성)

VLM·ODL 을 부르지 않는다. 이 PC 의 D:/SKOVIX/KCI/pdf 를 fitz 로만 읽어, extract_text 의
'ODL 본문이 짧은 쪽을 OCR 로 보낼지' 판정을 옛 규칙과 새 규칙으로 각각 내리고 OCR 로 가는 쪽을 센다.

규칙
  옛 규칙  round07 이전 운영 코드(0487057 의 부모 커밋, extractor.py:416-434)를 그대로 옮겼다.
           ODL >= 50자  fitz 가 ODL 의 2배보다 길면 OCR(CMap 의심), 아니면 ODL 채택
           ODL <  50자  0 < fitz < 50 이면 채택(원래 짧은 쪽), 그 밖(fitz 0자·fitz >= 50)은 OCR
           길이는 옛 _body_len — [그림] 만 빼고 <br> 는 글자로 센다.
  새 규칙  이 브랜치 HEAD(5b3be2e 이후)의 page_routing.is_scan_document + short_page_needs_ocr 를 부른다.
           ODL >= 50자  같음
           ODL <  50자  강제 -> fitz 0자 -> 문서 단위 스캔본 -> fitz 원래 길이 >= 50(ODL 이 놓친 본문) -> 채택
           비스캔·비강제 문서에서는 옛 규칙과 칸마다 같고, 문서 전체가 스캔본(짧은 쪽 과반)일 때만 그 짧은
           쪽도 OCR 한다. 되풀이 줄(머리말·꼬리말·스탬프)을 뺀 길이는 '문서 단위 스캔본 판정'에만 쓴다.
           길이는 새 body_len — <br> 도 뺀다.

ODL 본문 근사 — ODL 은 json header/footer 로 머리말·꼬리말을 지운 markdown 을 낸다. 여기서는 그 길이를
'fitz 텍스트에서 문서 전체에 되풀이되는 줄(repeated_lines)을 뺀 body_len' 으로 둔다. 근사가 놓치는 것:
  - ODL 이 fitz 보다 글자를 잃는 쪽(CMap 손상) — 근사에선 ODL ~ fitz 라 CMap 2배 분기는 머리말·꼬리말이
    길 때만 걸린다(cmap_pages 로 따로 센다). 이 분기는 두 규칙에 똑같이 걸려서 비교에는 영향이 없다.
  - ODL 의 <br> 빈 표 격자·[그림] 마커 — fitz 텍스트엔 없다. 그래서 '새 규칙이 <br> 를 길이에서 빼서
    판정이 바뀌는 쪽'(len_diff_pages)은 이 하네스에서 0 이다. 실제 ODL 로만 볼 수 있다.
  - 표 셀 충전율(json) 판정과 'ODL 누락' 쪽 — 쓰지 않는다(두 규칙에 똑같이 걸리는 분기).
그래서 이 결과는 '짧은 쪽 분기' 의 차이만 보여 준다. 두 규칙 모두 VLM 쪽수 상한(60쪽)을 적용한다.

묶음
  fail_block   — metadata.csv 의 「한국문학연구」 2002년 이전(10-01 '섹션 없음' 281건이 모두 이 안에 있다)
  pre2005      — 2004년 이전 다른 학술지 무작위
  digital      — 2005년 이후 무작위
  short_front  — 2005년 이후 문서 중 첫 두 쪽 안에 짧은 쪽(표지·간지, 이미지 표지 포함)이 있는 문서
                 (digital 표본 다음 순서에서 최대 25건)
  br_grid      — ODL embedded 에서 <br> 빈 격자가 나왔던 문서
  named_cases  — 계획서·리뷰에서 이름이 오른 문서(아래 NAMED 의 사유 참고)

산출물(이 폴더): pages.csv(쪽별 판정)·docs.csv(문서별)·summary.json(묶음별 합계·검사·출처)
  pages.csv 는 '본문 충분 + 두 규칙 모두 채택' 인 쪽을 뺀다(--all-pages 로 모두). 그 쪽의 합계는 docs.csv 에 있다.
  pages.csv 의 old_ocr/new_ocr 는 VLM 쪽수 상한을 적용하기 전의 규칙 판정이다(상한 적용 합계는 docs.csv).
검사(summary.json 의 checks)가 하나라도 틀리면 종료 코드 1 — 코드를 고치지 말고 결과를 보고한다.
사용법: python research/round07-ingest-regression/route_compare.py [--per-group 200] [--seed 20261001]
"""
import argparse
import csv
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "app"))

import fitz  # noqa: E402

from services.ingestion import page_routing as pr  # noqa: E402
from services.ingestion.extractor import _clean_text  # noqa: E402

PDF_DIR = Path("D:/SKOVIX/KCI/pdf")
META = Path("D:/SKOVIX/KCI/metadata.csv")
MIN_CHARS = 50          # 설정 EXTRACT_MIN_CHARS_PER_PAGE 기본값
VLM_CAP = 60            # VLM_MAX_PAGES_PER_DOC
REPEAT_RATIO = 0.6      # SCAN_REPEAT_LINE_RATIO
SHORT_RATIO = 0.5       # SCAN_SHORT_PAGE_RATIO
SCAN_MIN_PAGES = 3      # SCAN_MIN_PAGES
IMG_COVER_RATIO = 0.5   # 쪽 면적의 이만큼 이상을 이미지가 덮으면 '이미지 쪽'
FRONT_TARGET = 25
BR_GRID = ["KCI_FI001930485", "KCI_FI000897237"]
NAMED = [
    "KCI_FI003011274",  # 2023 디지털 논문 — 본문이 이미지로만 있고 텍스트 층엔 머리말·꼬리말뿐인 쪽(1·2·8·9쪽): 옛 규칙대로 OCR 이어야 한다
    "KCI_FI001141801",  # 4쪽 fitz 51자(쪽 번호 줄을 빼면 48자) 경계 사례: 옛 규칙대로 OCR 이어야 한다
    "KCI_FI002252358",  # 이미지 표지 디지털 논문(316쪽) — 0쪽을 쪽 전체 이미지가 덮고 글자 24자: 표지는 ODL 채택 그대로
    "KCI_FI002025246",  # 실패 블록 스탬프 문서 — 쪽마다 'Copyright (C) 2002 Nuri Media Co., Ltd.' 한 줄
    "KCI_FI001238691",  # 텍스트 층이 거의 없는 문서(옛 ODL 이 877초 넘게 돈 문서, 26쪽 중 0~24쪽 0자·25쪽 4자) — 옛 규칙은 25쪽 OCR(25쪽은 '원래 짧은 쪽'으로 ODL 채택), 새 규칙은 스캔본 판정으로 26쪽 모두 OCR
    "KCI_FI001343547",  # 실제 ODL 에서 <br> 를 빼니 2·13쪽이 바뀌었던 문서 — 이 근사로는 안 보인다
    "KCI_FI001667569",  # 되풀이 줄 뺀 길이로 짧은 쪽을 판정하던 첫 구현에서 'OCR 에서 빠짐' 3쪽이던 문서
    "KCI_FI001158431",  # 위와 같음(3쪽)
]

# page_routing 이 돌려주는 사유 문구 -> CSV 에 넣을 짧은 코드(모르는 문구는 그대로 둔다)
WHY = {
    "강제 OCR(섹션 0개 재추출)": "force",
    "텍스트 층 없음(fitz 0자)": "fitz0",
    "스캔본 문서(짧은 쪽 과반)": "scan_doc",
    "ODL 이 놓친 본문": "odl_missed",
    "원래 짧은 쪽": "short_ok",
}

_OLD_STRUCT = str.maketrans("", "", "|-: \t\n\r")


def old_body_len(text: str) -> int:
    """옛 extractor._body_len — [그림] 만 빼고 <br> 는 글자로 센다(round07 이전)."""
    return len(text.replace("[그림]", "").translate(_OLD_STRUCT))


def old_decision(odl_len: int, raw: int) -> tuple[bool, str]:
    """round07 이전 운영 코드의 길이 분기(표 셀 충전율·ODL 누락 분기는 제외)."""
    if odl_len >= MIN_CHARS:
        return (True, "cmap") if raw > odl_len * 2 else (False, "enough")
    if 0 < raw < MIN_CHARS:
        return False, "short_ok"
    return True, ("fitz0" if raw == 0 else "odl_missed")


def new_decision(odl_len: int, raw: int, stripped: int, doc_is_scan: bool) -> tuple[bool, str]:
    """HEAD extract_text 의 길이 분기 — 짧은 쪽은 page_routing 의 실제 함수를 부른다."""
    if odl_len >= MIN_CHARS:
        return (True, "cmap") if raw > odl_len * 2 else (False, "enough")
    need, why = pr.short_page_needs_ocr(
        fitz_len_stripped=stripped, fitz_len_raw=raw, doc_is_scan=doc_is_scan, force=False, min_chars=MIN_CHARS,
    )
    return need, WHY.get(why, why)


def cap_flags(flags: list[bool]) -> list[bool]:
    """문서당 VLM 쪽수 상한 — OCR 로 가는 쪽 중 앞에서 VLM_CAP 쪽까지만 OCR 한다."""
    out, used = [], 0
    for f in flags:
        out.append(f and used < VLM_CAP)
        used += f
    return out


def image_cover_ratio(page) -> float | None:
    """쪽 면적 중 이미지가 차지하는 비율(겹침은 더해서 1.0 으로 자른다). 읽지 못하면 None."""
    try:
        area = page.rect.width * page.rect.height
        if area <= 0:
            return 0.0
        total = sum((i["bbox"][2] - i["bbox"][0]) * (i["bbox"][3] - i["bbox"][1]) for i in page.get_image_info())
        return round(min(1.0, total / area), 2)
    except Exception:
        return None


def _init_worker() -> None:
    fitz.TOOLS.mupdf_display_errors(False)
    if hasattr(fitz.TOOLS, "mupdf_display_warnings"):
        fitz.TOOLS.mupdf_display_warnings(False)


def _page_texts(doc) -> tuple[list[str], int]:
    """extract_text 처럼 쪽마다 get_text 를 try 로 감싼다 — 실패한 쪽은 빈 텍스트 층."""
    texts, errors = [], 0
    for page in doc:
        try:
            texts.append(_clean_text(page.get_text()))
        except Exception:
            texts.append("")
            errors += 1
    return texts, errors


def analyze(pid: str) -> dict:
    """PDF 한 건의 쪽별 옛/새 판정. 읽지 못하면 {'id', 'skip'}."""
    try:
        with fitz.open(str(PDF_DIR / f"{pid}.pdf")) as doc:
            n = len(doc)
            if n == 0:
                return {"id": pid, "skip": "0쪽"}
            texts, text_errors = _page_texts(doc)
            rep = pr.repeated_lines(texts, REPEAT_RATIO)
            stripped_texts = [pr.strip_lines(t, rep) for t in texts]
            new_raw = [pr.body_len(t) for t in texts]
            new_str = [pr.body_len(t) for t in stripped_texts]
            # 이미지 덮임은 짧은 쪽에서만 잰다(두 규칙이 갈리는 쪽은 짧은 쪽뿐이다)
            img = [image_cover_ratio(doc[i]) if new_str[i] < MIN_CHARS else None for i in range(n)]
    except Exception as e:  # noqa: BLE001 — 깨진 PDF 한 건이 표본 전체를 멈추지 않게
        return {"id": pid, "skip": f"{type(e).__name__}: {e}"[:100]}

    old_raw = [old_body_len(t) for t in texts]
    old_str = [old_body_len(t) for t in stripped_texts]
    # ODL 본문 근사: 되풀이 줄을 뺀 fitz 길이(모듈 docstring)
    odl_new, odl_old = new_str, old_str
    short = [odl_new[i] < MIN_CHARS and new_str[i] < MIN_CHARS for i in range(n)]
    scan = pr.is_scan_document(short, min_pages=SCAN_MIN_PAGES, ratio=SHORT_RATIO)
    old = [old_decision(odl_old[i], old_raw[i]) for i in range(n)]
    new = [new_decision(odl_new[i], new_raw[i], new_str[i], scan) for i in range(n)]
    old_flag, new_flag = [o for o, _ in old], [w for w, _ in new]
    old_cap, new_cap = cap_flags(old_flag), cap_flags(new_flag)
    len_diff = [old_raw[i] != new_raw[i] or old_str[i] != new_str[i] for i in range(n)]
    changed = [old_flag[i] != new_flag[i] for i in range(n)]
    img_page = [short[i] and img[i] is not None and img[i] >= IMG_COVER_RATIO for i in range(n)]

    doc_row = {
        "pages": n, "short_pages": sum(short), "doc_is_scan": scan,
        "old_ocr": sum(old_cap), "new_ocr": sum(new_cap),
        "newly_ocr": sum(w and not o for o, w in zip(old_cap, new_cap)),
        "no_longer_ocr": sum(o and not w for o, w in zip(old_cap, new_cap)),
        "added_uncapped": sum(w and not o for o, w in zip(old_flag, new_flag)),
        "removed_uncapped": sum(o and not w for o, w in zip(old_flag, new_flag)),
        "changed_br": sum(c and d for c, d in zip(changed, len_diff)),
        "changed_other": sum(c and not d for c, d in zip(changed, len_diff)),
        "len_diff_pages": sum(len_diff),
        "cover_old": int(old_cap[0]), "cover_new": int(new_cap[0]),
        "img_cover_pages": sum(img_page),
        "img_cover_old_ocr": sum(p and f for p, f in zip(img_page, old_flag)),
        "img_cover_new_ocr": sum(p and f for p, f in zip(img_page, new_flag)),
        "cmap_pages": sum(why == "cmap" for _, why in new),
        # 되풀이 줄을 빼면 50자 미만이지만 원래 fitz 길이가 50자 이상이라 '이미지 본문 쪽'으로 OCR 에 남는 쪽
        # (되풀이 줄 뺀 길이로 판정하면 ODL 채택으로 바뀌어 본문이 사라진다 — 5b3be2e 가 닫은 경로)
        "held_by_raw": sum(new_flag[i] and new[i][1] == "odl_missed" and new_str[i] < MIN_CHARS for i in range(n)),
        "capped": int(sum(old_flag) > VLM_CAP or sum(new_flag) > VLM_CAP),
        "text_errors": text_errors,
        "repeated": " / ".join(sorted(rep)[:3])[:120],
    }
    pages = [
        {
            "page": i, "fitz_raw": new_raw[i], "fitz_stripped": new_str[i], "odl_approx": odl_new[i],
            "short": int(short[i]), "img_cover": "" if img[i] is None else img[i],
            "old_ocr": int(old_flag[i]), "old_why": old[i][1], "new_ocr": int(new_flag[i]), "new_why": new[i][1],
            "changed": int(changed[i]),
        }
        for i in range(n)
    ]
    return {"id": pid, "doc": doc_row, "pages": pages}


def front_flag(pid: str) -> bool:
    """첫 두 쪽 안에 '글자는 있지만 되풀이 줄을 빼면 짧은' 쪽이 있고 문서 대부분이 본문 쪽인가."""
    try:
        with fitz.open(str(PDF_DIR / f"{pid}.pdf")) as doc:
            if len(doc) < SCAN_MIN_PAGES:
                return False
            texts, _ = _page_texts(doc)
    except Exception:  # noqa: BLE001
        return False
    rep = pr.repeated_lines(texts, REPEAT_RATIO)
    s = [pr.body_len(pr.strip_lines(t, rep)) for t in texts]
    raw = [pr.body_len(t) for t in texts[:2]]
    short_front = any(raw[n] > 0 and s[n] < MIN_CHARS for n in (0, 1))
    return short_front and sum(x >= MIN_CHARS for x in s) >= len(s) * 0.6


def pick(args, ex) -> list[tuple[str, str]]:
    rng = random.Random(args.seed)
    with open(META, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    def year(r):
        return int(r["year_month"][:4]) if r["year_month"][:4].isdigit() else None

    # 26만 파일 폴더라 파일마다 exists() 를 부르면 수십 분 걸린다 — 목록을 한 번만 읽는다.
    local = {e.name[:-4] for e in os.scandir(PDF_DIR) if e.name.endswith(".pdf")}

    def ids(cond) -> list[str]:  # metadata.csv 에 같은 id 가 두 번 있는 행이 있다
        return list(dict.fromkeys(r["kci_fi_id"] for r in rows if cond(r) and r["kci_fi_id"] in local))

    fail = ids(lambda r: r["journal"] == "한국문학연구" and year(r) and year(r) <= 2002)
    if args.fail_limit:
        fail = fail[:args.fail_limit]
    fail_set = set(fail)
    pre = ids(lambda r: year(r) and year(r) < 2005 and r["kci_fi_id"] not in fail_set)
    digital = ids(lambda r: year(r) and year(r) >= 2005)
    rng.shuffle(pre)
    rng.shuffle(digital)
    out = [(p, "fail_block") for p in fail]
    out += [(p, "pre2005") for p in pre[:args.per_group]]
    out += [(p, "digital") for p in digital[:args.per_group]]

    # 표지·간지 후보를 앞에서부터 묶음 단위로 병렬로 읽고, 앞에서부터 front_target 건을 취한다
    # (한 건씩 읽다 멈추는 것과 같은 선택이다).
    cands = digital[args.per_group:args.per_group * 20]
    front: list[str] = []
    step = max(1, args.workers * 8)
    for i in range(0, len(cands), step):
        chunk = cands[i:i + step]
        front += [p for p, ok in zip(chunk, ex.map(front_flag, chunk)) if ok]
        if len(front) >= args.front_target:
            break
    out += [(p, "short_front") for p in front[:args.front_target]]
    out += [(p, "br_grid") for p in BR_GRID if p in local]
    out += [(p, "named_cases") for p in NAMED if p in local]
    return out


GROUP_ORDER = ["fail_block", "pre2005", "digital", "short_front", "br_grid", "named_cases"]


def aggregate(docs: list[dict]) -> dict:
    out = {}
    for g in [g for g in GROUP_ORDER if any(d["group"] == g for d in docs)]:
        rows = [d for d in docs if d["group"] == g]
        scan = [d for d in rows if d["doc_is_scan"]]
        non = [d for d in rows if not d["doc_is_scan"]]

        def tot(rs, k):
            return int(sum(r[k] for r in rs))

        out[g] = {
            "docs": len(rows), "pages": tot(rows, "pages"),
            "old_ocr_pages": tot(rows, "old_ocr"), "new_ocr_pages": tot(rows, "new_ocr"),
            "removed_uncapped_pages": tot(rows, "removed_uncapped"),
            "added_uncapped_pages": tot(rows, "added_uncapped"),
            "capped_docs": tot(rows, "capped"), "cmap_pages": tot(rows, "cmap_pages"),
            "len_diff_pages": tot(rows, "len_diff_pages"),
            "scan_docs": len(scan), "scan_pages": tot(scan, "pages"),
            "scan_old_ocr_pages": tot(scan, "old_ocr"), "scan_new_ocr_pages": tot(scan, "new_ocr"),
            "scan_docs_old_zero": sum(d["old_ocr"] == 0 for d in scan),
            "scan_docs_gained": sum(d["new_ocr"] > d["old_ocr"] for d in scan),
            "scan_cover_old_ocr": tot(scan, "cover_old"), "scan_cover_new_ocr": tot(scan, "cover_new"),
            "nonscan_docs": len(non), "nonscan_pages": tot(non, "pages"),
            "nonscan_old_ocr_pages": tot(non, "old_ocr"), "nonscan_new_ocr_pages": tot(non, "new_ocr"),
            "nonscan_newly_ocr_pages": tot(non, "newly_ocr"),
            "nonscan_no_longer_ocr_pages": tot(non, "no_longer_ocr"),
            "nonscan_changed_br_pages": tot(non, "changed_br"),
            "nonscan_changed_other_pages": tot(non, "changed_other"),
            "nonscan_held_by_raw_pages": tot(non, "held_by_raw"),
            "nonscan_held_by_raw_docs": sum(d["held_by_raw"] > 0 for d in non),
            "nonscan_cover_old_ocr": tot(non, "cover_old"), "nonscan_cover_new_ocr": tot(non, "cover_new"),
            "nonscan_img_cover_pages": tot(non, "img_cover_pages"),
            "nonscan_img_cover_old_ocr": tot(non, "img_cover_old_ocr"),
            "nonscan_img_cover_new_ocr": tot(non, "img_cover_new_ocr"),
        }
    return out


# 이름 오른 문서의 기대(비스캔 문서는 옛 규칙과 같고, 스탬프 스캔본은 전 쪽 OCR)
NAMED_EXPECT = {
    "KCI_FI002252358": ("이미지 표지(0쪽)는 옛·새 모두 ODL 채택",
                        lambda d: not d["doc_is_scan"] and d["cover_old"] == 0 and d["cover_new"] == 0),
    "KCI_FI003011274": ("본문이 이미지인 4쪽은 옛·새 모두 OCR (비스캔, 쪽 수 같음)",
                        lambda d: not d["doc_is_scan"] and d["old_ocr"] == d["new_ocr"] and d["new_ocr"] >= 4),
    "KCI_FI001141801": ("비스캔, 옛·새 OCR 쪽 같음",
                        lambda d: not d["doc_is_scan"] and d["old_ocr"] == d["new_ocr"]),
    "KCI_FI002025246": ("스탬프 스캔본: 옛 OCR 0쪽 -> 새 전 쪽",
                        lambda d: d["doc_is_scan"] and d["old_ocr"] == 0 and d["new_ocr"] == d["pages"]),
}


def run_checks(summary: dict, docs: list[dict]) -> list[dict]:
    checks = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    for g, s in summary.items():
        add(f"{g}: OCR 에서 빠진 쪽 0 (VLM 상한 전, 모든 문서)", s["removed_uncapped_pages"] == 0,
            f"removed_uncapped_pages={s['removed_uncapped_pages']}")
        add(f"{g}: 비스캔 문서 OCR 에서 빠진 쪽 0 (VLM 상한 후)", s["nonscan_no_longer_ocr_pages"] == 0,
            f"no_longer_ocr={s['nonscan_no_longer_ocr_pages']} newly_ocr={s['nonscan_newly_ocr_pages']}")
        add(f"{g}: 비스캔 문서는 <br> 길이 말고는 옛 규칙과 같다", s["nonscan_changed_other_pages"] == 0,
            f"changed_other={s['nonscan_changed_other_pages']} changed_br={s['nonscan_changed_br_pages']}")
        add(f"{g}: 비스캔 문서 표지 OCR 새 <= 옛", s["nonscan_cover_new_ocr"] <= s["nonscan_cover_old_ocr"],
            f"old={s['nonscan_cover_old_ocr']} new={s['nonscan_cover_new_ocr']}")
        add(f"{g}: 비스캔 문서 이미지 쪽 OCR 새 <= 옛", s["nonscan_img_cover_new_ocr"] <= s["nonscan_img_cover_old_ocr"],
            f"pages={s['nonscan_img_cover_pages']} old={s['nonscan_img_cover_old_ocr']} new={s['nonscan_img_cover_new_ocr']}")
        add(f"{g}: 스캔본 문서 OCR 쪽 새 >= 옛", s["scan_new_ocr_pages"] >= s["scan_old_ocr_pages"],
            f"old={s['scan_old_ocr_pages']} new={s['scan_new_ocr_pages']}")
    if "fail_block" in summary:
        s = summary["fail_block"]
        add("fail_block: 모두 스캔본, 옛 규칙으로는 OCR 0쪽, 새 규칙은 문서마다 OCR 가 늘어난다",
            s["scan_docs"] == s["docs"] and s["scan_docs_old_zero"] == s["docs"] and s["scan_docs_gained"] == s["docs"],
            f"docs={s['docs']} scan={s['scan_docs']} old_zero={s['scan_docs_old_zero']} gained={s['scan_docs_gained']}")
    named = {d["id"]: d for d in docs if d["group"] == "named_cases"}
    for pid, (what, ok) in NAMED_EXPECT.items():
        if pid in named:
            d = named[pid]
            add(f"{pid}: {what}", ok(d),
                f"scan={d['doc_is_scan']} old_ocr={d['old_ocr']} new_ocr={d['new_ocr']} pages={d['pages']} "
                f"cover={d['cover_old']}->{d['cover_new']}")
    return checks


def provenance(args, workers: int, elapsed: float) -> dict:
    def git(*a: str) -> str:
        try:
            return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True,
                                  encoding="utf-8", timeout=30).stdout.strip()
        except Exception:  # noqa: BLE001
            return ""

    from core.config import get_settings
    c = get_settings()
    cfg = {
        "EXTRACT_MIN_CHARS_PER_PAGE": c.EXTRACT_MIN_CHARS_PER_PAGE, "VLM_MAX_PAGES_PER_DOC": c.VLM_MAX_PAGES_PER_DOC,
        "SCAN_REPEAT_LINE_RATIO": c.SCAN_REPEAT_LINE_RATIO, "SCAN_SHORT_PAGE_RATIO": c.SCAN_SHORT_PAGE_RATIO,
        "SCAN_MIN_PAGES": c.SCAN_MIN_PAGES,
    }
    used = {"EXTRACT_MIN_CHARS_PER_PAGE": MIN_CHARS, "VLM_MAX_PAGES_PER_DOC": VLM_CAP,
            "SCAN_REPEAT_LINE_RATIO": REPEAT_RATIO, "SCAN_SHORT_PAGE_RATIO": SHORT_RATIO, "SCAN_MIN_PAGES": SCAN_MIN_PAGES}
    sha = hashlib.sha256((ROOT / "app/services/ingestion/page_routing.py").read_bytes()).hexdigest()[:12]
    return {
        "head": git("rev-parse", "HEAD"), "app_dirty": git("status", "--porcelain", "--", "app/").splitlines(),
        "page_routing_sha256": sha, "pymupdf": fitz.VersionBind, "python": sys.version.split()[0],
        "seed": args.seed, "per_group": args.per_group, "workers": workers, "elapsed_sec": round(elapsed),
        "settings_defaults_match": cfg == used, "settings_defaults": cfg,
    }


def fmt_tables(summary: dict) -> str:
    def pct(a: int, b: int) -> str:
        return f"{100 * a / b:.1f}%" if b else "-"

    lines = ["전체 (OCR 쪽 = VLM 쪽수 상한 60 적용 후)", "",
             "| 묶음 | 문서 | 쪽 | 스캔본 | 옛 OCR 쪽 | 새 OCR 쪽 | OCR 쪽 비율 옛 -> 새 | 문서당 증가 쪽 |",
             "|---|---|---|---|---|---|---|---|"]
    for g, s in summary.items():
        per_doc = (s["new_ocr_pages"] - s["old_ocr_pages"]) / s["docs"] if s["docs"] else 0
        lines.append(f"| {g} | {s['docs']} | {s['pages']} | {s['scan_docs']} | {s['old_ocr_pages']} | {s['new_ocr_pages']} "
                     f"| {pct(s['old_ocr_pages'], s['pages'])} -> {pct(s['new_ocr_pages'], s['pages'])} | {per_doc:+.2f} |")
    lines += ["", "스캔본 문서", "",
              "| 묶음 | 스캔본 | 쪽 | 옛 OCR 쪽 | 새 OCR 쪽 | 옛 규칙으로 OCR 0쪽이던 스캔본 | OCR 가 늘어난 스캔본 |",
              "|---|---|---|---|---|---|---|"]
    for g, s in summary.items():
        lines.append(f"| {g} | {s['scan_docs']} | {s['scan_pages']} | {s['scan_old_ocr_pages']} | {s['scan_new_ocr_pages']} "
                     f"| {s['scan_docs_old_zero']} | {s['scan_docs_gained']} |")
    lines += ["", "비스캔 문서", "",
              "| 묶음 | 문서 | 쪽 | 옛 OCR 쪽 | 새 OCR 쪽 | 새로 OCR | OCR 에서 빠짐 | <br> 길이만의 변화 | 그 밖의 변화 "
              "| 표지 OCR 옛 / 새 | 이미지 쪽 | 이미지 쪽 OCR 옛 / 새 | 원래 길이로 OCR 유지 쪽(문서) |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for g, s in summary.items():
        lines.append(f"| {g} | {s['nonscan_docs']} | {s['nonscan_pages']} | {s['nonscan_old_ocr_pages']} | {s['nonscan_new_ocr_pages']} "
                     f"| {s['nonscan_newly_ocr_pages']} | {s['nonscan_no_longer_ocr_pages']} | {s['nonscan_changed_br_pages']} "
                     f"| {s['nonscan_changed_other_pages']} | {s['nonscan_cover_old_ocr']} / {s['nonscan_cover_new_ocr']} "
                     f"| {s['nonscan_img_cover_pages']} | {s['nonscan_img_cover_old_ocr']} / {s['nonscan_img_cover_new_ocr']} "
                     f"| {s['nonscan_held_by_raw_pages']} ({s['nonscan_held_by_raw_docs']}) |")
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="round07 short-page routing: old rule vs new rule on real KCI PDFs (fitz only)")
    ap.add_argument("--per-group", type=int, default=200, help="random docs for pre2005 and digital")
    ap.add_argument("--seed", type=int, default=20261001)
    ap.add_argument("--workers", type=int, default=min(6, os.cpu_count() or 1))
    ap.add_argument("--fail-limit", type=int, default=0, help="use only the first N fail_block docs (0 = all)")
    ap.add_argument("--front-target", type=int, default=FRONT_TARGET)
    ap.add_argument("--all-pages", action="store_true", help="write every page to pages.csv")
    ap.add_argument("--out-dir", type=Path, default=HERE)
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):  # cp949 콘솔에서도 한글 표가 깨지지 않게
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    _init_worker()
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker) as ex:
        plan = pick(args, ex)
        uniq = list(dict.fromkeys(p for p, _ in plan))
        print(f"[{time.time() - t0:.0f}s] sample {len(plan)} (unique {len(uniq)} PDFs) - analyzing", file=sys.stderr, flush=True)
        results: dict[str, dict] = {}
        for i, res in enumerate(ex.map(analyze, uniq, chunksize=2), 1):
            results[res["id"]] = res
            if i % 50 == 0 or i == len(uniq):
                print(f"[{time.time() - t0:.0f}s] {i}/{len(uniq)}", file=sys.stderr, flush=True)

    docs, pages, skipped = [], [], []
    omitted = 0
    for pid, group in plan:
        r = results[pid]
        if "skip" in r:
            skipped.append({"id": pid, "group": group, "why": r["skip"]})
            continue
        docs.append({"id": pid, "group": group, **r["doc"]})
        for p in r["pages"]:
            trivial = p["odl_approx"] >= MIN_CHARS and not p["old_ocr"] and not p["new_ocr"]
            if trivial and not args.all_pages:
                omitted += 1
                continue
            pages.append({"id": pid, "group": group, **p})

    write_csv(args.out_dir / "docs.csv", docs)
    write_csv(args.out_dir / "pages.csv", pages)
    summary = aggregate(docs)
    checks = run_checks(summary, docs)
    meta = provenance(args, args.workers, time.time() - t0)
    meta["skipped"] = skipped
    meta["pages_csv_rows"] = len(pages)
    meta["pages_csv_omitted_enough_rows"] = omitted
    out = {"meta": meta, "groups": summary, "checks": checks}
    (args.out_dir / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(fmt_tables(summary))
    print()
    bad = [c for c in checks if not c["ok"]]
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["name"] + "  " + c["detail"])
    print(f"\nchecks: {len(checks) - len(bad)}/{len(checks)} passed; skipped PDFs: {len(skipped)}; "
          f"settings defaults match: {meta['settings_defaults_match']}; app dirty: {meta['app_dirty']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
