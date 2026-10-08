# GE66 OCR recovery — 2026-10-08

## ผลลัพธ์

ทำครบตามลำดับ: ซ่อมการโหลด Typhoon → อ่านหน้า 18 ต่อ → อ่านซ้ำแถวที่ขัดกัน → วัด 303 วิชา → ทดลอง Lab8B แยก

- หน้า 18 ครบ **19/19 วิชา** ชื่อไทย อังกฤษ และหน่วยกิตตรงอ้างอิงทั้งหมด
- อ่านซ้ำ **84 แถว** จากความต่าง/การขาดของสอง engine โดยใช้ภาพรายวิชาเท่านั้น
- candidate รอบแรกครบ 303 วิชา แต่ตรงทุกช่อง 295 วิชา; อ่านแบบ literal เพิ่ม 8 วิชาได้ 301 วิชา
- อ่านชื่ออังกฤษแยกบรรทัดด้วย Tesseract และเลือกเฉพาะเมื่อเนื้อหาตรงกับ Typhoon กู้ apostrophe จากภาพอีก 2 วิชา
- candidate สุดท้าย **303/303 วิชา** ตรงทั้งชื่อไทย อังกฤษ และโครงสร้างหน่วยกิต พร้อมตรวจหน้าและ graded_su
- ตรวจย้อนกลับ **909/909 ช่อง** พบค่าจากผล OCR จริง ไม่มีการเติมค่าจาก reference ด้วยมือหรือโค้ด
- โหลดลงสำเนา SQLite 5 แผน: AIT, DSBA สหกิจ/ไม่สหกิจ, IT สหกิจ/ไม่สหกิจ; integrity/FK ผ่าน ตารางนอก GE ไม่เปลี่ยน
- เทียบ backend Q&A แบบ database **20/20 คำถามตรงกับฐานข้อมูลเดิม** หลัง normalize Unicode/ช่องว่าง ไม่ใช่ benchmark generative NL2SQL
- Regression: **1014 passed** (ชุดวิชาเลือก 994 + รูปแบบ OCR 16 + การเลือกผล OCR 4)
- แคตตาล็อก ฐานข้อมูล และ Gold จริง **22 ไฟล์ SHA256 เท่าเดิม** ไม่ได้ promote candidate เข้าเว็บ

## วิธีแก้ ไม่ใช่ manual transcription

ใช้ Tesseract หา code anchors จากภาพ แล้ว crop รายวิชาโดยเผื่อสระ/วรรณยุกต์และหยุดก่อนข้อความแถวถัดไป
อ่านด้วย Tesseract และ Typhoon เก็บทุกผลที่ขัดกันไว้; เลือกค่าจาก OCR observations ด้วยกฎคงที่
แถวที่ยังผิดหลังวัดผล ใช้ prompt ให้ถอดตัวอักษรตรงตามภาพ ห้ามแก้คำสะกด/ตัวพิมพ์/เครื่องหมาย
ชื่ออังกฤษบรรทัดเดี่ยวเลือกผล Tesseract เมื่อเนื้อหาเห็นตรงกับ Typhoon โดยเทียบความเท่ากันของ apostrophe เท่านั้น
ไม่ rewrite ข้อความเพื่อให้ตรง reference และไม่ส่งรหัส/ชื่อ/หน่วยกิตที่ถูกต้องให้โมเดล

Reference ใช้เลือกข้อผิดพลาดในรอบพัฒนาและวัดผลหลังอ่านเสร็จ จึงเป็นผล development/reference-reused
ไม่ใช่ held-out test และไม่ใช่หลักฐานว่า OCR อ่านข้อความทั้ง PDF ได้ครบ
การเทียบ 303/303 ใช้ Unicode NFKC และตัดช่องว่างในการเปรียบเทียบ แต่ยังตรวจตัวพิมพ์และ punctuation
ค่าดิบและ candidate ยังเก็บรูปแบบที่ engine อ่าน ไม่คัดลอกข้อความจาก text layer

## Ollama

พบ manifest-v2 ของ Typhoon เป็น symlink ที่ Windows ปฏิเสธ (`untrusted mount point`)
สำรองลิงก์เดิมใต้ `%USERPROFILE%/.ollama/models/repair-backups/20261008-ge66/`
แล้วแทนด้วยไฟล์ manifest เนื้อหาเดิมที่ตรวจ SHA256 แล้ว ไม่มีการเปลี่ยนหรือลบ weights
โมเดลกลับมาปรากฏใน API และรับภาพได้ โดยไม่ต้อง restart/download

ใช้ runner `ggml:8ad769cbef404d27260763e014d082877bbd4d4c4361cd47a141a3d0acff5c47`
ซึ่งอ้าง weights `df8b6415ce11eeaa85d11f8c4288c489aa3818354d9691d71523bcdffb5f2fa8`
เพื่อแยกจาก runner llamacpp ที่ใช้ weights อีกชุด ผลหน้า 18 ช่วงแรกเก็บ digest เดิมแยกจากช่วงที่อ่านต่อ

## ไฟล์และการรันซ้ำ

- `tests/fixtures/ge66/image_ocr_catalog.json`: candidate ที่ผ่าน gate; ยังเป็นชุดทดลอง
- `tests/fixtures/ge66/verified-summary.json`: คะแนน ขอบเขต และ hashes ข้อมูลที่คงเดิม
- `tests/fixtures/ge66/archive/`: สำเนาข้อความ OCR เดิมแบบ portable (ข้อความไม่เปลี่ยน; ตัด metadata เฉพาะเครื่อง)
- ภาพดิบ, responses, trace และ SQLite ทดลอง เก็บในเครื่องใต้ ignored `.superpowers/ge66-ocr-audit/results/`
- เครื่องมือและ tests อยู่ `dev/tests`; parser Unicode punctuation อยู่ `feature/lab11-frontend`; main ไม่ได้ merge

ใช้ Python environment ที่มี PyMuPDF, Pillow, pytesseract, Tesseract tha+eng และ Ollama/Typhoon ที่รับภาพได้
`--root` ต้องชี้ source checkout ที่มี parser fix และ GE66 PDF เครื่องมือไม่ติดตั้งหรือดาวน์โหลดโมเดลเอง

รันตามลำดับ โดยกำหนด `$src`, `$run`, `$model` เป็น source checkout, output ใหม่, runner ของโมเดลในเครื่อง:

```powershell
$archive = 'tests/fixtures/ge66/archive'
python scripts/ge66_typhoon_crops.py --root $src --output "$run/page18" --request-model $model
python scripts/ge66_targeted_retry.py --root $src --archive $archive --page18 "$run/page18/ocr.json" --output "$run/targeted" --request-model $model
python scripts/ge66_select_candidate.py --root $src --observations "$run/targeted/observations.json" --output "$run/selected"
python scripts/ge66_literal_retry.py --root $src --selected "$run/selected" --targeted "$run/targeted" --output "$run/literal" --request-model $model
python scripts/ge66_typographic_consensus.py --root $src --literal "$run/literal" --targeted "$run/targeted" --output "$run/final"
python scripts/ge66_lab8b_trial.py --root $src --archive $archive --candidate "$run/final/candidate.json" --page18 "$run/page18/ocr.json" --output "$run/trial"
```

Ollama versions/runners can change outputs; inspect new results instead of assuming 303/303 repeats.
Lab8B trial refuses to create databases if the catalog, page/flag or parser round-trip gate fails.

## ขั้นต่อไป

candidate พร้อมพิจารณาใช้แทนเฉพาะ GE catalog หลัง review provenance และตัดสินใจ promote
เว็บยังใช้แคตตาล็อกเดิม การ promote หรือ merge main ไม่ได้อยู่ในรอบทดลองนี้
ถ้าจะอ้างคุณภาพ OCR ทั่วไป ต้องทดสอบหน้าหรือเอกสาร held-out และวัดข้อความ/ตารางส่วนอื่นเพิ่มเติม
