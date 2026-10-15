"""run_ab.py 출력(gen_ab/*.json)의 자동 지표 — 보고서·변형별 평균(회차 평균)과 변형별 평균(보고서 4건 평균).

사용: PYTHONIOENCODING=utf-8 python ab_metrics.py [--detail] [--dump 재인용|군말|일반론|무표기|되받기|참고문헌]
      PYTHONIOENCODING=utf-8 python ab_metrics.py --v2 [--variants base,focus]   → metrics_v2.txt·ab_metrics_v2.json
- 문장 나누기 = synthesizer._sentences(drop_repeats 와 같은 규칙), 무표기·무효 인용 = citations.bind_markers.
- 지표는 화면에 나가는 최종 절(report.sections) 기준이다. 무효 인용만 모델 원출력(drop_repeats 전, build_section 뒤)으로 센다
  — 최종본에서는 이미 지워져 있다. 군말은 원출력도 따로 센다(drop_repeats 가 '본 절에서는…' 을 지우므로).
결과 표는 표준출력, 수치 전부는 ab_metrics.json.

v2(2026-10-14, focus 채택 뒤 검토 지적 반영) — v1 지표와 키는 그대로 두고 더한다(ab_metrics_v1.py = 더하기 전 사본):
- 일반론 v2(_GENERIC_V2): v1 의 꼴은 base 어휘('꾸준히 진행')만 잡아 focus 의 일반론('다양한 방법과 기법이 활용되었다'·
  '…한계를 지니고 있다'·'기초자료를 제공할 수 있다')을 못 셌다. v1 키(generic_*)는 그대로, v2 키를 따로 센다.
- 첫 문장의 하위질문 되받기: 하위질문(절 소제목) 글자 bigram 의 ECHO_MIN 이상이 도입 첫 문장에 있는 절.
- 도입 4문장 초과 절·1문장 요약·향후 과제 0개 절·요약의 참고문헌 꼴(_BIBLIO — '30(3): 222'·'Vol. 3'·'학회지, 39').
- 남의 번호 인용 '[3]' 을 새 후처리(citations.strip_numbered_refs, fix-live 73feb90) 뒤로 다시 센 값(foreign_ref_after).
"""
import difflib
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # rebuild.py(같은 폴더)
import rebuild  # noqa: E402,F401  (SYNTH_AB_APP 또는 저장소 app/ 경로)
import services.research.synthesizer as syn  # noqa: E402

rebuild.JOBS.update({
    "85d2": rebuild.SD + "job_85d2bc0e-541d-4d27-a98f-c0b8fe262701.json",
    "9ba1": rebuild.SD + "job_9ba10849-36e2-417a-bc59-abec8e002c2c.json",
})
from services.research.citations import bind_markers, strip_markers, strip_numbered_refs  # noqa: E402

VARIANTS = ["base", "focus", "attrib", "concise"]
TAGS = ["630e", "d60a", "85d2", "9ba1"]
SIM_PAIR = 0.7

# ── 도입형 일반론 — 구체 내용(숫자) 없이 분야·연구 흐름을 개괄하거나 의의만 말하는 문장 ─────────────────────
_GENERIC = re.compile(
    r"(?:꾸준히|활발히|활발하게|지속적으로|폭넓게|다각도로|다각적으로)\s?(?:진행|이루어|수행|연구|논의|축적|다루어|시도)"
    r"|다양한\s?(?:측면|관점|시각|각도|접근|방식|시도|방향|논의|결과|차원)"
    r"|다양하게\s?(?:나타|이루어|진행|활용|시도|논의|제시|연구|분포)"
    r"|(?:연구|논의|관심)(?:가|이|는|들이)?\s?(?:꾸준히|활발히|증가|확대|늘어)"
    r"|중요한\s?(?:연구\s?)?(?:주제|과제|문제|의미|시사점)"
    r"|중요성(?:을|이)\s?(?:강조|시사|부각|대두|보여)"
    r"|시사점을\s?(?:제공|준다|던져)"
    r"|기여(?:하고자|할 수 있|하는 데)"
    r"|(?:관심|주목)(?:이|을)?\s?(?:높아|증가|커지|받고|받아)"
    r"|연구\s?(?:동향|흐름)(?:을|은|이)\s?(?:파악|살펴|보면|보여)")
_DIGIT = re.compile(r"\d")
# v2 — focus 출력의 일반론 꼴을 더한다. 숫자가 없는 문장만 일반론으로 세는 규칙(_DIGIT)은 v1 과 같다.
# '한계를 지니' 는 문장 끝에서만 — '…한계점을 지니며, 특히 e-서비스 환경에 …' 처럼 한계의 내용이 이어지는 문장은 구체적이다.
# 앞이 '-다는/-라는' 이면('일반화하기 어렵다는 한계를 지닌다') 한계의 내용을 적은 문장이라 뺀다
_GENERIC_V2 = re.compile(
    _GENERIC.pattern
    + r"|다양한\s?(?:방법|기법|접근|도구|연구)[^.]{0,15}?(?:활용|사용|적용|시도|모색|이루어|진행|수행|동원)"
    + r"|(?<!다는\s)(?<!라는\s)한계(?:점)?(?:[과와]\s?과제)?(?:를|을)\s?(?:지니|안고|드러내|가지)[가-힣 ]{0,8}\.?\s*$"
    + r"|몇\s?가지\s?(?:한계|문제|과제)"
    + r"|기초\s?자료(?:를|로)\s?(?:제공|활용|삼)")
ECHO_MIN = 0.6       # 하위질문 bigram 중 이만큼이 첫 문장에 있으면 하위질문을 되받은 첫 문장으로 본다
INTRO_MAX = 4        # 프롬프트의 intro 상한('4문장을 넘기지 않습니다')
# 참고문헌 꼴 — 권(호): 쪽 · pp./Vol./No. · N권 N호 · 쪽 범위 · doi/ISSN/URL · '학회지, 39'
_BIBLIO = re.compile(
    r"\d+\s?\(\s?\d+(?:[-–]\d+)?\s?\)\s?[:：,]\s?\d+"
    r"|\b[Pp]p?\.\s?\d+|\b[Vv]ol\.?\s?\d+|\b[Nn]o\.\s?\d+"
    r"|\d+\s?권\s?\d+\s?호|제\s?\d+\s?권|\d+[-–]\d+\s?쪽"
    r"|doi|DOI|ISSN|https?://"
    r"|[가-힣A-Za-z]+(?:학회지|학회논문지|저널|Journal)\s?,\s?\d+")


def is_generic(sentence: str, pattern: re.Pattern = _GENERIC) -> bool:
    t = strip_markers(sentence)
    return bool(pattern.search(t)) and not _DIGIT.search(t)

# ── '본 절에서는' 류 군말 — 절·보고서 자신을 가리키거나 할 일을 예고하는 문장 ────────────────────────────
_META_HEAD = re.compile(r"^(?:본|이)\s?(?:절|장|보고서|섹션|글)(?:에서는|에서|은|는|의)\s")
_META_PRESENT = re.compile(
    r"(?:살펴|알아|분석|검토|정리|고찰|논의|파악|제시|탐색|규명|조명|요약|종합)(?:하|해)?\s?(?:보|봐)?고자\s?한다"
    r"|(?:살펴본다|알아본다|다룬다|정리한다|검토한다|논의한다|요약한다|초점을\s?맞춘다)\s*\.?$")
# 남의 연구가 주어인 문장('… 개선 연구는 … 제시하고자 한다')은 그 논문의 목적을 옮긴 것 — '본 연구' 는 보고서 자신으로 읽혀 군말로 센다
_THIRD_SUBJECT = re.compile(r"(?:연구|논문|연구들|고찰|분석|조사)(?:은|는|에서는|들은)\s")


def is_meta(sentence: str) -> bool:
    """'본 절에서는 … 살펴본다' 류 — 절·보고서 자신을 가리키거나 할 일을 예고하는 문장."""
    t = strip_markers(sentence).strip()
    if _META_HEAD.match(t) or re.search(r"다음과\s?같다", t):
        return True
    if _META_PRESENT.search(t):
        return bool(re.search(r"본\s?연구", t)) or not _THIRD_SUBJECT.search(t)
    return False


# ── 재인용 — 대목 속 다른 연구의 결과를 전하는 문장 ─────────────────────────────────────────────────────
_YEAR = r"(?:19|20)\d{2}[a-z]?"
_CITE_AY = re.compile(
    rf"[가-힣]{{2,4}}\s*(?:외|등)?\s*\(\s*{_YEAR}"                       # 권희연 등(2010)
    rf"|[A-Z][A-Za-z\-]+(?:\s*(?:,|&|and|와|과|et al\.?)\s*[A-Z][A-Za-z\-]+)*\s*(?:et al\.?)?\s*\(\s*{_YEAR}"  # Cho(2006)
    rf"|\([^()]*?[가-힣A-Za-z][^()]*?,\s*{_YEAR}[^()]*\)")              # (Kwak, 2009)·(이현경, 서현, 2009)
_CITE_NUM = re.compile(
    r"\[\d{1,3}(?:\s*[,\-–]\s*\d{1,3})*\]"                               # 번호 인용 [3]·[33]·[3,4]
    r"|(?<=[.다])\d{1,2}\)")                                              # 각주 번호 '…왔다.6)'
_CITE = re.compile(f"{_CITE_AY.pattern}|{_CITE_NUM.pattern}")
_FOREIGN_REF = re.compile(r"\[\d{1,3}(?:\s*[,\-–]\s*\d{1,3})*\]")
_RECITE_WORDS = re.compile(
    r"(?<!본 )(?<!본)(?:연구\s?)?(?:결과)?에\s?따르면|대다수의\s?연구|많은\s?연구들?(?:은|에서|이)|최근(?:의)?\s?연구들?(?:은|에서|이)"
    r"|기존(?:의)?\s?연구들?(?:은|에서|이)|선행\s?연구들?(?:은|에서|이|에\s?의하면|결과)|여러\s?연구들?(?:은|에서|이)")
# 그 논문 자신의 방법을 적고 방법론 문헌을 괄호로 단 문장('조사 연구방법을 사용하였다 (Schiavetti & Metz, 1997)')은
# 남의 결과를 전하는 것이 아니다 — 자기 행위 동사가 있고 전하는 말(보고·지적·밝혔·확인·에 따르면 …)이 없으면 뺀다
_SELF_METHOD = re.compile(r"(?:사용|실시|정|구성|측정|결정|선정|채택|활용|적용)(?:하였다|했다|하였으며|하였고)")
_REPORTING = re.compile(r"보고|지적|밝혔|밝힌|나타났|나타난|확인|제안|주장|에\s?따르면|고\s?한다|다고|라고|보였")
_SELF = re.compile(r"본\s?연구")
# 문헌 분석 논문이 스스로 센 결과('… 연구가 57편(50.4%)으로 … (정예리･이숙희, 2010; …)')는 그 논문의 발견이다 — 괄호 인용은 예시다
_REVIEW_COUNT = re.compile(r"\d+\s?편")
_NAMES = re.compile(r"[가-힣]{2,4}(?=\s*(?:외|등)?\s*\(\s*(?:19|20)\d{2})|[A-Z][a-z]{2,}")
_YEARS = re.compile(_YEAR)
# 출력 문장이 '남의 연구' 임을 밝히는 말
_ATTRIB_WORDS = re.compile(
    r"선행|에\s?따르면|기존(?:의)?\s?연구|다른\s?연구|이전\s?연구|일부\s?연구|대다수의\s?연구|많은\s?연구|재인용|인용|검토|소개|문헌"
    r"|등의\s?연구|외의\s?연구|연구들|연구에서는|연구에\s?의하면|보고된\s?바")
_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
_WORD = re.compile(r"[\W_]+")
COVER_MIN = 0.5      # 출력 문장 글자 bigram 중 이만큼이 한 대목 문장에 있으면 그 문장을 옮긴 것으로 본다
COVER_MARGIN = 0.05  # 재인용 문장이 그 논문 자신의 문장보다 이만큼 더 맞아야 재인용을 옮긴 것으로 본다


def _key(s: str) -> str:
    return _WORD.sub("", strip_markers(s))


def _bigrams(s: str) -> set[str]:
    k = _key(s)
    return {k[i:i + 2] for i in range(len(k) - 1)}


def _ratio(a: str, b: str) -> float:
    sm = difflib.SequenceMatcher(None, a, b)
    if sm.real_quick_ratio() < SIM_PAIR - 0.2 or sm.quick_ratio() < SIM_PAIR - 0.2:
        return min(sm.quick_ratio(), 0.5)
    return sm.ratio()


def excerpt_units(text: str) -> list[dict]:
    """대목을 문장으로 자르고 재인용 여부를 단다. 앞 문장이 인용을 소개하고 '이 연구결과에 따르면' 으로 이어 가는 꼴을
    잡으려고 재인용 표지는 문장 단위로 본다."""
    out = []
    for s in _SPLIT.split(text):
        s = s.strip(" -\t")
        if len(_key(s)) < 6:
            continue
        own = (_SELF_METHOD.search(s) and not _REPORTING.search(s)) or _REVIEW_COUNT.search(s)
        strong = (bool(_CITE_AY.search(s)) and not own) or bool(_RECITE_WORDS.search(s))
        weak = bool(_CITE_NUM.search(s)) and not own
        recite = (strong or weak) and not _SELF.search(s)
        out.append({"text": s, "recite": recite, "kind": "강" if strong else "약", "bg": _bigrams(s)})
    return out


def excerpt_names(text: str) -> tuple[set[str], set[str]]:
    names, years = set(), set()
    for m in _CITE.finditer(text):
        frag = m.group(0)
        names.update(n for n in _NAMES.findall(frag) if n not in {"Abstract"})
        years.update(y[:4] for y in _YEARS.findall(frag))
    return names, years


def attributed(sentence: str, names: set[str], years: set[str]) -> bool:
    """출력 문장이 남의 연구임을 밝혔는가 — 출처 표현, 대목 인용의 저자 이름, 인용 꼴의 연도('(2010)'·'2010년 연구')."""
    if _ATTRIB_WORDS.search(sentence):
        return True
    if any(n in sentence for n in names):
        return True
    return any(re.search(rf"\(\s*{y}|{y}\s*\)|{y}년?(?:의)?\s?(?:연구|논문|조사)", sentence) for y in years)


def recite_check(sentence: str, eids: list[str], units: dict[str, list[dict]],
                 cites: dict[str, tuple[set, set]]) -> dict | None:
    """출력 문장 하나가 대목의 재인용 문장을 옮겼는지. 옮겼으면 {eid, src, cover, attributed}."""
    bg = _bigrams(sentence)
    if len(bg) < 8:
        return None
    best_r, best_n = (0.0, None, None), 0.0
    for e in eids:
        for u in units.get(e, []):
            if not u["bg"]:
                continue
            cov = len(bg & u["bg"]) / len(bg)
            if u["recite"]:
                if cov > best_r[0]:
                    best_r = (cov, e, u)
            else:
                best_n = max(best_n, cov)
    cov, e, unit = best_r
    if e is None or cov < COVER_MIN or cov < best_n + COVER_MARGIN:
        return None
    names, years = cites.get(e, (set(), set()))
    return {"eid": e, "src": unit["text"], "kind": unit["kind"], "cover": round(cov, 2),
            "attributed": attributed(sentence, names, years) and not _FOREIGN_REF.search(sentence)}


def section_items(sec: dict, by_cnts: dict) -> list[tuple[str, str, list[str]]]:
    """(필드, 문장, 근거 번호들). 도입·과제는 문장의 마커, 요약은 그 논문."""
    items = []
    for s in syn._sentences(sec["intro"]):
        items.append(("intro", s, bind_markers(s, set(by_cnts.values())).used))
    for p in sec["papers"]:
        e = by_cnts.get(p["cnts_id"])
        for s in syn._sentences(p["summary"]):
            items.append(("summary", s, [e]))
    for f in sec["future"]:
        items.append(("future", f["text"], list(f.get("evidence") or [])))
    return items


def job_metrics(r: dict, st) -> dict:
    by_cnts = {ev.cnts_id: eid for eid, ev in st.evidence.items()}
    secs = r["sections"] or []
    m = {}
    calls = r["calls"]
    m["calls"] = len(calls)
    m["retries"] = len(calls) - len(secs) if secs else len(calls)
    m["format_bad_calls"] = sum(1 for c in calls if c["issues"])
    m["truncated"] = sum(1 for c in calls if c.get("finish") == "length")
    m["failed_sections"] = sum(1 for s in (r["pre_final"] or []) if s.get("failed"))
    m["job_error"] = int(bool(r.get("error")))

    # 절 사이 유사도 — 도입 문장 + 향후 과제(최종본), 다른 절끼리의 모든 쌍
    raw_sents = [(k, x) for k, s in enumerate(secs) for x in [*syn._sentences(s["intro"]), *(f["text"] for f in s["future"])]]
    sents = [(k, _key(x), x) for k, x in raw_sents if len(_key(x)) >= 8]
    best, pairs, gen_pairs, gen_pairs_v2, pair_list = 0.0, 0, 0, 0, []

    def _is_generic(x):
        return is_generic(x, _GENERIC)
    for i in range(len(sents)):
        for j in range(i + 1, len(sents)):
            if sents[i][0] == sents[j][0]:
                continue
            v = _ratio(sents[i][1], sents[j][1])
            best = max(best, v)
            if v >= SIM_PAIR:
                pairs += 1
                gen_pairs += _is_generic(sents[i][2]) or _is_generic(sents[j][2])
                gen_pairs_v2 += is_generic(sents[i][2], _GENERIC_V2) or is_generic(sents[j][2], _GENERIC_V2)
                pair_list.append((round(v, 2), sents[i][0] + 1, sents[j][0] + 1, sents[i][2][:80], sents[j][2][:80]))
    m["xsec_max_sim"] = round(best, 3)
    m["xsec_pairs_07"] = pairs
    m["xsec_pairs_07_generic"] = gen_pairs
    m["xsec_pairs_07_generic_v2"] = gen_pairs_v2
    m["_pairs"] = pair_list
    # 같은 논문 요약의 절 사이 유사도(참고)
    by_paper = defaultdict(list)
    for k, s in enumerate(secs):
        for p in s["papers"]:
            if p["summary"]:
                by_paper[p["cnts_id"]].append((k, _key(p["summary"])))
    m["same_paper_summ_pairs_07"] = sum(1 for lst in by_paper.values() for i in range(len(lst)) for j in range(i + 1, len(lst))
                                        if _ratio(lst[i][1], lst[j][1]) >= SIM_PAIR)

    # 무표기(최종본) — bind_markers 의 unmarked(도입·과제)
    unmarked, unmarked_list = 0, []
    for k, s in enumerate(secs):
        valid = {by_cnts[p["cnts_id"]] for p in s["papers"] if p["cnts_id"] in by_cnts}
        for t in [s["intro"], *(f["text"] for f in s["future"])]:
            n = bind_markers(t, valid).unmarked
            unmarked += n
            if n:
                unmarked_list += [(k + 1, x) for x in syn._sentences(t) if not re.search(r"\[E\d+\]", x)]
    m["unmarked"] = unmarked
    m["foreign_ref"] = sum(1 for sec in secs for t in [sec["intro"], *(p["summary"] for p in sec["papers"]),
                                                       *(f["text"] for f in sec["future"])]
                           for x in syn._sentences(t) if _FOREIGN_REF.search(x))
    m["_unmarked"] = unmarked_list

    # 무효 인용 — 모델 원출력(build_section 뒤, drop_repeats 전)의 도입·과제에서 그 절 근거에 없는 번호·못 읽는 표기
    invalid = 0
    for k, s in enumerate(secs):
        d = r["dropped"].get(s["heading"])
        if not d:
            continue
        valid = {by_cnts[p["cnts_id"]] for p in s["papers"] if p["cnts_id"] in by_cnts}
        for t in [d["intro_before"], *d["future_before"]]:
            res = bind_markers(t, valid)
            invalid += len(res.dropped) + len(res.unparsed)
    m["invalid_cites"] = invalid
    m["drop_repeats_removed"] = sum(len(d["removed"]) for d in r["dropped"].values())

    # 분량
    n_sec = max(len(secs), 1)
    intro_n = [len(syn._sentences(s["intro"])) for s in secs]
    summ_n = [len(syn._sentences(p["summary"])) for s in secs for p in s["papers"] if p["summary"]]
    m["intro_sent_per_sec"] = sum(intro_n) / n_sec
    m["summ_sent_per_paper"] = sum(summ_n) / max(len(summ_n), 1)
    m["future_per_sec"] = sum(len(s["future"]) for s in secs) / n_sec
    m["sent_per_sec"] = (sum(intro_n) + sum(summ_n) + sum(len(s["future"]) for s in secs)) / n_sec
    m["chars_per_sec"] = sum(len(strip_markers(s["intro"])) + sum(len(p["summary"]) for p in s["papers"])
                             + sum(len(strip_markers(f["text"])) for f in s["future"]) for s in secs) / n_sec
    m["empty_summaries"] = sum(1 for s in secs for p in s["papers"] if not p["summary"])
    m["introless"] = sum(1 for s in secs if not s["intro"])

    # 도입형 일반론 — 첫 문장이 일반론인 절 수, 도입 안 일반론 문장 총수(숫자 없는 것만)
    gen_first, gen_all, gen_list = 0, 0, []
    for k, s in enumerate(secs):
        ss = syn._sentences(s["intro"])
        for i, x in enumerate(ss):
            g = bool(_GENERIC.search(strip_markers(x))) and not _DIGIT.search(strip_markers(x))
            if g:
                gen_all += 1
                gen_list.append((k + 1, i + 1, x))
                if i == 0:
                    gen_first += 1
    m["generic_first"] = gen_first
    m["generic_all"] = gen_all
    m["_generic"] = gen_list

    # ── v2 ─────────────────────────────────────────────────────────────────────────────────────────────
    intro_ss = [syn._sentences(s["intro"]) for s in secs]
    # 일반론 v2 — 도입 문장(숫자 없는 것만), 첫 문장
    gen2 = [(k + 1, i + 1, x) for k, ss in enumerate(intro_ss) for i, x in enumerate(ss) if is_generic(x, _GENERIC_V2)]
    m["generic_first_v2"] = sum(1 for _, i, _ in gen2 if i == 1)
    m["generic_all_v2"] = len(gen2)
    m["_generic_v2"] = gen2
    # 첫 문장의 하위질문 되받기 — 하위질문(소제목) bigram 의 ECHO_MIN 이상이 첫 문장에 있는 절
    echo = []
    for k, (s, ss) in enumerate(zip(secs, intro_ss)):
        q = _bigrams(s["heading"])
        if ss and q:
            cov = len(q & _bigrams(ss[0])) / len(q)
            if cov >= ECHO_MIN:
                echo.append((k + 1, round(cov, 2), s["heading"], ss[0]))
    m["echo_first"] = len(echo)
    # 되받은 첫 문장 대부분은 하위질문을 주어로 되풀이한 뒤 답을 잇는다('…주요 연구 대상 집단은 취학 전 연령의 아동이다').
    # 답 없이 되받기만 한 것('…측정하기 위해 다양한 방법 및 기법이 사용되었다')은 일반론 v2 와 겹치는 것으로 따로 센다
    m["echo_generic"] = sum(1 for _, _, _, x in echo if is_generic(x, _GENERIC_V2))
    m["_echo"] = echo
    # 분량 규칙 — 도입 상한 초과 절, 1문장 요약, 향후 과제 0개 절
    m["n_sections"] = len(secs)
    m["intro_over4"] = sum(1 for ss in intro_ss if len(ss) > INTRO_MAX)
    m["intro_over4_ratio"] = m["intro_over4"] / n_sec
    m["intro_max"] = max((len(ss) for ss in intro_ss), default=0)
    m["summ_total"] = len(summ_n)
    m["summ_one"] = sum(1 for n in summ_n if n == 1)
    m["summ_one_ratio"] = m["summ_one"] / max(len(summ_n), 1)
    m["future_zero"] = sum(1 for s in secs if not s["future"])
    # 요약의 참고문헌 꼴 — 참고문헌 목록뿐인 대목을 받은 요약이 서지를 그대로 옮긴다(편 수와 문장 수)
    bib = [(k + 1, p["cnts_id"], x) for k, s in enumerate(secs) for p in s["papers"]
           for x in syn._sentences(p["summary"]) if _BIBLIO.search(x)]
    m["biblio_summ"] = len({(k, c) for k, c, _ in bib})
    m["biblio_summ_sent"] = len(bib)
    m["_biblio"] = bib
    # 남의 번호 인용 — 새 후처리(strip_numbered_refs) 뒤로 다시 센다
    m["foreign_ref_after"] = sum(1 for sec in secs for t in [sec["intro"], *(p["summary"] for p in sec["papers"]),
                                                             *(f["text"] for f in sec["future"])]
                                 for x in syn._sentences(strip_numbered_refs(t)) if _FOREIGN_REF.search(x))

    # 군말 — 최종본(도입·과제)과 원출력(drop_repeats 전 도입·과제)
    def _meta_count(texts):
        return [x for t in texts for x in syn._sentences(t) if is_meta(x)]
    fin = _meta_count([t for s in secs for t in [s["intro"], *(f["text"] for f in s["future"])]])
    raw = _meta_count([t for d in r["dropped"].values() for t in [d["intro_before"], *d["future_before"]]])
    m["meta_final"] = len(fin)
    m["meta_raw"] = len(raw)
    m["_meta"] = fin + [f"(원출력) {x}" for x in raw if x not in fin]

    # 재인용 — 대목의 재인용 문장을 옮긴 출력 문장, 그중 남의 연구임을 밝히지 않은 것(오귀속 의심)
    units, cites = {}, {}
    for heading, ex in r["excerpts"].items():
        for e, v in ex.items():
            # 같은 논문이 절마다 다른 대목을 받는다 — 절별로 따로 둔다
            units[(heading, e)] = excerpt_units(v["text"])
            cites[(heading, e)] = excerpt_names(v["text"])
    used, suspect, suspect_summ, suspect_strong, marked, rec_list = 0, 0, 0, 0, 0, []
    for k, s in enumerate(secs):
        h = s["heading"]
        u = {e: units.get((h, e), []) for e in by_cnts.values()}
        c = {e: cites.get((h, e), (set(), set())) for e in by_cnts.values()}
        prev = None  # (필드, 근거들, 앞 문장 판정)
        for field, x, eids in section_items(s, by_cnts):
            # 출력이 남의 연구를 이름·연도·'에 따르면'·'선행연구' 로 밝힌 문장(참고)
            if _CITE_AY.search(x) or re.search(r"에\s?따르면|선행\s?연구", x):
                marked += 1
            res = recite_check(x, [e for e in eids if e], u, c)
            # 같은 필드에서 바로 앞 문장이 같은 재인용 문장을 밝히며 옮겼으면 이어 쓴 것으로 본다
            if (res and not res["attributed"] and prev and prev[0] == (field, tuple(eids)) and prev[1]
                    and prev[1]["src"] == res["src"] and prev[1]["attributed"]):
                res["attributed"] = True
                res["note"] = "앞 문장에서 밝힘"
            if res:
                used += 1
                if not res["attributed"]:
                    suspect += 1
                    suspect_summ += field == "summary"
                    suspect_strong += res["kind"] == "강"
                rec_list.append({"sec": k + 1, "field": field, "sentence": x, **res})
            prev = ((field, tuple(eids)), res)
    m["recite_used"] = used
    m["recite_suspect"] = suspect
    m["recite_suspect_summary"] = suspect_summ
    m["recite_suspect_strong"] = suspect_strong
    m["recite_marked_out"] = marked
    m["_recite"] = rec_list
    return m


COLS = [
    ("xsec_max_sim", "절간최대유사", 2), ("xsec_pairs_07", "0.7↑쌍", 1), ("xsec_pairs_07_generic", "그중일반론쌍", 1), ("unmarked", "무표기", 1), ("foreign_ref", "남의번호[3]", 1),
    ("invalid_cites", "무효인용", 1), ("retries", "재시도", 1), ("format_bad_calls", "형식문제", 1),
    ("failed_sections", "실패절", 1), ("empty_summaries", "빈요약", 1), ("sent_per_sec", "절당문장", 1), ("intro_sent_per_sec", "도입문장/절", 1),
    ("summ_sent_per_paper", "요약문장/편", 1), ("future_per_sec", "과제/절", 1), ("chars_per_sec", "절당글자", 0),
    ("generic_first", "첫문장일반론", 1), ("generic_all", "일반론문장", 1), ("meta_final", "군말(최종)", 1),
    ("meta_raw", "군말(원출력)", 1), ("recite_used", "재인용옮김", 1), ("recite_suspect", "오귀속의심", 1), ("recite_suspect_summary", "의심중요약", 1), ("recite_suspect_strong", "의심중저자연도", 1),
    ("recite_marked_out", "출처밝힌문장", 1), ("same_paper_summ_pairs_07", "같은논문요약0.7↑", 1),
    ("drop_repeats_removed", "되풀이삭제", 1), ("truncated", "길이잘림", 1),
]

# v2 표 — (키, 이름, 소수 자리). 묶음 제목은 None 키로 적는다
COLS_V2 = [
    (None, "[일반론·되받기]", 0),
    ("generic_first", "첫문장 일반론 v1", 1), ("generic_first_v2", "첫문장 일반론 v2", 1),
    ("generic_all", "도입 일반론 문장 v1", 1), ("generic_all_v2", "도입 일반론 문장 v2", 1),
    ("xsec_pairs_07_generic", "0.7↑쌍 중 일반론 v1", 1), ("xsec_pairs_07_generic_v2", "0.7↑쌍 중 일반론 v2", 1),
    ("echo_first", "첫문장 하위질문 되받기", 1), ("echo_generic", "  그중 일반론 v2", 1),
    (None, "[분량 규칙]", 0),
    ("intro_sent_per_sec", "도입 문장/절", 1), ("intro_over4", "도입 4문장 초과 절", 1),
    ("intro_over4_ratio", "  도입 초과 비율", 2), ("intro_max", "도입 최대 문장", 1),
    ("summ_sent_per_paper", "요약 문장/편", 1), ("summ_one", "1문장 요약(편)", 1), ("summ_one_ratio", "  1문장 요약 비율", 2),
    ("future_per_sec", "향후 과제/절", 1), ("future_zero", "향후 과제 0개 절", 1),
    (None, "[유출]", 0),
    ("biblio_summ", "참고문헌꼴 요약(편)", 1), ("biblio_summ_sent", "  그 문장", 1),
    ("foreign_ref", "남의 번호[3] 문장", 1), ("foreign_ref_after", "  새 후처리 뒤", 1),
]
# 합산(8잡 전부) — (분자 키, 분모 키 또는 None, 이름)
POOLED_V2 = [
    ("generic_first_v2", "n_sections", "첫문장 일반론 v2(절)"), ("echo_first", "n_sections", "첫문장 하위질문 되받기(절)"),
    ("echo_generic", "n_sections", "  그중 일반론 v2(절)"),
    ("intro_over4", "n_sections", "도입 4문장 초과(절)"), ("summ_one", "summ_total", "1문장 요약(편)"),
    ("future_zero", "n_sections", "향후 과제 0개(절)"), ("biblio_summ", "summ_total", "참고문헌꼴 요약(편)"),
    ("foreign_ref", None, "남의 번호[3] 문장"), ("foreign_ref_after", None, "  새 후처리 뒤"),
]


def collect():
    states = {t: rebuild.state_of(t)[1] for t in TAGS}
    rows = defaultdict(list)
    for f in sorted((HERE / "gen_ab").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        rows[(r["variant"], r["tag"])].append((r["run"], job_metrics(r, states[r["tag"]])))
    return rows


def main_v2():
    """--v2: base·focus(기본) 기존 출력으로 v2 지표를 세어 metrics_v2.txt·ab_metrics_v2.json 에 쓴다."""
    variants = (sys.argv[sys.argv.index("--variants") + 1].split(",") if "--variants" in sys.argv else ["base", "focus"])
    dump = sys.argv[sys.argv.index("--dump") + 1] if "--dump" in sys.argv else None
    rows = collect()
    keys = [c for c, _, _ in COLS_V2 if c]
    agg = {(v, t): {c: statistics.mean(m[c] for _, m in lst) for c in keys}
           for (v, t), lst in rows.items() if v in variants}
    by_v = {v: {c: statistics.mean(agg[(v, t)][c] for t in TAGS if (v, t) in agg) for c in keys}
            for v in variants}
    pooled = {v: {k: sum(m[k] for (vv, _), lst in rows.items() if vv == v for _, m in lst)
                  for k in {*(a for a, _, _ in POOLED_V2), *(b for _, b, _ in POOLED_V2 if b)}}
              for v in variants}
    for v in variants:
        pooled[v]["intro_max"] = max(m["intro_max"] for (vv, _), lst in rows.items() if vv == v for _, m in lst)
        pooled[v]["jobs"] = sum(len(lst) for (vv, _), lst in rows.items() if vv == v)

    def fmt(x, d):
        return f"{x:.{d}f}" if isinstance(x, float) else str(x)

    out = []
    out.append("# 종합 프롬프트 A/B 지표 v2 — base vs focus (gen_ab 기존 출력 재계산, 2026-10-14)")
    out.append("# 스크립트: prompt_ab/ab_metrics.py --v2 (v1 지표는 그대로, ab_metrics_v1.py = 더하기 전 사본)")
    out.append("")
    out.append("== 변형별 평균 — 보고서 1건(6절)당, 보고서 4건 × 2회(보고서마다 회차 평균을 낸 뒤 4건 평균)")
    out.append("지표".ljust(24) + "".join(v.rjust(10) for v in variants))
    for c, name, d in COLS_V2:
        if c is None:
            out.append(name)
            continue
        out.append(("  " + name).ljust(24) + "".join(fmt(by_v[v][c], d).rjust(10) for v in variants))
    out.append("")
    out.append("== 합산 — 변형마다 8잡(보고서 4건 × 2회) 전부")
    out.append("지표".ljust(24) + "".join(v.rjust(18) for v in variants))
    for num, den, name in POOLED_V2:
        cells = []
        for v in variants:
            p = pooled[v]
            cells.append((f"{p[num]}/{p[den]} ({p[num] / p[den]:.0%})" if den else str(p[num])).rjust(18))
        out.append(("  " + name).ljust(24) + "".join(cells))
    out.append(("  도입 최대 문장").ljust(24) + "".join(str(pooled[v]["intro_max"]).rjust(18) for v in variants))
    out.append("")
    out.append("== 보고서·변형별(회차 평균)")
    per = ["generic_first_v2", "generic_all_v2", "echo_first", "echo_generic", "intro_over4", "summ_one_ratio", "future_zero",
           "biblio_summ", "foreign_ref"]
    names = {c: n.strip() for c, n, _ in COLS_V2 if c}
    digits = {c: d for c, _, d in COLS_V2 if c}
    out.append("보고서 변형     " + " | ".join(names[k] for k in per))
    for t in TAGS:
        for v in variants:
            if (v, t) in agg:
                out.append(f"{t} {v:8}  " + " | ".join(fmt(agg[(v, t)][k], digits[k]).rjust(len(names[k])) for k in per))
    out.append("")
    out.append("정의")
    out.append("- 일반론 v1 = 기존 _GENERIC(base 어휘: '꾸준히 진행'·'다양한 측면' 등). v2 = v1 + '다양한 방법·기법·접근·도구·연구 … 활용/사용/진행',")
    out.append("  문장 끝 '한계(점)를 지니/안고/드러내/가지'(앞이 '-다는/-라는' 이면 제외), '몇 가지 한계/문제/과제', '기초자료를 제공/활용'.")
    out.append("  둘 다 숫자가 없는 도입 문장만 센다.")
    out.append(f"- 되받기 = 절 소제목(하위질문)의 글자 bigram 중 {ECHO_MIN:.0%} 이상이 도입 첫 문장에 있는 절. 하위질문을 주어로 되풀이하고")
    out.append("  답을 잇는 문장도 든다 — '그중 일반론 v2' 가 답 없이 되받기만 한 첫 문장이다.")
    out.append(f"- 도입 상한 = {INTRO_MAX}문장(프롬프트 규칙). 문장 = synthesizer._sentences. 1문장 요약은 빈 요약을 뺀 편 수가 분모.")
    out.append("- 참고문헌꼴 = '30(3): 222'·'Vol. 3'·'N권 N호'·'N-N쪽'·doi·'학회지, 39' 꼴이 든 요약(편)·문장.")
    out.append("- 남의 번호[3] = '[3]'·'[3, 4]' 꼴이 든 문장(도입·요약·과제). '새 후처리 뒤' = fix-live 73feb90 의 strip_numbered_refs 를 적용한 뒤.")
    text = "\n".join(out)
    print(text)
    (HERE / "metrics_v2.txt").write_text(text + "\n", encoding="utf-8")
    (HERE / "ab_metrics_v2.json").write_text(json.dumps({
        "per_job": {f"{v}_{t}_r{run}": {k: val for k, val in m.items() if not k.startswith("_")}
                    for (v, t), lst in rows.items() if v in variants for run, m in lst},
        "per_report_variant": {f"{v}_{t}": a for (v, t), a in agg.items()},
        "per_variant": by_v, "pooled": pooled}, ensure_ascii=False, indent=1), encoding="utf-8")

    if dump:
        for (v, t), lst in sorted(rows.items(), key=lambda x: (TAGS.index(x[0][1]), VARIANTS.index(x[0][0]))):
            if v not in variants:
                continue
            for run, m in sorted(lst, key=lambda x: x[0]):
                if dump == "일반론":
                    for k, i, x in m["_generic_v2"]:
                        print(f"[일반론v2] {v} {t} r{run} s{k}.{i}: {x[:120]}")
                if dump == "되받기":
                    for k, cov, h, x in m["_echo"]:
                        print(f"[되받기] {v} {t} r{run} s{k} cov{cov}: {h} → {x[:110]}")
                if dump == "참고문헌":
                    for k, c, x in m["_biblio"]:
                        print(f"[참고문헌] {v} {t} r{run} s{k} {c}: {x[:120]}")


def main():
    if "--v2" in sys.argv:
        return main_v2()
    detail = "--detail" in sys.argv
    dump = sys.argv[sys.argv.index("--dump") + 1] if "--dump" in sys.argv else None
    states = {t: rebuild.state_of(t)[1] for t in TAGS}
    rows = defaultdict(list)
    for f in sorted((HERE / "gen_ab").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        m = job_metrics(r, states[r["tag"]])
        rows[(r["variant"], r["tag"])].append((r["run"], m))
    out = {"per_job": {f"{v}_{t}_r{run}": {k: val for k, val in m.items()}
                       for (v, t), lst in rows.items() for run, m in lst}}

    def mean(lst, key):
        return statistics.mean(m[key] for _, m in lst) if lst else float("nan")

    # 보고서·변형별 평균(회차 평균)
    agg = {}
    for (v, t), lst in rows.items():
        agg[(v, t)] = {c: mean(lst, c) for c, _, _ in COLS}
        agg[(v, t)]["n"] = len(lst)
    # 변형별 평균(보고서 평균 → 보고서마다 같은 무게)
    by_v = {}
    for v in VARIANTS:
        ts = [agg[(v, t)] for t in TAGS if (v, t) in agg]
        if ts:
            by_v[v] = {c: statistics.mean(a[c] for a in ts) for c, _, _ in COLS}
            by_v[v]["n"] = sum(a["n"] for a in ts)
    out["per_report_variant"] = {f"{v}_{t}": a for (v, t), a in agg.items()}
    out["per_variant"] = by_v
    (HERE / "ab_metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=list), encoding="utf-8")

    def fmt(x, d):
        return f"{x:.{d}f}" if isinstance(x, float) else str(x)

    print("== 변형별 평균(보고서 4건 × 2회, 보고서마다 회차 평균을 낸 뒤 보고서 평균) — 값은 보고서 1건(6절)당")
    print("지표".ljust(16) + "".join(v.rjust(10) for v in VARIANTS))
    for c, name, d in COLS:
        print(name.ljust(16) + "".join(fmt(by_v[v][c], d).rjust(10) if v in by_v else "-".rjust(10) for v in VARIANTS))
    print("의심/옮김 비율".ljust(16) + "".join(
        (f"{by_v[v]['recite_suspect'] / by_v[v]['recite_used']:.0%}" if by_v.get(v, {}).get("recite_used") else "-").rjust(10)
        for v in VARIANTS))
    print("회수".ljust(16) + "".join(str(by_v.get(v, {}).get("n", 0)).rjust(10) for v in VARIANTS))

    print("\n== 보고서·변형별(회차 평균)")
    keys = ["xsec_max_sim", "xsec_pairs_07", "unmarked", "invalid_cites", "retries", "sent_per_sec", "generic_first",
            "generic_all", "meta_final", "meta_raw", "recite_used", "recite_suspect"]
    names = {c: n for c, n, _ in COLS}
    digits = {c: d for c, _, d in COLS}
    print("보고서 변형    " + " ".join(names[k][:8].rjust(9) for k in keys))
    for t in TAGS:
        for v in VARIANTS:
            if (v, t) in agg:
                print(f"{t} {v:8}  " + " ".join(fmt(agg[(v, t)][k], digits[k]).rjust(9) for k in keys))

    if detail or dump:
        for (v, t), lst in sorted(rows.items(), key=lambda x: (TAGS.index(x[0][1]), VARIANTS.index(x[0][0]))):
            for run, m in sorted(lst, key=lambda x: x[0]):
                if dump in (None, "재인용"):
                    for x in m["_recite"]:
                        flag = ("의심" if not x["attributed"] else "밝힘") + x.get("kind", "")
                        print(f"[재인용 {flag}] {v} {t} r{run} s{x['sec']} {x['field']} {x['eid']} cov{x['cover']}: {x['sentence'][:120]}\n"
                              f"      ← {x['src'][:140]}")
                if dump in (None, "군말"):
                    for x in m["_meta"]:
                        print(f"[군말] {v} {t} r{run}: {x[:120]}")
                if dump in (None, "일반론"):
                    for k, i, x in m["_generic"]:
                        print(f"[일반론] {v} {t} r{run} s{k}.{i}: {x[:120]}")
                if dump in (None, "무표기"):
                    for k, x in m["_unmarked"]:
                        print(f"[무표기] {v} {t} r{run} s{k}: {x[:120]}")
                if dump in (None, "유사"):
                    for p in m["_pairs"]:
                        print(f"[유사] {v} {t} r{run} {p}")


if __name__ == "__main__":
    main()
