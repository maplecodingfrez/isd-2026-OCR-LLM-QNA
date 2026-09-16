# Lab9_evaluation

โฟลเดอร์นี้เป็นงานส่งของ **Lab9** (บทที่ 9: Evaluation and Overfitting, `06026240`)
แยกออกมาจาก `../Lab8b_ocr_system` โดยตั้งใจ — โค้ดในนี้ **อ่านผลลัพธ์ที่ Lab 8B รันไว้แล้วเท่านั้น**
ไม่แก้ไข ไม่รันโมเดลใหม่ ไม่ยุ่งกับซอร์สของ Lab 8B เลย

## ทำไมต้องมีโฟลเดอร์นี้

สไลด์บทที่ 9 (`ISD/Learning Slides/ch9_EvaluationAndOverfitting.pdf`) สรุปว่าจบบทนี้ต้องทำ 5 อย่างได้:

1. เลือก metric ให้ตรงกับชนิดของงาน และอธิบายได้ว่าทำไมไม่ใช้ตัวอื่น
2. อ่านค่า metric ออกว่าค่าสูง/ต่ำแปลว่าอะไรในบริบทงานตัวเอง
3. ตรวจได้ว่าโมเดล/ระบบกำลัง overfit อยู่หรือเปล่า และถ้าใช่จะแก้ด้วยวิธีไหน
4. รู้จัก metric ที่วิชานี้ไม่ได้ใช้
5. **รันสคริปต์ประเมินผลกับงานโปรเจคของตัวเอง แล้วเอาตัวเลขไปใส่รายงานได้**

`evaluate_lab9.py` คือสคริปต์ของข้อ 5 — คำนวณ metric ที่เข้ากับงานสาย NL→SQL / structured
output ของ Lab 8B และเช็คสัญญาณ "ไม่เสถียร" (ตัวแทน overfitting สำหรับงานที่ไม่ได้เทรนโมเดลเอง)

## ขยายให้ครบทุกเล่มหลักสูตร (AIT/BIT/DSBA/IT)

ตอนนี้ pipeline Lab7B→Lab8B รันจริงแค่ DSBA-coop เล่มเดียว ส่วนอีก 3-4 เล่ม (AIT, BIT coop/no-coop,
IT coop/no-coop, DSBA no-coop) ยังไม่ได้รัน — รายละเอียด page range ที่ต้องป้อนเข้า Lab7B (ยืนยัน
ด้วยตาแล้วทุกจุด) และแผนงานที่เหลือ ดูที่ `ISD/Learning Slides/Knowledge-based/lab9_progress.md`

โฟลเดอร์ `gold_questions/` เตรียม `gold_questions.json` ของ AIT/BIT(coop+no-coop)/IT(coop+no-coop)
ไว้ล่วงหน้าแล้ว (คำนวณจาก ground truth ที่มีอยู่ + ยืนยันชุดวิชาปี 1 ภาค 1 กับหน้าเอกสารจริงแล้ว)
พอรัน Lab7B→Lab8B เสร็จเมื่อไร เอาไฟล์ที่ตรงเล่มไปวางเป็น `gold_questions.json` ในโฟลเดอร์ run
แล้วรัน `cmd_eval` ได้เลย — รายละเอียดว่าคำตอบแต่ละกลุ่มมาจากไหนและข้อควรระวังก่อนใช้จริง อยู่ใน
docstring ของ `gold_questions/build_gold_questions.py`

## วิธีรัน

```bash
cd Lab9_evaluation
python evaluate_lab9.py
```

ค่า default จะอ่านสาม run ที่มีอยู่แล้วใน `../Lab8b_ocr_system/work/`:

| run name | โฟลเดอร์ | ใช้ทำอะไร |
|---|---|---|
| `official_input_C` | `lab8b_run` | เอกสารทางการ 4 หน้า (ใช้รายงานตัวเลข "ทางการ") |
| `ours_coop_run1` | `lab8b_run_ours_coop` | รันจริงกับเอกสารของทีมรอบแรก |
| `ours_coop_run2_retry` | `lab8b_run_ours_coop_retry` | รันซ้ำเอกสารชุดเดียวกับ run1 — ใช้เทียบความเสถียร |

จะระบุ run เองก็ได้ เช่น

```bash
python evaluate_lab9.py --runs my_run=path/to/run_dir
```

## ผลลัพธ์

- พิมพ์ตาราง Markdown ออกหน้าจอ (copy ไปแปะในรายงานได้เลย)
- บันทึกไว้ที่ `reports/lab9_metrics_latest.md` และ `reports/lab9_metrics_latest.json`

## Metric ที่ใช้ และแม็ปกับสไลด์บทที่ 9

| ส่วน | metric | มาจากไฟล์ | ตรงกับสไลด์หัวข้อ |
|---|---|---|---|
| แปลง Markdown→JSON | `conversion_rate`, `skipped_rate` | `curriculum.conversion.json` | "วัดคุณภาพผลลัพธ์ที่มีโครงสร้าง" (Schema pass rate / Field-level recall) |
| ความถูกต้องเชิงเนื้อหา | `verify_pass_rate` (CHK1-CHK7) | `verify.json` | ใช้แทน "domain-specific correctness check" |
| ตอบคำถามด้วย NL→SQL | `valid_sql_rate`, `execution_accuracy` | `eval_result.json` | "วัดคำตอบสุดท้ายและความซื่อสัตย์ต่อแหล่งข้อมูล" (Execution Accuracy (SQL)) |
| ข้อความคำตอบจริง | `answer_text_accuracy` | `eval_result.json` (field `answer`) | Exact Match — **ตัวนี้ไม่เหมือน execution_accuracy** เพราะเช็คข้อความที่โมเดลพิมพ์จริง ไม่ใช่แค่แถว SQL |
| ความเสถียร | เทียบ `ours_coop_run1` vs `ours_coop_run2_retry` | ทุกไฟล์ข้างบน | "สัญญาณที่บอกว่ากำลัง overfit — ผลแกว่งมากเมื่อรันซ้ำ" |

### ทำไมต้องมี `answer_text_accuracy` แยกจาก `execution_accuracy`

เกณฑ์ให้คะแนนเดิมของ Lab 8B (`score_one` ใน `lab8b_curriculum_db.py`) เทียบแค่ **แถวผลลัพธ์ SQL**
กับเฉลย ไม่ได้เทียบ **ข้อความคำตอบ** ที่โมเดลพิมพ์ออกมาจริง ๆ — ตรงกับที่สไลด์เตือนไว้ว่า
เกณฑ์อัตโนมัติแบบนี้ "ให้คะแนนผ่านเพราะเทียบแค่แถวผลลัพธ์ SQL ไม่ได้เทียบข้อความ"

สคริปต์นี้เพิ่มการเช็คข้อความคำตอบแยกต่างหาก ผลคือเจอบั๊กที่เกณฑ์เดิมมองไม่เห็น เช่น
ใน `ours_coop_run2_retry` มีคำตอบพิมพ์รหัสวิชาเพี้ยน (`0:06066102` แทนที่จะเป็น `06066102`)
และมีคำตอบที่ echo คำถามกลับมาแทนการตอบจริง — ทั้งที่ `correct` (SQL) เป็น `true` ทุกข้อ

## ความเสถียร / overfitting

ระบบนี้ใช้ LLM สำเร็จรูป + prompt ไม่ได้เทรนโมเดลเอง จึงไม่มี train/val loss ให้ดูตรง ๆ
สัญญาณที่ใช้แทนตามสไลด์คือ **"ผลแกว่งมากเมื่อรันซ้ำด้วย seed/รอบต่างกัน"** — สคริปต์เทียบ
`ours_coop_run1` กับ `ours_coop_run2_retry` (เอกสารชุดเดียวกัน รันคนละรอบ) แล้ว flag
ว่า "ไม่เสถียร" ถ้าตัวเลขต่างกันเกิน 10%

**ห้าม** เอา `official_input_C` มาเทียบความเสถียรด้วย เพราะเป็นเอกสารคนละชุด (4 หน้าทางการ
vs เอกสารของทีมเอง) ตัวเลขต่างกันเป็นเรื่องปกติอยู่แล้ว ไม่เกี่ยวกับความเสถียรของโมเดล
