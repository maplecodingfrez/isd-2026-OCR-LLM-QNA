#!/bin/bash
# รันรอบ retry (เช็คความเสถียร Lab 9) ใหม่ด้วยโค้ดปัจจุบัน เงื่อนไขเดียวกับรอบหลัก — เพื่อให้เทียบ "หลัก vs retry" เป็นความแกว่งของ OCR ล้วน ๆ
# (ก่อนหน้านี้ retry เป็นโค้ดเก่า ทำให้ความต่างปนกับการแก้โค้ด); ผลเดิมอยู่ใน git; log: experiments/rerun_retries_<ชื่อ>.log
cd "$(dirname "$0")/.."
export PYTHONUTF8=1
# แต่ละงาน = "สคริปต์|อาร์กิวเมนต์เสริม|ชื่อ log"
jobs=(
  "run_lab8b_ait_retry.py||ait_retry"
  "run_lab8b_ait_retry.py|--tag 2|ait_retry2"
  "run_lab8b_ait_retry.py|--tag 3|ait_retry3"
  "run_lab8b_bit_no_coop_retry.py||bit_no_coop_retry"
  "run_lab8b_bit_coop_retry.py||bit_coop_retry"
  "run_lab8b_dsba_no_coop_retry.py||dsba_no_coop_retry"
  "run_lab8b_dsba_coop_retry.py||dsba_coop_retry"
  "run_lab8b_it_no_coop_retry.py||it_no_coop_retry"
  "run_lab8b_it_coop_retry.py||it_coop_retry"
)
for job in "${jobs[@]}"; do
  IFS='|' read -r script extra name <<< "$job"
  t0=$(date +%s)
  echo "=== START $name $(date +%H:%M:%S)"
  ../.venv/Scripts/python.exe "$script" $extra > "experiments/rerun_retries_$name.log" 2>&1
  rc=$?
  echo "=== DONE $name rc=$rc $(( ($(date +%s)-t0)/60 )) นาที | $(grep -E 'SQL รันผ่าน|ตอบถูก' "experiments/rerun_retries_$name.log" | tr -s ' ' | tr '\n' ' ')"
done
echo ALL_DONE $(date +%H:%M:%S)
