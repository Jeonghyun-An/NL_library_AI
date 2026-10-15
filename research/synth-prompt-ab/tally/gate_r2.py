"""2차 자동 지표 기준 — r2_metrics.json 의 8잡 합(pooled)·평균(per_variant)으로 focus2 가 focus 보다 나쁘지 않은지 본다."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
d = json.loads((here.parent / "r2_metrics.json").read_text(encoding="utf-8"))
jobs = d["per_job"]


def pooled(var, k):
    return sum(v.get(k, 0) or 0 for name, v in jobs.items() if name.startswith(var + "_"))


# 나쁘지 않아야 하는 것(작을수록 좋음)
NOT_WORSE = [
    ("invalid_cites", "무효 인용"),
    ("format_bad_calls", "형식 문제 호출"),
    ("failed_sections", "실패 절"),
    ("retries", "재시도"),
    ("empty_summaries", "빈 요약"),
    ("unmarked", "근거 표시 없는 문장"),
    ("biblio_summ", "참고문헌꼴 요약(편)"),
]
print("== 나쁘지 않을 것 (8잡 합, focus → focus2)")
fails = []
keys0 = set(next(iter(jobs.values())).keys())
for k, label in NOT_WORSE:
    if k not in keys0:
        print(f"  {label:14s} 키 {k} 없음 — 확인 필요")
        continue
    a, b = pooled("focus", k), pooled("focus2", k)
    ok = b <= a
    if not ok:
        fails.append(label)
    print(f"  {label:14s} {a} → {b}  {'OK' if ok else '나쁨'}")

print("\n== 줄어야 할 것 (8잡 합 비율)")
def ratio(var, num, den):
    n = pooled(var, num)
    m = pooled(var, "summ_total") if den == "summ_nonempty" else pooled(var, den)  # r2_metrics.txt 와 같은 분모
    return n, m


for num, den, label in [("summ_one", "summ_nonempty", "1문장 요약"), ("intro_over4", "n_sections", "도입 4문장 초과")]:
    (na, ma), (nb, mb) = ratio("focus", num, den), ratio("focus2", num, den)
    ok = nb / mb < na / ma
    print(f"  {label}: {na}/{ma} ({na/ma:.0%}) → {nb}/{mb} ({nb/mb:.0%})  {'OK' if ok else '안 줄어듦'}")
print("\n자동 지표 기준:", "통과" if not fails else "미달(" + "·".join(fails) + ")")
