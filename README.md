# isd-2026-OCR-LLM-QNA — Lab 10
> FastAPI + หน้าเว็บ ถาม-ตอบเล่มหลักสูตรด้วยภาษาธรรมชาติ (Qwen text-to-SQL + SQLite)

Branch นี้คือ **Lab 10** README นี้เลยมีแค่เนื้อหาของ Lab 10
ถ้าต้องการดูงานทุก Lab รวมกัน ให้ดูที่ [`main`](https://github.com/maplecodingfrez/isd-2026-OCR-LLM-QNA/tree/main)

## Members
* 67070168 - film_synthesis
* 67070185 - 17decc
* 67070195 - zvacia

---

## Lab 10 ทำอะไร

Lab 10 เอาฐานข้อมูลหลักสูตรที่ Lab 8B สร้างไว้ (`curriculum.db`) มาทำเป็น web application
ผู้ใช้เลือกหลักสูตร/แผน พิมพ์คำถามภาษาไทย แล้วได้คำตอบกลับมา พร้อม SQL ที่ใช้ เลขหน้าอ้างอิงในเล่ม และเวลาที่ใช้ตอบ

```text
หน้าเว็บ (index.html)
   │  POST /api/ask {question, program}
   ▼
FastAPI (main.py) ── เลือก curriculum.db ตาม program (7 แผน)
   │
   ▼
Lab 8B ask()  ──►  qwen3:4b แปลงคำถามเป็น SELECT
   │               guard_sql() บล็อกคำสั่งที่แก้ข้อมูล
   │               เปิด SQLite แบบ read-only แล้วรัน query
   │               qwen3:4b สรุป rows เป็นคำตอบภาษาไทย
   │               โค้ดแนบเลขหน้าอ้างอิง (LLM ไม่ได้เป็นคนเขียนเลขหน้า)
   ▼
JSON {answer, sql, rows, citations, citation_text}
```

- **ไม่ใช่ vector RAG:** ไม่มี embedding และไม่มี vector database โมเดลแค่แปลงคำถามเป็น SQL แล้วสรุปผลจาก SQLite
- **ไม่ OCR ตอนถาม:** `/api/ask` ไม่ได้อ่าน PDF หรือเรียก OCR เลย การ OCR เกิดครั้งเดียวตอนสร้างฐานข้อมูลใน Lab 7B/8B
- **คำถามนอกเล่ม:** ถ้าไม่มีข้อมูลในฐานข้อมูล ระบบตอบว่า `"ไม่พบข้อมูลนี้ในเล่มหลักสูตร"` และไม่เดาคำตอบ

### ต่อยอดจาก Lab ก่อนหน้า

| Lab | ส่งอะไรให้ Lab 10 | Branch |
|---|---|---|
| 7B | OCR ตารางแผนการศึกษาด้วย local VLM (Typhoon-OCR + qwen3) ได้ JSON | [Lab-7](https://github.com/maplecodingfrez/isd-2026-OCR-LLM-QNA/tree/Lab-7) |
| 8B | แปลง JSON เป็น `curriculum.db` และมีฟังก์ชัน `ask()` (NL→SQL + อ้างอิงหน้า) ที่ Lab 10 เรียกใช้ตรง ๆ | [Lab-8](https://github.com/maplecodingfrez/isd-2026-OCR-LLM-QNA/tree/Lab-8) |
| 9 | วัดผลคำตอบ NL→SQL ครบ 7 แผน (ตอบถูก 188/210 ข้อ) | [Lab-9](https://github.com/maplecodingfrez/isd-2026-OCR-LLM-QNA/tree/Lab-9) |

## ไฟล์ที่เกี่ยวข้อง

```text
ocr_system/
├── lab10_fastapi/
│   └── curriculum_app/
│       ├── main.py            # FastAPI: routes ทั้งหมด
│       ├── config.py          # อ่าน .env + รายการหลักสูตร PROGRAMS (7 แผน → path ของ DB)
│       ├── database.py        # อ่าน/เขียนตาราง course, program
│       ├── model_service.py   # เช็กว่า Ollama พร้อมไหม (ใช้ใน /api/health)
│       ├── schemas.py         # Pydantic request/response
│       ├── requirements.txt
│       ├── .env.example
│       └── static/index.html  # หน้าเว็บ: dropdown หลักสูตร, ช่องคำถาม, คำตอบ, SQL, เวลา
└── Lab7B_Lab8B_ocr_system/
    ├── src/ocr_system/lab8b_curriculum_db.py   # ask(), guard_sql(), open_db() ที่ Lab 10 import มาใช้
    └── runs/<AIT|BIT|DSBA|IT>/.../lab8b_output/curriculum.db   # ฐานข้อมูล 7 แผน (อยู่ใน git แล้ว)
```

## เริ่มใช้งาน

**ต้องมีก่อน:**
- Python 3.10 ขึ้นไป
- [Ollama](https://ollama.com) เปิดอยู่ในเครื่อง พร้อมโมเดล `qwen3:4b`

ฐานข้อมูลทั้ง 7 แผนอยู่ใน git แล้ว จึงไม่ต้องรัน Lab 7B/8B ใหม่ ทุกคำสั่งด้านล่างให้รันจากรากโปรเจกต์ (โฟลเดอร์ที่มี `pyproject.toml`)

**1. สร้าง venv แล้วติดตั้ง package**

```powershell
# Windows PowerShell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```
```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```
```bash
python -m pip install -r lab10_fastapi/curriculum_app/requirements.txt
```

**2. สร้างไฟล์ `.env`** (ห้าม commit ไฟล์นี้ เพราะอยู่ใน `.gitignore` แล้ว)

```powershell
Copy-Item lab10_fastapi\curriculum_app\.env.example lab10_fastapi\curriculum_app\.env   # Windows
```
```bash
cp lab10_fastapi/curriculum_app/.env.example lab10_fastapi/curriculum_app/.env         # macOS / Linux
```

ค่าเริ่มต้นใน `.env.example` ใช้ได้เลย:

| ตัวแปร | ค่าเริ่มต้น | ใช้ทำอะไร |
|---|---|---|
| `CURRICULUM_DB_PATH` | `.../runs/DSBA/coop/lab8b_output/curriculum.db` | DB ของ `/api/program`, `/api/courses` และของ `/api/ask` ตอนไม่ได้เลือกหลักสูตร |
| `CURRICULUM_OLLAMA_URL` | `http://127.0.0.1:11434` | ที่อยู่ Ollama |
| `CURRICULUM_OLLAMA_MODEL` | `qwen3:4b` | โมเดลที่ใช้แปลงคำถามเป็น SQL และสรุปคำตอบ |
| `CURRICULUM_REQUEST_TIMEOUT` | `180` | timeout ต่อ request (วินาที) |
| `CURRICULUM_MAX_ROWS` | `100` | จำนวนแถวสูงสุดที่ `/api/courses` คืน |

**3. เตรียมโมเดล**

```bash
ollama pull qwen3:4b
```

**4. รัน server**

```bash
python -m uvicorn lab10_fastapi.curriculum_app.main:app --reload --host 127.0.0.1 --port 8000
```

- หน้าเว็บ: <http://127.0.0.1:8000/>
- Swagger (ลอง API ได้): <http://127.0.0.1:8000/docs>
- ตรวจสถานะ: <http://127.0.0.1:8000/api/health> ถ้าพร้อมใช้ `database_ready` และ `ollama_ready` ต้องเป็น `true` ทั้งคู่

## API

| Method | Path | หน้าที่ |
|---|---|---|
| GET | `/api/health` | ตรวจว่า DB กับ Ollama พร้อมไหม |
| GET | `/api/programs` | รายการหลักสูตร/แผนทั้ง 7 แผน บอกด้วยว่ามี DB ไหม, หน่วยกิตรวม และจำนวนปี (ใช้เติม dropdown) |
| GET | `/api/program` | ข้อมูลหลักสูตรจาก DB ใน `.env` |
| GET | `/api/courses?search=&limit=&offset=` | ค้นหารายวิชา |
| POST | `/api/courses` | เพิ่มรายวิชา (**เขียนลง DB จริง** ให้ใช้รหัสทดลอง หรือใช้สำเนา DB) |
| POST | `/api/ask` | ถามคำถาม แล้วได้คำตอบ + SQL + อ้างอิงหน้า |

ค่า `program` ที่ใช้ได้: `ait`, `bit_no_coop`, `bit_coop`, `dsba_no_coop`, `dsba_coop`, `it_no_coop`, `it_coop`

**ตัวอย่าง `POST /api/ask`**

```json
{ "question": "ปี 1 เทอม 1 เรียนกี่หน่วยกิต", "program": "dsba_coop" }
```

Response มีฟิลด์ `question`, `program`, `sql`, `rows`, `answer`, `citations`, `citation_text`
โดย `citation_text` จะหน้าตาแบบ `(อ้างอิง: เล่มหลักสูตร หน้า 33 (PDF 38))`
"หน้า 33" คือเลขที่พิมพ์บนกระดาษ ส่วน "PDF 38" คือลำดับหน้าในไฟล์ PDF

| สถานะ | เกิดเมื่อ |
|---|---|
| 404 | `program` ไม่อยู่ในรายการ |
| 503 | ไม่พบไฟล์ DB หรือติดต่อ Ollama ไม่ได้ |
| 422 | สร้าง SQL ที่รันได้ไม่สำเร็จ หรือ request ไม่ผ่าน validation |

## ปัญหาที่พบบ่อย

| อาการ | วิธีแก้ |
|---|---|
| `No module named fastapi` | ยังไม่ได้ activate `.venv` หรือยังไม่ได้ติดตั้ง `requirements.txt` |
| เปิดเว็บแล้วขึ้น `ERR_CONNECTION_REFUSED` | server ยังไม่ได้รัน ให้รันคำสั่ง uvicorn แล้วเปิด terminal ค้างไว้ |
| `ติดต่อ Ollama ไม่ได้` | เปิด Ollama แล้วเช็กด้วย `ollama list` ว่ามี `qwen3:4b` |
| `ไม่พบฐานข้อมูล` | เช็ก `CURRICULUM_DB_PATH` ใน `.env` และรันคำสั่งจากรากโปรเจกต์ |
| คำตอบช้า | ครั้งแรก Ollama ต้องโหลดโมเดลเข้าหน่วยความจำก่อน ครั้งต่อไปจะเร็วขึ้น |

## ข้อจำกัด

- `/api/program` และ `/api/courses` ใช้ DB จาก `.env` ตัวเดียว ส่วน dropdown บนหน้าเว็บมีผลเฉพาะกับ `/api/ask`
- ความถูกต้องของคำตอบขึ้นกับข้อมูลที่ Lab 7B OCR ได้ ถ้า OCR อ่านวิชาไหนตกไป คำตอบก็จะไม่มีวิชานั้น
- ผลวัดความแม่นยำของ NL→SQL ดูได้ใน branch [Lab-9](https://github.com/maplecodingfrez/isd-2026-OCR-LLM-QNA/tree/Lab-9)
