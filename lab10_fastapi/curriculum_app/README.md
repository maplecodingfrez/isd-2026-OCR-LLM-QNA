# Curriculum Application

แอปนี้รับคำถาม → ใช้ทางลัดจากข้อมูลหลักสูตร หรือให้ Qwen สร้าง SQL → อ่าน SQLite → ส่งกลับคำตอบ, SQL อ้างอิง และ rows

`sql` ของทางลัดเป็นคำค้นอ้างอิง ไม่ใช่ execution trace ทั้งหมด: อาจมีหลายคำค้น การกรอง/คำนวณใน Python หรือข้อมูลจากอีกแผน ส่วนคำถามที่ผ่าน Qwen ส่ง SQL ที่รันจริง ช่องนี้ใช้ตรวจแนวทางค้นข้อมูล ไม่ใช้ replay เพื่อรับรองผลเหมือนคำตอบทุกกรณี

ตรวจ UI จริงวันที่ 2026-10-05 บน production `636927e`, API ในเครื่อง port8002: Chrome headless โปรไฟล์ว่าง ผ่านฟอร์มถาม/วิชาบังคับก่อน/ผลกระทบถอน, idle/loading/success/error, ปิดปุ่มขณะรอ, เปลี่ยนแผนล้างผลเครื่องมือ, ทิ้ง response เก่าหลังเปลี่ยนแผน และจอ390pxไม่มีแนวนอนล้น ไม่พบ JavaScript exception; การทดสอบ response เก่าใช้ข้อมูล API จริงที่หน่วงการส่งกลับใน browser ไม่เพิ่ม dependency ระบบ ผลนี้ไม่ใช่การรับรอง deployment หรือคะแนน Challenge ของอาจารย์

## เอาไฟล์ไปวางที่ไหน

วางโฟลเดอร์ `curriculum_app` ไว้ภายใน `ocr_system/lab10_fastapi/` และรักษาโครงสร้างนี้:

```text
ocr_system/
├── lab10_fastapi/
│   ├── __init__.py
│   └── curriculum_app/       ← ไฟล์ Lab 10 ของกลุ่มนี้
├── src/ocr_system/
│   └── lab8b_curriculum_db.py ← โค้ด Lab 8B
└── Lab7B_Lab8B_ocr_system/runs/<หลักสูตร>/<แผน>/lab8b_output/
    └── curriculum.db            ← ฐานข้อมูลของแต่ละแผน (ติดมากับ repo)
```

ห้ามย้าย `main.py` ออกจาก `curriculum_app` และให้รันคำสั่งจากโฟลเดอร์ `ocr_system`

ให้รันจากรากโปรเจกต์ `ocr_system` ใน VS Code Terminal:

```bash
python -m pip install -r lab10_fastapi/curriculum_app/requirements.txt
ollama pull qwen3:4b
python -m uvicorn lab10_fastapi.curriculum_app.main:app --reload --port 8000
```

เปิด <http://127.0.0.1:8000/> หรือ <http://127.0.0.1:8000/docs>

ก่อนรันต้องมี:

- `lab10_fastapi/curriculum_app/.env` ถ้าต้องการเปลี่ยนค่าเริ่มต้น (ไม่จำเป็นเมื่อใช้ default)
- `Lab7B_Lab8B_ocr_system/runs/DSBA/coop/lab8b_output/curriculum.db` (ติดมากับ repo)
- `Lab7B_Lab8B_ocr_system/src/ocr_system/lab8b_curriculum_db.py`

ถ้าแจกเฉพาะกลุ่ม Curriculum ให้ก็อปโฟลเดอร์นี้ พร้อม Lab 8B และไฟล์ DB ตามตำแหน่งข้างต้น

## รายการ API ในระบบ

| Method | Path | รายละเอียด |
|---|---|---|
| `GET` | `/` | หน้าเว็บ Frontend สำหรับผู้ใช้ |
| `GET` | `/api/health` | ตรวจสอบสถานะ DB และ Ollama |
| `GET` | `/api/program` | ดูข้อมูลภาพรวมหลักสูตร |
| `GET` | `/api/courses` | ดู/ค้นหารายวิชา (มี limit, offset, search) |
| `POST` | `/api/courses` | เพิ่มรายวิชาใหม่เข้า SQLite |
| `POST` | `/api/ask` | ถามคำถามหลักสูตร (Qwen Text-to-SQL + SQLite) |
| `GET` | `/api/courses/{code}/prerequisites` | ⭐ **(API เพิ่มเติม)** ตรวจสอบวิชาบังคับก่อนและวิชาที่ปลดล็อค |
| `GET` | `/api/courses/{code}/withdrawal-impact` | ตรวจตัวต่อโดยตรง/ทางอ้อมที่อาจได้รับผลกระทบเมื่อถอนวิชา |

### Current UI / archived chat design

The active page has returned to the pre-chat form interface: curriculum selection, questions, prerequisites, and withdrawal impact. Bilingual names, full credit notation, and elective accordions remain available.

The chat UI, design documents, and compatible backend snapshot are archived outside the repository at `D:/DSBA 3rd Year/Works/archived/curriculum-chat-ui-2026-10-04-225903`. Browser chat history is retained in localStorage but is not displayed by the current UI.

Backend routing, SQLite schema, and existing API endpoints are unchanged by the UI rollback. Additive `answer_type`, `processing_seconds`, and prerequisite `citations` metadata remain available.

### ขอบเขตผลกระทบการถอน

คำถาม เช่น `ถ้าถอนวิชา 90644007 ออกไป` ใช้ reverse prerequisite graph เดียวกับเครื่องมือตรวจผลกระทบ แสดงตัวต่อโดยตรง/ทางอ้อม พร้อมเงื่อนไขทางเลือกหรือเรียนร่วมกันและชื่อสองภาษา ไม่ต้องเรียก Qwen เพื่อเดาคู่ prerequisite; คำถามอื่นยังใช้ routing เดิม

แก้การสกัด prerequisite ที่ต้นฉบับระบุเป็นชื่อเต็มแทนรหัส เช่น FOUNDATION ENGLISH 1 โดยยอมรับเฉพาะชื่อที่ตรงและมีรหัสเดียว DSBA ทั้งสองแผนจึงมีคู่ `90644008 → requires 90644007` ตาม PDF209 (หน้าพิมพ์208) จำนวนคู่เพิ่มจาก5เป็น6; Gold v2.1 แก้จากต้นฉบับแล้ว และ v2.2 เพิ่มการแก้ AIT/IT พร้อมหลักฐานใน metadata

ช่องตรวจผลกระทบใช้หลักสูตร/แผนที่เลือกด้านบน รับรหัสวิชา 8 หลัก และอ่านความสัมพันธ์จาก SQLite โดยไม่ใช้ LLM หรือแก้ฐานข้อมูล ผลลัพธ์แยกตัวต่อโดยตรงและทางอ้อม พร้อมตัวอย่างเส้นทางสั้นที่สุด เงื่อนไขทางเลือก (`หรือ`) และเรียนร่วมกัน รวมถึงหน้า PDF ของคำอธิบายวิชาที่มีข้อมูลอ้างอิง

นี่คือรายวิชาที่อาจได้รับผลกระทบ หากถอนแล้วผู้ใช้ยังไม่เคยผ่านวิชาต้นทาง ไม่ใช่การยืนยันสิทธิ์ลงทะเบียนส่วนบุคคล เพราะยังไม่ได้รับประวัติวิชาที่ผ่านแล้ว วิชาทางเลือกที่ผ่าน และตารางลงทะเบียนของผู้ใช้ หากไม่พบเส้นทาง ระบบระบุว่าไม่พบความสัมพันธ์ในข้อมูล แทนการรับรองว่าไม่มีผลกระทบ

### การใช้งาน API ตรวจสอบวิชาบังคับก่อน (`GET /api/courses/{code}/prerequisites`)
* **Path Parameter**: `code` รหัสวิชา 8 หลัก (เช่น `06016407`)
* **ผลลัพธ์**: คืน JSON ระบุวิชาที่ต้องผ่านก่อน (`prerequisites_required`), `prerequisite_status` และวิชาที่มีความสัมพันธ์ต่อ (`unlocked_courses`); ไม่ใช่การรับรองสิทธิ์ลงทะเบียนส่วนบุคคล
* **ตัวอย่างการเรียก**:
  ```bash
  curl -s http://127.0.0.1:8000/api/courses/06016407/prerequisites
  ```
* **หมายเหตุ**: รองรับ 7 แผน ส่ง `?program=<id>` จาก `/api/programs` เพื่อเลือกแผน; default เป็น DSBA สหกิจเมื่อไม่ได้ปรับ config จำนวนวิชาและความสัมพันธ์อ่านจากฐานข้อมูลแผนที่เลือก

## คำถามที่พบบ่อย

### หลักฐาน readiness รอบ 2026-10-05

ตัวย่อที่นำจาก `backup_catoz@8bfe8b5` มาใช้กับ resolver เดิม: `ISAD`, `DSA/DSAA/DSDA`, `PSP/PSCP`, `DISCRETE`, `ITF`, `CNI/COMM NET`, `BDS`, `ERP`, `BISAD`, `AIoT`, `NoSQL DB` (15รูปสะกดใหม่). ต้องตรงวิชาเดียวในข้อมูลหลักสูตรที่เลือก; case/context และขอบคำเดิมยังใช้ เช่น `วิชา dsa รหัสอะไร`. `ISD` มีอยู่แล้ว; ยังไม่เพิ่ม `CRM` ที่ไม่พบวิชาตรงในข้อมูลปัจจุบัน และ `NLP` ที่ตรง2วิชา ไม่คัดลอกกฎเลือก exact แทนผลกำกวมหรือ bypass ตัวเล็ก2ตัวอักษร. ทดสอบ105resolver casesใน7DB (61positive/44ไม่มีวิชา) และ79regressionผ่าน

GE66 ที่ใช้งานมาจาก PDF text layer และข้อมูลที่ตรวจต้นฉบับ ไม่ใช่ผล image OCR ทั้งเล่ม; candidate Tesseract/Typhoon ยังไม่ใช้แทนข้อมูล production การแก้ source เฉพาะหน้าและ SQLite ต้องแยกจากผล pipeline OCR ล้วนในการสาธิต/รายงาน

- Chrome จริงตรวจ idle/loading/success/error, retry, เปลี่ยนแผน, ทิ้งคำตอบเก่าหลังเปลี่ยนแผน และมือถือ 390×844 แล้ว; 8 checks ผ่าน ไม่มี JavaScript exception
- Gold v2.2 HTTP ผ่าน 210/210 ที่ revision `9be5a5c`, qwen3:4b, ไม่มี error/ข้อเกิน 5s; เป็นผลชุดเดิมที่แก้ oracle จากต้นฉบับ ไม่ใช่คะแนนคำถามใหม่
- Trace + positive-path tests ครบ 52/52 shortcuts; มีทั้ง SQL ตรง, คำนวณ/กรองใน Python และข้อมูลข้ามแผน/แคตตาล็อก จึงใช้ช่อง SQL เป็นคำค้นอ้างอิง ไม่รับรอง replay ทุกกรณี
- คำถามใหม่จาก OCR ที่ตรึงก่อนอ่าน runtime ผ่านรอบแรก 16/21; พบ known-none prerequisite และรหัสตัวเลือกสหกิจ 5 ข้อ แก้ guard เดิมพร้อม regression; ไม่เปลี่ยนคำถาม/เฉลยและไม่เรียกคะแนนหลังแก้ว่า unseen
- หลังแก้ที่ `2c20cab`: คำถามใหม่21/21 และ Gold210/210; master220/220 คงโจทย์เพื่อนครบ ทั้งสอง suite1354pass/3skip ก่อน guard-review รอบท้าย; guard หลายเทอม/หลายเรื่อง RED2→GREEN และ affected991pass/3skip ไม่ตอบเพียงส่วนแรก
- รอบ Gold/master ที่ซ้อนกันมี7ข้อเกิน5s (Gold4/master3); วัดเฉพาะ7ข้อซ้ำแบบเดี่ยวได้1.657–4.472sทั้งหมด เก็บรอบโหลดเดิมไว้ ไม่รับรองlatency<5sทุกconcurrency/cold start
- เกณฑ์ Lab11 ที่ตรวจจาก PDF ในเครื่อง: wireframe ที่ `docs/wireframes/curriculum_app.png`, API contract ใน README หลัก และ HTML/CSS/JS เรียก API จริงพร้อม 4 สถานะ; ยังไม่ใช่การรับรองผล Challenge ของอาจารย์หรือเกณฑ์ใหม่ที่ยังไม่ได้รับ
- Local live8000 ย้ายไปใช้ verified production worktree ที่ `c0f73e5` แล้ว: healthยืนยัน source/DB, UI3ไฟล์ตรงbyte,7แผน,21คำตอบตรงผลที่ตรวจ ไม่มีข้อเกิน5s; Chromeจริงคลิกerror/loading/successไม่มีexception Checkoutหลักที่dirtyคงเดิมและสำรอง35ไฟล์พร้อมrollbackแล้ว ไม่mergemain

### เปิดเว็บแล้วขึ้น `ERR_CONNECTION_REFUSED`

FastAPI ยังไม่ได้รัน ให้รันคำสั่ง Uvicorn ด้านบนและเปิด Terminal ค้างไว้

### ขึ้น `No module named fastapi`

ยังไม่ได้ activate venv หรือยังไม่ได้ติดตั้ง `requirements.txt`

### ขึ้น `ไม่พบฐานข้อมูล`

ตรวจว่ามีไฟล์ `Lab7B_Lab8B_ocr_system/runs/<หลักสูตร>/<แผน>/lab8b_output/curriculum.db` (ติดมากับ repo) และค่า `CURRICULUM_DB_PATH` ใน `.env` (ถ้าตั้ง) ถูกต้อง

### เปิดหน้าเว็บได้แต่ถามไม่ได้

เปิด `/api/health` แล้วตรวจว่า `database_ready` และ `ollama_ready` เป็น `true`

<!-- Qwen สร้าง SQL จากคำถามที่ [model_service.py (line 50)](/E:/69/Lab3_ocr_system - Copy/ocr_system/lab10_fastapi/curriculum_app/model_service.py:50)
นำ SQL ไปอ่าน SQLite แบบ readonly=True ที่ [database.py (line 61)](/E:/69/Lab3_ocr_system - Copy/ocr_system/lab10_fastapi/curriculum_app/database.py:61)
ส่งเฉพาะ rows ที่ได้จากฐานข้อมูลให้ Qwen สรุปคำตอบที่ [model_service.py (line 71)](/E:/69/Lab3_ocr_system - Copy/ocr_system/lab10_fastapi/curriculum_app/model_service.py:71)
Endpoint /api/ask ไม่ได้เรียก OCR หรืออ่าน PDF เลย -->

<!-- ไม่ได้ส่งหนังสือหลักสูตรทั้งเล่มเข้า LLM ทุกครั้ง
OCR/ประมวลผลหนังสือจะเกิดเฉพาะตอนสร้างหรืออัปเดตฐานข้อมูล เช่น รัน:
python Lab7B_Lab8B_ocr_system/run_lab8b.py --plan <แผน>
ส่วน:
python Lab7B_Lab8B_ocr_system/run_lab8b.py --plan <แผน> --skip-lab7
จะไม่ OCR หนังสือใหม่ แต่จะนำผลเดิมมาสร้าง curriculum.db ใหม่ -->
