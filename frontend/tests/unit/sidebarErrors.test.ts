// frontend/tests/unit/sidebarErrors.test.ts
// 사이드바 기록의 오류 표시(에러 처리 2단계 — 공통 영역). 목록을 못 읽은 묶음은 '기록 없음'으로 보이지 않고 그 자리에 줄 안내 +
// [다시 시도](SkxInlineError), 브라우저 ID 를 저장하지 못하는 브라우저는 목록 아래 한 줄. 사이드바 모양(DeepResearch 패널은 늘 보임,
// 기록이 하나도 없을 때만 [연구 시작하기], 머리 'DeepResearch · 전체 삭제')은 그대로다. 마운트 도구가 없어 화면 약속은 소스 글로 지킨다
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { SIDEBAR_EMPTY } from "~/utils/sidebarGroups";

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(`../../${rel}`, import.meta.url)), "utf-8").replace(/\r\n/g, "\n");
const src = read("components/AppSidebar.vue");
const tpl = src.slice(src.indexOf("<template>"), src.lastIndexOf("</template>"));
const js = src.slice(src.indexOf("<script setup"), src.indexOf("</script>"));
const researchSection = tpl.slice(tpl.indexOf('aria-labelledby="skx-history-research"'), tpl.indexOf("</section>"));
const recentSection = tpl.slice(tpl.indexOf('aria-labelledby="skx-history-recent"'));

describe("사이드바 — 목록을 못 읽은 묶음", () => {
  it("묶음별 실패 안내는 failedKinds 로 정한다(줄 수는 자르기 전 전체)", () => {
    expect(js).toContain("const { loaded, failedKinds } = history;");
    expect(js).toContain(
      'const researchLoadError = computed(() => groupLoadError("research", failedKinds.value, groups.value.researchTotal));',
    );
    expect(js).toContain(
      'const recentLoadError = computed(() => groupLoadError("recent", failedKinds.value, recentRows.value.length));',
    );
  });

  it("DeepResearch 패널은 늘 보이고, 실패면 [연구 시작하기] 대신 줄 안내 + [다시 시도]", () => {
    expect(tpl).toMatch(/<section class="skx-history__group skx-history__group--research" aria-labelledby="skx-history-research">/);
    expect(researchSection).toMatch(
      /<SkxInlineError\s+v-if="researchLoadError"\s+class="skx-history__notice"\s+role="status"\s+:message="researchLoadError"\s+:busy="retrying"\s+@retry="retryLoad"\s+\/>\s*<button\s+v-else-if="!researchRows.length"[^>]*class="skx-history__start"/,
    );
    // 머리 'DeepResearch · 전체 삭제' 는 기록이 있을 때만 전체 삭제
    expect(researchSection).toMatch(/<button\s+v-if="researchRows.length"\s+ref="researchClearBtn"/);
  });

  it("최근 검색은 실패면 줄이 없어도 묶음을 그려 그 자리에 알린다 — 전체 삭제·목록은 줄이 있을 때만", () => {
    expect(tpl).toMatch(/<section\s+v-if="recentRows.length \|\| recentLoadError"\s+class="skx-history__group"\s+aria-labelledby="skx-history-recent"/);
    expect(recentSection).toMatch(/<button\s+v-if="recentRows.length"\s+ref="recentClearBtn"/);
    expect(recentSection).toMatch(
      /<SkxInlineError\s+v-if="recentLoadError"\s+class="skx-history__notice"\s+role="status"\s+:message="recentLoadError"\s+:busy="retrying"\s+@retry="retryLoad"\s+\/>/,
    );
    expect(recentSection).toMatch(/<ul v-if="recentRows.length" class="skx-history__list">/);
  });

  it("'아직 검색 기록이 없어요'는 두 묶음 모두 비었고 실패가 없을 때만 — 옛 한 줄 실패 문구는 없다", () => {
    expect(tpl).toMatch(
      /<p\s+v-if="!researchRows.length && !recentRows.length && !researchLoadError && !recentLoadError"\s+class="skx-history__empty"\s+role="status"\s*>\s*\{\{ SIDEBAR_EMPTY \}\}\s*<\/p>/,
    );
    expect(SIDEBAR_EMPTY).toBe("아직 검색 기록이 없어요.");
    expect(src).not.toContain("잠시 뒤 다시 열어 주세요");
    expect(src).not.toContain("listFailed");
  });

  it("[다시 시도]는 세 종류를 다시 읽고, 도는 동안 다시 누르면 무시한다", () => {
    expect(js).toMatch(
      /async function retryLoad\(\) \{\s*if \(retrying\.value\) return;\s*retrying\.value = true;\s*try \{\s*await history\.refresh\(\);\s*\} finally \{\s*retrying\.value = false;\s*\}\s*\}/,
    );
  });
});

describe("사이드바 — 사이트 데이터 저장이 막힌 브라우저", () => {
  it("마운트 뒤 브라우저 ID 를 저장했는지 보고, 못 했으면 목록 아래 한 줄", () => {
    expect(js).toContain('import { useBrowserIdPersisted } from "~/composables/useBrowserId";');
    expect(js).toContain("storageBlocked.value = !useBrowserIdPersisted();");
    expect(tpl).toMatch(
      /<SkxInlineError\s+v-if="storageBlocked"\s+class="skx-history__notice"\s+role="status"\s+:message="SIDEBAR_NOTICE\.storageBlocked"\s+\/>\s*<\/template>\s*<\/ClientOnly>/,
    );
  });
});

describe("사이드바 — 줄 안내의 알림 세기", () => {
  // 사이드바는 페이지마다 새로 그려진다 — 지난 목록 실패·저장 차단 안내가 화면을 옮길 때마다 alert 로 다시 끊고 읽히지 않게 status
  it("사이드바의 줄 안내는 모두 role=status 다", () => {
    const notices = tpl.match(/<SkxInlineError\b[^>]*>/g) ?? [];
    expect(notices).toHaveLength(3);
    for (const n of notices) expect(n).toMatch(/\srole="status"/);
  });
});

describe("사이드바 — 줄 안내 자리", () => {
  it("줄 안내는 묶음 제목·줄 글과 같은 왼쪽 선에 맞추기만 한다(색·글자는 공통 구역)", () => {
    const css = src.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] ?? "";
    const rule = css.match(/\.skx-history__notice \{([^}]*)\}/)?.[1] ?? "";
    expect(rule.trim()).toBe("padding: 0.2rem 0.4rem;");
  });
});

// 오류 목록 재감사(2026-10-17): 지우기 확인 칸(앱 안 alertdialog)의 문구가 합쇼체이고 두 문장이 한 줄이었다
describe("사이드바 — 지우기 확인 문구", () => {
  const texts = js.slice(js.indexOf("const CLEAR_TEXT"), js.indexOf("const POLL_MS"));

  it("해요체이고 문장마다 줄을 바꾼다 — 확인 칸 글은 pre-line", () => {
    expect(texts).not.toMatch(/습니다|하세요/);
    expect(texts).toContain("기록을 모두 지울까요?\\n보고서 자체는 지워지지 않아요.");
    expect(texts).toContain("기록은 지워지지 않아요.");
    expect(texts).toContain('"이 연구 기록을 지울까요?\\n보고서 자체는 지워지지 않아요."');
    const css = src.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] ?? "";
    expect(css.match(/\.skx-history__confirm-text \{([^}]*)\}/)?.[1]).toContain("white-space: pre-line;");
  });
});

describe("보존 화면 분류 목록(CategoryAccordion) — 빈 상태", () => {
  it("해요체 — 구조는 그대로 두고 말만 바꾼다", () => {
    const accordion = read("components/CategoryAccordion.vue");
    expect(accordion).toContain("<p>검색 결과가 표시돼요</p>");
    expect(accordion).not.toContain("표시됩니다");
  });
});
