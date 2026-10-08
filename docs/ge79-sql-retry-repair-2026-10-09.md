# Page79 English title and exhausted SQL retry repair — 2026-10-09

The user requested fixing the two limitations left by e1c91b0. Work stays in the dev/tests worktree; the five promoted GE66 databases and both BIT databases are not modified.

## Root causes and changes

- Page79 course90642125: the bounded English title has approximately22-pixel-high glyphs. Tesseract reads an invented terminal period; the retained image and independent Typhoon read have no period. Removing only blank margins did not help. Scaling the retained image2x makes Tesseract PSM6/7 read the literal title correctly.
- English regions now bound every nonwhite pixel (including tiny punctuation), upscale2x and add20-pixel white padding before either engine reads. Wrapped lines and original source crop metadata remain. No title string edits, dictionary rules, reference fills, engine-family changes or weaker conflict gates.
- The exhausted second SQL attempt returned the same NOT_FOUND text as a successful empty query. It now explains that the question could not be converted for searching and asks the user to rephrase, retaining the actual error. Valid empty results still return NOT_FOUND with error=None; second-attempt recovery is tested. No retries, SQL guards, model configuration or database schema are changed.

## Verification

The observed backend regression fails before the fix and passes after it. Broader backend suite:1045 passed,3 skipped, no failures. Additional retry boundary tests require one call for a valid empty query, two for recovered failure, and exactly two with no fabricated rows/answer/citations for exhausted failure.

Image tests fail before the new helper and pass afterward. They include the actual retained title image, isolated punctuation pixels, wrapped lines and blank regions. Related OCR/migration suite:131 passed plus7 subtests. Tesseract is real for the image regression; slow model calls are mocked only in unit tests. Current Pillow and pytest documentation were consulted via Context7.

The original frozen page79 score2/3 and its raw OCR/snapshot hashes remain preserved. A separate page79 development run and final-policy untouched page80 evaluation follow recognition completion before opening the reference. Results and exact hashes are recorded in the companion JSON when complete. References are the PDF Text Layer, not independent human ground truth; small-page outcomes do not certify arbitrary-document accuracy.

Existing DB/catalog/provenance/Gold/source file hashes are captured under ignored `outputs/ge79_sql_test_repair_20261009/protected-hashes.json`. No data promotion is needed for these code fixes: full GE66303-course OCR data already remains in the current dev/tests DBs.
