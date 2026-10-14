// frontend/tests/unit/sidebarResearch.test.ts
import { describe, expect, it } from "vitest";
import { EXPLORE_WEIGHT, SYNTH_WEIGHT, overallFraction } from "~/utils/researchProgress";
import { olderToggle, stageProgress, statusStageLine } from "~/utils/sidebarResearch";

describe("statusStageLine — 진행 중인 연구 줄의 단계 글(기록의 상태·stage 만, 숫자 없이)", () => {
  it("계획 중·순서를 기다리는 중", () => {
    expect(statusStageLine({ status: "created", stage: "created" })).toBe("계획 중");
    expect(statusStageLine({ status: "planning", stage: "created" })).toBe("계획 중");
    expect(statusStageLine({ status: "approved", stage: "planned" })).toBe("대기 중");
    expect(statusStageLine({ status: "queued", stage: "planned" })).toBe("대기 중");
  });

  it("실행 중은 stage 로 가른다 — 탐색을 마쳤으면(explored) 보고서 작성, 아니면 근거 수집", () => {
    expect(statusStageLine({ status: "running", stage: "planned" })).toBe("근거 수집 중");
    expect(statusStageLine({ status: "running", stage: "explored" })).toBe("보고서 작성 중");
    expect(statusStageLine({ status: "running", stage: "synthesized" })).toBe("보고서 작성 중");
  });

  it("승인 대기·끝난 잡·상태를 모르는 기록은 null — 완료 줄에는 아무것도 붙이지 않는다(배지가 말한다)", () => {
    for (const status of ["awaiting_approval", "completed", "failed", "canceled"]) {
      expect(statusStageLine({ status, stage: "synthesized" })).toBeNull();
    }
    expect(statusStageLine(undefined)).toBeNull();
    expect(statusStageLine(null)).toBeNull();
  });
});

describe("stageProgress — 진행 중인 연구 줄의 진행 막대(지난 단계까지 채움 + 지금 단계 구간)", () => {
  const collectEnd = EXPLORE_WEIGHT / (EXPLORE_WEIGHT + SYNTH_WEIGHT);

  it("연구 화면 큰 막대와 같은 구간 경계 — 계획·순서 대기 0, 근거 수집 0~탐색 몫, 보고서 작성 탐색 몫~1", () => {
    for (const status of ["created", "planning", "approved", "queued"]) {
      expect(stageProgress({ status, stage: "planned" })).toEqual({ start: 0, span: 0 });
    }
    expect(stageProgress({ status: "running", stage: "planned" })).toEqual({ start: 0, span: collectEnd });
    for (const stage of ["explored", "synthesized"]) {
      const r = stageProgress({ status: "running", stage })!;
      expect(r.start).toBeCloseTo(collectEnd);
      expect(r.start + r.span).toBeCloseTo(1);
    }
  });

  it("연구 화면 막대의 값은 늘 그 단계 구간 안이다 — 근거 수집 중 어느 값이든, 보고서 작성 중 어느 값이든", () => {
    const collect = stageProgress({ status: "running", stage: "planned" })!;
    const write = stageProgress({ status: "running", stage: "explored" })!;
    for (const e of [0, 0.3, 1]) {
      const v = overallFraction("collect", e, 0);
      expect(v).toBeGreaterThanOrEqual(collect.start - 1e-9);
      expect(v).toBeLessThanOrEqual(collect.start + collect.span + 1e-9);
    }
    for (const s of [0, 0.5, 1]) {
      const v = overallFraction("write", 1, s);
      expect(v).toBeGreaterThanOrEqual(write.start - 1e-9);
      expect(v).toBeLessThanOrEqual(write.start + write.span + 1e-9);
    }
  });

  it("승인 대기·끝난 잡·상태 모름은 막대 없음(null) — 단계 글과 같은 줄에만 선다", () => {
    for (const status of ["awaiting_approval", "completed", "failed", "canceled"]) {
      expect(stageProgress({ status, stage: "synthesized" })).toBeNull();
    }
    expect(stageProgress(undefined)).toBeNull();
    expect(stageProgress(null)).toBeNull();
  });
});

describe("olderToggle — 구분선 아래 '이전 연구 [n]' 한 줄", () => {
  it("접혀 있으면 '이전 연구'와 숨은 수 칩, 펼치면 '접기'", () => {
    expect(olderToggle(false, 3)).toEqual({ label: "이전 연구", count: 3, ariaLabel: "이전 연구 3건 더 보기" });
    expect(olderToggle(true, 0)).toEqual({ label: "접기", count: null, ariaLabel: "이전 연구 접기" });
  });
});
