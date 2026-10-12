// frontend/tests/unit/sidebarResearch.test.ts
import { describe, expect, it } from "vitest";
import { olderToggle, statusStageLine } from "~/utils/sidebarResearch";

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

describe("olderToggle — 구분선 아래 '이전 연구 [n]' 한 줄", () => {
  it("접혀 있으면 '이전 연구'와 숨은 수 칩, 펼치면 '접기'", () => {
    expect(olderToggle(false, 3)).toEqual({ label: "이전 연구", count: 3, ariaLabel: "이전 연구 3건 더 보기" });
    expect(olderToggle(true, 0)).toEqual({ label: "접기", count: null, ariaLabel: "이전 연구 접기" });
  });
});
