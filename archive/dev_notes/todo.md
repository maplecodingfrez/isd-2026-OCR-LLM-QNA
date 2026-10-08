# 📋 Lab 11 — Front-End Development TODO

> **เป้าหมาย:** สร้างหน้าเว็บที่ส่งข้อมูลให้โมเดลของกลุ่มผ่าน API และแสดงผลได้  
> **ส่งงาน:** push ขึ้น repo กลุ่ม — wireframe, README (contract), `index.html`, `style.css`, `app.js`

---

## สิ่งที่มีอยู่แล้ว

| สิ่งที่มี | ที่ไหน |
|---|---|
| FastAPI backend + routes | `src/ocr_system/api/` (app.py, routes.py, schemas.py, service.py) |
| API endpoints | `POST /api/v1/ocr/process`, `GET /api/v1/documents`, `POST /api/v1/curriculum/extract`, `GET /api/v1/health` |
| ตัวอย่าง frontend (transcript_app) | `lab10_fastapi/transcript_app/static/index.html` — แต่เป็นของ lab10 ยังรวมทุกอย่างไว้ในไฟล์เดียว |

---

## ✅ TODO — เรียงตามลำดับ

### Phase 1: Wireframe (วาดก่อนเขียนโค้ด)

- [ ] **1.1** ออกแบบ Wireframe — กำหนดว่ามีกี่หน้า ใครเห็นหน้าไหน
  - หน้าหลัก: อัปโหลดเอกสาร + แสดงผล OCR
  - หน้ารายการเอกสาร: แสดง list เอกสารที่เคย process
  - (optional) หน้า Curriculum Extract: ส่ง JSON ไป extract หลักสูตร
- [ ] **1.2** วาดบนกระดาษ / Figma / เครื่องมืออื่น
- [ ] **1.3** บันทึก wireframe เป็นไฟล์ภาพ → ใส่ไว้ในโฟลเดอร์ `docs/wireframes/`

### Phase 2: API Contract (เขียนใน README)

- [ ] **2.1** เขียน/อัปเดต `README.md` ส่วน **API Contract** ระบุ endpoint ทั้งหมดที่ frontend จะเรียก
- [ ] **2.2** ตรวจสอบว่า contract ตรงกับ `src/ocr_system/api/schemas.py` และ `routes.py`

### Phase 3: สร้าง Frontend (index.html + style.css + app.js)

- [ ] **3.1** สร้างโฟลเดอร์ `frontend/` ที่ root ของ repo (แยก CSS/JS เป็นไฟล์ external ตาม L11 slide 8)
- [ ] **3.2** `index.html` — โครงสร้าง semantic HTML5, ฟอร์มอัปโหลด, ส่วนแสดงผล, link CSS/JS
- [ ] **3.3** `style.css` — Layout (Flexbox/Grid), Responsive (Media Query), สไตล์ 4 สถานะ
- [ ] **3.4** `app.js` — fetch + async/await, classList เปลี่ยนสถานะ, เช็ก response.ok, try/catch
- [ ] **3.5** ต้องมีครบ **4 สถานะ** (Idle / Loading / Success / Error) — ห้ามฝัง API key

### Phase 4: ทดสอบ & Debug

- [ ] **4.1** รัน backend: `uvicorn src.ocr_system.api.app:app --reload`
- [ ] **4.2** ทดสอบทั้ง 4 สถานะจริง (อัปโหลดสำเร็จ, ไฟล์ผิดประเภท, ปิด server, idle)
- [ ] **4.3** ใช้ DevTools ตรวจ Console / Network / Elements
- [ ] **4.4** ทดสอบ Responsive

### Phase 5: Push ขึ้น Git

- [ ] **5.1** ตรวจไฟล์ครบ: wireframe, README, index.html, style.css, app.js
- [ ] **5.2** `git add` + `git commit` + `git push`
- [ ] **5.3** ตรวจบน GitHub ว่าไฟล์ขึ้นครบ

---

## 🔔 เตรียมตัวครั้งหน้า (5/10/2026)

- [ ] ระบบต้องทำงานได้จริง — challenge test ในคาบ 10:00-12:00
- [ ] ถ้าติด bug ระหว่าง test → คะแนน challenge = 0
- [ ] ส่ง: ไฟล์ JSON transcript (Accuracy, CER, WER) + ผลตอบ curriculum
- [ ] ส่งผลลง Discord กลุ่มทันทีหลัง test เสร็จ
