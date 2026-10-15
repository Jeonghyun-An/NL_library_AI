"""판정 결과를 연구별·변형별로 다시 센다 (1회성). 검증이 뒤집은 문장은 그 판정을 쓴다.

    python tally_perjob.py judge_r1_result.json judge_key.json base,cite,frame
    python tally_perjob.py judge_r2_result.json judge_r2_key.json base,cite,cite2
"""
import json,sys
from collections import defaultdict
res=json.load(open(sys.argv[1],encoding='utf-8')); key=json.load(open(sys.argv[2],encoding='utf-8'))
variants=sys.argv[3].split(',')
rows=defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
for r in res['perJob']:
    k=key[r['job']]
    fixes={f"{c['label']}#{c['n']}":c for c in ((r.get('verify') or {}).get('checks') or [])}
    for o in (r.get('audit') or {}).get('outputs') or []:
        v=k[o['label']]['variant']
        for s in o['sentences']:
            vd=s['verdict']
            fx=fixes.get(f"{o['label']}#{s['n']}")
            if fx and vd in ('W','M','U_claim','F'): vd=fx['final_verdict']
            rows[r['job']][v][vd]+=1; rows[r['job']][v]['n']+=1
    for tri in (r.get('rank') or {}).get('triads') or []:
        for i,l in enumerate(tri['ranking']):
            rows[r['job']][k[l]['variant']]['pts']+=3-i
print('job      '+'  '.join(f"{v:>22}" for v in variants))
for j in sorted(rows):
    cells=[]
    for v in variants:
        d=rows[j][v]; n=d['n'] or 1
        cells.append(f"S{100*d['S']//n:3d}% M{100*(d['M']+d['W'])//n:3d}% U{100*d['U_claim']//n:3d}% p{d['pts']}")
    print(j,'  '.join(f"{c:>22}" for c in cells))
