// frontend/tests/unit/readingNextActions.test.ts
// 참고문헌 선택하기의 다음 단계 버튼 묶음을 머리(소개 옆)에도 둔다(사용자 요청 2026-10-13). 버튼 묶음은 한 컴포넌트
// (ReadingNextActions)를 위·아래 두 번 쓴다 — 두 벌 복사가 아니라서 같은 동작·같은 비활성 조건·같은 문구다. 마운트 도구가 없어
// 화면 약속은 소스 글로 지킨다(저장소의 다른 화면 테스트와 같은 방식)
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { NARROW_QUERY } from "~/utils/sidebarDrawer";
import { cssRules } from "./helpers/cssRules";

const path = (rel: string) => fileURLToPath(new URL(`../../${rel}`, import.meta.url));
const read = (rel: string) => readFileSync(path(rel), "utf-8").replace(/\r\n/g, "\n");
const template = (src: string) => src.slice(src.indexOf("<template>"), src.lastIndexOf("</template>"));
const script = (src: string) => src.slice(src.indexOf("<script setup"));
const count = (src: string, needle: string) => src.split(needle).length - 1;

const ACTIONS = "components/work/ReadingNextActions.vue";

describe("ReadingNextActions — 다음 단계 버튼 묶음", () => {
  it("컴포넌트가 있다", () => {
    expect(existsSync(path(ACTIONS))).toBe(true);
  });

  const src = existsSync(path(ACTIONS)) ? read(ACTIONS) : "";
  const tpl = template(src);

  it("세 갈래 — 주제 없음 [제목 고르기](ghost), 목차를 만듦 [보고서 단계로]+[보고서 다시 만들기](ghost), 그 밖 [보고서 만들기]", () => {
    expect(tpl).toMatch(/<button\s+v-if="noTopic"[^>]*class="rs-btn rs-btn--ghost"[^>]*@click="emit\('go', 'topics'\)"[^>]*>\s*제목 고르기\s*<\/button>/);
    expect(tpl).toMatch(/<template v-else-if="outlineMade">/);
    expect(tpl).toMatch(/@click="emit\('go', 'proposal'\)"[^>]*>\{\{ FINAL_STEP_NAME \}\} 단계로<\/button>/);
    expect(tpl).toMatch(/class="rs-btn rs-btn--ghost"[^>]*:disabled="makeDisabled"[^>]*@click="emit\('make', true\)"[^>]*>\s*\{\{ REMAKE_REPORT \}\}/);
    expect(tpl).toMatch(/v-else[^>]*class="rs-btn"[^>]*:disabled="makeDisabled"[^>]*@click="emit\('make', false\)"[^>]*>\s*\{\{ MAKE_REPORT \}\}/);
    expect(script(src)).toContain('import { FINAL_STEP_NAME, MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";');
  });

  it("비활성 까닭(hint)을 버튼 곁에 보이고 aria-describedby 로 잇는다 — id 는 자리(where)마다 달라 두 묶음이 겹치지 않는다", () => {
    expect(tpl).toMatch(/<p v-if="hint" :id="hintId" class="rs-muted">\{\{ hint \}\}<\/p>/);
    expect(script(src)).toContain("const hintId = computed(() => `wk-reading-next-hint-${props.where}`);");
    expect(script(src)).toContain("const describedBy = computed(() => (props.hint ? hintId.value : undefined));");
    // [제목 고르기]·[보고서 다시 만들기]·[보고서 만들기] — 까닭이 있을 때만 이어진다
    expect(count(tpl, ':aria-describedby="describedBy"')).toBe(3);
    expect(script(src)).toMatch(/where: "top" \| "bottom";/);
  });

  it("상태는 받기만 하고 저장·목차 생성은 하지 않는다 — 누르면 go·make 를 올려 보낸다", () => {
    expect(script(src)).toMatch(/defineEmits<\{ go: \[step: WorkStep\]; make: \[again: boolean\] \}>\(\)/);
    expect(src).not.toMatch(/useWorkApi|createOutline|busy/);
  });
});

describe("ReadingStep — 위(소개 옆)·아래(표 밑) 두 곳에 같은 묶음", () => {
  const src = read("components/work/ReadingStep.vue");
  const tpl = template(src);
  const js = script(src);

  it("ReadingNextActions 를 두 번 — where 만 다르고 같은 상태(nextActions)·같은 핸들러를 넘긴다", () => {
    expect(js).toContain('import ReadingNextActions from "~/components/work/ReadingNextActions.vue";');
    expect(count(tpl, "<ReadingNextActions")).toBe(2);
    expect(tpl).toContain(
      '<ReadingNextActions class="wk-screen__lead-actions" where="top" v-bind="nextActions" @go="emit(\'go\', $event)" @make="makeOutline" />',
    );
    expect(tpl).toContain(
      '<ReadingNextActions class="wk-screen__next" where="bottom" v-bind="nextActions" @go="emit(\'go\', $event)" @make="makeOutline" />',
    );
    // 버튼을 화면에 직접 두 벌 적지 않는다
    expect(tpl).not.toContain("makeOutline(");
    expect(tpl).not.toMatch(/<button[^>]*>\s*\{\{ (MAKE_REPORT|REMAKE_REPORT) \}\}/);
    expect(tpl).not.toContain("제목 고르기");
  });

  it("비활성 조건은 한 곳에서 — 읽기 전용·저장 중(busy)·만들 수 없음. busy 잠금을 두 묶음이 함께 써 두 번 눌리지 않는다", () => {
    expect(js).toContain("const makeDisabled = computed(() => readOnly.value || busy.value || !canOutline.value);");
    expect(js).toMatch(
      /const nextActions = computed\(\(\) => \(\{\s*noTopic: reading\.value\?\.topic_id === null,\s*outlineMade: outlineMade\.value,\s*makeDisabled: makeDisabled\.value,\s*hint: hint\.value,\s*\}\)\);/,
    );
    // 위·아래 어느 쪽을 눌러도 같은 makeOutline — 들어가자마자 busy 를 보고 돌아선다
    expect(js).toMatch(/async function makeOutline\(again: boolean\): Promise<void> \{\s*if \(busy\.value \|\| readOnly\.value \|\| !canOutline\.value\) return;/);
  });

  it("위 묶음은 읽기 목록을 불러온 뒤에만 — 머리의 소개와 한 줄(wk-screen__lead)에, 아래 묶음은 표 밑(v-else 갈래)에", () => {
    const head = tpl.slice(tpl.indexOf('<header class="wk-screen__head">'), tpl.indexOf("</header>"));
    expect(head).toMatch(
      /<div v-if="reading" class="wk-screen__lead">\s*(?:<!--[^]*?-->\s*)?<p v-if="intro" class="rs-muted wk-screen__intro">\{\{ intro \}\}<\/p>\s*<ReadingNextActions[^>]*where="top"/,
    );
    const body = tpl.slice(tpl.indexOf("<template v-else>"));
    expect(body).toMatch(/<ReadingNextActions[^>]*where="bottom"/);
    expect(body.indexOf("<ReadingTable")).toBeLessThan(body.indexOf('where="bottom"'));
  });
});

describe("work.css — 넓으면 소개 옆, 좁으면 소개 아래", () => {
  const rules = cssRules(read("assets/css/work.css"));
  const rule = (selector: string, at = "") => rules.find((r) => r.at === at && r.selectors.includes(selector));

  it("소개와 버튼 묶음을 한 줄에 두고, 소개가 좁아지면(오른쪽 패널을 연 본문 칸) 버튼이 아래로 감긴다", () => {
    expect(rule(".wk-screen__lead")?.decls.get("display")).toBe("flex");
    expect(rule(".wk-screen__lead")?.decls.get("flex-wrap")).toBe("wrap");
    expect(rule(".wk-screen__intro")?.decls.get("flex")).toMatch(/^1 1 \d+(\.\d+)?rem$/);
    expect(rule(".wk-screen__intro")?.decls.get("min-width")).toBe("0");
    // 같은 줄이면 오른쪽 끝, 감겨도 오른쪽 — 소개 글을 밀지 않는다
    expect(rule(".wk-screen__lead-actions")?.decls.get("margin-left")).toBe("auto");
    expect(rule(".wk-screen__lead-actions")?.decls.get("justify-content")).toBe("flex-end");
  });

  it(`좁은 화면 기준(${NARROW_QUERY} — 앱의 휴대폰 배치 기준, utils/sidebarDrawer)에서는 소개 아래로 내리고 왼쪽에 붙인다`, () => {
    const at = `@media ${NARROW_QUERY}`;
    expect(rule(".wk-screen__lead", at)?.decls.get("flex-direction")).toBe("column");
    expect(rule(".wk-screen__lead-actions", at)?.decls.get("margin-left")).toBe("0");
    expect(rule(".wk-screen__lead-actions", at)?.decls.get("justify-content")).toBe("flex-start");
  });

  it("새 규칙은 배치만 — 색 값을 쓰지 않는다", () => {
    const mine = rules.filter((r) => r.selectors.some((s) => s.startsWith(".wk-screen__lead") || s.startsWith(".wk-screen__intro")));
    expect(mine.length).toBeGreaterThan(0);
    for (const r of mine) {
      for (const [prop, value] of r.decls) {
        expect(prop).not.toMatch(/color|background|border|shadow/);
        expect(value).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
      }
    }
  });
});
