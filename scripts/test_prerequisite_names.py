"""Check bilingual prerequisite/follow-up labels against actual plan names."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Lab7B_Lab8B_ocr_system/src/ocr_system'))
import lab8b_curriculum_db as db
from course_overview import prerequisite_lookup


class BilingualNamesTests(unittest.TestCase):
    def test_calculus_question_displays_followup_not_source_course(self):
        for plan in ('coop', 'no_coop'):
            conn = db.open_db(ROOT / f'Lab7B_Lab8B_ocr_system/runs/DSBA/{plan}/lab8b_output/curriculum.db', readonly=True)
            try:
                result = db.ask(conn, 'วิชาที่ต้องผ่าน 06026200 ก่อนมีอะไรบ้าง', verbose=False)
                self.assertEqual([row['code'] for row in result['rows']], ['06026201'])
                self.assertEqual(result['answer'].splitlines()[0], 'วิชาต่อที่ต้องผ่าน 06026200 ก่อน:')
                self.assertIn('06026201 (แคลคูลัส 2 / CALCULUS 2)', result['answer'])
                app = ROOT / 'lab10_fastapi/curriculum_app/static/app.js'
                code = f"const m=require({json.dumps(app.as_posix())}); console.log(JSON.stringify(m.groupCourseBlocks(m.answerBlocks({json.dumps(result)}))));"
                run = subprocess.run(['node', '-e', code], capture_output=True, text=True, encoding='utf-8', timeout=20)
                self.assertEqual(run.returncode, 0, run.stderr)
                entries = [entry for block in json.loads(run.stdout) if block['type'] == 'courses' for entry in block['entries']]
                self.assertEqual([entry['code'] for entry in entries], ['06026201'])
                self.assertEqual(entries[0]['nameEn'], 'CALCULUS 2')
            finally:
                conn.close()

    def test_real_followups_and_prerequisites_keep_both_names(self):
        count = 0
        for path in (ROOT / 'Lab7B_Lab8B_ocr_system/runs').rglob('curriculum.db'):
            if '_retry' in str(path):
                continue
            conn = db.open_db(path, readonly=True)
            try:
                for code, in conn.execute('SELECT code FROM course'):
                    for question in (f'วิชาที่ต้องผ่าน {code} ก่อนมีอะไรบ้าง', f'วิชาบังคับก่อนของ {code} มีอะไรบ้าง'):
                        result = prerequisite_lookup(conn, question, db.prerequisite_status)
                        self.assertIsNotNone(result)
                        for row in result[1]:
                            names = [row[key] for key in ('name_th', 'name_en') if row[key]]
                            self.assertIn(f"{row['code']} ({' / '.join(names)})", result[0])
                            count += 1
            finally:
                conn.close()
        self.assertGreater(count, 0)
        print(f'Checked {count} real prerequisite/follow-up labels across seven plans')

    def test_frontend_separates_bilingual_names(self):
        app = ROOT / 'lab10_fastapi/curriculum_app/static/app.js'
        line = 'วิชาต่อ: 06066301 (ระบบฐานข้อมูล / DATABASE SYSTEMS)'
        code = f"const m=require({json.dumps(app.as_posix())}); console.log(JSON.stringify(m.parseCourseLine({json.dumps(line)})));"
        run = subprocess.run(['node', '-e', code], capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        entry = json.loads(run.stdout)
        self.assertEqual(entry['name'], 'ระบบฐานข้อมูล')
        self.assertEqual(entry['nameEn'], 'DATABASE SYSTEMS')
        self.assertEqual(entry['lead'], 'วิชาต่อ:')


if __name__ == '__main__':
    unittest.main()
