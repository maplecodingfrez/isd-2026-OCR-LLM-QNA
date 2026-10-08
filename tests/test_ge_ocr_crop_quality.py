import sys
from pathlib import Path
import unittest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ge66_crop_quality import safe_row_crop

class CropTests(unittest.TestCase):
    def image(self):
        return Image.frombytes('L', (100, 160), bytes(
            0 if 30 <= x < 80 and (20 <= y < 40 or 70 <= y < 95) else 255
            for y in range(160) for x in range(100)))

    def test_bottom_cut_expands_until_glyphs_complete(self):
        crop, quality = safe_row_crop(self.image(), (0, 10, 100, 85))
        self.assertFalse(quality['clipped'])
        self.assertGreaterEqual(quality['box'][3], 95)
        self.assertEqual(crop.getpixel((40, 94-quality['box'][1])), 0)

    def test_top_cut_expands_before_upper_marks(self):
        _, quality = safe_row_crop(self.image(), (0, 30, 100, 110))
        self.assertFalse(quality['clipped'])
        self.assertLessEqual(quality['box'][1], 20)

    def test_insufficient_safe_expansion_remains_flagged(self):
        _, quality = safe_row_crop(self.image(), (0, 10, 100, 85), max_expand=2)
        self.assertTrue(quality['clipped'])

    def test_table_rules_do_not_force_expansion_or_remove_pixels(self):
        image = Image.frombytes('L', (100, 300), bytes(
            0 if 90 <= x < 93 or (30 <= x < 65 and 100 <= y < 130) else 255
            for y in range(300) for x in range(100)))
        crop, quality = safe_row_crop(image, (0, 90, 100, 140))
        self.assertFalse(quality['clipped'])
        self.assertGreaterEqual(quality['box'][1], 80)
        self.assertLessEqual(quality['box'][3], 150)
        self.assertEqual(crop.getpixel((91, 0)), 0)

    def test_glyph_cut_remains_flagged_beside_a_table_rule(self):
        image = Image.frombytes('L', (100, 300), bytes(
            0 if 90 <= x < 93 or (30 <= x < 65 and 100 <= y < 190) else 255
            for y in range(300) for x in range(100)))
        _, quality = safe_row_crop(image, (0, 90, 100, 150), max_expand=60)
        self.assertFalse(quality['clipped'])
        _, quality = safe_row_crop(image, (0, 90, 100, 150), max_expand=10)
        self.assertTrue(quality['clipped'])

if __name__ == '__main__':
    unittest.main()
