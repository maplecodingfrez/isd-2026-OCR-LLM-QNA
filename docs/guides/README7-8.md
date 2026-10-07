# คู่มือการรัน Lab 7 และ Lab 8 (Step-by-Step Guide)
### โครงการ OCR & LLM ถาม-ตอบข้อมูลหลักสูตร (DSBA Coop)

คู่มือนี้สรุปคำสั่งและขั้นตอนทั้งหมดสำหรับการรัน **Lab 7B (Curriculum Extraction)** และ **Lab 8B (NL-to-SQL Curriculum Q&A)** ตั้งแต่เริ่มต้นจนได้ระบบถาม-ตอบผ่าน CLI

---

## 1. สิ่งที่ต้องเตรียมก่อนเริ่มต้น (Prerequisites)

### 1.1 ตรวจสอบ Environment
เปิด Terminal ในโฟลเดอร์โปรเจกต์ และเปิดใช้งาน Virtual Environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
```

```bash
# Linux / macOS / Git Bash
source .venv/bin/activate
export PYTHONUTF8=1
```

---

### 1.2 ติดตั้งและเปิดใช้งาน Ollama

ดึงโมเดลที่จำเป็นทั้งหมด 3 ตัว:

```bash
# 1. โมเดลสายตาสำหรับอ่านหน้าเอกสาร / สกัด Markdown (Lab 7B)
ollama pull scb10x/typhoon-ocr1.5-3b

# 2. โมเดลวิเคราะห์ข้อความและสังเคราะห์คำตอบภาษาไทย (Lab 7B & Lab 8B Tier 2)
ollama pull qwen3:4b

# 3. โมเดลเขียนคำสั่ง SQL สำหรับ NL-to-SQL (Lab 8B Tier 1)
ollama pull qwen2.5-coder:7b
```

เปิด Ollama Service ทิ้งไว้ในอีกหน้าต่าง Terminal:
```bash
ollama serve
```

ทดสอบว่า Ollama พร้อมทำงาน:
```bash
curl http://127.0.0.1:11434/api/tags
```

---

## 2. Lab 7B — การสกัดข้อมูลหลักสูตรด้วย Local LLM

Lab 7B ใช้ Local LLM สกัดรายวิชา, หน่วยกิต, ปี/ภาค และวิชาบังคับก่อน (Prerequisite) จากเอกสารหลักสูตรออกมาเป็น JSON

### คำสั่งรัน Lab 7B:

#### กรณีใช้ชุดภาพหน้าเอกสาร (`data/input_C`) ด้วย VLM Pipeline:
```bash
python src/ocr_system/lab7b_curriculum.py `
  -i data/input_C `
  -g data/ground_truth_C/DSBA_academic_plan_coop.json `
  -p vlm `
  -o work/lab7b_run
```
*(ถ้าใช้ Git Bash หรือ Linux ให้เปลี่ยนเครื่องหมาย `` ` `` เป็น `\`)*

#### พารามิเตอร์ที่สำคัญ:
- `-i` : ไฟล์ PDF ต้นฉบับ หรือ โฟลเดอร์รูปภาพ (เช่น `data/input_C`)
- `-g` : ไฟล์ Ground Truth เพื่อประเมินผล (เช่น `data/ground_truth_C/DSBA_academic_plan_coop.json`)
- `-p` : Pipeline ที่ต้องการใช้งาน:
  - `vlm` : ใช้ `scb10x/typhoon-ocr1.5-3b` อ่านจากรูปภาพโดยตรง
  - `text` : ใช้ `pdfplumber` ดึงข้อความจาก Digital PDF (เร็วกว่า ไม่เพี้ยน)
  - `baseline` : Tesseract OCR
  - `all` : รันทุก pipeline เพื่อเทียบผล
- `-o` : โฟลเดอร์ปลายทางสำหรับบันทึกผล (แนะนำ `work/lab7b_run`)
- `--pages` : เลือกเฉพาะบางหน้า เช่น `--pages 19,21,27,28`

#### ผลลัพธ์ที่ได้ใน `work/lab7b_run/`:
- `pred_vlm.json` : ข้อมูลรายวิชาที่ LLM สกัดได้ทั้งหมด
- `evaluation.json` : รายงานความแม่นยำรายฟิลด์ (Recall, Precision, F1)
- `comparison.csv` : ตารางเปรียบเทียบผลลัพธ์กับ Ground Truth ทีละวิชา

---

## 3. Lab 8B — NL-to-SQL ถาม-ตอบข้อมูลหลักสูตรผ่าน CLI

Lab 8B นำข้อมูล JSON ที่สกัดได้จาก Lab 7B แปลงเป็นฐานข้อมูล SQLite แล้วสร้างระบบถาม-ตอบภาษาไทยผ่าน CLI

---

### วิธีที่ 1: รันอัตโนมัติทั้งหมด (All-in-One Runner)

คุณสามารถใช้สคริปต์ `run_lab8b.py` รัน workflow ทั้งหมดได้ทันที:

```bash
# รันตั้งแต่ Lab 7B (VLM Extraction) -> Lab 8B (DB + Evaluation)
python run_lab8b.py
```

ถ้าเคยรัน Lab 7B ได้ไฟล์ `pred_vlm.json` หรือ `pred_markdown.json` ไว้แล้ว สามารถข้ามขั้นตอนการสกัดเพื่อประหยัดเวลาได้:
```bash
# ข้าม Lab 7B แล้วรันเฉพาะขั้นตอนของ Lab 8B
python run_lab8b.py --skip-lab7
```

---

### วิธีที่ 2: รันทีละขั้นตอน (Step-by-Step CLI)

หากต้องการทดลองรันและตรวจสอบผลทีละขั้นตอน ให้ทำตามลำดับต่อไปนี้:

#### ขั้นตอนที่ 1: สร้าง Schema ฐานข้อมูล SQLite
```bash
python src/ocr_system/lab8b_curriculum_db.py schema -o work/lab8b_run/schema
```
*ไฟล์ที่ได้:* `schema.sql` (โครงสร้าง 4 ตาราง + 2 Views) และ `curriculum.schema.json`

#### ขั้นตอนที่ 2: แปลงผลลัพธ์จาก Lab 7B เข้าสู่ Schema ของ Lab 8B
```bash
python src/ocr_system/lab8b_curriculum_db.py import-lab7b `
  -i work/lab7b_run/pred_vlm.json `
  -o work/lab8b_run/curriculum.json `
  --program-id "DSBA-coop" `
  --program-name "วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ (สหกิจศึกษา)" `
  --total-credits 135 `
  --years 4
```

#### ขั้นตอนที่ 3: โหลดข้อมูล JSON เข้าสู่ SQLite Database
```bash
python src/ocr_system/lab8b_curriculum_db.py load `
  -i work/lab8b_run/curriculum.json `
  -d work/lab8b_run/curriculum.db `
  --replace
```

#### ขั้นตอนที่ 4: ตรวจสอบความสอดคล้องตามกฎ 7 ข้อ (Consistency Verification)
```bash
python src/ocr_system/lab8b_curriculum_db.py verify `
  -d work/lab8b_run/curriculum.db `
  -o work/lab8b_run/verify.json
```
*ตรวจกฎ 7 ข้อ:*
1. `CHK1`: ผลรวมหน่วยกิตตรงกับที่ประกาศ
2. `CHK2`: ทุกรหัสวิชาในแผนมีคำอธิบายรายวิชา
3. `CHK3`: รหัสวิชาเป็นตัวเลข 8 หลัก
4. `CHK4`: หน่วยกิตในแผนตรงกับในคำอธิบาย
5. `CHK5`: วิชาบังคับก่อน (Prerequisite) อยู่ในเทอมก่อนหน้า
6. `CHK6`: ไม่มีวิชาซ้ำในเทอมเดียวกัน
7. `CHK7`: หน่วยกิตต่อเทอมอยู่ระหว่าง 9–22 หน่วยกิต

#### ขั้นตอนที่ 5: ถาม-ตอบข้อมูลหลักสูตรผ่าน CLI (`ask`)
ทดลองพิมพ์คำถามภาษาไทย ระบบจะแปลงคำถามเป็น SQL ดึงข้อมูลจากฐานข้อมูล และตอบกลับเป็นภาษาไทย:

```bash
# ตัวอย่างคำถามที่ 1: ถามหน่วยกิตประจำเทอม
python src/ocr_system/lab8b_curriculum_db.py ask `
  -d work/lab8b_run/curriculum.db `
  -q "ปีที่ 2 เทอม 1 นักศึกษาต้องเรียนกี่หน่วยกิต"

# ตัวอย่างคำถามที่ 2: ถามค้นหารหัสวิชา
python src/ocr_system/lab8b_curriculum_db.py ask `
  -d work/lab8b_run/curriculum.db `
  -q "วิชาการพัฒนาระบบอัจฉริยะมีรหัสอะไร"

# ตัวอย่างคำถามที่ 3: ถามเงื่อนไขวิชาบังคับก่อน
python src/ocr_system/lab8b_curriculum_db.py ask `
  -d work/lab8b_run/curriculum.db `
  -q "วิชาคอมพิวเตอร์วิทัศน์ต้องเรียนวิชาอะไรมาก่อน"

# ตัวอย่างคำถามที่ 4: ถามรายวิชาในเทอม
python src/ocr_system/lab8b_curriculum_db.py ask `
  -d work/lab8b_run/curriculum.db `
  -q "ปี 1 เทอม 1 เรียนวิชาอะไรบ้าง"
```

#### ขั้นตอนที่ 6: ประเมินความแม่นยำด้วยชุดคำถามทอง (Benchmark Evaluation)
ทดสอบระบบด้วยชุดคำถามมาตรฐาน 30 ข้อ:

```bash
python src/ocr_system/lab8b_curriculum_db.py eval `
  -d work/lab8b_run/curriculum.db `
  -q work/lab8b_run/gold_questions.json `
  -o work/lab8b_run/eval_result.json
```

---

## 4. คำสั่งตรวจสอบผลลัพธ์ (Checking Results)

### ตรวจสอบผลการประเมินชุดคำถาม 30 ข้อ (Lab 8B):
```bash
python -c "
import json
data = json.load(open('work/lab8b_run/eval_result.json', encoding='utf-8'))
correct = sum(1 for r in data if r.get('correct'))
sql_ok = sum(1 for r in data if not r.get('error'))
print(f'SQL Execution Success : {sql_ok}/{len(data)} ({sql_ok/len(data):.1%})')
print(f'Answer Accuracy       : {correct}/{len(data)} ({correct/len(data):.1%})')
"
```

### ตรวจสอบผลการ verify ฐานข้อมูล:
```bash
python -c "
import json
data = json.load(open('work/lab8b_run/verify.json', encoding='utf-8'))
for rule in data:
    status = '✓ ผ่าน' if rule['ok'] else '✗ ไม่ผ่าน'
    print(f\"{rule['id']}: {status} - {rule['name']}\")
"
```

---

## 5. ปัญหาที่พบบ่อยและการแก้ไข (Troubleshooting)

| ปัญหา | สาเหตุ | วิธีแก้ |
|---|---|---|
| ต่อ Ollama ไม่ได้ (`ConnectionRefusedError`) | ยังไม่ได้เปิด background service | รัน `ollama serve` ในอีก Terminal หนึ่ง |
| ภาษาไทยแสดงผลเพี้ยนบน Windows | Terminal ใช้ Code Page เก่า | รัน `chcp 65001` และตั้ง `$env:PYTHONUTF8="1"` |
| ประมวลผลช้ามากบน CPU | ไม่ได้ใช้ GPU หรือ Context ใหญ่เกินไป | ปรับ Context ในคำสั่ง: `$env:LAB7B_NUM_CTX="2048"` หรือรันเฉพาะหน้าที่จำเป็นด้วย `--pages` |
| หาไฟล์ `pred_vlm.json` ไม่เจอ | Lab 7B ยังรันไม่เสร็จหรือระบุ path ผิด | ตรวจสอบโฟลเดอร์ `work/lab7b_run/` ว่ามีไฟล์ JSON อยู่หรือไม่ |
