import sys
from pathlib import Path
import unittest
import json
import hashlib
import tempfile
from unittest.mock import patch
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ge66_script_evidence import (raised_english_text, thai_title_image, thai_region_text,
                                 recognize_region, typhoon_raised_text, thai_tesseract_readings)


class ScriptEvidenceTests(unittest.TestCase):
    def raised_image(self):
        image = Image.new('L', (200, 60), 'white')
        draw = ImageDraw.Draw(image)
        for x in (10, 40, 130):
            draw.rectangle((x, 20, x+15, 39), fill=0)
        draw.rectangle((70, 20, 85, 39), fill=0)
        draw.rectangle((90, 13, 96, 24), fill=0)
        return image

    def data(self):
        return dict(text=['A', 'B', 'garbled', 'C'], conf=[95, 95, 60, 95],
                    left=[10, 40, 70, 130], top=[20, 20, 13, 20],
                    width=[16, 16, 27, 16], height=[20, 20, 27, 20],
                    block_num=[1]*4, par_num=[1]*4, line_num=[1]*4)

    def test_raised_glyphs_are_read_not_replaced_from_suffix_rules(self):
        with patch('ge66_script_evidence.audit.ocr', side_effect=[self.data(), '42', 'nd']):
            text, meta = raised_english_text(self.raised_image())
        self.assertEqual(text, 'A B 42nd C')
        self.assertEqual([p['text'] for p in meta['readings'][0]['parts']], ['42', 'nd'])
        self.assertFalse(meta['case_normalized'])
        self.assertFalse(meta['reference_used'])

    def test_raw_capitalization_is_preserved(self):
        with patch('ge66_script_evidence.audit.ocr', side_effect=[self.data(), '42', 'ND']):
            text, _ = raised_english_text(self.raised_image())
        self.assertEqual(text, 'A B 42ND C')

    def test_inconclusive_part_does_not_create_evidence(self):
        with patch('ge66_script_evidence.audit.ocr', side_effect=[self.data(), '??', 'nd']):
            text, _ = raised_english_text(self.raised_image())
        self.assertIsNone(text)

    def test_missing_peer_baseline_does_not_guess(self):
        data = self.data()
        data['line_num'] = [1, 2, 3, 4]
        with patch('ge66_script_evidence.audit.ocr', return_value=data):
            text, _ = raised_english_text(self.raised_image())
        self.assertIsNone(text)

    def test_normal_title_does_not_add_an_observation(self):
        data = self.data()
        data['height'] = [20]*4
        with patch('ge66_script_evidence.audit.ocr', return_value=data):
            text, _ = raised_english_text(self.raised_image())
        self.assertIsNone(text)

    def test_thai_crop_keeps_upper_and_lower_marks(self):
        data = dict(text=['\u0e0a\u0e37\u0e48\u0e2d', '\u0e0a\u0e38\u0e21\u0e0a\u0e19', 'TITLE'],
                    left=[10, 50, 10], top=[10, 15, 70], width=[30, 40, 50], height=[30, 35, 20])
        with patch('ge66_script_evidence.audit.ocr', return_value=data):
            image, meta = thai_title_image(Image.new('L', (200, 100), 'white'))
        self.assertIsNotNone(image)
        self.assertLess(meta['thai_box'][1], 10)
        self.assertGreater(meta['thai_box'][3], 50)
        self.assertLess(meta['thai_box'][3], 70)

    def test_thai_crop_requires_image_recognized_thai(self):
        with patch('ge66_script_evidence.audit.ocr', return_value={'text': ['TITLE']}):
            image, _ = thai_title_image(Image.new('L', (200, 100), 'white'))
        self.assertIsNone(image)

    def test_title_reader_rejects_structural_or_wrong_region_output(self):
        self.assertEqual(thai_region_text('\u0e0a\u0e37\u0e48\u0e2d\n\u0e27\u0e34\u0e0a\u0e32'), '\u0e0a\u0e37\u0e48\u0e2d \u0e27\u0e34\u0e0a\u0e32')
        for text in ['TITLE', '<table>\u0e0a\u0e37\u0e48\u0e2d</table>', '90642093 \u0e0a\u0e37\u0e48\u0e2d', '\u0e0a\u0e37\u0e48\u0e2d 3 (3-0-6)']:
            self.assertIsNone(thai_region_text(text))

    def cached_region(self, folder, reason='stop'):
        path = Path(folder) / 'region.png'
        path.write_bytes(b'opaque image fixture')
        body = dict(message={'content': 'raw reading'}, done_reason=reason,
                    region_request={'image_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                    'prompt_sha256': hashlib.sha256(b'prompt').hexdigest(),
                                    'model': 'model', 'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 1024}})
        path.with_suffix('.response.json').write_text(json.dumps(body), encoding='utf-8')
        return path

    def test_cached_region_requires_the_same_prompt_and_model(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.cached_region(folder)
            self.assertEqual(recognize_region(path, 'prompt', 'model'), 'raw reading')
            for prompt, model in [('other prompt', 'model'), ('prompt', 'other model')]:
                with self.assertRaisesRegex(RuntimeError, 'provenance'):
                    recognize_region(path, prompt, model)

    def test_truncated_region_response_cannot_vote(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.cached_region(folder, reason='length')
            with self.assertRaisesRegex(RuntimeError, 'truncated'):
                recognize_region(path, 'prompt', 'model')

    def independent_meta(self):
        return {'tokens': ['A', 'B', 'garbled', 'C'],
                'readings': [{'token_index': 2, 'word_box': [70, 13, 97, 40], 'text': '42nd'}]}

    def test_independent_word_reader_does_not_copy_tesseract_answer(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                'ge66_script_evidence.recognize_region', side_effect=['A B 42ND C', '73rd']):
            text, meta = typhoon_raised_text(self.raised_image(), Path(folder), 'model', self.independent_meta())
        self.assertEqual(text, 'A B 73rd C')
        self.assertFalse(meta['tesseract_text_used_as_fill'])

    def test_independent_case_is_not_normalized(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                'ge66_script_evidence.recognize_region', side_effect=['A B 42nd C', '42ND']):
            text, _ = typhoon_raised_text(self.raised_image(), Path(folder), 'model', self.independent_meta())
        self.assertEqual(text, 'A B 42ND C')

    def test_unaligned_context_refuses_token_substitution(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                'ge66_script_evidence.recognize_region', return_value='A extra B 42ND C') as read:
            text, meta = typhoon_raised_text(self.raised_image(), Path(folder), 'model', self.independent_meta())
        self.assertIsNone(text)
        self.assertEqual(read.call_count, 1)
        self.assertEqual(meta['reason'], 'unaligned_whole_region_reading')

    def test_wrong_unchanged_token_refuses_substitution(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                'ge66_script_evidence.recognize_region', return_value='A WRONG 42ND C'):
            text, _ = typhoon_raised_text(self.raised_image(), Path(folder), 'model', self.independent_meta())
        self.assertIsNone(text)

    def test_thai_crop_preserves_letters_outside_old_column_ratio(self):
        data = dict(text=['\u0e40\u0e2d'], left=[10], top=[10], width=[20], height=[20])
        with patch('ge66_script_evidence.audit.ocr', return_value=data) as read:
            image, meta = thai_title_image(Image.new('L', (200, 100), 'white'))
        self.assertEqual(read.call_args.args[0].size, (200, 100))
        self.assertEqual(meta['coordinate_space'], 'row_image')
        self.assertLessEqual(meta['thai_box'][0], 10)

    def test_wrapped_thai_does_not_use_single_line_psm(self):
        data = dict(text=['\u0e0a\u0e37\u0e48\u0e2d', '\u0e27\u0e34\u0e0a\u0e32'],
                    block_num=[1, 1], par_num=[1, 1], line_num=[1, 2])
        with tempfile.TemporaryDirectory() as folder, patch(
                'ge66_script_evidence.audit.ocr', side_effect=[data, '\u0e0a\u0e37\u0e48\u0e2d', '\u0e0a\u0e37\u0e48\u0e2d']) as read:
            result = thai_tesseract_readings(self.raised_image(), Path(folder))
        self.assertEqual(len(result), 2)
        self.assertEqual([call.args[2] for call in read.call_args_list], [6, 6, 6])

    def test_single_line_thai_keeps_native_and_half_readings(self):
        data = dict(text=['\u0e0a\u0e37\u0e48\u0e2d'], block_num=[1], par_num=[1], line_num=[1])
        with tempfile.TemporaryDirectory() as folder, patch(
                'ge66_script_evidence.audit.ocr', side_effect=[data]+['\u0e0a\u0e37\u0e48\u0e2d']*4):
            result = thai_tesseract_readings(self.raised_image(), Path(folder))
        self.assertEqual(len(result), 4)
        self.assertEqual(len({r['image_sha256'] for r in result}), 2)

    def test_thai_region_keeps_latin_acronym_and_excludes_code_credits(self):
        data = dict(text=['90642000', '\u0e0a\u0e37\u0e48\u0e2d', 'XYZ', '3', '(3-0-6)', 'ENGLISH'],
                    left=[1, 40, 80, 140, 150, 40], top=[20, 10, 20, 20, 20, 70],
                    width=[20, 25, 25, 5, 30, 60], height=[20, 35, 20, 20, 20, 20],
                    block_num=[1]*6, par_num=[1]*6, line_num=[1]*5+[2])
        with patch('ge66_script_evidence.audit.ocr', return_value=data):
            image, meta = thai_title_image(Image.new('L', (200, 100), 'white'))
        self.assertLessEqual(meta['thai_box'][0], 40)
        self.assertGreaterEqual(meta['thai_box'][0], 21)
        self.assertGreaterEqual(meta['thai_box'][2], 105)
        self.assertLess(meta['thai_box'][2], 140)
        self.assertLess(meta['thai_box'][3], 70)
