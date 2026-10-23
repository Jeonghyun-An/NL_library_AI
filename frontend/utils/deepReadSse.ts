// frontend/utils/deepReadSse.ts
// 딥리드(논문·책 1편과의 대화 — POST /api/books/chat/{cnts_id})의 SSE 조각 읽기와 대화 모양·실패 문구. 서버(services/chat/book_chat.py)는
// `data: {"text": …}` 를 흘리고, 답에서 인용한 대목이 있으면 `data: {"sources": […]}` 하나, 끝에 `data: [DONE]` 을 보낸다.
// 답을 만들지 못하면 sources 대신 [DONE] 바로 앞에 `data: {"error": 문구, "code": 갈래}` 를 보낸다(받은 글이 있어도 실패다).
// code 는 not_found(자료 없음)·empty_answer(빈 답)·retrieval_failed(자료 내용 검색 실패)이고, LLM 호출 실패는 code 없이 {error} 만 온다.
// 대화는 서버에 저장하지 않는다 — 요청마다 앞 대화를 history 로 싣는다(spec §12-4 D24)
import { CODE_MESSAGES, ERROR_HINTS, apiErrorMessage, codeMessage, errorKind } from "~/utils/apiErrors";

// 출처 대목의 쪽은 저장된 값 그대로다(0부터 센다). 사람이 보는 쪽은 +1 이다 — 서버는 LLM 문맥 [p.X–Y] 를 +1 쪽으로 싣고
// (book_chat.py _context_label), 화면은 칩 글자(deepRead.sourceLabel)·원문 쪽(sourcePdfTarget)에서 +1 한다
export interface DeepReadSource {
  page_start: number;
  page_end: number;
  text: string;
}

// pinnedChip·pinnedPassage 는 화면이 쥐는 값 — 펼친 근거 묶음(같은 쪽 대목 한 줄 — deepReadCitations.groupSources)의 번호와
// 그 묶음에서 보이는 대목 번호(BookChat 의 근거 목록)
export interface DeepReadMessage {
  role: "user" | "assistant";
  content: string;
  sources?: DeepReadSource[];
  pinnedChip?: number;
  pinnedPassage?: number;
}

// error 의 code 는 서버가 붙인 갈래 — 없거나 글이 아니면 null(LLM 호출 실패 — 옛 서버의 {error} 도 같다).
// 서버의 error 문구는 읽지 않는다 — 화면 말투(해요체)가 섞이지 않게 문구는 화면이 가진다(streamFailure)
export type DeepReadEvent =
  | { type: "text"; text: string }
  | { type: "sources"; sources: DeepReadSource[] }
  | { type: "error"; code: string | null }
  | { type: "done" };

// 질문 글자 수 한도 — 서버 BookChatRequest.message 의 max_length(app/schemas/book.py). 입력 칸 maxlength·글자 수 표시가 같은 값을 쓴다
export const CHAT_MAX_CHARS = 2000;

// 이만큼 아무 데이터도 오지 않으면 화면이 스스로 끊고 실패로 알린다(응답 머리를 기다리는 동안과 글 조각 사이 모두).
// 서버 쪽 제한(LLM 읽기 httpx 90초·nginx proxy_read_timeout 120초)도 '새 데이터가 그만큼 없을 때'라, 멈춘 답을 그보다 먼저 끊는다
export const CHAT_IDLE_TIMEOUT_MS = 60_000;

// 답을 받지 못했을 때(4xx·5xx·네트워크 오류·[DONE] 없이 끊김)의 문구 — 이유(네트워크·서버 등)가 있으면 apiErrorMessage 가 ' — ' 뒤에 붙인다
export const CHAT_ERROR_TEXT = "답을 받지 못했어요";
// 서버가 code 없이 {error} 로 끝낸 답(LLM 호출 실패)
export const CHAT_ANSWER_FAILED = "답을 만들지 못했어요";
// 닫기·논문 바꾸기·[멈춤]으로 끊은 답의 꼬리 — 끊긴 답도 대화에 남겨 다음 질문의 history 가 user/assistant 짝을 잃지 않게 한다(06e 정함 21)
export const CHAT_STOPPED_TEXT = "(답을 받다가 멈췄어요)";
export const CHAT_STOPPED_EMPTY = "(답을 받기 전에 멈췄어요)";
// 옛 서버(오류 code 배포 전)가 대화할 자료를 서지에서 찾지 못했을 때 {error} 가 아닌 보통 글로 보내던 문구
export const LEGACY_NOT_FOUND_TEXT = "도서를 찾을 수 없습니다.";

// 답을 받지 못한 까닭의 문구와, 같은 질문을 그대로 다시 보내 볼 만한가(retryable). 자료가 없거나(not_found) 질문이 서버 검증에
// 걸렸으면(422 — 너무 김 등) 다시 보내도 같은 실패라 화면은 [다시 시도]를 숨긴다
export interface ChatFailureCopy {
  message: string;
  retryable: boolean;
}

// 스트림 {error, code} 의 문구 — code 별 문구(CODE_MESSAGES), code 가 없거나 모르는 값이면 LLM 호출 실패 문구
export function streamFailure(code: string | null): ChatFailureCopy {
  return { message: codeMessage(code) ?? CHAT_ANSWER_FAILED, retryable: code !== "not_found" };
}

// 응답 전·응답 중의 실패(HTTP 오류·네트워크 오류·끊김) — apiErrorMessage 규칙(서버 code·422 검증 사유·이유 붙이기)을 따른다.
// err 는 fetch 가 던진 오류이거나 {status, data}(오류 응답의 상태와 JSON 본문)를 단 오류다
export function requestFailure(err: unknown): ChatFailureCopy {
  return { message: apiErrorMessage(err, CHAT_ERROR_TEXT), retryable: errorKind(err) !== "invalid" };
}

// 오류 응답(4xx·5xx)을 $fetch 의 FetchError 처럼 status·data(JSON 본문 — 아니면 undefined)를 단 오류로 — apiErrorMessage 가 읽는다.
// 딥리드 대화(useDeepReadChat)와 보존 화면의 초안 대화 칸(BookChat.legacy)이 함께 쓴다
export async function chatResponseError(resp: Response): Promise<Error> {
  const data: unknown = await resp.json().catch(() => undefined);
  return Object.assign(new Error(`DeepRead 응답 ${resp.status}`), { status: resp.status, data });
}

// 아무 데이터 없이 CHAT_IDLE_TIMEOUT_MS 가 지나 화면이 끊은 답
export const CHAT_TIMEOUT_FAILURE: Readonly<ChatFailureCopy> = { message: ERROR_HINTS.timeout, retryable: true };

// [DONE] 까지 받은 답이 실패인가 — 옛 서버는 글 조각 없는 빈 답을 정상으로 끝내고, 자료를 못 찾으면 안내를 보통 글로 보냈다
// (새 서버는 둘 다 {error, code} 로 보낸다). 실패면 그 갈래의 code, 정상 답이면 null
export function finishedAnswerCode(text: string): keyof typeof CODE_MESSAGES | null {
  const answer = text.trim();
  if (!answer) return "empty_answer";
  return answer === LEGACY_NOT_FOUND_TEXT ? "not_found" : null;
}

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
    const { text, sources, code } = evt as { text?: unknown; sources?: unknown; code?: unknown };
    if ("error" in evt) {
      events.push({ type: "error", code: typeof code === "string" && code ? code : null });
    } else if (typeof text === "string" && text) events.push({ type: "text", text });
    else if (Array.isArray(sources)) events.push({ type: "sources", sources: sources as DeepReadSource[] });
  }
  return { buffer: rest, events };
}
