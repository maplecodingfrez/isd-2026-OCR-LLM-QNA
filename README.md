# isd-2026-OCR-LLM-QNA
> OCR เล่มหลักสูตร เพื่อตอบคำถามเกี่ยวกับการเรียน

> **Branch นี้ (`Lab-8b-prereq`) เก็บเฉพาะงานที่เพิ่มต่อจาก Lab 7B / 8B / 9** ได้แก่ (1) ตัวประเมินที่จับคู่แถววิชาเลือก (wildcard) และ
> (2) การสกัดวิชาบังคับก่อน (`prerequisite`) จากข้อความ OCR ของเล่ม ระบบเต็มที่รวมทุก Lab พร้อมวิธีติดตั้ง/ใช้งาน ดูที่ branch `main`

## Members
* 67070168 - film_synthesis
* 67070185 - 17decc
* 67070195 - zvacia

---

## สิ่งที่เพิ่มใน branch นี้

| เรื่อง | ไฟล์หลัก |
|---|---|
| ตัวประเมินจับคู่ wildcard | `Lab8b_ocr_system/src/ocr_system/lab7b_curriculum.py` (`match_wildcards`), `Lab8b_ocr_system/regenerate_evaluation.py` |
| ตัวสกัดวิชาบังคับก่อนจากข้อความ OCR | `Lab8b_ocr_system/src/ocr_system/prereq_from_book.py` |
| โหลดเข้า DB (`load-prerequisites`, ตาราง `prerequisite_alt`) | `Lab8b_ocr_system/src/ocr_system/lab8b_curriculum_db.py` |
| คำถามทอง "มีคู่ prerequisite กี่คู่" คำนวณจากเฉลย | `Lab9_evaluation/gold_questions/build_gold_questions.py` |
| ชุดทดสอบ + ผลทดลอง | `Lab8b_ocr_system/experiments/wildcard_pass_2026-09-21/`, `.../prereq_from_book_ocr_2026-09-21/` |
| บันทึกทุกขั้นตอน | `Lab8b_ocr_system/PROGRESS.md` |

(โฟลเดอร์ `lab10_fastapi/` อยู่ใน branch นี้ด้วย ดูวิธีใช้ที่ `lab10_fastapi/README.md`)

---

## 1. ประเมินผล: จับคู่แถววิชาเลือก (wildcard)

**ปัญหา:** แถววิชาเลือกที่เล่มเขียนเป็นรหัส wildcard (เช่น `06036xxx`) Lab 7B คืนปี/ภาค = 0/0 โดยออกแบบ แต่เฉลย scoped มีปี/ภาคจริง
กุญแจจับคู่ `รหัส|ปี|ภาค` จึงไม่มีทางตรง แถวเดียวกันถูกนับซ้ำเป็นทั้ง "ตก" และ "เกิน" ทั้งที่ OCR อ่านเจอ

**แก้:** หลังจับคู่กุญแจเดิมแล้ว `match_wildcards` จับคู่แถว wildcard ที่เหลือด้วยความคล้ายของชื่อไทย (greedy, ≥ 0.6)
โดยปฏิเสธคู่ที่เลขท้ายชื่อต่างกัน, ปี/ภาคที่ระบุชัดทั้งสองฝั่งไม่ตรง, หรือชื่อสั้นกว่า 6 ตัวอักษร (ไม่ใช้ containment)
ตัวเลขแบบเดิมยังเก็บไว้ที่ `alignment.strict` ข้างตัวเลขใหม่

**ผล (P / R / F1; OCR เดิมทุกไฟล์ ความต่างคือวิธีวัดอย่างเดียว):**

| แผน | strict | wildcard-aware |
|---|---|---|
| AIT | 0.838 / 0.775 / 0.805 | 0.946 / 0.875 / 0.909 |
| BIT no-coop | 0.905 / 0.884 / 0.894 | 0.976 / 0.954 / 0.965 |
| BIT coop | 0.756 / 0.809 / 0.782 | 0.867 / 0.929 / 0.897 |
| DSBA no-coop | 0.635 / 0.733 / 0.680 | 0.827 / 0.956 / 0.887 |
| DSBA coop | 0.538 / 0.795 / 0.642 | 0.677 / 1.000 / 0.807 |
| IT no-coop | 0.796 / 0.722 / 0.757 | 0.918 / 0.833 / 0.874 |
| IT coop | 0.709 / 0.736 / 0.722 | 0.800 / 0.830 / 0.815 |

ทุกคู่ที่จับเพิ่มถูกตรวจด้วยตาแล้ว: ชื่อตรงกัน ต่างแค่รหัสที่ OCR เพี้ยน

**ที่ยังผิดจริง (ไม่ปิดบัง):** DSBA coop มีแถวเกิน (หน้าแคตตาล็อกนอกแผน), DSBA `06026xxx` ที่เฉลยรวมหลายกลุ่มเป็นแถวเดียวแต่ OCR แยกทีละกลุ่ม,
และกลุ่มวิชาเลือกเฉพาะด้านของ IT ที่ยังตก/รวมเซลล์

```bash
cd Lab8b_ocr_system
python regenerate_evaluation.py                    # 7 แผนหลัก
python regenerate_evaluation.py ait_dewm5 ait_dewm6  # ระบุรอบเอง
python experiments/wildcard_pass_2026-09-21/test_wildcard_pass.py   # ชุดทดสอบ 13 ข้อ
```

---

## 2. วิชาบังคับก่อน (prerequisite)

**ที่มา:** Lab 7B ไม่สกัดฟิลด์นี้โดยตั้งใจ (หน้าแผนการเรียนไม่มีคอลัมน์นี้ และโมเดลเคยเดาเอง) ข้อมูลจริงอยู่ที่หน้า "3.4 คำอธิบายรายวิชา"
(`วิชาบังคับก่อน : <รหัส> <ชื่อ>`) ซึ่งเรามีข้อความ OCR ทั้งเล่มจาก Lab 4–6 อยู่แล้ว (`outputs/<หลักสูตร>/*_curriculum_ocr.txt`)

**ตัวสกัด `prereq_from_book.py`:** กฎล้วน ไม่เรียก LLM ไม่ใช้เฉลย และ **ไม่เดา** — หาหัวรายวิชาแล้วอ่านบรรทัด "วิชาบังคับก่อน" ของวิชานั้น
รวมบรรทัดต่อ ("หรือ/และ") ตรวจซ้ำกับบรรทัด PREREQUISITE ภาษาอังกฤษ แต่ละวิชาได้สถานะ `found` / `none` / `not_found` / `unreadable`
(`not_found`/`unreadable` = ไม่ทราบ ไม่ใช่ "ไม่มี" จึงไม่มีแถวในตาราง)

**ตรวจกับเล่มจริง:** ในแถวที่อ่านได้ 200 แถวตรงเฉลย 200/200 (หลังแก้เฉลย) — ส่วนอีก 42 แถวอ่านไม่ได้ เกือบทั้งหมดเป็นวิชาศึกษาทั่วไปที่ไม่มีหัวรายวิชาแบบภาคผนวก
เปิดภาพเล่มตรวจ 6 แถวที่เฉลยเดิมไม่ตรง พบว่าเฉลยเดิมผิด จึงแก้ใน `Lab9_evaluation/ground_truth_scoped/` (AIT 2, IT no-coop 2, IT coop 2; ต้นฉบับก่อนแก้เก็บไว้ที่
`Lab8b_ocr_system/experiments/prereq_from_book_ocr_2026-09-21/before_gt/`)

**"A หรือ B":** ตาราง `prerequisite` เก็บเป็นสองแถว `kind='pre'` และระบุว่าเป็นทางเลือกกันในตารางเสริม `prerequisite_alt(code, requires, group_no)`
(แถวของวิชาเดียวกันที่ `group_no` เดียวกัน = ผ่านอย่างใดอย่างหนึ่งก็พอ) ตารางเสริมนี้ **แยกจาก DDL หลักโดยตั้งใจ** เพราะ DDL หลักถูกยัดเข้า prompt ของ NL2SQL
การแก้จะเปลี่ยนคะแนนเดิม CHK5 (วิชาบังคับก่อนอยู่ภาคก่อน) รู้จักกลุ่ม "หรือ" ด้วย

**ผลรัน 7 แผน (`--skip-lab7`):** SQL รันผ่าน 29/30 ทุกแผน

| แผน | ตอบถูก NL2SQL | คู่ในตาราง | คำตอบทอง "กี่คู่" | ข้อ "กี่คู่" |
|---|---|---|---|---|
| AIT | 20/30 | 5 | 6 | ผิด |
| BIT no-coop | 26/30 | 3 | 3 | ถูก |
| BIT coop | 26/30 | 2 | 2 | ถูก |
| DSBA no-coop | 27/30 | 5 | 5 | ถูก |
| DSBA coop | 27/30 | 5 | 5 | ถูก |
| IT no-coop | 24/30 | 5 | 8 | ผิด |
| IT coop | 22/30 | 5 | 8 | ผิด |

AIT/IT ตกข้อ "กี่คู่" เพราะคำตอบทองคำนวณจากเฉลย (ครบ) แต่ตารางได้เฉพาะวิชาที่ตัวสกัดอ่านเจอ (เช่น AIT `90641005` อ่านไม่ออกเพราะ `90641004` หายไปกับตราน้ำ)
ส่วนรอบ `AIT_dewm1–6` (ตัดตราน้ำก่อน OCR) ได้ 6 คู่ ตรงคำตอบทอง

```bash
cd Lab8b_ocr_system
# รัน Lab 8B ต่อจากผล OCR เดิมของแผนหนึ่ง (ขั้น load-prerequisites อยู่ในสคริปต์อยู่แล้ว)
PYTHONUTF8=1 python run_lab8b_ait.py --skip-lab7        # Windows: ตั้ง PYTHONUTF8=1 กัน UnicodeEncodeError เมื่อ pipe ผ่าน grep

# หรือเรียกขั้นเดียว
python src/ocr_system/lab8b_curriculum_db.py load-prerequisites \
    -t ../outputs/ait/ait_curriculum_ocr.txt -d runs/AIT/lab8b_output/curriculum.db \
    -o runs/AIT/lab8b_output/prerequisites_report.json

# ชุดทดสอบ
python experiments/prereq_from_book_ocr_2026-09-21/test_prereq_from_book.py   # 11 ข้อ
python experiments/prereq_from_book_ocr_2026-09-21/test_prereq_alt.py         # 6 ข้อ ("หรือ" + CHK5)
python src/ocr_system/lab8b_curriculum_db.py selftest                         # 24 ข้อ
```

**ข้อจำกัด:** ถามเรื่อง "หรือ" ผ่าน NL2SQL ไม่ได้ (ตารางเสริมไม่อยู่ใน prompt โดยตั้งใจ) · รองรับกลุ่ม "หรือ" ได้ 1 กลุ่มต่อวิชา (ยังไม่รองรับ "(A หรือ B) และ C") ·
วิชาที่หาหัวรายวิชาไม่เจอจะไม่มีแถวในตาราง

---

## ต้องมีอะไรก่อนรัน

Python 3.10+ และ `pip install pythainlp requests` (ยังไม่มี `requirements.txt` ครอบคลุม Lab 7B/8B) · Ollama พร้อมโมเดล `scb10x/typhoon-ocr1.5-3b` และ `qwen3:4b`
· รันจาก `--skip-lab7` ได้โดยไม่ต้อง OCR ใหม่ถ้ามี `pred_vlm.json` ใน `runs/<แผน>/lab7b_output/` แล้ว

วิธีติดตั้งเต็ม, Lab 3–9 และโครงสร้างโปรเจกต์ทั้งหมด → ดู branch `main`
