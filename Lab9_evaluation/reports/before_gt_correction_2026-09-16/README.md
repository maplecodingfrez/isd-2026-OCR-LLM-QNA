# Snapshot ก่อนแก้ Ground Truth (2026-09-16)

- `prf1_before_recomputed.md/.json` — P/R/F1 + name_th CER/WER/exact ของ 4 run ที่ GT ถูกแก้
  **คำนวณใหม่ 2026-09-20** ด้วย GT ต้นฉบับ (รายงานเดิมถูกอัปเดตทับหลังแก้ GT ไปแล้วตั้งแต่ 2026-09-16
  จึงไม่มีสำเนา "ก่อนแก้" ของไฟล์นั้นเหลืออยู่ — ตัวเลข exact เดิม 0.600/0.587/0.642/0.630 ตรงกับที่บันทึกใน PROGRESS.md)
- `ground_truth_original/` — GT ต้นฉบับ DSBA coop/no_coop + IT coop/no_coop (สำเนาจาก `sources/GT/`)
  แก้ typo `name_th` รวม 7 จุด (DSBA: 06066303, 90641001, 06026205, 06066304, 06026204 · IT: 06066301, 06016412)
- AIT/BIT ไม่มีการแก้ GT จึงไม่เก็บสำเนา

ฉบับหลังแก้ GT คือ `reports/lab7b_prf1_cerwer_2026-09-16.md` (อัปเดตแล้วตั้งแต่ 2026-09-16)
