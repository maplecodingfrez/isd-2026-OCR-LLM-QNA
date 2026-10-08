import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ge66_english_evidence import english_title_image

class EnglishEvidenceTests(unittest.TestCase):
    def image(self, ink=True):
        return Image.frombytes('L',(100,120),bytes(0 if ink and 30<=x<70 and
            (50<=y<60 or 80<=y<90) else 255 for y in range(120) for x in range(100)))

    def test_wrapped_english_keeps_both_lines(self):
        data={'text':['\u0e0a\u0e37\u0e48\u0e2d'], 'top':[20], 'height':[20]}
        with patch('ge66_english_evidence.audit.ocr',return_value=data):
            image, meta=english_title_image(self.image())
        self.assertIsNotNone(image)
        self.assertLessEqual(meta['english_box'][1],50)
        self.assertGreaterEqual(meta['english_box'][3],90)
        self.assertFalse(meta['reference_used'])

    def test_no_thai_boundary_does_not_guess(self):
        with patch('ge66_english_evidence.audit.ocr',return_value={'text':['TITLE'],'top':[20],'height':[20]}):
            image,meta=english_title_image(self.image())
        self.assertIsNone(image)
        self.assertEqual(meta['reason'],'no_image_recognized_thai_boundary')

    def test_blank_region_is_not_evidence(self):
        with patch('ge66_english_evidence.audit.ocr',return_value={'text':['\u0e0a\u0e37\u0e48\u0e2d'],'top':[20],'height':[20]}):
            image,meta=english_title_image(self.image(False))
        self.assertIsNone(image)
        self.assertEqual(meta['reason'],'empty_english_region')

    def test_table_cell_keeps_rightmost_english_and_excludes_vertical_rules(self):
        image = Image.new('L', (400, 140), 255)
        for x in (60, 340):
            for y in range(140): image.putpixel((x, y), 0)
        for y in range(60, 75):
            for x in range(70, 334): image.putpixel((x, y), 0)
        data = {'text': ['\u0e0a\u0e37\u0e48\u0e2d'], 'top': [20], 'height': [20]}
        with patch('ge66_english_evidence.audit.ocr', return_value=data):
            crop, meta = english_title_image(image)
        self.assertEqual(meta.get('table_cell_box'), [61, 0, 340, 140])
        self.assertGreater(crop.width, 300)

    def test_plain_row_preserves_english_beyond_old_fixed_columns(self):
        image = Image.new('L', (400, 140), 255)
        for y in range(60, 75):
            for x in range(60, 390): image.putpixel((x, y), 0)
        data = {'text': ['\u0e0a\u0e37\u0e48\u0e2d'], 'top': [20], 'height': [20]}
        with patch('ge66_english_evidence.audit.ocr', return_value=data):
            crop, meta = english_title_image(image)
        self.assertEqual(meta['english_box'][2], 400)
        self.assertEqual(crop.getpixel((400, 28)), 0)

    def test_multiple_course_codes_refuse_english_field_crop(self):
        data={'text':['90642113','\u0e0a\u0e37\u0e48\u0e2d','90643021','\u0e2d\u0e37\u0e48\u0e19'],
              'top':[20,20,90,90],'height':[20]*4}
        with patch('ge66_english_evidence.audit.ocr',return_value=data):
            crop,meta=english_title_image(Image.new('L',(300,140),'white'))
        self.assertIsNone(crop)
        self.assertEqual(meta['reason'],'multiple_course_rows')

    def test_faculty_footer_does_not_hide_initial_english_title(self):
        image=Image.new('L',(300,180),'white')
        for y in range(60,75):
            for x in range(60,250):image.putpixel((x,y),0)
        data={'text':['\u0e0a\u0e37\u0e48\u0e2d','ENGLISH','\u0e04\u0e13\u0e30'],
              'top':[20,60,125],'height':[20,15,20]}
        with patch('ge66_english_evidence.audit.ocr',return_value=data):
            crop,meta=english_title_image(image)
        self.assertIsNotNone(crop)
        self.assertLess(meta['english_box'][3],125)

    def test_footer_upper_marks_above_ocr_box_do_not_enter_english_crop(self):
        image=Image.new('L',(300,180),'white')
        for lo,hi in [(60,75),(119,124)]:
            for y in range(lo,hi):
                for x in range(60,250):image.putpixel((x,y),0)
        data={'text':['\u0e0a\u0e37\u0e48\u0e2d','ENGLISH','\u0e04\u0e13\u0e30'],
              'top':[20,60,125],'height':[20,15,20]}
        with patch('ge66_english_evidence.audit.ocr',return_value=data):
            crop,meta=english_title_image(image)
        self.assertLess(meta['english_box'][3],100)

    def test_wrapped_english_word_lines_remain_in_bounded_region(self):
        image=Image.new('L',(300,200),'white')
        for lo,hi in [(60,75),(90,105),(155,175)]:
            for y in range(lo,hi):
                for x in range(60,250):image.putpixel((x,y),0)
        data={'text':['\u0e0a\u0e37\u0e48\u0e2d','FIRST','SECOND','footerArtifact','\u0e04\u0e13\u0e30'],
              'top':[20,60,90,155,155],'height':[20,15,15,20,20]}
        with patch('ge66_english_evidence.audit.ocr',return_value=data):
            crop,meta=english_title_image(image)
        self.assertGreaterEqual(meta['english_box'][3],105)
        self.assertLess(meta['english_box'][3],130)
