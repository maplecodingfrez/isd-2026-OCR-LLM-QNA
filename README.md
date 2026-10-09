# isd-2026-OCR-LLM-QNA
> ระบบถาม-ตอบเล่มหลักสูตร (AIT / BIT / DSBA / IT) — พิมพ์คำถามภาษาไทย ได้คำตอบพร้อมหน้าอ้างอิงในเล่ม

## โครงสร้างโฟลเดอร์

```text
.
├── lab10_fastapi/curriculum_app/   # แอปที่รัน: FastAPI (main.py) + หน้าเว็บ (static/)
├── Lab7B_Lab8B_ocr_system/
│   ├── src/ocr_system/             # ตรรกะ OCR → JSON → SQLite → ถาม-ตอบ (lab8b_curriculum_db.py)
│   └── runs/<AIT|BIT|DSBA|IT>/[coop|no_coop]/   # AIT ไม่มีชั้น coop
│       ├── data_input/             # ภาพหน้าเล่มหลักสูตร
│       ├── lab7b_output/           # ผล OCR + ผลประเมิน
│       └── lab8b_output/curriculum.db   # ฐานข้อมูลที่แอปอ่าน (7 แผน)
├── Lab9_evaluation/                # ชุดคำถามทอง + รายงาน metric
├── docs/                           # wireframe, รายงาน
└── src/, scripts/, outputs/, data/ # งาน Lab 3–6 (ไม่ต้องใช้รันแอป)
```

ใช้งานได้ทันทีหลัง clone: ฐานข้อมูล 7 แผนและหน้าเว็บอยู่ใน repo แล้ว ไม่ต้องมี PDF หรือไฟล์ `.env`

## สิ่งที่ต้องมี
- Python 3.10+ และ Git
- [Ollama](https://ollama.com) + โมเดล `qwen3:4b` (ดิสก์ ~3 GB, ไม่ต้องใช้ GPU)
- อินเทอร์เน็ตเฉพาะตอนติดตั้งและดึงโมเดลครั้งแรก

## 1. รันระบบ

### 1.1 ติดตั้ง (ครั้งเดียวต่อเครื่อง)
```powershell
git clone https://github.com/maplecodingfrez/isd-2026-OCR-LLM-QNA.git
cd isd-2026-OCR-LLM-QNA
python -m venv .venv
.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -r lab10_fastapi/curriculum_app/requirements.txt
ollama pull qwen3:4b
```
> Windows ฟ้อง execution policy → `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 1.2 เปิดใช้งาน (ทุกครั้งที่เปิดเครื่องใหม่)
เปิด PowerShell ที่โฟลเดอร์โปรเจกต์ แล้วรันตามลำดับ:
```powershell
ollama serve        # ข้ามได้ถ้าแอป Ollama เปิดอยู่ในถาดระบบแล้ว (เปิดค้างไว้ แล้วเปิดเทอร์มินัลใหม่)
.venv\Scripts\Activate.ps1
python -m uvicorn lab10_fastapi.curriculum_app.main:app --host 127.0.0.1 --port 8000
```
รอจนขึ้น `Application startup complete` (ครั้งแรกโมเดลโหลดช้า) · หยุดด้วย `Ctrl+C`

## 2. ใช้งาน
เปิด <http://127.0.0.1:8000/>

1. เลือกหลักสูตร (7 แผน: AIT, BIT / DSBA / IT แบบสหกิจและไม่สหกิจ)
2. พิมพ์คำถามภาษาไทย 2–500 ตัวอักษร แล้วกด "ถาม"
3. ได้คำตอบ + หน้าอ้างอิง (หน้า PDF / หน้าที่พิมพ์ รหัสและชื่อวิชา) · "คัดลอกผล" คัดลอกเป็นข้อความ

**ลองถาม:** `ปี 1 เทอม 1 เรียนอะไรบ้าง` · `วิชา Calculus 1 กี่หน่วยกิต` · `การจะเรียนวิชา DATA WAREHOUSE ต้องผ่านวิชาอะไรมาก่อน` · `ปี 2 เทอม 1 มีกี่หน่วยกิต` · `แผนสหกิจกับไม่สหกิจต่างกันอย่างไร`

คำถามที่เล่มไม่มีคำตอบจะได้ "ไม่พบข้อมูลนี้ในเล่มหลักสูตร" (ระบบไม่เดา)

ตรวจความพร้อม <http://127.0.0.1:8000/api/health> ต้องได้ `status: ok` · เอกสาร API <http://127.0.0.1:8000/docs>


## แก้ปัญหา
| อาการ | วิธีแก้ |
|---|---|
| พอร์ต 8000 ถูกใช้อยู่ | เปลี่ยน `--port 8001` แล้วเปิด URL ตามพอร์ตใหม่ |
| `/api/health` ไม่ ok / แจ้งเชื่อมต่อ Ollama ไม่ได้ | ตรวจว่า `ollama serve` ทำงาน และ `ollama list` เห็น `qwen3:4b` |
| ถามแล้วช้าครั้งแรก | ปกติ — โมเดลกำลังโหลด ครั้งถัดไปเร็วขึ้น |

> ถ้าไม่เปิด Ollama ระบบตอบได้เฉพาะคำถามที่มีกฎตายตัว (ราว 30–45%) ที่เหลือจะแจ้งว่าเชื่อมต่อไม่ได้

## เอกสารเพิ่มเติม
- API / สถาปัตยกรรม / ส่งคำถามเป็นชุด (`ask-batch`) / ข้อจำกัดที่รู้อยู่: [`lab10_fastapi/README.md`](lab10_fastapi/README.md)
- ความแม่นยำ: ชุดคำถามอิสระ + Master Test Suite ราว 75–79% กับสำนวนที่ไม่เคยเห็น

## สมาชิก
- นายวีร์กฤต โอวาทสาร 67070168
- นายสิทธิชัย เมฆขยาย 67070185
- นายอธิบดี บูรณากาญจน์ 67070195
