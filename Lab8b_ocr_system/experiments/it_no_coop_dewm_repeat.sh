#!/bin/bash
# รอบควบคุม + รอบ dewm ซ้ำ 2 รอบของ IT no-coop (ทำต่อเนื่อง; ผลไปโฟลเดอร์ใหม่ ไม่ทับของเดิม)
cd "$(dirname "$0")/.."
export PYTHONUTF8=1
for args in "--control" "--tag 2" "--tag 3"; do
  echo "=== run_lab8b_it_no_coop_dewm.py $args $(date +%H:%M:%S)"
  ../.venv/Scripts/python.exe run_lab8b_it_no_coop_dewm.py $args 2>&1 | grep -E "ตัดตราน้ำ|ไม่ตัดตราน้ำ|อ่านซ้ำ|หมดรอบ|❌|Traceback|Error|เสร็จแล้ว|SQL รันผ่าน|ตอบถูก"
done
echo ALL_DONE $(date +%H:%M:%S)
