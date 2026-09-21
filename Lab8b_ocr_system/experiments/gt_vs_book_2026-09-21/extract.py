import fitz,json,sys
for n in ["ait","bit","dsba","it"]:
    d=fitz.open(f"data/input/{n}_curriculum.pdf")
    pages=[p.get_text() for p in d]
    json.dump(pages,open(sys.argv[1]+f"/{n}_pages.json","w",encoding="utf-8"),ensure_ascii=False)
    print(n,len(pages),sum(len(p) for p in pages))
