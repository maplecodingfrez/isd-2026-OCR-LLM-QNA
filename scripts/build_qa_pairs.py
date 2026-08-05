"""
Lab 5 - Q&A pairs answerable from the DSBA (coop) ground truth
(data/ground_truth/DSBA_academic_plan_coop.json), each answer citing the PDF
page(s) in data/input/dsba_curriculum.pdf that the fact came from.

Two buckets:
  - "course": answerable directly from the ground truth / outputs/course_page_mapping.csv
    (built by scripts/build_page_mapping.py).
  - "regulation": answerable from the institute-wide "ข้อบังคับสถาบันฯ ว่าด้วยการศึกษา
    ระดับปริญญาตรี" appendix, which is bound into the same curriculum book
    (found by grepping the OCR text for "ข้อบังคับ" -- see README Lab 5 section).
    OCR quality on these appendix pages is noticeably worse than the course
    tables (garbled Thai numerals, stray Latin letters), so only facts that
    were clearly legible in the raw text were kept.

Page numbers = physical page order in data/input/dsba_curriculum.pdf
(1-indexed), same convention as outputs/dsba_curriculum_ocr.json and
outputs/course_page_mapping.csv -- NOT the printed page number shown in the
document body (which runs about 1 page behind the PDF index).

Run: python scripts/build_qa_pairs.py
"""

import csv
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "outputs" / "qa_pairs.csv"

QA_PAIRS = [
    # ---------- course-level (from data/ground_truth/DSBA_academic_plan_coop.json) ----------
    {
        "type": "course",
        "program": "DSBA",
        "question": "รหัสวิชา 06026211 ชื่อวิชาอะไร และมีหน่วยกิตเท่าไหร่?",
        "answer": "การเรียนรู้ของเครื่องเชิงประยุกต์ (APPLIED MACHINE LEARNING) 3(2-2-5) หน่วยกิต",
        "cited_pages": "18;323",
        "note": "ground truth: code 06026211",
    },
    {
        "type": "course",
        "program": "DSBA",
        "question": "วิชา 90641001 CHARM SCHOOL มีกี่หน่วยกิต และพบข้อมูลอยู่กี่หน้าในเล่มหลักสูตร?",
        "answer": (
            "2(1-2-3) หน่วยกิต พบใน 4 หน้า (16, 123, 125, 234) เพราะเป็นวิชาศึกษาทั่วไปที่ปรากฏซ้ำ"
            "ในตารางหลักสูตรของหลายสาขา ไม่ใช่แค่ DSBA"
        ),
        "cited_pages": "16;123;125;234",
        "note": "ground truth: code 90641001",
    },
    {
        "type": "course",
        "program": "DSBA",
        "question": "วิชา 06026225 ชื่อเต็มภาษาอังกฤษคืออะไร และโครงสร้างหน่วยกิต 3(2-2-5) แปลว่าอะไร?",
        "answer": (
            "DEEP LEARNING IN MEDICAL IMAGE AND VIDEO ANALYSIS -- 3 หน่วยกิต คือ บรรยาย 2 ชม. / "
            "ปฏิบัติ 2 ชม. / ศึกษาด้วยตนเอง 5 ชม. ต่อสัปดาห์"
        ),
        "cited_pages": "19;329",
        "note": "ground truth: code 06026225",
    },
    {
        "type": "course",
        "program": "DSBA",
        "question": "วิชา 06026209 คือวิชาอะไร และต้องลงทะเบียนเรียนปีไหน เทอมไหน?",
        "answer": "การแสดงข้อมูลด้วยแผนภาพ (DATA VISUALIZATION) เรียนปี 2 เทอม 2",
        "cited_pages": "18;26;322",
        "note": "ground truth: code 06026209",
    },
    {
        "type": "course",
        "program": "DSBA",
        "question": "รหัสวิชา 06026212 ต้องผ่านวิชาอะไรมาก่อนถึงจะลงทะเบียนได้?",
        "answer": "ต้องผ่านวิชา 06066300 มาก่อน (prerequisite) -- 06026212 คือ การสร้างคลังข้อมูล (DATA WAREHOUSING)",
        "cited_pages": "18;323",
        "note": "ground truth: code 06026212, field 'prerequisite'",
    },
    {
        "type": "course",
        "program": "DSBA",
        "question": "การจะเรียนวิชารหัส 06026201 ได้ ต้องเรียนวิชาใดมาก่อน?",
        "answer": "ต้องผ่านวิชา 06026200 (แคลคูลัส 1 / CALCULUS 1) มาก่อน -- 06026201 คือ แคลคูลัส 2 (CALCULUS 2)",
        "cited_pages": "17;31;314",
        "note": "ground truth: code 06026201, field 'prerequisite'",
    },
    {
        "type": "course",
        "program": "DSBA",
        "question": "วิชาใดบ้างที่ต้องเรียนในปี 1 เทอม 1?",
        "answer": (
            "8 วิชา: 06016401 (คณิตศาสตร์สำหรับเทคโนโลยีสารสนเทศ), 06026200 (แคลคูลัส 1), "
            "06026202 (พีชคณิตเชิงเส้น), 06066101 (พื้นฐานทางธุรกิจสำหรับเทคโนโลยีสารสนเทศ), "
            "06066303 (การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์), 90641001 (CHARM SCHOOL), "
            "90641003 (กีฬาและนันทนาการ), 90644007 (ภาษาอังกฤษพื้นฐาน 1) -- ทุกวิชายกเว้น 06016401 "
            "มีหน้าอ้างอิงในตารางหลักสูตรโดยตรง ส่วน 06016401 ไม่พบรหัสในตารางเลย พบเพียงชื่อวิชาในหน้า"
            "ภาระงานสอนอาจารย์ (หน้า 49, ไม่ใช่หลักฐานยืนยันด้วยรหัส)"
        ),
        "cited_pages": "16;17;18;23;30;123;125;136;151;234;273;314;315;317;319;49(name-only)",
        "note": "ground truth: filtered by year=1, semester=1",
    },
    {
        "type": "course",
        "program": "DSBA",
        "question": "ในแต่ละปี มีวิชาหมวดวิชาเฉพาะกับหมวดวิชาศึกษาทั่วไปอย่างละกี่วิชา?",
        "answer": (
            "ปี 1: เฉพาะ 9 / ทั่วไป 6 | ปี 2: เฉพาะ 12 / ทั่วไป 0 | ปี 3: เฉพาะ 5 / ทั่วไป 2 | "
            "ปี 4: เฉพาะ 1 / ทั่วไป 0 -- นอกจากนี้มีวิชาเลือก 45 วิชา (หมวดวิชาเฉพาะทั้งหมด) ที่ไม่ผูกกับ"
            "ปีตายตัว เลือกลงได้ตามเงื่อนไข flexible_year_semester ของแต่ละวิชา"
        ),
        "cited_pages": "15",
        "note": "ground truth: aggregated by year + category; หน้า 15 มีตารางโครงสร้างหลักสูตรโดยรวม",
    },
    {
        "type": "course",
        "program": "DSBA",
        "question": "หลักสูตร DSBA มีวิชาบังคับกับวิชาเลือกอย่างละกี่วิชา?",
        "answer": "วิชาบังคับ 35 วิชา, วิชาเลือก 45 วิชา (รวม 80 วิชาตาม ground truth)",
        "cited_pages": "15",
        "note": "ground truth: aggregated by field 'type'",
    },
    {
        "type": "course",
        "program": "DSBA",
        "question": "มีวิชาที่เกี่ยวกับ Machine Learning หรือ AI โดยตรงกี่วิชา อะไรบ้าง?",
        "answer": (
            "6 วิชา: Applied Machine Learning (06026211), Artificial Intelligence (06026216), "
            "Machine Learning (06026217), Deep Learning (06026218), "
            "Deep Learning in Medical Image and Video Analysis (06026225), "
            "Machine Learning Operations (06026241)"
        ),
        "cited_pages": "18;19;21;323;325;326;329;334",
        "note": "ground truth: filtered by keyword in name_en",
    },
    # ---------- regulation-level (ข้อบังคับสถาบันฯ ว่าด้วยการศึกษาระดับปริญญาตรี, ภาคผนวกในเล่มเดียวกัน) ----------
    {
        "type": "regulation",
        "program": "DSBA",
        "question": "หลักสูตร DSBA มีจำนวนหน่วยกิตรวมตลอดหลักสูตรเท่าไหร่?",
        "answer": "132 หน่วยกิต (ข้อ 3.1.1 -- ใช้ร่วมกันทั้งแผนที่เข้าและไม่เข้าร่วมโครงการสหกิจศึกษา)",
        "cited_pages": "15",
        "note": "หัวข้อ 3. หลักสูตรและอาจารย์ผู้สอน / 3.1.1 จำนวนหน่วยกิตรวมตลอดหลักสูตร",
    },
    {
        "type": "regulation",
        "program": "DSBA",
        "question": "นักศึกษาที่มีค่าระดับคะแนนเฉลี่ยสะสม (GPA) ต่ำกว่าเท่าไหร่ ต้องถูกภาคทัณฑ์?",
        "answer": "ต่ำกว่า 2.00 ต้องถูกภาคทัณฑ์ (ข้อ 22) และจะพ้นภาคทัณฑ์เมื่อ GPA สะสมไม่ต่ำกว่า 2.00 อีกครั้ง",
        "cited_pages": "94",
        "note": "ข้อบังคับสถาบันฯ ว่าด้วยการศึกษาระดับปริญญาตรี พ.ศ. 2564 (ภาคผนวก ก)",
    },
    {
        "type": "regulation",
        "program": "DSBA",
        "question": "นักศึกษาที่ต้องการลาพักการศึกษา ต้องดำเนินการอย่างไร?",
        "answer": (
            "ต้องได้รับความเห็นชอบจากคณะกรรมการประจำส่วนงานวิชาการ และแจ้งสำนักทะเบียนฯ ระยะเวลาที่ลาพัก"
            "นับรวมในระยะเวลาการศึกษาตามหลักสูตรด้วย และต้องชำระค่าธรรมเนียมรักษาสถานภาพนักศึกษาทุก"
            "ภาคการศึกษาปกติ (ข้อ 31)"
        ),
        "cited_pages": "96",
        "note": "ข้อบังคับสถาบันฯ ข้อ 31 การลาพักการศึกษา",
    },
    {
        "type": "regulation",
        "program": "DSBA",
        "question": "นักศึกษาที่พ้นสภาพการเป็นนักศึกษา จะขอกลับเข้าศึกษาใหม่ได้ในเงื่อนไขแบบไหน?",
        "answer": (
            "ยื่นคำร้องขอกลับเข้าศึกษาได้ในบางกรณี โดยอธิการบดีเป็นผู้อนุมัติ (ผ่านความเห็นชอบหัวหน้าส่วนงาน"
            "วิชาการ) ต้องไม่เกิน 1 ปีนับจากวันที่พ้นสภาพ และไม่ขัดกับระยะเวลาการศึกษาสูงสุดของหลักสูตร (ข้อ 32)"
        ),
        "cited_pages": "97",
        "note": "ข้อบังคับสถาบันฯ ข้อ 32 -- OCR หน้านี้คุณภาพต่ำ (เลขไทยอ่านยาก) ใช้เฉพาะส่วนที่ชัดเจน",
    },
    {
        "type": "regulation",
        "program": "DSBA",
        "question": "รายวิชาสหกิจศึกษาของแผน coop สาขา DSBA มีรหัสอะไรบ้าง และมีกี่หน่วยกิต?",
        "answer": (
            "06026259 สหกิจศึกษาทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ (ในประเทศ) หรือ 06026260 "
            "สหกิจศึกษาต่างประเทศฯ -- เลือกลงทะเบียนวิชาใดวิชาหนึ่ง รวม 6 หน่วยกิต ทั้งสองวิชาเป็น "
            "6(0-35-0) คือไม่มีชั่วโมงบรรยาย ฝึกปฏิบัติ 35 ชม./สัปดาห์"
        ),
        "cited_pages": "22",
        "note": "ตารางหลักสูตร แผนสหกิจศึกษา (ไม่ใช่ข้อบังคับสถาบันฯ โดยตรง แต่เป็นเกณฑ์เฉพาะหลักสูตร)",
    },
    {
    "type": "regulation",
    "program": "DSBA",
    "question": "นักศึกษา DSBA ต้องมี GPA เท่าไหร่ถึงจะได้เกียรตินิยม?",
    "answer": "เกียรตินิยมอันดับ 1 เหรียญทอง: GPA ตั้งแต่ 3.75 ขึ้นไป | เกียรตินิยมอันดับ 1: GPA ตั้งแต่ 3.50 ขึ้นไป | เกียรตินิยมอันดับ 2: ไม่มีค่าระบุในฐานข้อมูล (ต้องตรวจสอบเพิ่ม)",
    "cited_pages": "",
    "note": "ground truth: rules_ground_truth.json, program DSBA, category 'เกณฑ์เกียรตินิยม' -- ค่า GPA อันดับ 2 เป็น null ในไฟล์ต้นทาง ยังไม่มีข้อมูล",

    },
    {
    "type": "regulation",
    "program": "DSBA",
    "question": "นักศึกษา DSBA ลงทะเบียนได้กี่หน่วยกิตในภาคการศึกษาปกติ?",
    "answer": "ขั้นต่ำ 9 หน่วยกิต สูงสุด 22 หน่วยกิต (กรณีพิเศษมีเพดานสูงกว่านี้ แต่ไม่มีค่าระบุในฐานข้อมูล)",
    "cited_pages": "",
    "note": "ground truth: rules_ground_truth.json, program DSBA, category 'เกณฑ์การลงทะเบียน' -- ค่า 'หน่วยกิตสูงสุดกรณีพิเศษ' เป็น null ในไฟล์ต้นทาง",
    },

    # ---------- AIT (rules_ground_truth.json) ----------
    {
        "type": "regulation",
        "program": "AIT",
        "question": "นักศึกษา AIT ต้องเรียนจบด้วยหน่วยกิตขั้นต่ำเท่าไหร่ และ GPA สะสมต้องไม่ต่ำกว่าเท่าไหร่?",
        "answer": "120 หน่วยกิต และ GPA สะสมต้องไม่ต่ำกว่า 2.00",
        "cited_pages": "",
        "note": "ground truth: rules_ground_truth.json, program AIT, category 'เกณฑ์การสำเร็จการศึกษา'",
    },
    {
        "type": "regulation",
        "program": "AIT",
        "question": "นักศึกษา AIT ต้องมี GPA เท่าไหร่ถึงจะได้เกียรตินิยม?",
        "answer": "เหรียญทอง: ตั้งแต่ 3.75 ขึ้นไป | อันดับ 1: ตั้งแต่ 3.50 ขึ้นไป | อันดับ 2: ไม่มีค่าระบุในไฟล์ต้นทาง",
        "cited_pages": "",
        "note": "ground truth: rules_ground_truth.json, program AIT, category 'เกณฑ์เกียรตินิยม' -- GPA อันดับ 2 เป็น null",
    },
    {
        "type": "regulation",
        "program": "AIT",
        "question": "นักศึกษา AIT ลงทะเบียนได้กี่หน่วยกิตในภาคการศึกษาปกติ?",
        "answer": "ขั้นต่ำ 9 หน่วยกิต สูงสุด 22 หน่วยกิต (กรณีพิเศษไม่มีค่าระบุในไฟล์ต้นทาง)",
        "cited_pages": "",
        "note": "ground truth: rules_ground_truth.json, program AIT, category 'เกณฑ์การลงทะเบียน' -- เพดานกรณีพิเศษเป็น null",
    },

    {
        "type": "course",
        "program": "AIT",
        "question": "รหัสวิชา 06046400 ของ AIT ชื่อวิชาอะไร และมีหน่วยกิตเท่าไหร่?",
        "answer": "แคลคูลัส 1 (CALCULUS 1) 3(3-0-6) หน่วยกิต",
        "cited_pages": "19;23;287",
        "note": "ground truth: code 06046400",
    },

    {
        "type": "course",
        "program": "AIT",
        "question": "วิชา 06066001 PROBABILITY AND STATISTICS ของ AIT มีหน่วยกิตเท่าไหร่ และพบข้อมูลอยู่หน้าไหนบ้าง?",
        "answer": "ความน่าจะเป็นและสถิติ 3(3-0-6) หน่วยกิต พบใน 3 หน้า",
        "cited_pages": "19;23;289",
        "note": "ground truth: code 06066001",
    },

    # ---------- IT (rules_ground_truth.json) ----------
    {
        "type": "regulation",
        "program": "IT",
        "question": "นักศึกษา IT ต้องเรียนจบด้วยหน่วยกิตขั้นต่ำเท่าไหร่ และเงื่อนไข GPA คืออะไร?",
        "answer": "129 หน่วยกิต เรียนครบหน่วยกิตและสอบผ่านทุกรายวิชา และคะแนนเฉลี่ยสะสมต้องไม่ต่ำกว่า 2.00",
        "cited_pages": "",
        "note": "ground truth: rules_ground_truth.json, program IT, category 'เกณฑ์การสำเร็จการศึกษา' (มี summary ระบุไว้ในไฟล์ต้นทางด้วย)",
    },
    {
        "type": "regulation",
        "program": "IT",
        "question": "นักศึกษา IT ต้องมี GPA เท่าไหร่ถึงจะได้เกียรตินิยม?",
        "answer": "เหรียญทอง: ตั้งแต่ 3.75 ขึ้นไป | อันดับ 1: ตั้งแต่ 3.50 ขึ้นไป | อันดับ 2: ตั้งแต่ 3.25 ขึ้นไป",
        "cited_pages": "",
        "note": "ground truth: rules_ground_truth.json, program IT, category 'เกณฑ์เกียรตินิยม' -- ไฟล์นี้มีค่าครบทั้ง 3 อันดับ ไม่มี null",
    },
    {
        "type": "regulation",
        "program": "IT",
        "question": "นักศึกษา IT ลงทะเบียนได้กี่หน่วยกิตในภาคการศึกษาปกติ และกรณีพิเศษเป็นอย่างไร?",
        "answer": "ขั้นต่ำ 9 สูงสุด 22 หน่วยกิตในภาคปกติ หากลงทะเบียนตั้งแต่ 27 หน่วยกิตขึ้นไปต้องขออนุมัติเป็นกรณีพิเศษ",
        "cited_pages": "",
        "note": "ground truth: rules_ground_truth.json, program IT, category 'เกณฑ์การลงทะเบียน'",
    },

     {
        "type": "course",
        "program": "IT",
        "question": "รหัสวิชา 06016402 ของ IT ชื่อวิชาอะไร และมีหน่วยกิตเท่าไหร่?",
        "answer": "พื้นฐานทางด้านเทคโนโลยีสารสนเทศ (INFORMATION TECHNOLOGY FUNDAMENTALS) 3(2-2-5) หน่วยกิต",
        "cited_pages": "23;38;324",
        "note": "ground truth: code 06016402",
    },

    {
        "type": "course",
        "program": "IT",
        "question": "วิชา 06066303 PROBLEM SOLVING AND COMPUTER PROGRAMMING ของ IT มีหน่วยกิตเท่าไหร่ และพบข้อมูลอยู่หน้าไหนบ้าง?",
        "answer": "การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์ 3(2-2-5) หน่วยกิต พบใน 3 หน้า",
        "cited_pages": "24;38;359",
        "note": "ground truth: code 06066303",
    },
]


def write_qa_csv(rows: list[dict], output_path: Path = OUTPUT_PATH) -> None:
    fields = ["type", "program", "question", "answer", "cited_pages", "note"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    write_qa_csv(QA_PAIRS)
    n_course = sum(1 for r in QA_PAIRS if r["type"] == "course")
    n_reg = sum(1 for r in QA_PAIRS if r["type"] == "regulation")
    print(f"Saved {len(QA_PAIRS)} Q&A pairs ({n_course} course, {n_reg} regulation) -> {OUTPUT_PATH}")
