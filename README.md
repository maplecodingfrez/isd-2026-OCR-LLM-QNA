# Thai-English OCR System

โปรเจกต์นี้เป็น OCR pipeline สำหรับเอกสารภาพเดี่ยวและหลายหน้า เช่น `.jpg`, `.png`, `.tif`, `.pdf` โดยรองรับเอกสารภาษาไทยและอังกฤษปนกัน

OCR engines ที่มีให้:

- PaddleOCR: เหมาะกับภาษาไทยและเอกสารทั่วไป
- Tesseract OCR: ใช้ `tha+eng` ได้ดีเมื่อมีภาษาไทย/อังกฤษปนกัน
- TrOCR: OCR แบบ Transformer เหมาะกับ printed English เป็นหลัก
- Ensemble: ใช้ PaddleOCR + Tesseract แล้วรวมผลแบบง่าย

---

## Project Structure

```text
ocr_system/
├── README.md
├── requirements.txt
├── pyproject.toml
├── data/
│   ├── input/                 # dsba_curriculum.pdf, ait_curriculum.pdf, it_curriculum.pdf, bit_curriculum.pdf
│   └── ground_truth/          # DSBA/AIT/IT/BIT (coop + no_coop), general_education, rules
├── outputs/
│   ├── dsba/ ait/ it/ bit/     # ผลลัพธ์ OCR, extraction, evaluation, page mapping, Lab 6 (แยกโฟลเดอร์ต่อหลักสูตร)
│   ├── qa_pairs.csv            # Q&A ร่วมทุกหลักสูตร (Lab 5/6)
│   └── pages/                  # ภาพหน้า PDF ที่แปลงแล้ว (debug, ใช้ร่วมกัน)
├── scripts/
│   ├── lab5_page_mapping.py  # Lab 5: รัน gt_page_mapping ต่อ program+plan (DSBA/AIT/IT/BIT)
│   ├── lab5_qa_pairs.py      # Lab 5: สร้าง outputs/qa_pairs.csv (32 ข้อ)
│   ├── supplement_check_rules.py         # เช็ค coverage ของ rules_ground_truth.json ต่อ program
│   ├── supplement_general_education.py # เทียบ courses ที่ extract ได้กับ general_education_ground_truth.json (DSBA/AIT/IT)
│   └── lab6_evaluate.py       # Lab 6: รวม Field/Page/Category level evaluation
└── src/
    └── ocr_system/
        ├── cli.py             # command line interface
        ├── config.py          # config หลักของระบบ
        ├── document_loader.py # โหลดภาพ / แปลง PDF เป็นภาพ
        ├── preprocessing.py   # resize, denoise, contrast, deskew, threshold, ลบลายน้ำ (AIT/IT)
        ├── pipeline.py        # OCR pipeline หลัก
        ├── evaluation.py      # CER, WER, exact match (เอกสารทั่วไป)
        ├── field_extraction.py# ดึง field เช่น email, date, id, phone
        ├── curriculum_extraction.py # ดึง course records จากเอกสารหลักสูตร (Lab 4, ใช้กับ DSBA/AIT/IT/BIT)
        ├── evaluate_curriculum.py   # recall + field-level agreement + CER/WER (Lab 4)
        ├── gt_page_mapping.py       # map course code → หน้า PDF จริง (Lab 5)
        ├── evaluate_lab6.py         # รวม Field/Page/Category level evaluation (Lab 6)
        ├── schemas.py         # dataclass ของผลลัพธ์
        ├── engine_factory.py  # เลือก OCR engine
        ├── engines/
        │   ├── base.py
        │   ├── paddle_engine.py
        │   ├── tesseract_engine.py
        │   ├── trocr_engine.py
        │   └── ensemble_engine.py
        └── utils/
            └── io.py
```

---

## ใช้งานผ่าน VS Code 

แนะนำให้ใช้ **VS Code** เพราะเปิดดูโครงสร้างไฟล์ แก้โค้ด และรันคำสั่งใน Terminal ได้ในที่เดียว
---
## วิธีเปิดโปรเจกต์ใน VS Code
1. แตกไฟล์ `ocr_system.zip`
2. จะได้โฟลเดอร์ชื่อ `ocr_system`
3. เปิด VS Code
4. ไปที่เมนู
```text
File > Open Folder
```

5. เลือกโฟลเดอร์ `ocr_system`
6. เปิด Terminal ใน VS Code
```text
Terminal > New Terminal
```
หลังจากนี้ให้พิมพ์คำสั่งต่าง ๆ ใน Terminal ของ VS Code ได้เลย

---

## Installation
แนะนำใช้ Python 3.10 ขึ้นไป
เช็กเวอร์ชัน Python ก่อน:

```bash
python --version
```
หรือบางเครื่องอาจต้องใช้:
```bash
py --version
```
ถ้าเวอร์ชันเป็น Python 3.10, 3.11 หรือ 3.12 สามารถใช้ได้

---

## สร้าง Virtual Environment
Virtual Environment คือพื้นที่แยกสำหรับติดตั้ง package ของโปรเจกต์นี้โดยเฉพาะ เพื่อไม่ให้ชนกับโปรเจกต์อื่น
ให้เข้าไปในโฟลเดอร์โปรเจกต์ก่อน:
```bash
cd ocr_system
```
จากนั้นสร้าง environment:
```bash
python -m venv .venv
```

ถ้าใช้ Windows แล้วคำสั่ง `python` ไม่ได้ ให้ลองใช้:
```bash
py -m venv .venv
```

---

## เปิดใช้งาน Virtual Environment

### Windows CMD
```bash
.venv\Scripts\activate
```

### Windows PowerShell
```bash
.venv\Scripts\Activate.ps1
```

ถ้า PowerShell ขึ้น error เรื่อง policy ให้รัน:
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

แล้วลอง activate ใหม่อีกครั้ง

### macOS / Linux
```bash
source .venv/bin/activate
```
ถ้าสำเร็จ จะเห็นชื่อ environment ขึ้นต้นบรรทัดประมาณนี้:
```text
(.venv) C:\...\ocr_system>
```

---

## ติดตั้ง Python Packages
หลังจาก activate `.venv` แล้ว ให้ติดตั้ง package ทั้งหมด:
```bash
pip install -r requirements.txt
```

จากนั้นติดตั้งโปรเจกต์แบบ editable:
```bash
pip install -e .
```

คำสั่งนี้ทำให้สามารถเรียกใช้งานโปรเจกต์ด้วยรูปแบบนี้ได้:
```bash
python -m ocr_system.cli
```

---

## Install Tesseract Engine
ในโปรเจกต์นี้มี OCR หลายตัว เช่น PaddleOCR, Tesseract และ TrOCR
แต่สำหรับ Tesseract ต้องติดตั้งโปรแกรม Tesseract OCR แยกต่างหาก เพราะ `pytesseract` เป็นแค่ Python package ที่ใช้เรียกโปรแกรม Tesseract เท่านั้น

---

## ติดตั้ง Tesseract บน Windows
ให้ติดตั้ง Tesseract OCR จาก UB Mannheim build
ระหว่างติดตั้ง ให้เลือกภาษา:
```text
English
Thai
```

หลังติดตั้งเสร็จ ให้เปิด CMD หรือ VS Code Terminal ใหม่ แล้วตรวจสอบ:
```bash
tesseract --version
```

จากนั้นตรวจสอบภาษาที่ติดตั้ง:
```bash
tesseract --list-langs
```
ควรเห็นอย่างน้อย:
```text
eng
tha
```
ถ้าไม่เห็น `tha` แปลว่ายังไม่ได้ติดตั้งภาษาไทย

---

## ติดตั้ง Tesseract บน Ubuntu / Debian
```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-tha poppler-utils
```
---

## ติดตั้ง Tesseract บน macOS
```bash
brew install tesseract poppler
brew install tesseract-lang
```
หมายเหตุ: `poppler` จำเป็นสำหรับแปลง PDF เป็นภาพผ่าน `pdf2image`

---

## เตรียมไฟล์สำหรับทดสอบ OCR
นำไฟล์เอกสารไปวางในโฟลเดอร์นี้:
```text
data/input/
```

ตัวอย่าง:
```text
data/input/sample.pdf
data/input/sample.jpg
data/input/sample.png
```

รองรับทั้ง:
```text
PDF หลายหน้า
JPG
PNG
TIFF
BMP
```

---

## Usage
### 1. OCR ด้วย Ensemble
Ensemble คือการใช้หลาย OCR engine ช่วยกัน แล้วเลือกผลลัพธ์ที่เหมาะสมที่สุด
เหมาะสำหรับเอกสารที่มีทั้งภาษาไทยและอังกฤษปนกัน

```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine ensemble
```

หลังรันเสร็จ ผลลัพธ์จะอยู่ในโฟลเดอร์:
```text
outputs/
```

จะได้ไฟล์ประมาณนี้:
```text
outputs/sample_ocr.json
outputs/sample_ocr.txt
outputs/sample_fields.json
outputs/pages/
```

ความหมายของไฟล์:
```text
sample_ocr.json     ผล OCR แบบละเอียด เช่น text, confidence, page
sample_ocr.txt      ข้อความ OCR รวมทั้งหมด อ่านง่าย
sample_fields.json  field ที่ระบบพยายาม extract เช่น วันที่ ชื่อ รหัส
outputs/pages/      ภาพแต่ละหน้าที่แปลงจาก PDF
```

---

## 2. OCR ด้วย PaddleOCR
เหมาะกับเอกสารทั่วไป โดยเฉพาะภาษาไทยและอังกฤษปนกัน
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine paddle --paddle-lang th
```
ถ้าเอกสารเป็นอังกฤษล้วน อาจลองใช้:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine paddle --paddle-lang en
```
---
## 3. OCR ด้วย Tesseract ไทย + อังกฤษ
เหมาะกับเอกสาร scan ที่ตัวหนังสือชัด หรือเอกสารราชการ/ฟอร์มที่ layout ไม่ซับซ้อนมาก
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine tesseract --languages tha+eng
```

ถ้าเป็นอังกฤษอย่างเดียว:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine tesseract --languages eng
```

ถ้าเป็นไทยอย่างเดียว:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine tesseract --languages tha
```

---

## 4. OCR ด้วย TrOCR
TrOCR เป็นโมเดล OCR จาก Transformer
ในโปรเจกต์นี้ใช้เป็น fallback สำหรับข้อความสั้น ๆ หรือภาพที่ crop เป็นบรรทัดแล้ว
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine trocr --device cpu
```
ถ้ามี GPU และติดตั้ง PyTorch แบบ CUDA แล้ว สามารถใช้:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine trocr --device cuda
```
หมายเหตุ: TrOCR ในโปรเจกต์นี้ยังไม่เหมาะกับเอกสารยาวทั้งหน้า แนะนำใช้ PaddleOCR หรือ Tesseract เป็นหลัก

---
## Evaluation
Evaluation คือการวัดว่า OCR อ่านถูกแค่ไหน โดยเทียบกับข้อความจริง หรือ Ground Truth
สร้างไฟล์ ground truth เช่น:
```text
data/ground_truth/example_ground_truth.json
```

ตัวอย่างเนื้อหา:
```json
{
  "sample.pdf": "ข้อความจริงทั้งหมดในเอกสาร sample.pdf",
  "sample.jpg": "ข้อความจริงในเอกสาร sample.jpg"
}
```

จากนั้นรัน OCR ก่อน:
```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine ensemble
```
แล้ว evaluate:
```bash
python -m ocr_system.cli evaluate data/ground_truth/example_ground_truth.json outputs/sample_ocr.json
```

Metric ที่ได้:

```text
cer           Character Error Rate ยิ่งต่ำยิ่งดี
wer           Word Error Rate ยิ่งต่ำยิ่งดี
exact_match   ข้อความตรงทั้งหมดหรือไม่
```

ตัวอย่างการอ่านผล:
```text
CER = 0.05 หมายถึงผิดประมาณ 5% ระดับตัวอักษร
WER = 0.12 หมายถึงผิดประมาณ 12% ระดับคำ
exact_match = false หมายถึงยังไม่ตรง 100%
```
---

## คำสั่งที่ใช้บ่อย
OCR ไฟล์ PDF ด้วยระบบรวม:
```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine ensemble
```

OCR รูปภาพด้วย PaddleOCR:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine paddle --paddle-lang th
```

OCR รูปภาพด้วย Tesseract:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine tesseract --languages tha+eng
```

Evaluate ผล OCR:
```bash
python -m ocr_system.cli evaluate data/ground_truth/example_ground_truth.json outputs/sample_ocr.json
```

---

## Recommended Engine

สำหรับเอกสารไทย+อังกฤษปนกัน แนะนำเริ่มจาก:
```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine ensemble --languages tha+eng --paddle-lang th --save-debug-images
```

ถ้าเอกสารเป็นอังกฤษเกือบทั้งหมด:
```bash
python -m ocr_system.cli ocr data/input/sample.pdf --engine paddle --paddle-lang en
```

ถ้า Tesseract อ่านไทยเพี้ยน ให้ลอง OCR แบบไม่ preprocess:
```bash
python -m ocr_system.cli ocr data/input/sample.jpg --engine tesseract --no-preprocess
```

---

## Output JSON Format
```json
{
  "source_path": "data/input/sample.pdf",
  "engine": "ensemble",
  "text": "--- Page 1 ---\n...",
  "pages": [
    {
      "page": 1,
      "text": "...",
      "lines": [
        {
          "text": "ข้อความที่ OCR อ่านได้",
          "confidence": 0.95,
          "box": [[0, 0], [100, 0], [100, 30], [0, 30]],
          "engine": "paddle",
          "page": 1
        }
      ],
      "image_path": "outputs/pages/sample_page_001.jpg"
    }
  ]
}
```

---

## Curriculum Extraction (Lab 4)

ทีมเลือกหัวข้อ **Curriculum Extraction** — ดึงข้อมูลรายวิชา (รหัสวิชา, ชื่อไทย, ชื่ออังกฤษ, หน่วยกิต) จากเอกสารเล่มหลักสูตร ด้วย OCR แล้ววัดผลเทียบกับ Ground Truth ครอบคลุมทั้ง 4 หลักสูตร: **DSBA** (PDF สแกน 403 หน้า, GT `DSBA_academic_plan_coop.json`), **AIT** (346 หน้า, GT `AIT_academic_plan.json`), **IT** (429 หน้า, GT `IT_academic_plan_coop.json`) และ **BIT** (GT `BIT_academic_plan_coop.json`) — ตัวอย่าง pipeline/คำสั่งด้านล่างใช้ DSBA เป็นหลัก ส่วนผลลัพธ์ทั้ง 4 หลักสูตรดูที่หัวข้อ "AIT / IT / BIT Curriculum" ท้ายส่วนนี้

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
python -m ocr_system.cli ocr data/input/dsba_curriculum.pdf --engine tesseract --output-dir outputs/dsba

# 2. Extract + Evaluate ในคำสั่งเดียว
python -m ocr_system.cli curriculum outputs/dsba/dsba_curriculum_ocr.json \
    --ground-truth data/ground_truth/DSBA_academic_plan_coop.json --output-dir outputs/dsba
```

ผลลัพธ์ที่ได้:
```text
outputs/dsba/dsba_curriculum_courses.json                 รายวิชาที่ดึงได้ทั้งหมด
outputs/dsba/dsba_curriculum_curriculum_evaluation.json   ผล evaluation เทียบกับ GT
```

หมายเหตุ: `outputs/` จัดเรียงเป็นโฟลเดอร์ย่อยตามหลักสูตร (`outputs/dsba/`, `outputs/ait/`, `outputs/it/`, `outputs/bit/`) — ไฟล์ที่ใช้ร่วมกันข้ามหลักสูตร (`qa_pairs.csv`, `pages/`) ยังอยู่ที่ระดับบนสุดของ `outputs/` เหมือนเดิม

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

### ฟิลด์เพิ่มเติม: category, prerequisite, year/semester

Ground truth มีทั้งหมด 11 field ต่อวิชา (`code`, `name_th`, `name_en`, `credits`,
`year`, `semester`, `category`, `type`, `prerequisite`, `flexible_year_semester`,
`note`) แต่เดิม extraction ดึงได้จริงแค่ 4 field แรกจากตาราง "รายวิชา" เดียว
ส่วนที่เหลือ hardcode เป็น `None` ทั้งหมด เพราะไม่มีข้อมูลนั้นอยู่ใน block ข้อความ
เดียวกับ code/name/credits

พบว่าเอกสารมีอีก 2 ส่วนที่ให้ข้อมูล 3 field เพิ่มได้โดยไม่ต้องแตะ logic เดิมเลย —
สร้างเป็น lookup อิสระ (code → value) แล้ว merge เข้ากับ course ที่ extract ได้แล้ว
ทีหลัง:

- **`category`** — ตาราง "รายวิชา" เดิมมี header คั่นเป็นช่วงๆ อยู่แล้ว
  ("ก. หมวดวิชาศึกษาทั่วไป" / "ข. หมวดวิชาเฉพาะ" / "ค. หมวดวิชาเลือกเสรี") แค่ track
  ว่า header ล่าสุดที่เจอคืออะไรระหว่างเดินอ่านข้อความไปเรื่อยๆ
- **`prerequisite`** — มีส่วน "คำอธิบายรายวิชา" แยกต่างหาก (มักอยู่ท้ายเล่ม) เขียนกำกับ
  ทุกวิชาว่า `"วิชาบังคับก่อน : <รหัส> <ชื่อ>"` หรือ `"... : ไม่มี"` ตรงๆ อยู่แล้ว
- **`year` / `semester`** — มีตาราง "แผนการศึกษา" แยกต่างหาก แสดงรหัสวิชาอีกครั้งจัด
  กลุ่มด้วย header "ปีที่ N ภาคการศึกษาที่ M" โปรแกรมที่มีทั้ง coop/no_coop
  (DSBA/IT/BIT) จะมีตารางนี้ซ้ำ 2 รอบ (คนละแผน) ต้องแยกอ่านให้ตรงกับ `plan` ที่ขอ
  หลายแถวในตารางนี้ OCR ไม่เหลือรหัสวิชากำกับเลย (เหลือแต่ชื่อวิชาเปล่าๆ เช่น
  "CALCULUS 1" ไม่มี "06026200" นำหน้า) จึงมี fallback เพิ่ม: จับคู่ชื่อวิชานั้นกับ
  ชื่อที่ extract ได้แล้วจากตารางหลัก (`_build_name_to_code_map`) เพื่อย้อนหารหัส
  กลับมา — ใช้เฉพาะชื่อที่ยาวพอ (≥8 ตัวอักษร) และ map กับรหัสเดียวแบบไม่กำกวมเท่านั้น
  ถ้าชื่อเดียวกันไป match ได้เกิน 4 ช่วงปี/เทอม (ผิดปกติ ไม่ใช่ flexible จริง) จะทิ้งไปเป็น
  `None` แทนที่จะเดา flexible ผิดๆ

ผลลัพธ์จริงเมื่อรันกับทั้ง 7 ชุด (เทียบเป็น field-by-field accuracy กับ ground truth
ตรงๆ ไม่ผ่าน `evaluate_curriculum.py`):

| Program | Plan | category | prerequisite | year/semester |
|---|---|---|---|---|
| DSBA | coop | 100% | 100% | 39.2% |
| DSBA | no_coop | 100% | 100% | 41.8% |
| AIT | (ไม่มี coop) | 100% | 95.8% | 4.2% |
| IT | coop | 100% | 97.0% | 43.4% |
| IT | no_coop | 100% | 97.0% | 43.4% |
| BIT | coop | 90.9% | 98.2% | 60.0% |
| BIT | no_coop | 90.9% | 98.2% | 63.6% |

`category`/`prerequisite` ใช้ได้จริงแทบทุกกรณี (BIT เหลือ 90.9% เพราะ 5 วิชาใน
กลุ่ม 9664xxxx ถูก tag ผิดเป็น "หมวดวิชาเลือกเสรี" — โค้ดเดิมยึด occurrence แรกสุดที่
เจอในเอกสาร แต่ของ BIT ไปเจอ mention ในโซนเลือกเสรีก่อนโซนศึกษาทั่วไป)

`year`/`semester` ได้ต่ำกว่ามาก (4-64% แล้วแต่เล่ม) เพราะตาราง "แผนการศึกษา" เป็นตาราง
คนละหน้ากับตารางหลัก และ OCR ของตารางนี้ garbled กว่าตารางอื่นๆ ในเล่มเดียวกันมาก —
การเพิ่ม name-matching fallback ช่วย DSBA (13.9%→39.2%, 20.3%→41.8%) และ IT
(25.3%→43.4%) ได้เกือบ 2 เท่า แต่ทำให้ AIT/BIT ลดลงเล็กน้อย (AIT 6.2%→4.2%, BIT
61.8%→60.0% และ 65.5%→63.6%) เพราะ AIT ใช้ระบบ "กลุ่มทักษะ" ที่ชื่อวิชาเดียวกันถูก
อ้างซ้ำเป็นตัวเลือกในหลายภาคเรียน (ไม่ใช่ fixed schedule) ทำให้ชื่อไป match กับ header
ที่ไม่ตรงกับค่าคงที่ที่ GT ระบุ — ตัดสินใจเก็บ fallback ไว้เหมือนกันทุกโปรแกรม (ไม่ special-case
AIT/BIT) เพราะภาพรวมได้มากกว่าเสีย และ field นี้ไม่ถูก score ใน `evaluate_curriculum.py`/
`evaluate_lab6.py` อยู่แล้ว (ไม่กระทบเกรด Lab 4/5/6) ถ้าจะย้อนกลับทีหลังทำง่าย: ส่ง
`name_to_code=None` เข้า `_build_year_semester_lookup()` เฉพาะตอน program เป็น AIT/BIT
ก็พอ ไม่ต้องแก้ logic การ match เลย

`flexible_year_semester` ยังคงเป็น `None` เกือบทุกกรณี — ที่ตั้งใจจะ derive จากการที่
รหัสวิชาเดียวกันโผล่ซ้ำใน "แผนการศึกษา" มากกว่า 1 ช่วงปี/เทอม (ตรงกับที่ ground truth
ใช้ค่าเช่น `"3/1, 3/2, 4/1"`) แต่พบว่าวิชากลุ่มเลือกที่ ground truth ระบุเป็น flexible
จริงๆ ไม่เคยถูกระบุรหัสในตาราง "แผนการศึกษา" เลย (ตารางระบุแค่ชื่อกลุ่มวิชาเลือกที่
ให้เลือก ไม่ใช่รหัสวิชาที่เจาะจง) จึงไม่มีสัญญาณให้ดึงจริงๆ

`type` (บังคับ/เลือก) และ `note` ยังคง hardcode เป็น `None` เหมือนเดิม — ไม่พบ label
ที่ระบุชัดเจนติดกับแต่ละวิชาในเอกสาร ต้องเดาจากชื่อกลุ่มย่อยซึ่งเสี่ยงผิดสูง จึงยังไม่ทำ

**หมายเหตุ**: `evaluate_curriculum.py` และ `evaluate_lab6.py` ยังคงวัดผลแค่ 4 field
เดิม (`code`/`name_en`/`name_th`/`credits`) เหมือนเดิม ไม่ได้แก้ให้ไปเช็ค 3 field ใหม่นี้
ด้วย — ตัวเลขข้างต้นมาจากการเทียบ JSON ตรงๆ กับ ground truth เท่านั้น (ตรงกับที่ใช้ใน
การเช็คงานจริง)

### ไฟล์ที่เกี่ยวข้อง

```text
src/ocr_system/engines/tesseract_engine.py   ใช้ image_to_string() สำหรับภาษาไทย
src/ocr_system/pipeline.py                   join ข้อความแต่ละหน้าด้วย "\n"
src/ocr_system/curriculum_extraction.py      ดึง course records จาก OCR text (regex-based)
                                              + _build_category_lookup / _build_prerequisite_lookup
                                              / _build_year_semester_lookup (code -> value, merge เข้า course หลัง extract)
                                              / _build_name_to_code_map (fallback ย้อนหารหัสจากชื่อวิชา
                                              เมื่อ OCR ไม่เหลือรหัสในตาราง "แผนการศึกษา")
src/ocr_system/evaluate_curriculum.py        วัดผล recall + field-level agreement เทียบ GT
src/ocr_system/cli.py                        subcommand `curriculum` รวม extraction + evaluation
```

### หมายเหตุเกี่ยวกับ `outputs/`

โฟลเดอร์ `outputs/` ใน branch นี้เก็บเฉพาะไฟล์ที่เกี่ยวข้องกับ curriculum extraction เท่านั้น
ตัวอย่าง output ของระบบ OCR พื้นฐาน (quote.jpg, pdf_sample.pdf ฯลฯ) อยู่ใน branch `Lab-3`

ไฟล์ต่อหลักสูตรทั้งหมด (OCR, extraction, evaluation, page mapping, Lab 6, general_education)
แยกเก็บในโฟลเดอร์ย่อยตามหลักสูตร `outputs/{dsba,ait,it,bit}/` ส่วนไฟล์ที่ใช้ร่วมกันข้ามหลักสูตร
(`qa_pairs.csv`, `pages/`) อยู่ที่ระดับบนสุดของ `outputs/`

---

## AIT / IT / BIT Curriculum (Lab 4 ต่อ)

Lab 4 ครอบคลุมทั้ง 4 หลักสูตร (DSBA/AIT/IT/BIT) — ตัวอย่าง pipeline/คำสั่งด้านบนโชว์แค่ DSBA เพื่อไม่ให้ซ้ำ ส่วนนี้คือผลลัพธ์และรายละเอียดเฉพาะของ AIT/IT/BIT ใช้ pipeline เดียวกันทุกขั้นตอน (OCR → `curriculum_extraction.py` → `evaluate_curriculum.py`) กับเอกสารหลักสูตร AIT (`ait_curriculum.pdf`, 346 หน้า), IT (`it_curriculum.pdf`, 429 หน้า) และ BIT (`bit_curriculum.pdf`)

### ปัญหาที่เจอและวิธีแก้

1. **ลายน้ำ (watermark)** — เอกสาร AIT/IT มีตราประทับสถาบันสีส้ม/ชมพูจางๆ พิมพ์ทับทุกหน้า (คลุม 50-76% ของพิกเซลที่ไม่ใช่พื้นขาว) ทำให้ Tesseract อ่านข้อความปนกับลายน้ำผิดเพี้ยนหนัก แก้ด้วย `suppress_warm_watermark()` ใน `preprocessing.py` — ตรวจ pixel ที่ warm/light (ช่อง R สูงกว่า B ชัดเจน) แล้วฟอกเป็นสีขาวก่อนแปลง grayscale ตรวจสอบแล้วว่าไม่กระทบ DSBA เลย (0% ของพิกเซลที่ไม่ใช่พื้นขาวเข้าเงื่อนไขนี้ในหน้า DSBA) ผลลัพธ์: name_en agreement ของ AIT จาก 52.1% → 97.9%
2. **Token ตัวเลขปนในชื่อวิชา** — แก้ `_looks_english()` ให้ token ที่มีตัวเลข 4 หลักขึ้นไปไม่ถูกนับเป็นภาษาอังกฤษ (เดิมรหัสวิชาที่หลุด regex หลักมาปนในชื่อวิชา)
3. **Block-bleed ใน `_join_english_name()`** — เจอ credits pattern ที่สองระหว่างเดินอ่านชื่อวิชา ให้ `break` แทน `continue` เพราะเป็นสัญญาณว่าอ่านเลยเข้าบล็อกของวิชาถัดไปแล้ว

**BIT ไม่ต้องแก้อะไรเพิ่ม** — OCR เอกสาร BIT ผ่าน pipeline เดียวกัน (รวม `suppress_warm_watermark()` ที่ทำงานอัตโนมัติทุกหน้าอยู่แล้ว ไม่ต้องเปิดแยกต่อโปรแกรม) ได้ผลลัพธ์ recall 100% ทันทีโดยไม่ต้องหา fix ใหม่ — ดีกว่า AIT/IT ด้วยซ้ำ

### CER/WER (ตามคำแนะนำอาจารย์)

`evaluate_curriculum.py` เพิ่มการวัด CER/WER ต่อ field (`name_en`, `name_th`) ของทุกวิชาที่ match ได้ ต่อยอดจาก exact-match agreement เดิม เพราะ exact-match หยาบเกินไป — ชื่อที่ผิดแค่ 1-2 ตัวอักษร กับชื่อที่ผิดทั้งชื่อ นับเป็น 0 เท่ากัน แต่ CER/WER แยกความต่างนี้ได้ ใช้ `evaluate_text()` เดิมจาก `evaluation.py` ทำต่อ field แทนที่จะทำทั้งเอกสาร

### ผลลัพธ์ล่าสุด

| Program | Plan | Recall | name_en agreement | credits agreement | name_en CER / WER | name_th CER / WER |
|---|---|---|---|---|---|---|
| DSBA | coop | 98.8% (79/80) | 98.7% | 100.0% | 1.2% / 1.3% | 4.4% / 44.3% |
| AIT | none | 98.0% (48/49) | 97.9% | 100.0% | 0.5% / 0.4% | 3.6% / 36.5% |
| IT | coop | 100% (99/99) | 97.0% | 99.0% | 1.1% / 1.6% | 12.6% / 47.0% |
| BIT | coop | 100% (55/55) | 85.5% | 98.2% | 0.2% / 8.8% | 4.2% / 49.1% |

หมายเหตุ: ground truth ของ AIT (`AIT_academic_plan.json`) มี `"plan": null` ไม่มีการแบ่งแผน coop/no_coop เหมือน DSBA/IT/BIT — ใช้ `--plan none` เพื่อสื่อความหมายตรงกับข้อมูลจริง (ไม่กระทบผล evaluation เพราะ `plan` เป็นแค่ metadata ไม่ถูกใช้ในการ match/ประเมินผล)

สำหรับ DSBA และ IT ตรวจสอบแล้วว่าไฟล์ coop/no_coop ให้ผล evaluation เหมือนกันทุกประการ (DSBA: record เหมือนกัน 100%; IT: ต่างกันแค่ field `year`/`semester`/`note` ที่ `evaluate_curriculum.py` ไม่ได้ใช้เทียบ) จึงรันแค่ไฟล์เดียวก็ครอบคลุม

**BIT ต่างออกไปเล็กน้อย** — ตรวจสอบละเอียดแล้วพบว่า `BIT_academic_plan_coop.json`/`_no_coop.json` มี `name_en` สะกดต่างกันจริง 4 วิชา (ไม่ใช่แค่ field ที่ไม่ถูกใช้เทียบแบบ IT) เช่น coop เขียน `"...FORBUSINESS"` ติดกัน ส่วน no_coop เขียนแยก `"...FOR BUSINESS"` (หรือกลับกัน) รันแล้วผลจริงคือ **name_en agreement เท่ากันทั้งคู่ (85.5%)** แต่เป็นเพราะวิชาที่ mismatch สลับคู่กันพอดี (วิชาหนึ่ง match เฉพาะกับ coop, อีกวิชา match เฉพาะกับ no_coop) จำนวนสุทธิเลยเท่ากันโดยบังเอิญ ไม่ใช่เพราะข้อมูลเหมือนกันทุกประการแบบ DSBA — `name_en_wer` ต่างกันเล็กน้อย (coop 8.8% / no_coop 6.8%) ยืนยันว่าไม่ใช่ไฟล์เดียวกันจริงๆ ยังคงรันทั้งคู่ไว้เพื่อความสม่ำเสมอ

### วิธีรัน

```bash
python -m ocr_system.cli curriculum outputs/ait/ait_curriculum_ocr.json --ground-truth data/ground_truth/AIT_academic_plan.json --program AIT --plan none --output-dir outputs/ait

python -m ocr_system.cli curriculum outputs/it/it_curriculum_ocr.json --ground-truth data/ground_truth/IT_academic_plan_coop.json --program IT --plan coop --output-dir outputs/it

python -m ocr_system.cli curriculum outputs/bit/bit_curriculum_ocr.json --ground-truth data/ground_truth/BIT_academic_plan_coop.json --program BIT --plan coop --output-dir outputs/bit

python -m ocr_system.cli curriculum outputs/bit/bit_curriculum_ocr.json --ground-truth data/ground_truth/BIT_academic_plan_no_coop.json --program BIT --plan no_coop --output-dir outputs/bit
```

หมายเหตุ: คำสั่ง `curriculum` เขียนผลลัพธ์เป็น `outputs/bit/bit_curriculum_courses.json`/`outputs/bit/bit_curriculum_curriculum_evaluation.json` เสมอ (ไม่แยกชื่อไฟล์ตาม plan เหมือน `lab6_evaluate.py`) รันสองรอบแล้วต้อง copy ผลของรอบแรกไปเก็บชื่ออื่นก่อนรันรอบสอง ไม่งั้นไฟล์จะถูกเขียนทับ — ผลที่เก็บไว้จริงในโปรเจกต์คือ `outputs/bit/bit_coop_curriculum_courses.json`/`outputs/bit/bit_coop_curriculum_evaluation.json` (สำรองจากรอบ coop) และ `outputs/bit/bit_curriculum_courses.json`/`outputs/bit/bit_curriculum_curriculum_evaluation.json` (ผลรอบ no_coop ล่าสุด)

### ไฟล์ที่เกี่ยวข้อง

```text
src/ocr_system/preprocessing.py         suppress_warm_watermark() (ใหม่)
src/ocr_system/curriculum_extraction.py แก้ _looks_english() + _join_english_name()
src/ocr_system/evaluate_curriculum.py   เพิ่ม CER/WER ต่อ field (name_en, name_th)
outputs/ait/ait_curriculum_courses.json, ait_curriculum_curriculum_evaluation.json
outputs/it/it_curriculum_courses.json, it_curriculum_curriculum_evaluation.json
outputs/bit/bit_curriculum_courses.json, bit_curriculum_curriculum_evaluation.json (no_coop)
outputs/bit/bit_coop_curriculum_courses.json, bit_coop_curriculum_evaluation.json (coop, สำรองแยกไว้)
```

---

## Ground Truth Page Mapping (Lab 5)

ต่อยอดจาก Lab 4 — โจทย์คือแมพแต่ละวิชาใน Ground Truth เข้ากับหน้าจริงของเล่มหลักสูตร ทำเป็นไฟล์ CSV ที่บอกได้ว่า GT แต่ละวิชามาจากหน้าไหน พร้อมชุดคำถาม-คำตอบที่อ้างอิงหน้าได้ (รวมข้อบังคับสถาบันฯ) — ครอบคลุมทั้ง 4 หลักสูตร (DSBA/AIT/IT/BIT) เช่นเดียวกับ Lab 4 รายละเอียดด้านล่างใช้ DSBA (`DSBA_academic_plan_coop.json`, `data/input/dsba_curriculum.pdf`) เป็นตัวอย่างหลัก ส่วนผลลัพธ์ AIT/IT/BIT ดูที่หัวข้อ "AIT / IT / BIT Page Mapping" ท้ายส่วนนี้

### Ground Truth ที่ใช้

| Field | ค่า |
|---|---|
| ไฟล์ | `data/ground_truth/DSBA_academic_plan_coop.json` |
| source | GT_Template-2.xlsx / Academic Plan GT — DSBA coop |
| program | DSBA |
| plan | coop |

ไม่ได้ใส่ `source` เป็นคอลัมน์ใน `course_page_mapping.csv` เพราะรันจาก GT ไฟล์เดียว ทุกแถวจะมีค่าเดียวกันหมด (ต่างจาก `program`/`plan` ที่ตอบโจทย์ "หลักสูตรไหน" ตรงๆ) เลยเก็บ provenance ระดับไฟล์ไว้ที่นี่แทน — ถ้าในอนาคตรวมหลาย GT เป็น CSV เดียวค่อยพิจารณาเพิ่มคอลัมน์นี้

### Pipeline

```text
outputs/dsba/dsba_curriculum_ocr.json (มีอยู่แล้วจาก Lab 4)
    → curriculum_extraction.py (extract_curriculum, เก็บ page number ต่อ occurrence)
    → gt_page_mapping.py (group_by_code → classify_pages → เทียบกับ GT)
    → outputs/dsba/dsba_coop_course_page_mapping.csv
```

### วิธีรัน

```bash
python scripts/lab5_page_mapping.py DSBA_coop
python scripts/lab5_qa_pairs.py
```

(`lab5_page_mapping.py` แก้ให้รับ program+plan เป็น argument แล้วแทนการ hardcode DSBA ตัวเดียว — ดูหัวข้อ "AIT / IT Page Mapping (Lab 5 ต่อ)" ท้าย Lab 5 สำหรับ AIT/IT/no_coop)

ผลลัพธ์ที่ได้:
```text
outputs/dsba/dsba_coop_course_page_mapping.csv    80 วิชา พร้อมหน้าอ้างอิง (primary/other)
outputs/qa_pairs.csv                              32 คำถาม-คำตอบ อ้างอิงหน้า (ครอบคลุม DSBA/AIT/IT/BIT)
```

### สิ่งที่แก้ใน `curriculum_extraction.py` (Lab 4) และทำไม

Lab 5 ต้องรู้ว่าแต่ละ course record มาจากหน้าไหน แต่ Lab 4 ไม่เคยเก็บเลขหน้าไว้ในผลลัพธ์เลย (ทั้งที่ `_extract_page_courses` มีเลขหน้าอยู่ในมืออยู่แล้วตอน loop) จึงแก้ 2 จุด:

1. เติม parameter `page_no` ให้ `_course_from_text()` และใส่ค่าเป็น key `"page"` ในผลลัพธ์ — เป็นการเติม field ใหม่แบบ additive ไม่กระทบ field เดิมที่ `evaluate_curriculum.py` ใช้เทียบ (name_en, credits) เลย
2. แก้บั๊กใน `_trim_block_text()` — footer token `"มคอ"` (มาจากแบบฟอร์ม มคอ.3) ไปแมตช์ substring กลางคำ **"คอมพิวเตอร์"** โดยบังเอิญ (…โปรแกร**มคอ**มพิวเตอร์…) ทำให้ block ถูกตัดก่อนถึงหน่วยกิตของทุกวิชาที่ชื่อมีคำว่า "คอมพิวเตอร์" อยู่ก่อนหน่วยกิต (กระทบ `06066303`, `06026203`) แก้โดยให้เริ่มค้นหา footer token **หลัง**ตำแหน่งที่เจอ credits pattern แล้วเท่านั้น

หมายเหตุ: การแก้บั๊กข้อ 2 ทำให้ตัวเลข evaluation ของ Lab 4 ดีขึ้นเล็กน้อยจากที่เคยรายงานไว้ — แก้ไว้ตรงนี้อย่างโปร่งใส ไม่ใช่แก้แบบเงียบๆ

### หลักการทำงานของ mapping

`gt_page_mapping.py` ทำงานเป็น 5 ขั้น (ไม่ใช่แค่ "เทียบ OCR กับ GT" เฉยๆ):

1. **ดึงทุกครั้งที่เจอรหัสวิชา (ไม่ merge)** — `extract_curriculum()` ไล่อ่านทุกหน้า หารหัสวิชา ตัด block ข้อความระหว่างรหัสสองตัวที่ติดกัน แยกเป็นชื่อไทย/อังกฤษ/หน่วยกิต รหัสเดียวกันอาจโผล่ได้หลายหน้า (ตารางหลักสูตรจริง, หน้าดัชนี, หน้าภาระงานสอนอาจารย์) ขั้นนี้เก็บไว้ทุกครั้งที่เจอ ไม่ทิ้งอันไหน

2. **จัดกลุ่มตามรหัส** — `group_by_code()` รวม occurrence ทั้งหมดเป็น `{รหัสวิชา: [occurrence ทั้งหมด]}`

3. **เทียบแต่ละ occurrence กับ GT** — `classify_pages()` normalize ค่าทั้งสองฝั่งก่อน (ยุบช่องว่าง/ตัดขึ้นบรรทัดใหม่/ตัวพิมพ์ใหญ่) แล้วถือว่าเป็น **primary page** ถ้า `name_en` **หรือ** `name_th` **หรือ** `credits` ตรงกับ GT ข้อใดข้อหนึ่ง (ไม่ต้องตรงทุก field) ที่เหลือเป็น **other page** — เลือกเกณฑ์ OR เพราะ OCR มี noise เยอะ (เจอเคสจริงที่หน้า 30: credits ตรงแต่ name_en เพี้ยนเพราะ block ปนกับวิชาถัดไป ถ้าบังคับต้องตรงหมดจะพลาดหน้าจริงไปฟรีๆ)

4. **fallback ด้วยชื่อวิชา** — ถ้าวิชาไหนหารหัสไม่เจอเลยในเอกสาร (เช่น `06016401`) จะค้นหาด้วยชื่อวิชาแทน บันทึกหน้าที่เจอไว้เป็นหลักฐาน (แต่ไม่นับ primary เพราะไม่ได้ยืนยันด้วยรหัส)

5. **เขียนผลลัพธ์** — ได้ 80 แถว (1 แถวต่อวิชาใน GT) พร้อม `primary_pages`/`other_pages` → `write_csv()`

### รูปแบบคอลัมน์ `primary_pages` / `other_pages`

ถ้าวิชาหนึ่งเจอมากกว่า 1 หน้า จะเก็บเลขหน้าทั้งหมดไว้ในคอลัมน์เดียว คั่นด้วย `;` (เช่น `17;30;314`) ไม่ใช้ `,` เพราะ `,` เป็นตัวแบ่งคอลัมน์หลักของ CSV เองอยู่แล้ว — ถ้าเอาไปใช้แบ่งเลขหน้าในคอลัมน์เดียวกันด้วย จะต้องพึ่ง quote (`"17,30,314"`) ถึงจะไม่พัง และยังอ่านด้วยตาเปล่ายากเวลาเปิดไฟล์แบบ raw text หรือถ้ามีใครประมวลผลต่อด้วยการ split ธรรมดาไม่ผ่าน CSV parser ที่รู้เรื่อง quote ก็จะพังทันที ใช้ `;` แทนจึงชัดเจนและปลอดภัยกว่า

### ผลลัพธ์

| Metric | ผลลัพธ์ |
|---|---|
| GT courses ทั้งหมด | 80 |
| เจอด้วยรหัสวิชา + มี primary page | 79 (98.75%) |
| เจอด้วยชื่อวิชาเท่านั้น (fallback) | 1 |
| หาไม่เจอเลย | 0 |

### Known Limitations

- **`06016401`** — เหมือนที่ระบุไว้ใน Lab 4: รหัสวิชานี้ไม่ปรากฏในเอกสาร OCR เลย พบเพียงชื่อวิชาในหน้าภาระงานสอนอาจารย์ (หน้า 49) จึงนับเป็น name-only match ไม่ใช่ primary page
- **หน้า 30** — วิชา `06026200` มี `name_en` ปนเปื้อนจากวิชาถัดไป เพราะรหัส `06026202` หายไปจาก OCR บนหน้านี้ (ทำให้ `06026202` ไม่ได้เครดิตหน้า 30 ทั้งที่ควรจะมี) เป็นข้อจำกัดจากคุณภาพ OCR ต้นทาง ไม่ใช่บั๊กของ mapping script
- **ข้อบังคับสถาบันฯ (หน้า 89-108)** — OCR คุณภาพต่ำกว่าส่วนอื่นมาก (เลขไทยอ่านผิดบ่อย มีตัวอักษรละตินมั่วปน) คำถามข้อบังคับที่เขียนไว้เลือกเฉพาะข้อความที่อ่านได้ชัดเจนเท่านั้น

### ไฟล์ที่เกี่ยวข้อง

```text
src/ocr_system/curriculum_extraction.py   แก้เพิ่ม page number + แก้บั๊ก "มคอ" (ไฟล์ Lab 4, แก้ต่อใน Lab 5)
src/ocr_system/gt_page_mapping.py         group_by_code / classify_pages / write_csv (ใหม่, Lab 5)
scripts/lab5_page_mapping.py             รัน pipeline สร้าง course_page_mapping.csv ต่อ program+plan
scripts/lab5_qa_pairs.py                 ชุดคำถาม-คำตอบ (ปัจจุบัน 32 ข้อ ครอบคลุม DSBA/AIT/IT/BIT) พร้อมเลขหน้าอ้างอิง
outputs/dsba/dsba_coop_course_page_mapping.csv 80 วิชา พร้อม primary/other pages
outputs/qa_pairs.csv                           32 คำถาม-คำตอบ (16 รายวิชา + 16 ข้อบังคับ) -- ดูจำนวน ณ ตอนเขียน Lab 5 นี้คือ 17 ข้อ (DSBA ล้วน) ก่อนขยายไป AIT/IT/BIT ทีหลัง (ดูหัวข้อ Lab 6 Known Limitations)
```

---

## AIT / IT / BIT Page Mapping (Lab 5 ต่อ)

เช่นเดียวกับ Lab 4 — Lab 5 ครอบคลุมทั้ง 4 หลักสูตร (DSBA/AIT/IT/BIT) ไม่ใช่แค่ DSBA ตัวอย่าง pipeline/คำสั่งด้านบนโชว์แค่ DSBA (coop) เพื่อไม่ให้ซ้ำ ส่วนนี้คือผลลัพธ์เฉพาะของ AIT/IT/BIT ใช้ `gt_page_mapping.py` เดิมทั้งหมดโดยไม่แก้โค้ดเลย (`group_by_code()` / `classify_pages()` / `write_csv()` รับ program, plan, output path เป็นพารามิเตอร์อยู่แล้ว) เพียงแก้ `scripts/lab5_page_mapping.py` ให้รับ program+plan จาก command line แทนการ hardcode เป็น DSBA ตัวเดียว

### ทำไมต้องรันแยกทั้ง coop และ no_coop (ไม่ใช่แค่แยก program)

`evaluate_curriculum.py` (Lab 4) เช็คแค่ `name_en` / `name_th` / `credits` ซึ่งเหมือนกันทุกประการระหว่างไฟล์ coop/no_coop ของทั้ง DSBA และ IT — แต่ `classify_pages()` (Lab 5) เขียน `year` / `semester` / `flexible_year_semester` / `note` ลง CSV ตรงจาก GT โดยตรง ตรวจสอบแล้วว่า **IT** มี 57/99 วิชาที่ field เหล่านี้ต่างกันจริงระหว่าง coop/no_coop (เช่นวิชาเดียวกันเรียนปี 4 เทอม 2 ในแผน coop แต่ปี 3 เทอม 2 ในแผน no_coop) ถ้ารันแค่ไฟล์เดียวจะโชว์ปี/เทอมผิดให้นักศึกษาอีกแผน จึงต้องรันแยกทั้งคู่สำหรับ IT ส่วน DSBA เหมือนกัน 100% ทุก field แต่รันแยกไว้ด้วยเพื่อความสม่ำเสมอ ไม่ต้องให้คนอ่านต้องรู้ก่อนว่าไฟล์เหมือนกัน **BIT** อยู่ตรงกลาง — 5/60 วิชามี `year`/`semester`/`note` ต่างกันจริงระหว่าง coop/no_coop (น้อยกว่า IT มาก แต่ไม่ใช่ศูนย์) จึงยังต้องรันแยกทั้งคู่เหมือนกัน

### ผลลัพธ์

| Program | Plan | ไฟล์ | GT courses | with primary page |
|---|---|---|---|---|
| DSBA | coop | `outputs/dsba/dsba_coop_course_page_mapping.csv` | 80 | 79 (98.75%) |
| DSBA | no_coop | `outputs/dsba/dsba_no_coop_course_page_mapping.csv` | 80 | 79 (98.75%) |
| AIT | none | `outputs/ait/ait_course_page_mapping.csv` | 49 | 48 (97.96%) |
| IT | coop | `outputs/it/it_coop_course_page_mapping.csv` | 99 | 99 (100%) |
| IT | no_coop | `outputs/it/it_no_coop_course_page_mapping.csv` | 99 | 99 (100%) |
| BIT | coop | `outputs/bit/bit_coop_course_page_mapping.csv` | 55 | 55 (100%) |
| BIT | no_coop | `outputs/bit/bit_no_coop_course_page_mapping.csv` | 55 | 55 (100%) |

(DSBA coop และ no_coop ให้ตัวเลขเดียวกันเป๊ะตามที่คาด เพราะ GT เหมือนกัน 100% ทุก field ที่ใช้ matching — BIT ให้ตัวเลขรวมเท่ากันด้วย แม้ GT จะไม่ได้เหมือนกันทุกประการเหมือน DSBA ก็ตาม เพราะทุกวิชาหารหัสเจอครบทั้งสองแผนอยู่แล้ว)

### วิธีรัน

```bash
python scripts/lab5_page_mapping.py DSBA_coop
python scripts/lab5_page_mapping.py DSBA_no_coop
python scripts/lab5_page_mapping.py AIT
python scripts/lab5_page_mapping.py IT_coop
python scripts/lab5_page_mapping.py IT_no_coop
python scripts/lab5_page_mapping.py BIT_coop
python scripts/lab5_page_mapping.py BIT_no_coop
```

### คำถามเพิ่มจาก ground truth ใหม่ (`rules_ground_truth.json`)

`outputs/qa_pairs.csv` เดิมมี 15 ข้อ (DSBA เท่านั้น) เพิ่มอีก 2 ข้อจาก `rules_ground_truth.json` (program DSBA) รวมเป็น 17 ข้อ:

- **เกณฑ์เกียรตินิยม** — GPA ตั้งแต่ 3.75 ขึ้นไปได้เหรียญทอง, ตั้งแต่ 3.50 ขึ้นไปได้อันดับ 1 (เกณฑ์อันดับ 2 ไม่มีค่าระบุในไฟล์ต้นทาง)
- **เกณฑ์การลงทะเบียน** — ขั้นต่ำ 9 หน่วยกิต สูงสุด 22 หน่วยกิตต่อภาคปกติ (เพดานกรณีพิเศษไม่มีค่าระบุในไฟล์ต้นทาง)

ค่าที่ขาด (`null`) ในไฟล์ต้นทางไม่ได้เดาเติมเอง ระบุตรงๆ ในคำตอบว่า "ไม่มีข้อมูล" แทน และค่าที่เขียนเป็น `"<3.75"` / `"<3.50"` ในไฟล์ต้นทางถูกตีความใหม่เป็น "ตั้งแต่ ... ขึ้นไป" ให้ตรงความหมายจริง (เกณฑ์ขั้นต่ำ ไม่ใช่ขั้นสูง) ไม่ได้ copy เครื่องหมาย `<` ตรงๆ

ทั้งสองข้อเป็น `type: regulation` เหมือนกลุ่มเดิม — ไม่กระทบ "QA citation consistency" ของ Lab 6 เลย เพราะ `evaluate_page_level()` เช็คเฉพาะแถวที่ `type == "course"` เท่านั้น (ตัวเลข 6/6 ในหัวข้อ Lab 6 ด้านล่างยังถูกต้องอยู่)

อัปเดต: คำถามเฉพาะของ AIT/IT/BIT ถูกเพิ่มเข้ามาแล้วในภายหลัง (คนละรอบกับตอนเขียน Lab 5 นี้) รวมทั้งหมดเป็น 32 ข้อ — รายละเอียดอยู่ที่หัวข้อ Lab 6 Known Limitations ด้านล่าง ส่วน `general_education_ground_truth.json` ยังคงใช้แค่ยืนยันข้อเท็จจริงเดิม (เช่น CHARM SCHOOL) ยังไม่ได้แต่งเป็นคำถามใหม่

### ไฟล์ที่เกี่ยวข้อง

```text
scripts/lab5_page_mapping.py   parameterize รับ program+plan (PROGRAMS dict) แทน hardcode DSBA
scripts/lab5_qa_pairs.py       เพิ่ม 2 entry จาก rules_ground_truth.json (ตอนเขียน Lab 5 นี้ -- ภายหลังขยายเป็น 32 ข้อรวม AIT/IT/BIT)
outputs/ait/ait_course_page_mapping.csv
outputs/dsba/dsba_no_coop_course_page_mapping.csv
outputs/it/it_coop_course_page_mapping.csv
outputs/it/it_no_coop_course_page_mapping.csv
outputs/bit/bit_coop_course_page_mapping.csv
outputs/bit/bit_no_coop_course_page_mapping.csv
outputs/qa_pairs.csv                          32 คำถาม-คำตอบ (16 รายวิชา + 16 ข้อบังคับ, ครอบคลุม DSBA/AIT/IT/BIT)
```

---

## Combined Evaluation — Field / Page / Category Level (Lab 6)

Lab 6 ไม่ได้ใช้ dataset ใหม่ — รัน dataset เดิมจาก Lab 4/5 ทั้งชุด (OCR output +
ground truth + page mapping ของ Lab 5) ผ่าน evaluation เดียวกัน แล้วรายงาน 3
ระดับ ครอบคลุมทั้ง 4 หลักสูตร (DSBA/AIT/IT/BIT) เช่นเดียวกับ Lab 4/5:

- **Field Level** — accuracy รายฟิลด์ (`name_en`, `credits`) ของวิชาที่ match ได้
  + recall โดยรวม + **CER/WER** ของ `name_en`/`name_th` (แนวคิดเดียวกับ
  `evaluate_curriculum.py` ของ Lab 4 — เพิ่มเข้ามาทีหลังตามคำแนะนำอาจารย์
  ให้ใช้ CER/WER ในการ evaluate ด้วย)
- **Page Level** — สัดส่วนวิชาที่ระบุ primary page ได้ (page mapping ของ Lab 5)
  บวก sanity check ว่า `cited_pages` ใน `outputs/qa_pairs.csv` ตรงกับหน้าที่
  mapping หาได้จริงหรือไม่ (เฉพาะคำถาม `type: course` ที่มีรหัสวิชาฝังใน `note`)
- **Category Level** — เอา metric ของ Field/Page Level ข้างต้นมาแยกตาม field
  `category` ของ ground truth (หมวดวิชาเฉพาะ / หมวดวิชาศึกษาทั่วไป)

(หมายเหตุ: ตอนแรกมีมุมมองรองแยกตาม field `type` (บังคับ / เลือก) ด้วย แต่ตัดออก
แล้ว เพราะ `type` เป็นคนละ field กับ `category` — ทำให้ dataclass/summary
เรียบง่ายขึ้น เหลือมิติเดียวตามที่โจทย์ระบุ)

extraction ถูกรันใหม่จาก `*_curriculum_ocr.json` ของแต่ละหลักสูตรทุกครั้ง (ไม่ได้
อ่านผลลัพธ์เก่าที่ค้างไว้) จึงสะท้อนการแก้บั๊ก OCR/extraction ล่าสุดเสมอ

### วิธีรัน

```bash
python scripts/lab6_evaluate.py DSBA_coop
python scripts/lab6_evaluate.py DSBA_no_coop
python scripts/lab6_evaluate.py AIT
python scripts/lab6_evaluate.py IT_coop
python scripts/lab6_evaluate.py IT_no_coop
python scripts/lab6_evaluate.py BIT_coop
python scripts/lab6_evaluate.py BIT_no_coop
```

### ผลลัพธ์ล่าสุด (รันจริงกับ dataset นี้ ทั้ง 7 ชุด)

| Program | Plan | recall | name_en | credits | name_en CER/WER | name_th CER/WER | page primary | QA citation |
|---|---|---|---|---|---|---|---|---|
| DSBA | coop | 98.8% | 98.7% | 100.0% | 1.2% / 1.3% | 4.4% / 44.3% | 79/80 | 6/6 |
| DSBA | no_coop | 98.8% | 98.7% | 100.0% | 1.2% / 1.3% | 4.4% / 44.3% | 79/80 | 6/6 |
| AIT | (ไม่มี coop) | 98.0% | 97.9% | 100.0% | 0.5% / 0.4% | 3.6% / 36.5% | 48/49 | 2/2 |
| IT | coop | 100.0% | 97.0% | 99.0% | 1.1% / 1.6% | 12.6% / 47.0% | 99/99 | 2/2 |
| IT | no_coop | 100.0% | 97.0% | 99.0% | 1.1% / 1.6% | 12.6% / 47.0% | 99/99 | 2/2 |
| BIT | coop | 100.0% | 85.5% | 98.2% | 0.2% / 8.8% | 4.2% / 49.1% | 55/55 | 2/2 |
| BIT | no_coop | 100.0% | 85.5% | 98.2% | 0.2% / 6.8% | 4.2% / 49.1% | 55/55 | 2/2 |

Category Level (ทุกโปรแกรมแบ่งได้แค่ 2 กลุ่ม — ดูสาเหตุใน Known Limitations):

| Program | Category | n | recall | name_en | page_localized |
|---|---|---|---|---|---|
| DSBA | หมวดวิชาเฉพาะ | 72 | 98.6% | 98.6% | 98.6% |
| DSBA | หมวดวิชาศึกษาทั่วไป | 8 | 100% | 100% | 100% |
| AIT | หมวดวิชาเฉพาะ | 41 | 97.6% | 97.5% | 97.6% |
| AIT | หมวดวิชาศึกษาทั่วไป | 8 | 100% | 100% | 100% |
| IT | หมวดวิชาเฉพาะ | 91 | 100% | 98.9% | 100% |
| IT | หมวดวิชาศึกษาทั่วไป | 8 | 100% | 75.0% | 100% |
| BIT | หมวดวิชาเฉพาะ | 47 | 100% | 85.1% | 100% |
| BIT | หมวดวิชาศึกษาทั่วไป | 8 | 100% | 87.5% | 100% |

### Known Limitations

- **`หมวดวิชาเลือกเสรี` หายไปจาก Category Level** — ground truth มี category ที่ 3
  คือ `หมวดวิชาเลือกเสรี` (free elective, 2 รายการ) แต่ทั้งสองรายการใช้ code เป็น
  placeholder `"xxxxxxxx"` (ยังไม่ระบุว่านักศึกษาจะเลือกวิชาอะไรจริง) ซึ่งไม่ผ่าน
  `_is_valid_code()` (ต้องเป็นตัวเลขล้วน) เลยถูกกรองทิ้งตั้งแต่ตอนสร้าง
  `gt_courses` ก่อนจะถึงขั้น group by category ผลคือ Category Level เห็นแค่ 2
  กลุ่ม (เฉพาะ/ทั่วไป) ไม่ใช่ 3 กลุ่มตาม ground truth จริง — เป็น filter เดิมที่
  สืบทอดมาจาก Lab 4 (`evaluate_curriculum.py` กรองแบบเดียวกัน) จึงกระทบ
  Field Level และ Page Level ด้วยเช่นกัน (BIT ก็มี `หมวดวิชาเลือกเสรี` แบบเดียวกัน
  2 รายการ โดน filter ทิ้งเหมือนกัน)
- **หมวดวิชาศึกษาทั่วไปของ IT, name_en 75%** — ต่ำกว่า DSBA/AIT (100%) เพราะ n=8
  เล็ก แค่ 2 วิชาผิดก็กระทบเปอร์เซ็นต์แรง ไม่ใช่ปัญหาเชิงระบบ (ดูหัวข้อ
  `general_education_ground_truth.json` แยกต่างหากสำหรับปัญหา OCR ที่ใหญ่กว่านี้
  ในโซนวิชาศึกษาทั่วไปของเล่ม IT)
- **หมวดวิชาเฉพาะของ BIT, name_en 85.1%** — ต่ำกว่าโปรแกรมอื่น แต่ตรวจสอบทุก
  mismatch แล้วพบว่า 7 ใน 8 รายการมี CER ≈ 0 (ตัวอักษรถูกหมด ต่างแค่ช่องว่างที่
  หายไปฝั่ง ground truth เอง เช่น GT เขียน `"SPECIALTOPICS..."` ติดกัน แต่สิ่งที่
  extract ได้ถูกต้องเป็น `"SPECIAL TOPICS..."`) มีแค่ `CHARM SCHOOL` ตัวเดียวที่
  OCR ผิดจริง (คอมม่าเกิน) — recall และ page localization ยังคง 100% ทั้งคู่ ไม่ใช่
  ปัญหาเชิงระบบ
- **CHARM SCHOOL (90641001) เช็ค cross-program ผิดพลาด (แก้แล้ว)** — คำถาม QA
  เดิมของ DSBA อ้างอิงเลขหน้าตามเล่ม DSBA แต่ 90641001 เป็นวิชาศึกษาทั่วไปที่
  ปรากฏในเล่ม IT ด้วย (คนละเลขหน้า) ตอนรัน Lab 6 กับ IT ระบบเลยเอาเลขหน้าของ
  DSBA ไปเทียบกับเล่ม IT แล้ว flag ว่า mismatch ทั้งที่ทั้งสองฝั่งถูกทั้งคู่ แก้โดย
  เพิ่มคอลัมน์ `program` ใน `qa_pairs.csv` และให้ `evaluate_page_level()` ข้าม
  แถวที่ `program` ไม่ตรงกับโปรแกรมที่กำลังประเมิน — พร้อมเพิ่มคำถาม course-level
  ใหม่ให้ AIT/IT อย่างละ 2 ข้อ (ใช้ `cited_pages` จาก `{program}_course_page_mapping.csv`
  โดยตรง การันตี consistency) รวม `qa_pairs.csv` เป็น 27 ข้อ (14 course + 13 regulation)
  ณ ตอนนั้น — ต่อมาเพิ่ม BIT อีก 5 ข้อ (2 course + 3 regulation จาก
  `rules_ground_truth.json`) รวมปัจจุบันเป็น 32 ข้อ (16 course + 16 regulation)

### ไฟล์ที่เกี่ยวข้อง

```text
src/ocr_system/evaluate_lab6.py   evaluate_field_level (+ CER/WER) / evaluate_page_level (+ program filter) / evaluate_category_level
scripts/lab6_evaluate.py          รัน pipeline รวมทั้ง 3 ระดับ ต่อ program+plan
scripts/lab5_qa_pairs.py         QA_PAIRS 32 ข้อ พร้อมคอลัมน์ program
outputs/{program}/{key}_lab6_evaluation.json   ผลลัพธ์ต่อ program+plan (7 ไฟล์ ในโฟลเดอร์ย่อยของแต่ละหลักสูตร)
```

---

## General Education Ground Truth (ส่วนเสริม)

`data/ground_truth/general_education_ground_truth.json` เป็น ground truth ของวิชา
ศึกษาทั่วไป (266 วิชา) ที่ใช้ร่วมกันทุกหลักสูตร ไม่ได้ผูกกับ program ใดโดยเฉพาะ —
ทดสอบโดยเอา courses ที่ extract ไว้แล้วจาก Lab 4 (`{program}_curriculum_courses.json`)
มาเทียบกับไฟล์นี้ผ่าน `evaluate_curriculum()` ตัวเดิม ไม่ต้องเขียนโค้ดใหม่เลย

### วิธีรัน

```bash
python scripts/supplement_general_education.py
```

### ผลลัพธ์

| Curriculum book | Recall | name_en agreement | credits agreement | name_en CER/WER |
|---|---|---|---|---|
| DSBA | 100% (266/266) | 83.5% | 99.3% | 3.8% / 6.7% |
| AIT | 82.7% (220/266) | 78.2% | 98.2% | 3.2% / 7.8% |
| IT | 82.0% (218/266) | **31.2%** | 78.0% | **38.4% / 56.3%** |

### Known Limitations

- **IT: name_en agreement ต่ำผิดปกติ (31.2%)** — สืบสาเหตุแล้วพบว่าไม่ใช่ปัญหา
  ลายน้ำ (เช็ค pixel ratio ของ warm-color mask บนหน้า 136/137/164 ได้ 73-79%
  ใกล้เคียงหน้า 19 ที่ตารางหลักสูตรหลักทำงานได้ดี 97% แปลว่าลายน้ำถูกลบเหมือนกัน
  ทุกหน้า ไม่ใช่ตัวแปรที่ทำให้ต่างกัน) สาเหตุจริงคือโซนภาคผนวกรายชื่อวิชาเลือกเสรี
  ของ IT (หน้าประมาณ 134-287, กระจายกว่า 60 หน้า) มีคุณภาพ OCR แย่กว่าตาราง
  หลักสูตรหลักมาก ถึงขั้นที่**ตัวเลขในรหัสวิชาเองถูกอ่านผิด** เช่น `90642011` ถูก
  อ่านเป็น `9ดธ42011` (ตัวเลขไทยปนตัวอักษร), `90642014` เป็น `90612014`
  (เลข 4→1 สลับ) — พอรหัสไม่ตรง 8 หลักสะอาดตาม `CODE_FIND_RE` ระบบจำไม่ได้ว่า
  เป็นวิชาใหม่ บล็อกข้อความของวิชานั้นเลยไปปนกับวิชาก่อนหน้าแทน ได้ผลลัพธ์เป็น
  ชื่อเพี้ยนหรือ `None`
  - เปิดดู PDF จริงแล้วยืนยันว่าโซนนี้มีทั้งลายน้ำและตารางที่แน่น/ฟอนต์เล็กกว่า
    ตารางหลักสูตรหลักอย่างชัดเจน
  - ไม่ได้พยายามแก้ เพราะการแก้จริงต้องทำ fuzzy-match รหัสวิชา (ยอมรับตัวอักษร
    ผิด 1-2 ตัวแล้วเดารหัสที่ใกล้เคียงที่สุด) ซึ่งมีความเสี่ยงสูง/ผลไม่แน่นอน
    คล้ายกับ heuristic merge ที่เคยลองทำใน Lab 4 แล้วต้อง revert (ดูหมายเหตุใน
    `_merge_duplicate_courses()` ของ `evaluate_curriculum.py`)
  - ผลกระทบจำกัดอยู่แค่การเทียบกับ `general_education_ground_truth.json` เท่านั้น
    — ไม่กระทบ Lab 4/5/6 หลักที่ใช้ ground truth เฉพาะของแต่ละหลักสูตรเอง (ตาราง
    หลักสูตรบังคับ ไม่ใช่ภาคผนวกวิชาเลือกเสรี)
- **AIT/IT recall ต่ำกว่า DSBA (82% vs 100%)** — ยังไม่ได้ลงลึกสาเหตุเพิ่มเติมว่า
  ทำไม DSBA หาเจอครบทุกวิชา ขณะที่ AIT/IT หาไม่เจอ ~18% (น่าจะเกี่ยวข้องกับ
  ปัญหาเดียวกันข้างต้น คือรหัสวิชาอ่านผิดจนหาไม่เจอเลย ไม่ใช่แค่ชื่อเพี้ยน)
- **BIT ไม่รวมอยู่ในตารางผลลัพธ์ข้างบน — ตั้งใจ ไม่ใช่ตกหล่น** — ตรวจสอบแล้วว่า
  รหัสวิชาหมวดวิชาศึกษาทั่วไปของ BIT เอง (ใน `BIT_academic_plan_coop.json`,
  category `หมวดวิชาศึกษาทั่วไป`) ใช้ช่วงรหัส `9664xxxx` ทั้งหมด ไม่ทับซ้อนกับ
  `general_education_ground_truth.json` เลยแม้แต่รหัสเดียว (ไฟล์นั้นใช้ช่วง
  `9064xxxx` ซึ่งเป็นชุดที่ DSBA/AIT/IT ใช้ร่วมกัน) พบ overlap เล็กน้อยแค่ 6 รหัส
  ระหว่างรหัสวิชาที่ OCR เจอทั้งหมดในเล่ม BIT (580 รหัสไม่ซ้ำ ทั้งเล่ม) กับ
  `9064xxxx` แต่เป็นแค่การกล่าวถึงในภาคผนวก catalog ของสถาบัน ไม่ใช่ตัวข้อกำหนด
  หมวดวิชาศึกษาทั่วไปของ BIT เอง — รันเทียบกับไฟล์นี้จะได้ recall ใกล้ 0% ซึ่ง
  ไม่มีความหมาย เพราะเทียบกับข้อกำหนดที่ BIT ไม่ได้ใช้จริง ข้อกำหนดหมวดวิชา
  ศึกษาทั่วไปของ BIT ถูกประเมินไปแล้วผ่าน Lab 6 Category Level (ดูหัวข้อ Lab 6
  ด้านบน — recall 100%, name_en agreement 87.5%) ซึ่งเทียบกับ ground truth ของ
  BIT เองโดยตรง ถูกต้องกว่า

### ไฟล์ที่เกี่ยวข้อง

```text
scripts/supplement_general_education.py                รัน evaluate_curriculum() เทียบกับ general_education_ground_truth.json ทั้ง 3 หลักสูตร
outputs/dsba/general_education_dsba_evaluation.json
outputs/ait/general_education_ait_evaluation.json
outputs/it/general_education_it_evaluation.json
```
