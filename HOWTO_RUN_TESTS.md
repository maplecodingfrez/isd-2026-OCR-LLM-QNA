# 🧪 คู่มือการรันชุดทดสอบระบบถาม-ตอบหลักสูตร (Master Test Suite - 210 ข้อ)

เอกสารนี้สำหรับเพื่อนร่วมทีมหรือผู้ตรวจ ใช้รันชุดทดสอบฉบับรวมสมบูรณ์ (Master Test Suite) ครบทุกมิติของระบบ **210 ข้อ** โดยอัตโนมัติ

---

## 📋 1. สิ่งที่ต้องเตรียมก่อนรัน (Prerequisites)

1. **Python 3.10+**
2. **ติดตั้ง Dependencies:**
   ```bash
   pip install -r lab10_fastapi/curriculum_app/requirements.txt
   ```
3. **เปิด Ollama และดึงโมเดลภาษา:**
   - เปิดโปรแกรม Ollama ทิ้งไว้ในเครื่อง
   - ตรวจสอบว่ามีโมเดล `qwen3:4b` หากยังไม่มีให้รัน:
     ```bash
     ollama pull qwen3:4b
     ```

---

## 🚀 2. ขั้นตอนการรันการทดสอบ (2 ขั้นตอน)

### ขั้นตอนที่ 1: สตาร์ท Backend Server (เปิด Terminal 1)
รันคำสั่งที่ root ของโปรเจกต์:
```bash
python -m uvicorn lab10_fastapi.curriculum_app.main:app --host 127.0.0.1 --port 8000
```
> 💡 **ตรวจสอบความพร้อม:** เปิดบราวเซอร์ไปที่ [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) ต้องขึ้นสถานะ:
> ```json
> {"status": "ok", "database_ready": true, "ollama_ready": true}
> ```

---

### ขั้นตอนที่ 2: รันสคริปต์ทดสอบ (เปิด Terminal 2)
เปิด Terminal ที่ 2 (อยู่ที่ root ของโปรเจกต์เช่นกัน) แล้วรัน:
```bash
python run_all_tests.py
```

*(กรณีรัน FastAPI ที่พอร์ตอื่น เช่น 8080 สามารถกำหนด URL ผ่าน Environment Variable ได้:)*
- **PowerShell:** `$env:API_BASE_URL="http://127.0.0.1:8080"; python run_all_tests.py`
- **Bash:** `API_BASE_URL=http://127.0.0.1:8080 python run_all_tests.py`

---

## 📊 3. ผลลัพธ์ที่จะได้รับ

เมื่อรันเสร็จสิ้น สคริปต์จะสร้างและอัปเดตรายงานผลให้อัตโนมัติ:
1. **หน้าจอ Terminal:** แสดงผลลัพธ์ ผ่าน/ไม่ผ่าน แบบ Real-time พร้อมเวลาที่ใช้ในแต่ละข้อ
2. **`test.md`:** รายงานผลฉบับสมบูรณ์ แยกตาม 22 หมวดหมู่ คำนวณเปอร์เซ็นต์ความสำเร็จ และตารางสรุปครบ 210 ข้อ
3. **`test_master_results.json`:** ข้อมูลดิบ (Raw JSON) ของผลการทดสอบทุกข้อ รวมถึง SQL Query และเวลาที่ประมวลผล

---

## 📑 4. ขอบเขตการทดสอบทั้ง 22 หมวดหมู่ (210 ข้อ)

| # | หมวดหมู่การทดสอบ | จำนวนข้อ | คำอธิบาย |
|---|---|:---:|---|
| 01 | **API Infrastructure** | 5 | Health check, รายชื่อ 7 แผน, ค้นหารายวิชา, Prereq endpoint, Swagger docs |
| 02 | **Frontend UI/UX** | 7 | โครงสร้าง HTML, Dropdown 7 แผน, รองรับ 4 สถานะ, ปุ่ม Copy, กล่อง Citation, แยก CSS/JS |
| 03 | **Program Facts** | 4 | หน่วยกิตรวมหลักสูตร IT, DSBA, AIT และระยะเวลาเรียน |
| 04 | **Term Details** | 8 | รายวิชาในแต่ละเทอม, หน่วยกิตประจำเทอม, จำนวนวิชาแต่ละภาค |
| 05 | **Course Lookup & Attributes** | 11 | ค้นหาชื่อไทย/อังกฤษ, รหัสวิชา, ชั่วโมงบรรยาย/ปฏิบัติ, ชั้นปีที่เรียน |
| 06 | **Prerequisites** | 12 | วิชาบังคับก่อนเดี่ยว/ต่อเป็นลูกโซ่, วิชาที่ปลดล็อค, วิชาที่ไม่มีตัวต่อ |
| 07 | **Plan Comparison** | 5 | เปรียบเทียบแผนปกติ vs แผนสหกิจศึกษา |
| 08 | **Complex Filters** | 4 | กรองวิชาตามเงื่อนไขซับซ้อน เช่น จำนวนหน่วยกิต, คำสำคัญ |
| 09 | **Out-of-Scope Guardrails** | 7 | คำถามนอกหลักสูตร (อาหารกลางวัน, หอพัก, บอลโลก) ต้องปฏิเสธอย่างปลอดภัย |
| 10 | **English Acronyms** | 15 | ตัวย่อภาษาอังกฤษ (OS, AI, MIS, DB, OOP, SE, ML, DW, SAD, CAL 1/2, ENG 1 ฯลฯ) |
| 11 | **English Prefixes & Course Names** | 14 | ค้นหาด้วยชื่อวิชาภาษาอังกฤษแบบต่างๆ |
| 12 | **Thai Slang & Short Names** | 16 | คำย่อภาษาพูดไทย (เช่น สหกิจ, อิ้ง 1, แคล 1, โปรแกรมมิ่ง) |
| 13 | **Cross-Program Shared Courses** | 8 | วิชาเรียนร่วมกันข้ามสาขา (DSBA / AIT / IT) |
| 14 | **Free Electives & Slots** | 8 | หมวดวิชาเลือกเสรี, กฎเกณฑ์ 6 หน่วยกิต, วิชาเลือกประจำแผน |
| 15 | **TQF:2 Book Sections** | 12 | ข้อมูลเฉพาะเล่ม มคอ.2 (อาชีพหลังจบ, ปรัชญา, วัตถุประสงค์, คุณสมบัติผู้สมัคร, สถานที่เรียน) |
| 16 | **Multi-Plan Facts & Credit Rules** | 7 | หน่วยกิตรวมและระยะเวลาเรียนตามแผนครบทั้ง 7 แผน (AIT, BIT, DSBA, IT) |
| 17 | **Course Hours & Prereq Chains** | 10 | ชั่วโมงบรรยาย/ปฏิบัติ/ศึกษาด้วยตนเอง, การปลดล็อควิชาต่อ, และวิชาที่ไม่มี prereq |
| 18 | **TQF:2 Multi-Program & Guards** | 17 | ปรัชญา, คุณสมบัติ, ชื่อปริญญาข้ามสาขา, เปรียบเทียบแผน, และ Guardrails สกัดข้อมูลนอกสารบบ |
| 19 | **Multi-Program TQF:2 & Facts** | 12 | เจาะลึก มคอ.2 และแผนการเรียนของ BIT (ปรัชญา, อาชีพ, ชื่อปริญญา, คุณสมบัติ, วิชาปี 1), DSBA, AIT, IT |
| 20 | **Advanced Prereqs & Course Hours** | 15 | กราฟวิชาบังคับก่อนและชั่วโมงเรียนเชิงลึกใน BIT, AIT, DSBA, IT |
| 21 | **Real-World Inquiries & Out-of-Scope Guards** | 3 | คำถามจริงของนักศึกษาที่อยู่นอกเล่ม มคอ.2 (ค่าเทอม, ทุนการศึกษา, หอพัก) ต้องปฏิเสธอย่างปลอดภัย |
| 22 | **Course Families & Degree Framework** | 10 | ค้นหากลุ่มวิชาตามรหัสขึ้นต้น (0601, 0602, 0603, 0604), โครงสร้าง GE และเกณฑ์จบข้ามสาขา |

---

## 🛠️ 5. การแก้ปัญหาที่พบบ่อย (Troubleshooting)

- **`urllib.error.URLError: [WinError 10061] No connection could be made`**
  - **สาเหตุ:** ยังไม่ได้สตาร์ท Backend FastAPI
  - **วิธีแก้:** เปิด Terminal อีกหน้าต่างแล้วรัน `python -m uvicorn lab10_fastapi.curriculum_app.main:app --port 8000`
- **Health Check แจ้ง `ollama_ready: false`**
  - **สาเหตุ:** Ollama ยังไม่ได้ถูกเปิดใช้งาน หรือยังไม่ได้ดึงโมเดล `qwen3:4b`
  - **วิธีแก้:** เปิดโปรแกรม Ollama แล้วรัน `ollama pull qwen3:4b`
- **Port 8000 ชน (Address already in use)**
  - **วิธีแก้:** เปลี่ยนไปรันพอร์ตอื่น เช่น `--port 8080` แล้วรันสคริปต์ด้วย `$env:API_BASE_URL="http://127.0.0.1:8080"; python run_all_tests.py`
