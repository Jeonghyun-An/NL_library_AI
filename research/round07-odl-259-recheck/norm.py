import re,sys
opts={};cur=None
for line in open(sys.argv[1],encoding='utf-8',errors='replace'):
    m=re.match(r'^\s*(-\w,)?(--[\w-]+)( <arg>)?\s{2,}(.*)$',line.rstrip())
    if m:
        cur=m.group(2); opts[cur]=[(m.group(3) or '').strip(), m.group(4).strip()]
    elif cur and line.strip():
        opts[cur][1]+=' '+line.strip()
for k in sorted(opts): print(k, opts[k][0], '|', re.sub(r'(\w)- (\w)',r'\1-\2',opts[k][1]).replace('-hyb rid','-hybrid'))
