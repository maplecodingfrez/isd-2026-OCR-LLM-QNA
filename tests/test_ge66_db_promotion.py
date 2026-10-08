from contextlib import closing
import sys
import unittest
import tempfile
import sqlite3
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))


class PromotionTests(unittest.TestCase):
    def catalog(self):
        return {'source':'GE66 image OCR','plan_slot':'GE edition 2566','groups':[{'group_no':2,'courses':[
            {'code':'90642001','name_th':'NEW THAI','name_en':'NEW ENGLISH','credits':'3 (3-0-6)','page':12,'graded_su':False},
            {'code':'90642002','name_th':'SECOND','name_en':'SECOND ENGLISH','credits':'2 (1-2-3)','page':12,'graded_su':False}]}],
            'provenance':{'method':'image_only_ocr','verified_records':2,'raw_ocr_traceable_field_values':6,'manual_fills':0,'reference_used_as_ocr_prompt_or_field_fill':False}}

    def source_db(self,path):
        with closing(sqlite3.connect(path)) as c:
            c.executescript('CREATE TABLE course(code TEXT PRIMARY KEY,name TEXT); CREATE TABLE elective_group(id INTEGER PRIMARY KEY,plan_slot TEXT,group_no INTEGER); CREATE TABLE elective_group_course(group_id INTEGER,code TEXT,name_th TEXT,name_en TEXT,credits INTEGER);')
            c.execute('INSERT INTO course VALUES (?,?)',('fixed','KEEP'))
            c.executemany('INSERT INTO elective_group VALUES (?,?,?)',[(7,'GE edition 2566',2),(9,'OTHER',3)])
            c.executemany('INSERT INTO elective_group_course VALUES (?,?,?,?,?)',[(7,'90642001','OLD','OLD',3),(7,'90642002','OLD SECOND','OLD SECOND',2),(9,'OTHER','KEEP','KEEP',1)])
            c.commit()

    def test_untraceable_or_partial_image_catalog_is_refused(self):
        import ge66_promote_db as m
        cat=self.catalog();rows=cat['groups'][0]['courses']
        obs={r['code']:[dict(r)] for r in rows}
        summary={'all_fields_exact':2,'field_values_traceable_to_raw_ocr':6,'manually_filled_fields':0,'page_and_flag_checks':True,'reference_used_as_ocr_prompt_or_field_fill':False}
        m.verify_catalog(cat,rows,obs,summary,expected=2)
        del obs['90642001'][0]['name_en']
        with self.assertRaises(ValueError):m.verify_catalog(cat,rows,obs,summary,expected=2)
        with self.assertRaises(ValueError):m.verify_catalog(cat,rows,obs,summary,expected=303)

    def test_staging_updates_only_ge_fields_and_preserves_ids_other_tables_and_source(self):
        import ge66_promote_db as m
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/'original.db';dst=Path(folder)/'stage.db';self.source_db(src)
            before=m.sha(src);m.stage_database(src,dst,self.catalog())
            self.assertEqual(m.sha(src),before)
            with closing(sqlite3.connect(dst)) as c:
                self.assertEqual(c.execute('SELECT * FROM course').fetchall(),[('fixed','KEEP')])
                self.assertEqual(c.execute('SELECT id FROM elective_group ORDER BY id').fetchall(),[(7,),(9,)])
                self.assertEqual(c.execute('SELECT name_th,name_en,credits FROM elective_group_course WHERE code=?',('90642001',)).fetchone(),('NEW THAI','NEW ENGLISH',3))
                self.assertEqual(c.execute('SELECT * FROM elective_group_course WHERE code=?',('OTHER',)).fetchone(),(9,'OTHER','KEEP','KEEP',1))

    def test_missing_existing_course_is_refused_without_source_changes(self):
        import ge66_promote_db as m
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/'original.db';dst=Path(folder)/'stage.db';self.source_db(src)
            with closing(sqlite3.connect(src)) as c:
                c.execute("DELETE FROM elective_group_course WHERE code='90642002'");c.commit()
            before=m.sha(src)
            with self.assertRaises(ValueError):m.stage_database(src,dst,self.catalog())
            self.assertEqual(m.sha(src),before)

    def manifest(self,folder):
        import ge66_promote_db as m
        root=Path(folder)/'root';work=Path(folder)/'work';root.mkdir();work.mkdir()
        entries=[]
        for relative in (m.CATALOG,m.PROVENANCE):
            target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
            existed=relative==m.CATALOG
            if existed:target.write_bytes(b'OLD')
            staged=work/(target.name+'.new');staged.write_bytes(b'NEW')
            backup=work/(target.name+'.bak')
            if existed:backup.write_bytes(target.read_bytes())
            entries.append({'relative':relative,'before':m.sha(target) if existed else None,'after':m.sha(staged),'staged':str(staged),'backup':str(backup) if existed else None})
        return {'root':str(root),'state':'prepared','files':entries,'databases':[]},root

    def test_install_refuses_target_stage_and_backup_drift_before_any_write(self):
        import ge66_promote_db as m
        for kind in ('target','staged','backup'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder:
                manifest,root=self.manifest(folder);e=manifest['files'][0]
                path=root/e['relative'] if kind=='target' else Path(e[kind]);path.write_bytes(b'DRIFT')
                before=(root/m.CATALOG).read_bytes()
                with self.assertRaises(ValueError):m.install(manifest)
                self.assertEqual((root/m.CATALOG).read_bytes(),before)
                self.assertFalse((root/m.PROVENANCE).exists())

    def test_partial_install_failure_restores_original_and_removes_new_file(self):
        import ge66_promote_db as m
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            manifest,root=self.manifest(folder);original=m.replace_file;calls=[]
            def fail_second(source,target):
                calls.append(target)
                if len(calls)==2:raise OSError('simulated install failure')
                return original(source,target)
            with patch.object(m,'replace_file',side_effect=fail_second):
                with self.assertRaises(OSError):m.install(manifest)
            self.assertEqual((root/m.CATALOG).read_bytes(),b'OLD')
            self.assertFalse((root/m.PROVENANCE).exists())

    def test_checked_restore_refuses_intervening_changes_then_restores(self):
        import ge66_promote_db as m
        with tempfile.TemporaryDirectory() as folder:
            manifest,root=self.manifest(folder);m.install(manifest)
            (root/m.CATALOG).write_bytes(b'OTHER WRITER')
            with self.assertRaises(ValueError):m.restore(manifest,apply=True)
            self.assertEqual((root/m.CATALOG).read_bytes(),b'OTHER WRITER')
            (root/m.CATALOG).write_bytes(b'NEW');m.restore(manifest,apply=True)
            self.assertEqual((root/m.CATALOG).read_bytes(),b'OLD')
            self.assertFalse((root/m.PROVENANCE).exists())
