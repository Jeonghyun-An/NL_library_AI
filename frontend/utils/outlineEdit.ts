// frontend/utils/outlineEdit.ts
import type { Outline, OutlinePut } from "~/types/work";
import { GROUP_LABEL_MAX } from "~/utils/readingList";

// 서버 PUT 검증(services/research_work/shapes.py 의 같은 이름)과 같은 상한 — 넘기면 422 로 거절된다.
// 글자 수는 코드 포인트로 센다(파이썬 len). 묶음 이름 상한 GROUP_LABEL_MAX 는 readingList.ts 가 내보낸다
// (Nuxt 자동 import 는 같은 이름을 두 파일이 내보내면 경고하고 하나를 버린다)
export const OUTLINE_QUESTION_MAX = 300;
export const OUTLINE_METHOD_MAX = 1000;
const QUESTION_MIN = 2;

// 목차 화면이 고치는 것 — 묶음 이름·묶음 사이 논문 배정·연구 질문·방법. 묶음 수·키는 서버가 정하고 바꾸지 않는다
export interface OutlineDraft {
  groups: { key: string; name: string; papers: string[] }[];
  question: string;
  method: string;
}

function chars(s: string): number {
  return Array.from(s).length;
}

// 서버가 준 묶음을 순서·배정 그대로 옮긴다. 연구 질문은 저장된 값, 없으면 첫 후보에서 시작한다
export function draftFrom(outline: Outline): OutlineDraft {
  return {
    groups: outline.groups.map((g) => ({ key: g.key, name: g.name, papers: [...g.papers] })),
    question: outline.question ?? outline.questions[0] ?? "",
    method: outline.method,
  };
}

// 논문 하나를 다른 묶음 끝으로 옮긴다. 없는 논문·없는 묶음·이미 그 묶음이면 같은 초안을 돌려준다.
// 묶음이 비는 것은 막지 않는다 — 옮기는 중간에는 빌 수 있고, 저장 전에 outlineProblems 가 알린다
export function movePaper(d: OutlineDraft, cnts: string, toKey: string): OutlineDraft {
  const from = d.groups.find((g) => g.papers.includes(cnts));
  if (!from || from.key === toKey || !d.groups.some((g) => g.key === toKey)) return d;
  return {
    ...d,
    groups: d.groups.map((g) => {
      if (g.key === from.key) return { ...g, papers: g.papers.filter((p) => p !== cnts) };
      if (g.key === toKey) return { ...g, papers: [...g.papers, cnts] };
      return g;
    }),
  };
}

export function renameGroup(d: OutlineDraft, key: string, name: string): OutlineDraft {
  if (!d.groups.some((g) => g.key === key)) return d;
  return { ...d, groups: d.groups.map((g) => (g.key === key ? { ...g, name } : g)) };
}

// 서버가 422 로 거절할 것을 보내기 전에 알린다 — 빈 묶음·묶음 이름·글자 수, 승인이면 연구 질문 2자 이상
export function outlineProblems(d: OutlineDraft, approve: boolean): string[] {
  const out: string[] = [];
  d.groups.forEach((g, i) => {
    const name = g.name.trim();
    if (!name) out.push(`${i + 1}번째 묶음의 이름을 적어 주세요`);
    else if (chars(name) > GROUP_LABEL_MAX) out.push(`${i + 1}번째 묶음 이름은 ${GROUP_LABEL_MAX}자까지입니다`);
    if (!g.papers.length) {
      out.push(`${name ? `「${name}」` : `${i + 1}번째`} 묶음이 비었습니다 — 논문을 하나 이상 옮겨 두세요`);
    }
  });
  const question = chars(d.question.trim());
  if (question > OUTLINE_QUESTION_MAX) out.push(`연구 질문은 ${OUTLINE_QUESTION_MAX}자까지입니다`);
  else if (approve && question < QUESTION_MIN) out.push("승인하려면 연구 질문을 고르거나 적어 주세요");
  if (chars(d.method.trim()) > OUTLINE_METHOD_MAX) out.push(`방법은 ${OUTLINE_METHOD_MAX}자까지입니다`);
  return out;
}

export function toOutlinePut(d: OutlineDraft, approve: boolean): OutlinePut {
  return {
    groups: d.groups.map((g) => ({ key: g.key, name: g.name.trim(), papers: [...g.papers] })),
    question: d.question.trim(),
    method: d.method.trim(),
    approve,
  };
}

// 목차 생성이 내용 검사를 넘지 못해 기본값(묶음 이름 = 개념 힌트, 질문 = 고른 주제의 질문 하나)으로 끝났는가.
// 검사를 넘은 목차는 연구 질문 후보가 둘 이상이다(services/research_work/outline 의 check)
export function isFallbackOutline(outline: Outline): boolean {
  return outline.questions.length < 2;
}
