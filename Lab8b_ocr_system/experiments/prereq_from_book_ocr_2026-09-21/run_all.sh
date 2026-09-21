#!/bin/bash
cd "$(dirname "$0")/../.."
for s in ait bit_no_coop bit_coop dsba_no_coop dsba_coop it_no_coop it_coop; do
  echo "=== run_lab8b_$s.py --skip-lab7 $(date +%H:%M:%S)"
  ../.venv/Scripts/python.exe run_lab8b_$s.py --skip-lab7 2>&1 | grep -E "prerequisite|วิชารหัสจริง|CHK5|ผ่าน:|execution|valid_sql|เสร็จแล้ว|Traceback|Error" | head -12
  echo "exit=$?"
done
echo ALL_DONE
