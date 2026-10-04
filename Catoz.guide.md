# ขั้นตอนรวม `lab10_1` เข้า `main` (สำหรับ Catoz)

**ก่อนเริ่ม:** รอให้ Synthesizzz merge `feature/gold-questions-v2` และ `Lab-10-synthesis` เข้า `main` ก่อน

`lab10_1` แตกมาจาก `main` เก่าวันที่ 22 ก.ย. พอ `main` อัปเดตแล้ว จะชนกัน 4 ไฟล์ ขั้นตอนนี้ให้รวมงานของทั้งสองคนครบ
ไม่มีใครทับใคร (วิธีรวมนี้ทดสอบในเครื่องแล้ว: เทสผ่าน 114/114, หน้าเว็บโหลดได้, endpoint ของทั้งสองคนใช้ได้)

## 1. ดึง `main` ล่าสุดเข้า branch ของตัวเอง

```bash
git checkout lab10_1
git status                 # ต้องไม่มีงานค้าง ถ้ามีให้ commit ก่อน
git fetch origin
git merge origin/main      # ใช้ merge ไม่ใช้ rebase จะได้ไม่ต้อง force push
```

Git จะแจ้ง `CONFLICT` 4 ไฟล์ ได้แก่ `main.py`, `static/index.html`, `.gitignore`, `README.md` ตามคาด

## 2. แก้ `lab10_fastapi/curriculum_app/main.py` (ชน 2 จุด)

- **จุดที่ 1 (import จาก `.schemas`):** เอาของทั้งสองฝั่ง

  ```python
  from .schemas import (  # noqa: E402
      AskRequest, AskResponse, CourseCreate, CourseResponse, HealthResponse, ProgramInfo,
      CoursePrerequisitesResponse,
  )
  ```

- **จุดที่ 2 (`/api/ask` ติดกับ endpoint ใหม่):**
  - ฝั่ง HEAD (`try:` … `finally: conn.close()` … `return result`) เป็นของ `main` ที่ใช้ `lab8b.ask()` มีอ้างอิงหน้าและเลือกแผน
    **ให้เก็บทั้งหมด**
  - ฝั่ง `lab10_1` ให้ลบบรรทัด `except (ValueError, json.JSONDecodeError, sqlite3.Error)` ซึ่งเป็นของ `/api/ask` แบบเก่า
  - เก็บ `@app.get("/api/courses/{code}/prerequisites" ...)` ทั้งฟังก์ชัน ไว้ต่อท้าย `/api/ask`

## 3. แก้ `lab10_fastapi/curriculum_app/static/index.html` (ชน 3 จุด)

- **จุดที่ 1 (ส่วนหัวและฟอร์มถาม):** ใช้ฝั่ง HEAD เพราะมี dropdown `<select id="program">` สำหรับเลือกแผน
- **จุดที่ 2 (ส่วนคำตอบ + script):** เรียงตามนี้
  1. ฝั่ง HEAD ตั้งแต่ `<h2>คำตอบ</h2>` ถึง `</section>` (มี `citations` กับ `elapsed`)
  2. ต่อด้วย **section ตรวจวิชาบังคับก่อนของตัวเอง** ตั้งแต่ `<!-- ส่วนที่ 2 ...` ถึง `</section>`
  3. ต่อด้วยฝั่ง HEAD ตั้งแต่ `<script>` จนจบ block (มี `loadPrograms()` และ handler ของ ask-form)
  4. ส่วนหัว `💬 ถามคำถามหลักสูตร` และฟอร์มถามของฝั่ง `lab10_1` ไม่ต้องเอา เพราะซ้ำกับของ HEAD
- **จุดที่ 3 (`body` ของ fetch `/api/ask`):** ใช้ฝั่ง HEAD ที่ส่ง `program` ไปด้วย
- ตรวจให้แน่ใจว่าไม่มี `id` ซ้ำกันในหน้า

## 4. แก้ `.gitignore` กับ `README.md`

- **`.gitignore`:** ใช้ฝั่ง HEAD ซึ่งใช้ชื่อโฟลเดอร์ใหม่ `Lab7B_Lab8B_ocr_system/…` แล้วเพิ่มบรรทัด `work/` ของตัวเองต่อท้าย
- **`README.md`:** เก็บทั้งสองส่วน คือส่วนชุดคำถามทองของ HEAD ตามด้วยส่วน Lab 10 ของตัวเอง
  ถ้าในส่วนของตัวเองมีชื่อโฟลเดอร์เก่า `Lab8b_ocr_system` ให้แก้เป็น `Lab7B_Lab8B_ocr_system`

## 5. ลบสำเนาโมดูล Lab 8B ที่คัดลอกมา

`main` import โมดูล Lab 8B ตัวจริงจาก `Lab7B_Lab8B_ocr_system/src/ocr_system/` อยู่แล้ว สำเนาใน `src/ocr_system/` เป็นรุ่นเก่า
ถ้าเก็บไว้จะมีโค้ดสองชุดที่ไม่อัปเดตตามกัน

```bash
git rm src/ocr_system/lab8b_curriculum_db.py
```

## 6. ทดสอบก่อน commit

```bash
grep -rn "^<<<<<<<\|^>>>>>>>" lab10_fastapi README.md .gitignore   # ต้องไม่เจออะไร
python -m pytest tests -q                                           # ต้องผ่านทั้งหมด
python -m uvicorn lab10_fastapi.curriculum_app.main:app --reload --port 8000
```

เปิด http://127.0.0.1:8000 แล้วเช็ก:

- dropdown มี 7 แผน, ถามแล้วได้คำตอบพร้อมอ้างอิงหน้าและเวลาที่ใช้
- ตรวจวิชาบังคับก่อน `06066102` ต้องได้ `06066101`
- `/api/courses/123/prerequisites` ต้องได้ 422 และ `/api/courses/99999999/prerequisites` ต้องได้ 404

## 7. commit, push และเปิด PR

```bash
git add -A
git commit -m "Merge main into lab10_1: keep ask/programs from main, add prerequisites endpoint and page section, drop stale lab8b copy"
git push origin lab10_1
```

- เปิด PR `lab10_1` → `main` บน GitHub
- ตอนกด merge ให้เลือก **"Create a merge commit"** ห้ามเลือก Squash เพราะ commit จะรวมเป็นก้อนเดียวในชื่อคนกด
  และประวัติ contributor ของตัวเองจะหาย

## (ไม่บังคับ) ให้ endpoint ตามแผนที่เลือก

- **ตอนนี้:** `/api/courses/{code}/prerequisites` อ่าน DB จาก `.env` แผนเดียว และข้อความในหน้าเว็บเขียนตายตัวว่า
  "หลักสูตร IT 41 รายวิชา" ซึ่งจะไม่ตรงถ้า `.env` ชี้แผนอื่น
- **ถ้าจะปรับ:**
  - รับ `?program=` แล้วใช้ `program_db_path()` ใน `config.py` แบบเดียวกับ `/api/ask` (ชื่อแผนไม่มี = 404, ไม่มีไฟล์ = 503)
  - ส่งค่าจาก dropdown `program` ไปด้วย
  - ลบข้อความ "IT 41 รายวิชา" ออก
