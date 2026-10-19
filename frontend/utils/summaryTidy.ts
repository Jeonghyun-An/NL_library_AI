// frontend/utils/summaryTidy.ts
// 논문 검색 AI 요약(pages/papers/index.vue)을 marked 로 그리기 전에 다듬는 순수 로직 — 모델 출력에 기대지 않고 화면에서 늘 같게 정리한다.
// 받은 글(aiText)과 검색 기록에는 원문 그대로 두고, 보이는 글만 다듬는다(복원한 기록도 같은 자리에서 그린다).
//
// ① 자료가 없다는 말만 하는 목록 항목 — '초록이 없'·'파악할 수 없'·'확인할 수 없'이 든 항목은 뺀다. 프롬프트가 쓰지 말라 해도
//    (paper_search_summary.yaml '자료가 부족하다거나 확인할 수 없다는 문장은 쓰지 마세요') 나온다. 다만 '확인할 수 없었다'·
//    '파악할 수 없던'처럼 뒤가 '었'·'던'이면 연구가 밝힌 결과(유의한 차이를 확인할 수 없었다)를 옮긴 것이라 남긴다.
// ② 섹션(제목 줄 아래, 다음 제목 전까지)마다 목록 항목은 앞에서 SUMMARY_ITEMS_MAX 개까지만 — 프롬프트의 '2~4개'를 넘겨도 화면은 넘기지 않는다.
//    ①로 뺀 항목은 세지 않는다. ①로 항목이 모두 빠지고 다른 글도 없는 섹션은 제목까지 뺀다(빈 제목만 남지 않게).
//
// 항목 안의 글은 고치지 않고 줄 단위로만 빼므로 인용 번호 (1)·(1, 3)은 그대로다(SummaryText 의 linkCitations 가 그린 뒤 버튼으로 바꾼다).
// 스트리밍 중간 글에도 쓴다 — 글은 뒤로만 자라 이미 보인 앞 항목은 사라지지 않고, 다섯째 항목부터는 처음부터 보이지 않는다.
// 쓰는 중인 마지막 줄은 '확인할 수 없' 바로 뒤 글자가 오기 전까지 판단을 미루고('없었다'가 될 수 있다), 마지막 섹션의 빈 제목은
// 스트리밍이 끝난 뒤에야 뺀다(다음 항목이 올 수 있다) — 보였다 사라졌다 다시 보이는 깜빡임을 막는다

/** 섹션마다 보일 목록 항목 수 — 프롬프트 '각 섹션은 2~4개 항목'의 위 끝 */
export const SUMMARY_ITEMS_MAX = 4;

export interface TidyOptions {
  /** 아직 받는 중인가 — 마지막 줄은 쓰는 중이고, 마지막 섹션은 닫히지 않았다 */
  streaming?: boolean;
}

// ATX 제목 줄 — '## 핵심 요약'. 쓰는 중인 '##' 도 제목으로 본다(뒤에 글이 붙어도 제목이라 판단이 바뀌지 않는다)
const HEADING = /^ {0,3}#{1,6}(?:[ \t]|$)/;
// 맨 바깥 목록 항목의 머리 — '- '·'* '·'+ '·'1. '·'1) '. 두 칸 넘게 들여 쓴 항목은 앞 항목에 딸린 하위 목록으로 본다
const BULLET = /^ ?(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)/;
// 가로줄('- - -'·'***') — 목록 머리처럼 보여도 항목이 아니다
const THEMATIC_BREAK = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
// 자료가 없다는 말. '파악/확인할 수 없' 은 바로 뒤 글자가 '었'·'던'이 아닐 때만 — 뒤 글자가 아직 없으면(쓰는 중인 줄의 끝) 걸리지 않는다
const MISSING_INFO = /초록이\s*없|(?:파악|확인)\s*할\s*수\s*없(?=[^었던])/;

type Block =
  | { kind: "heading"; lines: string[] }
  | { kind: "item"; lines: string[] }
  | { kind: "other"; lines: string[] };

function toBlocks(lines: string[]): Block[] {
  const blocks: Block[] = [];
  for (const line of lines) {
    const last = blocks[blocks.length - 1];
    if (HEADING.test(line)) blocks.push({ kind: "heading", lines: [line] });
    else if (BULLET.test(line) && !THEMATIC_BREAK.test(line)) blocks.push({ kind: "item", lines: [line] });
    // 빈 줄이 아닌 다음 줄(들여 쓴 줄·하위 목록·이어 쓴 줄)은 바로 앞 항목에 딸린다. 빈 줄이 항목을 닫는다
    else if (line.trim() && last?.kind === "item") last.lines.push(line);
    else blocks.push({ kind: "other", lines: [line] });
  }
  return blocks;
}

/** 요약 글을 화면에 보일 꼴로 다듬는다 — 자료가 없다는 항목 빼기, 섹션마다 SUMMARY_ITEMS_MAX 항목까지. 줄바꿈은 \n 으로 맞춘다 */
export function tidySummary(text: string, opts: TidyOptions = {}): string {
  if (!text) return text;
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const streaming = !!opts.streaming;
  const blocks = toBlocks(lines);
  const lastBlock = blocks[blocks.length - 1];

  // 섹션 = 제목 블록(첫 제목 앞 머리말은 제목 없음)과 그 아래 블록들
  const sections: { heading: Block | null; body: Block[] }[] = [{ heading: null, body: [] }];
  for (const block of blocks) {
    if (block.kind === "heading") sections.push({ heading: block, body: [] });
    else sections[sections.length - 1]!.body.push(block);
  }

  const out: string[] = [];
  sections.forEach((section, si) => {
    const kept: string[] = [];
    let items = 0;
    let dropped = 0;
    let otherText = false;
    for (const block of section.body) {
      if (block.kind !== "item") {
        if (block.lines.some((l) => l.trim())) otherText = true;
        kept.push(...block.lines);
        continue;
      }
      // 끝난 항목은 줄 끝(\n)을 붙여 본다 — '확인할 수 없' 이 줄 끝에 있어도 뒤 글자가 정해진 것이다
      const body = block.lines.join("\n") + (streaming && block === lastBlock ? "" : "\n");
      if (MISSING_INFO.test(body)) {
        dropped++;
        continue;
      }
      if (items >= SUMMARY_ITEMS_MAX) continue;
      items++;
      kept.push(...block.lines);
    }
    // 항목이 모두 빠지고 남은 글도 없는 섹션은 제목까지 뺀다 — 다음 제목이 왔거나 다 받은 뒤에만(닫힌 섹션)
    const closed = si < sections.length - 1 || !streaming;
    const emptied = dropped > 0 && items === 0 && !otherText;
    if (section.heading && !(emptied && closed)) out.push(...section.heading.lines);
    out.push(...kept);
  });
  // 남은 것이 빈 줄뿐이면 빈 글 — 화면이 빈 요약(또는 받는 중 안내)으로 그린다
  const tidy = out.join("\n");
  return tidy.trim() ? tidy : "";
}
