// frontend/utils/summaryTidy.ts
// 논문 검색 AI 요약(pages/papers/index.vue)을 marked 로 그리기 전에 다듬는 순수 로직 — 모델 출력에 기대지 않고 화면에서 늘 같게 정리한다.
// 받은 글(aiText)과 검색 기록에는 원문 그대로 두고, 보이는 글만 다듬는다(복원한 기록도 같은 자리에서 그린다).
//
// ① 자료가 없다는 말만 하는 목록 항목 — '초록이 없'이 든 항목, '파악할 수 없'·'확인할 수 없'으로 문장을 맺는 항목(없다·없습니다·
//    없음·없어요 뒤에 인용 번호·마침표나 줄 끝)은 뺀다. 프롬프트가 쓰지 말라 해도(paper_search_summary.yaml '자료가 부족하다거나
//    확인할 수 없다는 문장은 쓰지 마세요') 나온다. 문장이 그 뒤로 이어지면 — '확인할 수 없었다'·'파악할 수 없던'·'확인할 수 없는 것으로
//    나타났다'·'확인할 수 없다는 한계가 있다'·'확인할 수 없음을 보고했다'·'확인할 수 없어 … 제언했다' — 논문이 밝힌 결과·한계를
//    옮긴 것이라 남긴다('시사점 및 한계' 섹션을 뺀 뒤로 한계 문장은 '연구 방법 및 근거'에 나온다). 판단이 서지 않으면 남긴다 —
//    자료 없음 문장 하나가 남는 것보다 연구 결과 하나가 사라지는 쪽이 더 나쁘다.
// ② 섹션(제목 줄 아래, 다음 제목 전까지)마다 목록 항목은 앞에서 SUMMARY_ITEMS_MAX 개까지만 — 프롬프트의 '2~4개'를 넘겨도 화면은 넘기지 않는다.
//    ①로 뺀 항목은 세지 않는다. ①로 항목이 모두 빠지고 다른 글도 없는 섹션은 제목까지 뺀다(빈 제목만 남지 않게).
//    제목은 프롬프트가 시킨 '## ' 말고도 굵은 글씨만 있는 줄('**핵심 요약**')과 setext 제목(글 줄 아래 '---'·'===')도 센다 —
//    제목을 못 알아보면 두 섹션이 한 섹션으로 세어져 둘째 섹션 항목이 상한에 걸려 소리 없이 잘린다.
//
// 항목 안의 글은 고치지 않고 줄 단위로만 빼므로 인용 번호 (1)·(1, 3)은 그대로다(SummaryText 의 linkCitations 가 그린 뒤 버튼으로 바꾼다).
// 항목 바로 아래 빈 줄 없이 온 들여 쓰지 않은 줄은, 항목 문장이 마침표로 끝났으면 새 문단으로 보고 항목에 딸리지 않는다 — 그 문단에
// 자료가 없다는 말이 있어도 출처가 붙은 앞 항목까지 함께 빠지지 않고, 넘친 항목 뒤에 붙은 맺음 문단도 남는다(목록 밖 문단은 건드리지 않는다).
// 스트리밍 중간 글에도 쓴다 — 글은 뒤로만 자라 이미 보인 앞 항목은 사라지지 않고, 다섯째 항목부터는 처음부터 보이지 않는다.
// 쓰는 중인 마지막 줄은 문장이 맺어질 때까지(마침표나 줄 끝) '…확인할 수 없다' 판단을 미루고('없다는 한계'가 될 수 있다), 줄이 끝나야
// 정해지는 제목 꼴(굵은 글씨·setext 밑줄)도 다 쓴 뒤에 알아본다. 마지막 섹션의 빈 제목은 스트리밍이 끝난 뒤에야 뺀다(다음 항목이
// 올 수 있다) — 보였다 사라졌다 다시 보이는 깜빡임을 막는다

/** 섹션마다 보일 목록 항목 수 — 프롬프트 '각 섹션은 2~4개 항목'의 위 끝 */
export const SUMMARY_ITEMS_MAX = 4;

export interface TidyOptions {
  /** 아직 받는 중인가 — 마지막 줄은 쓰는 중이고, 마지막 섹션은 닫히지 않았다 */
  streaming?: boolean;
}

// ATX 제목 줄 — '## 핵심 요약'. 쓰는 중인 '##' 도 제목으로 본다(뒤에 글이 붙어도 제목이라 판단이 바뀌지 않는다)
const HEADING = /^ {0,3}#{1,6}(?:[ \t]|$)/;
// 굵은 글씨만 있는 줄 — '**핵심 요약**'·'__연구 방법__'·'**핵심 요약:**'. 두 칸 이상 들여 쓴 줄은 앞 항목의 내용이다
const BOLD_HEADING = /^ ?(?:\*\*[^*\n]+\*\*|__[^_\n]+__)[ \t]*:?[ \t]*$/;
// setext 제목의 밑줄 — 글 줄 바로 아래의 '---'·'==='(사이에 칸이 없다. '- - -'는 가로줄)
const SETEXT_UNDERLINE = /^ {0,3}(?:=+|-+)[ \t]*$/;
// 맨 바깥 목록 항목의 머리 — '- '·'* '·'+ '·'1. '·'1) '. 두 칸 넘게 들여 쓴 항목은 앞 항목에 딸린 하위 목록으로 본다
const BULLET = /^ ?(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)/;
// 가로줄('- - -'·'***') — 목록 머리처럼 보여도 항목이 아니다
const THEMATIC_BREAK = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
// 들여 쓴 줄 — 앞 항목의 내용(이어 쓴 문단·하위 목록)
const INDENTED = /^(?: {2,}|\t)/;
// 문장이 맺어진 줄 끝 — 마침표류, 그 뒤에 인용 번호가 붙은 꼴('…했다. (1)')도
const SENTENCE_END = /[.!?。][ \t]*(?:\(\s*\d{1,3}(?:\s*[,，]\s*\d{1,3})*\s*\)[ \t]*)?$/;
// 자료가 없다는 말 — '초록이 없', 또는 '파악/확인할 수 없'이 문장을 맺는 꼴(없다·없습니다·없음·없어요 + 인용 번호 + 마침표류나 줄 끝).
// '없었다'·'없던'·'없는 것으로'·'없다는'·'없음을'·'없어 …'처럼 문장이 이어지면 걸리지 않는다. 쓰는 중인 줄의 끝은 아직 문장 끝이 아니라
// 걸리지 않는다(끝난 항목은 줄 끝 \n 을 붙여 본다)
const MISSING_INFO =
  /초록이\s*없|(?:파악|확인)\s*할\s*수\s*없(?:다|습니다|음|어요)[ \t]*(?:\(\s*\d{1,3}(?:\s*[,，]\s*\d{1,3})*\s*\)[ \t]*)?(?:[.!?。]|\n)/;

type Block =
  | { kind: "heading"; lines: string[] }
  | { kind: "item"; lines: string[] }
  | { kind: "other"; lines: string[] };

function toBlocks(lines: string[], streaming: boolean): Block[] {
  const blocks: Block[] = [];
  lines.forEach((line, i) => {
    const last = blocks[blocks.length - 1];
    // 받는 중인 마지막 줄은 쓰는 중 — 줄이 끝나야 정해지는 제목 꼴(굵은 글씨·setext 밑줄)은 다 쓴 뒤에 알아본다
    const done = !streaming || i < lines.length - 1;
    if (HEADING.test(line)) blocks.push({ kind: "heading", lines: [line] });
    else if (done && BOLD_HEADING.test(line)) blocks.push({ kind: "heading", lines: [line] });
    // setext — 바로 위 글 줄(항목에 딸린 줄이 아닌 문단 줄)과 밑줄이 한 제목이다
    else if (
      done &&
      SETEXT_UNDERLINE.test(line) &&
      last?.kind === "other" &&
      last.lines[0]!.trim() &&
      blocks[blocks.length - 2]?.kind !== "item"
    ) {
      blocks[blocks.length - 1] = { kind: "heading", lines: [...last.lines, line] };
    } else if (BULLET.test(line) && !THEMATIC_BREAK.test(line)) blocks.push({ kind: "item", lines: [line] });
    // 빈 줄이 아닌 다음 줄은 바로 앞 항목에 딸린다 — 들여 쓴 줄(이어 쓴 문단·하위 목록)이거나, 항목 문장이 아직 맺어지지 않아
    // 줄을 바꿔 이어 쓴 줄이면. 항목 문장이 마침표로 끝난 뒤 들여 쓰지 않고 온 줄은 새 문단이다. 빈 줄이 항목을 닫는다
    else if (line.trim() && last?.kind === "item" && (INDENTED.test(line) || !SENTENCE_END.test(last.lines.at(-1)!))) {
      last.lines.push(line);
    } else blocks.push({ kind: "other", lines: [line] });
  });
  return blocks;
}

/** 요약 글을 화면에 보일 꼴로 다듬는다 — 자료가 없다는 항목 빼기, 섹션마다 SUMMARY_ITEMS_MAX 항목까지. 줄바꿈은 \n 으로 맞춘다 */
export function tidySummary(text: string, opts: TidyOptions = {}): string {
  if (!text) return text;
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const streaming = !!opts.streaming;
  const blocks = toBlocks(lines, streaming);
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
      // 끝난 항목은 줄 끝(\n)을 붙여 본다 — '…확인할 수 없다' 가 줄 끝에 있으면 문장이 맺어진 것이다
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
