// frontend/utils/evidenceLedger.ts
// 근거 장부(spec §3·§4 S2) — 탐색 중 채택 논문이 쌓이고 자기점검이 뺀 논문이 '뺌' 더미로 내려가는 딥리서치 화면의
// 시각화. 채택·뺌의 재료는 06a 가 받아 둔 회차 기록(SubqView.rounds[].adoptedPapers·excludedPapers)뿐이다 — 점검 이벤트와
// 진행 저장본이 같은 모양으로 채우므로 라이브로 본 장부와 다시 연 화면의 장부가 같다.
// 후보 이벤트(candidates)로 리듀서가 세운 '검토 중'(SubqView.reviewing)을 세 번째 묶음으로 둔다. 저장되지 않는 화면 상태라
// 재접속·끝난 잡에는 없다
import type { RoundView, SubqView } from "~/types/research";

export interface LedgerPaper {
  cntsId: string;
  title: string | null;
  personalAuthor: string | null;
  pubDate: string | null;
  // 이 논문을 채택한(뺀) 하위질문 번호(0부터, 오름차순)
  subqIdx: number[];
  // 채택: 처음 채택된 회차 · 뺌: 처음 뺀 회차 · 검토 중: 후보가 온 회차(모르면 0)
  round: number;
  // 그 하위질문의 마지막 점검 회차에서 새로 들어왔다(채택은 그 회차의 새 채택, 뺌은 그 회차에 뺌)
  isNew: boolean;
}

export interface Ledger {
  adopted: LedgerPaper[];
  dropped: LedgerPaper[];
  // 자기점검을 기다리는 후보 — 판정이 오면 채택·뺌으로 옮긴다
  reviewing: LedgerPaper[];
}

interface Bib {
  title: string | null;
  personalAuthor: string | null;
  pubDate: string | null;
}

// 회차 끝 채택 목록을 기록하기 전 잡(06a 전)은 어느 회차에도 목록이 없다 — 장부를 그리지 않는다. 첫 회차의 후보가
// 점검 전에 왔으면(검토 중) 채택 목록이 없어도 그린다
export function hasLedger(subqs: SubqView[]): boolean {
  return subqs.some((sq) => !!sq.reviewing?.papers.length || sq.rounds.some((r) => r.adoptedPapers.length > 0));
}

// 하위질문의 '마지막 회차' = 점검이 끝난(verdict 가 있는) 마지막 회차다. 검색만 끝나고 점검을 기다리는 회차는
// 채택 목록이 아직 비어 있다 — 그 회차를 보면 다음 점검이 올 때까지 장부가 비었다 다시 차오른다
function lastChecked(sq: SubqView): RoundView | null {
  for (let i = sq.rounds.length - 1; i >= 0; i -= 1) {
    const r = sq.rounds[i]!;
    if (r.verdict !== null) return r;
  }
  return null;
}

function addSubq(p: LedgerPaper, idx: number): void {
  if (!p.subqIdx.includes(idx)) p.subqIdx = [...p.subqIdx, idx].sort((a, b) => a - b);
}

export function ledgerFrom(subqs: SubqView[]): Ledger {
  // 서지는 그 논문이 새로 채택된 회차(isNew)에만 실린다 — 앞 회차에서 찾고, 없으면 뺀 논문 목록의 서지를 쓴다
  const bib = new Map<string, Bib>();
  const firstAdopted = new Map<string, number>();
  for (const sq of subqs) {
    for (const r of sq.rounds) {
      for (const p of r.adoptedPapers) {
        firstAdopted.set(p.cntsId, Math.min(firstAdopted.get(p.cntsId) ?? r.round, r.round));
        if (p.isNew && !bib.has(p.cntsId)) {
          bib.set(p.cntsId, { title: p.title, personalAuthor: p.personalAuthor, pubDate: p.pubDate });
        }
      }
    }
  }
  for (const sq of subqs) {
    for (const r of sq.rounds) {
      for (const p of r.excludedPapers) {
        if (!bib.has(p.cntsId)) bib.set(p.cntsId, { title: p.title || null, personalAuthor: p.personalAuthor, pubDate: p.pubDate });
      }
    }
  }

  // 채택: 하위질문마다 마지막 점검 회차의 채택을 하위질문 순 → 순위 순으로 합친다(한 논문은 한 줄)
  const adopted = new Map<string, LedgerPaper>();
  for (const sq of subqs) {
    const last = lastChecked(sq);
    if (!last) continue;
    for (const p of last.adoptedPapers) {
      const known = adopted.get(p.cntsId);
      if (known) {
        addSubq(known, sq.idx);
        known.isNew = known.isNew || p.isNew;
        continue;
      }
      const b: Bib = p.isNew ? p : (bib.get(p.cntsId) ?? p);
      adopted.set(p.cntsId, {
        cntsId: p.cntsId,
        title: b.title,
        personalAuthor: b.personalAuthor,
        pubDate: b.pubDate,
        subqIdx: [sq.idx],
        round: firstAdopted.get(p.cntsId) ?? last.round,
        isNew: p.isNew,
      });
    }
  }

  // 검토 중: 하위질문 순 → 후보 순으로 채택 더미에 없는 후보를 중복 없이. 서지는 후보가 실은 것을 먼저, 없으면 앞에서
  // 모은 서지를 쓴다. 판정 전이라 모두 새로 든 것이다
  const reviewing = new Map<string, LedgerPaper>();
  for (const sq of subqs) {
    if (!sq.reviewing) continue;
    for (const p of sq.reviewing.papers) {
      if (adopted.has(p.cntsId)) continue;
      const known = reviewing.get(p.cntsId);
      if (known) {
        addSubq(known, sq.idx);
        continue;
      }
      const b = bib.get(p.cntsId);
      reviewing.set(p.cntsId, {
        cntsId: p.cntsId,
        title: p.title || b?.title || null,
        personalAuthor: p.personalAuthor ?? b?.personalAuthor ?? null,
        pubDate: p.pubDate ?? b?.pubDate ?? null,
        subqIdx: [sq.idx],
        round: sq.reviewing.round ?? 0,
        isNew: true,
      });
    }
  }

  // 뺌: 탐색이 지나간 순서(하위질문 순 → 회차 순)로 중복 없이. 다른 하위질문이나 뒤 회차에 다시 채택된 논문, 다른 하위질문이
  // 다시 후보로 이어 검토 중인 논문은 두지 않는다 — 장부의 더미 셋에 같은 논문이 함께 있지 않다
  const dropped = new Map<string, LedgerPaper>();
  for (const sq of subqs) {
    const last = lastChecked(sq);
    for (const r of sq.rounds) {
      for (const p of r.excludedPapers) {
        if (adopted.has(p.cntsId) || reviewing.has(p.cntsId)) continue;
        const isNew = last?.round === r.round;
        const known = dropped.get(p.cntsId);
        if (known) {
          addSubq(known, sq.idx);
          known.isNew = known.isNew || isNew;
          continue;
        }
        const b = bib.get(p.cntsId);
        dropped.set(p.cntsId, {
          cntsId: p.cntsId,
          title: b?.title ?? null,
          personalAuthor: b?.personalAuthor ?? null,
          pubDate: b?.pubDate ?? null,
          subqIdx: [sq.idx],
          round: r.round,
          isNew,
        });
      }
    }
  }

  return { adopted: [...adopted.values()], dropped: [...dropped.values()], reviewing: [...reviewing.values()] };
}

export function ledgerLine(l: Ledger): string {
  // '뺌' 대신 '제외'(사용자 2026-10-26) — 같은 화면 카운터의 '제외한 논문'과 말을 맞춘다
  const head = `채택 ${l.adopted.length} · 제외 ${l.dropped.length}`;
  return l.reviewing.length ? `${head} · 검토 중 ${l.reviewing.length}` : head;
}

// 직전 장부와 비교해 이번에 들어온 논문. 처음 그릴 때(prev 가 null)는 없다 — 다시 연 화면에서 장부 전체가 한꺼번에
// 떨어지지 않게(움직임은 실제 이벤트가 도착할 때만 — spec §4 시연 정직성)
export function newlyAdded(prev: ReadonlySet<string> | null, papers: readonly LedgerPaper[]): string[] {
  if (!prev) return [];
  return papers.filter((p) => !prev.has(p.cntsId)).map((p) => p.cntsId);
}

// 장부 목록(높이 14rem 안에서 굴린다)의 스크롤 상태. 새 채택은 지금 도는 하위질문 묶음, 곧 목록 끝에 들고 뺌도 끝에
// 붙어서 목록을 그대로 두면 떨어지는 효과가 화면 밖에서 일어난다 — 목록만 새 줄 쪽으로 옮긴다(페이지는 굴리지 않는다)
export interface LedgerScroll {
  scrollTop: number;
  clientHeight: number;
  scrollHeight: number;
}

// 목록 안의 한 줄 자리(목록 내용 맨 위에서 잰 위·아래 끝, 스크롤과 무관)
export interface LedgerRowSpan {
  top: number;
  bottom: number;
}

const FOLLOW_SLACK_PX = 8;

// 이 목록을 따라가도 되는가 — 마지막으로 둔 자리 그대로이거나 바닥 근처일 때만이다. 사용자가 목록을 굴려 위쪽을 읽고
// 있으면 끌고 가지 않는다(다시 바닥까지 내리면 다시 따라간다)
export function ledgerFollowing(s: LedgerScroll, placedTop: number): boolean {
  return (
    Math.abs(s.scrollTop - placedTop) <= FOLLOW_SLACK_PX ||
    s.scrollTop + s.clientHeight >= s.scrollHeight - FOLLOW_SLACK_PX
  );
}

// 새로 든 줄(목록 순서)이 보이게 옮길 scrollTop — 첫 새 줄을 위 끝에 두되 목록 끝을 넘지 않는다. 새 줄이 모두
// 보이거나 옮길 자리가 지금 자리와 같으면 null(옮기지 않는다)
export function ledgerRevealTop(s: LedgerScroll, rows: readonly LedgerRowSpan[]): number | null {
  if (!rows.length) return null;
  const first = rows[0]!.top;
  const last = rows[rows.length - 1]!.bottom;
  if (first >= s.scrollTop - 1 && last <= s.scrollTop + s.clientHeight + 1) return null;
  const top = Math.max(0, Math.min(first, s.scrollHeight - s.clientHeight));
  return Math.abs(top - s.scrollTop) < 1 ? null : top;
}
