import json,sys
from pathlib import Path
ROOT=Path(r"D:/DSBA 3rd Year/Works/ocr_system (all)/ocr_system/Lab8b_ocr_system")
sys.path[:0]=[str(ROOT/"src"/"ocr_system"),str(ROOT/"src")]
from lab7b_curriculum import evaluate
import lab7_metrics as M
gt=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out={}
for t in ["AIT","AIT_dewm2","AIT_dewm3","AIT_dewm4","AIT_dewm5","AIT_dewm6"]:
    p=json.loads((ROOT/"runs"/t/"lab7b_output"/"pred_vlm.json").read_text(encoding="utf-8"))
    st,al=evaluate(p,gt); d=M.stats_to_dict(st)
    out[t]={"tok":M.TOKENIZER_NAME,"P":round(al["precision"],3),"R":round(al["recall"],3),"gt":al["gt_total"],"matched":al["matched"],"missed":al["missed"],"spur":al["spurious"],"fields":d}
json.dump(out,open(sys.argv[2],"w",encoding="utf-8"),ensure_ascii=False,indent=1)
for t,v in out.items(): print(t,v["tok"],v["gt"],v["matched"],v["missed"],v["spur"],v["P"],v["R"])
print(json.dumps(out["AIT_dewm5","AIT_dewm6"]["fields"],ensure_ascii=False)[:600])
