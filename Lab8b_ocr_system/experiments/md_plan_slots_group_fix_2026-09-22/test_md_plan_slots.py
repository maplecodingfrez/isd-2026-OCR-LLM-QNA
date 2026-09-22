"""ทดสอบ md_plan_slots.py — โดยเฉพาะบั๊ก "หัวกลุ่มหาย" (กลุ่มย่อยที่ OCR ไม่แยกเซลล์รหัส แถวต่อของ rowspan
ยำรหัสวิชาไว้ในเซลล์บรรยายเดียว ทำให้ถูกเข้าใจผิดว่าเป็นวิชาปกติ) — เจอจริงที่ IT ปี 2/2

รัน (จาก Lab8b_ocr_system): PYTHONUTF8=1 ../.venv/Scripts/python.exe experiments/md_plan_slots_group_fix_2026-09-22/test_md_plan_slots.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / "ocr_system")]
import md_plan_slots as M  # noqa: E402

fails = 0


def check(name, cond):
    global fails
    print(("  [ ok ] " if cond else "  [FAIL] ") + name)
    fails += 0 if cond else 1


def term(md, y=2, s=2):
    return M.derive_slots(md)[0], {r["year"]: r for r in M.derive_slots(md)[1] if r["year"] == y}[y]


# ===== ของจริง: IT no-coop ปี 2/2 (ก๊อปจาก runs/IT/no_coop/lab7b_output/intermediate_vlm.md วันที่ 2026-09-22) =====
REAL_IT = """
ปีที่ 2 ภาคการศึกษาที่ 2
<table><tr><td>รหัสวิชา</td><td>ชื่อวิชา</td><td>หน่วยกิต (บรรยาย-ปฏิบัติ-ศึกษาด้วยตนเอง)</td></tr>
<tr><td>06016405</td><td>พื้นฐานความมั่นคงปลอดภัยไซเบอร์ CYBERSECURITY FUNDAMENTALS</td><td>3(3-0-6)</td></tr>
<tr><td>06016410</td><td>วิศวกรรมซอฟต์แวร์ SOFTWARE ENGINEERING</td><td>3(3-0-6)</td></tr>
<tr><td>06016412</td><td>โครงสร้างระบบคอมพิวเตอร์และระบบปฏิบัติการ COMPUTER ORGANIZATION AND OPERATING SYSTEM</td><td>3(2-2-5)</td></tr>
<tr><td>06066302</td><td>การเขียนโปรแกรมเว็บพื้นฐาน FUNDAMENTAL WEB PROGRAMMING</td><td>3(2-2-5)</td></tr>
<tr><td rowspan="4">06016414, 06016415</td><td>กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์ ระบบฐานข้อมูลแบบโนเอสคิวแอล NOSQL DATABASE SYSTEMS การเขียนโปรแกรมเชิงฝังก๊อป FUNCTIONAL PROGRAMMING</td><td rowspan="4">3(2-2-5)</td></tr>
<tr><td>06016419 กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ โครงสร้างพื้นฐานเครือข่ายการสื่อสาร COMMUNICATION NETWORK INFRASTRUCTURE</td></tr>
<tr><td>06016420 ระบบโครงสร้างพื้นฐานและการบริการ INFRASTRUCTURE SYSTEMS AND SERVICES</td></tr>
<tr><td rowspan="3">06016424, 06016425</td><td>กลุ่มวิชาด้านสื่อประสมสำหรับการพัฒนาสื่อเชิงโตตอบ เว็บ และเกม การออกแบบส่วนต่อประสานกับมนุษย์ HUMAN INTERFACE DESIGN พื้นฐานการออกแบบทัศนศิลป์สำหรับสื่อปฏิสัมพันธ์ VISUAL DESIGN FUNDAMENTALS FOR INTERACTIVE MEDIA</td><td rowspan="3">3(3-0-6)</td></tr>
<tr><td>06016424 กลุ่มวิชาด้านเทคโนโลยีสารสนเทศ การออกแบบส่วนต่อประสานกับมนุษย์ HUMAN INTERFACE DESIGN</td></tr>
<tr><td>06016425 พื้นฐานการออกแบบทัศนศิลป์สำหรับสื่อปฏิสัมพันธ์ VISUAL DESIGN FUNDAMENTALS FOR INTERACTIVE MEDIA</td></tr>
<tr><td colspan="3">รวม 18</td></tr></table>
"""

print("กรณีจริง: IT no-coop ปี 2/2 (3 กลุ่ม แต่กลุ่มกลางเขียนแบบไม่มีเซลล์รหัสแยก)")
slots, report = M.derive_slots(REAL_IT)
rpt = {(r["year"], r["semester"]): r for r in report}[(2, 2)]
check("plain = 12 (เฉพาะ 4 วิชาปกติ; ไม่ปนวิชาในกลุ่ม)", rpt["plain"] == 12)
check("ไม่มีหน่วยกิตที่อธิบายไม่ได้ (unexplained = 0)", rpt["unexplained"] == 0)
cg = [s for s in slots if s["kind"] == "choose_group"][0]
check("เลือก 1 กลุ่มวิชา = 6 หน่วยกิต", cg["credits"] == 6)
groups = {g["name"]: set(g["codes"]) for g in cg["groups"]}
codesets = list(groups.values())
check("มี 3 กลุ่ม (ไม่ใช่ 2) — กลุ่มกลางที่หัวหายต้องถูกกู้กลับมา",
      len(codesets) == 3)
check("กลุ่มกลาง (06016419, 06016420) อยู่ในกลุ่มเดียวกัน ไม่ใช่วิชาปกติ",
      {"06016419", "06016420"} in codesets)
check("กลุ่มที่ 1 และ 3 ยังถูกต้องเหมือนเดิม",
      {"06016414", "06016415"} in codesets and {"06016424", "06016425"} in codesets)
check("ไม่มีรหัสซ้ำข้ามกลุ่ม (แถวอธิบายซ้ำ 06016424/06016425 ถูกข้าม ไม่สร้างกลุ่มที่ 4)",
      len(codesets) == len(set(map(frozenset, codesets))) and sum(len(c) for c in codesets) == 6)
plain_codes = {p["code"] for p in M.parse_terms(REAL_IT)[(2, 2)]["plain"]}
check("06016419/06016420 ไม่ถูกนับเป็นวิชาปกติอีกต่อไป",
      "06016419" not in plain_codes and "06016420" not in plain_codes)

print("\nกรณีถดถอย: rowspan ปกติ 2 แถวไม่มีป้ายชื่อกลุ่ม (ต้องยังทำงานเหมือนเดิม — ไม่ใช่เคสที่แก้)")
SIMPLE = """
ปีที่ 1 ภาคการศึกษาที่ 1
<table><tr><td>รหัสวิชา</td><td>ชื่อวิชา</td><td>หน่วยกิต</td></tr>
<tr><td rowspan="2">10000001, 10000002</td><td>กลุ่มวิชาด้านทดสอบ วิชาเอ VISIT A</td><td rowspan="2">3(3-0-6)</td></tr>
<tr><td>ชื่อวิชาสอง (ไม่มีรหัส ไม่มีคำว่ากลุ่มวิชาด้าน)</td></tr>
<tr><td>10000003</td><td>วิชาปกติ</td><td>3(3-0-6)</td></tr>
<tr><td colspan="3">รวม 6</td></tr></table>
"""
slots2, report2 = M.derive_slots(SIMPLE)
r2 = {(r["year"], r["semester"]): r for r in report2}[(1, 1)]
check("กรณีไม่มีบั๊ก (แถวต่อไม่มีรหัสฝัง) ยังทำงานเหมือนเดิม: unexplained ไม่ใช่ None และไม่พัง",
      r2["unexplained"] is not None)

print("\nกรณี boundary: ไม่มี span_kind=='merged' ที่ใช้งานอยู่ (กันไม่ให้ทริกเกอร์ผิดจังหวะ)")
WILD_ONLY = """
ปีที่ 1 ภาคการศึกษาที่ 2
<table><tr><td>รหัสวิชา</td><td>ชื่อวิชา</td><td>หน่วยกิต</td></tr>
<tr><td>10000004</td><td>วิชาปกติ</td><td>3(3-0-6)</td></tr>
<tr><td>10000005 มีรหัสแต่ไม่ได้อยู่กลาง rowspan ใด ๆ</td></tr>
<tr><td colspan="3">รวม 3</td></tr></table>
"""
slots3, report3 = M.derive_slots(WILD_ONLY)
p3 = M.parse_terms(WILD_ONLY)[(1, 2)]
check("แถวเดี่ยวที่มีรหัสแต่ไม่ได้อยู่ใน rowspan merged -> เข้าทางเดิม (นับเป็นวิชาปกติ ไม่ทริกเกอร์ตัวกันใหม่)",
      any(p["code"] == "10000005" for p in p3["plain"]))

print(f"\n{'ผ่านทั้งหมด' if not fails else 'ไม่ผ่าน ' + str(fails) + ' ข้อ'}")
sys.exit(1 if fails else 0)
