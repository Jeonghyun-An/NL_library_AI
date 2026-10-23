"""페르소나 책 17권 — 적재 뒤 운영 확인 (1회성, 2026-10-23). 결과는 verify_report.txt.

운영 공개 API 만 읽는다(쓰지 않는다). 책마다 상세(적재 여부·요약 칸 빈칸·'책' 단정 표현·'이 자료' 횟수)와 썸네일·원문 PDF
응답 코드를 보고, 제목·인물·원제 30개 질의로 소장자료 검색(book 모드, 재작성·재순위 켬)에서 몇 위에 오는지 센다.

    python verify_ingest.py > verify_report.txt
"""
import httpx, re, json, sys, concurrent.futures as cf
sys.stdout.reconfigure(encoding="utf-8")
B="https://skovix.landsoft.co.kr"; H={"x-session-id":"00000000-0000-4000-8000-00000000d1a9"}
IDS=["PSN-MANSEJEON","PSN-SONAGI","PSN-JEOKBIN","PSN-CHUNHYANG","PSN-HEOSAENG","PSN-BEAUTY-BEAST","PSN-RED-CAP","PSN-STUDY-SCARLET","PSN-DOG-FLANDERS","PSN-ROBIN-HOOD","PSN-BULFINCH","PSN-ANDERSEN","PSN-DADDY-LONG-LEGS","PSN-PERRAULT","PSN-GEUMDOKKI","PSN-ONDAL","PSN-GRIFFIS-COREA"]
BOOKW=re.compile(r"이 책|(?<![정대방])책(?:은|을|이)(?=[\s.,])")
def check(bid):
    d=httpx.get(f"{B}/api/books/{bid}",timeout=30).json()
    f={}
    for k in ("summary","introduction","plot","read_effect","themes"):
        v=d.get(k) or (d.get("extra") or {}).get(k) or ""
        f[k]=(len(v), len(BOOKW.findall(v)), v.count("이 자료"))
    th=httpx.get(f"{B}/api/books/{bid}/thumbnail",timeout=60).status_code
    pdf=httpx.get(f"{B}/api/books/{bid}/pdf",timeout=120).status_code
    return bid, d.get("title"), d.get("doc_type"), d.get("is_embedded"), f, th, pdf
with cf.ThreadPoolExecutor(4) as ex:
    for bid,title,dt,emb,f,th,pdf in ex.map(check, IDS):
        miss=[k for k,(n,_,_) in f.items() if n==0]
        bw=sum(b for _,b,_ in f.values()); jr=sum(j for _,_,j in f.values())
        print(f"{bid:22} {title[:14]:14} {dt:10} 적재={emb} 빈칸={miss or '없음'} '책'={bw} '이 자료'={jr} 썸네일={th} 원문={pdf}")
Q=[("만세전","PSN-MANSEJEON"),("소나기","PSN-SONAGI"),("적빈","PSN-JEOKBIN"),("백신애 적빈","PSN-JEOKBIN"),("춘향전","PSN-CHUNHYANG"),("허생전","PSN-HEOSAENG"),("박지원 허생전","PSN-HEOSAENG"),
   ("미녀와 야수","PSN-BEAUTY-BEAST"),("빨간 모자","PSN-RED-CAP"),("주홍색 연구","PSN-STUDY-SCARLET"),("셜록 홈즈와 왓슨의 첫 만남","PSN-STUDY-SCARLET"),("플랜더스의 개","PSN-DOG-FLANDERS"),("파트라슈","PSN-DOG-FLANDERS"),
   ("로빈 후드","PSN-ROBIN-HOOD"),("로빈 후드의 모험","PSN-ROBIN-HOOD"),("신화의 시대","PSN-BULFINCH"),("불핀치 그리스 로마 신화","PSN-BULFINCH"),("안데르센 동화","PSN-ANDERSEN"),("성냥팔이 소녀","PSN-ANDERSEN"),
   ("키다리 아저씨","PSN-DADDY-LONG-LEGS"),("주디 애벗","PSN-DADDY-LONG-LEGS"),("페로 동화집","PSN-PERRAULT"),("신데렐라","PSN-PERRAULT"),("금도끼","PSN-GEUMDOKKI"),("금도끼 은도끼","PSN-GEUMDOKKI"),
   ("바보 온달","PSN-ONDAL"),("평강공주와 온달","PSN-ONDAL"),("하멜 표류기","PSN-GRIFFIS-COREA"),("하멜","PSN-GRIFFIS-COREA"),("Corea Without and Within","PSN-GRIFFIS-COREA")]
def search(qt):
    q,t=qt
    d=httpx.post(B+"/api/books/search",headers=H,timeout=180,json={"query":q,"mode":"book","top_k":10,"use_rewrite":True,"use_rerank":True}).json()
    ids=[b["book_id"] for b in d["books"]]
    return q,t,(ids.index(t)+1 if t in ids else None),(ids[0] if ids else None),((d["books"][0].get("book_info") or {}).get("title") if ids else "")
hit1=0
with cf.ThreadPoolExecutor(3) as ex:
    for q,t,r,top,tt in ex.map(search,Q):
        hit1+= r==1
        print(f"[검색] {q:22} → {t} 순위 {r}" + ("" if r==1 else f" | 1위 {top} {str(tt)[:24]}"))
print("1위", hit1, "/", len(Q))
