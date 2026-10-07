// frontend/utils/queueLine.ts
// 대기 순번 문구 — 딥리서치(잡 대기열)와 연구 어시스턴트(생성 대기열)가 같은 말투를 쓴다
import type { QueueView } from "~/types/research";
import type { WorkGeneration } from "~/types/work";

function etaPart(etaSec: number | null | undefined): string {
  return etaSec != null ? ` · 약 ${Math.max(1, Math.ceil(etaSec / 60))}분` : "";
}

// 대기 카드·진행 패널의 queued 문구 뒤에 덧붙이는 순번. 순번을 모르면(옛 서버·대기 아님) 덧붙이지 않는다
export function queueLine(q: QueueView | null): string | null {
  if (!q) return null;
  if (q.ahead === 0) return "바로 다음 차례입니다";
  return `앞에 ${q.ahead}건${etaPart(q.etaSec)}`;
}

// 생성 한 건의 대기 문구(dispatch.queue_info). 생성은 전역 한 줄이라 다른 연구의 생성이 앞에 있을 수 있다 —
// 그때 "다른 연구 작업 진행 중" 을 함께 보인다. 순번을 아직 모르면(이벤트로 막 들어온 생성) "대기 중",
// 도는 중이면 "쓰는 중", 끝났으면 null
export function genQueueLine(
  g: Pick<WorkGeneration, "status" | "position" | "eta_sec" | "others_ahead">,
): string | null {
  if (g.status === "running") return "쓰는 중";
  if (g.status !== "queued") return null;
  if (g.position == null) return "대기 중";
  if (g.position === 0) return "바로 다음 차례";
  const others = g.others_ahead ? " · 다른 연구 작업 진행 중" : "";
  return `앞에 ${g.position}건${etaPart(g.eta_sec)}${others}`;
}
