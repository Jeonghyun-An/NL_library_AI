// frontend/utils/relevance.ts
// 관련도 알약(RelevanceBadge)의 순수 계산 — 퍼센트 내림·팝오버 링 목록·화면 밖으로 안 나가는 위치

export interface RelevanceRing {
  key: "title" | "content";
  label: string;
  pct: number;
  variant: "title" | "content";
}

/**
 * 점수(0~1)를 정수 퍼센트로. 내린다 — 99.6% 가 100% 로 올림 표기되는 것을 막는다.
 * 소장자료·논문 결과 카드와 두 상세 화면이 모두 이 함수 하나로 퍼센트를 만든다(화면마다 값이 어긋나지 않게).
 * 0.29×100 처럼 부동소수 오차로 28.999… 가 되는 값이 한 칸 덜 나오지 않게 아주 작은 값을 더한 뒤 내린다
 */
export function relevancePct(score: unknown): number {
  if (typeof score !== "number" || !Number.isFinite(score)) return 0;
  return Math.max(0, Math.min(100, Math.floor(score * 100 + 1e-9)));
}

/** 상세 화면 주소의 점수(?score=·title_score=·content_score=) → 퍼센트. 없거나 숫자가 아니면 null(0 점은 0) */
export function queryScorePct(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value;
  if (typeof raw !== "string" || raw.trim() === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? relevancePct(n) : null;
}

function hasScore(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/**
 * 점수(0~1)를 상세 주소에 싣는 문자열로 — 소수 넷째 자리까지 **버림**(끝의 0 은 빼서 0.48·0.9388 처럼). 숫자가 아니거나 유한하지 않으면 null.
 * 서버가 주는 점수는 자릿수가 들쭉날쭉하다(0.9388 · 0.48 · 0.9243096611209584) — 종합·제목·내용 세 점수가 한 규칙으로 실리게 한다.
 * 올리지 않고 버리므로 상세가 읽을 때(relevancePct 는 내림) 퍼센트가 절대 바뀌지 않는다: floor(floor(x·10⁴)/100) = floor(x·100).
 * (반올림이면 0.92999 → 0.93 처럼 92% 가 93% 로 바뀐다.) 부동소수 오차 보정(1e-9)도 relevancePct 와 같은 눈금(×10⁴ 에서는 1e-7)으로 맞춘다.
 * 0~1 밖의 값은 자른다(relevancePct 가 0~100 으로 자르는 것과 같다)
 */
export function scoreParam(value: unknown): string | null {
  if (!hasScore(value)) return null;
  const clamped = Math.max(0, Math.min(1, value));
  return String(Math.floor(clamped * 10000 + 1e-7) / 10000);
}

/**
 * 결과 카드에서 상세 화면 주소로 싣는 점수(?score=·title_score=·content_score=) — 있는(유한한 숫자인) 것만, 모두 scoreParam 규칙으로.
 * 상세 머리의 관련도 알약과 일치율 팝오버가 이 값을 읽는다(queryScorePct). 소장자료·논문 결과가 같은 함수로 싣는다
 */
export function detailScoreParams(item: {
  best_score?: unknown;
  title_score?: unknown;
  content_score?: unknown;
} | null | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  const score = scoreParam(item?.best_score);
  const title = scoreParam(item?.title_score);
  const content = scoreParam(item?.content_score);
  if (score !== null) out.score = score;
  if (title !== null) out.title_score = title;
  if (content !== null) out.content_score = content;
  return out;
}

/** 팝오버의 링 — 제목 일치율 → 내용 일치율 순, 있는 점수만. 둘 다 없으면 빈 목록(알약만 보인다) */
export function relevanceRings(titleScore: unknown, contentScore: unknown): RelevanceRing[] {
  const rings: RelevanceRing[] = [];
  if (hasScore(titleScore)) rings.push({ key: "title", label: "제목 일치율", pct: relevancePct(titleScore), variant: "title" });
  if (hasScore(contentScore)) rings.push({ key: "content", label: "내용 일치율", pct: relevancePct(contentScore), variant: "content" });
  return rings;
}

export interface PopoverRect {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/**
 * 아래에 놓아 본 팝오버(rect)가 화면(viewport)을 넘는지 보고 옮길 값을 준다.
 * shiftX: 좌우로 넘으면 넘는 만큼 민다(왼쪽 여백이 우선). above: 아래로 넘고 알약 위에 자리가 있으면 위로 올린다
 */
export function popoverPlacement(
  rect: PopoverRect,
  anchor: { top: number },
  viewport: { width: number; height: number },
  margin = 8,
): { shiftX: number; above: boolean } {
  let shiftX = 0;
  if (rect.right > viewport.width - margin) shiftX = viewport.width - margin - rect.right;
  if (rect.left + shiftX < margin) shiftX = margin - rect.left;
  const height = rect.bottom - rect.top;
  const overflowsBelow = rect.bottom > viewport.height - margin;
  const above = overflowsBelow && anchor.top - height >= margin;
  return { shiftX, above };
}
