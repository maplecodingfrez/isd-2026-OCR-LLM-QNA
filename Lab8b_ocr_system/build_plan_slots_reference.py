"""สร้าง plan_slots_REFERENCE.json — เฉลยช่องตามเล่ม (กรอกมือ ใช้เทียบผล OCR เท่านั้น ห้ามโหลดเข้า DB)

ช่องในตารางแผนที่ plan_item เก็บไม่ตรงเล่ม (กรอกจากรูปเล่มด้วยมือ)

ที่มา: อ่านรูป runs/*/data_input/ ด้วยตา — ใช้เป็น "เฉลย" เทียบผลสกัดจาก OCR (compare_slots_to_reference.py) เท่านั้น
รันซ้ำได้: python build_plan_slots_reference.py
"""
import json
from pathlib import Path

GE = "วิชาเลือกหมวดศึกษาทั่วไป"
LANG = "วิชาเลือกด้านภาษาและการสื่อสาร"


def w(y, s, code, name, cr=3):
    return {"year": y, "semester": s, "kind": "wildcard", "code": code,
            "name_th": name, "credits": cr}


def one(y, s, codes, name, cr=6):
    return {"year": y, "semester": s, "kind": "choose_one", "name_th": name,
            "credits": cr, "groups": [{"name": name, "codes": codes}]}


def grp(y, s, cr, groups, name):
    return {"year": y, "semester": s, "kind": "choose_group", "name_th": name,
            "credits": cr, "note": "เลือก 1 กลุ่มวิชา หน่วยกิตนับเฉพาะกลุ่มที่เลือก",
            "groups": [{"name": n, "codes": c} for n, c in groups]}


BIT_GE = "วิชาเลือกหมวดศึกษาทั่วไปสำหรับหลักสูตรนานาชาติ"
BIT_IT = "วิชาเลือกทางเทคโนโลยีสารสนเทศทางธุรกิจ"
FREE = "วิชาเลือกเสรี"

IT_G22 = grp(2, 2, 6, [("กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์", ["06016414", "06016415"]),
                       ("กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ", ["06016419", "06016420"]),
                       ("กลุ่มวิชาด้านสื่อประสมสำหรับการพัฒนาสื่อเชิงโต้ตอบ เว็บ และเกม", ["06016424", "06016425"])],
             "เลือก 1 กลุ่มวิชา ปี 2/2")
IT_G31 = grp(3, 1, 9, [("กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์", ["06016416", "06016417", "06016418"]),
                       ("กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ", ["06016421", "06016422", "06016423"]),
                       ("กลุ่มวิชาด้านสื่อประสมสำหรับการพัฒนาสื่อเชิงโต้ตอบ เว็บ และเกม", ["06016426", "06016427", "06016418"])],
             "เลือก 1 กลุ่มวิชา ปี 3/1")

plans = {
    "AIT": [w(1, 2, "9064xxxx", GE),
            w(3, 1, "060464xx", "วิชาเลือกเทคโนโลยีปัญญาประดิษฐ์เฉพาะทาง", 6),
            w(3, 2, "060464xx", "วิชาเลือกเทคโนโลยีปัญญาประดิษฐ์เฉพาะทาง", 6),
            w(3, 2, "xxxxxxxx", FREE + " 1"),
            w(4, 1, "9064xxxx", GE), w(4, 1, "90644xxx", LANG), w(4, 1, "xxxxxxxx", FREE + " 2"),
            one(4, 2, ["06046443", "06046444"], "สหกิจศึกษา หรือ สหกิจศึกษาต่างประเทศ")],
    "BIT_coop": [w(2, 2, "9664xxxx", BIT_GE + " 1"), w(3, 1, "96644xxx", LANG),
                 w(3, 2, "06036xxx", BIT_IT + " 1"), w(3, 2, "xxxxxxxx", FREE + " 1"),
                 w(4, 1, "06036xxx", BIT_IT + " 2"), w(4, 1, "xxxxxxxx", FREE + " 2"),
                 w(4, 1, "9664xxxx", BIT_GE + " 2"),
                 one(4, 2, ["06036147", "06036148"], "สหกิจศึกษา หรือ สหกิจศึกษาต่างประเทศ")],
    "BIT_no_coop": [w(2, 2, "9664xxxx", BIT_GE + " 1"), w(3, 1, "96644xxx", LANG),
                    w(4, 1, "9664xxxx", BIT_GE + " 2"),
                    w(4, 2, "06036xxx", BIT_IT + " 1"), w(4, 2, "06036xxx", BIT_IT + " 2"),
                    w(4, 2, "xxxxxxxx", FREE + " 1"), w(4, 2, "xxxxxxxx", FREE + " 2")],
    "DSBA_coop": [w(2, 1, "90644xxx", LANG),
                  w(3, 1, "06026xxx", "วิชาเลือกกลุ่ม 1"), w(3, 1, "06026xxx", "วิชาเลือกกลุ่ม 2"),
                  w(3, 1, "9064xxxx", GE),
                  w(3, 2, "06026xxx", "วิชาเลือกกลุ่ม 3"), w(3, 2, "06026xxx", "วิชาเลือกกลุ่ม 4"),
                  w(4, 1, "9064xxxx", GE), w(4, 1, "xxxxxxxx", FREE + " 1"), w(4, 1, "xxxxxxxx", FREE + " 2"),
                  one(4, 2, ["06026259", "06026260"], "สหกิจศึกษา หรือ สหกิจศึกษาต่างประเทศ")],
    "DSBA_no_coop": [w(2, 1, "90644xxx", LANG),
                     w(3, 1, "06026xxx", "วิชาเลือกกลุ่ม 1"), w(3, 1, "06026xxx", "วิชาเลือกกลุ่ม 2"),
                     w(3, 1, "9064xxxx", GE),
                     w(3, 2, "06026xxx", "วิชาเลือกกลุ่ม 3"), w(3, 2, "06026xxx", "วิชาเลือกกลุ่ม 4"),
                     w(4, 1, "06026xxx", "วิชาเลือกในกลุ่มวิชาเลือกหรือกลุ่มวิชาชีพเฉพาะด้าน 1"),
                     w(4, 1, "06026xxx", "วิชาเลือกในกลุ่มวิชาเลือกหรือกลุ่มวิชาชีพเฉพาะด้าน 2"),
                     w(4, 2, "9064xxxx", GE), w(4, 2, "xxxxxxxx", FREE + " 1"), w(4, 2, "xxxxxxxx", FREE + " 2")],
    "IT_coop": [IT_G22, w(3, 1, "90644xxx", LANG), IT_G31,
                one(3, 2, ["06016481", "06016482"], "สหกิจศึกษา หรือ สหกิจศึกษาต่างประเทศ"),
                w(4, 1, "060464xx", "วิชาเลือกทางเทคโนโลยีสารสนเทศ 1"), w(4, 1, "9064xxxx", GE + " 1"),
                w(4, 1, "xxxxxxxx", FREE + " 1"), w(4, 1, "xxxxxxxx", FREE + " 2"),
                w(4, 2, "9064xxxx", GE + " 2")],
    "IT_no_coop": [IT_G22, w(3, 1, "90644xxx", LANG), IT_G31,
                   w(3, 2, "060464xx", "วิชาเลือกทางเทคโนโลยีสารสนเทศ 1"),
                   w(3, 2, "060464xx", "วิชาเลือกทางเทคโนโลยีสารสนเทศ 2"),
                   w(4, 1, "060464xx", "วิชาเลือกทางเทคโนโลยีสารสนเทศ 3"), w(4, 1, "9064xxxx", GE + " 1"),
                   w(4, 1, "xxxxxxxx", FREE + " 1"),
                   w(4, 2, "9064xxxx", GE + " 2"), w(4, 2, "xxxxxxxx", FREE + " 2")],
}
apply = {
    "runs/AIT": "AIT", "runs/AIT_retry": "AIT", "runs/AIT_retry2": "AIT", "runs/AIT_retry3": "AIT",
    "runs/BIT/coop": "BIT_coop", "runs/BIT/coop_retry": "BIT_coop",
    "runs/BIT/no_coop": "BIT_no_coop", "runs/BIT/no_coop_retry": "BIT_no_coop",
    "runs/DSBA/coop": "DSBA_coop",
    "runs/DSBA/no_coop": "DSBA_no_coop", "runs/DSBA/no_coop_retry": "DSBA_no_coop",
    "runs/IT/coop": "IT_coop", "runs/IT/coop_retry": "IT_coop",
    "runs/IT/no_coop": "IT_no_coop", "runs/IT/no_coop_retry": "IT_no_coop",
}
out = {"_note": "ช่องตามเล่มที่ plan_item เก็บไม่ได้ — สร้างโดย build_plan_slots.py",
       "plans": {k: {"slots": v} for k, v in plans.items()}, "apply": apply}
Path(__file__).with_name("plan_slots_REFERENCE.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote plan_slots_REFERENCE.json", {k: len(v) for k, v in plans.items()})
