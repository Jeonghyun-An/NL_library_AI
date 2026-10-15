// frontend/tests/unit/reportCiteNumbers.test.ts
// 보고서 화면의 인용칩을 '김 2012'(성 연도) 대신 숫자로, 보고서 끝에 번호 순 참고문헌을 접어 둔다(사용자 결정 2026-10-15 —
// 대표 의견 '성 연도 칩이 보기 그렇다'). 번호·참고문헌 줄은 Word·PDF 와 같은 함수(reportCiteNumbers·reportReferences)에서 온다.
// 마운트 도구가 없어 화면 약속은 소스 글로 지킨다(저장소의 다른 화면 테스트와 같은 방식)
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { REFERENCES_TITLE } from "~/utils/researchReport";

const read = (rel: string) => readFileSync(fileURLToPath(new URL(`../../${rel}`, import.meta.url)), "utf8");

describe("보고서 인용칩은 숫자, 끝에 접힌 참고문헌", () => {
  const view = read("components/research/ReportView.vue");
  const body = read("components/research/ReportSectionBody.vue");
  const chip = read("components/research/CitationChip.vue");

  it("ReportView 가 문서와 같은 함수로 번호·참고문헌을 만들어 절 본문에 번호를 넘긴다", () => {
    expect(view).toMatch(/import \{[^}]*\breportCiteNumbers\b[^}]*\breportReferences\b[^}]*\} from "~\/utils\/reportDocument";/);
    expect(view).toContain(':numbers="citeNumbers"');
  });

  it("절 본문의 칩 셋(도입·대표 논문·향후 과제)이 모두 번호를 받는다", () => {
    expect(body.match(/:num="numbers\.get\([^"]+\)"/g) ?? []).toHaveLength(3);
  });

  it("칩은 번호가 있으면 숫자, 없으면 전처럼 '성 연도' — 보조기기 이름도 같은 번호", () => {
    expect(chip).toMatch(/const label = computed\(\(\) => \(props\.num \? String\(props\.num\) : citeLabel\(/);
    expect(chip).toContain(":aria-label=\"`근거 ${label}: ${title}`\"");
  });

  it("참고문헌은 제외한 논문 아래 접힌 섹션이고 제목은 문서와 같은 말이다", () => {
    expect(REFERENCES_TITLE).toBe("참고문헌");
    expect(view).toContain("{{ REFERENCES_TITLE }} ({{ references.length }})");
    expect(view.indexOf('class="rs-refs"')).toBeGreaterThan(view.indexOf('class="rs-excluded"'));
    expect(view).toMatch(/v-show="refsOpen"/);
    expect(view).toMatch(/const refsOpen = ref\(false\)/);
  });
});
