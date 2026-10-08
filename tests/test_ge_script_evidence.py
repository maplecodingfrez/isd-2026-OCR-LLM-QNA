import sys
from pathlib import Path
import unittest
import json
import hashlib
import tempfile
from unittest.mock import patch
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ge66_script_evidence import raised_english_text, thai_title_image, thai_region_text, recognize_region


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
