"""scripts/bulk_ingest/build_manifest.py — 메타↔PDF 매칭/검증 로직 테스트."""
import json
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "bulk_ingest"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def dataset(tmp_path: Path):
    pdf_dir = tmp_path / "pdfs"
    (pdf_dir / "sub").mkdir(parents=True)
    (pdf_dir / "KCI_FI001.pdf").write_bytes(b"%PDF-1.4 a")
    (pdf_dir / "KCI_FI002_.pdf").write_bytes(b"%PDF-1.4 b")   # 정규화 필요 (끝 _)
    (pdf_dir / "KCI_FI003.pdf").write_bytes(b"%PDF-1.4 c")     # 메타 없음
    (pdf_dir / "sub" / "KCI_FI001.pdf").write_bytes(b"%PDF dup")  # 중복 ID
    (pdf_dir / "KCI_FI005.pdf").write_bytes(b"")               # 0바이트

    wb = Workbook()
    ws = wb.active
    ws.append(["KCI_FI_ID", "TITLE_KR"])
    ws.append(["KCI_FI001", "논문 1"])
    ws.append(["KCI_FI002", "논문 2"])
    ws.append(["KCI_FI004", "PDF 없는 논문"])
    ws.append(["KCI_FI005", "빈 파일 논문"])
    excel = tmp_path / "meta.xlsx"
    wb.save(excel)
    return excel, pdf_dir, tmp_path / "out"


def test_build_manifest_matching(dataset):
    from build_manifest import build_manifest

    excel, pdf_dir, out_dir = dataset
    report = build_manifest(
        excel_paths=[str(excel)],
        pdf_dir=str(pdf_dir),
        out_dir=str(out_dir),
    )

    # 매칭: 001(중복이지만 1개 선택), 002(정규화) — 005는 0바이트로 제외
    assert report["matched"] == 2
    assert report["meta_without_pdf"] == ["KCI_FI004"]
    assert report["pdf_without_meta"] == ["KCI_FI003"]
    assert "KCI_FI001" in report["duplicates"]
    assert "KCI_FI005" in report["zero_size"]

    manifest_path = out_dir / "manifest.jsonl"
    rows = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    by_id = {r["book_id"]: r for r in rows}
    assert set(by_id) == {"KCI_FI001", "KCI_FI002"}
    # object_key 는 평탄 키 originals/{id}.pdf (mc mirror 호환)
    assert by_id["KCI_FI001"]["object_key"] == "originals/KCI_FI001.pdf"
    assert by_id["KCI_FI002"]["title"] == "논문 2"
    assert by_id["KCI_FI002"]["size"] > 0

    report_path = out_dir / "validation_report.json"
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["matched"] == 2


def test_build_manifest_csv_input(tmp_path: Path):
    """CSV 메타 직접 읽기 (대용량 경로)."""
    from build_manifest import build_manifest

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "KCI_FI010.pdf").write_bytes(b"%PDF-1.4 x")
    csv_path = tmp_path / "meta.csv"
    csv_path.write_text(
        "kci_fi_id,title_kr\nKCI_FI010,씨에스브이 논문\n", encoding="utf-8",
    )
    report = build_manifest(
        excel_paths=[str(csv_path)], pdf_dir=str(pdf_dir), out_dir=str(tmp_path / "out"),
    )
    assert report["matched"] == 1
    rows = [json.loads(l) for l in (tmp_path / "out" / "manifest.jsonl")
            .read_text(encoding="utf-8").splitlines()]
    assert rows[0]["book_id"] == "KCI_FI010"
    assert rows[0]["title"] == "씨에스브이 논문"
    assert rows[0]["object_key"] == "originals/KCI_FI010.pdf"


def test_build_manifest_limit(tmp_path: Path):
    """--limit 로 파일럿 서브셋 매니페스트 생성 (리포트는 전체 기준)."""
    from build_manifest import build_manifest

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    for i in range(5):
        (pdf_dir / f"KCI_FI10{i}.pdf").write_bytes(b"%PDF-1.4 z")
    csv_path = tmp_path / "meta.csv"
    lines = ["kci_fi_id,title_kr"] + [f"KCI_FI10{i},t{i}" for i in range(5)]
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = build_manifest(
        excel_paths=[str(csv_path)], pdf_dir=str(pdf_dir),
        out_dir=str(tmp_path / "out"), limit=2,
    )
    assert report["matched"] == 5            # 리포트는 전체
    assert report["manifest_written"] == 2   # 매니페스트엔 2건만
    written = (tmp_path / "out" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(written) == 2
