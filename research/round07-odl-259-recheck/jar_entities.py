"""jar_entities.py — opendataloader-pdf CLI jar 의 자체 클래스(라이브러리 제외)에서 HTML 엔티티 문자열 상수를 찾는다.

1회성(round07 markdown 이스케이프 되돌리기의 근거). usage: python jar_entities.py LABEL=JAR [LABEL=JAR ...]
클래스 파일의 상수 풀(CONSTANT_Utf8)만 읽는다 — 디컴파일하지 않는다. MarkdownGenerator 의 상수는 모두 찍는다.
"""
import re
import struct
import sys
import zipfile

ENTITY = re.compile(r"&(?:[A-Za-z]+|#\d+|#x[0-9A-Fa-f]+);")
OWN = ("org/opendataloader/", "com/hancom/", "org/verapdf/wcag/")  # 자체 패키지 후보 — 실제 목록은 아래에서 찍는다


def utf8_constants(data: bytes) -> list[str]:
    if data[:4] != b"\xca\xfe\xba\xbe":
        return []
    count = struct.unpack(">H", data[8:10])[0]
    i, idx, out = 10, 1, []
    while idx < count:
        tag = data[i]
        if tag == 1:
            n = struct.unpack(">H", data[i + 1:i + 3])[0]
            out.append(data[i + 3:i + 3 + n].decode("utf-8", "replace"))
            i += 3 + n
        elif tag in (3, 4):
            i += 5
        elif tag in (5, 6):
            i += 9
            idx += 1
        elif tag in (7, 8, 16, 19, 20):
            i += 3
        elif tag in (9, 10, 11, 12, 17, 18):
            i += 5
        elif tag == 15:
            i += 4
        else:
            raise ValueError(f"unknown constant tag {tag}")
        idx += 1
    return out


for arg in sys.argv[1:]:
    label, jar = arg.split("=", 1)
    with zipfile.ZipFile(jar) as z:
        classes = [n for n in z.namelist() if n.endswith(".class")]
        tops = sorted({"/".join(n.split("/")[:2]) for n in classes})
        print(f"== {label}: {len(classes)} classes, top packages: {tops[:40]}")
        hits: dict[str, set[str]] = {}
        for name in classes:
            if not name.startswith(OWN):
                continue
            consts = utf8_constants(z.read(name))
            ents = {e for c in consts for e in ENTITY.findall(c)}
            if ents:
                hits[name] = ents
            if name.endswith("MarkdownGenerator.class"):
                print(f"  {name} — '&' 가 든 상수: {sorted(c for c in consts if '&' in c)}")
                print(f"  {name} — 메서드·필드 이름(일부): {[c for c in consts if 'Markdown' in c or 'Correct' in c or 'escape' in c.lower()][:12]}")
        print(f"  자체 클래스 중 엔티티 상수가 있는 곳: {[(k, sorted(v)) for k, v in sorted(hits.items())] or '없음'}")
