// frontend/utils/clipboard.ts
// 글 복사. 운영 게이트웨이는 http 라(infra/conf.d/default.conf — listen 80) localhost 가 아닌 주소로 접속하면 보안 컨텍스트가 아니어서
// navigator.clipboard 가 없다(있어도 권한 거부로 실패할 수 있다). 그때는 화면에 보이는 그 글을 선택해 execCommand('copy')(옛 방식 —
// 사용자가 누른 동작 안이면 http 에서도 된다)로 복사하고 원래 선택을 되살린다. 그것도 안 되면 글을 선택해 둔 채 false 를 돌려준다 —
// 화면은 '직접 복사해 주세요' 안내를 보인다(선택된 글은 사용자가 바로 복사할 수 있다)

/**
 * text 를 클립보드에 쓴다. Clipboard API 가 없거나 실패하면 source(화면의 그 글이 든 요소)를 선택해 옛 방식으로 복사한다.
 * 복사했으면 true. Clipboard API 가 없을 때는 기다림(await) 없이 바로 옛 방식으로 가 사용자 동작(클릭) 안에서 돈다
 */
export async function copyToClipboard(text: string, source: Element | null): Promise<boolean> {
  const clipboard = typeof navigator === "undefined" ? undefined : navigator.clipboard;
  if (clipboard && typeof clipboard.writeText === "function") {
    try {
      await clipboard.writeText(text);
      return true;
    } catch {
      /* 권한 거부·문서에 초점 없음 — 아래 옛 방식으로 */
    }
  }
  return copySelection(source);
}

/**
 * source 의 글을 선택하고 execCommand('copy') 로 복사한다. 복사했으면 사용자가 그 전에 잡아 둔 선택을 되살리고 true
 * (복사하려고 잠깐 바꾼 선택이 사용자의 선택을 지우지 않게 — 없었으면 선택 없음으로), 못 했으면 source 를 선택해 둔 채 false
 * (사용자가 그대로 Ctrl·⌘+C 로 복사할 수 있게). source 가 없거나 선택할 수 없는 환경이면 false
 */
export function copySelection(source: Element | null): boolean {
  if (!source || typeof window === "undefined" || typeof document === "undefined") return false;
  const selection = typeof window.getSelection === "function" ? window.getSelection() : null;
  if (!selection || typeof document.createRange !== "function") return false;
  const previous = savedRanges(selection);
  const range = document.createRange();
  range.selectNodeContents(source);
  selection.removeAllRanges();
  selection.addRange(range);
  let copied = false;
  try {
    copied = typeof document.execCommand === "function" && document.execCommand("copy");
  } catch {
    copied = false;
  }
  if (copied) {
    selection.removeAllRanges();
    for (const r of previous) selection.addRange(r);
  }
  return copied;
}

// 지금 선택의 범위들 — removeAllRanges 뒤에도 쓸 수 있게 복제해 둔다(Range 는 문서가 바뀌면 따라 움직이는 살아 있는 객체다)
function savedRanges(selection: Selection): Range[] {
  const count = typeof selection.rangeCount === "number" ? selection.rangeCount : 0;
  const ranges: Range[] = [];
  for (let i = 0; i < count; i++) ranges.push(selection.getRangeAt(i).cloneRange());
  return ranges;
}
