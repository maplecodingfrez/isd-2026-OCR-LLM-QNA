# Thai-English OCR System

> **Branch นี้ (`Lab-9`) เก็บเฉพาะงานของ Lab 9 (Evaluation & Overfitting)** ระบบเต็มที่รวมทุก Lab
> พร้อมวิธีติดตั้ง/ใช้งานล่าสุด ดูที่ branch `main`

โปรเจกต์นี้เป็น OCR pipeline สำหรับเอกสารภาพเดี่ยวและหลายหน้า เช่น `.jpg`, `.png`, `.tif`, `.pdf` โดยรองรับเอกสารภาษาไทยและอังกฤษปนกัน

OCR engines ที่มีให้:

- PaddleOCR: เหมาะกับภาษาไทยและเอกสารทั่วไป
- Tesseract OCR: ใช้ `tha+eng` ได้ดีเมื่อมีภาษาไทย/อังกฤษปนกัน
- TrOCR: OCR แบบ Transformer เหมาะกับ printed English เป็นหลัก
- Ensemble: ใช้ PaddleOCR + Tesseract แล้วรวมผลแบบง่าย

---

> **หมายเหตุ:** โครงสร้างโฟลเดอร์ที่ root นี้ (`src/`, `scripts/`, `outputs/`, `data/`) เป็นงาน
> **Lab 4-6** (OCR/extraction/evaluation รอบแรก) งานของ Lab 7B ขึ้นไปอยู่ในโฟลเดอร์แยกต่างหาก
> ระดับเดียวกับ root นี้: `Lab7B_curriculum/`, `Lab8b_ocr_system/`, `Lab9_evaluation/`

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
│   └── lab6_evaluate.py       # Lab 6: evaluate Field/Page/Category level แล้วเซฟแยกไฟล์ (json/json/csv)
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
        ├── evaluate_lab6.py         # evaluate_field_level / evaluate_page_level / evaluate_category_level / write_lab6_outputs (Lab 6)
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

## 5. รันเร็วขึ้นด้วย `--workers` (เอกสารหลายหน้า)

Pipeline เดิม render PDF เป็นภาพ + OCR ทีละหน้าเสมอ (sequential) ทั้งที่แต่ละหน้า
ไม่ขึ้นต่อกันเลย `--workers N` ให้ประมวลผลหลายหน้าพร้อมกัน (ทั้งขั้น render PDF ผ่าน
poppler's `thread_count` และขั้น OCR ผ่าน `ThreadPoolExecutor`) — **ไม่เปลี่ยน dpi,
preprocessing, หรือ engine settings ใดๆ ทั้งสิ้น ผลลัพธ์ OCR จึงเหมือนเดิมทุกตัวอักษร**
ต่างกันแค่เวลาที่ใช้รัน (ยืนยันด้วย test: สลับลำดับหน้าที่ทำเสร็จแบบสุ่ม แล้วเทียบ
output กับตอน `workers=1` — เหมือนกัน 100%)

```bash
python -m ocr_system.cli ocr data/input/dsba_curriculum.pdf --engine tesseract --workers 4
```

ค่า default คือ `workers=1` (พฤติกรรมเดิมทุกประการ ไม่ต้องเปลี่ยนอะไรถ้าไม่ระบุ flag นี้)

**ข้อควรรู้**: Tesseract แต่ละครั้งที่เรียก (`image_to_string`) เป็น process แยก
และใช้ทุก core ของเครื่องเป็น default สำหรับ OpenMP thread ภายในตัวเอง ถ้ารันหลาย
หน้าพร้อมกันโดยไม่ลด thread ต่อ process จะเกิด oversubscription (แย่งกัน) ทำให้
**ช้าลง** ไม่ใช่เร็วขึ้น — โค้ดจึงตั้ง `OMP_THREAD_LIMIT=1` ให้อัตโนมัติเมื่อ
`workers > 1` เท่านั้น (ไม่กระทบตอน `workers=1`) แนะนำตั้ง `--workers` ใกล้เคียง
จำนวน CPU core ที่มี ไม่ใช่ยิ่งเยอะยิ่งดี

ทดสอบใช้ได้ดีกับ `--engine tesseract` เป็นหลัก (ตรงกับ engine ที่โปรเจกต์นี้ใช้จริง
กับเอกสารหลักสูตร) — engine อื่น (`paddle`/`trocr`) ยังไม่ได้ยืนยันว่า thread-safe
สำหรับเรียก `recognize()` พร้อมกันหลาย thread

### วัดความเร็วจริง (BIT, 317 หน้า, เครื่อง 16 core)

| | เวลา | วินาที/หน้า |
|---|---|---|
| `--workers 1` | 1h 19m 51s (4791.0s) | 15.1 |
| `--workers 12` | 23m 28.6s (1408.6s) | 4.44 |

**Speedup ≈ 3.4 เท่า** (เวลาลดลง ~70.6%) — เร็วขึ้นจริงและมีนัยสำคัญ แต่ไม่ใกล้เคียง
12 เท่าตามจำนวน worker ที่ตั้ง เหตุผล:

1. การ render PDF เป็นภาพ (`pdf2image`/poppler) ไม่ได้ขนานเต็มประสิทธิภาพเท่าขั้น OCR เอง
2. ขั้น preprocessing (deskew/denoise ด้วย cv2/numpy) รันอยู่ใน Python thread เดียวกับที่
   เรียก Tesseract — บาง operation ของ cv2/numpy ไม่ปล่อย GIL เต็มที่ ทำให้ 12 thread
   แย่งกันทำงานส่วนนี้แทนที่จะขนานจริง (ต่างจากตอนรอ Tesseract subprocess ซึ่งปล่อย
   GIL เต็มที่ เป็นส่วนที่ขนานได้จริง)
3. I/O contention — 12 process อ่าน/เขียนไฟล์ภาพพร้อมกันบนดิสก์เดียวกัน

CPU 89% ที่เห็นใน Task Manager ตอนรันสอดคล้องกับภาพนี้ — ใช้ CPU เกือบเต็มจริง แต่ไม่ใช่
ทุก core ทำงานคู่ขนานเต็มประสิทธิภาพตลอดเวลา ยังไงก็ตาม 3.4 เท่าคือกำไรจริงโดยไม่มี
ต้นทุนด้านคุณภาพเลย (ผลลัพธ์เหมือนกันทุกตัวอักษร) — ถ้าต้องการเร็วกว่านี้อีกต้องเปลี่ยนเป็น
process-based parallelism แทน thread-based เพื่อเลี่ยงปัญหา GIL ในขั้น preprocessing
ซึ่งเป็นงานใหญ่กว่านี้มาก ยังไม่ได้ทำ

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

> Lab 4/5/6 (Curriculum Extraction, Page Mapping, Field/Page/Category Evaluation), Lab 7B
> (Curriculum OCR Extraction ด้วย Local VLM) และ Lab 8B (Curriculum DB + NL2SQL Q&A) เป็นงานคนละ
> branch — ดูที่ `Lab-4` / `lab-5` / `Lab-6-separate` / `Lab-7` / `Lab-8` หรือ `main`

## Evaluation & Overfitting (Lab 9)

อ่านผลลัพธ์ที่ Lab 8B รันไว้แล้วเท่านั้น (ไม่รันโมเดลใหม่) มาคำนวณ metric ตามสไลด์บทที่ 9 ครบทั้ง
5 ข้อของ checklist: เลือก metric ให้ตรงงาน, อ่านค่าออกว่าสูง/ต่ำแปลว่าอะไร, ตรวจสัญญาณ overfitting,
รู้จัก metric ที่ไม่ได้ใช้ (+ เหตุผล), และรันสคริปต์ประเมินผลได้จริง

### วิธีรัน

```bash
cd Lab9_evaluation
python evaluate_lab9.py
```

> ⚠️ **ต้องรันผ่าน `.venv` (activate แล้ว) ทุกครั้งที่คำนวณ CER/WER**
> ค่า WER ของภาษาไทยขึ้นกับ tokenizer — ถ้า Python ที่ใช้ไม่มี `pythainlp` จะ fallback เป็นตัดคำด้วย
> ช่องว่างเงียบ ๆ (ไม่ error) ได้ WER ที่ผิดและเขียนทับ `evaluation.json`/`comparison.csv` ไปเลย
> ตรวจได้จากบรรทัด `tokenizer สำหรับ WER:` ตอนรัน หรือฟิลด์ `tokenizer` ใน `evaluation.json`
> ต้องเป็น `pythainlp/newmm` ถ้าขึ้น `whitespace (fallback)` แปลว่าผิด ให้ activate venv แล้วรันใหม่
> (สคริปต์ที่เกี่ยวข้อง: `Lab8b_ocr_system/regenerate_evaluation.py`, `lab7b_curriculum.py --eval-only`)
> `regenerate_evaluation.py` มี guard: ถ้าไม่มี pythainlp จะหยุดและไม่เขียนไฟล์ (ส่วน `--eval-only` ไม่มี guard)
> ถ้า activate ไม่ได้ให้เรียกตรง: `.venv\Scripts\python.exe regenerate_evaluation.py`

### ผลลัพธ์

- `reports/lab9_metrics_latest.md` — conversion_rate, verify_pass_rate, MAE/MAPE หน่วยกิตรวม,
  execution_accuracy, answer_text_accuracy, ความเสถียร (รันซ้ำเอกสารชุดเดียวกัน), confusion
  matrix/MCC ของฟิลด์ `ctype`, และสรุป metric ที่ไม่ได้ใช้ + เหตุผล
- `reports/lab7b_prf1_cerwer_2026-09-16.md` — P/R/F1 + CER/WER ระดับการสกัดข้อมูลดิบของ Lab 7B

รายละเอียดเต็ม (การแม็ปแต่ละ metric กับสไลด์บทที่ 9, ทำไมต้องมี `answer_text_accuracy`/confusion
matrix แยกจากเกณฑ์เดิม) อยู่ที่ `Lab9_evaluation/README.md`
