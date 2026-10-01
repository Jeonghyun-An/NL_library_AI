// frontend/utils/slashCommand.ts
import { questionProblem } from "./researchInput";

export type SearchModeId = "deep-research";
export type SearchInputKind = "book" | "paper";

export interface SearchMode {
  id: SearchModeId;
  label: string;
  description: string;
  icon: string;
  slash: string;
  placeholder: string;
  available: (kind: SearchInputKind) => boolean;
}

// + 메뉴 항목의 정본. 새 모드는 여기 한 줄을 더하면 메뉴·칩·슬래시가 함께 생긴다.
export const SEARCH_MODES: readonly SearchMode[] = [
  {
    id: "deep-research",
    label: "딥리서치",
    description: "질문을 하위질문으로 나눠 논문을 찾고, 스스로 점검한 뒤 인용이 달린 보고서를 씁니다",
    icon: "/img/ico-ai-related.svg",
    slash: "/deep-research",
    placeholder: "연구 질문을 입력하세요",
    available: (kind) => kind === "paper",
  },
];

export function modesFor(kind: SearchInputKind): SearchMode[] {
  return SEARCH_MODES.filter((m) => m.available(kind));
}

export function parseSlash(input: string): { mode: SearchModeId | null; text: string } {
  const lead = input.trimStart();
  for (const m of SEARCH_MODES) {
    if (lead.slice(0, m.slash.length).toLowerCase() !== m.slash) continue;
    const rest = lead.slice(m.slash.length);
    if (rest !== "" && !/^\s/.test(rest)) continue;
    return { mode: m.id, text: rest.trimStart() };
  }
  return { mode: null, text: input };
}

// 명령 뒤에 공백이나 글이 붙었을 때만 칩으로 바꾼다 — "/deep-research" 까지만 친
// 순간 바꾸면 비슷한 이름의 다른 명령을 치는 중일 수 있다.
export function shouldAutoChip(input: string): boolean {
  const { mode, text } = parseSlash(input);
  return mode !== null && (text !== "" || /\s$/.test(input));
}

// 슬래시 명령 목록에 띄울 명령. 글 전체가 "/" 로 시작하는 한 토큰일 때만 고른다 — 토큰 뒤에
// 공백이 붙으면 shouldAutoChip 이 칩으로 바꾸거나 사용자가 일반 글을 치는 중이다.
// "/딥" 처럼 슬래시 뒤를 한글 라벨로 쳐도 찾게 라벨 접두도 본다.
export function slashSuggestions(input: string, modes: readonly SearchMode[]): SearchMode[] {
  const token = input.trimStart().toLowerCase();
  if (!token.startsWith("/") || /\s/.test(token)) return [];
  const name = token.slice(1);
  return modes.filter((m) => m.slash.startsWith(token) || (name !== "" && m.label.toLowerCase().startsWith(name)));
}

export type PaletteKeyAction = "next" | "prev" | "select" | "close" | "block";

// 슬래시 명령 목록이 떠 있을 때 입력창의 키를 어떻게 쓸지 정한다. null 이면 목록의 키가 아니다 —
// 화면은 막지 않고 입력창·기존 엔터 처리에 그대로 넘긴다.
export function paletteKeyAction(key: string, state: { composing: boolean; shift: boolean }): PaletteKeyAction | null {
  switch (key) {
    case "ArrowDown":
      return state.composing ? null : "next";
    case "ArrowUp":
      return state.composing ? null : "prev";
    case "Enter":
      // 한글 조합 중의 엔터는 글자 확정용이다 — 고르지 않되 페이지의 검색 핸들러로도 보내지 않는다
      if (state.shift) return null;
      return state.composing ? "block" : "select";
    case "Tab":
      // Shift+Tab 은 초점을 뒤로 보내는 키다 — 고르지 않고 초점이 빠지며 목록이 닫힌다
      return state.composing || state.shift ? null : "select";
    case "Escape":
      return "close";
    default:
      return null;
  }
}

export interface SlashSubmit {
  mode: SearchModeId;
  // 서버로 보낼 질문(앞뒤 공백을 뗀 글)
  question: string;
  // 입력창에 되돌려 쓸 값 — 슬래시 접두를 뗀 글. 접두가 없었으면 null(입력창을 건드리지 않는다)
  stripped: string | null;
  // 보내기 전에 알릴 검증 오류. 이때도 접두는 떼어 칩으로 바꾼다 — 사용자는 질문만 고치면 된다
  problem: string | null;
}

// 입력창의 제출을 딥리서치로 보낼지와 그때 할 일을 정한다. 칩도 명령도 없으면 null(원래 검색).
export function planSlashSubmit(
  text: string,
  activeId: SearchModeId | null,
  available: readonly SearchMode[],
): SlashSubmit | null {
  const slash = parseSlash(text);
  const mode = activeId ?? (available.some((m) => m.id === slash.mode) ? slash.mode : null);
  if (!mode) return null;
  const question = (slash.mode ? slash.text : text).trim();
  return { mode, question, stripped: slash.mode ? slash.text : null, problem: questionProblem(question) };
}

// 컴포넌트가 스스로 emit 한 값이 v-model 로 되돌아온 것인지 가린다. 되돌아온 값에 반응해
// 방금 넣은 검증 오류를 지우면 오류가 한 번도 보이지 않는다. 한 번 보면 잊는다 — 부모가 값을
// 받지 않아 되돌아오지 않았으면 다음 변화는 사용자의 것이다.
export function createEchoGuard() {
  let pending: string | null = null;
  return {
    mark(value: string): void {
      pending = value;
    },
    take(value: string): boolean {
      const echoed = pending !== null && pending === value;
      pending = null;
      return echoed;
    },
  };
}
