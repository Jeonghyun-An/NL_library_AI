// frontend/utils/deepReadHistory.ts
// 딥리드 대화 기록 — 이 브라우저(localStorage)에 자료별 대화를 남겨 사이드바 'DeepRead' 묶음에 보이고, 그 자료의 딥리드를 다시 열면
// 대화를 이어 보인다. 대표 요청(2026-10-26): 사이드바에 딥리서치만이 아니라 딥리드 기록도 — 딥리드를 더 드러내게.
// 기록 하나 = 대화(세션) 하나. 한 자료에 대화가 여럿일 수 있다([새 대화] — 사용자 2026-10-26). 질문·답과 답마다 인용한 출처 원문
// 조각을 함께 남겨, 다시 열면 출처를 펼쳐 볼 수 있고 이어 묻는 질문은 앞 대화를 history 로 받는다(멀티턴).
// 서버 기록(검색·딥리서치 — app/api/history.py)과 따로 둔다: 서버 배포 없이 화면만으로 내보내려고(그날 운영 재적재 중이었다).
// 그래서 기록은 브라우저마다 따로다(딥리서치가 브라우저 ID 에 묶인 것과 같은 범위).
import { computed, ref } from "vue";
import { safeLocalStorage } from "~/utils/browserId";
import type { DocKind } from "~/utils/deepRead";
import type { DeepReadMessage, DeepReadSource } from "~/utils/deepReadSse";

export const DEEP_READ_HISTORY_KEY = "skx-deepread-history-v1";
// 남기는 대화 수 — 넘으면 가장 오래된 대화부터 뺀다
export const DEEP_READ_HISTORY_MAX = 30;
// 자료마다 남기는 말(질문·답) 수 — 넘으면 앞에서부터 뺀다(질문부터 시작하게)
export const DEEP_READ_MESSAGES_MAX = 40;
// 출처 원문 조각 하나에 남기는 글자 수 — 서버 조각보다 넉넉히(펼친 미리보기가 잘리지 않게). 저장소가 차면 오래된 대화부터 뺀다
const SOURCE_TEXT_MAX = 4000;

export interface DeepReadHistoryItem {
  // 대화(세션) id
  id: string;
  // 자료 id(cntsId)
  docId: string;
  title: string;
  kind: DocKind;
  updatedAt: string;
  messages: DeepReadMessage[];
}

function isMessage(m: unknown): m is DeepReadMessage {
  const v = m as DeepReadMessage | null;
  return !!v && (v.role === "user" || v.role === "assistant") && typeof v.content === "string";
}

function isItem(x: unknown): x is DeepReadHistoryItem {
  const v = x as DeepReadHistoryItem | null;
  return (
    !!v &&
    typeof v.id === "string" &&
    !!v.id &&
    typeof v.docId === "string" &&
    !!v.docId &&
    typeof v.title === "string" &&
    (v.kind === "paper" || v.kind === "book") &&
    typeof v.updatedAt === "string" &&
    Array.isArray(v.messages) &&
    v.messages.every(isMessage)
  );
}

function readAll(): DeepReadHistoryItem[] {
  try {
    const raw = safeLocalStorage()?.getItem(DEEP_READ_HISTORY_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter(isItem) : [];
  } catch {
    return [];
  }
}

// 저장소가 가득 차면(QuotaExceeded) 오래된 대화부터 빼며 다시 쓴다. 맨 앞(새로 남길 대화) 하나도 못 들어가면 저장소를 건드리지 않고
// keep(지금까지의 목록)을 돌려준다 — 새 대화 하나 때문에 남긴 기록이 통째로 지워지지 않게(리뷰 지적). 빈 목록은 키를 지운다
function writeAll(list: DeepReadHistoryItem[], keep: DeepReadHistoryItem[] = list): DeepReadHistoryItem[] {
  const ls = safeLocalStorage();
  if (!ls) return list;
  if (!list.length) {
    try {
      ls.removeItem(DEEP_READ_HISTORY_KEY);
    } catch {
      // 막힌 저장소 — 이 탭의 목록만 비운다
    }
    return [];
  }
  let rest = list;
  while (rest.length) {
    try {
      ls.setItem(DEEP_READ_HISTORY_KEY, JSON.stringify(rest));
      return rest;
    } catch {
      rest = rest.slice(0, -1);
    }
  }
  return keep;
}

function trimSource(s: DeepReadSource): DeepReadSource {
  return { page_start: s.page_start, page_end: s.page_end, text: (s.text || "").slice(0, SOURCE_TEXT_MAX) };
}

/** 남길 대화 — 화면 상태(펼친 출처)는 빼고, 끝의 DEEP_READ_MESSAGES_MAX 개만(질문에서 시작하게) */
export function cleanMessages(messages: readonly DeepReadMessage[]): DeepReadMessage[] {
  let start = Math.max(0, messages.length - DEEP_READ_MESSAGES_MAX);
  while (start < messages.length && messages[start]?.role !== "user") start += 1;
  return messages.slice(start).map((m) =>
    m.sources?.length ? { role: m.role, content: m.content, sources: m.sources.map(trimSource) } : { role: m.role, content: m.content },
  );
}

// 탭 안에서 함께 쓰는 목록 — 사이드바와 딥리드 창이 같은 값을 본다. 다른 탭의 저장은 storage 사건으로 따라온다
const items = ref<DeepReadHistoryItem[]>([]);
let loaded = false;

function ensureLoaded(): void {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  items.value = readAll();
  window.addEventListener("storage", (e) => {
    if (e.key === DEEP_READ_HISTORY_KEY || e.key === null) items.value = readAll();
  });
}

function copyMessages(list: readonly DeepReadMessage[]): DeepReadMessage[] {
  return list.map((m) => ({ ...m, sources: m.sources?.map((s) => ({ ...s })) }));
}

/** 새 대화 id */
export function newSessionId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/** 되살릴 대화 — 고른 대화(sessionId, 그 자료의 것일 때)가 있으면 그것, 없으면 그 자료의 가장 최근 대화. 없으면 null */
export function savedSession(docId: string, sessionId?: string | null): { id: string; messages: DeepReadMessage[] } | null {
  ensureLoaded();
  const picked = sessionId ? items.value.find((i) => i.id === sessionId && i.docId === docId) : undefined;
  const hit =
    picked ?? items.value.filter((i) => i.docId === docId).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0];
  return hit ? { id: hit.id, messages: copyMessages(hit.messages) } : null;
}

/** 대화를 남긴다(맨 앞으로) — 답이 없으면 남기지 않는다 */
export function saveConversation(
  id: string,
  docId: string,
  title: string,
  kind: DocKind,
  messages: readonly DeepReadMessage[],
): void {
  ensureLoaded();
  if (!id || !docId) return;
  const cleaned = cleanMessages(messages);
  if (!cleaned.some((m) => m.role === "assistant")) return;
  const item: DeepReadHistoryItem = {
    id,
    docId,
    title: title || docId,
    kind,
    updatedAt: new Date().toISOString(),
    messages: cleaned,
  };
  const rest = items.value.filter((i) => i.id !== id);
  items.value = writeAll([item, ...rest].slice(0, DEEP_READ_HISTORY_MAX), items.value);
}

export function removeConversation(id: string): void {
  ensureLoaded();
  items.value = writeAll(items.value.filter((i) => i.id !== id));
}

export function clearConversations(): void {
  ensureLoaded();
  items.value = writeAll([]);
}

/** 사이드바용 — 최신순 목록 */
export function useDeepReadHistory() {
  ensureLoaded();
  const sorted = computed(() => [...items.value].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)));
  return { items: sorted, remove: removeConversation, clear: clearConversations };
}

/** 기록을 누르면 갈 곳 — 그 자료의 상세 화면에서 딥리드 창을 연 채로(?chat=1), 그 대화로(?dr=대화 id) */
export function deepReadRoute(item: Pick<DeepReadHistoryItem, "id" | "docId" | "kind">): {
  path: string;
  query: { chat: string; dr: string };
} {
  const doc = encodeURIComponent(item.docId);
  return { path: item.kind === "paper" ? `/papers/${doc}` : `/books/${doc}`, query: { chat: "1", dr: item.id } };
}

/** 대화의 첫 질문 — 한 자료에 대화가 여럿일 때 줄을 가른다 */
export function firstQuestion(item: Pick<DeepReadHistoryItem, "messages">): string {
  return item.messages.find((m) => m.role === "user")?.content ?? "";
}

/** 질문 수 — 사이드바 줄의 '질문 n개' */
export function questionCount(item: Pick<DeepReadHistoryItem, "messages">): number {
  return item.messages.filter((m) => m.role === "user").length;
}

// 테스트 — 모듈 상태를 비운다
export function resetDeepReadHistoryForTest(): void {
  loaded = false;
  items.value = [];
}
