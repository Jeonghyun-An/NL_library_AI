"""페르소나 책 14권 v2 — 서버로 옮길 묶음을 만든다 (1회성, 2026-10-23).

render_pdfs.py 로 다시 그린 out/upload/pdf/ 에서 txt 렌더본 14권만 골라 out/v2/pdf/ 에 담고, 해시(sha256s.txt)와 서버에서 돌릴
restage_v2.py·precheck_extract.py 를 함께 둔 뒤 out/persona_books_v2.tar.gz 로 묶는다. 서버에서는 /data/nl-lib/data/persona_books/v2/
에 푼다(컨테이너 안 /app/data/persona_books/v2/). out/persona_books.tar.gz(첫 판)는 옛 표지라 보내지 않는다.

    python render_pdfs.py <14권>   # 표지 문구를 뺀 판으로 다시 그리기
    python bundle_v2.py
"""
import hashlib
import shutil
import sys
import tarfile
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
SRC, OUT = HERE / "out" / "upload" / "pdf", HERE / "out" / "v2"
IDS = ("PSN-MANSEJEON", "PSN-SONAGI", "PSN-JEOKBIN", "PSN-CHUNHYANG", "PSN-HEOSAENG", "PSN-BEAUTY-BEAST", "PSN-RED-CAP",
       "PSN-STUDY-SCARLET", "PSN-DOG-FLANDERS", "PSN-ROBIN-HOOD", "PSN-BULFINCH", "PSN-ANDERSEN", "PSN-DADDY-LONG-LEGS",
       "PSN-PERRAULT")
NOTE = ("SKOVIX 소장자료", "페르소나 에이전트")
sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    (OUT / "pdf").mkdir(parents=True, exist_ok=True)
    lines = []
    for cid in IDS:
        src = SRC / f"{cid}.pdf"
        with fitz.open(src) as d:
            if any(n in d[0].get_text() for n in NOTE):
                sys.exit(f"멈춤 — {src} 1쪽에 문구가 남았다(render_pdfs.py 로 다시 그렸나?)")
        shutil.copy2(src, OUT / "pdf" / src.name)
        lines.append(f"{hashlib.sha256(src.read_bytes()).hexdigest()} {cid}")
    (OUT / "sha256s.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for name in ("restage_v2.py", "precheck_extract.py"):
        shutil.copy2(HERE / name, OUT / name)
    tar = HERE / "out" / "persona_books_v2.tar.gz"
    with tarfile.open(tar, "w:gz") as t:
        t.add(OUT, arcname="v2")
    print(f"{len(lines)}권 → {tar} ({tar.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
