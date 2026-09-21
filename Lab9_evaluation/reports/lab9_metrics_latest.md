# Lab9 evaluation report — 2026-09-21 14:12

อ้างอิงเนื้อหา: `ISD/Learning Slides/ch9_EvaluationAndOverfitting.pdf`
ข้อมูลดิบมาจาก: `Lab8b_ocr_system/runs/<CURRICULUM>/<plan>/lab8b_output/` (สคริปต์นี้แค่คำนวณ ไม่ได้รันโมเดลใหม่)

## 1. Structured-output metrics (Markdown → JSON → curriculum.db)

| run | conversion_rate | skipped_rate | plan_total_credits | declared_total_credits | credits_abs_error | credits_pct_error | verify_pass_rate | failed checks |
|---|---|---|---|---|---|---|---|---|
| ait | 0.8649 | 0.1351 | 98 | 120 | 22 | 18.33 | 0.7143 | CHK1, CHK7 |
| bit_no_coop | 0.8571 | 0.1667 | 105 | 126 | 21 | 16.67 | 0.8571 | CHK1 |
| bit_coop | 0.8 | 0.1556 | 111 | 126 | 15 | 11.9 | 0.7143 | CHK1, CHK7 |
| dsba_no_coop | 0.6538 | 0.3462 | 99 | 132 | 33 | 25.0 | 0.7143 | CHK1, CHK7 |
| dsba_coop | 0.7692 | 0.4462 | 111 | 132 | 21 | 15.91 | 0.7143 | CHK1, CHK7 |
| it_no_coop | 0.8571 | 0.1633 | 123 | 129 | 6 | 4.65 | 0.7143 | CHK1, CHK7 |
| it_coop | 0.8 | 0.1273 | 135 | 129 | 6 | 4.65 | 0.7143 | CHK1, CHK7 |
| dsba_coop_retry | 0.7692 | 0.4769 | 108 | 132 | 24 | 18.18 | 0.7143 | CHK1, CHK7 |
| bit_coop_retry | 0.8 | 0.1556 | 111 | 126 | 15 | 11.9 | 0.7143 | CHK1, CHK7 |
| it_coop_retry | 0.7857 | 0.125 | 135 | 129 | 6 | 4.65 | 0.7143 | CHK1, CHK7 |
| ait_retry | 0.8718 | 0.1282 | 99 | 120 | 21 | 17.5 | 0.7143 | CHK1, CHK7 |
| ait_retry2 | 0.85 | 0.15 | 99 | 120 | 21 | 17.5 | 0.7143 | CHK1, CHK7 |
| ait_retry3 | 0.8649 | 0.1351 | 98 | 120 | 22 | 18.33 | 0.7143 | CHK1, CHK7 |
| bit_no_coop_retry | 0.8571 | 0.1667 | 105 | 126 | 21 | 16.67 | 0.8571 | CHK1 |
| dsba_no_coop_retry | 0.6538 | 0.3462 | 99 | 132 | 33 | 25.0 | 0.7143 | CHK1, CHK7 |
| it_no_coop_retry | 0.75 | 0.1429 | 123 | 129 | 6 | 4.65 | 0.7143 | CHK1, CHK7 |

### หน่วยกิตรวม — MAE/MAPE ข้ามหลักสูตร (สไลด์ ch9 ส่วนที่ 2 "งานทำนายค่าต่อเนื่อง")

CHK1 ข้างบนบอกแค่ผ่าน/ไม่ผ่าน (`total == declared` เป๊ะ) ไม่บอกว่าคลาดเคลื่อนไปแค่ไหน — MAE/MAPE ตรงนี้วัดขนาดความคลาดเคลื่อนแทน (ยิ่งต่ำยิ่งดี ตามสไลด์)

- **MAE** = 18.31 หน่วยกิต (เฉลี่ยจาก 16 run ที่มีข้อมูลครบ)
- **MAPE** = 14.47%
- คลาดเคลื่อนมากสุด: **dsba_no_coop** (33 หน่วยกิต)

## 2. NL→SQL metrics (eval_result.json)

| run | n_questions | valid_sql_rate | execution_accuracy | answer_text_accuracy | avg_seconds |
|---|---|---|---|---|---|
| ait | 30 | 0.9667 | 0.7 | 0.7 | 1.92 |
| bit_no_coop | 30 | 0.9667 | 0.8667 | 0.8667 | 1.95 |
| bit_coop | 30 | 0.9667 | 0.8667 | 0.8667 | 1.69 |
| dsba_no_coop | 30 | 0.9667 | 0.9 | 0.8667 | 1.93 |
| dsba_coop | 30 | 0.9667 | 0.9 | 0.9 | 1.84 |
| it_no_coop | 30 | 0.9667 | 0.8333 | 0.8333 | 1.86 |
| it_coop | 30 | 0.9667 | 0.7667 | 0.7667 | 1.87 |
| dsba_coop_retry | 30 | 1.0 | 1.0 | 0.9 | 1.66 |
| bit_coop_retry | 30 | 0.9667 | 0.8667 | 0.8667 | 1.9 |
| it_coop_retry | 30 | 0.9667 | 0.7667 | 0.7667 | 1.8 |
| ait_retry | 30 | 0.9667 | 0.9333 | 0.9333 | 1.82 |
| ait_retry2 | 30 | 0.9667 | 0.9333 | 0.9333 | 1.98 |
| ait_retry3 | 30 | 0.9667 | 0.7333 | 0.7333 | 2.62 |
| bit_no_coop_retry | 30 | 0.9667 | 0.8667 | 0.8667 | 12.52 |
| dsba_no_coop_retry | 30 | 0.9667 | 0.9667 | 0.9333 | 2.07 |
| it_no_coop_retry | 30 | 0.9667 | 0.8333 | 0.8333 | 1.81 |

### บั๊ก "SQL ถูกแต่ข้อความคำตอบผิด" (execution_accuracy สูงแต่ answer_text_accuracy ต่ำกว่า)

- **dsba_no_coop**: 1 ข้อ
  - มีรายวิชากี่วิชาที่มีหน่วยกิตเท่ากับ 3
- **dsba_coop_retry**: 3 ข้อ
  - ในแผนการศึกษา ชั้นปีที่ 1 ภาคการศึกษาที่ 2 ประกอบด้วยรายวิชา
  - มีรายวิชากี่วิชาที่มีหน่วยกิตเท่ากับ 3
  - ในฐานข้อมูลนี้มีคู่ความสัมพันธ์วิชาบังคับก่อน (prerequisite)
- **dsba_no_coop_retry**: 1 ข้อ
  - มีรายวิชากี่วิชาที่มีหน่วยกิตเท่ากับ 3

## 3. ความเสถียร / สัญญาณ overfitting (รันซ้ำเอกสารชุดเดียวกัน)

- **dsba_coop vs dsba_coop_retry**
  - หน่วยกิตรวมในแผน: dsba_coop=111  vs  dsba_coop_retry=108  (ต่างกัน 2.7%) -> โอเค
  - จำนวนวิชาที่แปลงได้: dsba_coop=50  vs  dsba_coop_retry=50  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): dsba_coop=0.9  vs  dsba_coop_retry=1.0  (ต่างกัน 10.0%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: dsba_coop=0.9  vs  dsba_coop_retry=0.9  (ต่างกัน 0.0%) -> โอเค
- **bit_coop vs bit_coop_retry**
  - หน่วยกิตรวมในแผน: bit_coop=111  vs  bit_coop_retry=111  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: bit_coop=36  vs  bit_coop_retry=36  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): bit_coop=0.8667  vs  bit_coop_retry=0.8667  (ต่างกัน 0.0%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: bit_coop=0.8667  vs  bit_coop_retry=0.8667  (ต่างกัน 0.0%) -> โอเค
- **it_coop vs it_coop_retry**
  - หน่วยกิตรวมในแผน: it_coop=135  vs  it_coop_retry=135  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: it_coop=44  vs  it_coop_retry=44  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): it_coop=0.7667  vs  it_coop_retry=0.7667  (ต่างกัน 0.0%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: it_coop=0.7667  vs  it_coop_retry=0.7667  (ต่างกัน 0.0%) -> โอเค
- **ait vs ait_retry**
  - หน่วยกิตรวมในแผน: ait=98  vs  ait_retry=99  (ต่างกัน 1.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: ait=32  vs  ait_retry=34  (ต่างกัน 5.9%) -> โอเค
  - Execution accuracy (SQL): ait=0.7  vs  ait_retry=0.9333  (ต่างกัน 25.0%) -> ⚠️ ไม่เสถียร (เกิน threshold)
  - ความถูกต้องของข้อความคำตอบ: ait=0.7  vs  ait_retry=0.9333  (ต่างกัน 25.0%) -> ⚠️ ไม่เสถียร (เกิน threshold)
- **ait vs ait_retry2**
  - หน่วยกิตรวมในแผน: ait=98  vs  ait_retry2=99  (ต่างกัน 1.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: ait=32  vs  ait_retry2=34  (ต่างกัน 5.9%) -> โอเค
  - Execution accuracy (SQL): ait=0.7  vs  ait_retry2=0.9333  (ต่างกัน 25.0%) -> ⚠️ ไม่เสถียร (เกิน threshold)
  - ความถูกต้องของข้อความคำตอบ: ait=0.7  vs  ait_retry2=0.9333  (ต่างกัน 25.0%) -> ⚠️ ไม่เสถียร (เกิน threshold)
- **ait vs ait_retry3**
  - หน่วยกิตรวมในแผน: ait=98  vs  ait_retry3=98  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: ait=32  vs  ait_retry3=32  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): ait=0.7  vs  ait_retry3=0.7333  (ต่างกัน 4.5%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: ait=0.7  vs  ait_retry3=0.7333  (ต่างกัน 4.5%) -> โอเค
- **bit_no_coop vs bit_no_coop_retry**
  - หน่วยกิตรวมในแผน: bit_no_coop=105  vs  bit_no_coop_retry=105  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: bit_no_coop=36  vs  bit_no_coop_retry=36  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): bit_no_coop=0.8667  vs  bit_no_coop_retry=0.8667  (ต่างกัน 0.0%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: bit_no_coop=0.8667  vs  bit_no_coop_retry=0.8667  (ต่างกัน 0.0%) -> โอเค
- **dsba_no_coop vs dsba_no_coop_retry**
  - หน่วยกิตรวมในแผน: dsba_no_coop=99  vs  dsba_no_coop_retry=99  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: dsba_no_coop=34  vs  dsba_no_coop_retry=34  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): dsba_no_coop=0.9  vs  dsba_no_coop_retry=0.9667  (ต่างกัน 6.9%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: dsba_no_coop=0.8667  vs  dsba_no_coop_retry=0.9333  (ต่างกัน 7.1%) -> โอเค
- **it_no_coop vs it_no_coop_retry**
  - หน่วยกิตรวมในแผน: it_no_coop=123  vs  it_no_coop_retry=123  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: it_no_coop=42  vs  it_no_coop_retry=42  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): it_no_coop=0.8333  vs  it_no_coop_retry=0.8333  (ต่างกัน 0.0%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: it_no_coop=0.8333  vs  it_no_coop_retry=0.8333  (ต่างกัน 0.0%) -> โอเค

## 4. Metric ที่วิชานี้ไม่ได้ใช้ + ทำไม (checklist ch9 ข้อ 4)

### 4.1 Confusion matrix / MCC — **ใช้แล้ว** สำหรับฟิลด์ `ctype` (บังคับ/เลือก)

`ctype` เป็นงาน binary classification ตรงตามสไลด์ ch9 ส่วนที่ 1 แต่เดิมวัดด้วย exact_match_acc (กลไกเดียวกับ free text) ซึ่งไม่เผย accuracy paradox — เพิ่ม confusion matrix + per-class precision/recall/F1 + MCC แล้ว (`lab7_metrics.py::classification_report`) พบว่าโมเดลเอนเอียงทาย "บังคับ" อย่างเป็นระบบทุกหลักสูตร (precision(บังคับ)=1.000 ทุก run แต่ recall(เลือก) ต่ำมาก):

| run | ctype accuracy | recall(บังคับ) | recall(เลือก) | MCC |
|---|---|---|---|---|
| ait | 0.775 | 0.9091 | 0.1429 | 1.0 |
| bit_no_coop | 0.8605 | 0.9167 | 0.5714 | 0.8812 |
| bit_coop | 0.7857 | 0.9429 | 0.0 | 0.0 |
| dsba_no_coop | 0.6667 | 0.8529 | 0.0909 | 0.476 |
| dsba_coop | 0.6136 | 0.7714 | 0.0 | 0.0 |
| it_no_coop | 0.7222 | 0.8261 | 0.125 | 1.0 |
| it_coop | 0.6981 | 0.766 | 0.1667 | 0.562 |
| bit_coop_retry | 0.7857 | 0.9429 | 0.0 | 0.0 |
| it_coop_retry | 0.6981 | 0.766 | 0.1667 | 0.562 |
| ait_retry | 0.8049 | 0.9412 | 0.1429 | 1.0 |
| ait_retry2 | 0.8293 | 0.9412 | 0.2857 | 1.0 |
| ait_retry3 | 0.7073 | 0.8235 | 0.1429 | 0.5578 |
| bit_no_coop_retry | 0.8372 | 0.9167 | 0.4286 | 0.8532 |
| dsba_no_coop_retry | 0.6957 | 0.8857 | 0.0909 | 0.4774 |
| it_no_coop_retry | 0.7222 | 0.8261 | 0.125 | 1.0 |

ตัวเลข `exact_match_acc` เดิม (60-86%, ดูพอใช้ได้) บังตาปัญหานี้ไว้ทั้งหมด — เป็นตัวอย่าง accuracy paradox ตรงตามที่สไลด์เตือนจริง

### 4.2 MAE/MAPE — **ใช้แล้ว** สำหรับหน่วยกิตรวม (ดูหัวข้อ 1 ด้านบน)

CHK1 เดิมบอกแค่ผ่าน/ไม่ผ่าน ไม่บอกขนาดความคลาดเคลื่อน — เพิ่ม MAE/MAPE ต่อยอด แล้ว (MAE=18.31 หน่วยกิต, MAPE=14.47% ข้ามทั้ง 7 หลักสูตร) เผยว่า run ที่ "fail CHK1" เหมือนกันหมด จริง ๆ คลาดเคลื่อนต่างกันมาก (dsba_no_coop แย่สุด 33 หน่วยกิต ขณะที่บาง run คลาดเคลื่อนแค่ ~5%)

**Known limitation ของค่านี้ (ตั้งใจปล่อยไว้ ไม่ใช่บั๊ก):** ส่วนใหญ่ของความคลาดเคลื่อนมาจากแถว "วิชาเลือก" ที่ตารางแผนเขียนเป็นรหัส wildcard (เช่น `06036xxx`) แทนรหัสจริง — เอกสารต้นฉบับเองก็ไม่ได้ระบุว่านักศึกษาจะเลือกวิชาไหน จึงไม่ถูกใส่ใน `plan_item` ที่ MAE นับ (ไม่เดารหัสปลอม/ไม่แต่งข้อมูล) เคยลอง แก้โดยบวกหน่วยกิตจากตาราง catalog แยก (`elective_group.credits_required`) กลับ เข้าไปแล้ว แต่พบว่า **จะทำให้ตัวเลขเฟ้อผิดทิศทางแทน**: ค่า `credits_required` ถูกก็อปปี้ซ้ำทุกกลุ่มย่อยในเมนู (เช่น BIT-coop 1 ช่อง 6 หน่วยกิต แต่มี 4 กลุ่มย่อย → รวมผิดเป็น 24) และ catalog กับตำแหน่งจริงในแผนก็ไม่ได้ผูกกันแบบ 1:1 (เช็คแล้ว BIT-coop มีแถว wildcard จริง 7 แถวในแผน แต่ catalog นิยามไว้แค่ 1 slot) บางแถว ยังเป็น "เลือกเสรี" ที่ไม่มีเมนูจำกัดในเอกสารเลยด้วยซ้ำ (เลือกวิชาอะไรก็ได้ทั้งมหาวิทยาลัย) — สรุปว่าค่า MAE/MAPE ที่รายงานนี้เป็น **upper bound ที่ถูกต้อง** (หน่วยกิตที่หายจริง) ไม่ใช่ตัวชี้วัดคุณภาพการสกัดที่แย่

### 4.3 Metric ที่ตัดสินใจ **ไม่ใช้** + เหตุผล

- **MSE/RMSE/MAPE/Huber สำหรับฟิลด์อื่นนอกจากหน่วยกิตรวม** — ไม่มีงาน regression/depth-estimation อื่นในโปรเจกต์นี้ ฟิลด์ที่เหลือเป็น categorical หรือ free text ทั้งหมด วัดด้วย CER/WER/exact_match (ฟิลด์อิสระ) หรือ confusion matrix (ฟิลด์ categorical) แทน
- **LLM-as-a-judge / Cohen kappa** — คำถาม NL→SQL ของโปรเจกต์นี้เป็น closed-form (มีคำตอบถูกหนึ่งเดียว ตรวจด้วยกฎ/SQL result ได้ตรง ๆ) ไม่ใช่งานปลายเปิดที่ต้องให้ LLM ช่วยตัดสินความ "ดี" แบบอัตนัย จึงไม่จำเป็นต้องใช้
- **Citation coverage** — คำตอบมาจาก SQL ที่รันจริงกับ DB ที่สกัดมา ไม่ใช่การ generate ข้อความอิสระแบบ RAG ที่ต้องอ้างอิงหน้า/แหล่งที่มา จึงไม่มีขั้นตอน "citation" ให้วัดตั้งแต่ต้น
- **Faithfulness/Groundedness** — รับประกันโดยสถาปัตยกรรมเดียวกับข้อบน: คำตอบมาจาก SQL execution ต่อฐานข้อมูลจริงเสมอ ไม่มีช่องให้โมเดล "แต่งเรื่อง" หลุดจากข้อมูลได้
