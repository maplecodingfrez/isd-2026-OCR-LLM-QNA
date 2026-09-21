# Lab9 evaluation report — 2026-09-22 06:51

อ้างอิงเนื้อหา: `ISD/Learning Slides/ch9_EvaluationAndOverfitting.pdf`
ข้อมูลดิบมาจาก: `Lab8b_ocr_system/runs/<CURRICULUM>/<plan>/lab8b_output/` (สคริปต์นี้แค่คำนวณ ไม่ได้รันโมเดลใหม่)

## 1. Structured-output metrics (Markdown → JSON → curriculum.db)

| run | conversion_rate | skipped_rate | plan_total_credits | declared_total_credits | credits_abs_error | credits_pct_error | verify_pass_rate | failed checks |
|---|---|---|---|---|---|---|---|---|
| ait | 0.8649 | 0.1351 | 98 | 120 | 22 | 18.33 | 0.7143 | CHK1, CHK7 |
| bit_no_coop | 0.8571 | 0.1667 | 105 | 126 | 21 | 16.67 | 0.8571 | CHK1 |
| bit_coop | 0.8182 | 0.1364 | 111 | 126 | 15 | 11.9 | 0.7143 | CHK1, CHK7 |
| dsba_no_coop | 0.6471 | 0.3529 | 96 | 132 | 36 | 27.27 | 0.7143 | CHK1, CHK7 |
| dsba_coop | 0.8065 | 0.4355 | 111 | 132 | 21 | 15.91 | 0.7143 | CHK1, CHK7 |
| it_no_coop | 0.8039 | 0.1569 | 120 | 129 | 9 | 6.98 | 0.7143 | CHK1, CHK7 |
| it_coop | 0.8627 | 0.1569 | 135 | 129 | 6 | 4.65 | 0.7143 | CHK1, CHK7 |
| dsba_coop_retry | 0.7463 | 0.4776 | 111 | 132 | 21 | 15.91 | 0.7143 | CHK1, CHK7 |
| bit_coop_retry | 0.8372 | 0.1163 | 111 | 126 | 15 | 11.9 | 0.7143 | CHK1, CHK7 |
| it_coop_retry | 0.7719 | 0.1228 | 135 | 129 | 6 | 4.65 | 0.7143 | CHK1, CHK7 |
| ait_retry | 0.8421 | 0.1579 | 98 | 120 | 22 | 18.33 | 0.7143 | CHK1, CHK7 |
| ait_retry2 | 0.8649 | 0.1351 | 98 | 120 | 22 | 18.33 | 0.7143 | CHK1, CHK7 |
| ait_retry3 | 0.8421 | 0.1579 | 98 | 120 | 22 | 18.33 | 0.7143 | CHK1, CHK7 |
| bit_no_coop_retry | 0.8372 | 0.1628 | 105 | 126 | 21 | 16.67 | 0.8571 | CHK1 |
| dsba_no_coop_retry | 0.6538 | 0.3462 | 99 | 132 | 33 | 25.0 | 0.7143 | CHK1, CHK7 |
| it_no_coop_retry | 0.8113 | 0.1509 | 126 | 129 | 3 | 2.33 | 0.7143 | CHK1, CHK7 |

### หน่วยกิตรวม — MAE/MAPE ข้ามหลักสูตร (สไลด์ ch9 ส่วนที่ 2 "งานทำนายค่าต่อเนื่อง")

CHK1 ข้างบนบอกแค่ผ่าน/ไม่ผ่าน (`total == declared` เป๊ะ) ไม่บอกว่าคลาดเคลื่อนไปแค่ไหน — MAE/MAPE ตรงนี้วัดขนาดความคลาดเคลื่อนแทน (ยิ่งต่ำยิ่งดี ตามสไลด์)

- **MAE** = 18.44 หน่วยกิต (เฉลี่ยจาก 16 run ที่มีข้อมูลครบ)
- **MAPE** = 14.57%
- คลาดเคลื่อนมากสุด: **dsba_no_coop** (36 หน่วยกิต)

## 2. NL→SQL metrics (eval_result.json)

| run | n_questions | valid_sql_rate | execution_accuracy | answer_text_accuracy | avg_seconds |
|---|---|---|---|---|---|
| ait | 30 | 0.9667 | 0.7 | 0.7 | 2.46 |
| bit_no_coop | 30 | 0.9667 | 0.8667 | 0.8667 | 2.63 |
| bit_coop | 30 | 0.9667 | 0.8667 | 0.8667 | 3.2 |
| dsba_no_coop | 30 | 0.9667 | 0.8667 | 0.8667 | 2.48 |
| dsba_coop | 30 | 0.9667 | 0.9333 | 0.9333 | 2.57 |
| it_no_coop | 30 | 0.9667 | 0.7667 | 0.7667 | 2.45 |
| it_coop | 30 | 0.9667 | 0.7667 | 0.7667 | 2.1 |
| dsba_coop_retry | 30 | 0.9667 | 0.8667 | 0.8667 | 3.08 |
| bit_coop_retry | 30 | 0.9667 | 0.8333 | 0.8333 | 3.11 |
| it_coop_retry | 30 | 0.9667 | 0.7333 | 0.7333 | 2.99 |
| ait_retry | 30 | 0.9667 | 0.7 | 0.7 | 2.85 |
| ait_retry2 | 30 | 0.9667 | 0.7 | 0.7 | 2.96 |
| ait_retry3 | 30 | 0.9667 | 0.7 | 0.7 | 2.96 |
| bit_no_coop_retry | 30 | 0.9667 | 0.8333 | 0.8333 | 3.04 |
| dsba_no_coop_retry | 30 | 0.9667 | 0.9333 | 0.9 | 3.02 |
| it_no_coop_retry | 30 | 0.9667 | 0.8 | 0.8 | 2.93 |

### บั๊ก "SQL ถูกแต่ข้อความคำตอบผิด" (execution_accuracy สูงแต่ answer_text_accuracy ต่ำกว่า)

- **dsba_no_coop_retry**: 1 ข้อ
  - มีรายวิชากี่วิชาที่มีหน่วยกิตเท่ากับ 3

## 3. ความเสถียร / สัญญาณ overfitting (รันซ้ำเอกสารชุดเดียวกัน)

- **dsba_coop vs dsba_coop_retry**
  - หน่วยกิตรวมในแผน: dsba_coop=111  vs  dsba_coop_retry=111  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: dsba_coop=50  vs  dsba_coop_retry=50  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): dsba_coop=0.9333  vs  dsba_coop_retry=0.8667  (ต่างกัน 7.1%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: dsba_coop=0.9333  vs  dsba_coop_retry=0.8667  (ต่างกัน 7.1%) -> โอเค
- **bit_coop vs bit_coop_retry**
  - หน่วยกิตรวมในแผน: bit_coop=111  vs  bit_coop_retry=111  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: bit_coop=36  vs  bit_coop_retry=36  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): bit_coop=0.8667  vs  bit_coop_retry=0.8333  (ต่างกัน 3.9%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: bit_coop=0.8667  vs  bit_coop_retry=0.8333  (ต่างกัน 3.9%) -> โอเค
- **it_coop vs it_coop_retry**
  - หน่วยกิตรวมในแผน: it_coop=135  vs  it_coop_retry=135  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: it_coop=44  vs  it_coop_retry=44  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): it_coop=0.7667  vs  it_coop_retry=0.7333  (ต่างกัน 4.4%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: it_coop=0.7667  vs  it_coop_retry=0.7333  (ต่างกัน 4.4%) -> โอเค
- **ait vs ait_retry**
  - หน่วยกิตรวมในแผน: ait=98  vs  ait_retry=98  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: ait=32  vs  ait_retry=32  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): ait=0.7  vs  ait_retry=0.7  (ต่างกัน 0.0%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: ait=0.7  vs  ait_retry=0.7  (ต่างกัน 0.0%) -> โอเค
- **ait vs ait_retry2**
  - หน่วยกิตรวมในแผน: ait=98  vs  ait_retry2=98  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: ait=32  vs  ait_retry2=32  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): ait=0.7  vs  ait_retry2=0.7  (ต่างกัน 0.0%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: ait=0.7  vs  ait_retry2=0.7  (ต่างกัน 0.0%) -> โอเค
- **ait vs ait_retry3**
  - หน่วยกิตรวมในแผน: ait=98  vs  ait_retry3=98  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: ait=32  vs  ait_retry3=32  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): ait=0.7  vs  ait_retry3=0.7  (ต่างกัน 0.0%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: ait=0.7  vs  ait_retry3=0.7  (ต่างกัน 0.0%) -> โอเค
- **bit_no_coop vs bit_no_coop_retry**
  - หน่วยกิตรวมในแผน: bit_no_coop=105  vs  bit_no_coop_retry=105  (ต่างกัน 0.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: bit_no_coop=36  vs  bit_no_coop_retry=36  (ต่างกัน 0.0%) -> โอเค
  - Execution accuracy (SQL): bit_no_coop=0.8667  vs  bit_no_coop_retry=0.8333  (ต่างกัน 3.9%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: bit_no_coop=0.8667  vs  bit_no_coop_retry=0.8333  (ต่างกัน 3.9%) -> โอเค
- **dsba_no_coop vs dsba_no_coop_retry**
  - หน่วยกิตรวมในแผน: dsba_no_coop=96  vs  dsba_no_coop_retry=99  (ต่างกัน 3.0%) -> โอเค
  - จำนวนวิชาที่แปลงได้: dsba_no_coop=33  vs  dsba_no_coop_retry=34  (ต่างกัน 2.9%) -> โอเค
  - Execution accuracy (SQL): dsba_no_coop=0.8667  vs  dsba_no_coop_retry=0.9333  (ต่างกัน 7.1%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: dsba_no_coop=0.8667  vs  dsba_no_coop_retry=0.9  (ต่างกัน 3.7%) -> โอเค
- **it_no_coop vs it_no_coop_retry**
  - หน่วยกิตรวมในแผน: it_no_coop=120  vs  it_no_coop_retry=126  (ต่างกัน 4.8%) -> โอเค
  - จำนวนวิชาที่แปลงได้: it_no_coop=41  vs  it_no_coop_retry=43  (ต่างกัน 4.7%) -> โอเค
  - Execution accuracy (SQL): it_no_coop=0.7667  vs  it_no_coop_retry=0.8  (ต่างกัน 4.2%) -> โอเค
  - ความถูกต้องของข้อความคำตอบ: it_no_coop=0.7667  vs  it_no_coop_retry=0.8  (ต่างกัน 4.2%) -> โอเค

## 4. Metric ที่วิชานี้ไม่ได้ใช้ + ทำไม (checklist ch9 ข้อ 4)

### 4.1 Confusion matrix / MCC — **ใช้แล้ว** สำหรับฟิลด์ `ctype` (บังคับ/เลือก)

`ctype` เป็นงาน binary classification ตรงตามสไลด์ ch9 ส่วนที่ 1 แต่เดิมวัดด้วย exact_match_acc (กลไกเดียวกับ free text) ซึ่งไม่เผย accuracy paradox — เพิ่ม confusion matrix + per-class precision/recall/F1 + MCC แล้ว (`lab7_metrics.py::classification_report`) พบว่าโมเดลเอนเอียงทาย "บังคับ" อย่างเป็นระบบทุกหลักสูตร (precision(บังคับ)=1.000 ทุก run แต่ recall(เลือก) ต่ำมาก):

| run | ctype accuracy | recall(บังคับ) | recall(เลือก) | MCC |
|---|---|---|---|---|
| ait | 0.875 | 0.9091 | 0.7143 | 1.0 |
| bit_no_coop | 0.9302 | 0.9167 | 1.0 | 0.9216 |
| bit_coop | 0.9286 | 0.9429 | 0.8571 | 0.9121 |
| dsba_no_coop | 0.9111 | 0.8824 | 1.0 | 0.8452 |
| dsba_coop | 0.8864 | 0.8571 | 1.0 | 0.7423 |
| it_no_coop | 0.8148 | 0.8043 | 0.875 | 0.859 |
| it_coop | 0.7547 | 0.7872 | 0.5 | 0.8546 |
| dsba_coop_retry | 0.8182 | 0.7714 | 1.0 | 0.6391 |
| bit_coop_retry | 0.881 | 0.9429 | 0.5714 | 0.8812 |
| it_coop_retry | 0.8868 | 0.8936 | 0.8333 | 1.0 |
| ait_retry | 0.875 | 0.9091 | 0.7143 | 1.0 |
| ait_retry2 | 0.875 | 0.9091 | 0.7143 | 1.0 |
| ait_retry3 | 0.9 | 0.9091 | 0.8571 | 1.0 |
| bit_no_coop_retry | 0.9767 | 0.9722 | 1.0 | 0.9223 |
| dsba_no_coop_retry | 0.9333 | 0.9118 | 1.0 | 0.8464 |
| it_no_coop_retry | 0.9074 | 0.913 | 0.875 | 0.9245 |

ตัวเลข `exact_match_acc` เดิม (60-86%, ดูพอใช้ได้) บังตาปัญหานี้ไว้ทั้งหมด — เป็นตัวอย่าง accuracy paradox ตรงตามที่สไลด์เตือนจริง

### 4.2 MAE/MAPE — **ใช้แล้ว** สำหรับหน่วยกิตรวม (ดูหัวข้อ 1 ด้านบน)

CHK1 เดิมบอกแค่ผ่าน/ไม่ผ่าน ไม่บอกขนาดความคลาดเคลื่อน — เพิ่ม MAE/MAPE ต่อยอด แล้ว (MAE=18.44 หน่วยกิต, MAPE=14.57% ข้ามทั้ง 7 หลักสูตร) เผยว่า run ที่ "fail CHK1" เหมือนกันหมด จริง ๆ คลาดเคลื่อนต่างกันมาก (dsba_no_coop แย่สุด 36 หน่วยกิต ขณะที่บาง run คลาดเคลื่อนแค่ ~5%)

**Known limitation ของค่านี้ (ตั้งใจปล่อยไว้ ไม่ใช่บั๊ก):** ส่วนใหญ่ของความคลาดเคลื่อนมาจากแถว "วิชาเลือก" ที่ตารางแผนเขียนเป็นรหัส wildcard (เช่น `06036xxx`) แทนรหัสจริง — เอกสารต้นฉบับเองก็ไม่ได้ระบุว่านักศึกษาจะเลือกวิชาไหน จึงไม่ถูกใส่ใน `plan_item` ที่ MAE นับ (ไม่เดารหัสปลอม/ไม่แต่งข้อมูล) เคยลอง แก้โดยบวกหน่วยกิตจากตาราง catalog แยก (`elective_group.credits_required`) กลับ เข้าไปแล้ว แต่พบว่า **จะทำให้ตัวเลขเฟ้อผิดทิศทางแทน**: ค่า `credits_required` ถูกก็อปปี้ซ้ำทุกกลุ่มย่อยในเมนู (เช่น BIT-coop 1 ช่อง 6 หน่วยกิต แต่มี 4 กลุ่มย่อย → รวมผิดเป็น 24) และ catalog กับตำแหน่งจริงในแผนก็ไม่ได้ผูกกันแบบ 1:1 (เช็คแล้ว BIT-coop มีแถว wildcard จริง 7 แถวในแผน แต่ catalog นิยามไว้แค่ 1 slot) บางแถว ยังเป็น "เลือกเสรี" ที่ไม่มีเมนูจำกัดในเอกสารเลยด้วยซ้ำ (เลือกวิชาอะไรก็ได้ทั้งมหาวิทยาลัย) — สรุปว่าค่า MAE/MAPE ที่รายงานนี้เป็น **upper bound ที่ถูกต้อง** (หน่วยกิตที่หายจริง) ไม่ใช่ตัวชี้วัดคุณภาพการสกัดที่แย่

### 4.3 Metric ที่ตัดสินใจ **ไม่ใช้** + เหตุผล

- **MSE/RMSE/MAPE/Huber สำหรับฟิลด์อื่นนอกจากหน่วยกิตรวม** — ไม่มีงาน regression/depth-estimation อื่นในโปรเจกต์นี้ ฟิลด์ที่เหลือเป็น categorical หรือ free text ทั้งหมด วัดด้วย CER/WER/exact_match (ฟิลด์อิสระ) หรือ confusion matrix (ฟิลด์ categorical) แทน
- **LLM-as-a-judge / Cohen kappa** — คำถาม NL→SQL ของโปรเจกต์นี้เป็น closed-form (มีคำตอบถูกหนึ่งเดียว ตรวจด้วยกฎ/SQL result ได้ตรง ๆ) ไม่ใช่งานปลายเปิดที่ต้องให้ LLM ช่วยตัดสินความ "ดี" แบบอัตนัย จึงไม่จำเป็นต้องใช้
- **Citation coverage** — คำตอบมาจาก SQL ที่รันจริงกับ DB ที่สกัดมา ไม่ใช่การ generate ข้อความอิสระแบบ RAG ที่ต้องอ้างอิงหน้า/แหล่งที่มา จึงไม่มีขั้นตอน "citation" ให้วัดตั้งแต่ต้น
- **Faithfulness/Groundedness** — รับประกันโดยสถาปัตยกรรมเดียวกับข้อบน: คำตอบมาจาก SQL execution ต่อฐานข้อมูลจริงเสมอ ไม่มีช่องให้โมเดล "แต่งเรื่อง" หลุดจากข้อมูลได้
