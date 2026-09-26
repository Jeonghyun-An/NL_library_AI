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

export function metaLine(meta: EvidenceMeta | undefined): string {
  if (!meta) return "";
  const journal = [meta.series_title, meta.vol_issue].filter((s) => s && s.trim()).join(" ");
  const citations = meta.kci_citations != null ? `피인용 ${meta.kci_citations}` : "";
  return [meta.personal_author ?? "", journal, pubYear(meta.pub_date) ?? "", citations, meta.grade ?? ""]
    .map((s) => s.trim())
    .filter(Boolean)
    .join(" · ");
}

// 한 논문이 여러 절에 실리면 evidence.chunks 는 그 합집합이다 — 칩은 자기 절에서
// 매칭된 대목만 보여 줘야 절 내용과 맞는다. 매핑이 없으면(옛 보고서) 전부 보여 준다.
export function citeChunks(
  section: ReportSection | undefined,
  evidence: ReportEvidence | undefined,
  eid: string,
): ReportChunk[] {
  if (!evidence) return [];
  const ids = section?.evidence_chunks?.[eid];
  if (!ids || !ids.length) return evidence.chunks;
  const wanted = new Set(ids);
  const picked = evidence.chunks.filter((c) => wanted.has(c.chunk_id));
  return picked.length ? picked : evidence.chunks;
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
