// frontend/utils/deepReadSse.ts
// 딥리드(논문·책 1편과의 대화 — POST /api/books/chat/{cnts_id})의 SSE 조각 읽기와 대화 모양. 서버(services/chat/book_chat.py)는
// `data: {"text": …}` 를 흘리고, 답에서 인용한 대목이 있으면 `data: {"sources": […]}` 하나, 끝에 `data: [DONE]` 을 보낸다.
// 대화는 서버에 저장하지 않는다 — 요청마다 앞 대화를 history 로 싣는다(spec §12-4 D24)

// 출처 대목의 쪽은 저장된 값 그대로다(0부터 센다 — 서버가 LLM 문맥에도 같은 값 [p.X–Y] 를 싣는다, book_chat.py:155)
export interface DeepReadSource {
  page_start: number;
  page_end: number;
  text: string;
}

// pinnedChip 은 화면이 쥐는 값 — 펼친 출처 칩의 번호(BookChat 의 대목 미리보기)
export interface DeepReadMessage {
  role: "user" | "assistant";
  content: string;
  sources?: DeepReadSource[];
  pinnedChip?: number;
}

export type DeepReadEvent = { type: "text"; text: string } | { type: "sources"; sources: DeepReadSource[] } | { type: "done" };

export const CHAT_ERROR_TEXT = "오류가 발생했습니다. 다시 시도해주세요.";
// 닫기·논문 바꾸기로 끊은 답의 꼬리 — 끊긴 답도 대화에 남겨 다음 질문의 history 가 user/assistant 짝을 잃지 않게 한다(06e 정함 21)
export const CHAT_STOPPED_TEXT = "(답을 받다가 멈췄습니다)";
export const CHAT_STOPPED_EMPTY = "(답을 받기 전에 멈췄습니다)";

const DATA = "data: ";

// 받은 조각(chunk)을 앞 조각의 남은 줄(buffer)에 이어 줄 단위로 읽는다. 마지막 줄은 아직 덜 왔을 수 있어 buffer 로 남긴다.
// data: 줄만 읽고, 깨진 JSON·모르는 모양은 버린다. [DONE] 을 만나면 그 뒤 줄은 읽지 않는다(BookChat 의 옛 읽기와 같다)
export function parseSse(buffer: string, chunk: string): { buffer: string; events: DeepReadEvent[] } {
  const lines = (buffer + chunk).split("\n");
  const rest = lines.pop() ?? "";
  const events: DeepReadEvent[] = [];
  for (const line of lines) {
    if (!line.startsWith(DATA)) continue;
    const payload = line.slice(DATA.length).trim();
    if (payload === "[DONE]") {
      events.push({ type: "done" });
      return { buffer: "", events };
    }
    let evt: unknown;
    try {
      evt = JSON.parse(payload);
    } catch {
      continue;
    }
    if (!evt || typeof evt !== "object") continue;
    const { text, sources } = evt as { text?: unknown; sources?: unknown };
    if (typeof text === "string" && text) events.push({ type: "text", text });
    else if (Array.isArray(sources)) events.push({ type: "sources", sources: sources as DeepReadSource[] });
  }
  return { buffer: rest, events };
}
