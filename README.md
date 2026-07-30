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
│   ├── input/                 # ใส่ไฟล์ภาพหรือ PDF ที่ต้องการ OCR
│   └── ground_truth/          # ไฟล์เฉลยสำหรับ evaluate
├── outputs/                   # ผลลัพธ์ OCR และ evaluation
└── src/
    └── ocr_system/
        ├── cli.py             # command line interface
        ├── config.py          # config หลักของระบบ
        ├── document_loader.py # โหลดภาพ / แปลง PDF เป็นภาพ
        ├── preprocessing.py   # resize, denoise, contrast, deskew, threshold
        ├── pipeline.py        # OCR pipeline หลัก
        ├── evaluation.py      # CER, WER, exact match
        ├── field_extraction.py# ดึง field เช่น email, date, id, phone
        ├── curriculum_extraction.py # ดึง course records จากเอกสารหลักสูตร (Lab 4)
        ├── evaluate_curriculum.py   # วัดผล recall + field-level agreement (Lab 4)
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
outputs/dsba_curriculum_courses.json                 รายวิชาที่ดึงได้ทั้งหมด
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

---

## Ground Truth Page Mapping (Lab 5)

ต่อยอดจาก Lab 4 — โจทย์คือแมพแต่ละวิชาใน Ground Truth (`DSBA_academic_plan_coop.json`) เข้ากับหน้าจริงของเล่มหลักสูตร (`data/input/dsba_curriculum.pdf`) ทำเป็นไฟล์ CSV ที่บอกได้ว่า GT แต่ละวิชามาจากหน้าไหน พร้อมชุดคำถาม-คำตอบที่อ้างอิงหน้าได้ (รวมข้อบังคับสถาบันฯ)

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
outputs/dsba_curriculum_ocr.json (มีอยู่แล้วจาก Lab 4)
    → curriculum_extraction.py (extract_curriculum, เก็บ page number ต่อ occurrence)
    → gt_page_mapping.py (group_by_code → classify_pages → เทียบกับ GT)
    → outputs/course_page_mapping.csv
```

### วิธีรัน

```bash
python scripts/build_page_mapping.py
python scripts/build_qa_pairs.py
```

ผลลัพธ์ที่ได้:
```text
outputs/course_page_mapping.csv    80 วิชา พร้อมหน้าอ้างอิง (primary/other)
outputs/qa_pairs.csv               15 คำถาม-คำตอบ อ้างอิงหน้า
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
scripts/build_page_mapping.py             รัน pipeline สร้าง course_page_mapping.csv
scripts/build_qa_pairs.py                 ชุดคำถาม-คำตอบ 15 ข้อ พร้อมเลขหน้าอ้างอิง
outputs/course_page_mapping.csv           80 วิชา พร้อม primary/other pages
outputs/qa_pairs.csv                      15 คำถาม-คำตอบ (10 รายวิชา + 5 ข้อบังคับ)
```

---

## Combined Evaluation — Field / Page / Category Level (Lab 6)

Lab 6 ไม่ได้ใช้ dataset ใหม่ — รัน dataset เดิมจาก Lab 4/5 ทั้งชุด (OCR output +
ground truth + page mapping ของ Lab 5) ผ่าน evaluation เดียวกัน แล้วรายงาน 3
ระดับ:

- **Field Level** — accuracy รายฟิลด์ (`name_en`, `credits`) ของวิชาที่ match ได้
  + recall โดยรวม (แนวคิดเดียวกับ `evaluate_curriculum.py` ของ Lab 4)
- **Page Level** — สัดส่วนวิชาที่ระบุ primary page ได้ (page mapping ของ Lab 5)
  บวก sanity check ว่า `cited_pages` ใน `outputs/qa_pairs.csv` ตรงกับหน้าที่
  mapping หาได้จริงหรือไม่
- **Category Level** — เอา metric ของ Field/Page Level ข้างต้นมาแยกตาม field
  `category` ของ ground truth (หมวดวิชาเฉพาะ / หมวดวิชาศึกษาทั่วไป)

(หมายเหตุ: ตอนแรกมีมุมมองรองแยกตาม field `type` (บังคับ / เลือก) ด้วย แต่ตัดออก
แล้ว เพราะ `type` เป็นคนละ field กับ `category` — ทำให้ dataclass/summary
เรียบง่ายขึ้น เหลือมิติเดียวตามที่โจทย์ระบุ)

extraction ถูกรันใหม่จาก `outputs/dsba_curriculum_ocr.json` ทุกครั้ง (ไม่ได้อ่าน
ผลลัพธ์เก่าที่ค้างไว้) จึงได้ตัวเลขล่าสุดที่รวมการแก้บั๊ก "มคอ" ของ Lab 5 แล้ว —
`name_en agreement` และ `credits agreement` จึงสูงกว่าที่เคยรายงานไว้ใน Lab 4
(`outputs/dsba_curriculum_curriculum_evaluation.json` เป็นค่าก่อนแก้บั๊ก)

### วิธีรัน

```bash
python scripts/lab6_evaluate.py
```

ผลลัพธ์ล่าสุด (รันจริงกับ dataset นี้):

| Level | Metric | ผลลัพธ์ |
|---|---|---|
| Field | recall / name_en / credits | 98.8% / 98.7% / 100.0% |
| Page | with primary page | 79/80 (98.8%) |
| Page | QA citation consistency | 6/6 |
| Category (หมวดวิชาเฉพาะ, n=72) | recall / page_localized | 98.6% / 98.6% |
| Category (หมวดวิชาศึกษาทั่วไป, n=8) | recall / page_localized | 100% / 100% |

### Known Limitations

- **`หมวดวิชาเลือกเสรี` หายไปจาก Category Level** — ground truth มี category ที่ 3
  คือ `หมวดวิชาเลือกเสรี` (free elective, 2 รายการ) แต่ทั้งสองรายการใช้ code เป็น
  placeholder `"xxxxxxxx"` (ยังไม่ระบุว่านักศึกษาจะเลือกวิชาอะไรจริง) ซึ่งไม่ผ่าน
  `_is_valid_code()` (ต้องเป็นตัวเลขล้วน) เลยถูกกรองทิ้งตั้งแต่ตอนสร้าง
  `gt_courses` ก่อนจะถึงขั้น group by category ผลคือ Category Level เห็นแค่ 2
  กลุ่ม (เฉพาะ/ทั่วไป) ไม่ใช่ 3 กลุ่มตาม ground truth จริง — เป็น filter เดิมที่
  สืบทอดมาจาก Lab 4 (`evaluate_curriculum.py` กรองแบบเดียวกัน) จึงกระทบ
  Field Level และ Page Level ด้วยเช่นกัน (ทั้งคู่นับจากฐาน 80 วิชา ไม่ใช่ 91 วิชา
  เต็มในไฟล์ ground truth)

### ไฟล์ที่เกี่ยวข้อง

```text
src/ocr_system/evaluate_lab6.py   evaluate_field_level / evaluate_page_level / evaluate_category_level
scripts/lab6_evaluate.py          รัน pipeline รวมทั้ง 3 ระดับ ในคำสั่งเดียว
lab6_reference/                   ตัวอย่างเวอร์ชันแรก (มี type_level ด้วย) เก็บไว้เทียบเฉยๆ ไม่ใช่โค้ดที่ใช้จริง
```
