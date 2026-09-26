// frontend/utils/slashCommand.ts
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
