// frontend/utils/detailView.ts
// 상세 화면(논문·소장자료)이 보이는 글을 만드는 순수 함수 — 서지 표 행·저자 줄·관련 자료 카드 줄·AI 큐레이션 탭·검색바 이동.
// 키워드 칩 규칙(먼저 비지 않은 출처 하나, 최대 개수)은 결과 카드와 같은 utils/resultCard.ts 의 cardKeywords 를 그대로 쓴다
import { splitAuthors } from "~/utils/citations";
import { kdcChip } from "~/utils/kdc";
import { queryScorePct } from "~/utils/relevance";
import { formatPubLabel, formatVolIssue, normalizeName, type CardInfo, type ResultKind } from "~/utils/resultCard";

export interface DetailInfo extends CardInfo {
  title?: string | null;
  title_responsibility?: string | null;
  pub_place?: string | null;
  vol_issue?: string | null;
  extent?: string | null;
  wos_citations?: number | null;
  kdc?: string | null;
  ddc?: string | null;
  isbn?: string | null;
  uci?: string | null;
  language?: string | null;
}

export interface MetaPart {
  text: string;
  /** 이 조각 앞에 '›' 화살표를 둔다(발행처 › 분야 › 권호) */
  arrow?: boolean;
}

/** 서지 표 한 행 — 라벨 열 | 값 열. 값은 조각으로 나뉘어 화살표로 이어질 수 있다 */
export interface MetaRow {
  label: string;
  parts: MetaPart[];
}

function clean(v: string | null | undefined): string {
  return (v ?? "").trim();
}

function row(label: string, text: string): MetaRow[] {
  return text ? [{ label, parts: [{ text }] }] : [];
}

/**
 * 저자 줄. 개인 저자는 '김수영 | 조성배'·'A;B' 처럼 원본마다 다른 구분자를 쉼표로 맞춘다(보고서 참고문헌과 같은 splitAuthors).
 * 개인 저자가 없으면 기관 저자
 */
export function formatAuthors(personal: string | null | undefined, corporate?: string | null): string {
  const names = splitAuthors(personal);
  return names.length ? names.join(", ") : clean(corporate);
}

/** 저자 줄과 같은 이름(공백·괄호 차이 무시)이면 빈 문자열 — 기관 보고서는 저자·발행처가 같은 기관이라 같은 말이 두 번 나왔다 */
function unlessAuthor(name: string, author: string): string {
  const key = normalizeName(name);
  return key && key !== normalizeName(author) ? name : "";
}

/** 논문 발행처 — 논문 원본은 학회를 기관 저자(corporate_author)에 싣고 publisher 는 비어 있는 일이 많다 */
function paperPublisher(info: DetailInfo): string {
  return clean(info.publisher) || clean(info.corporate_author);
}

/**
 * 논문 머리의 서지 표.
 *  저자정보 · 저널정보(발행처 › 분야 › 권호) · 발행년도 · 수록면 · 인용수(KCI, WOS 가 있으면 함께) · 등재 정보(KCI 등재·후보 등 — 칩이 아니라 서지 글자)
 * 값이 없는 행은 뺀다
 */
export function paperMetaRows(info: DetailInfo | null | undefined): MetaRow[] {
  if (!info) return [];
  const author = formatAuthors(info.personal_author, info.corporate_author);
  const rows: MetaRow[] = [...row("저자정보", author)];

  const journal: MetaPart[] = [];
  const publisher = unlessAuthor(paperPublisher(info), author);
  if (publisher) journal.push({ text: publisher });
  const field = clean(info.series_title);
  if (field) journal.push({ text: field, arrow: journal.length > 0 });
  const volIssue = formatVolIssue(info.vol_issue);
  if (volIssue) journal.push({ text: volIssue, arrow: journal.length > 0 });
  if (journal.length) rows.push({ label: "저널정보", parts: journal });

  rows.push(...row("발행년도", formatPubLabel(info.pub_date, "paper") || clean(info.pub_date)));
  rows.push(...row("수록면", clean(info.extent)));

  const kci = info.kci_citations;
  const wos = info.wos_citations;
  if (typeof kci === "number" && Number.isFinite(kci)) {
    const withWos = typeof wos === "number" && Number.isFinite(wos) && wos > 0;
    rows.push(...row("인용수", withWos ? `KCI ${kci} · WOS ${wos}` : String(kci)));
  }
  rows.push(...row("등재 정보", clean(info.grade)));
  return rows;
}

/** 분류 값 — KDC 이름을 찾으면 '재정 (KDC 329)', 못 찾으면 번호만 'KDC 329'. 값이 없으면 빈 문자열 */
export function kdcLabel(kdc: string | null | undefined): string {
  const raw = clean(kdc);
  if (!raw) return "";
  const chip = kdcChip(raw);
  return chip ? `${chip.name} (KDC ${raw})` : `KDC ${raw}`;
}

/**
 * 소장자료 머리의 서지 표 — 저자정보 · 발행처 · 발행년도 · 분류. 저자와 같은 기관인 발행처는 뺀다.
 * 나머지 서지(형태·총서·표준번호…)는 bookDetailRows 가 '상세 서지 정보'로 따로 낸다
 */
export function bookMetaRows(info: DetailInfo | null | undefined): MetaRow[] {
  if (!info) return [];
  const author = formatAuthors(info.personal_author, info.corporate_author);
  return [
    ...row("저자정보", author),
    ...row("발행처", unlessAuthor(clean(info.publisher), author)),
    ...row("발행년도", formatPubLabel(info.pub_date, "book") || clean(info.pub_date)),
    ...row("분류", kdcLabel(info.kdc)),
  ];
}

/** 소장자료 '상세 서지 정보' — 예전 상세 정보 표의 행들. 값이 없는 행은 '-' 대신 뺀다 */
export function bookDetailRows(info: DetailInfo | null | undefined): MetaRow[] {
  if (!info) return [];
  const publication = [info.pub_place, info.publisher, info.pub_date].map(clean).filter(Boolean).join(", ");
  const classes = [info.kdc, info.ddc].map(clean).filter(Boolean).join(" → ");
  return [
    ...row("표제/저자사항", clean(info.title_responsibility) || clean(info.title)),
    ...row("발행사항", publication),
    ...row("형태사항", clean(info.extent)),
    ...row("총서사항", clean(info.series_title)),
    ...row("표준번호", clean(info.isbn) || clean(info.uci)),
    ...row("분류기호", classes),
    ...row("주제명", clean(info.subject) || clean(info.keyword)),
    ...row("언어", clean(info.language)),
  ];
}

/** 관련 자료 카드의 서지 줄 — '2004년 9월 · 한국인지과학회'. 저자와 같은 기관은 뺀다 */
export function relatedMetaLine(info: DetailInfo | null | undefined, kind: ResultKind): string {
  if (!info) return "";
  const author = formatAuthors(info.personal_author, info.corporate_author);
  const publisher = kind === "paper" ? paperPublisher(info) : clean(info.publisher);
  return [formatPubLabel(info.pub_date, kind), unlessAuthor(publisher, author)].filter(Boolean).join(" · ");
}

/** 상세 주소의 점수(?score=·title_score=·content_score=) → 0~1 원래 값. 없거나 숫자가 아니면 null — 관련도 알약(RelevanceBadge)에 넘긴다 */
export function queryScore(value: unknown): number | null {
  if (queryScorePct(value) === null) return null;
  const raw = Array.isArray(value) ? value[0] : value;
  return Number(raw);
}

/** 관련 논문의 점수는 절대값이 아주 작아(0.03 안팎) 목록 안 1위를 100% 로 둔 비율로 보인다 */
export function relativeScore(score: number | null | undefined, all: readonly (number | null | undefined)[]): number {
  const max = Math.max(...all.map((s) => (typeof s === "number" && Number.isFinite(s) ? s : 0)), 1e-9);
  return typeof score === "number" && Number.isFinite(score) ? score / max : 0;
}

export interface CurationTab {
  key: string;
  label: string;
  /** 보일 글이 있거나(또는 받는 중이라 곧 생긴다) — false 면 탭을 뺀다 */
  available: boolean;
}

/** 글이 없는 탭은 뺀다 */
export function visibleTabs<T extends CurationTab>(tabs: readonly T[]): T[] {
  return tabs.filter((t) => t.available);
}

/** 고른 탭이 빠졌으면 첫 탭으로. 탭이 하나도 없으면 null */
export function activeTabKey(current: string | null, tabs: readonly Pick<CurationTab, "key">[]): string | null {
  if (current && tabs.some((t) => t.key === current)) return current;
  return tabs[0]?.key ?? null;
}

/** AI 글 탭(논문 상세 AI 요약·소장자료 상세 추천 이유)을 둘지 — 아직 정하지 않았거나(곧 채워진다) 받는 중이거나, 받은 글이나
 *  실패 안내가 있으면 둔다. 받는 중을 따로 보는 까닭: [다시 시도]는 실패로 done 이 된 뒤 글·안내를 비우고 다시 받는다 — 보지
 *  않으면 첫 글자가 올 때까지 탭이 빠져 첫 탭(초록·줄거리)으로 넘어가고, 누른 버튼도 사라진다 */
export function aiTabAvailable(s: { loading: boolean; done: boolean; text: string; error: string }): boolean {
  return s.loading || !s.done || !!s.text || !!s.error;
}

/** [다시 시도]처럼 누르면 DOM 에서 빠지는 버튼의 초점을 그 버튼이 든 탭 본문(Tabs.vue 의 tabpanel, tabindex=0)으로 옮긴다 —
 *  그대로 두면 초점이 body 로 떨어져 키보드·화면낭독기 사용자가 자리를 잃는다. 탭 본문 밖이면 아무것도 하지 않는다 */
export function focusOwningPanel(target: EventTarget | null): void {
  const el = target as { closest?: (selector: string) => { focus?: () => void } | null } | null;
  el?.closest?.('[role="tabpanel"]')?.focus?.();
}

/** 탭 목록에서 방향키로 옮겨 갈 자리 — 좌우는 끝에서 반대쪽으로 돌고, Home·End 는 처음·끝. 그 밖의 키는 null */
export function tabKeyTarget(key: string, index: number, count: number): number | null {
  if (count <= 0) return null;
  switch (key) {
    case "ArrowRight":
      return (index + 1) % count;
    case "ArrowLeft":
      return (index - 1 + count) % count;
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return null;
  }
}

/** 상세 주소에 DeepRead 를 열어 둔 채 들어가는 표시(?chat=1)를 붙인다 */
export function withChat(url: string): string {
  const [path, hash] = url.split("#", 2) as [string, string | undefined];
  const joined = `${path}${path.includes("?") ? "&" : "?"}chat=1`;
  return hash === undefined ? joined : `${joined}#${hash}`;
}

/**
 * 상세 위 검색바에서 보낼 곳. 빈 글이면 null.
 * 들어온 검색과 같은 검색어면 그 결과 화면으로 돌아간다(same.to — 기록을 다시 쓰지 않고 복원) — 다르면 새 검색이다.
 * 논문은 /papers, 소장자료는 / 가 ?q= 로 검색한다
 */
export function detailSearchUrl(
  kind: ResultKind,
  input: string,
  same: { q: string; to: string } | null = null,
): string | null {
  const q = input.trim();
  if (!q) return null;
  if (same && same.q.trim() === q) return same.to;
  return `${kind === "paper" ? "/papers" : "/"}?${new URLSearchParams({ q })}`;
}
