import json,re,sys
SP=sys.argv[1]
RANGES={"ait":(23,26),"bit":(26,35),"dsba":(23,36),"it":(31,44)}
GT={"ait":("ait","all"),"bit_no_coop":("bit","no_coop"),"bit_coop":("bit","coop"),
    "dsba_no_coop":("dsba","no_coop"),"dsba_coop":("dsba","coop"),"it_no_coop":("it","no_coop"),"it_coop":("it","coop")}
PUA=re.compile("[\uf700-\uf7ff]")
def nth(s): return re.sub(r"[\s\u0e31\u0e33-\u0e3a\u0e47-\u0e4e]","",PUA.sub("",s or ""))
def nen(s): return re.sub(r"[^A-Z0-9]","",(s or "").upper())
def blobs(n):
    pages=json.load(open(f"{SP}/{n}_pages.json",encoding="utf-8"))
    a,b=RANGES[n]; B={}; plan="all"; key=None
    for pg in range(a,b+1):
        for raw in pages[pg-1].split("\n"):
            l=PUA.sub("",raw).strip()
            if "3.1.4.1" in l: plan="no_coop"
            elif "3.1.4.2" in l: plan="coop"
            if re.match(r"3\.1\.\d+\.?\s*คำอธิบาย|3\.1\.\d+\s*คําอธิบาย",l): return B
            m=re.search(r"ป\S?ท\S?ี่\s*(\d)\s*ภาคการศึกษาที่\s*(\d)",l)
            if m: key=(plan,int(m[1]),int(m[2])); B.setdefault(key,{"lines":[],"tot":None,"page":pg}); continue
            if key is None: continue
            B[key]["lines"].append(l)
    return B
def total(lines):
    for i,l in enumerate(lines):
        if l.startswith("รวม") and not l.startswith("รวมตลอด"):
            for m in lines[i:i+4]:
                x=re.fullmatch(r"\d+",m.strip())
                if x: return int(x[0])
    return None
res={}
for g,(n,plan) in GT.items():
    gt=json.load(open(f"Lab9_evaluation/ground_truth_scoped/{g}_scoped.json",encoding="utf-8"))
    B=blobs(n); issues=[]
    seen={}
    for c in gt["courses"]:
        y,s=int(c["year"]),int(c["semester"]); key=(plan,y,s)
        b=B.get(key)
        code=c["code"]
        if not b: issues.append(("NO_SEM",code,f"{y}/{s}","ภาคนี้ไม่มีในเล่ม")); continue
        seen.setdefault(key,[]).append(c)
        text="\n".join(b["lines"]); tt=nth(text); te=nen(text)
        if code not in text.replace(" ",""):
            # code elsewhere in plan?
            elsewhere=[k for k,v in B.items() if k[0]==plan and code in "\n".join(v["lines"])]
            issues.append(("CODE_NOT_IN_SEM",code,f"{y}/{s}",f"GT ระบุ {y}/{s}; ในเล่มพบที่ {[k[1:] for k in elsewhere] or 'ไม่พบเลยในแผน'}")); continue
        if c.get("name_th") and nth(c["name_th"]) not in tt: issues.append(("NAME_TH",code,f"{y}/{s}",c["name_th"]))
        if c.get("name_en") and nen(c["name_en"]) not in te: issues.append(("NAME_EN",code,f"{y}/{s}",c["name_en"]))
        cr=(c.get("credits") or "").replace(" ","")
        if cr and cr.replace("(x-x-x)","") and cr not in text.replace(" ","") and not re.search(r"x",code,re.I):
            issues.append(("CREDITS",code,f"{y}/{s}",cr))
    # reverse: real codes in book not in GT
    for key,b in B.items():
        if key[0]!=plan: continue
        gtc={c["code"] for c in gt["courses"] if (int(c["year"]),int(c["semester"]))==key[1:]}
        for l in b["lines"]:
            for m in re.findall(r"(?<![0-9])\d{8}(?![0-9])",l):
                if m not in gtc: issues.append(("BOOK_NOT_IN_GT",m,f"{key[1]}/{key[2]}",l[:60]))
        # totals
        t=total(b["lines"]); gs=sum(int(re.match(r"\d+",c["credits"]).group()) for c in gt["courses"] if (int(c["year"]),int(c["semester"]))==key[1:] and c.get("credits") and re.match(r"\d+",c["credits"]))
        b["tot"]=t
        if t is not None and t!=gs: issues.append(("SEM_TOTAL",f"{key[1]}/{key[2]}",f"{key[1]}/{key[2]}",f"เล่มพิมพ์ รวม={t} ; GT รวม={gs}"))
    res[g]={"n_gt":len(gt["courses"]),"issues":issues,"sems":[k[1:] for k in B if k[0]==plan]}
    print("=====",g,"GT",len(gt["courses"]),"ภาคในเล่ม",len(res[g]["sems"]),"issues",len(issues))
    for i in issues: print("  ",*i)
json.dump(res,open(f"{SP}/gtcheck.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
