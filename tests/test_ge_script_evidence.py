import sys
from pathlib import Path
import unittest
import json
import hashlib
import tempfile
from unittest.mock import patch
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ge66_script_evidence as se
from ge66_script_evidence import (raised_english_text, thai_title_image, thai_region_text,
                                 recognize_region, typhoon_raised_text, thai_tesseract_readings,
                                 mixed_script_tesseract_reading, catalog_table_delimiters)


class ScriptEvidenceTests(unittest.TestCase):
    def test_table_delimiter_conversion_preserves_all_title_characters(self):
        raw = '90642022 | \u0e0a\u0e37\u0e48\u0e2d | XYZ 3 (3-0-6)\nTITLE'
        self.assertEqual(catalog_table_delimiters(raw),
                         '90642022 \u0e0a\u0e37\u0e48\u0e2d | XYZ 3 (3-0-6)\nTITLE')

    def test_table_conversion_does_not_touch_names_or_malformed_codes(self):
        raw = '9064202X | NAME\n90642022 |NAME\nNAME | OTHER\n<table>90642022 | NAME</table>'
        self.assertEqual(catalog_table_delimiters(raw),
                         '9064202X | NAME\n90642022 NAME\nNAME | OTHER\n<table>90642022 | NAME</table>')

    def test_thai_title_region_stops_before_english_and_faculty_footer(self):
        image = Image.new('L', (400, 180), 'white')
        image.putpixel((70, 130), 0)
        data = dict(text=['90643030', '\u0e0a\u0e37\u0e48\u0e2d', 'ENGLISH', '\u0e04\u0e13\u0e30'],
                    left=[0, 70, 70, 70], top=[20, 20, 65, 125],
                    width=[50, 100, 200, 100], height=[20,20,20,20],
                    block_num=[1]*4, par_num=[1]*4, line_num=[1,1,2,3])
        with patch('ge66_script_evidence.audit.ocr',return_value=data):
            crop,meta=thai_title_image(image)
        self.assertIsNotNone(crop)
        self.assertLess(meta['thai_box'][3],65)

    def test_missing_upper_thai_title_never_promotes_footer_after_english(self):
        data=dict(text=['ENGLISH','คณะ'],left=[20,20],top=[20,90],width=[90,90],height=[20,20])
        with patch('ge66_script_evidence.audit.ocr',return_value=data):
            crop,meta=thai_title_image(Image.new('L',(200,150),'white'))
        self.assertIsNone(crop)
        self.assertEqual(meta['reason'],'no_image_recognized_thai_region')

    def test_empty_region_response_refuses_completion_and_retains_raw_response(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'region.png';p.write_bytes(b'image')
            identity={'image_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'prompt_sha256':hashlib.sha256(b'prompt').hexdigest(),'model':'model','options':{'temperature':0,'num_ctx':8192,'num_predict':1024}}
            p.with_suffix('.response.json').write_text(json.dumps({'region_request':identity,'message':{'content':''},'done':True}),encoding='utf-8')
            with self.assertRaises(RuntimeError):recognize_region(p,'prompt','model')
            self.assertTrue(p.with_suffix('.response.json').exists())

    def test_multiple_code_row_cannot_supply_thai_field_evidence(self):
        data=dict(text=['90642113','\u0e0a\u0e37\u0e48\u0e2d','90643021','\u0e2d\u0e37\u0e48\u0e19'],
                  left=[0,70,0,70],top=[20,20,90,90],width=[50]*4,height=[20]*4)
        with patch('ge66_script_evidence.audit.ocr',return_value=data):
            crop,meta=thai_title_image(Image.new('L',(300,140),'white'))
        self.assertIsNone(crop)
        self.assertEqual(meta['reason'],'multiple_course_rows')

    def test_isolated_thai_initial_mark_uses_two_literal_image_readings(self):
        image=Image.new('L',(200,100),'white');draw=ImageDraw.Draw(image)
        draw.rectangle((20,35,50,75),fill=0);draw.rectangle((22,20,45,25),fill=0)
        draw.rectangle((70,35,100,75),fill=0)
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',
                side_effect=['\u0e25\u0e37\u0e19 text','\u0e25\u0e35','\u0e25\u0e35']):
            text,meta=se.thai_initial_cluster_reading(image,Path(folder))
        self.assertEqual(text,'\u0e25\u0e35\u0e19 text')
        self.assertEqual(meta['raw_cluster_readings'],{'8':'\u0e25\u0e35','13':'\u0e25\u0e35'})

    def test_initial_cluster_cannot_change_a_different_base_letter(self):
        image=Image.new('L',(150,100),'white');draw=ImageDraw.Draw(image)
        draw.rectangle((20,35,50,75),fill=0);draw.rectangle((22,20,45,25),fill=0)
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',
                side_effect=['\u0e25\u0e37\u0e19','\u0e2a\u0e35','\u0e2a\u0e35']):
            text,meta=se.thai_initial_cluster_reading(image,Path(folder))
        self.assertIsNone(text)

    def test_isolated_punctuation_word_uses_typhoon_pixels_without_tesseract_fill(self):
        data=dict(text=['ONE,','WORD'],left=[10,100],top=[20,20],width=[60,70],height=[25,25])
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',return_value=data), patch(
                'ge66_script_evidence.recognize_region',side_effect=['ONE WORD','ONE ,']):
            text,meta=se.typhoon_word_text(Image.new('L',(200,80),'white'),Path(folder),'model')
        self.assertEqual(text,'ONE , WORD')
        self.assertFalse(meta['tesseract_text_used_as_fill'])
        self.assertEqual(meta['word_readings'][0]['raw_text'],'ONE ,')

    def test_isolated_word_cannot_inject_another_title(self):
        data=dict(text=['ONE,','WORD'],left=[10,100],top=[20,20],width=[60,70],height=[25,25])
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',return_value=data), patch(
                'ge66_script_evidence.recognize_region',side_effect=['ONE WORD','OTHER TITLE']):
            text,meta=se.typhoon_word_text(Image.new('L',(200,80),'white'),Path(folder),'model')
        self.assertIsNone(text)

    def mixed_read(self, raw, words, readings):
        data = dict(text=words, left=[20+50*i for i in range(len(words))],
                    top=[20]*len(words), width=[30]*len(words), height=[20]*len(words))
        with tempfile.TemporaryDirectory() as folder, patch(
                'ge66_script_evidence.audit.ocr', side_effect=[raw, data]+readings):
            return mixed_script_tesseract_reading(Image.new('L', (300, 80), 'white'), Path(folder))

    def test_isolated_latin_read_preserves_raw_case_and_thai(self):
        text, meta = self.mixed_read('\u0e0a\u0e37\u0e48\u0e2d !00', ['\u0e0a\u0e37\u0e48\u0e2d', '!00'], ['AbC', 'AbC'])
        self.assertEqual(text, '\u0e0a\u0e37\u0e48\u0e2d AbC')
        self.assertEqual(meta['engine_family'], 'tesseract')
        self.assertFalse(meta['reference_used'])

    def test_conflicting_latin_reads_cannot_replace_token(self):
        text, _ = self.mixed_read('\u0e0a\u0e37\u0e48\u0e2d !00', ['!00'], ['ABC', 'AbC'])
        self.assertIsNone(text)

    def test_repeated_or_substring_anchors_are_refused(self):
        for raw, words in [('\u0e0a\u0e37\u0e48\u0e2d 100 100', ['100','100']),
                           ('\u0e0a\u0e37\u0e48\u0e2d X100Y', ['100'])]:
            text, meta = self.mixed_read(raw, words, [])
            self.assertIsNone(text)
            self.assertEqual(meta['readings'], [])

    def test_word_read_cannot_inject_multiple_words(self):
        text, _ = self.mixed_read('\u0e0a\u0e37\u0e48\u0e2d !00', ['!00'], ['A B','A B'])
        self.assertIsNone(text)

    def test_overlapping_word_anchors_cannot_corrupt_a_title(self):
        text, meta = self.mixed_read('\u0e0a\u0e37\u0e48\u0e2d !00', ['!00','00'], ['ABC','ABC','XYZ','XYZ'])
        self.assertIsNone(text)
        self.assertEqual(meta['reason'], 'overlapping_text_anchors')

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

    def test_wrapped_raised_word_uses_one_peer_with_consistent_title_height(self):
        data=self.data();data['line_num']=[1,1,2,2]
        with patch('ge66_script_evidence.audit.ocr',side_effect=[data,'42','nd']):
            text,meta=raised_english_text(self.raised_image())
        self.assertEqual(text,'A B 42nd C')
        self.assertEqual(meta['readings'][0]['parts'][1]['text'],'nd')

    def test_one_peer_with_conflicting_other_line_height_is_refused(self):
        data=self.data();data['line_num']=[1,1,2,2];data['height'][-1]=9
        with patch('ge66_script_evidence.audit.ocr',return_value=data):
            text,_=raised_english_text(self.raised_image())
        self.assertIsNone(text)

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

    def test_thai_crop_excludes_adjacent_code_and_credit_columns(self):
        data = dict(text=['90642058', '\u0e04\u0e27\u0e32\u0e21', '3', '(3-0-6)'],
                    left=[10, 40, 180, 195], top=[15, 10, 15, 15],
                    width=[25, 70, 8, 35], height=[20, 30, 20, 20],
                    block_num=[1]*4, par_num=[1]*4, line_num=[1]*4)
        image = Image.new('L', (240, 90), 'white')
        draw = ImageDraw.Draw(image)
        draw.line((30, 0, 30, 89), fill='black', width=4)
        draw.line((170, 0, 170, 89), fill='black', width=4)
        with patch('ge66_script_evidence.audit.ocr', return_value=data):
            crop, meta = thai_title_image(image)
        self.assertIsNotNone(crop)
        self.assertGreaterEqual(meta['thai_box'][0], 32)
        self.assertLessEqual(meta['thai_box'][2], 170)

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


class ThaiSupplementTests(unittest.TestCase):
    def test_half_raw_line_requires_literal_segmentation_agreement(self):
        data=dict(text=['ชื่อ'],block_num=[1],par_num=[1],line_num=[1])
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',side_effect=[data,'ชื่อจริง','ชื่อจริง']):
            text,meta=se.thai_raw_line_probe(Image.new('L',(200,80),'white'),Path(folder))
            self.assertEqual(text,'ชื่อจริง')
            self.assertEqual(meta['raw_readings'],{'8':'ชื่อจริง','13':'ชื่อจริง'})
            self.assertEqual(Image.open(Path(folder)/'thai-half.png').size,(100,40))

    def test_wrapped_title_refuses_single_word_or_raw_line_probe(self):
        data=dict(text=['ชื่อ','ชื่อ'],block_num=[1,1],par_num=[1,1],line_num=[1,2])
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',return_value=data) as read:
            text,meta=se.thai_raw_line_probe(Image.new('L',(200,80),'white'),Path(folder))
            self.assertIsNone(text)
            self.assertEqual(read.call_count,1)

    def test_probe_keeps_unsupported_leading_punctuation_raw_without_voting(self):
        data=dict(text=['ชื่อ'],block_num=[1],par_num=[1],line_num=[1])
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',side_effect=[data,'. ชื่อ','. ชื่อ']):
            text,meta=se.thai_raw_line_probe(Image.new('L',(200,80),'white'),Path(folder))
            self.assertIsNone(text)
            self.assertEqual(meta['raw_readings']['8'],'. ชื่อ')

    def test_half_typhoon_reading_remains_literal_not_tesseract_fill(self):
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.recognize_region',return_value='ชื่อ XYZ') as read:
            text,meta=se.thai_half_literal_probe(Image.new('L',(200,80),'white'),Path(folder),'model')
            self.assertEqual(text,'ชื่อ XYZ')
            self.assertEqual(Image.open(read.call_args.args[0]).size,(100,40))
            self.assertFalse(meta['reference_used'])


class ThaiTerminalTests(unittest.TestCase):
    def fixture(self):
        image=Image.new('L',(140,70),'white');ImageDraw.Draw(image).rectangle((90,20,110,45),fill='black')
        return image

    def data(self):
        return dict(text=['ชื่อต่าง'],left=[50],top=[20],width=[60],height=[25],block_num=[1],par_num=[1],line_num=[1])

    def test_terminal_glyph_uses_typhoon_own_prefix_and_raw_character(self):
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',return_value=self.data()), patch('ge66_script_evidence.recognize_region',side_effect=['ชื่อป','บ']):
            text,meta=se.thai_terminal_literal_probe(self.fixture(),Path(folder),'model')
            self.assertEqual(text,'ชื่อบ')
            self.assertEqual(meta['raw_whole_text'],'ชื่อป')
            self.assertEqual(meta['raw_cluster_text'],'บ')
            self.assertFalse(meta['tesseract_text_used_as_fill'])

    def test_terminal_probe_refuses_a_whole_word_response(self):
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',return_value=self.data()), patch('ge66_script_evidence.recognize_region',side_effect=['ชื่อป','หลายตัว']):
            text,meta=se.thai_terminal_literal_probe(self.fixture(),Path(folder),'model')
            self.assertIsNone(text)
            self.assertEqual(meta['raw_cluster_text'],'หลายตัว')

    def test_wrapped_or_latin_terminal_does_not_supply_a_thai_glyph(self):
        data=self.data();data['text']=['TITLE']
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',return_value=data), patch('ge66_script_evidence.recognize_region') as read:
            text,meta=se.thai_terminal_literal_probe(self.fixture(),Path(folder),'model')
            self.assertIsNone(text);read.assert_not_called()


class EnglishSplitTests(unittest.TestCase):
    def fixture(self):
        image=Image.new('L',(160,60),'white');draw=ImageDraw.Draw(image)
        for x in (20,40,60,90,110,130):draw.rectangle((x,20,x+8,40),fill='black')
        return image

    def test_word_margin_cannot_include_previous_word_pixels(self):
        data=dict(text=['FOR','RIGHT'],left=[5,48],top=[20,20],width=[40,50],height=[20,20])
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.audit.ocr',return_value=data), patch('ge66_script_evidence.recognize_region',side_effect=['FOR WRONG','RIGHT']):
            text,meta=se.typhoon_word_text(Image.new('L',(120,70),'white'),Path(folder),'model')
            self.assertEqual(text,'FOR RIGHT')
            self.assertGreaterEqual(meta['word_readings'][0]['box'][0],45)

    def test_split_word_preserves_both_literal_parts_without_dictionary_fill(self):
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.recognize_region',side_effect=['ABc','Def']):
            text,meta=se.typhoon_split_word(self.fixture(),Path(folder),'model')
            self.assertEqual(text,'ABcDef')
            self.assertEqual(meta['raw_parts'],['ABc','Def'])
            self.assertFalse(meta['tesseract_text_used_as_fill'])

    def test_split_word_refuses_multiword_response(self):
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.recognize_region',return_value='OTHER TITLE'):
            text,meta=se.typhoon_split_word(self.fixture(),Path(folder),'model')
            self.assertIsNone(text)

    def test_split_word_refuses_a_solid_unseparated_glyph(self):
        image=Image.new('L',(160,60),'white');ImageDraw.Draw(image).rectangle((20,20,140,40),fill='black')
        with tempfile.TemporaryDirectory() as folder, patch('ge66_script_evidence.recognize_region') as read:
            text,meta=se.typhoon_split_word(image,Path(folder),'model')
            self.assertIsNone(text);read.assert_not_called()


class MissingWholeWordTests(unittest.TestCase):
    def data(self):
        return dict(text=['TESSA,','TESSB','TESSC','TESSD'],left=[20,90,160,230],top=[20]*4,width=[50]*4,height=[20]*4)

    def test_missing_whole_word_re_reads_every_box_from_typhoon_no_tesseract_fill(self):
        with tempfile.TemporaryDirectory() as folder,patch('ge66_script_evidence.audit.ocr',return_value=self.data()),patch('ge66_script_evidence.recognize_region',side_effect=['OWN FIRST LAST','OWN,','FIRST','MIDDLE','LAST']):
            text,meta=se.typhoon_word_text(Image.new('L',(320,70),'white'),Path(folder),'model')
        self.assertEqual(text,'OWN, FIRST MIDDLE LAST')
        self.assertEqual(len(meta['word_readings']),4)
        self.assertFalse(meta['tesseract_text_used_as_fill'])
        self.assertEqual(meta['alignment_policy'],'all_image_words')

    def test_unaligned_word_retry_still_refuses_multiword_injection(self):
        with tempfile.TemporaryDirectory() as folder,patch('ge66_script_evidence.audit.ocr',return_value=self.data()),patch('ge66_script_evidence.recognize_region',side_effect=['OWN FIRST LAST','OTHER TITLE']):
            text,meta=se.typhoon_word_text(Image.new('L',(320,70),'white'),Path(folder),'model')
        self.assertIsNone(text)
        self.assertEqual(meta['reason'],'invalid_single_word_reading')

    def test_unaligned_whole_title_with_too_many_boxes_is_not_unbounded_retry(self):
        data=self.data();data={k:(v*3) for k,v in data.items()}
        with tempfile.TemporaryDirectory() as folder,patch('ge66_script_evidence.audit.ocr',return_value=data),patch('ge66_script_evidence.recognize_region',return_value='OWN FIRST LAST') as read:
            text,meta=se.typhoon_word_text(Image.new('L',(320,70),'white'),Path(folder),'model')
        self.assertIsNone(text);self.assertEqual(read.call_count,1)
        self.assertEqual(meta['reason'],'too_many_unaligned_image_words')
