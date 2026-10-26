// frontend/tests/unit/researchScreenCopy.test.ts
// 딥리서치·연구 어시스턴트 화면 문구의 말투·줄바꿈 규칙(사용자 요청 2026-10-16) — 오류·빈 상태·경고·안내 문구는 해요체이고
// 두 문장 이상이면 문장마다 줄을 바꾼다. 토스트는 한 줄(nowrap)이라 한 문장('무엇을 못 했는지 — 할 일')이다. 오류는 화면 안에서
// 알린다(브라우저 prompt·alert·confirm 금지 — 확인은 누른 버튼 곁의 확인 칸 SkxConfirm). 보고서 문서 자체의 글(화면 본문과 내려받은 Word·PDF 가 같은 상수를 쓴다)은 문서 말투(합쇼체)로 둔다.
// 순수 함수·상수는 실제로 돌리고, 화면(.vue)은 Nuxt 를 띄우지 않고 소스 글을 검사한다(기존 관례)
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { REPORT_EXPORT_FAILED, REPORT_EXPORT_FAILED_TOAST } from "~/composables/useReportExport";
import { FOOTPRINT_EMPTY } from "~/utils/proposalView";
import { RESEARCH_TOAST_TEXT, pdfCheckProblem, toastLine } from "~/utils/researchErrors";
import { EXCLUDED_WHY, INTROLESS, NO_LIMITS, NO_SUMMARY } from "~/utils/researchReport";
import { REMAKE_CONFIRM, REMAKE_CONFIRM_OK, REMAKE_REPORT } from "~/utils/workPhase";
import { findBlock } from "./helpers/themeCss";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8");
/** <template> 부분만 — 머리 주석의 글에 속지 않게 */
const template = (src: string) => src.match(/<template>([\s\S]*)<\/template>/)?.[1] ?? "";
/** 주석(<!-- -->·/* *\/·//)과 개발자 로그(console.*) 줄을 지운 소스 — 화면에 나가는 글만 남긴다 */
function screenText(src: string): string {
  return src
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split(/\r?\n/)
    .filter((line) => !/console\.(warn|error|log|info)\(/.test(line))
    .map((line) => line.replace(/(^|[^:"'`])\/\/.*$/, "$1"))
    .join("\n");
}

describe("토스트 — 한 줄이라 한 문장", () => {
  it("toastLine 은 줄 안내용 두 줄 문구를 '무엇을 못 했어요 — 할 일.' 한 문장으로 잇고, 한 줄 문구는 그대로 둔다", () => {
    expect(toastLine("Word 문서를 만들지 못했어요.\n새로고침한 뒤 다시 시도해 주세요.")).toBe(
      "Word 문서를 만들지 못했어요 — 새로고침한 뒤 다시 시도해 주세요.",
    );
    expect(toastLine("원문 파일이 없어요")).toBe("원문 파일이 없어요");
    expect(toastLine(pdfCheckProblem(500) ?? "")).toBe("원문을 불러오지 못했어요 — 잠시 뒤 다시 시도해 주세요.");
  });

  it("내보내기 실패의 토스트판은 줄 안내 문구에서 만든 한 문장 — 줄 안내 쪽(작업대 보고서)은 두 줄 그대로", () => {
    expect(REPORT_EXPORT_FAILED_TOAST).toEqual({
      docx: "Word 문서를 만들지 못했어요 — 새로고침한 뒤 다시 시도해 주세요.",
      pdf: "인쇄 창을 열지 못했어요 — 다시 시도해 주세요.",
    });
    expect(REPORT_EXPORT_FAILED.docx).toBe("Word 문서를 만들지 못했어요.\n새로고침한 뒤 다시 시도해 주세요.");
    expect(REPORT_EXPORT_FAILED.pdf).toBe("인쇄 창을 열지 못했어요.\n다시 시도해 주세요.");
    // 원문 확인 실패도 줄 안내(논문 검색·상세·소장자료)는 두 줄 그대로다
    expect(pdfCheckProblem(500)).toBe("원문을 불러오지 못했어요.\n잠시 뒤 다시 시도해 주세요.");
  });

  const toasts: [string, string][] = [...Object.entries(RESEARCH_TOAST_TEXT), ...Object.entries(REPORT_EXPORT_FAILED_TOAST)];

  it.each(toasts)("%s: 줄바꿈 없이 한 문장이고 해요체다", (_name, text) => {
    expect(text).not.toContain("\n");
    expect(text).not.toMatch(/[.?!] \S/);
    expect(text).not.toMatch(/습니다|입니다|[^주]세요/);
  });

  it("딥리서치 화면 토스트 문구", () => {
    expect(RESEARCH_TOAST_TEXT).toEqual({
      linkCopied: "링크를 복사했어요.",
      linkCopyFailed: "링크를 복사하지 못했어요 — 주소창의 주소를 복사해 주세요.",
      docxSaved: "Word 문서를 내려받았어요.",
    });
  });
});

describe("딥리서치 화면([id].vue) — 오류는 화면 안에서, 토스트는 한 문장", () => {
  const page = read("pages/research/[id].vue");

  it("[링크 복사]가 클립보드에 실패해도 브라우저 입력창(prompt)을 띄우지 않고 토스트로 알린다", () => {
    expect(page).not.toMatch(/window\.(prompt|alert|confirm)\(/);
    expect(page).toMatch(
      /async function copyLink\(\): Promise<void> \{\s*try \{\s*await navigator\.clipboard\.writeText\(window\.location\.href\);\s*showToast\(RESEARCH_TOAST_TEXT\.linkCopied\);\s*\} catch \{[\s\S]*?showToast\(RESEARCH_TOAST_TEXT\.linkCopyFailed\);\s*\}\s*\}/,
    );
  });

  it("원문 확인 실패·내보내기 실패·내보내기 성공 토스트는 한 줄판·해요체 상수를 쓴다", () => {
    expect(page).toContain("if (problem) showToast(toastLine(problem));");
    expect(page).toContain("showToast(REPORT_EXPORT_FAILED_TOAST.pdf);");
    expect(page).toContain("showToast(REPORT_EXPORT_FAILED_TOAST[format]);");
    expect(page).toContain("showToast(RESEARCH_TOAST_TEXT.docxSaved);");
    // 줄 안내용 두 줄 문구를 토스트에 그대로 싣지 않는다
    expect(page).not.toMatch(/showToast\(REPORT_EXPORT_FAILED[[.]/);
    expect(page).not.toMatch(/showToast\(problem\)/);
    expect(page).not.toMatch(/복사했습니다|내려받았습니다/);
  });
});

describe("보고서 문서 자체의 글 — 문서 말투(합쇼체)를 지킨다", () => {
  const doc = read("utils/reportDocument.ts");

  it("빈자리·한계 없음·제외 사유 상수는 화면 본문과 내려받은 Word·PDF(reportDocument)가 함께 쓴다", () => {
    expect(INTROLESS).toBe("이 절은 도입 서술을 받지 못했습니다. 아래 논문 목록만 싣습니다.");
    expect(NO_SUMMARY).toBe("요약을 받지 못했습니다.");
    expect(NO_LIMITS).toBe("자동 점검에서 보고할 한계가 발견되지 않았습니다.");
    expect(EXCLUDED_WHY).toBe("자기점검이 하위질문의 핵심 개념과 무관하다고 판단해 근거에서 제외한 논문입니다.");
    // 들여온 줄 말고도 문서 모델을 만드는 곳에서 쓴다(가져오기 1 + 쓰임 1 이상)
    for (const name of ["INTROLESS", "NO_SUMMARY", "NO_LIMITS", "EXCLUDED_WHY"]) {
      expect(doc.match(new RegExp(`\\b${name}\\b`, "g"))?.length ?? 0).toBeGreaterThanOrEqual(2);
    }
  });

  it("초안 안내(draftIntro)는 화면에만 쓴다 — 내려받는 초안의 서론은 reportIntro", () => {
    expect(doc).not.toContain("draftIntro");
    // 초안은 인용이 다 끝나지 않아 인용 수 한 줄을 붙이지 않는다(withCited=false)
    expect(doc).toMatch(/intro: reportIntro\(draft\.report, view\.subqs\.length, false\)/);
    // 초안 안내가 여러 줄이라 보고서 서론 칸이 '\n' 을 줄로 그린다
    const researchCss = read("assets/css/research.css").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(findBlock(".rs-report__intro", researchCss)).toMatch(/white-space:\s*pre-line/);
  });

  it("AI 기여 줄의 빈 문구 — 화면 막대는 해요체, 보고서 Word 의 AI 사용 공개 부록은 문서 말투", () => {
    expect(FOOTPRINT_EMPTY).toEqual({ screen: "아직 쓴 문단이 없어요", doc: "아직 쓴 문단이 없습니다" });
    expect(read("utils/proposalDocument.ts")).toContain("footprintLine(footprint(p), FOOTPRINT_EMPTY.doc)");
    expect(read("components/work/AiFootprintMeter.vue")).toContain("footprintLine(counts.value)");
  });
});

describe("여러 문장 안내 — 문장마다 줄을 바꾼다", () => {
  it("rs-lines 는 '\\n' 을 줄로 그린다(white-space: pre-line)", () => {
    const researchCss = read("assets/css/research.css").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(findBlock(".rs-lines", researchCss)).toMatch(/white-space:\s*pre-line/);
  });

  it("함수·상수가 만든 여러 줄 글을 그리는 자리는 rs-lines 를 단다", () => {
    expect(template(read("components/work/OutlineEditor.vue"))).toContain('<p class="rs-muted rs-lines">{{ basisNote }}</p>');
    expect(template(read("components/work/ContinueResearchCard.vue"))).toContain('<p class="rs-muted rs-lines">{{ view.body }}</p>');
  });

  it("[보고서 다시 만들기] 확인은 두 화면이 한 상수를 화면 안 확인 칸(SkxConfirm)에 쓴다 — 해요체·문장마다 줄", () => {
    expect(REMAKE_CONFIRM.split("\n")).toEqual([
      "보고서를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀌어요.",
      "연구 배경은 그대로 둬요.",
      "이미 쓴 절은 지우지 않고 아직 쓰지 않은 절만 자동으로 써요 — 주제·묶음·연구 질문이 바뀐 절에는 '다시 맞춤 필요'가 붙어요.",
      "계속할까요?",
    ]);
    expect(REMAKE_CONFIRM_OK).toBe("다시 만들기");
    for (const file of ["components/work/ProposalStep.vue", "components/work/ReadingStep.vue"]) {
      const src = read(file);
      expect(src).toMatch(/import \{[^}]*\bREMAKE_CONFIRM\b[^}]*\bREMAKE_CONFIRM_OK\b[^}]*\} from "~\/utils\/workPhase";/);
      expect(src).not.toMatch(/const REMAKE_CONFIRM\b/);
      // 브라우저 확인 창이 아니라 화면 안 확인 칸으로 묻는다
      expect(src).not.toMatch(/window\.confirm|(?<![\w$.])confirm\(/);
      expect(src).toMatch(/message: REMAKE_CONFIRM,|:message="REMAKE_CONFIRM"/);
      expect(template(src)).toContain("<SkxConfirm");
    }
  });

  it("다시 맞춤이 필요하다는 경고는 누를 버튼 이름을 [대괄호]로 적는다", () => {
    expect(REMAKE_REPORT).toBe("보고서 다시 만들기");
    expect(template(read("components/work/OutlineEditor.vue"))).toContain("[{{ REMAKE_REPORT }}]를 눌러 주세요.");
    expect(template(read("components/work/ProposalStep.vue"))).toContain("[{{ REMAKE_REPORT }}]를 누르면 지금 담은 논문으로 묶음을 새로 나눠요");
    expect(template(read("components/work/ProposalSection.vue"))).toContain("[이 절 다시 쓰기]를 눌러 주세요.");
    expect(template(read("components/work/ReadingStep.vue"))).toContain("[{{ REMAKE_REPORT }}]를 눌러 맞춰 주세요.");
  });
});

describe("화면 문구 훑기 — 합쇼체('~습니다'·'~입니다')·명령형('~하세요')이 남지 않는다", () => {
  // 화면 글이 있는 곳. 보고서 문서 상수(researchReport)·문서 모델(reportDocument·proposalDocument)은 문서 말투라 넣지 않는다
  const dirs = ["components/research", "components/work"];
  const files = [
    ...dirs.flatMap((dir) => readdirSync(join(root, dir)).filter((f) => f.endsWith(".vue")).map((f) => `${dir}/${f}`)),
    "pages/research/[id].vue",
    "utils/proposalView.ts",
    "utils/queueLine.ts",
    "utils/readingList.ts",
    "utils/researchDraft.ts",
    "utils/researchErrors.ts",
    "utils/researchInput.ts",
    "utils/researchLive.ts",
    "utils/researchProgress.ts",
    "utils/researchStart.ts",
    "utils/synthCard.ts",
    "utils/topicDeck.ts",
    "utils/workErrors.ts",
    "utils/workPhase.ts",
  ];
  // 일부러 남긴 것 — 이유를 함께 적는다
  const KEPT: { file: string; text: string; why: string }[] = [
    // 사용자 결정 2026-10-13 — 온보딩은 합니다체, 참고문헌 선택하기 단계 설명은 승인 문구 글자 그대로(workPhase.test.ts 가 지킨다)
    { file: "components/work/OnboardingModal.vue", text: "탐색은 끝났습니다", why: "온보딩 합니다체(2026-10-13)" },
    { file: "components/work/OnboardingModal.vue", text: "알겠습니다", why: "온보딩 합니다체(2026-10-13)" },
    // utils/workPhase.ts 의 ONBOARDING_LEAD·ONBOARDING_STEPS 는 아래에서 블록째 건너뛴다
    // 사용자 결정 2026-10-13 — 참고문헌 선택하기 머리 소개는 승인 문구 글자 그대로(readingList.test.ts 가 지킨다)
    { file: "utils/readingList.ts", text: "후보로 들어와 있습니다", why: "승인 문구(2026-10-13)" },
    { file: "utils/readingList.ts", text: "미리 담아 두었습니다", why: "승인 문구(2026-10-13)" },
    { file: "utils/readingList.ts", text: "대화할 수 있습니다", why: "승인 문구(2026-10-13)" },
    // 문서 말투 — 내려받은 보고서의 AI 사용 공개 부록
    { file: "utils/proposalView.ts", text: '"아직 쓴 문단이 없습니다"', why: "문서 말투" },
    // 사이드바의 준비 중 토스트 두 줄은 다른 작업(feat/error-handling)이 이미 바꿨다 — 이 브랜치는 건드리지 않는다
    { file: "pages/research/[id].vue", text: "준비 중입니다.", why: "다른 작업이 바꿈" },
  ];

  it.each(files)("%s", (file) => {
    const lines = screenText(read(file)).split("\n");
    // 온보딩 상수는 블록째 남긴다 — ONBOARDING_LEAD 한 줄과 ONBOARDING_STEPS 선언부터 닫는 '];' 까지
    let inOnboarding = false;
    const left = lines.filter((line) => {
      const onboarding = inOnboarding || /ONBOARDING_(LEAD|STEPS)\b.*=/.test(line);
      inOnboarding = onboarding && !/ONBOARDING_LEAD\b/.test(line) && line.trim() !== "];";
      if (file === "utils/workPhase.ts" && onboarding) return false;
      if (KEPT.some((k) => k.file === file && line.includes(k.text))) return false;
      return /[가-힣]니다(?![가-힣])|[^주]세요(?![가-힣])|십시오/.test(line);
    });
    expect(left).toEqual([]);
  });
});

// 대표 지적 2026-10-26 — '검토한 논문 23 · 채택한 근거 18 · 제외 10'이 더해 맞지 않았다. 제외 칸은 서버의 하위질문별 무관 판정 수
// (counters.excluded)가 아니라 검토 − 채택(excludedCounter)이고, 패널 이름은 사서가 쓰는 말로(사용자 확정)
describe("딥리서치 카운터·패널 이름 — 숫자가 더해 맞고 사서가 쓰는 말로", () => {
  const panels = ["components/research/ProgressPanel.vue", "components/research/ResearchLive.vue"];

  it.each(panels)("%s — 채택한 논문·제외한 논문 칸, 제외는 검토 − 채택", (file) => {
    const src = read(file);
    const tpl = template(src);
    expect(tpl).toContain("<dt>채택한 논문</dt>");
    expect(tpl).toContain("<dt>제외한 논문</dt>");
    expect(src).toContain("excludedCounter(");
    expect(tpl).not.toContain("counters.excluded");
    expect(tpl).not.toContain("채택한 근거");
  });

  it("옆 칸 채택 목록 카드는 '채택한 논문'(보고서 참고문헌과 이름을 가른다), 탐색이 끝난 진행 패널은 '탐색 과정', 회차 줄은 '본문 N곳'", () => {
    expect(template(read("components/work/EvidenceLedger.vue"))).toContain(">채택한 논문</h2>");
    expect(template(read("components/work/EvidenceLedger.vue"))).not.toContain(">참고문헌</h2>");
    expect(screenText(read("components/work/EvidenceLedger.vue"))).not.toContain("근거 장부");
    const panel = read("components/research/ProgressPanel.vue");
    expect(panel).toContain('completed: "탐색 과정"');
    expect(template(panel)).toContain("본문 {{ r.foundChunks }}곳");
    expect(screenText(panel)).not.toContain("탐색 경로");
  });
});
