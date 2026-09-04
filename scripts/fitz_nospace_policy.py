"""fitz_nospace_policy.py — 정책 코퍼스 전수의 fitz 문자 수(공백 제외).

ODL 본문 길이는 공백·구조 문자를 뺀 값이므로, 복원율 ODL/fitz 를 재려면
fitz 쪽도 같은 단위로 세어야 한다. 기존 fitz_lengths_policy200.json 은
공백을 포함한 값이라 그대로 나누면 15% 안팎 왜곡된다.
"""
import io, json, os, re, sys
import fitz

SAMPLE = "scripts/policy_sample200.txt"
BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
OUT = "scripts/fitz_nospace_policy.json"

def main():
    names = [l.strip() for l in io.open(SAMPLE, encoding="utf-8") if l.strip()]
    res = json.load(io.open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for i, rel in enumerate(names, 1):
        if rel in res:
            continue
        try:
            d = fitz.open(BASE + rel)
        except Exception as e:
            print("실패 %s: %s" % (rel, e), file=sys.stderr); continue
        res[rel] = [{"page": n, "fitz_ns": len(re.sub(r'\s', '', p.get_text("text")))}
                    for n, p in enumerate(d, 1)]
        d.close()
        if i % 20 == 0 or i == len(names):
            json.dump(res, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
            print("[%d/%d]" % (i, len(names)), file=sys.stderr)
    json.dump(res, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("완료 %d문서 %d쪽" % (len(res), sum(len(v) for v in res.values())), file=sys.stderr)

if __name__ == "__main__":
    main()
