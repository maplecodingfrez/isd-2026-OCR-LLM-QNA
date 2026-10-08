"""Repeated content is distinct unless it occupies the same region."""
import pytest
from ocr_system.schemas import OCRLine
from ocr_system.engines.ensemble_engine import EnsembleOCREngine

@pytest.fixture
def merger(): return EnsembleOCREngine.__new__(EnsembleOCREngine)

def line(text='3',y=10,confidence=.9,page=1,engine='paddle'):
    return OCRLine(text=text,confidence=confidence,page=page,engine=engine,
        box=[[0,y],[20,y],[20,y+10],[0,y+10]])

def test_repeated_credits_at_distinct_positions_survive(merger):
    rows=merger.merge([line(y=10),line(y=100)])
    assert len(rows)==2
    assert [r.box[0][1] for r in rows]==[10,100]

def test_cross_engine_same_region_uses_strongest_confidence(merger):
    weak=line(confidence=.7); strong=line(y=11,confidence=.95,engine='tesseract')
    assert merger.merge([weak],[strong])==[strong]

def test_same_text_on_different_pages_never_merges(merger):
    assert len(merger.merge([line(page=1),line(page=2)]))==2

def test_equal_confidence_keeps_first_detection(merger):
    first=line(); second=line(engine='tesseract')
    assert merger.merge([first],[second])[0] is first

def test_missing_confidence_loses_to_real_score(merger):
    first=line(confidence=None); second=line(confidence=.2)
    assert merger.merge([first],[second])[0] is second

@pytest.mark.parametrize('box',[
    None,[],[[0,0]],[[0,0],[0,10]],[[0,float('nan')],[10,10]],
    [[0,0],[10,float('inf')]],[['bad',0],[10,10]],[[0],[10,10]],
])
def test_uncertain_geometry_does_not_discard_content(merger,box):
    first=line(); second=line()
    first.box=box;second.box=box
    assert len(merger.merge([first],[second]))==2

def test_overlap_with_different_text_is_distinct(merger):
    assert len(merger.merge([line('3')],[line('4')]))==2

class AmbiguousTruthBox(list):
    def __bool__(self): raise ValueError('array truth value is ambiguous')

def test_geometry_does_not_truth_test_polygon(merger):
    first=line(); second=line(confidence=.95)
    first.box=AmbiguousTruthBox(first.box)
    second.box=AmbiguousTruthBox(second.box)
    assert merger.merge([first],[second])==[second]

def test_repeated_course_rows_keep_all_credit_cells(merger):
    primary=[line('3',y=i*30) for i in range(6)]
    secondary=[line('3',y=i*30+1,confidence=.95,engine='tesseract') for i in range(6)]
    merged=merger.merge(primary,secondary)
    assert len(merged)==6
    assert [r.box[0][1] for r in merged]==[1,31,61,91,121,151]
