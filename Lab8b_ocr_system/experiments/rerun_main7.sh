#!/bin/bash
# รัน 7 แผนหลักใหม่ทั้งรอบ (Lab 7B OCR + Lab 8B) ด้วยโค้ดปัจจุบัน — ไม่ตัดตราน้ำ ไม่อ่านซ้ำ (ค่าเริ่มต้น)
# ผลเดิมอยู่ใน git (ย้อนกลับได้); log ต่อแผนที่ experiments/rerun_main7_<แผน>.log; ต่อด้วย apply_name_consensus/regenerate/lab9 ทำแยก
cd "$(dirname "$0")/.."
export PYTHONUTF8=1
for s in ait bit_no_coop bit_coop dsba_no_coop dsba_coop it_no_coop it_coop; do
  t0=$(date +%s)
  echo "=== START $s $(date +%H:%M:%S)"
  ../.venv/Scripts/python.exe run_lab8b_$s.py > experiments/rerun_main7_$s.log 2>&1
  rc=$?
  echo "=== DONE $s rc=$rc $(( ($(date +%s)-t0)/60 )) นาที | $(grep -E 'SQL รันผ่าน|ตอบถูก' experiments/rerun_main7_$s.log | tr -s ' ' | tr '\n' ' ')"
done
echo ALL_DONE $(date +%H:%M:%S)
