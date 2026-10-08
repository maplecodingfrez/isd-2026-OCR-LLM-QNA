import sys
from pathlib import Path
import unittest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ge66_crop_quality import safe_row_crop, table_row_crop, table_title_cell
import ge66_crop_quality as quality

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

    def test_adjacent_rules_keep_wrapped_title_lines_in_the_same_row(self):
        image = Image.new('L', (300, 320), 255)
        for y in (30, 180, 290):
            for x in range(15, 286):
                image.putpixel((x, y), 0)
        for x in (30, 100, 270):
            for y in range(30, 291):
                image.putpixel((x, y), 0)
        for y in (60, 95, 130):
            for x in range(120, 220):
                image.putpixel((x, y), 0)
        crop, quality = table_row_crop(image, 70, 28, 280)
        self.assertFalse(quality['clipped'])
        self.assertEqual(quality['crop_method'], 'adjacent_horizontal_rules')
        self.assertGreaterEqual(quality['box'][1], 30)
        self.assertLessEqual(quality['box'][3], 180)
        self.assertEqual(crop.getpixel((120-28, 130-quality['box'][1])), 0)
        self.assertEqual(crop.getpixel((120-28, 95-quality['box'][1])), 0)

    def test_missing_row_rule_uses_flagged_fallback(self):
        _, quality = table_row_crop(self.image(), 70, 10, 90)
        self.assertTrue(quality['clipped'])

    def test_title_cell_ignores_blank_margins_and_keeps_all_glyph_pixels(self):
        image = Image.new('L', (400, 140), 255)
        for x in (60, 340):
            for y in range(20, 120): image.putpixel((x, y), 0)
        image.putpixel((333, 90), 0)
        cell, meta = table_title_cell(image)
        self.assertEqual(meta['table_cell_box'], [61, 0, 340, 140])
        self.assertEqual(cell.getpixel((333-61, 90)), 0)

    def test_no_table_rules_does_not_invent_cell(self):
        cell, meta = table_title_cell(self.image())
        self.assertIsNone(cell)
        self.assertEqual(meta['reason'], 'no_unique_wide_title_cell')

    def test_two_wide_cells_remain_ambiguous(self):
        image = Image.new('L', (500, 140), 255)
        for x in (10, 250, 490):
            for y in range(140): image.putpixel((x, y), 0)
        cell, _ = table_title_cell(image)
        self.assertIsNone(cell)

    def test_image_code_positions_set_left_bound_on_wide_layouts(self):
        anchors = [{'left': 180, 'height': 20}, {'left': 160, 'height': 20}]
        self.assertEqual(quality.code_anchor_left(anchors), 144)
        self.assertLess(quality.code_anchor_left(anchors), min(a['left'] for a in anchors))

    def test_code_left_bound_clamps_to_image_edge(self):
        self.assertEqual(quality.code_anchor_left([{'left': 5, 'height': 20}]), 0)

if __name__ == '__main__':
    unittest.main()
