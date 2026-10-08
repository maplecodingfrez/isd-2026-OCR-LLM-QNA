"""Exercise actual runner functions without invoking the CLI or OCR services."""
import ast
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
import ge66_ocr_audit as audit
from ge66_script_evidence import catalog_table_delimiters
from ge66_select_candidate import select_occurrences
from ge64_occurrence_score import occurrence_gate,occurrence_metrics


def function(name,namespace):
    path=Path(__file__).resolve().parents[1]/'scripts/ge64_image_trial.py'
    node=next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    return namespace[name]


class RunnerSafetyTests(unittest.TestCase):
    def test_multi_course_required_row_cannot_vote_even_when_both_engines_agree(self):
        rows=[dict(code=c,page=1,name_th='ชื่อ',name_en='WRONG NEIGHBOR TITLE',credits='3 (3-0-6)') for c in ('90642113','90643021')]
        observations=defaultdict(list);failures=[]
        namespace=dict(eec=SimpleNamespace(parse_ge_ocr=lambda pages:rows),audit=audit,catalog_table_delimiters=catalog_table_delimiters,observations=observations,failures=failures)
        add=function('add',namespace)
        for engine in ('tesseract','typhoon'):
            add(engine,'row',1,'90642113 ชื่อ 3 (3-0-6)\nWRONG NEIGHBOR TITLE\n90643021 อื่น 3 (3-0-6)\nOTHER','90642113',{'clipped':False,'occurrence_id':'row-1'})
        for items in observations.values():
            for item in items:item['occurrence_id']='row-1'
        selected,_=select_occurrences(observations)
        self.assertEqual(selected,[])
        self.assertTrue(failures)

    def test_empty_cached_required_response_closes_the_actual_occurrence_gate(self):
        for content in ('','   ',None,[]):
            with self.subTest(content=content),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);p=root/'row.png';p.write_bytes(b'image');failures=[]
                body={'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'prompt_sha256':'prompt','model_digest':'model','request_options':{'temperature':0,'num_ctx':8192,'num_predict':1024},'message':{'content':content},'done':True}
                p.with_suffix('.response.json').write_text(json.dumps(body),encoding='utf-8')
                recognize=function('recognize',dict(hashlib=hashlib,json=json,plan={'prompt_sha256':'prompt'},MODEL='model',OUT=root,failures=failures))
                try:recognize(p,1024)
                except TypeError:pass
                row=dict(code='90642113',page=1,name_th='ชื่อ',name_en='TITLE',credits='3 (3-0-6)',engine='tesseract',variant='row',occurrence_id='row-1')
                selected,_=select_occurrences({row['code']:[row]})
                self.assertFalse(occurrence_gate(occurrence_metrics([row],selected),failures=failures))
                self.assertTrue(failures)
