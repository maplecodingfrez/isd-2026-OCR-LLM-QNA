import json,re,sys
sys.argv=[sys.argv[0],sys.argv[1]]+sys.argv[2:]
exec(open(sys.argv[1]+"/gtcheck.py",encoding="utf-8").read().split("res={}")[0])
def show_book(n,plan,y,s):
    b=blobs(n)[(plan,y,s)]; print(f"--- BOOK {n} {plan} {y}/{s} p{b['page']}"); print(" | ".join(b["lines"]))
def show_gt(g,y,s):
    gt=json.load(open(f"Lab9_evaluation/ground_truth_scoped/{g}_scoped.json",encoding="utf-8"))
    print(f"--- GT {g} {y}/{s}")
    for c in gt["courses"]:
        if (int(c["year"]),int(c["semester"]))==(y,s): print("  ",c["code"],c["credits"],c["name_th"].replace("\n","/"),"|",(c["name_en"] or "").replace("\n","/"),"|",c["category"],c["type"],c["prerequisite"],c.get("flexible_year_semester"),c.get("note"))
