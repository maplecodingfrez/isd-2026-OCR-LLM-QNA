"""Checks that selection preserves observed text and distinctions, without a GT API."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ge66_select_candidate import select
import ge66_select_candidate as selection
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
        self.assertEqual(result, [])
        self.assertEqual(len(review), 1)
        self.assertEqual(review[0]['unresolved_fields'], ['name_th'])

    def test_thai_region_agreement_beats_engine_preference(self):
        row = dict(code='90642102', page=19, engine='tesseract', variant='whole_page',
                   name_th='observed Thai title', name_en='TITLE', credits='3 (3-0-6)')
        wrong = {**row, 'engine': 'typhoon', 'variant': 'row_crop', 'name_th': 'conflicting title'}
        partial = dict(code=row['code'], page=19, engine='typhoon', variant='thai_line',
                       name_th=row['name_th'])
        result, review = select({row['code']: [row, wrong, partial]})
        self.assertEqual(result[0]['name_th'], row['name_th'])
        self.assertEqual(review[0]['evidence']['name_th']['engines'], ['tesseract', 'typhoon'])
        self.assertEqual(review[0]['evidence']['credits']['total'], 2)

    def test_single_engine_stays_reviewable(self):
        rows = [dict(code='90642102', page=19, engine='typhoon', variant='row_crop',
                     name_th='นักสื่อสารผ่านยูทูป', name_en='YOUTUBER', credits='3 (3-0-6)')]
        result, review = select({'90642102': rows})
        self.assertEqual(result[0]['name_th'], 'นักสื่อสารผ่านยูทูป')
        self.assertEqual(review[0]['evidence']['name_th']['engines'], ['typhoon'])

    def test_unsupported_crop_does_not_win_a_tie(self):
        original = dict(code='90644054', page=29, engine='tesseract', variant='whole_page',
                        name_th='Thai title', name_en='COMPLETE ENGLISH TITLE', credits='3 (3-0-6)')
        cropped = {**original, 'variant': 'row_crop', 'name_en': 'CLIPPED GARBLED TITLE'}
        result, review = select({'90644054': [original, cropped]})
        self.assertEqual(result, [])
        self.assertEqual(review[0]['unresolved_fields'], ['name_en'])
        self.assertEqual(len(review), 1)

    def test_clipped_majority_is_rejected(self):
        original = dict(code='90644054', page=29, engine='tesseract', variant='whole_page',
                        name_th='Thai title', name_en='COMPLETE TITLE', credits='3 (3-0-6)')
        bad = {**original, 'variant': 'row_crop', 'name_en': 'BROKEN', 'crop_quality': {'clipped': True}}
        result, review = select({'90644054': [original, bad, {**bad, 'engine': 'typhoon'}]})
        self.assertEqual(result[0]['name_en'], original['name_en'])
        self.assertEqual(review[0]['rejected_clipped_observations'], 2)

    def test_all_clipped_observations_need_review_without_a_candidate(self):
        row = dict(code='90644054', page=29, engine='typhoon', variant='row_crop',
                   name_th='Thai title', name_en='BROKEN', credits='3 (3-0-6)', crop_quality={'clipped': True})
        result, review = select({'90644054': [row]})
        self.assertEqual(result, [])
        self.assertEqual(review[0]['reason'], 'all_observations_clipped')

    def test_repeated_engine_cannot_outvote_cross_engine_agreement(self):
        good = dict(code='90642102', page=19, engine='typhoon', variant='chunk_crop',
                    name_th='Thai title', name_en='TITLE', credits='3 (3-0-6)')
        partner = {**good, 'engine': 'tesseract', 'variant': 'english_line'}
        bad = {**partner, 'variant': 'whole_page', 'name_en': 'T1TLE'}
        result, review = select({'90642102': [good, partner]+[bad]*20})
        self.assertEqual(result[0]['name_en'], 'TITLE')
        self.assertEqual(len(review), 1)

    def test_two_competing_cross_engine_values_remain_unresolved(self):
        row = dict(code='90642102', page=19, engine='typhoon', variant='chunk_crop',
                   name_th='Thai title', name_en='TITLE', credits='3 (3-0-6)')
        rows=[row,{**row,'engine':'tesseract'},{**row,'name_en':'T1TLE'},
              {**row,'engine':'tesseract','name_en':'T1TLE'}]
        result, review=select({'90642102':rows})
        self.assertEqual(result,[])
        self.assertEqual(review[0]['unresolved_fields'],['name_en'])

    def test_agreed_truncated_title_does_not_beat_a_longer_observed_title(self):
        short = dict(code='90642058', page=131, engine='tesseract', variant='whole_page',
                     name_th='ประชาชน', name_en='TITLE', credits='3 (3-0-6)')
        short_peer = {**short, 'engine':'typhoon', 'variant':'chunk_crop'}
        full = {**short, 'engine':'typhoon', 'variant':'thai_line',
                'name_th':'ความเข้าใจเกี่ยวกับนโยบายสุขภาพและสวัสดิภาพของประชาชน'}
        result, review = select({'90642058':[short, short_peer, full]})
        self.assertEqual(result, [])
        self.assertEqual(review[0]['unresolved_fields'], ['name_th'])

    def test_english_substring_conflict_remains_unresolved(self):
        short = dict(code='90643011', page=139, engine='tesseract', variant='whole_page',
                     name_th='Thai title', name_en='TITLE', credits='3 (3-0-6)')
        peer = {**short, 'engine': 'typhoon'}
        full = {**peer, 'variant': 'english_line', 'name_en': 'COMPLETE TITLE'}
        result, review = select({short['code']: [short, peer, full]})
        self.assertEqual(result, [])
        self.assertEqual(review[0]['unresolved_fields'], ['name_en'])

    def test_clipped_long_title_does_not_block_eligible_agreement(self):
        short = dict(code='90643011', page=139, engine='tesseract', variant='whole_page',
                     name_th='Thai title', name_en='TITLE', credits='3 (3-0-6)')
        peer = {**short, 'engine': 'typhoon'}
        clipped = {**peer, 'name_en': 'COMPLETE TITLE', 'crop_quality': {'clipped': True}}
        result, review = select({short['code']: [short, peer, clipped]})
        self.assertEqual(result[0]['name_en'], 'TITLE')
        self.assertEqual(review[0]['rejected_clipped_observations'], 1)

    def test_bounded_title_fields_do_not_vote_with_footer_contaminated_row(self):
        whole=dict(code='90643006',page=153,engine='tesseract',variant='row',name_th='Thai',
                   name_en='COMPLETE TITLE footer',credits='3 (3-0-6)')
        th={**whole,'engine':'typhoon','name_en':'COMPLETE TITLE'}
        narrow=[dict(code=whole['code'],page=153,engine=e,variant='english_line',
                     name_en='COMPLETE TITLE',field_scope='bounded_title') for e in ('tesseract','typhoon')]
        records,review=select({whole['code']:[whole,th]+narrow})
        self.assertEqual(records[0]['name_en'],'COMPLETE TITLE')
        self.assertEqual(review[0]['evidence']['name_en']['discarded_unbounded_observations'],2)

    def test_single_family_bounded_title_cannot_fall_back_to_broad_agreement(self):
        whole=dict(code='90643006',page=153,engine='tesseract',variant='row',name_th='Thai',
                   name_en='OTHER ROW',credits='3 (3-0-6)')
        narrow=dict(code=whole['code'],page=153,engine='tesseract',variant='english_line',
                    name_en='ACTUAL TITLE',field_scope='bounded_title')
        records,review=select({whole['code']:[whole,{**whole,'engine':'typhoon'},narrow]})
        self.assertEqual(records,[])
        self.assertIn('name_en',review[0]['unresolved_fields'])

    def test_fresh_occurrence_selection_requires_a_bounded_code_position(self):
        row=dict(code='90642113',page=151,engine='tesseract',variant='whole',name_th='Thai',
                 name_en='TITLE',credits='3 (3-0-6)')
        records,review=selection.select_occurrences({'90642113':[row,{**row,'engine':'typhoon'}]},require_scoped=True)
        self.assertEqual(records,[])
        self.assertEqual(review[0]['reason'],'no_bounded_code_occurrence')

    def test_page_occurrences_keep_conflicting_printed_titles_separate(self):
        rows=[]
        for page,name in [(150,'First printed title'),(153,'Other printed title')]:
            for engine in ('tesseract','typhoon'):
                rows.append(dict(code='90643006',page=page,engine=engine,variant='row',
                                 name_th=name,name_en='TITLE',credits='3 (3-0-6)'))
        records,review=selection.select_occurrences({'90643006':rows})
        self.assertEqual([(r['page'],r['name_th']) for r in records],[(150,'First printed title'),(153,'Other printed title')])
        catalog,conflicts=selection.catalog_from_occurrences(records)
        self.assertEqual(catalog,[])
        self.assertEqual(conflicts[0]['reason'],'printed_title_conflict')

    def test_occurrence_field_cannot_vote_from_another_row_on_same_page(self):
        rows=[]
        for ident,name in [('150:100','First'),('150:300','Other')]:
            for engine in ('tesseract','typhoon'):
                rows.append(dict(code='90643006',page=150,occurrence_id=ident,engine=engine,
                                 variant='row',name_th=name,name_en='TITLE',credits='3 (3-0-6)'))
        records,_=selection.select_occurrences({'90643006':rows})
        self.assertEqual(len(records),2)
        self.assertEqual({r['name_th'] for r in records},{'First','Other'})

    def test_verified_occurrence_does_not_mix_unbounded_baseline_title(self):
        row=dict(code='90642113',page=151,occurrence_id='151:100',engine='tesseract',variant='row',
                 name_th='Thai',name_en='ROW TITLE',credits='3 (3-0-6)')
        broad={**row,'engine':'typhoon','name_en':'OTHER ROW'};broad.pop('occurrence_id')
        records,_=selection.select_occurrences({'90642113':[row,{**row,'engine':'typhoon'},broad]})
        self.assertEqual(records[0]['name_en'],'ROW TITLE')

    def test_complete_cross_engine_title_can_beat_single_engine_fragment(self):
        full = dict(code='90643025', page=140, engine='tesseract', variant='title_cell',
                    name_th='Thai title with acronym', name_en='COMPLETE TITLE', credits='3 (3-0-6)')
        peer = {**full, 'engine': 'typhoon'}
        fragment = {**peer, 'variant': 'chunk_crop', 'name_th': 'Thai title'}
        result, review = select({full['code']: [full, peer, fragment]})
        self.assertEqual(result[0]['name_th'], full['name_th'])
        self.assertEqual(review[0]['evidence']['name_th']['engines'], ['tesseract', 'typhoon'])

    def test_english_only_evidence_does_not_vote_other_fields(self):
        full=dict(code='90642102',page=19,engine='typhoon',variant='chunk_crop',
                  name_th='Thai title',name_en='TITLE',credits='3 (3-0-6)')
        partial=dict(code='90642102',page=19,engine='tesseract',variant='english_line',name_en='TITLE')
        result,review=select({'90642102':[full,partial]})
        self.assertEqual(result[0]['name_th'],'Thai title')
        self.assertEqual(review[0]['evidence']['name_th']['support_count'],1)
        self.assertEqual(review[0]['evidence']['name_th']['total'],1)
        self.assertEqual(review[0]['evidence']['name_en']['engines'],['tesseract','typhoon'])


if __name__ == '__main__':
    unittest.main()
