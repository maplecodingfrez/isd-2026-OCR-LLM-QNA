# Lab9_evaluation

โฟลเดอร์นี้เป็นงานส่งของ **Lab9** (บทที่ 9: Evaluation and Overfitting, `06026240`)
แยกออกมาจาก `../Lab8b_ocr_system` โดยตั้งใจ — โค้ดในนี้ **อ่านผลลัพธ์ที่ Lab 8B รันไว้แล้วเท่านั้น**
ไม่แก้ไข ไม่รันโมเดลใหม่ ไม่ยุ่งกับซอร์สของ Lab 8B เลย

## ทำไมต้องมีโฟลเดอร์นี้

สไลด์บทที่ 9 (`ISD/Learning Slides/ch9_EvaluationAndOverfitting.pdf`) สรุปว่าจบบทนี้ต้องทำ 5 อย่างได้
— **ตอนนี้ตอบครบทั้ง 5 ข้อแล้ว** (สถานะเดิมของไฟล์นี้เคยเขียนไว้ว่าข้อ 4 ยังไม่ได้ทำ ตอนนี้ทำแล้ว):

1. เลือก metric ให้ตรงกับชนิดของงาน และอธิบายได้ว่าทำไมไม่ใช้ตัวอื่น
2. อ่านค่า metric ออกว่าค่าสูง/ต่ำแปลว่าอะไรในบริบทงานตัวเอง
3. ตรวจได้ว่าโมเดล/ระบบกำลัง overfit อยู่หรือเปล่า และถ้าใช่จะแก้ด้วยวิธีไหน
4. **รู้จัก metric ที่วิชานี้ไม่ได้ใช้** — ตอบครบแล้ว ดูหัวข้อ "## 4." ที่ `evaluate_lab9.py`
   สร้างในรายงานทุกครั้งที่รัน (สรุปย่อ: เพิ่ม confusion matrix/MCC ให้ฟิลด์ `ctype` เพราะเป็นงาน
   classification จริง, เพิ่ม MAE/MAPE ให้หน่วยกิตรวมเพราะเป็นค่าต่อเนื่อง, ส่วน MSE/RMSE/Huber
   อื่น ๆ / LLM-as-a-judge / citation coverage ตัดสินใจไม่ใช้เพราะไม่มีงานที่ตรงเงื่อนไข)
5. **รันสคริปต์ประเมินผลกับงานโปรเจคของตัวเอง แล้วเอาตัวเลขไปใส่รายงานได้**

`evaluate_lab9.py` คือสคริปต์ของข้อ 5 — คำนวณ metric ที่เข้ากับงานสาย NL→SQL / structured
output ของ Lab 8B และเช็คสัญญาณ "ไม่เสถียร" (ตัวแทน overfitting สำหรับงานที่ไม่ได้เทรนโมเดลเอง)

## ครบทุกเล่มหลักสูตรแล้ว (AIT/BIT/DSBA/IT)

**อัปเดต (เดิมส่วนนี้เคยเขียนว่า "รันจริงแค่ DSBA-coop เล่มเดียว" — ตอนนี้ครบทั้ง 7 run แล้ว):**
pipeline Lab7B→Lab8B รันจบครบทุกเล่ม/ทุกแผนตามขอบเขตที่อาจารย์ขอ ("ประเมินครบทุกเล่มหลักสูตร") —
AIT (แผนเดียว), BIT coop/no-coop, DSBA coop/no-coop, IT coop/no-coop รวม 7 run จริง +
`dsba_coop_retry` อีก 1 run (รันซ้ำเอกสารชุดเดียวกับ `dsba_coop` ไว้เช็คความเสถียรโดยเฉพาะ)

โฟลเดอร์ `gold_questions/` มี `gold_questions.json` ของทั้ง 7 run แล้ว (คำนวณจาก ground truth
อัตโนมัติ ไม่ใช่เดามือ — ดู `gold_questions/build_gold_questions.py`) และ
`ground_truth_scoped/*.json` (กรอง `year >= 1` จาก `data/ground_truth/*.json` เต็มชุด) ที่ใช้เทียบ
P/R/F1/CER/WER ของ Lab7B ก็มีครบทั้ง 7 ไฟล์เช่นกัน — รายละเอียดวิธีสร้างและ caveat ของแต่ละไฟล์
อยู่ใน `Lab8b_ocr_system/PROGRESS.md`

## วิธีรัน

```bash
cd Lab9_evaluation
python evaluate_lab9.py
```

ค่า default อ่านครบทั้ง 8 run ที่มีอยู่แล้วใน `../Lab8b_ocr_system/runs/<CURRICULUM>/<plan>/`:

| run name | โฟลเดอร์ | ใช้ทำอะไร |
|---|---|---|
| `ait` | `runs/AIT/lab8b_output` | หลักสูตร AIT (แผนเดียว ไม่แยกสหกิจ) |
| `bit_no_coop` / `bit_coop` | `runs/BIT/no_coop\|coop/lab8b_output` | หลักสูตร BIT ทั้งสองแผน |
| `dsba_no_coop` / `dsba_coop` | `runs/DSBA/no_coop\|coop/lab8b_output` | หลักสูตร DSBA ทั้งสองแผน |
| `it_no_coop` / `it_coop` | `runs/IT/no_coop\|coop/lab8b_output` | หลักสูตร IT ทั้งสองแผน |
| `dsba_coop_retry` | `archive/lab8b_run_ours_coop_retry` | รันซ้ำเอกสารชุดเดียวกับ `dsba_coop` — ใช้เทียบความเสถียร (checklist ข้อ 3) เท่านั้น |

จะระบุ run เองก็ได้ เช่น

```bash
python evaluate_lab9.py --runs my_run=path/to/run_dir
```

## ผลลัพธ์

- พิมพ์ตาราง Markdown ออกหน้าจอ (copy ไปแปะในรายงานได้เลย)
- บันทึกไว้ที่ `reports/lab9_metrics_latest.md` และ `reports/lab9_metrics_latest.json`
- รายงานแยกอีกฉบับ `reports/lab7b_prf1_cerwer_2026-09-16.md` — วัดคุณภาพขั้น **สกัดข้อมูลดิบของ
  Lab7B** (P/R/F1/CER/WER เทียบ ground truth คนละสคริปต์กับ `evaluate_lab9.py`, ดูหัวข้อถัดไป)

## Metric ที่ใช้ และแม็ปกับสไลด์บทที่ 9

| ส่วน | metric | มาจากไฟล์ | ตรงกับสไลด์หัวข้อ |
|---|---|---|---|
| แปลง Markdown→JSON | `conversion_rate`, `skipped_rate` | `curriculum.conversion.json` | "วัดคุณภาพผลลัพธ์ที่มีโครงสร้าง" (Schema pass rate / Field-level recall) |
| ความถูกต้องเชิงเนื้อหา | `verify_pass_rate` (CHK1-CHK7) | `verify.json` | ใช้แทน "domain-specific correctness check" |
| หน่วยกิตรวม (ค่าต่อเนื่อง) | `credits_abs_error` (MAE), `credits_pct_error` (MAPE) | `curriculum.json` (`plan_total_credits` vs `declared_total_credits`) | "งานทำนายค่าต่อเนื่อง" — CHK1 บอกแค่ผ่าน/ไม่ผ่าน ตัวนี้บอกขนาดคลาดเคลื่อน |
| ตอบคำถามด้วย NL→SQL | `valid_sql_rate`, `execution_accuracy` | `eval_result.json` | "วัดคำตอบสุดท้ายและความซื่อสัตย์ต่อแหล่งข้อมูล" (Execution Accuracy (SQL)) |
| ข้อความคำตอบจริง | `answer_text_accuracy` | `eval_result.json` (field `answer`) | Exact Match — **ตัวนี้ไม่เหมือน execution_accuracy** เพราะเช็คข้อความที่โมเดลพิมพ์จริง ไม่ใช่แค่แถว SQL |
| ฟิลด์ categorical (`ctype`) | confusion matrix, precision/recall/F1 ต่อ class, MCC | `Lab8b_ocr_system/.../lab7b_output/evaluation.json` (`alignment.classification.ctype`) | "งานจำแนก" — เผย accuracy paradox ที่ exact_match_acc มองไม่เห็น |
| ความเสถียร | เทียบ `dsba_coop` vs `dsba_coop_retry` | ทุกไฟล์ข้างบน | "สัญญาณที่บอกว่ากำลัง overfit — ผลแกว่งมากเมื่อรันซ้ำ" |

### ทำไมต้องมี `answer_text_accuracy` แยกจาก `execution_accuracy`

เกณฑ์ให้คะแนนเดิมของ Lab 8B (`score_one` ใน `lab8b_curriculum_db.py`) เทียบแค่ **แถวผลลัพธ์ SQL**
กับเฉลย ไม่ได้เทียบ **ข้อความคำตอบ** ที่โมเดลพิมพ์ออกมาจริง ๆ — ตรงกับที่สไลด์เตือนไว้ว่า
เกณฑ์อัตโนมัติแบบนี้ "ให้คะแนนผ่านเพราะเทียบแค่แถวผลลัพธ์ SQL ไม่ได้เทียบข้อความ"

สคริปต์นี้เพิ่มการเช็คข้อความคำตอบแยกต่างหาก ผลคือเจอบั๊กที่เกณฑ์เดิมมองไม่เห็น เช่น
ใน `dsba_coop_retry` มีคำตอบพิมพ์รหัสวิชาเพี้ยน (`0:06066102` แทนที่จะเป็น `06066102`)
และมีคำตอบที่ echo คำถามกลับมาแทนการตอบจริง — ทั้งที่ `correct` (SQL) เป็น `true` ทุกข้อ

### ทำไมต้องมี confusion matrix/MCC แยกจาก exact_match_acc (ฟิลด์ `ctype`)

`ctype` (บังคับ/เลือก) เป็นงาน binary classification ตรงตามสไลด์ ch9 ส่วนที่ 1 แต่เดิมวัดด้วย
`exact_match_acc` (กลไกเดียวกับ free text อย่าง `name_th`) ซึ่งไม่เผย accuracy paradox — พอเพิ่ม
confusion matrix + per-class precision/recall/F1 + MCC (`lab7_metrics.py::classification_report`)
พบว่าโมเดลเอนเอียงทาย "บังคับ" อย่างเป็นระบบทุกหลักสูตร (`precision(บังคับ)=1.000` ทุก run แต่
`recall(เลือก)` ต่ำมาก บางหลักสูตรเหลือ 0%) — ตัวเลข `exact_match_acc` เดิม (60-86%, ดูพอใช้ได้)
บังตาปัญหานี้ไว้ทั้งหมด

### หน่วยกิตรวม (MAE/MAPE) — known limitation ที่ต้องอ่านก่อนเชื่อตัวเลข

ส่วนใหญ่ของความคลาดเคลื่อนมาจากแถว "วิชาเลือก" ที่ตารางแผนเขียนเป็นรหัส wildcard (เช่น
`06036xxx`) แทนรหัสจริง — เอกสารต้นฉบับเองก็ไม่ได้ระบุว่านักศึกษาจะเลือกวิชาไหน จึงไม่ถูกใส่ใน
`plan_item` ที่ MAE นับ เคยลองแก้โดยบวกหน่วยกิตจาก `elective_group.credits_required` กลับเข้าไป
แต่พบว่าจะทำให้ตัวเลขเฟ้อผิดทิศทางแทน (ค่าถูกก็อปปี้ซ้ำทุกกลุ่มย่อยในเมนู + catalog กับตำแหน่งจริง
ในแผนไม่ผูกกัน 1:1) — สรุปว่า MAE/MAPE ที่รายงานนี้เป็น **upper bound ที่ถูกต้อง** ไม่ใช่ตัวชี้วัด
คุณภาพการสกัดที่แย่ รายละเอียดเต็มอยู่ใน `Lab8b_ocr_system/PROGRESS.md`

## ความเสถียร / overfitting

ระบบนี้ใช้ LLM สำเร็จรูป + prompt ไม่ได้เทรนโมเดลเอง จึงไม่มี train/val loss ให้ดูตรง ๆ
สัญญาณที่ใช้แทนตามสไลด์คือ **"ผลแกว่งมากเมื่อรันซ้ำด้วย seed/รอบต่างกัน"** — สคริปต์เทียบ
`dsba_coop` กับ `dsba_coop_retry` (เอกสารชุดเดียวกัน รันคนละรอบ) แล้ว flag
ว่า "ไม่เสถียร" ถ้าตัวเลขต่างกันเกิน 10%

**ห้าม** เอา run อื่น (เช่น `ait`, `bit_coop`) มาเทียบความเสถียรกับ `dsba_coop` เพราะเป็นเอกสาร
คนละชุด ตัวเลขต่างกันเป็นเรื่องปกติอยู่แล้ว ไม่เกี่ยวกับความเสถียรของโมเดล — เทียบได้แค่คู่ที่อยู่ใน
`STABILITY_GROUP` เท่านั้น
