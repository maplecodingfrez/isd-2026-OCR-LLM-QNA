# Lab 10 — FastAPI + Qwen text-to-SQL + SQLite + Frontend

Lab นี้มีสอง application แยก `main.py` และ `index.html` ออกจากกัน

```text
Curriculum App                 Transcript App
คำถาม → SQL → SQLite          Upload PDF/Image
       → rows → คำตอบ          → preprocess → OCR → postprocess → JSON
```

> ระบบนี้ยังไม่ใช่ vector RAG: ไม่มี embedding หรือ vector database โมเดลทำหน้าที่แปลงคำถามเป็น SQL และสรุปผลจาก SQLite

## 1. ไฟล์สำคัญ

```text
lab10_fastapi/
├── curriculum_app/
│   ├── main.py         Curriculum API
│   ├── config.py / .env.example
│   ├── database.py / model_service.py / schemas.py
│   ├── requirements.txt
│   ├── README.md
│   └── static/index.html
├── transcript_app/
│   ├── main.py         Transcript upload API
│   ├── config.py / .env.example
│   ├── pipeline_service.py / schemas.py
│   ├── requirements.txt
│   ├── README.md
│   └── static/index.html
└── README.md
```

แต่ละกลุ่มสามารถก็อปเฉพาะโฟลเดอร์ application ของตนเองได้ แต่ต้องมีโฟลเดอร์ `src/ocr_system` ที่เก็บ Lab 8 อยู่ในโปรเจกต์เดียวกัน

## 2. สิ่งที่ต้องมีก่อนเริ่ม

- Python 3.10 ขึ้นไป
- VS Code
- Ollama
- โมเดล `qwen3:4b`
- ฝั่ง Transcript ต้องมีโมเดล `scb10x/typhoon-ocr1.5-3b` ด้วย
- ฐานข้อมูล `work/lab8b_run/curriculum.db` จาก Lab 8B

ถ้ายังไม่มีฐานข้อมูล ให้กลับไปรันจากรากโปรเจกต์:

```bash
python run_lab8b.py --skip-lab7
```

หากยังไม่มีผล Lab 7B ให้รันโดยไม่ใส่ `--skip-lab7`:

```bash
python run_lab8b.py
```

## 3. เปิดโปรเจกต์และ Terminal

เปิดโฟลเดอร์ `ocr_system` ใน VS Code แล้วเลือก:

```text
Terminal > New Terminal
```

ทุกคำสั่งต่อจากนี้ให้รันใน Terminal ของ VS Code และต้องอยู่ที่รากโปรเจกต์ ซึ่งเป็นตำแหน่งเดียวกับ `pyproject.toml`

## 4. สร้าง virtual environment

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

หาก PowerShell ปฏิเสธการ activate ให้รันหนึ่งครั้ง:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

เมื่อ activate สำเร็จ จะเห็น `(.venv)` ด้านหน้าบรรทัดคำสั่ง

## 5. ติดตั้ง package

ใช้คำสั่งเดียวกันทุกระบบหลัง activate env:

```bash
python -m pip install --upgrade pip
python -m pip install -r lab10_fastapi/curriculum_app/requirements.txt
python -m pip install -r lab10_fastapi/transcript_app/requirements.txt
```

ตรวจว่า FastAPI และ Uvicorn พร้อม:

```bash
python -c "import fastapi, uvicorn; print('Lab 10 packages OK')"
```

## 6. เตรียมไฟล์ `.env`

ห้ามใส่รหัสผ่านหรือ config จริงลง source code และห้าม commit `.env`

### Windows PowerShell

```powershell
Copy-Item lab10_fastapi\curriculum_app\.env.example lab10_fastapi\curriculum_app\.env
Copy-Item lab10_fastapi\transcript_app\.env.example lab10_fastapi\transcript_app\.env
```

### macOS/Linux

```bash
cp lab10_fastapi/curriculum_app/.env.example lab10_fastapi/curriculum_app/.env
cp lab10_fastapi/transcript_app/.env.example lab10_fastapi/transcript_app/.env
```

Curriculum App ใช้ค่า:

```dotenv
CURRICULUM_DB_PATH=work/lab8b_run/curriculum.db
CURRICULUM_OLLAMA_URL=http://127.0.0.1:11434
CURRICULUM_OLLAMA_MODEL=qwen3:4b
```

Transcript App ใช้ `TRANSCRIPT_OLLAMA_URL`, `TRANSCRIPT_OCR_MODEL` และ `TRANSCRIPT_TEXT_MODEL` ใน `.env` ของตนเอง

Path ของฐานข้อมูลแบบ relative จะเริ่มจากรากโปรเจกต์

## 7. เตรียม Ollama และ Qwen

เปิด Ollama และตรวจโมเดล:

```bash
ollama list
```

หากยังไม่มี Qwen:

```bash
ollama pull qwen3:4b
ollama pull scb10x/typhoon-ocr1.5-3b
```

ทดสอบ:

```bash
ollama run qwen3:4b "ตอบคำว่า พร้อม"
```

กด `Ctrl+D` หรือพิมพ์ `/bye` เพื่อออกจากหน้าสนทนา

## 8. รัน FastAPI

### Curriculum Application

```bash
python -m uvicorn lab10_fastapi.curriculum_app.main:app --reload --host 127.0.0.1 --port 8000
```

เปิดเบราว์เซอร์:

- หน้าเว็บ: <http://127.0.0.1:8000/>
- Swagger API: <http://127.0.0.1:8000/docs>
- ตรวจสถานะ: <http://127.0.0.1:8000/api/health>

### Transcript Application

เปิด Terminal ของ VS Code อีกหน้าหนึ่ง activate `.venv` แล้วรัน:

```bash
python -m uvicorn lab10_fastapi.transcript_app.main:app --reload --host 127.0.0.1 --port 8001
```

- หน้า upload: <http://127.0.0.1:8001/>
- Swagger API: <http://127.0.0.1:8001/docs>
- ตรวจสถานะ: <http://127.0.0.1:8001/api/health>

หยุด server ด้วย `Ctrl+C`

## 9. API ที่มีให้

### Curriculum API

| Method | Path | หน้าที่ |
|---|---|---|
| GET | `/api/health` | ตรวจ DB และ Ollama |
| GET | `/api/program` | อ่านข้อมูลหลักสูตร |
| GET | `/api/courses` | อ่าน/ค้นหารายวิชา |
| POST | `/api/courses` | เพิ่มรายวิชาลง SQLite |
| POST | `/api/ask` | ให้ Qwen สร้าง SQL และตอบคำถาม |
| GET | `/api/courses/{code}/prerequisites` | ⭐ **(API เพิ่มเติม)** ตรวจสอบวิชาบังคับก่อนและวิชาที่ปลดล็อค |

### Transcript API

| Method | Path | หน้าที่ |
|---|---|---|
| GET | `/api/health` | ตรวจ config ของ Transcript App |
| POST | `/api/transcript/extract` | อัปโหลดและสกัด Transcript |

ทดลอง GET:

```text
http://127.0.0.1:8000/api/courses?search=06026200
```

ทดลอง POST แนะนำให้เปิด `/docs`, เลือก endpoint แล้วกด **Try it out**

ตัวอย่าง body ของ `/api/ask`:

```json
{
  "question": "ปี 1 เทอม 1 เรียนกี่หน่วยกิต"
}
```

ตัวอย่าง body ของ `/api/courses`:

```json
{
  "code": "99999999",
  "name_th": "วิชาทดลอง API",
  "name_en": "API TEST COURSE",
  "credits": 3,
  "lecture_h": 3,
  "lab_h": 0,
  "self_h": 6,
  "description_th": "ข้อมูลตัวอย่างสำหรับทดสอบ POST"
}
```

> POST `/api/courses` เขียนลง DB จริง ควรใช้รหัสทดลองที่ลบออกภายหลัง หรือใช้สำเนา DB สำหรับการสาธิต

### 9.1 API เพิ่มเติม: ตรวจสอบวิชาบังคับก่อน (Prerequisite Analyzer)

เป็น Endpoint เพิ่มเติมที่พัฒนาขึ้นเพื่อต่อยอดฐานข้อมูล `prerequisite` จาก Lab 8B ช่วยให้นักศึกษาสามารถวางแผนการลงทะเบียนเรียนได้อย่างแม่นยำ

* **Path**: `GET /api/courses/{code}/prerequisites`
* **พารามิเตอร์**: `code` (Path Parameter) รหัสวิชาตัวเลข 8 หลัก (เช่น `06016407`)
* **หน้าที่**:
  1. `prerequisites_required`: ตรวจสอบวิชาที่ต้องสอบผ่านก่อน จึงจะลงเรียนวิชานี้ได้ (Requires)
  2. `unlocked_courses`: ตรวจสอบวิชาที่จะปลดล็อคให้ลงเรียนต่อได้ หลังจากสอบผ่านวิชานี้ (Unlocks)

#### วิธีใช้งาน (How to use)

1. **ผ่าน Browser URL โดยตรง**:
   - ตรวจสอบวิชาที่มีวิชาบังคับก่อน: [http://127.0.0.1:8000/api/courses/06016407/prerequisites](http://127.0.0.1:8000/api/courses/06016407/prerequisites)
   - ตรวจสอบวิชาที่ปลดล็อควิชาอื่น: [http://127.0.0.1:8000/api/courses/06016406/prerequisites](http://127.0.0.1:8000/api/courses/06016406/prerequisites)
2. **ผ่าน cURL / Terminal**:
   ```bash
   curl -s http://127.0.0.1:8000/api/courses/06016407/prerequisites
   ```
3. **ผ่าน Swagger UI (`/docs`)**:
   - เปิด [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - เลือกแท็ก **Prerequisites** ➔ `GET /api/courses/{code}/prerequisites`
   - กด **Try it out** ➔ กรอก `code`: `06016407` ➔ กด **Execute**
4. **ผ่านหน้าเว็บ Web UI (`/`)**:
   - เปิด [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
   - เลื่อนลงมาที่ส่วน **"ตรวจสอบวิชาบังคับก่อน (Prerequisite Analyzer)"**
   - พิมพ์รหัสวิชา (มีระบบเลือกรหัสวิชาอัตโนมัติจากฐานข้อมูล) หรือคลิกปุ่มลัดตัวอย่าง เช่น `06016407` แล้วกด **"ตรวจสอบ"**

#### ตัวอย่างผลลัพธ์ (Response JSON)

```json
{
  "code": "06016407",
  "name_th": "โครงงาน 2",
  "name_en": "PROJECT 2",
  "credits": 3,
  "prerequisites_required": [
    {
      "code": "06016406",
      "name_th": "โครงงาน 1",
      "name_en": "PROJECT 1",
      "credits": 3,
      "kind": "pre"
    }
  ],
  "unlocked_courses": []
}
```

#### การทำงานเบื้องหลัง (How it works)

1. **Validation (`schemas.py`)**: ตรวจสอบว่ารหัสวิชาเป็นตัวเลข 8 หลักพอดี (`^\d{8}$`) หากผิดรูปแบบจะส่งกลับ `422 Unprocessable Entity`
2. **Read-Only Database Connection (`database.py`)**: เชื่อมต่อ SQLite แบบ Read-Only ป้องกันการแก้ไขข้อมูล
3. **Query รายวิชาหลัก**: ค้นหารายละเอียดชื่อวิชาและหน่วยกิตจากตาราง `course` หากไม่พบจะคืน `404 Not Found`
4. **Query วิชาบังคับก่อน (Requires)**: ดึงข้อมูลจากตาราง `prerequisite` โดยจับคู่ `WHERE code = ?` และ JOIN กับ `course` เพื่อนำชื่อวิชามาแสดง
5. **Query วิชาที่ปลดล็อค (Unlocks)**: ดึงข้อมูลจากตาราง `prerequisite` โดยจับคู่ `WHERE requires = ?` และ JOIN กับ `course`
6. **Data Contract Serialization**: แปลงผลลัพธ์ผ่าน Pydantic Model `CoursePrerequisitesResponse` ส่งคืน Client เป็น JSON

> 💡 **หมายเหตุเกี่ยวกับข้อมูลในระบบ**: ฐานข้อมูลปัจจุบัน (`work/lab8b_run/curriculum.db`) เป็นข้อมูลของ **หลักสูตร IT (เทคโนโลยีสารสนเทศ) แผนปกติ** มี 41 รายวิชาตามแผนการศึกษา 4 ปี โดยมีกฎ Prerequisite อยู่จริง 4 วิชา (`06016407`, `06016418`, `06016419`, `06016420`) วิชาอื่นๆ ในเล่มจะไม่มีวิชาบังคับก่อน และหากค้นหารหัสวิชาของสาขาอื่น (เช่น DSBA, BIT) จะคืนค่า `404 Not Found`

## 10. จุดเปลี่ยนโมเดลของนักศึกษา

เปิด `curriculum_app/model_service.py` แล้วค้นหา:

```text
MODEL INTEGRATION POINT
```

ฟังก์ชันที่ต้องเปลี่ยนคือ:

```python
QwenTextToSQL._chat()
```

จากนั้นแก้ `_chat()` ให้เรียกฟังก์ชัน inference ของโมเดลและคืน Python `dict` รูปแบบเดิม ส่วน FastAPI, SQLite และ frontend ไม่ต้องแก้ ส่วน Transcript App ใช้โมเดลผ่าน `lab8a_denoise.py` และ `lab7a_transcript.py` โดยตรง

## 11. ลำดับการทำงานของ `/api/ask`

1. `index.html` ส่ง `POST /api/ask`
2. FastAPI ตรวจ request ด้วย Pydantic
3. Qwen สร้าง `SELECT` SQL
4. `database.py` ปฏิเสธ SQL ที่แก้ข้อมูล
5. เปิด SQLite แบบ read-only แล้วรัน query
6. Qwen สรุป rows เป็นคำตอบภาษาไทย
7. FastAPI ส่ง JSON กลับหน้าเว็บ

## 12. ปัญหาที่พบบ่อย

### `No module named fastapi`

ยังไม่ได้ activate env หรือติดตั้ง requirements:

```bash
python -m pip install -r lab10_fastapi/curriculum_app/requirements.txt
python -m pip install -r lab10_fastapi/transcript_app/requirements.txt
```

### `ไม่พบฐานข้อมูล`

ตรวจ `CURRICULUM_DB_PATH` ใน `curriculum_app/.env` และสร้าง DB จาก Lab 8B ก่อน

### `ติดต่อ Ollama ไม่ได้`

เปิด Ollama แล้วตรวจ:

```bash
ollama list
```

### เปิดหน้าเว็บได้แต่ถามไม่ได้

เปิด `/api/health` แล้วดูว่า `database_ready` และ `ollama_ready` เป็น `true` หรือไม่
