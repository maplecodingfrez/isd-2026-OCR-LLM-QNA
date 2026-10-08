"""Checks that selection preserves observed text and distinctions, without a GT API."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ge66_select_candidate import select
from ge66_typographic_consensus import content_key


class SelectionTests(unittest.TestCase):
    def test_apostrophes_are_content_equivalent(self):
        self.assertEqual(content_key('MY DOG’S MY BOSS'), content_key("MY DOG'S MY BOSS"))

    def test_letter_and_case_errors_are_not_hidden(self):
        self.assertNotEqual(content_key('FUN WITH AI'), content_key('FUN WITH Al'))
        self.assertNotEqual(content_key('21st CENTURY'), content_key('215 CENTURY'))
        self.assertNotEqual(content_key('21st CENTURY'), content_key('21ST CENTURY'))

    def test_selection_keeps_real_observation_and_review(self):
        rows = [dict(code='90642102', page=19, engine='tesseract', variant='original',
                     name_th='นักสื่อสารผ่านยูทูบ', name_en='YOUTUBER', credits='3 (3-0-6)'),
                dict(code='90642102', page=19, engine='typhoon', variant='row_crop',
                     name_th='นักสื่อสารผ่านยูทูป', name_en='YOUTUBER', credits='3 (3-0-6)')]
        result, review = select({'90642102': rows})
        self.assertEqual(len(result), 1)
        self.assertEqual(len(review), 1)
        for key in ('name_th', 'name_en', 'credits'):
            self.assertIn(result[0][key], [r[key] for r in rows])
        self.assertEqual(review[0]['evidence']['name_th']['different_values'], 2)

    def test_single_engine_stays_reviewable(self):
        rows = [dict(code='90642102', page=19, engine='typhoon', variant='row_crop',
                     name_th='นักสื่อสารผ่านยูทูป', name_en='YOUTUBER', credits='3 (3-0-6)')]
        result, review = select({'90642102': rows})
        self.assertEqual(result[0]['name_th'], 'นักสื่อสารผ่านยูทูป')
        self.assertEqual(review[0]['evidence']['name_th']['engines'], ['typhoon'])


if __name__ == '__main__':
    unittest.main()
