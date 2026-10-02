import csv, json, random, os, collections
rows=list(csv.DictReader(open(r'C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/research/round07-ingest-regression/docs.csv',encoding='utf-8-sig')))
sample={e['id'] for e in json.load(open('sample.json',encoding='utf-8'))}
print(collections.Counter(r['group'] for r in rows))
cand=[r for r in rows if r['id'] not in sample and r['doc_is_scan']=='False' and 4<=int(r['pages'])<=40]
rep=[r for r in cand if r['repeated'].strip()]
norep=[r for r in cand if not r['repeated'].strip()]
random.seed(7)
pick=random.sample(rep,min(16,len(rep)))+random.sample(norep,8)
out=[]
for r in pick:
    p=f"D:/SKOVIX/KCI/pdf/{r['id']}.pdf"
    if os.path.isfile(p): out.append({'id':r['id'],'group':r['group'],'pages':int(r['pages']),'repeated':r['repeated'][:80]})
json.dump(out,open('verify/hf_ids.json','w',encoding='utf-8'),ensure_ascii=False,indent=0)
for o in out: print(o)
print(len(out), sum(o['pages'] for o in out))
