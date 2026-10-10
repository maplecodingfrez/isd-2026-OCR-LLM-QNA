# isd-2026-OCR-LLM-QNA
> ระบบถาม-ตอบเล่มหลักสูตร (AIT / BIT / DSBA / IT) — พิมพ์คำถามภาษาไทย ได้คำตอบพร้อมหน้าอ้างอิงในเล่ม

## งาน Lab 11 (Front-End) อยู่ที่ไหน

| งานที่ส่ง | ที่อยู่ในรีโป |
|---|---|
| Wireframe | [`docs/wireframes/curriculum_app.png`](docs/wireframes/curriculum_app.png) (ต้นฉบับ [Figma](https://www.figma.com/design/u3nW7UBo6zoQ2UHUzAVgBa)) |
| API contract | [`lab10_fastapi/README.md`](lab10_fastapi/README.md) หัวข้อ 13 |
| `index.html`, `style.css`, `app.js` | [`lab10_fastapi/curriculum_app/static/`](lab10_fastapi/curriculum_app/static/) |

ใช้งานได้ทันทีหลัง clone: ฐานข้อมูล 7 แผนและหน้าเว็บอยู่ใน repo แล้ว ไม่ต้องมี PDF หรือไฟล์ `.env`

## 0. เตรียมเครื่อง (ครั้งเดียวต่อเครื่อง ข้ามได้ถ้ามีครบแล้ว)

เริ่มจากเครื่องที่ยังไม่มีอะไรเลย (ตัวอย่างนี้ใช้ Windows และ PowerShell) ต้องต่ออินเทอร์เน็ตตอนติดตั้งและดึงโมเดลครั้งแรกเท่านั้น หลังจากนั้นใช้งานแบบออฟไลน์ได้

1. ติดตั้ง **Python 3.10 ขึ้นไป** จาก <https://www.python.org/downloads/> ตอนติดตั้งต้องติ๊ก "Add python.exe to PATH"
2. ติดตั้ง **Git** จาก <https://git-scm.com/downloads>
3. ติดตั้ง **Ollama** จาก <https://ollama.com/download> (ใช้ CPU ได้ ไม่ต้องมี GPU)
4. ปิดแล้วเปิดเทอร์มินัลใหม่ (กด Start พิมพ์ `PowerShell` แล้วเปิด) เพื่อให้เครื่องรู้จักคำสั่งที่เพิ่งติดตั้ง จากนั้นเช็กว่าได้เวอร์ชันทั้งสามตัว:
   ```powershell
   python --version
   git --version
   ollama --version
   ```
   ถ้าตัวไหนขึ้นว่าไม่รู้จักคำสั่ง ให้ปิดเทอร์มินัลแล้วเปิดใหม่อีกครั้ง หรือติดตั้งตัวนั้นใหม่

ใช้พื้นที่ดิสก์ประมาณ 3 GB สำหรับโมเดล `qwen3:4b` (ดึงในข้อ 1.1)

## 1. รันระบบ

**สรุป:** ติดตั้งครั้งแรกทำข้อ 1.1 ครั้งเดียว หลังจากนั้นทุกครั้งใช้ 3 คำสั่งในข้อ 1.2 (`ollama serve` → เปิด venv → `uvicorn`) แล้วเปิด <http://127.0.0.1:8000/>

### 1.1 ติดตั้งโปรเจกต์ (ครั้งเดียวต่อเครื่อง)
เปิด PowerShell แล้วเลือกที่เก็บโปรเจกต์ (ตัวอย่างนี้ใช้ Documents) คำสั่ง `git clone` จะสร้างโฟลเดอร์ `isd-2026-OCR-LLM-QNA` ให้เอง
```powershell
cd $HOME\Documents                # macOS/Linux: cd ~/Documents
git clone https://github.com/maplecodingfrez/isd-2026-OCR-LLM-QNA.git
cd isd-2026-OCR-LLM-QNA
python -m venv .venv
.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -r lab10_fastapi/curriculum_app/requirements.txt
ollama pull qwen3:4b
```
เมื่อ venv ทำงานจะมี `(.venv)` นำหน้าบรรทัดคำสั่ง · `pip install` ใช้เวลาประมาณ 1–2 นาที · `ollama pull` ดาวน์โหลด ~3 GB ครั้งเดียว

> Windows ฟ้อง execution policy ดูวิธีแก้ในหัวข้อ "แก้ปัญหา"

### 1.2 เปิดใช้งาน (ทุกครั้งที่เปิดเครื่องใหม่)
ใช้เทอร์มินัล 2 หน้าต่าง (PowerShell หรือเทอร์มินัลใน VSCode: Terminal > New Terminal) ทั้งสองหน้าต่างต้องอยู่ที่โฟลเดอร์โปรเจกต์ ถ้าเพิ่งเปิดเทอร์มินัลใหม่ให้เข้าโฟลเดอร์ก่อน:
```powershell
cd $HOME\Documents\isd-2026-OCR-LLM-QNA
```

**เทอร์มินัล 1: เปิด Ollama** (เปิดค้างไว้ ข้ามได้ถ้าแอป Ollama เปิดอยู่ในถาดระบบแล้ว)
```powershell
ollama serve
```

**เทอร์มินัล 2: เปิดแอป**
```powershell
.venv\Scripts\Activate.ps1
python -m uvicorn lab10_fastapi.curriculum_app.main:app --host 127.0.0.1 --port 8000
```
รอจนขึ้น `Application startup complete` (ครั้งแรกโมเดลโหลดช้า) แล้วเปิดเบราว์เซอร์ไปที่ <http://127.0.0.1:8000/> · หยุดด้วย `Ctrl+C`

### 1.3 อ่านเล่มหลักสูตร PDF เข้าระบบ (ทำเมื่อมีเล่มใหม่/แก้เล่ม)
ข้ามได้ถ้าใช้เล่มเดิม 7 แผน เพราะ `curriculum.db` อยู่ใน repo แล้ว ถ้าต้องสร้างฐานข้อมูลจาก PDF เอง ทำตามลำดับนี้ (เปิด `ollama serve` และเปิด venv ไว้ก่อน)

**เพิ่มที่ต้องมี:**
- [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) + ข้อมูลภาษา `tha` และ `eng` (เช็กด้วย `tesseract --list-langs`)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases) (ใช้แปลงหน้า PDF เป็นภาพ) แตก zip แล้วเพิ่มโฟลเดอร์ `Libraryin` เข้า PATH เช็กด้วย `pdftoppm -v` (macOS: `brew install poppler`, Linux: `apt install poppler-utils`)
- `ollama pull scb10x/typhoon-ocr1.5-3b` (อ่านภาพหน้าแผน)
- แพ็กเกจ Python สำหรับขั้น OCR (ติดตั้งใน venv เดิม ใช้เวลา ~1–2 นาที):
  ```powershell
  pip install -r requirements.txt
  ```
  ไฟล์นี้มีเฉพาะแพ็กเกจที่ใช้จริง พร้อมคอมเมนต์ว่าแต่ละตัวใช้ทำอะไร ส่วนเอนจินเสริม (`paddleocr` `paddlepaddle` `torch` `transformers`) แยกไว้ที่ `requirements-extra-engines.txt` ไม่ต้องติดตั้ง เพราะระบบนี้ใช้ Tesseract อย่างเดียว (และ `paddlepaddle` ติดตั้งไม่ได้บน Python 3.14)

1. วาง PDF ที่ `data/input/<หลักสูตร>_curriculum.pdf` (`ait` `bit` `dsba` `it`) · ไฟล์ PDF ไม่ได้อยู่ใน git ดาวน์โหลดจาก [Google Drive: `data/input`](https://drive.google.com/drive/folders/1crBEmbONwORI_MMpcAFGK9rTr5WFiP_I)
2. OCR ทั้งเล่มด้วย **Tesseract เท่านั้น** (ใส่ `--engine tesseract` เสมอ ค่าเริ่มต้นของ CLI คือ `ensemble` ซึ่งจะได้ผลต่างจากที่ระบบนี้ปรับกฎไว้) บางหน้า/บางจุดอาจอ่านเพี้ยน ขั้นหลังมีกฎซ่อมให้แล้ว (ใช้ตอบเรื่องวิชาบังคับก่อน คำอธิบายวิชา เกณฑ์จบ และหน้าอ้างอิง):
   ```powershell
   $env:PYTHONPATH="src"
   python -m ocr_system.cli ocr data/input/dsba_curriculum.pdf --output-dir outputs/dsba --engine tesseract --languages tha+eng --workers 4
   ```
   ได้ `outputs/dsba/dsba_curriculum_ocr.txt` และ `.json`
3. ใส่ภาพหน้าแผนการศึกษา (เฉพาะหน้าตารางปี/เทอม) ไว้ที่ `Lab7B_Lab8B_ocr_system/runs/<หลักสูตร>/[coop|no_coop]/data_input/` ตั้งชื่อ `<หลักสูตร>_<เลขหน้า PDF>.png` เช่น `DSBA_19.png`
4. สร้างฐานข้อมูล (เต็มรอบ: Typhoon-OCR + qwen3 อ่านภาพหน้าแผน **ช้า** ใช้เวลาหลายสิบนาทีต่อแผน):
   ```powershell
   cd Lab7B_Lab8B_ocr_system
   python run_lab8b.py --plan dsba_coop      # ait | bit_coop | bit_no_coop | dsba_coop | dsba_no_coop | it_coop | it_no_coop
   cd ..
   ```
   ได้ `runs/DSBA/coop/lab8b_output/curriculum.db` (สคริปต์รัน verify ให้ในตัว ดูผลที่ `verify.json`) ใช้ `--skip-lab7` ถ้าต้องการใช้ผลอ่านภาพเดิมแล้วรันเฉพาะขั้นหลัง
5. **รีสตาร์ต `uvicorn`** (ข้อ 1.2) แล้วถามผ่านหน้าเว็บตามข้อ 2

> **เวลาที่ใช้จริง (ซ้อมกับ PDF DSBA 403 หน้า, `--workers 4`):** ขั้น 2 (OCR ทั้งเล่ม) ประมาณ **1.5 ชั่วโมง** · ขั้น 4 เต็มรอบประมาณ **20 นาที** ต่อแผน (ใช้ `--skip-lab7` เหลือไม่ถึงนาที เพราะข้ามการอ่านภาพ) จึงควรเริ่มก่อนเวลาใช้งานมาก
>
> **คำเตือน — ห้ามทับฐานข้อมูลที่ใช้อยู่:** ผลจากโมเดลอ่านภาพไม่นิ่งทุกครั้งที่รัน (ซ้อมแล้วป้าย บังคับ/เลือก ของ 3 วิชาเปลี่ยน) และข้อความ OCR ที่สร้างใหม่ได้ไม่เหมือนไฟล์ที่ commit ไว้ (ตรงกันระดับบรรทัด ~85%) ผลคือตาราง `credit_structure` ว่างและ `course_description` หายไป 10 แถว ถ้าใช้เล่มเดิมให้ใช้ `curriculum.db` ที่อยู่ใน repo ไม่ต้องรันข้อนี้ ถ้าจำเป็นต้องสร้างใหม่ ให้ทำในโฟลเดอร์สำเนา (เช่น `git worktree add ../tmp-run`) แล้วตรวจก่อนนำไปใช้

## 2. ใช้งาน
เปิด <http://127.0.0.1:8000/>

1. เลือกหลักสูตร (7 แผน: AIT, BIT / DSBA / IT แบบสหกิจและไม่สหกิจ)
2. พิมพ์คำถามภาษาไทย 2–500 ตัวอักษร แล้วกด "ถาม"
3. ได้คำตอบ + หน้าอ้างอิง (หน้า PDF / หน้าที่พิมพ์ รหัสและชื่อวิชา) · "คัดลอกคำตอบ" คัดลอกเฉพาะคำตอบ + หน้าอ้างอิงเป็นข้อความล้วน · "คัดลอกเป็น JSON" คัดลอกเป็น JSON (มี `answer` และ `citation_text`)

**ลองถาม:** `ปี 1 เทอม 1 เรียนอะไรบ้าง` · `วิชา Calculus 1 กี่หน่วยกิต` · `การจะเรียนวิชา DATA WAREHOUSE ต้องผ่านวิชาอะไรมาก่อน` · `ปี 2 เทอม 1 มีกี่หน่วยกิต` · `แผนสหกิจกับไม่สหกิจต่างกันอย่างไร`

คำถามที่เล่มไม่มีคำตอบจะได้ "ไม่พบข้อมูลนี้ในเล่มหลักสูตร" (ระบบไม่เดา)

ตรวจความพร้อม <http://127.0.0.1:8000/api/health> ต้องได้ `status: ok` · เอกสาร API <http://127.0.0.1:8000/docs>

## 3. ทดสอบ challenge (handydrive)
อาจารย์ให้คำถามชุดหนึ่งผ่าน handydrive ให้พิมพ์ลงหน้าเว็บทีละข้อ แล้วส่งคำตอบรวมเป็นไฟล์ text ไฟล์เดียว

1. เปิดระบบตามข้อ 1.2 (เครื่องใหม่ให้ทำข้อ 1.1 ก่อน) และเช็ค <http://127.0.0.1:8000/api/health> ได้ `status: ok` · ถ้าอาจารย์ให้เล่มใหม่ ทำข้อ 1.3 ก่อน
2. คัดลอกไฟล์คำถามจาก handydrive ลงเครื่อง
3. ทีละข้อ: เลือกหลักสูตร/แผนให้ตรงกับคำถาม → พิมพ์คำถามลงช่อง → กด "ถาม" → รอคำตอบ
4. กดปุ่ม **"คัดลอกคำตอบ"** (ได้ข้อความล้วน: คำตอบ + หน้าอ้างอิง ไม่มี JSON) แล้ววางต่อท้ายไฟล์ `<ชื่อกลุ่ม>.txt` โดยใส่เลขข้อกำกับก่อนทุกครั้ง (ใช้ Notepad ได้) คำตอบหนึ่งข้อต่อหนึ่งบล็อก:
   ```text
   ข้อ 1: <คำถาม>
   <ข้อความที่วางจากปุ่ม "คัดลอกคำตอบ">

   ข้อ 2: ...
   ```
   ถ้าต้องการข้อมูลครบ (มีคำถาม โปรแกรม เวลาตอบ) ใช้ปุ่ม "คัดลอกเป็น JSON" แทนได้ ถ้าเบราว์เซอร์คัดลอกอัตโนมัติไม่ได้ จะมีกล่องข้อความขึ้นมาให้กด Ctrl+C เอง
5. ตอบครบทุกข้อแล้ว บันทึกไฟล์ `<ชื่อกลุ่ม>.txt` (UTF-8) ใส่กลับใน handydrive ของอาจารย์ ถือว่าสอบเสร็จ

ข้อควรรู้: ข้อที่เล่มไม่มีคำตอบระบบจะตอบ "ไม่พบข้อมูลนี้ในเล่มหลักสูตร" ให้ส่งตามนั้น ไม่ต้องแก้คำตอบด้วยมือ (ข้อนี้ก็กด "คัดลอกคำตอบ" ได้เหมือนข้ออื่น)

## แก้ปัญหา
| อาการ | วิธีแก้ |
|---|---|
| พอร์ต 8000 ถูกใช้อยู่ | เปลี่ยน `--port 8001` แล้วเปิด URL ตามพอร์ตใหม่ |
| `/api/health` ไม่ ok / แจ้งเชื่อมต่อ Ollama ไม่ได้ | ตรวจว่า `ollama serve` ทำงาน และ `ollama list` เห็น `qwen3:4b` |
| ถามแล้วช้าครั้งแรก | ปกติ — โมเดลกำลังโหลด ครั้งถัดไปเร็วขึ้น |
| `ollama` ไม่รู้จักคำสั่ง | ปิดแล้วเปิดเทอร์มินัลใหม่หลังติดตั้ง Ollama (ต้องโหลด PATH ใหม่) |
| `Activate.ps1` ฟ้อง execution policy | รัน `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` แล้วลองใหม่ |

> ถ้าไม่เปิด Ollama ระบบตอบได้เฉพาะคำถามที่มีกฎตายตัว (ราว 30–45%) ที่เหลือจะแจ้งว่าเชื่อมต่อไม่ได้

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
├── Lab9_evaluation/                # ชุด Gold Questions + รายงาน metric
├── docs/                           # wireframe, รายงาน
└── src/, scripts/, outputs/, data/ # งาน Lab 3–6 (ไม่ต้องใช้รันแอป)
```

## เอกสารเพิ่มเติม
- ไฟล์ส่งงานบน Google Drive: [โฟลเดอร์หลัก](https://drive.google.com/drive/folders/1mhhxO0R8MMXIJNS68DoQGWU53jR4lau-) · PDF หลักสูตร (`data/input/`) · สไลด์นำเสนอ `.pdf` (`slides/`) · คลิปเดโม (`demo-video/`)
- API / สถาปัตยกรรม / ส่งคำถามเป็นชุด (`ask-batch`) / ข้อจำกัดที่รู้อยู่: [`lab10_fastapi/README.md`](lab10_fastapi/README.md)
- เทสต์: อยู่ใน branch `dev/tests` (`git checkout dev/tests`)
- ความแม่นยำ: ชุดคำถามอิสระ + Master Test Suite ราว 75–79% กับสำนวนที่ไม่เคยเห็น

## สมาชิก
- นายวีร์กฤต โอวาทสาร 67070168
- นายสิทธิชัย เมฆขยาย 67070185
- นายอธิบดี บูรณากาญจน์ 67070195
