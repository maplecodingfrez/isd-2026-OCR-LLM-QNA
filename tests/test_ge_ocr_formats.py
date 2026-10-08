"""GE66 OCR format regressions; no PDF, model or reference catalog needed."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(os.environ['GE66_SOURCE_ROOT']) if 'GE66_SOURCE_ROOT' in os.environ else next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / 'Lab7B_Lab8B_ocr_system/src/ocr_system/extract_elective_catalog.py').is_file())
MODULE_DIR = ROOT / "Lab7B_Lab8B_ocr_system/src/ocr_system"
sys.path.insert(0, str(MODULE_DIR))
import extract_elective_catalog as eec


class GEFormats(unittest.TestCase):
    def parse(self, text):
        return eec.parse_ge_ocr([{"page": 15, "text": text}])

    def test_inline_bilingual_and_wrapped_credit(self):
        rows = self.parse("90642011 การคิดอย่างมีวิจารณญาณ CRITICAL THINKING "
                          "<page_number>3 (3-0-6)</page_number>")
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['name_th'], rows[0]['name_en']),
                         ('การคิดอย่างมีวิจารณญาณ', 'CRITICAL THINKING'))

    def test_credit_after_english_line(self):
        rows = self.parse("90644009 การออกเสียงภาษาอังกฤษเบื้องต้น\n"
                          "BASIC ENGLISH PRONUNCIATION <page_number>3 (3-0-6)</page_number>")
        self.assertEqual(rows[0]['credit_text'], '3 (3-0-6)')
        self.assertEqual(rows[0]['name_en'], 'BASIC ENGLISH PRONUNCIATION')

    def test_mixed_html_cell(self):
        rows = self.parse('<table><tr><td>90645001</td><td>การคิดวิเคราะห์ ANALYTICAL THINKING'
                          '</td><td>1 (1-0-2)</td></tr></table>')
        self.assertEqual(rows[0]['name_en'], 'ANALYTICAL THINKING')

    def test_entities_and_punctuation(self):
        rows = self.parse('90642039 ซ่อมได้ภายในบ้าน 3 (3-0-6)\nQUICK-FIX @ HOME\n'
                          '90642052 จากเส้นสาย DNA สู่พันธุกรรม 3 (3-0-6)\n'
                          'GENES &amp; GENETICS : FROM HELIX TO HEREDITARY')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['name_en'], 'QUICK-FIX @ HOME')
        self.assertEqual(rows[1]['name_th'], 'จากเส้นสาย DNA สู่พันธุกรรม')
        self.assertIn('& GENETICS', rows[1]['name_en'])

    def test_separate_code_and_credit(self):
        rows = self.parse('**90641008\nพื้นฐานทักษะภาษาอังกฤษ\nENGLISH SKILLS\n0 (0-0-45)')
        self.assertEqual(rows[0]['credits'], 0)
        self.assertTrue(rows[0]['graded_su'])

    def test_incomplete_credit_not_borrowed_from_next_course(self):
        rows = self.parse('90642011 วิชาหนึ่ง 3 (3-0-6\nCOURSE ONE\n'
                          '90642012 วิชาสอง 3 (3-0-6)\nCOURSE TWO')
        self.assertEqual([r['code'] for r in rows], ['90642012'])

    def test_multiple_credit_values_are_ambiguous(self):
        self.assertEqual(self.parse('90642011 วิชาหนึ่ง 3 (3-0-6) 2 (2-0-4)\nCOURSE ONE'), [])

    def test_conflicting_duplicates_excluded(self):
        self.assertEqual(self.parse('90642011 วิชาหนึ่ง 3 (3-0-6)\nCOURSE ONE\n'
                                   '90642011 วิชาหนึ่ง 2 (2-0-4)\nCOURSE ONE'), [])

    def test_no_name_repair_or_code_guessing(self):
        rows = self.parse('*90641004 โครงงานกลุ่ม 1 1 (0-2-1)\nTEAM-PROJECT 4\n'
                          '9064I005 โครงงานกลุ่ม 2 1 (0-2-1)\nTEAM-PROJECT 2')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name_en'], 'TEAM-PROJECT 4')

    def test_no_english_no_record(self):
        self.assertEqual(self.parse('90642011 วิชาหนึ่ง 3 (3-0-6)'), [])

    def test_shifted_and_merged_bilingual_titles_rejected(self):
        self.assertEqual(self.parse('90642083 MUSIC APPRECIATION ศิลปะแห่งภาพยนตร์ 3 (3-0-6)'), [])
        self.assertEqual(self.parse('90642091 เอเชียนศึกษา ASIAN STUDY การศึกษาเพื่อสร้างพลเมือง '
                                   'CIVIC EDUCATION 3 (3-0-6)'), [])

    def test_malformed_next_code_does_not_destroy_complete_row(self):
        rows = self.parse('90642138 สมาธิเพื่อพัฒนาชีวิต 3 (3-0-6)\nMEDITATION FOR LIFE DEVELOPMENT\n'
                          '906642140 ภูมิคุ้มกันทางใจ 3 (3-0-6)\nIMMUNITY OF MIND')
        self.assertEqual([r['code'] for r in rows], ['90642138'])

    def test_html_rowspan_and_colspan_continuations(self):
        rows = self.parse('<table><tr><td>90642082</td><td>สุนทรียะดนตรี</td><td></td></tr>'
                          '<tr><td colspan="3">MUSIC APPRECIATION 3 (3-0-6)</td></tr>'
                          '<tr><td rowspan="2">90642083</td><td>ศิลปะแห่งภาพยนตร์</td><td></td></tr>'
                          '<tr><td>FILM APPRECIATION</td><td>3 (3-0-6)</td></tr></table>')
        self.assertEqual([r['code'] for r in rows], ['90642082', '90642083'])
        self.assertEqual(rows[1]['name_en'], 'FILM APPRECIATION')

    def test_html_does_not_borrow_next_title_or_cross_tables(self):
        self.assertEqual(self.parse('<table><tr><td rowspan="2">90642082</td><td>สุนทรียะดนตรี</td>'
                                   '<td></td></tr><tr><td>วิชาถัดไป OTHER COURSE</td>'
                                   '<td>3 (3-0-6)</td></tr></table>'), [])
        self.assertEqual(self.parse('<table><tr><td rowspan="2">90642082</td><td>สุนทรียะดนตรี</td>'
                                   '<td></td></tr></table><table><tr><td colspan="3">'
                                   'MUSIC APPRECIATION 3 (3-0-6)</td></tr></table>'), [])

    def test_truncated_table_keeps_only_complete_rows(self):
        rows = self.parse('<table><tr><td>90642011</td><td>การคิดอย่างมีวิจารณญาณ<br>'
                          'CRITICAL THINKING</td><td>3 (3-0-6)</td></tr>'
                          '<tr><td>90642012</td><td>วิชาที่ขาด')
        self.assertEqual([r['code'] for r in rows], ['90642011'])


if __name__ == '__main__':
    unittest.main()
