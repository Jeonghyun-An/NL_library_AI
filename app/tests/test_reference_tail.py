"""test_reference_tail.py — 참고문헌 목록 끝 꼬리 걷기(services/ingestion/reference_tail.clean_references).

예는 운영 표본(2026-10-26, 1,347편 — research/reference-tail-clean)에서 본 꼴이다. 앞 절은 걷어야 하는 꼬리, 뒤 절은 두 번의
표본 검토가 찾은 거짓 양성(진짜 참고문헌을 잃은 경우)을 다시 내지 않는지 본다.
"""
from models.book import Book
from services.ingestion.paper_enricher import extract_references
from services.ingestion.reference_tail import clean_references

REF_A = "김대행(2000), “한국어교육과 한국문학”, 외국인을 위한 한국어교육 3, 서울대학교."
REF_B = "Seelye, H. Ned(1984), Teaching culture: strategies for intercultural communication, Skokie: National Textbook."
REF_C = "황상심(2018), 「다문화가정의 이중언어 사용에 관한 질적 탐색」, 『언어치료 연구』27-1, pp.99-113."


# ── 걷어야 하는 꼬리 ─────────────────────────────────────────

def test_a_wrapped_abstract_header_ends_the_list_even_when_html_escaped():
    assert clean_references([REF_A, REF_B, "&lt;Abstract&gt;", "This study aims to …"]) == [REF_A, REF_B]
    assert clean_references([REF_A, "￭국문초록", "본 연구는 …"]) == [REF_A]
    assert clean_references([REF_A, "|Abstract| |---|", "The purpose …"]) == [REF_A]


def test_a_keyword_header_cuts_the_entry_it_sits_in_and_keeps_the_reference_before_it():
    tail = REF_C + " * Key Words: COVID-19 and School Violence, Victimization"
    assert clean_references([REF_A, tail, "접수일: 2024년 5월 23일"]) == [REF_A, REF_C]
    assert clean_references([REF_A, "#### [Keywords : Depression of the Elderly]"]) == [REF_A]


def test_a_bare_abstract_at_the_end_of_an_entry_is_cut():
    ref = "Hart, H. L. A. “Positivism.” Yale Law Jour. 72(2): 283-303."
    assert clean_references([REF_A, ref + " Abstract"]) == [REF_A, ref]


def test_an_author_bio_ends_the_list_and_a_name_before_a_membership_badge_is_not_kept():
    assert clean_references([REF_A, "###### 김 명 숙(Myungsook Kim) [정회원]", "1990년 서울대 …"]) == [REF_A]
    assert clean_references([REF_A, "최희용(崔熙容): 성균관대학교에서 박사학위를 취득하고 재직 중이다."]) == [REF_A]
    assert clean_references([REF_A, "서 영 진 전자우편：seoyj@scnu.ac.kr"]) == [REF_A]
    assert clean_references([REF_A, "∙ Address reprint requests to : Kim, Geun Myun Department of Nursing"]) == [REF_A]


def test_page_furniture_and_watermarks_are_dropped_without_ending_the_list():
    refs = [REF_A, "28 ｜『노인복지연구』 통권 33호", "- 59 -", "108", "_____", REF_B + " www.kci.go.kr ```", REF_C]
    assert clean_references(refs) == [REF_A, REF_B, REF_C]


def test_submission_info_followed_by_something_that_is_not_a_reference_ends_the_list():
    # 같은 PDF 에 이어 실린 다음 논문(제목·본문)이 붙어 온 꼴 — 투고 정보 뒤가 서지 꼴이 아니면 끊는다
    refs = [REF_A, REF_B + " 접수일자: 2008. 21 게재결정: 2008. 24", "# 국내 대학의 학문 목적 한국어 교육 현황 분석*", "8)"]
    assert clean_references(refs) == [REF_A, REF_B]
    assert clean_references([REF_A, "원 고 접 수 일 : 2019. 12. 27 수정원고 접수일 : 2020. 1. 5"]) == [REF_A]


# ── 거짓 양성 — 진짜 참고문헌을 잃지 않는다 ───────────────────────

def test_a_submission_box_in_the_middle_of_a_two_column_list_does_not_end_it():
    refs = ["1. Kamakura, W. (1986). Consumer sentiment.", "|논문접수일 : 2010년 4월 7일 |", "9. Katona, G. (1968). Consumer behavior."]
    assert clean_references(refs) == [refs[0], refs[2]]


def test_submission_info_inside_a_reference_is_removed_and_the_reference_stays():
    ref = ("Hayes, S. C. (2004). DBT, FAP, and ACT: how empirically oriented are the new behavior therapy technologies. "
           "Behavior ․ 논문제출일: 2016. 11. 14 ․ 논문심사일: 2016. 11. 28 ․ 게재확정일: 2016. 12. 19 Therapy, 35, 35-54.")
    out = clean_references([REF_A, ref, "Weinberg, R.S., & Gould D.(2003). Foundation of Sport & Exercise Psychology."])
    assert len(out) == 3 and "Behavior" in out[1] and "Therapy, 35, 35-54." in out[1] and "논문제출일" not in out[1]


def test_a_date_box_inside_the_last_reference_keeps_the_volume_and_pages_after_it():
    hayes = ("Hayes, S. C. (2004). DBT, FAP, and ACT: how empirically oriented are the new behavior therapy technologies. "
             "Behavior ․ 논문제출일: 2016. 11. 14 ․ 논문심사일: 2016. 11. 28 ․ 게재확정일: 2016. 12. 19 Therapy, 35, 35-54.")
    out = clean_references([REF_A, hayes])
    assert out[-1].endswith("Behavior Therapy, 35, 35-54.") and "논문제출일" not in out[-1]


def test_a_numbered_reference_keeps_its_bracket_when_the_tail_after_it_is_cut():
    ref = "[25] Kim, D. W. “Wheelchair tennis”, Journal of the Korea Convergence Society, Vol. 6, No. 4, pp. 15-23, 2015."
    assert clean_references(["[24] " + REF_B, ref + " 이 승 은(Lee, Sheng Yen) · E-Mail : hercules7@hanmail.net"]) == ["[24] " + REF_B, ref]


def test_a_last_modified_date_inside_a_web_reference_is_left_alone():
    ref = "통계청. 2019. 「장래인구추계」. https://kostat.go.kr (최종 수정일: 2019. 3. 28)."
    assert clean_references([REF_A, ref, REF_B]) == [REF_A, ref, REF_B]


def test_abstract_inside_a_reference_title_is_not_a_header():
    apa = ("Brewer, B. W. (1994). A psychometric evaluation of the Rehabilitation Adherence Questionnaire[Abstract]. "
           "Journal of Sport & Exercise Psychology, 16, S34.")
    dai = "Smith, J. (1999). Extraversion and well-being. Dissertation Abstracts International B 60(7-B): 3608."
    assert clean_references([REF_A, apa, dai, REF_B]) == [REF_A, apa, dai, REF_B]


def test_subheadings_and_odl_heading_references_inside_the_list_are_kept():
    refs = ["###### Ⅰ. 국내문헌", "##### 교육과학기술부(2009). 학교폭력 예방 및 대책 5개년 기본계획.", REF_A]
    assert clean_references(refs) == refs


def test_a_split_word_is_not_read_as_a_corresponding_author_marker():
    ref = "이영희(2010). 대학교 신입생의 적응. 교육연구, 12(3), 1-20."
    assert clean_references([REF_A, ref]) == [REF_A, ref]


def test_words_inside_reference_titles_are_not_markers():
    special = "장선철 (2008). 특별기고 : 노인상담에 관한 연구동향 분석. 사회과학논총, 23(2), 1-22."
    querying = ("Baker, P.(2004), Querying keywords: Questions of difference, frequency, and sense in keywords analysis. "
                "Journal of English linguistics 32(4), 346-359.")
    assert clean_references([REF_A, special, querying, REF_B]) == [REF_A, special, querying, REF_B]


def test_kci_urls_inside_references_are_kept_and_only_a_standalone_watermark_goes():
    url_ref = "김종성 (2010). 공공도서관 청소년 프로그램. 한국비블리아학회지, 21(2), 39-56. https://uci.kci.go.kr/G704-000742.2010.21.2.011"
    portal = "Kim, S. K. (2012). Youth. Korean J. Youth Stud, 19, 147-176. https://www.kci.go.kr/kciportal/ci/sereArticleSearch"
    assert clean_references([url_ref, portal, REF_B + " www.kci.go.kr"]) == [url_ref, portal, REF_B]


def test_bulleted_entries_and_split_off_years_are_references_not_page_furniture():
    assert clean_references(["• 玉野和志 1999", "• 千相哲 2006", REF_A]) == ["• 玉野和志 1999", "• 千相哲 2006", REF_A]
    alexy = "Alexy, R., Theorie der juristischen Argumentation, Frankfurt a.M.: Suhrkamp,"
    assert clean_references([alexy, "1978", REF_B]) == [alexy + " 1978", REF_B]


def test_a_reference_glued_in_front_of_an_author_badge_is_kept():
    ref = "[28] T. G. An. (2017). A Study on the Effect of Festival Satisfaction. Journal of the Korea Convergence Society, 8(11), 241-247."
    assert clean_references([REF_A, ref + " 김 영 대(Kim, Young Dai) [정회원] • 2016년 8월 …"]) == [REF_A, ref]


def test_the_reference_before_submission_info_at_the_end_of_the_list_is_kept():
    vargas = "Vargas-Silva, C., 2008, “Monetary policy and the US housing market,” Journal of Macroeconomics 30(3), pp.977-990."
    assert clean_references([REF_A, vargas + " 교신: 김경민 … 최초투고일 2019년 11월 15일"]) == [REF_A, vargas]
    hong = "홍승아(2014). 한국어 학습자의 주체높임법 습득연구. 한국언어문화학, 11(3), 271-291."
    assert clean_references([REF_A, hong + " 논문 접수: 2015년 11월 15일 ##### <ABSTRACT> ## A Study on …"]) == [REF_A, hong]


def test_contact_details_wedged_into_a_two_column_list_do_not_end_it():
    contact = "최용기(국립국어원 국어진흥부장) 주소 : 서울시 강서구 … 전자우편 : choiyg58@mct.go.kr"
    refs = [REF_A, contact, "김중섭(2006), 한국어 교육의 정체성, 한국어교육 17-2.", "박영순(2001), 외국어로서의 한국어교육론, 월인."]
    out = clean_references(refs)
    assert out[0] == REF_A and out[-2:] == refs[-2:] and not any("전자우편" in x for x in out)


# ── 쓰는 곳 ───────────────────────────────────────────────────

def test_the_stored_list_is_cleaned_when_read_and_left_as_is_in_storage():
    stored = [REF_A, REF_B, "&lt;Abstract&gt;", "This study …"]
    book = Book(cnts_id="KCI_1", extra={"references": stored})
    assert book.references == [REF_A, REF_B]
    assert book.extra["references"] == stored


def test_extraction_cleans_the_tail_too():
    text = "본문 …\n\n참고문헌\n" + "\n".join([REF_A, REF_B, REF_C]) + "\n<Abstract>\nThis study aims …\n"
    assert extract_references(text) == [REF_A, REF_B, REF_C]
