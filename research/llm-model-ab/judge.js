export const meta = {
  name: 'llm-model-ab-judge',
  description: 'Blind-judge model-comparison outputs: deep-research synthesis reports and research-gap sections — sentence audit, adversarial verify, pairwise ranking',
  phases: [
    { title: 'Audit', detail: 'synthesis: one agent per report output; gap: one agent per work (all outputs)' },
    { title: 'Verify', detail: 'one agent per audit: try to refute every flagged sentence' },
    { title: 'Rank', detail: 'pairwise: same-run outputs of the two arms' },
  ],
}

// args: { dir, synth: {tag: [labels]}, gap: {job: [labels]}, key: {synth: {tag: {label: {arm, run}}}, gap: {...}} }
// 판정자는 dir 아래 묶음 파일 하나만 읽는다. key 는 마지막 집계에만 쓴다(프롬프트에 넣지 않는다).
const DIR = args.dir
const KEY = args.key

const V = ['S', 'W', 'M', 'U_ok', 'U_claim', 'F']
const AUDIT = {
  type: 'object',
  properties: {
    outputs: { type: 'array', items: { type: 'object', properties: {
      label: { type: 'string' },
      sentences: { type: 'array', items: { type: 'object', properties: {
        n: { type: 'integer' }, verdict: { type: 'string', enum: V }, reason: { type: 'string' },
      }, required: ['n', 'verdict'] } },
      presentation_issues: { type: 'array', items: { type: 'object', properties: {
        n: { type: 'integer' }, severity: { type: 'string', enum: ['high', 'medium', 'low'] }, issue: { type: 'string' },
      }, required: ['n', 'severity', 'issue'] } },
    }, required: ['label', 'sentences', 'presentation_issues'] } },
  },
  required: ['outputs'],
}
const VERIFY = {
  type: 'object',
  properties: { checks: { type: 'array', items: { type: 'object', properties: {
    label: { type: 'string' }, n: { type: 'integer' }, confirmed: { type: 'boolean' },
    final_verdict: { type: 'string', enum: V }, reason: { type: 'string' },
  }, required: ['label', 'n', 'confirmed', 'final_verdict'] } } },
  required: ['checks'],
}
const RANK = {
  type: 'object',
  properties: { pairs: { type: 'array', items: { type: 'object', properties: {
    winner: { type: 'string', description: 'label of the better output, or "tie"' }, reason: { type: 'string' },
  }, required: ['winner', 'reason'] } } },
  required: ['pairs'],
}

const VERDICTS = `Sentence verdicts:
- S: the cited paper's evidence supports what the sentence says (faithful paraphrase and modest summarizing are fine).
- W: the content comes from a DIFFERENT paper in this file than the one cited (wrong paper).
- M: cites a paper but states something that paper's evidence does not say — an added finding, population, setting or cause, a reversed or distorted finding, or an interpretation/recommendation beyond what the paper says.
- U_ok: no citation; restates the question/heading/seed or is a pure transition.
- U_claim: no citation (and not a summary sentence); makes a substantive claim, interpretation or recommendation.
- F: a fact or number found in none of the evidence.`

const SYNTH_INTRO = (tag) => `You are checking machine-written Korean text from a library research assistant. Read ONLY the UTF-8 JSON file ${DIR}/synth/${tag}.json with the Read tool. Open no other file, run no commands, edit nothing.

The file holds one deep-research question, several candidate reports (outputs R1, R2, … — produced by different systems; which is which is hidden) and the evidence papers (eid, title, year, chunks = all source passages available for that paper). Each output lists 'headings' (sections = sub-questions) and numbered 'sentences' with section index and part: intro (the section's answer paragraph; [E#] marks cite evidence), summary (a one-paper summary — it is about the paper in 'paper' and counts as citing it even without a mark), future (a future-research line).`

const GAP_INTRO = (job) => `You are checking machine-written Korean text from a library research assistant. Read ONLY the UTF-8 JSON file ${DIR}/gap/${job}.json with the Read tool. Open no other file, run no commands, edit nothing.

The file holds one '연구 공백' (research gap) section input — original_question, topic_title, research_question, gap_seeds (gap candidates; a seed may carry [E#] marks), evidence (eid, title, year, abstract, excerpt — all the writer saw of each paper) — and several candidate outputs (L1, L2, …; which system wrote which is hidden), each a list of numbered sentences. The writer's rules: use only the evidence and seeds; every sentence carries the [E#] that supports it; no paper titles/authors/years in the text; no specific result numbers; never claim a topic is unstudied.`

function flagsOf(audit) {
  const out = []
  for (const o of (audit?.outputs || [])) for (const s of (o.sentences || []))
    if (['W', 'M', 'U_claim', 'F'].includes(s.verdict)) out.push({ label: o.label, n: s.n, verdict: s.verdict, reason: s.reason || '' })
  return out
}

async function auditVerify(intro, labels, what, label) {
  const a = await agent(`${intro}

Task: audit EVERY sentence of ${labels.length === 1 ? `output ${labels[0]} only` : `every output (${labels.join(', ')})`}.

${VERDICTS}

Also list presentation_issues per output: repeated content, summaries that only restate a title, off-topic papers, sentences that answer a different question than their heading, broken Korean, leftover markup or internal wording. Use severity high only for things that would embarrass a demo. Give a short reason for every verdict other than S and U_ok.`,
    { label: `audit:${label}`, phase: 'Audit', schema: AUDIT })
  const flagged = flagsOf(a)
  if (!a || !flagged.length) return { audit: a, verify: { checks: [] } }
  const v = await agent(`${intro}

Another reviewer flagged the sentences below. Re-check each independently against the evidence and try to REFUTE the flag — look hard for support in the cited paper's evidence (and the seeds, if any) before agreeing. Set confirmed=false when the flag is wrong; give the correct final_verdict either way.

${VERDICTS}

Flagged (label, sentence number, original verdict, reason):
${flagged.map(f => `- ${f.label} #${f.n} ${f.verdict}: ${f.reason}`).join('\n')}`,
    { label: `verify:${label}`, phase: 'Verify', schema: VERIFY })
  return { audit: a, verify: v }
}

// 짝 순위 — 판정자 셋(관점 셋, 하나는 짝의 순서를 뒤집어 본다). A/A(같은 모델끼리, 2026-10-19)에서 판정자 하나가
// '거의 같다'고 쓰고도 승자를 골라 종합 6쌍이 6:0 으로 쏠렸다 — 차이가 작으면 무승부를 고르게 하고, 셋 중 둘 이상이
// 같은 출력을 고를 때만 이긴 것으로 센다
const LENSES = [
  { name: 'faithful', order: 'given', text: 'Weigh faithfulness to the evidence most.' },
  { name: 'reader', order: 'reversed', text: 'Read as a researcher who must rely on this text: which would you rather cite from?' },
  { name: 'demo', order: 'given', text: 'Read as a competition judge watching a demo: which looks more correct and specific?' },
]

async function rank(intro, label, what) {
  const votes = await parallel(LENSES.map(lens => () => agent(`${intro}

Task: the file's 'pairs' lists pairs of outputs. For each pair (in the file's pair order), ${lens.order === 'reversed' ? 'read the SECOND output of the pair first, then the first one, and' : ''} pick the better ${what}, or "tie". ${lens.text} Criteria, in order: (1) faithfulness — nothing beyond the evidence, citations point at the paper that actually says it; (2) actually answers its heading / states gaps tied to the research question, specific rather than generic; (3) no repetition or filler, no leftover markup; (4) natural academic Korean.
If the two outputs are of essentially equal quality — the same structure and the same kinds and number of errors — answer "tie". Do not pick a winner on one minor difference. Return one entry per pair, in the file's pair order, with a one- or two-sentence reason.`,
    { label: `rank:${lens.name}:${label}`, phase: 'Rank', schema: RANK })))
  const n = Math.max(0, ...votes.filter(Boolean).map(v => (v.pairs || []).length))
  const pairs = []
  for (let i = 0; i < n; i++) {
    const picks = votes.filter(Boolean).map(v => (v.pairs || [])[i]?.winner).filter(Boolean)
    const count = {}
    for (const w of picks) count[w] = (count[w] || 0) + 1
    const top = Object.entries(count).sort((a, b) => b[1] - a[1])[0]
    pairs.push({ winner: top && top[0] !== 'tie' && top[1] >= 2 ? top[0] : 'tie', votes: picks })
  }
  return { pairs, votes }
}

const synthItems = Object.entries(args.synth || {}).flatMap(([tag, labels]) => labels.map(l => ({ tag, labels: [l] })))
const gapItems = Object.entries(args.gap || {}).map(([job, labels]) => ({ job, labels }))

// args.only — 'rank' 이면 순위만, 'audit' 이면 감사·검증만(이미 받은 결과와 밖에서 합친다). 없으면 둘 다
const ONLY = args.only || 'all'
const doAudit = ONLY !== 'rank'
const doRank = ONLY !== 'audit'
const [synthAudits, gapAudits, synthRanks, gapRanks] = await Promise.all([
  !doAudit ? [] : pipeline(synthItems, it => auditVerify(SYNTH_INTRO(it.tag), it.labels, 'report', `synth:${it.tag}:${it.labels[0]}`)
    .then(r => ({ kind: 'synth', id: it.tag, ...r }))),
  !doAudit ? [] : pipeline(gapItems, it => auditVerify(GAP_INTRO(it.job), it.labels, 'section', `gap:${it.job}`)
    .then(r => ({ kind: 'gap', id: it.job, ...r }))),
  !doRank ? [] : pipeline(Object.keys(args.synth || {}), tag => rank(SYNTH_INTRO(tag), `synth:${tag}`, 'report').then(r => ({ kind: 'synth', id: tag, rank: r }))),
  !doRank ? [] : pipeline(Object.keys(args.gap || {}), job => rank(GAP_INTRO(job), `gap:${job}`, 'research-gap section').then(r => ({ kind: 'gap', id: job, rank: r }))),
])

// ---- 집계(열쇠로 팔을 푼다) ----
const tally = {}
function bucket(kind, arm) {
  const k = `${kind}:${arm}`
  return (tally[k] ??= { sentences: 0, S: 0, W: 0, M: 0, U_ok: 0, U_claim: 0, F: 0, refuted: 0, high: 0, medium: 0, low: 0, wins: 0, losses: 0, ties: 0 })
}
for (const r of [...synthAudits, ...gapAudits].filter(Boolean)) {
  const key = KEY[r.kind][r.id]
  const fix = {}
  for (const c of (r.verify?.checks || [])) fix[`${c.label}#${c.n}`] = c
  for (const o of (r.audit?.outputs || [])) {
    const arm = key[o.label]?.arm
    if (!arm) continue
    const t = bucket(r.kind, arm)
    for (const s of (o.sentences || [])) {
      let v = s.verdict
      const f = fix[`${o.label}#${s.n}`]
      if (f && ['W', 'M', 'U_claim', 'F'].includes(v)) { if (!f.confirmed) t.refuted++; v = f.final_verdict }
      t.sentences++; t[v] = (t[v] || 0) + 1
    }
    for (const i of (o.presentation_issues || [])) t[i.severity] = (t[i.severity] || 0) + 1
  }
}
for (const r of [...synthRanks, ...gapRanks].filter(Boolean)) {
  const key = KEY[r.kind][r.id]
  for (const p of (r.rank?.pairs || [])) {
    if (p.winner === 'tie') { for (const a of new Set(Object.values(key).map(x => x.arm))) bucket(r.kind, a).ties++; continue }
    const arm = key[p.winner]?.arm
    if (!arm) continue
    bucket(r.kind, arm).wins++
    for (const a of new Set(Object.values(key).map(x => x.arm))) if (a !== arm) bucket(r.kind, a).losses++
  }
}
return { tally, synthAudits, gapAudits, synthRanks, gapRanks }
