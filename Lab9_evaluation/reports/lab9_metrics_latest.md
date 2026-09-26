# Lab9 evaluation report — 2026-09-26 13:42

อ้างอิงเนื้อหา: `ISD/Learning Slides/ch9_EvaluationAndOverfitting.pdf`
ข้อมูลดิบมาจาก: `Lab7B_Lab8B_ocr_system/runs/<CURRICULUM>/<plan>/lab8b_output/` (สคริปต์นี้แค่คำนวณ ไม่ได้รันโมเดลใหม่)

## 1. Structured-output metrics (Markdown → JSON → curriculum.db)

| run | conversion_rate | skipped_rate | plan_total_credits | declared_total_credits | credits_abs_error | credits_pct_error | verify_pass_rate | failed checks |
|---|---|---|---|---|---|---|---|---|
| ait | 0.8684 | 0.1316 | 99 | 120 | 21 | 17.5 | 0.7143 | CHK1, CHK7 |
| bit_no_coop | 0.8372 | 0.1628 | 105 | 126 | 21 | 16.67 | 0.8571 | CHK1 |
| bit_coop | 0.8182 | 0.1364 | 111 | 126 | 15 | 11.9 | 0.7143 | CHK1, CHK7 |
| dsba_no_coop | 0.6538 | 0.3462 | 99 | 132 | 33 | 25.0 | 0.7143 | CHK1, CHK7 |
| dsba_coop | 0.8065 | 0.4355 | 111 | 132 | 21 | 15.91 | 0.7143 | CHK1, CHK7 |
| it_no_coop | 0.8491 | 0.1509 | 132 | 129 | 3 | 2.33 | 0.7143 | CHK1, CHK7 |
| it_coop | 0.8545 | 0.1091 | 144 | 129 | 15 | 11.63 | 0.7143 | CHK1, CHK7 |

### หน่วยกิตรวม — MAE/MAPE ข้ามหลักสูตร (สไลด์ ch9 ส่วนที่ 2 "งานทำนายค่าต่อเนื่อง")

CHK1 ข้างบนบอกแค่ผ่าน/ไม่ผ่าน (`total == declared` เป๊ะ) ไม่บอกว่าคลาดเคลื่อนไปแค่ไหน — MAE/MAPE ตรงนี้วัดขนาดความคลาดเคลื่อนแทน (ยิ่งต่ำยิ่งดี ตามสไลด์)

- **MAE** = 18.43 หน่วยกิต (เฉลี่ยจาก 7 run ที่มีข้อมูลครบ)
- **MAPE** = 14.42%
- คลาดเคลื่อนมากสุด: **dsba_no_coop** (33 หน่วยกิต)

### หน่วยกิตรวม — นับช่องตามเล่ม (plan_item + plan_slot, CHK1F/CHK7F)

ตารางบนนับแค่วิชารหัสจริงใน `plan_item` จึงขาดหน่วยกิตของช่องวิชาเลือกแบบ wildcard (`06026xxx`) และนับซ้ำคู่ "A หรือ B" / กลุ่ม "เลือก 1 กลุ่ม" — ตารางนี้นับผ่าน `v_semester_credits_full` ของ Lab 8B ซึ่งใช้ `plan_slot` ที่ `md_plan_slots.py` สกัดจาก Markdown ของ OCR ด้วยกฎล้วน (ไม่อ่านเฉลย) · แยกส่วนต่างตาม `verify_full.json`: `slot_adjust` = full − plan_item (ส่วนที่อธิบายได้ด้วยช่องตามเล่ม), `gap_extraction` = declared − full (ส่วนที่ยังอธิบายไม่ได้ ส่วนใหญ่คือ OCR/สกัดตกวิชา)

| run | plan_total_credits | plan_total_credits_full | declared | abs_error_full | pct_error_full | slot_adjust | gap_extraction | failed (full) |
|---|---|---|---|---|---|---|---|---|
| ait | 99 | 120 | 120 | 0 | 0.0 | 21 | 0 | - |
| bit_no_coop | 105 | 126 | 126 | 0 | 0.0 | 21 | 0 | - |
| bit_coop | 111 | 126 | 126 | 0 | 0.0 | 15 | 0 | - |
| dsba_no_coop | 99 | 132 | 132 | 0 | 0.0 | 33 | 0 | - |
| dsba_coop | 111 | 132 | 132 | 0 | 0.0 | 27 | 0 | - |
| it_no_coop | 132 | 129 | 129 | 0 | 0.0 | -3 | 0 | - |
| it_coop | 144 | 129 | 129 | 0 | 0.0 | -15 | 0 | - |

- **MAE (นับช่องตามเล่ม)** = 0 หน่วยกิต (จาก 7 run) เทียบกับ 18.43 แบบเดิม
- **MAPE (นับช่องตามเล่ม)** = 0.0% เทียบกับ 14.42% แบบเดิม
- คลาดเคลื่อนมากสุด: **ait** (0 หน่วยกิต)

## 2. NL→SQL metrics (eval_result.json)

| run | n_questions | valid_sql_rate | execution_accuracy | answer_text_accuracy | avg_seconds |
|---|---|---|---|---|---|
| ait | 30 | 1.0 | 0.7333 | 0.7333 | 1.92 |
| bit_no_coop | 30 | 1.0 | 0.9 | 0.9 | 1.83 |
| bit_coop | 30 | 1.0 | 0.9 | 0.9 | 1.4 |
| dsba_no_coop | 30 | 1.0 | 1.0 | 1.0 | 1.68 |
| dsba_coop | 30 | 1.0 | 0.9667 | 0.9667 | 1.78 |
| it_no_coop | 30 | 1.0 | 0.9333 | 0.9333 | 1.66 |
| it_coop | 30 | 1.0 | 0.8333 | 0.8333 | 1.36 |

### บั๊ก "SQL ถูกแต่ข้อความคำตอบผิด" (execution_accuracy สูงแต่ answer_text_accuracy ต่ำกว่า)

ไม่พบในรอบนี้ (execution_accuracy กับ answer_text_accuracy ตรงกันทุกข้อ)

### คำตอบ + อ้างอิงหน้า แยกตามระดับคำถาม (ch1: 1 = ค้นตรง, 2 = อ่านตาราง/รวม; none = ไม่มีในเล่ม)

หน้าอ้างอิงแนบด้วยโค้ดจากตาราง `course_page` (ไม่ใช่ LLM) · ถูก = หน้าที่อ้างมีอย่างน้อย 1 หน้าตรงกับหน้าที่ Lab 5 พบวิชา/ตารางเทอมนั้น (เทียบเลขหน้า PDF) · ข้อที่ไม่มีหน้าคาดหวัง (เช่น นับทั้งหลักสูตร) ไม่นับในอัตราอ้างอิง

หน้าที่คาด = หน้า primary ของ Lab 5 (มีทั้งรหัสและชื่อวิชา; ไม่มี primary ค่อยใช้หน้าที่แค่เอ่ยรหัส) · คำถามระดับ none ไม่นับในอัตราอ้างอิง (ไม่อ้างหน้าคือถูก)

ข้อจำกัดของตัววัดระดับ 2: หน้าที่คาดของคำถามรายเทอม = หน้าที่พบวิชาของเทอมนั้นบ่อยที่สุดในผล Lab 5 ซึ่ง IT no_coop ชี้หน้าแผนสหกิจ PDF 38 (Tesseract อ่านรหัสวิชาหน้า 31 ไม่ออก) — หน้าที่ระบบอ้าง (PDF 31) ตรวจกับหัวเทอมใน OCR ทั้งเล่มแล้วถูก จึงอัตราระดับ 2 ของ IT no_coop ต่ำกว่าจริง · DSBA coop ไม่อ้างหน้าตารางแผน (เลขไฟล์ภาพไม่ตรงเลขหน้า PDF — ยืนยันกับเล่มไม่ได้ จึงไม่อ้าง)

| run | level | n | execution_accuracy | answers with citation | citation_accuracy (checkable) |
|---|---|---|---|---|---|
| ait | 1 | 15 | 0.8667 | 11/15 | 11/13 |
| ait | 2 | 12 | 0.5 | 4/12 | 4/5 |
| ait | none | 3 | 1.0 | 0/3 | - |
| bit_no_coop | 1 | 15 | 1.0 | 13/15 | 13/13 |
| bit_no_coop | 2 | 12 | 0.75 | 5/12 | 5/5 |
| bit_no_coop | none | 3 | 1.0 | 0/3 | - |
| bit_coop | 1 | 15 | 1.0 | 13/15 | 13/13 |
| bit_coop | 2 | 12 | 0.75 | 5/12 | 5/5 |
| bit_coop | none | 3 | 1.0 | 0/3 | - |
| dsba_no_coop | 1 | 15 | 1.0 | 13/15 | 13/13 |
| dsba_no_coop | 2 | 12 | 1.0 | 5/12 | 5/5 |
| dsba_no_coop | none | 3 | 1.0 | 0/3 | - |
| dsba_coop | 1 | 12 | 1.0 | 10/12 | 10/10 |
| dsba_coop | 2 | 15 | 0.9333 | 2/15 | 2/7 |
| dsba_coop | none | 3 | 1.0 | 0/3 | - |
| it_no_coop | 1 | 15 | 0.9333 | 12/15 | 12/13 |
| it_no_coop | 2 | 12 | 0.9167 | 5/12 | 2/5 |
| it_no_coop | none | 3 | 1.0 | 0/3 | - |
| it_coop | 1 | 15 | 0.9333 | 12/15 | 12/13 |
| it_coop | 2 | 12 | 0.6667 | 5/12 | 5/5 |
| it_coop | none | 3 | 1.0 | 0/3 | - |

## 3. ความเสถียร / สัญญาณ overfitting (รันซ้ำเอกสารชุดเดียวกัน)

- **dsba_coop vs dsba_coop_retry** — ข้าม: ยังไม่มี run dsba_coop_retry
- **bit_coop vs bit_coop_retry** — ข้าม: ยังไม่มี run bit_coop_retry
- **it_coop vs it_coop_retry** — ข้าม: ยังไม่มี run it_coop_retry
- **ait vs ait_retry** — ข้าม: ยังไม่มี run ait_retry
- **ait vs ait_retry2** — ข้าม: ยังไม่มี run ait_retry2
- **ait vs ait_retry3** — ข้าม: ยังไม่มี run ait_retry3
- **bit_no_coop vs bit_no_coop_retry** — ข้าม: ยังไม่มี run bit_no_coop_retry
- **dsba_no_coop vs dsba_no_coop_retry** — ข้าม: ยังไม่มี run dsba_no_coop_retry
- **it_no_coop vs it_no_coop_retry** — ข้าม: ยังไม่มี run it_no_coop_retry

## 4. Metric ที่วิชานี้ไม่ได้ใช้ + ทำไม (checklist ch9 ข้อ 4)

### 4.1 Confusion matrix / MCC — **ใช้แล้ว** สำหรับฟิลด์ `ctype` (บังคับ/เลือก)

`ctype` เป็นงาน binary classification ตรงตามสไลด์ ch9 ส่วนที่ 1 แต่เดิมวัดด้วย exact_match_acc (กลไกเดียวกับ free text) ซึ่งไม่เผย accuracy paradox — เพิ่ม confusion matrix + per-class precision/recall/F1 + MCC แล้ว (`lab7_metrics.py::classification_report`) พบว่าโมเดลเอนเอียงทาย "บังคับ" อย่างเป็นระบบทุกหลักสูตร (precision(บังคับ)=1.000 ทุก run แต่ recall(เลือก) ต่ำมาก):

| run | ctype accuracy | recall(บังคับ) | recall(เลือก) | MCC |
|---|---|---|---|---|
| ait | 0.875 | 0.9091 | 0.7143 | 1.0 |
| bit_no_coop | 0.9767 | 0.9722 | 1.0 | 0.9223 |
| bit_coop | 0.9286 | 0.9429 | 0.8571 | 0.9121 |
| dsba_no_coop | 0.9111 | 0.8824 | 1.0 | 0.8452 |
| dsba_coop | 0.8864 | 0.8571 | 1.0 | 0.7423 |
| it_no_coop | 0.8704 | 0.8696 | 0.875 | 0.8607 |
| it_coop | 0.7925 | 0.8298 | 0.5 | 0.6814 |

ตัวเลข `exact_match_acc` เดิม (60-86%, ดูพอใช้ได้) บังตาปัญหานี้ไว้ทั้งหมด — เป็นตัวอย่าง accuracy paradox ตรงตามที่สไลด์เตือนจริง

### 4.2 MAE/MAPE — **ใช้แล้ว** สำหรับหน่วยกิตรวม (ดูหัวข้อ 1 ด้านบน)

CHK1 เดิมบอกแค่ผ่าน/ไม่ผ่าน ไม่บอกขนาดความคลาดเคลื่อน — เพิ่ม MAE/MAPE ต่อยอด แล้ว (MAE=18.43 หน่วยกิต, MAPE=14.42% ข้ามทั้ง 7 หลักสูตร) เผยว่า run ที่ "fail CHK1" เหมือนกันหมด จริง ๆ คลาดเคลื่อนต่างกันมาก (dsba_no_coop แย่สุด 33 หน่วยกิต ขณะที่บาง run คลาดเคลื่อนแค่ ~5%)

**Known limitation ของค่านี้ (ตั้งใจปล่อยไว้ ไม่ใช่บั๊ก):** ส่วนใหญ่ของความคลาดเคลื่อนมาจากแถว "วิชาเลือก" ที่ตารางแผนเขียนเป็นรหัส wildcard (เช่น `06036xxx`) แทนรหัสจริง — เอกสารต้นฉบับเองก็ไม่ได้ระบุว่านักศึกษาจะเลือกวิชาไหน จึงไม่ถูกใส่ใน `plan_item` ที่ MAE นับ (ไม่เดารหัสปลอม/ไม่แต่งข้อมูล) เคยลอง แก้โดยบวกหน่วยกิตจากตาราง catalog แยก (`elective_group.credits_required`) กลับ เข้าไปแล้ว แต่พบว่า **จะทำให้ตัวเลขเฟ้อผิดทิศทางแทน**: ค่า `credits_required` ถูกก็อปปี้ซ้ำทุกกลุ่มย่อยในเมนู (เช่น BIT-coop 1 ช่อง 6 หน่วยกิต แต่มี 4 กลุ่มย่อย → รวมผิดเป็น 24) และ catalog กับตำแหน่งจริงในแผนก็ไม่ได้ผูกกันแบบ 1:1 (เช็คแล้ว BIT-coop มีแถว wildcard จริง 7 แถวในแผน แต่ catalog นิยามไว้แค่ 1 slot) บางแถว ยังเป็น "เลือกเสรี" ที่ไม่มีเมนูจำกัดในเอกสารเลยด้วยซ้ำ (เลือกวิชาอะไรก็ได้ทั้งมหาวิทยาลัย) — สรุปว่าค่า MAE/MAPE ที่รายงานนี้เป็น **upper bound ที่ถูกต้อง** (หน่วยกิตที่หายจริง) ไม่ใช่ตัวชี้วัดคุณภาพการสกัดที่แย่

### 4.3 Metric ที่ตัดสินใจ **ไม่ใช้** + เหตุผล

- **MSE/RMSE/MAPE/Huber สำหรับฟิลด์อื่นนอกจากหน่วยกิตรวม** — ไม่มีงาน regression/depth-estimation อื่นในโปรเจกต์นี้ ฟิลด์ที่เหลือเป็น categorical หรือ free text ทั้งหมด วัดด้วย CER/WER/exact_match (ฟิลด์อิสระ) หรือ confusion matrix (ฟิลด์ categorical) แทน
- **LLM-as-a-judge / Cohen kappa** — คำถาม NL→SQL ของโปรเจกต์นี้เป็น closed-form (มีคำตอบถูกหนึ่งเดียว ตรวจด้วยกฎ/SQL result ได้ตรง ๆ) ไม่ใช่งานปลายเปิดที่ต้องให้ LLM ช่วยตัดสินความ "ดี" แบบอัตนัย จึงไม่จำเป็นต้องใช้
- **Citation coverage / accuracy — ใช้แล้ว (อัปเดต 2026-09-26)** — เดิมตัดสินใจไม่ใช้เพราะคำตอบมาจาก SQL ไม่ใช่ RAG; ตอนนี้คำตอบแนบหน้าอ้างอิงในเล่ม (ch1 ส่วน Q&A ต้องอ้างอิงหน้า) จึงวัดทั้ง "คำตอบที่มีอ้างอิง" (coverage) และ "อ้างหน้าถูก" (accuracy) แยกตามระดับคำถาม — ดูตารางในหัวข้อ 2
- **Faithfulness/Groundedness** — รับประกันโดยสถาปัตยกรรมเดียวกับข้อบน: คำตอบมาจาก SQL execution ต่อฐานข้อมูลจริงเสมอ ไม่มีช่องให้โมเดล "แต่งเรื่อง" หลุดจากข้อมูลได้
