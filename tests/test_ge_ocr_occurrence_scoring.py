import sys
from pathlib import Path
import unittest
import tempfile
import hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ge64_occurrence_score as audit
import ge64_trial_artifacts as artifacts
import json

class OccurrenceScoreTests(unittest.TestCase):
    def row(self,page,title='TITLE',code='90643006'):
        return dict(code=code,page=page,name_th='Thai',name_en=title,credits='3 (3-0-6)')

    def test_repeated_rows_are_counted_and_missing_repeat_closes_gate(self):
        reference=[self.row(150),self.row(150),self.row(153)]
        score=audit.occurrence_metrics(reference,[self.row(150),self.row(153)])
        self.assertEqual(score['expected'],3)
        self.assertEqual(score['all_fields_exact'],2)
        self.assertEqual(score['missing_occurrences'],[{'page':150,'code':'90643006','count':1}])
        self.assertFalse(audit.occurrence_gate(score,failures=[]))

    def test_cross_page_field_mixing_does_not_score_as_correct(self):
        reference=[self.row(150,'FIRST'),self.row(153,'SECOND')]
        score=audit.occurrence_metrics(reference,[self.row(150,'SECOND'),self.row(153,'FIRST')])
        self.assertEqual(score['all_fields_exact'],0)
        self.assertEqual(len(score['differences']),2)

    def test_page_specific_printed_conflict_is_correct_without_canonical_guess(self):
        reference=[self.row(150,'FIRST'),self.row(153,'SECOND')]
        score=audit.occurrence_metrics(reference,reference)
        self.assertEqual(score['all_fields_exact'],2)
        self.assertTrue(audit.occurrence_gate(score,failures=[]))

    def test_extra_duplicate_or_failed_recognition_closes_gate(self):
        score=audit.occurrence_metrics([self.row(150)],[self.row(150),self.row(150)])
        self.assertEqual(score['extra_occurrences'],[{'page':150,'code':'90643006','count':1}])
        self.assertFalse(audit.occurrence_gate(score,failures=[]))
        exact=audit.occurrence_metrics([self.row(150)],[self.row(150)])
        self.assertFalse(audit.occurrence_gate(exact,failures=[{'reason':'truncated'}]))

    def test_empty_sample_cannot_pass_gate(self):
        self.assertFalse(audit.occurrence_gate(audit.occurrence_metrics([],[]),failures=[]))

    def test_completion_marker_detects_candidate_changes_before_scoring(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'candidate.json').write_bytes(b'original')
            marker={'immutable_ocr_sha256':{'candidate.json':hashlib.sha256(b'original').hexdigest()}}
            self.assertEqual(audit.verify_completion_hashes(root,marker),1)
            (root/'candidate.json').write_bytes(b'changed')
            with self.assertRaises(RuntimeError):audit.verify_completion_hashes(root,marker)

    def test_exact_unambiguous_catalog_does_not_hide_a_printed_source_conflict(self):
        score={'expected':33,'all_fields_exact':33,'extra_codes':[], 'missing_codes':[], 'differences':[]}
        self.assertTrue(audit.catalog_gate(score,failures=[],reference_conflicts={}))
        self.assertFalse(audit.catalog_gate(score,failures=[],reference_conflicts={'90643006':['two printed titles']}))

    def test_no_anchor_run_writes_empty_observations_before_completion_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            artifacts.write_trial_artifacts(root,observations={},records=[],occurrences=[],review=[],
                                            raw_pages={'tesseract':[],'typhoon':[]},failures=[])
            self.assertEqual(json.loads((root/'observations.json').read_text(encoding='utf-8')), {})
            marker=json.loads((root/'ocr-complete.json').read_text(encoding='utf-8'))
            self.assertTrue(marker['completed_before_reference_extraction'])
            self.assertEqual(audit.verify_completion_hashes(root,marker),3)
