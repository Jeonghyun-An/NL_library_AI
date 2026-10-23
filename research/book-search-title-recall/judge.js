export const meta = {
  name: 'book-search-judge',
  description: 'Blind-judge relevance of book search results (union of current vs proposed variants) for thematic queries',
  phases: [{ title: 'Judge', detail: '5 batches of 4 queries x 3 lenses' }],
}

const DIR = args.dir
const QIDS = args.qids
const SCHEMA = {
  type: 'object',
  properties: { queries: { type: 'array', items: { type: 'object', properties: {
    qid: { type: 'string' },
    scores: { type: 'array', items: { type: 'object', properties: {
      label: { type: 'string' }, score: { type: 'integer', enum: [0, 1, 2] }, reason: { type: 'string' },
    }, required: ['label', 'score'] } },
  }, required: ['qid', 'scores'] } } },
  required: ['queries'],
}
const LENSES = [
  { name: 'librarian', text: 'Judge as a reference librarian: does the item satisfy what the request literally asks for (topic, genre, and the kind of material — e.g. a request for "자료를 연구한 자료" wants studies/theses about it, a request for a novel wants the novel)?' },
  { name: 'reader', text: 'Judge as the person who typed the request: would you be glad to see this item in the results, or would it feel off-target?' },
  { name: 'demo', text: 'Judge as a competition judge watching a library-search demo: would this item look like a correct, sensible hit for the request, or like a search mistake?' },
]
const batches = []
for (let i = 0; i < QIDS.length; i += 4) batches.push(QIDS.slice(i, i + 4))

const jobs = []
for (const [bi, qs] of batches.entries()) for (const lens of LENSES) jobs.push({ bi, qs, lens })

const results = await parallel(jobs.map(j => () => agent(
`You are rating Korean library search results. Read ONLY these UTF-8 JSON files with the Read tool, one per query: ${j.qs.map(q => `${DIR}/${q}.json`).join(', ')}. Open no other file, run no commands, edit nothing.

Each file has a search request ('query', Korean) and a list of candidate items ('books', labelled B1, B2, … in random order). Each item has title, author, doc_type (literature = literary works and Korean-literature theses, book = general books, policy = government/policy reports), year and, when available, the library's own summary/introduction/themes/keywords (machine-written — use them only as a description of the item). Items with English titles are English-language classics.

${j.lens.text}

Score EVERY item of every file: 2 = clearly matches the request; 1 = partly (related but not what was asked, or only loosely fitting); 0 = not relevant / a search mistake. Judge each item on its own — do not compare items or try to balance scores. Give a short Korean reason for every 0 and 1. Return one entry per file with qid = the file name without .json (e.g. "q03").`,
  { label: `judge:${j.lens.name}:b${j.bi}`, phase: 'Judge', schema: SCHEMA }).then(r => ({ lens: j.lens.name, ...r }))))

return { results: results.filter(Boolean) }
