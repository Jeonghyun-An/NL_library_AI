// frontend/tests/unit/landingExamplesFloat.test.ts
// 랜딩 DeepResearch 예시 연구 카드가 로고·전환·입력창을 밀어 올리지 않는다(사용자 요청 2026-10-16) — 카드는 패널 아래에 띄워 세로
// 가운데 정렬 계산에서 빠지고, 화면 아래를 넘는 만큼은 .skx-app 의 아래 바깥 여백으로 페이지를 늘린다(가운데 정렬 기준 높이는 그대로)
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { blockOrThrow } from "./helpers/themeCss";

const index = readFileSync(resolve(__dirname, "../../pages/index.vue"), "utf-8");

/** 블록 안의 일반 속성 `이름: 값;` 전부(helpers 의 declarations 는 --skx-* 토큰만 읽는다) */
function props(selector: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [, name, value] of blockOrThrow(selector).matchAll(/([a-z-]+)\s*:\s*([^;]+);/g)) {
    if (name && value) out[name] = value.trim();
  }
  return out;
}

describe("랜딩 — 예시 연구 카드는 레이아웃 높이에 들지 않는다", () => {
  it("예시 카드는 논문 패널 안의 띄우는 칸(.skx-panel__float)에만 있고, DeepResearch 모드일 때만 선다", () => {
    expect(index).toMatch(
      /<div v-if="deepResearch" ref="examplesRef" class="skx-panel__float">\s*<ResearchExampleCards \/>\s*<\/div>/,
    );
    expect(index.match(/<ResearchExampleCards\b/g)).toHaveLength(1);
  });

  it("띄우는 칸은 패널 바로 아래 절대 위치(패널 안 간격 2rem)이고, 패널이 그 기준이다", () => {
    expect(props(".skx-panel__float")).toMatchObject({
      position: "absolute",
      top: "100%",
      left: "0",
      right: "0",
      "margin-top": "2rem",
    });
    expect(props(".skx-panel")).toMatchObject({ position: "relative", gap: "2rem" });
  });

  it("넘친 만큼은 .skx-app 의 아래 바깥 여백으로만 늘린다(안쪽 여백·높이는 가운데 정렬 기준이라 건드리지 않는다)", () => {
    expect(index).toContain(
      '<div class="skx-app" :style="examplesOverflow ? { marginBottom: `${examplesOverflow}px` } : undefined">',
    );
    // 카드·본문·입력창 쪽 크기가 바뀌면 다시 재고, 카드가 사라지거나 화면을 떠나면 여백을 걷고 관찰을 끊는다
    expect(index).toMatch(/for \(const el of \[box, contentsRef\.value, contentsInnerRef\.value\]\)/);
    expect(index).toMatch(/if \(!box \|\| typeof ResizeObserver === "undefined"\) \{\s*examplesOverflow\.value = 0;/);
    expect(index).toMatch(/onUnmounted\(\(\) => \{[\s\S]*?examplesObserver\?\.disconnect\(\);[\s\S]*?\}\);/);
  });
});
