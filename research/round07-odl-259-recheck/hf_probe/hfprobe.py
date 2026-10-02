"""verify/hfprobe.py — one-off: (A) round07 extract_text (VLM stubbed) on extra ids per ODL version;
(B) raw convert with include_header_footer=True to see whether ODL detects header/footer at all."""
import asyncio, json, os, sys, shutil, types, glob, time, importlib.metadata
BASE=os.path.dirname(os.path.abspath(__file__))
ver=sys.argv[1]; part=sys.argv[2]
ids=json.load(open(os.path.join(BASE,'hf_ids.json'),encoding='utf-8'))
import opendataloader_pdf
assert importlib.metadata.version('opendataloader-pdf')==ver, importlib.metadata.version('opendataloader-pdf')
out={}
if part=='A':
    from services.ingestion import extractor
    async def stub_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        return extractor.PageResult(page_num=page.number, text="OCR_STUB", method="vlm", confidence=0.9)
    extractor._extract_with_vlm=stub_vlm
    cur={}
    def keep(path, ignore_errors=False, **kw):
        cur['n']=cur.get('n',0)+1
        dst=os.path.join(cur['dir'],f"attempt{cur['n']}")
        try: shutil.move(str(path),dst)
        except Exception: shutil.rmtree(path,ignore_errors=True)
    extractor.shutil=types.SimpleNamespace(rmtree=keep)
    import logging
    logs=[]
    class H(logging.Handler):
        def emit(self,r): logs.append(r.getMessage())
    lg=logging.getLogger(extractor.__name__); lg.setLevel(logging.INFO); lg.addHandler(H()); lg.propagate=False
    for e in ids:
        i=e['id']; d=os.path.join(BASE,'hf_out',ver,i); shutil.rmtree(d,ignore_errors=True); os.makedirs(d)
        cur.clear(); cur['dir']=d; logs.clear()
        cap=[]
        real=extractor.extract_text_opendataloader if not hasattr(extractor,'_real_odl') else extractor._real_odl
        extractor._real_odl=real
        async def rec(*a,**kw):
            r=await real(*a,**kw); cap.append(r); return r
        extractor.extract_text_opendataloader=rec
        t0=time.monotonic()
        res=asyncio.run(extractor.extract_text(f"D:/SKOVIX/KCI/pdf/{i}.pdf", i))
        odl=cap[0]
        types_c={}
        for j in glob.glob(d+'/attempt*/*.json'):
            jd=json.load(open(j,encoding='utf-8'))
            for el in jd.get('kids',[]): types_c[el.get('type')]=types_c.get(el.get('type'),0)+1
        out[i]={'vlm':sorted(p.page_num for p in res.pages if p.method=='vlm'),
                'odl_pages':[p.page_num for p in odl.pages],'odl_text':{str(p.page_num):p.text for p in odl.pages},
                'final_text':{str(p.page_num):p.text for p in res.pages},
                'fill':{str(k):v for k,v in odl.table_fill_ratios.items()},'errors':res.errors,'fb':res.odl_fallback,
                'odl_seconds':round(odl.odl_seconds,2),'json_types':types_c,
                'reasons':[m for m in logs if 'OCR 보완' in m],'short_kept':res.short_kept,'vlm_capped':res.vlm_capped,
                'cfg_image_output':extractor.cfg.ODL_IMAGE_OUTPUT}
        print(i, ver, 'vlm',len(out[i]['vlm']), 'pages',len(odl.pages), 'fb',res.odl_fallback, 'hf', {k:v for k,v in types_c.items() if k in('header','footer')}, round(time.monotonic()-t0,1), flush=True)
else:
    for e in ids:
        i=e['id']; d=os.path.join(BASE,'hf_inc',ver,i); shutil.rmtree(d,ignore_errors=True); os.makedirs(d)
        opendataloader_pdf.convert(input_path=f"D:/SKOVIX/KCI/pdf/{i}.pdf", output_dir=d, format=["markdown","json"],
            image_output="off", image_format="jpeg", table_method="cluster",
            markdown_page_separator="\n<<<ODL_PAGE_BREAK_%page-number%>>>\n", keep_line_breaks=False, quiet=True,
            include_header_footer=True)
        types_c={}; hf=[]
        for j in glob.glob(d+'/*.json'):
            jd=json.load(open(j,encoding='utf-8'))
            for el in jd.get('kids',[]):
                types_c[el.get('type')]=types_c.get(el.get('type'),0)+1
                if el.get('type') in ('header','footer'): hf.append((el.get('page number'),el.get('type')))
        out[i]={'json_types':types_c,'hf':hf}
        print(i, ver, 'B hf', {k:v for k,v in types_c.items() if k in('header','footer')}, flush=True)
json.dump(out,open(os.path.join(BASE,f'hfprobe_{ver}_{part}.json'),'w',encoding='utf-8'),ensure_ascii=False)
