---

## Curriculum Extraction (Lab 4)

ทีมเลือกหัวข้อ **Curriculum Extraction** — ดึงข้อมูลรายวิชา (รหัสวิชา, ชื่อไทย, ชื่ออังกฤษ, หน่วยกิต) จากเอกสารเล่มหลักสูตร DSBA (PDF สแกน 403 หน้า) ด้วย OCR แล้ววัดผลเทียบกับ Ground Truth (`data/ground_truth/DSBA_academic_plan_coop.json`)

### Pipeline

```text
เล่มหลักสูตร (PDF, 403 หน้า)
    → OCR (Tesseract, image_to_string)
    → curriculum_extraction.py (ดึง code / name_th / name_en / credits)
    → evaluate_curriculum.py (เทียบกับ Ground Truth)
```

### วิธีรัน (ครบ pipeline ในคำสั่งเดียว)

```bash
# 1. OCR เล่มหลักสูตร
python -m ocr_system.cli ocr data/input/dsba_curriculum.pdf --engine tesseract --output-dir outputs

# 2. Extract + Evaluate ในคำสั่งเดียว
python -m ocr_system.cli curriculum outputs/dsba_curriculum_ocr.json \
    --ground-truth data/ground_truth/DSBA_academic_plan_coop.json
```

ผลลัพธ์ที่ได้:
```text
outputs/dsba_curriculum_courses.json           รายวิชาที่ดึงได้ทั้งหมด
outputs/dsba_curriculum_curriculum_evaluation.json   ผล evaluation เทียบกับ GT
```

### ทำไมต้องใช้ Tesseract แทน PaddleOCR

ลองทั้งสอง engine แล้วพบว่า:
- **PaddleOCR**: โมเดลภาษาไทยที่ดาวน์โหลดผ่าน `paddlex` มีปัญหาการอ่านภาษาไทยผิดเพี้ยน (อ่านออกมาเป็นตัวอักษรละตินมั่วๆ ทั้งที่ตั้ง `lang="th"` ถูกแล้ว) และการดาวน์โหลดโมเดลใหม่ค้างบ่อย (คาดว่า host ต้นทางไม่เสถียรสำหรับเครือข่ายในไทย)
- **Tesseract**: ใช้ `pytesseract.image_to_string()` (แทน `image_to_data()`) ให้ผลลัพธ์ภาษาไทยที่ถูกต้องและเสถียรกว่า จึงเลือกใช้เป็น engine หลักสำหรับงานนี้

หมายเหตุ: `image_to_data()` (word-level bounding box) ใช้ไม่ได้ดีกับภาษาไทย เพราะภาษาไทยไม่มีช่องว่างระหว่างคำ ทำให้ Tesseract ตรวจจับแต่ละตัวอักษรเป็น "คำ" แยกกัน ส่งผลให้ลำดับคำพังเมื่อพยายามต่อ (join) กลับเป็นประโยค `image_to_string()` ให้ Tesseract จัดการ line/word reconstruction เองภายใน จึงได้ผลลัพธ์ที่ถูกต้องกว่า

### ทำไมต้องมี `evaluate_curriculum.py` แยกจาก `evaluation.py`

`evaluation.py` เดิมออกแบบมาสำหรับวัด **CER/WER** โดยเทียบ OCR text กับ Ground Truth ที่เป็น **ข้อความก้อนเดียว** ต่อไฟล์ (`{"filename": "ข้อความเต็ม..."}`) — เหมาะกับเอกสารทั่วไปที่ไม่มีโครงสร้าง

แต่ Ground Truth ของ curriculum (`DSBA_academic_plan_coop.json`) เป็น **structured data**: list ของ course record ที่มี field ย่อย (`code`, `name_th`, `name_en`, `credits`, `year`, `semester`, ...) การเทียบแบบ CER/WER ทั้งก้อนใช้ไม่ได้ จึงต้องสร้าง `evaluate_curriculum.py` ที่วัดผลแบบ:

- **Recall** — ใน Ground Truth ทั้งหมด ดึงเจอกี่ % (match ด้วย course code)
- **Field-level agreement** — ในบรรดาวิชาที่เจอ ชื่อภาษาอังกฤษ (`name_en`) และหน่วยกิต (`credits`) ตรงกับ GT กี่ %

### ผลลัพธ์ล่าสุด

| Metric | ผลลัพธ์ |
|---|---|
| Recall (จำนวนวิชาที่เจอ) | 98.8% (79 / 80 valid courses) |
| name_en agreement | 96.2% |
| credits agreement | 97.5% |

### Known Limitations

- **1 วิชาหาไม่เจอ**: `06016401` (Mathematics for Information Technology) ไม่ถูกดึงจากตารางหลักสูตรหลัก แม้ชื่อวิชาจะปรากฏซ้ำในหน้าประวัติอาจารย์ผู้สอน (หน้า 49) คาดว่าหน้าตารางรายวิชาจริงของวิชานี้มีปัญหา OCR หรือ layout ตารางต่างจากส่วนอื่น
- **รหัสวิชาซ้ำในเอกสาร**: เอกสารเป็น course catalog ระดับสถาบัน รหัสวิชาเดียวกันอาจปรากฏหลายจุด (ตารางหลักสูตร, หน้าภาระงานสอน, ดัชนี) บาง occurrence ไม่มีข้อมูลชื่อ/หน่วยกิตกำกับ — `evaluate_curriculum.py` แก้ปัญหานี้ด้วยการ merge ทุก occurrence ของรหัสเดียวกัน โดยเลือกค่าที่ไม่ว่างเปล่ามาใช้ แทนที่จะให้ occurrence สุดท้ายทับของเดิมเฉยๆ
- **2-3 วิชามี field ไม่ครบ**: บาง table row มี format แตกต่างจากส่วนใหญ่ในเล่ม ทำให้ credit pattern regex จับไม่ได้ (`name_en`/`credits` เป็น `null`)

### ไฟล์ที่เกี่ยวข้อง

```text
src/ocr_system/engines/tesseract_engine.py   ใช้ image_to_string() สำหรับภาษาไทย
src/ocr_system/pipeline.py                   join ข้อความแต่ละหน้าด้วย "\n"
src/ocr_system/curriculum_extraction.py      ดึง course records จาก OCR text (regex-based)
src/ocr_system/evaluate_curriculum.py        วัดผล recall + field-level agreement เทียบ GT
src/ocr_system/cli.py                        subcommand `curriculum` รวม extraction + evaluation
```

### หมายเหตุเกี่ยวกับ `outputs/`

โฟลเดอร์ `outputs/` ใน branch นี้เก็บเฉพาะไฟล์ที่เกี่ยวข้องกับ curriculum extraction เท่านั้น
ตัวอย่าง output ของระบบ OCR พื้นฐาน (quote.jpg, pdf_sample.pdf ฯลฯ) อยู่ใน branch `Lab-3`
