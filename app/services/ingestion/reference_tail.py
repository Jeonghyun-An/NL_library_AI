"""참고문헌 목록 끝에 붙어 온 논문 뒷부분(투고 정보·키워드·초록 머리·저자 소개·쪽 머리글) 걷기.

paper_enricher.extract_references 는 '참고문헌' 머리 뒤를 다음 멈춤 머리(_REF_STOP — 초록·부록 등)까지 잘라 항목으로 나눈다.
KCI 논문은 참고문헌 뒤에 영문 제목·저자·Abstract·Key words·투고 정보·저자 소개가 이어지는데, 머리 꼴이 '<Abstract>'(ODL 이
'&lt;Abstract&gt;'로 내기도 한다 — 함정 22)·'[Keywords : …]'·'￭국문초록'·'원 고 접 수 일 : …'처럼 멈춤 패턴에 안 걸리면
마지막 항목에 이어 붙거나 항목으로 따로 들어왔다(운영 표본 1,347편 중 약 20% — research/reference-tail-clean). 화면(논문 상세
참고문헌·인용하기)과 딥리드 참고문헌 답에 그대로 보였다.

clean_references 는 저장된 목록을 읽을 때(models.Book.references)와 새로 뽑을 때(extract_references) 같은 규칙으로 쓴다:
- 꼬리 표지(키워드 머리·감싼 초록 머리·저자 소개·교신 저자·회원 배지)가 나온 항목에서 목록을 끊는다. 표지 앞부분은 길이가
  넉넉하면 남긴다(배지 바로 앞의 저자 이름은 떼어 낸다). 꼬리는 목록 끝에 온다.
- 투고 정보(접수·심사·게재 날짜)와 연락처(전자우편)는 2단 조판에서 참고문헌 한가운데에 끼기도 한다 — 그 구간만 지우고, 다음
  항목이 서지 꼴이면 계속 읽고 아니면(다음 논문 제목·영문 제목 등) 거기서 끊는다. 끊을 때 그 항목의 앞 서지는 남긴다.
- 쪽 머리글·바닥글·쪽 번호·밑줄 구분선은 그 항목만 버린다. 줄이 갈려 따로 들어온 출판 연도('1978')는 앞 서지에 다시 붙인다.
지나치게 자르지 않게 한 것(두 차례 표본 검토가 찾은 거짓 양성 — research/reference-tail-clean):
- 초록 머리는 감쌌거나 항목 맨 앞·맨 끝일 때만 본다 — 'Dissertation Abstracts International', APA 의 '…Questionnaire[Abstract].
  Journal …'은 서지다. 키워드 머리는 항목 가운데에서는 대문자 꼴만 본다 — 'Querying keywords: Questions of …'는 서지 제목이다.
- 투고 정보는 낱말 한가운데('특별기고:')와 괄호 안('(최종 수정일: …)' 웹 자료)에서 보지 않고, '일' 없이 ':' 만 있으면 날짜가
  뒤따라야 한다. 'www.kci.go.kr' 워터마크는 홀로 섰을 때만 지운다(서지 URL 'https://uci.kci.go.kr/…'는 그대로).
- 마크다운 제목 머리 일반('###### Ⅰ. 국내문헌'·ODL 이 제목으로 낸 서지)과 머리 없는 영문 제목·저자 줄은 건드리지 않는다.
HTML 이스케이프(&lt; &gt; &amp;)는 풀어서 본다 — 남기는 항목도 푼 글로 낸다.
"""
import html
import re

_OPEN = r"(?:<|\[|【|￭|■|▪|◆|❙|│|\||=+|—+|-{2,}|#{1,6}\s*)"
_CLOSE = r"(?:>|\]|】|❙|│|\||=+|—+|-{2,})"
_ABSTRACT = (r"(?:(?:Korean|English)\s+Abstract|Abstract|ABSTRACT|Abstact|Zusammenfassung|R[ée]sum[ée]"
             r"|논\s*문\s*초\s*록|국\s*문\s*(?:초\s*록|요\s*약)|영\s*문\s*(?:초\s*록|요\s*약)|초\s*록|요\s*약)")
# 항목 가운데의 키워드 머리는 대문자 꼴만('Key words'·'Keywords'·'KEY WORDS'·'Key Concepts')
_KEYWORDS = r"(?:Key\s*-?\s*[Ww]ords?|KEY\s*-?\s*WORDS?|Key\s*[Cc]oncepts?|주\s*제\s*어|키\s*워\s*드|핵\s*심\s*어|검\s*색\s*어)"

# 끊는 표지 — 항목 어디에 있어도
_HARD_TAIL = re.compile("|".join([
    # 키워드 머리 — 뒤에 ':'·'|' (사이에 '(Key words)' 같은 괄호 하나는 허용), 또는 감싼 머리
    _OPEN + r"?\s*" + _KEYWORDS + r"\s*(?:\([^)]{0,20}\))?\s*[:：|]",
    _OPEN + r"\s*" + _KEYWORDS + r"\s*" + _CLOSE,
    # 감싼 초록 머리 — 앞이 항목 시작·공백이고 뒤에 마침표·쉼표가 오지 않을 때(APA '[Abstract].' 는 서지)
    r"(?:^|(?<=\s))" + _OPEN + r"\s*" + _ABSTRACT + r"\s*" + _CLOSE + r"?(?!\s*[.,;])",
    # 항목 끝의 맨 'Abstract'(… 283-303. Abstract)
    r"\s(?:Abstract|ABSTRACT|Abstact)\s*$",
    # 교신 저자·저자 소개('교\s*신'으로 넓히면 줄바꿈으로 갈린 '대학교 신입생'을 자른다 — 붙여 쓴 꼴만)
    r"교신\s*[:：]|교신\s*저자|(?i:corresponding\s+author)|(?i:address\s+(?:reprint\s+requests|correspondence))"
    r"|(?i:correspondence)\s*[:：]|저\s*자\s*소\s*개",
]))
# 연락처 — 2단 조판에서 목록 가운데에 끼기도 해서 투고 정보처럼 다룬다(뒤가 서지 꼴이면 계속 읽는다)
_CONTACT = re.compile(r"(?i:e-?\s*mail)\s*[:：]|전\s*자\s*우\s*편\s*[:：]|이\s*메\s*일\s*[:：]")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 회원 배지 — '김 명 숙(Myungsook Kim) [정회원]'. 바로 앞의 저자 이름은 떼어 낸다
_BADGE = re.compile(r"\[\s*(?:정|종신|학생|준|평|명예)\s*회\s*원\s*\]")
_BADGE_NAME = re.compile(r"(?:#{1,6}\s*)?[가-힣](?:\s?[가-힣]){1,3}\s*(?:\([^()]{1,40}\))?\s*$")
# 연락처 바로 앞의 저자 이름 — 글자 사이를 띄운 꼴('이 승 은(Lee, Sheng Yen)')만. 붙여 쓴 '박영사(…)'는 출판사일 수 있다
_CONTACT_NAME = re.compile(r"[가-힣](?:\s[가-힣]){1,3}\s*(?:\([^()]{1,40}\))?\s*$")
# 항목 맨 앞이면 꼬리 — 감싸지 않은 초록 머리, '이름(漢字):' 꼴 저자 소개
_TAIL_AT_START = re.compile(
    r"^\W*" + _ABSTRACT + r"\b"
    r"|^\s*(?:#{1,6}\s*)?[가-힣]{2,4}\s*\(\s*[一-鿿]{2,4}\s*\)\s*[:：]"
)

# 투고 정보 — '논문접수일 : 2010년 4월 7일', '원 고 접 수 일 : 2019. 12. 27', '접수 일자 : 9월 10일', '게재결정: 2008. 24'.
# 낱말 한가운데('특별기고:')에서는 시작하지 않고, '일' 없이 ':' 만 있으면 숫자 날짜가 뒤따라야 한다
_SUB_LABEL = (r"(?<![가-힣])(?:(?:\d\s*차\s*)?(?:원\s*고|논\s*문|수\s*정\s*본|수\s*정\s*원\s*고|최\s*종|최\s*초)\s*)?"
              r"(?:제\s*출|접\s*수|투\s*고|기\s*고|심\s*사\s*(?:완\s*료)?|수\s*정|게\s*재\s*(?:확\s*정|결\s*정|승\s*인|예\s*정)?)")
_SUB_DATE = r"\s*\(?\s*(?:(?:19|20)\d{2}|\d{1,2})\s*(?:[.\-/년월]\s*\d{0,2}\s*(?:[.\-/월]\s*\d{1,2}\s*[.일]?)?)?\s*\.?\s*\)?"
_SUBMISSION = re.compile(_SUB_LABEL + r"\s*(?:일\s*자?\s*[:：]?(?:" + _SUB_DATE + r")?|[:：]" + _SUB_DATE + r")")
_SUB_JUNK = re.compile(r"[\s/∙·․•|｜【】\[\]()\-–—_]+")

# 쪽 머리글·바닥글 — '28 ｜『노인복지연구』 통권 33호', '- 59 -', '108', '30 教育法學研究', 밑줄 구분선.
# 글머리표 항목('• 玉野和志 1999')과 맨 연도('1978')는 서지 조각이라 쪽 머리글로 보지 않는다
_FURNITURE = [
    re.compile(r"^\s*\d{1,4}\s*[｜|│]\s*\S|[｜|│]\s*\d{1,4}\s*$"),
    re.compile(r"^\s*[-－–]\s*\d{1,4}\s*[-－–]\s*$|^\s*(?!(?:19|20)\d{2}\s*$)\d{1,4}\s*$"),
    re.compile(r"^[#\s]*_{5,}\s*$"),
    re.compile(r"^\s*\d{1,4}\s+[^\d(),.•∙·▪\-]{2,24}$|^(?![\s•∙·▪\-])[^\d(),.]{2,24}\s+(?!(?:19|20)\d{2}\s*$)\d{1,4}\s*$"),
]
_FURNITURE_MAX = 80
_BARE_YEAR = re.compile(r"^\s*(?:19|20)\d{2}[a-z]?\s*$")
_WATERMARK = re.compile(r"(?<![\w/.:])(?:www\.)?kci\.go\.kr(?![\w/.])\s*(?:```\w*)?", re.IGNORECASE)

# 다음 항목이 서지 꼴인가 — 번호 머리, 저자(연도), 'Last, F.', '저자. 연도.' 꼴
_BIB_START = re.compile(
    r"^\s*(?:[-•∙·]\s*)?(?:\[?\d{1,3}[.\])]\s"
    r"|[^\n]{0,60}?[(（]\s*(?:19|20)\d{2}[a-z]?\s*[)）]"
    r"|[A-Z][A-Za-z'\-]+,\s*[A-Z]\."
    r"|[^\n]{1,40}?[.,]\s*(?:19|20)\d{2}[a-z]?[.,])"
)
_HAS_YEAR = re.compile(r"(?:19|20)\d{2}")
# 날짜 상자 뒤에 남은 서지 꼬리(학술지 이름 뒷부분·권·쪽) — 'Behavior ․ 논문제출일: … Therapy, 35, 35-54.'
_BIB_RESUME = re.compile(
    r"^[^\d가-힣]{0,40}?\d{1,4}\s*(?:\(\s*[\d\-–]{1,7}\s*\))?\s*[,:]\s*(?:pp?\.\s*)?\d{1,5}\s*[-–~]\s*\d{1,5}\s*\.?\s*$"
)
# 남길 앞부분의 최소 글자 수(기호·공백 빼고)
_MIN_ENTRY = 12


def _letters(s: str) -> int:
    return len(re.sub(r"[\W_]+", "", s))


def _is_furniture(text: str) -> bool:
    return len(text) <= _FURNITURE_MAX and any(p.search(text) for p in _FURNITURE)


def _submission_spans(text: str) -> list[tuple[int, int]]:
    """투고 정보 구간 — 괄호 안('(최종 수정일: 2019. 3. 28)' 같은 웹 자료 서지)은 빼고."""
    spans = []
    for m in _SUBMISSION.finditer(text):
        before = text[:m.start()]
        if before.count("(") + before.count("（") > before.count(")") + before.count("）"):
            continue
        spans.append(m.span())
    return spans


def _tidy(s: str, lead: bool = False) -> str:
    """뒤에 남은 구분 기호를 걷는다. 앞은 서지 머리('[28] …'·'- 1. …'·'• …'·'#### …')라 건드리지 않고, 날짜 상자를 지운
    자리(lead=True)만 표 칸 기호를 걷는다."""
    s = re.sub(r"\s{2,}", " ", s).rstrip(" ,;/∙·․•|｜#[<【—-=￭■*_")
    return s.lstrip(" /|｜【】") if lead else s.strip()


def _head_before_tail(text: str) -> str | None:
    """끊는 표지가 있으면 그 앞 서지(없거나 짧으면 '')를, 표지가 없으면 None 을 낸다."""
    hard = _HARD_TAIL.search(text)
    badge = _BADGE.search(text)
    contact = _CONTACT.search(text)
    cuts = [m for m in (hard, badge, contact) if m]
    if not cuts:
        return None
    m = min(cuts, key=lambda x: x.start())
    head = text[:m.start()]
    if m is badge:
        head = _BADGE_NAME.sub("", head)
    head = _tidy(head)
    return head if _letters(head) >= _MIN_ENTRY else ""


def _next_ref(items: list[str], i: int) -> str | None:
    return next((t for t in items[i + 1:] if t and not _is_furniture(t) and not _BARE_YEAR.match(t)), None)


def _continues(items: list[str], i: int) -> bool:
    """다음 항목이 이 논문의 서지로 이어지는가 — 서지 꼴이고 투고 정보·끊는 표지를 품지 않았다."""
    nxt = _next_ref(items, i)
    return bool(nxt and _BIB_START.match(nxt) and not _submission_spans(nxt) and not _HARD_TAIL.search(nxt))


def clean_references(refs: list[str] | None) -> list[str]:
    items = [_WATERMARK.sub(" ", html.unescape(r or "")).strip() for r in refs or []]
    out: list[str] = []
    for i, text in enumerate(items):
        if not text:
            continue
        if _BARE_YEAR.match(text):
            # 줄이 갈려 따로 들어온 출판 연도 — 앞 서지가 덜 끝났으면(쉼표·쌍점·마침표 없음) 거기에 붙인다
            if out and not out[-1].rstrip().endswith("."):
                out[-1] = f"{out[-1].rstrip()} {text.strip()}"
            else:
                out.append(text.strip())
            continue
        if _is_furniture(text):
            continue
        if _TAIL_AT_START.match(text):
            break

        spans = _submission_spans(text)
        contact = _CONTACT.search(text)
        if spans or (contact and not _HARD_TAIL.search(text[:contact.start()])):
            soft_at = min([s for s, _ in spans] + ([contact.start()] if contact else []))
            # 날짜 상자·연락처가 목록 가운데에 낀 2단 조판 — 그 구간만 지우고 계속 읽는다
            if _continues(items, i) and not _HARD_TAIL.search(text) and not _BADGE.search(text):
                rest = "".join(text[a:b] for a, b in zip([0] + [e for _, e in spans], [s for s, _ in spans] + [len(text)]))
                if contact:
                    after = rest[_CONTACT.search(rest).start():] if _CONTACT.search(rest) else ""
                    m = _EMAIL.search(after)
                    rest = rest[:len(rest) - len(after)] + (after[m.end():] if m else "")
                rest = _tidy(rest, lead=True)
                if _letters(_SUB_JUNK.sub("", rest)) >= _MIN_ENTRY:
                    out.append(rest)
                continue
            # 목록 끝 — 날짜·연락처 앞 서지만 남기고 끊는다(그 앞에 다른 꼬리 표지가 있으면 그 앞까지)
            head = text[:soft_at]
            cut = _head_before_tail(head)
            head = _tidy(head) if cut is None else cut
            if cut is None and contact and contact.start() == soft_at:
                head = _tidy(_CONTACT_NAME.sub("", head))
            # 2단 조판의 날짜 상자가 서지 한가운데(학술지 이름 사이)에 끼었으면 상자 뒤의 권·쪽을 다시 잇는다
            if spans and not contact and cut is None and soft_at == spans[0][0]:
                tail = text[spans[-1][1]:]
                gaps = "".join(text[e:s] for (_, e), (s, _) in zip(spans, spans[1:]))
                if _BIB_RESUME.match(tail) and not _SUB_JUNK.sub("", gaps):
                    head = f"{head.rstrip(' ․∙·•/|')} {tail.strip()}"
            if _letters(head) >= _MIN_ENTRY:
                out.append(head)
            break

        cut = _head_before_tail(text)
        if cut is not None:
            if cut:
                out.append(cut)
            break
        out.append(text)
    return out
