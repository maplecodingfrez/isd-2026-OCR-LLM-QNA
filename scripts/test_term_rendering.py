"""Regression checks for term elective rendering using the seven real plan databases.

Run with the project Python. Only standard-library test tools and Node are used.
"""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Lab7B_Lab8B_ocr_system/src/ocr_system'))
import lab8b_curriculum_db as db


class TermRenderingTests(unittest.TestCase):
    def test_it_group_correction_is_guarded_and_source_matches(self):
        from source_term_groups import verified_groups
        source = json.loads((ROOT / 'data/reference/it-year3-semester1.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256((ROOT / source['source']).read_bytes()).hexdigest(), source['sha256'])
        self.assertIsNone(verified_groups(3, 1, {'kind': 'choose_group', 'credits': 9}, []))
        self.assertIsNone(verified_groups(2, 1, {'kind': 'choose_group', 'credits': 9}, []))

    def test_real_plan_slots_and_alternatives_render_separately(self):
        answers = []
        for path in (ROOT / 'Lab7B_Lab8B_ocr_system/runs').rglob('curriculum.db'):
            if '_retry' in str(path):
                continue
            conn = db.open_db(path, readonly=True)
            try:
                answer = db.ask(conn, 'ปี 3 เทอม 1 มีวิชาอะไรบ้าง และรวมกี่หน่วยกิต', verbose=False)
                self.assertEqual(answer['answer_type'], 'database')
                if path.parts[-4] == 'IT':
                    slot = next(row for row in answer['rows'] if row.get('kind') == 'choose_group')
                    groups = {}
                    for member in slot['alternatives']:
                        groups.setdefault(member['group_name'], []).append(member['code'])
                    self.assertEqual(groups, {
                        'กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์': ['06016416', '06016417', '06016418'],
                        'กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ': ['06016421', '06016422', '06016423'],
                        'กลุ่มวิชาด้านสื่อประสมสำหรับการพัฒนาสื่อเชิงโต้ตอบ เว็บ และเกม': ['06016426', '06016427', '06016418'],
                    })
                    self.assertEqual(answer['citations'][0]['pdf_page'], 35)
                    self.assertEqual(answer['citations'][0]['printed_page'], '30')
                answers.append(answer)
            finally:
                conn.close()
        self.assertEqual(len(answers), 7)
        app = ROOT / 'lab10_fastapi/curriculum_app/static/app.js'
        script = '''
const assert = require('node:assert/strict');
const m = require(APP);
const i18n = require(I18N);
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; }
  appendChild(child) { this.children.push(child); }
  setAttribute() {}
}
global.document = {createElement: tag => new Element(tag), createTextNode: text => ({textContent:text, children:[]})};
const text = node => node.textContent + node.children.map(text).join(' ');
const nodes = node => [node, ...node.children.flatMap(nodes)];
for (const data of DATA) {
  const p = m.termAnswerParts(data);
  assert(p);
  assert.equal(p.total, 18);
  for (const lang of ['th', 'en']) {
    i18n.setLang(lang);
    const root = new Element('div');
    m.renderTermAnswer(root, p);
    assert(text(root.children[0]).includes('18'));
    for (const slot of p.slots) {
      if (!slot.groups.length) {
        const matches = nodes(root).filter(n => n.className === 'course-name' && n.textContent === slot.name);
        assert.equal(matches.length, 1);
        assert(!text(matches[0]).includes('06016416'));
      } else {
        const section = root.children.find(n => n.tag === 'section' && text(n.children[0]).startsWith(slot.name));
        assert(section);
        assert.equal(section.children.filter(n => n.tag === 'h4').length, slot.groups.length);
        const lists = section.children.filter(n => n.tag === 'ul');
        assert.equal(lists.length, slot.groups.length);
        slot.groups.forEach((group, index) => {
          const heading = section.children.filter(n => n.tag === 'h4')[index];
          assert.equal(heading.children[0].className, 'slot-tag');
          assert.equal(heading.children[0].textContent, i18n.t('slot.tag'));
          assert.equal(heading.children[1].textContent, group.name);
          assert.equal(lists[index].children.length, group.courses.length);
          group.courses.forEach(course => assert(text(lists[index]).includes(course.code)));
        });
      }
    }
  }
  assert.equal(m.termAnswerParts({...data, question:'วิชาเลือกมีอะไรบ้าง'}), null);
  assert.equal(m.termAnswerParts({...data, rows:[]}), null);
}
// A term with only elective slots must not crash on an empty compulsory list.
const onlySlots = {...DATA[0], rows:DATA[0].rows.filter(r => r.slot)};
m.renderTermAnswer(new Element('div'), m.termAnswerParts(onlySlots));
console.log('Seven plans, TH/EN, elective separation, all alternatives, totals, fallback and empty course list: passed');
'''
        script = script.replace('APP', json.dumps(app.as_posix())).replace('I18N', json.dumps(app.with_name('i18n.js').as_posix())).replace('DATA', json.dumps(answers, ensure_ascii=False))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'term.js'
            target.write_text(script, encoding='utf-8')
            run = subprocess.run(['node', str(target)], capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        print(run.stdout.strip())


if __name__ == '__main__':
    unittest.main()
