// frontend/utils/citations.ts
import type { EvidenceMeta, ReportChunk, ReportEvidence, ReportSection } from "../types/research";

export type CitationPart = { type: "text"; text: string } | { type: "cite"; eid: string };

// 서버(services/research/citations.bind_markers)가 인식한 표기를 전부 [E3] 한 모양으로
// 다시 써서 보낸다 — 화면은 이 표준형만 칩으로 바꾸고 나머지는 글자 그대로 둔다.
const MARKER = /\[(E\d+)\]/g;
const YEAR = /(19|20)\d{2}/;
const HANGUL_NAME = /^[가-힣\s]+$/;

export function splitCitations(text: string): CitationPart[] {
  const parts: CitationPart[] = [];
  let last = 0;
  for (const m of text.matchAll(MARKER)) {
    const at = m.index ?? 0;
    if (at > last) parts.push({ type: "text", text: text.slice(last, at) });
    parts.push({ type: "cite", eid: m[1] ?? "" });
    last = at + m[0].length;
  }
  if (last < text.length) parts.push({ type: "text", text: text.slice(last) });
  return parts;
}

export function pubYear(pubDate: string | null | undefined): string | null {
  const m = YEAR.exec(pubDate ?? "");
  return m ? m[0] : null;
}

export function splitAuthors(personal: string | null | undefined): string[] {
  const raw = (personal ?? "").trim();
  if (!raw) return [];
  const bySemicolon = raw.split(/[;|·]/).map((s) => s.trim()).filter(Boolean);
  if (bySemicolon.length > 1) return bySemicolon;
  const byComma = raw.split(",").map((s) => s.trim()).filter(Boolean);
  // "Smith, John" 처럼 성과 이름을 쉼표로 가른 한 사람은 쪼개지 않는다 — 조각마다
  // 한글이 있거나 띄어 쓴 이름일 때만 여러 저자로 본다
  const allNames = byComma.every((s) => /[가-힣]/.test(s) || /\s/.test(s));
  return byComma.length > 1 && allNames ? byComma : [raw];
}

export function firstAuthorSurname(personal: string | null | undefined): string | null {
  const first = splitAuthors(personal)[0]?.replace(/\s*외\s*\d*\s*인?\s*$/, "").trim();
  if (!first) return null;
  if (HANGUL_NAME.test(first)) return first.replace(/\s/g, "").slice(0, 1);
  if (first.includes(",")) return first.split(",")[0]?.trim() || first;
  const tokens = first.split(/\s+/);
  return tokens[tokens.length - 1] ?? first;
}

export function citeLabel(meta: EvidenceMeta | undefined, eid: string): string {
  const who = firstAuthorSurname(meta?.personal_author);
  const year = pubYear(meta?.pub_date);
  if (who && year) return `${who} ${year}`;
  return who ?? eid;
}

export interface VolIssue {
  vol: string | null;
  issue: string | null;
  // 권·호로 읽지 못한 꼴('특별호' 등)은 글 그대로 — 이때 vol·issue 는 null
  raw: string | null;
}

// 논문 권호(vol_issue) 읽기. 운영 값: 'V(N)'(권(호))·'-N'(권 없이 호만 — KCI 적재가 빈 권 자리를 비워 이은 꼴)·'V'(권만).
// 비었거나 기호뿐이면 null. 서버 paper_citation 과 같은 규칙이고, 결과 카드·상세의 'V권 N호'(resultCard.formatVolIssue)도 이것으로 읽는다
export function parseVolIssue(value: string | null | undefined): VolIssue | null {
  const raw = (value ?? "").trim();
  if (!raw || /^[-–—\s/.,]+$/.test(raw)) return null;
  const both = raw.match(/^(\d+)\s*\(\s*(\d+)\s*\)$/);
  if (both) return { vol: both[1]!, issue: both[2]!, raw: null };
  const issueOnly = raw.match(/^-\s*(\d+)$/);
  if (issueOnly) return { vol: null, issue: issueOnly[1]!, raw: null };
  const volOnly = raw.match(/^(\d+)$/);
  if (volOnly) return { vol: volOnly[1]!, issue: null, raw: null };
  return { vol: null, issue: null, raw };
}

// 참고문헌의 권호 — APA 꼴 '57(3)'·'(46)'(호만)·'57'(권만), 없으면 빈 글
export function referenceVolIssue(value: string | null | undefined): string {
  const v = parseVolIssue(value);
  if (!v) return "";
  if (v.raw !== null) return v.raw;
  return `${v.vol ?? ""}${v.issue ? `(${v.issue})` : ""}`;
}

// 참고문헌의 쪽 — 수록면(extent, KCI 적재 값 'S~E')을 'S–E'(같은 쪽이면 하나)로. 다른 꼴(단행본 형태사항 '352 p.' 등)은
// 쪽으로 읽지 않는다(빈 글)
export function referencePages(extent: string | null | undefined): string {
  const m = (extent ?? "").trim().match(/^(\d+)\s*(?:[~\-–—]\s*(\d+))?$/);
  if (!m) return "";
  const [, start, end] = m;
  return end && end !== start ? `${start}–${end}` : start!;
}

// 참고문헌의 학술지 자리 '학술지, 권(호), 쪽' — 있는 칸만 쉼표로 잇는다. 학술지가 없으면 권·호·쪽도 싣지 않는다(빈 글).
// 논문 상세 인용(app/services/search/paper_citation.py _journal_part)과 같은 글자다 — 두 쪽 테스트가
// tests/fixtures/citation_reference.json 을 함께 읽는다
export function journalText(meta: Pick<EvidenceMeta, "series_title" | "vol_issue" | "extent">): string {
  const journal = meta.series_title?.trim() ?? "";
  if (!journal) return "";
  return [journal, referenceVolIssue(meta.vol_issue), referencePages(meta.extent)].filter(Boolean).join(", ");
}

export function metaLine(meta: EvidenceMeta | undefined): string {
  if (!meta) return "";
  const journal = [meta.series_title?.trim(), referenceVolIssue(meta.vol_issue)].filter(Boolean).join(" ");
  const citations = meta.kci_citations != null ? `피인용 ${meta.kci_citations}` : "";
  return [meta.personal_author ?? "", journal, pubYear(meta.pub_date) ?? "", citations, meta.grade ?? ""]
    .map((s) => s.trim())
    .filter(Boolean)
    .join(" · ");
}

// 한 논문이 여러 절에 실리면 evidence.chunks 는 그 합집합이다 — 칩은 자기 절에서
// 매칭된 대목만 보여 줘야 절 내용과 맞는다. 매핑이 없으면(옛 보고서) 전부 보여 준다.
// 순서는 절 매핑(evidence_chunks)의 순서를 그대로 쓴다 — 서버가 그 하위질문의 점수 순으로
// 준다(citations.link_chunks). evidence.chunks 는 전역 최고점 순이라 그 순서로 고르면 이 절의
// 검색어로는 덜 맞은 대목이 먼저 나온다.
export function citeChunks(
  section: ReportSection | undefined,
  evidence: ReportEvidence | undefined,
  eid: string,
): ReportChunk[] {
  if (!evidence) return [];
  const ids = section?.evidence_chunks?.[eid];
  if (!ids || !ids.length) return evidence.chunks;
  const byId = new Map(evidence.chunks.map((c) => [c.chunk_id, c]));
  const picked = ids.map((id) => byId.get(id)).filter((c): c is ReportChunk => c !== undefined);
  return picked.length ? picked : evidence.chunks;
}

// 인용칩이 보던 대목을 첫 대목으로 돌릴지 견주는 열쇠. 초안에 절이 더해지거나 초안이 최종본으로 바뀌어 다시
// 그리면 citeChunks 가 같은 대목의 새 배열을 돌려주므로, 배열이 아니라 대목 id 로 견준다
export function chunkListKey(chunks: readonly ReportChunk[]): string {
  return chunks.map((c) => c.chunk_id).join("|");
}

// 저장된 쪽수는 0부터 센다(ingestion/extractor). 0 은 "첫 쪽"과 "쪽 정보 없음"
// (indexer 의 `or 0`)이 겹쳐 구분할 수 없으므로 쪽을 표시하지 않는다.
export function pageLabel(chunk: Pick<ReportChunk, "page_start" | "page_end">): string {
  if (!chunk.page_start || chunk.page_start <= 0) return "쪽 정보 없음";
  const start = chunk.page_start + 1;
  const end = chunk.page_end + 1;
  return end > start ? `p.${start}–${end}` : `p.${start}`;
}

export function pdfPage(chunk: Pick<ReportChunk, "page_start">): number | undefined {
  return chunk.page_start > 0 ? chunk.page_start + 1 : undefined;
}
