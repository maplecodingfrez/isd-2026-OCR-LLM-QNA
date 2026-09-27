# Transcript App — Application 2 (ISD Chapter 10)

Transcript Application คือ Web API สำหรับสกัดข้อมูลจากใบแสดงผลการเรียน (Transcript) ด้วย OCR และวิเคราะห์ข้อมูลออกมาเป็น JSON โครงสร้าง ตามที่สอนในสไลด์ ISD Chapter 10 (สไลด์ที่ 25 และ 27)

```text
Upload PDF/Image
  → ตรวจสอบชนิดไฟล์ (415) และขนาด (413)
  → บันทึกลงโฟลเดอร์ชั่วคราว
  → Preprocessing (none / denoise / threshold)
  → OCR & Field Extraction
  → ลบไฟล์ชั่วคราวทิ้งทันที (ไม่มีไฟล์ค้างในเครื่อง)
  → ส่งคืน JSON ผลลัพธ์
```

---

## 1. Endpoints ทั้งหมด (สไลด์ที่ 27)

| Method | Path | Content-Type | หน้าที่ / ผลลัพธ์ | Status Code |
|---|---|---|---|---|
| `GET` | `/` | text/html | ส่งคืนหน้าเว็บ `static/index.html` | 200 OK |
| `GET` | `/api/health` | application/json | ตรวจสอบสถานะระบบ, โมเดล OCR/Text, และขนาดไฟล์สูงสุด | 200 OK |
| `POST` | `/api/transcript/extract` | `multipart/form-data` | อัปโหลดไฟล์เพื่อทำ OCR และสกัดข้อมูลนักศึกษา/รายวิชา | 200 OK |

---

## 2. พารามิเตอร์ของ `POST /api/transcript/extract`

- `file` (Required): ไฟล์ใบแสดงผลการเรียน รองรับเฉพาะนามสกุล `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`
- `preprocessing` (Optional): การปรับสภาพภาพก่อนส่งเข้า OCR ค่าเริ่มต้นคือ `none` (ตัวเลือก: `none`, `denoise`, `threshold`)
- `include_markdown` (Optional): เป็น boolean (true/false) ขอผลสรุปรูปแบบ Markdown แนบมาด้วยหรือไม่ (ค่าเริ่มต้น `false`)

---

## 3. ด่านตรวจและการจัดการ Error Codes (สไลด์ที่ 27 & 30)

| Status Code | ข้อความ / กรณีที่เกิดขึ้น | การแก้ไข |
|---|---|---|
| `200 OK` | สกัดข้อมูลสำเร็จ ส่งคืน JSON | — |
| `413 Payload Too Large` | ขนาดไฟล์เกินเพดานที่กำหนดใน `TRANSCRIPT_MAX_UPLOAD_MB` (ค่าเริ่มต้น 15 MB) | ย่อขนาดไฟล์หรือปรับ config ใน `.env` |
| `415 Unsupported Media Type` | นามสกุลไฟล์ไม่ใช่ PDF, PNG, JPG, หรือ TIFF | เลือกไฟล์รูปภาพหรือเอกสารที่ถูกต้อง |
| `422 Unprocessable Content` | OCR หรือตัวอ่านเอกสารอ่านไม่ออก เอกสารเสียหาย หรือข้อความว่างเปล่า | ตรวจสอบคุณภาพไฟล์ |
| `503 Service Unavailable` | ระบบยังไม่พร้อม (เช่น ไม่สามารถเชื่อมต่อ Ollama ได้) | ตรวจสอบการรัน Ollama |

---

## 4. วิธีการรันเซิร์ฟเวอร์

จากรากของโปรเจกต์ (`isd-2026-OCR-LLM-QNA`):

```bash
python -m uvicorn lab10_fastapi.transcript_app.main:app --reload --host 127.0.0.1 --port 8001
```

เปิดทดสอบผ่านเบราว์เซอร์:
- **หน้าเว็บแอปพลิเคชัน:** <http://127.0.0.1:8001/>
- **Swagger Interactive API Documentation:** <http://127.0.0.1:8001/docs>
- **ReDoc Documentation:** <http://127.0.0.1:8001/redoc>
- **Health Check Endpoint:** <http://127.0.0.1:8001/api/health>
