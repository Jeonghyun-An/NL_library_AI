// frontend/tests/unit/queueLine.test.ts
import { describe, expect, it } from "vitest";
import { genQueueLine, queueLine } from "~/utils/queueLine";
import { queueLine as queueLineFromEvents } from "~/utils/researchEvents";

describe("queueLine — 옮긴 자리", () => {
  it("researchEvents 가 같은 함수를 다시 내보낸다(호출처·기존 테스트가 그대로다)", () => {
    expect(queueLineFromEvents).toBe(queueLine);
    expect(queueLine({ ahead: 2, etaSec: 1500 })).toBe("앞에 2건 · 약 25분");
    expect(queueLine({ ahead: 0, etaSec: null })).toBe("바로 다음 차례입니다");
    expect(queueLine(null)).toBeNull();
  });
});

describe("genQueueLine — 생성 대기 문구", () => {
  it("앞 건수·분 단위 어림(올림·최소 1분)·다른 연구 작업을 잇는다", () => {
    expect(genQueueLine({ status: "queued", position: 2, eta_sec: 60, others_ahead: true }))
      .toBe("앞에 2건 · 약 1분 · 다른 연구 작업 진행 중");
    expect(genQueueLine({ status: "queued", position: 3, eta_sec: 121, others_ahead: false })).toBe("앞에 3건 · 약 3분");
    expect(genQueueLine({ status: "queued", position: 1, eta_sec: 0 })).toBe("앞에 1건 · 약 1분");
  });

  it("어림을 모르면(표본 없음·옛 서버) 건수만, 다른 연구 표시는 따로 붙인다", () => {
    expect(genQueueLine({ status: "queued", position: 2, eta_sec: null, others_ahead: false })).toBe("앞에 2건");
    expect(genQueueLine({ status: "queued", position: 2 })).toBe("앞에 2건");
    expect(genQueueLine({ status: "queued", position: 1, eta_sec: null, others_ahead: true }))
      .toBe("앞에 1건 · 다른 연구 작업 진행 중");
  });

  it("앞에 없으면 다음 차례, 순번을 아직 모르면 대기 중이다", () => {
    expect(genQueueLine({ status: "queued", position: 0, eta_sec: null, others_ahead: false })).toBe("바로 다음 차례");
    expect(genQueueLine({ status: "queued", position: null })).toBe("대기 중");
  });

  it("도는 중이면 쓰는 중, 끝났으면 null", () => {
    expect(genQueueLine({ status: "running", position: null })).toBe("쓰는 중");
    expect(genQueueLine({ status: "done", position: null })).toBeNull();
    expect(genQueueLine({ status: "failed", position: 2 })).toBeNull();
    expect(genQueueLine({ status: "canceled", position: null })).toBeNull();
  });
});
