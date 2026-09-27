"""ดึง "กลุ่มวิชาเลือก" (elective group) จากหน้า catalog ("3.1.3 รายวิชา") ของเล่มหลักสูตร

คนละส่วนกับ Lab7B/8B ที่ดึงเฉพาะตาราง "แผนการศึกษา" (3.1.4) เท่านั้น — วิชาเลือกในตารางแผนเขียน
เป็นรหัส wildcard (เช่น "06036xxx") เพราะตัวเลือกจริงอยู่คนละหน้า (หน้า catalog) ต่างหาก
สคริปต์นี้ดึงหน้า catalog มาแยกเป็นรายวิชาต่อกลุ่ม ไม่ยุ่งกับ pipeline VLM เดิม — ตาราง catalog
เป็นข้อความสะอาด อ่านจาก OCR ข้อความเต็มเล่มที่มีอยู่แล้ว (`outputs/{program}/{program}_curriculum_ocr.txt`
จาก Lab4-6) ได้ตรงๆ ด้วย regex ไม่ต้องเรียกโมเดลซ้ำ

ใช้ (path ตัวอย่างอิงโครงสร้างโฟลเดอร์ใหม่หลังจัดระเบียบ 2026-09-16 — ดู runs/<CURRICULUM>/):
    python -m ocr_system.extract_elective_catalog \
        --text "../outputs/bit/bit_curriculum_ocr.txt" --start-page 24 --end-page 25 \
        -o runs/BIT/electives.json
"""

import argparse
import json
import re
from pathlib import Path

PAGE_RE = re.compile(r"^--- Page (\d+) ---\s*$", re.MULTILINE)
GROUP_RE = re.compile(r"^กลุ่มวิชาที่\s*(\d+)\s*[:：]\s*(.+)$")
# บางเล่มไม่แบ่งย่อยแบบ "กลุ่มวิชาที่ 1-4" — AIT/IT มีกลุ่มเดียวแบนๆ "N) กลุ่มวิชาเลือก... N หน่วยกิต"
# (ไม่มีเลข "ที่ N" กำกับ), DSBA มีหลายกลุ่มย่อยขึ้นต้นด้วย "-" เช่น "- กลุ่มวิทยาการข้อมูล 12 หน่วยกิต"
# — รองรับทั้ง 3 แบบด้วย pattern เดียว (prefix "-" หรือ "N)" หรือไม่มีเลยก็ได้) เรียง group_no ตาม
# ลำดับที่เจอเอง หัวข้อระดับบนที่ไม่มีวิชาเลือกได้จริง (แค่รวมกลุ่มย่อยไว้ข้างใน เช่น DSBA
# "3) กลุ่มวิชาชีพเฉพาะด้าน 12 หน่วยกิต" ตามด้วย "-" กลุ่มย่อยทันที ไม่มีวิชาของตัวเอง) จะกลายเป็น
# กลุ่มว่าง (0 วิชา) เพราะ flush ทันทีที่กลุ่มย่อยถัดมาสร้างกลุ่มใหม่ — กรองทิ้งท้ายฟังก์ชันอยู่แล้ว
SECTION_RE = re.compile(r"^(?:-|\d+\))?\s*(กลุ่ม.+?)\s+\d+\s*หน่วยกิต\s*$")
# หน่วยกิตชั่วโมงต่อสัปดาห์อาจเป็นเลข 2 หลัก (เช่น สหกิจศึกษา "6(0-35-0)") ห้ามจำกัดแค่ 1 หลัก
# บางเล่ม (AIT) เว้นวรรคก่อนวงเล็บ "3 (3-0-6)" บางเล่ม (BIT) ไม่เว้น "3(3-0-6)" — รับทั้งคู่
# ตัวคั่นก่อนหน่วยกิตใช้ \s* (ไม่ใช่ \s+) เพราะบาง OCR มีอักขระแปลกปลอมแทรกก่อนตัวเลขหน่วยกิต
# (เจอจริงกับ DSBA "06026225": "...ทางการ »3 (2-2-5)" — ถ้าบังคับ \s+ ตรงหน้าตัวเลขเป๊ะๆ
# ตัว "»" จะกันไม่ให้ match เลย ทั้งที่ชื่อวิชา/หน่วยกิตอ่านออกชัดเจน)
CODE_RE = re.compile(r"^(\d{8})\)?\s+(.+?)\s*(\d+\s*\(\d+-\d+-\d+\))\s*$")
# "วท.บ" ไม่ใช่ "วท.บ." เสมอไป — DSBA เขียน "วท.บ (วิทยาการข้อมูล...)" ไม่มีจุด ตัดจุดออกกันพลาด
# "นักศึกษา..." คือประโยคอธิบายกติกาเลือกวิชา (เจอซ้ำๆ ทั้ง 3 เล่ม เช่น "นักศึกษาเลือกลงทะเบียน...",
# "นักศึกษาสามารถเลือกเรียน...") ไม่ใช่ส่วนของชื่อวิชา ต้องข้ามไปด้วย ไม่งั้นหลุดไปต่อท้าย name_en
# ของวิชาสุดท้ายในกลุ่มก่อนหน้า (เจอจริงกับ DSBA "06026258")
SKIP_PREFIXES = ("รหัสวิชา", "วท.บ", "คณะ", "---", "นักศึกษา")
# หยุดทันทีที่เจอ "หัวข้อ" ของโซนที่ไม่ใช่วิชาเลือกแบบที่ wildcard อื่นชี้ถึง (เลือกเสรี/สหกิจศึกษา/
# โมดูลอาชีพแนะนำของ IT ซึ่งเป็นแค่ subset ของวิชาที่ดึงมาแล้วซ้ำ ไม่ใช่วิชาใหม่)
# ต้อง anchor ที่ต้นบรรทัด (เว้นได้แค่ prefix สั้นๆ แบบ "ก." "A," "-") ห้ามใช้ substring เปล่าๆ
# เพราะเคยเจอ false positive จริง — DSBA มีประโยคบรรยาย "...ไม่เข้าร่วมโครงการสหกิจศึกษา" ที่มีคำว่า
# "สหกิจศึกษา" ปนอยู่กลางประโยค ทำให้ตัดจบเร็วเกินไปก่อนถึงกลุ่มวิชาเลือกจริงที่อยู่ถัดไป
STOP_HEADER_RE = re.compile(
    r"^(?:[ก-ฮ0-9A-Za-z][.,]\s*)?-?\s*"
    r"(หมวดวิชาเลือกเสรี|หมวดวิชาสหกิจศึกษา|สหกิจศึกษา|โมดูลอาชีพ)")


def extract_page_range(text: str, start_page: int, end_page: int) -> str:
    """ตัดข้อความเฉพาะช่วงหน้า [start_page, end_page] จากไฟล์ OCR เต็มเล่ม (marker "--- Page N ---")"""
    spans = {int(m.group(1)): m for m in PAGE_RE.finditer(text)}
    if start_page not in spans:
        raise ValueError(f"ไม่เจอ marker หน้า {start_page} ในไฟล์นี้")
    start = spans[start_page].end()
    after = end_page + 1
    end = spans[after].start() if after in spans else len(text)
    return text[start:end]


def parse_groups(block: str) -> list[dict]:
    """แยกข้อความ catalog เป็นลิสต์กลุ่มวิชา แต่ละกลุ่มมีรายวิชา (code, name_th, name_en, credits)

    รับมือ 2 เคส OCR ที่เจอจริง: (1) ชื่อกลุ่มภาษาอังกฤษวงเล็บ wrap ขึ้นบรรทัดใหม่
    เช่น "ระบบระดับองค์กร (Enterprise System, Business Process\\nImprovement)"
    (2) ชื่อวิชาภาษาอังกฤษ wrap หลายบรรทัด เช่น "INTRODUCTION TO COMPUTER NETWORK AND\\nCYBERSECURITY"
    """
    groups: list[dict] = []
    current: dict | None = None
    pending_group_header: tuple[int, str] | None = None
    pending_course: dict | None = None

    def flush_course() -> None:
        nonlocal pending_course
        if pending_course and current is not None:
            current["courses"].append(pending_course)
        pending_course = None

    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(SKIP_PREFIXES) or line.startswith("มคอ.") or re.fullmatch(r"\d{1,3}", line):
            continue
        if STOP_HEADER_RE.match(line):
            break  # หมดโซนวิชาเลือกแล้ว (ต่อด้วยหมวดวิชาเลือกเสรี/สหกิจศึกษา ไม่ใช่ของกลุ่มนี้)

        m = GROUP_RE.match(line)
        if m:
            flush_course()
            name = m.group(2)
            if "(" in name and ")" not in name:
                pending_group_header = (int(m.group(1)), name)
                continue
            paren = re.search(r"\(([^)]*)\)\s*$", name)
            name_th = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
            current = {"group_no": int(m.group(1)), "name_th": name_th,
                       "name_en": paren.group(1).strip() if paren else None,
                       "courses": []}
            groups.append(current)
            continue

        if pending_group_header:
            no, partial = pending_group_header
            full = partial + " " + line
            close = full.find(")")
            name_th = re.sub(r"\s*\(.*$", "", full).strip()
            name_en = full[full.find("(") + 1:close].strip() if close != -1 else None
            current = {"group_no": no, "name_th": name_th, "name_en": name_en, "courses": []}
            groups.append(current)
            pending_group_header = None
            continue

        # กลุ่มไม่มีเลข "ที่ N" กำกับ (AIT: กลุ่มเดียว, DSBA: หลายกลุ่มขึ้นต้น "-") — สร้างกลุ่มใหม่
        # ทุกครั้งที่เจอหัวข้อแบบนี้ เรียง group_no ตามลำดับที่เจอเอง
        sm = SECTION_RE.match(line)
        if sm:
            flush_course()
            current = {"group_no": len(groups) + 1, "name_th": sm.group(1).strip(),
                       "name_en": None, "courses": []}
            groups.append(current)
            continue

        cm = CODE_RE.match(line)
        if cm:
            flush_course()
            name_th = re.sub(r"[»«|]+\s*$", "", cm.group(2)).strip()  # ล้างอักขระ OCR แปลกปลอมท้ายชื่อ
            pending_course = {"code": cm.group(1), "name_th": name_th,
                               "name_en": None, "credits": cm.group(3)}
            continue

        if pending_course is not None:
            # ชื่อไทยบางวิชาตัดขึ้นบรรทัดใหม่กลางคำ (เจอจริงกับ DSBA 06026225) — ถ้าบรรทัดถัดมา
            # มีอักษรไทยและยังไม่เจอชื่ออังกฤษเลย ถือว่าเป็นส่วนต่อของชื่อไทย ต่อแบบไม่เว้นวรรค
            # (คำเดียวกันถูกตัดพอดี) แทนที่จะไปเป็นชื่ออังกฤษผิดๆ
            if pending_course["name_en"] is None and re.search(r"[ก-๙]", line):
                pending_course["name_th"] += line
            elif pending_course["name_en"] is None:
                pending_course["name_en"] = line
            else:
                pending_course["name_en"] += " " + line
            continue

    flush_course()
    # กลุ่มจริงต้องมีวิชาอย่างน้อย 1 วิชาเสมอ — กลุ่มว่างมาจากได้ 2 ทาง: (1) หัวข้อปลอม เช่น
    # ประโยคบรรยายที่ตัดขึ้นบรรทัดใหม่พอดีจนหน้าตาเหมือนหัวข้อกลุ่ม (เจอจริงกับ DSBA) (2) หัวข้อ
    # หมวดใหญ่ที่ไม่มีวิชาเลือกได้ตรงๆ ของตัวเอง แค่รวมกลุ่มย่อยไว้ข้างใน (เช่น DSBA
    # "3) กลุ่มวิชาชีพเฉพาะด้าน" ตามด้วย "-" กลุ่มย่อยทันที) — กรองทิ้งแล้วเรียงเลขกลุ่มใหม่ให้
    # ต่อเนื่อง 1..N (ไม่งั้นจะมีรอยขาดเช่น 2,3,4,6 จากกลุ่มว่างที่ถูกกรองไปแล้ว)
    kept = [g for g in groups if g["courses"]]
    for i, g in enumerate(kept, start=1):
        g["group_no"] = i
    return kept


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True, help="ไฟล์ OCR เต็มเล่ม (มี marker '--- Page N ---')")
    parser.add_argument("--start-page", type=int, required=True)
    parser.add_argument("--end-page", type=int, required=True)
    parser.add_argument("--program", required=True, help="เช่น BIT")
    parser.add_argument("--plan-slot", required=True,
                        help="ชื่อช่องในตารางแผนที่ wildcard นี้แทนอยู่ เช่น "
                             "'วิชาเลือกทางเทคโนโลยีสารสนเทศทางธุรกิจ 1/2 (ปี 4/2, รหัส 06036xxx)'")
    parser.add_argument("--credits-required", type=int, required=True)
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    text = Path(args.text).read_text(encoding="utf-8")
    block = extract_page_range(text, args.start_page, args.end_page)
    groups = parse_groups(block)

    n_courses = sum(len(g["courses"]) for g in groups)
    result = {
        "program": args.program,
        "source": f"{args.text} หน้า {args.start_page}-{args.end_page}",
        "plan_slot": args.plan_slot,
        "credits_required": args.credits_required,
        "groups": groups,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  พบ {len(groups)} กลุ่ม, {n_courses} วิชา")
    for g in groups:
        print(f"    กลุ่มที่ {g['group_no']}: {g['name_th']} ({g['name_en']}) — {len(g['courses'])} วิชา")
    print(f"  เขียน {out}")


if __name__ == "__main__":
    main()
