# Independent OCR region evidence - 2026-10-08

The three remaining development disagreements now resolve from image OCR: Thai 90642062/90642091 and English 90643037. No expected spelling, course-code lookup, case folding or reference fill is used. Selection still counts distinct engine families and requires unique cross-engine agreement for conflicting names.

## Changes

- Thai extraction uses word boxes across the full row instead of fixed horizontal ratios that clipped leading vowels on native images. It retains all words on Thai-title lines between image-recognized code and credit columns, including Latin acronyms/numbers, and excludes the separate English-title line.
- Thai retries render native 600-DPI rows and read native/half-size regions with `tha+eng`. PSM6 is retained; PSM7 is used only for one image-recognized Thai line. All variants remain one Tesseract engine family. Raw images/readings remain retained, and native-page PDF/page/DPI/image provenance is checked.
- Typhoon reads a whole English region plus its raised-glyph word images under a generic literal-transcription prompt. Unchanged tokens must align with image OCR geometry. Replacements come entirely from Typhoon raw word readings; Tesseract text is never inserted into a Typhoon observation. Case stays raw; mismatched token counts/context or malformed word reads are refused.
- `ge66_targeted_retry.py` integrates the new field-only evidence. Existing crop/cache guards, observations and strict agreement policy remain retained. Production OCR/API/database code is unchanged.

## Verification

**51 focused regressions passed in 1.81 seconds.** Tests cover full-row leading vowels, mixed Thai/Latin titles, credit/code exclusion, wrapped-title PSM safeguards, independent word reading without Tesseract fills, raw case preservation, alignment refusal, existing parser/crop/voting/cache/truncation behavior.

Known development samples: pages 19/21/27 now select **57/57 complete exact**, resolving the two Thai disagreements; pages 20/24/26 now select **55/55 complete exact**, resolving raised English `st` versus `ST`. The final `tha+eng` helper was checked again against both native Thai images and still supplies exact cross-engine-supported values. These are post-fix development results, not untouched benchmarks.

## Untouched samples and remaining limits

The first frozen new sample, pages **25/30/31**, exposed a mixed-script Thai-region omission: `IPO` was cropped out of a Thai title. Baseline retained unchanged: **21/23 complete exact**, 22 selected; Thai ambiguity 90643017 withheld and incomplete Thai title 90643025 selected but flagged. All failures flagged. Page 30 also has three creditless Audit cross-references, reported outside the catalog schema; page 31 is a learning-outcomes table with no course codes. They receive no fabricated credits and are not full-text OCR scores. This sample's zero-error gate fails. After this result, the mixed-script crop was fixed and regression-tested; this sample remains development evidence.

A different sample was frozen after that fix: pages **14/15/16**. Result: **19/19 unique courses complete exact**, zero review entries, zero HTTP/truncation failures, no extra courses. There are **22 course occurrences** because three course definitions repeat across pages; all repeated fields agree before deduplication. Per-page frozen observations: page 14 = 5/5, page 16 = 17/17. Page 15 has no course codes and generates no candidates, a schema negative control. The schema-scoped zero-error gate passes for this small sample.

Evaluation-only readers needed assessment-footnote, spaced-star cross-reference and repeated-code accounting fixes. Initial assertions and invalid intermediate results are retained. OCR candidates/hashes and frozen recognition/selection were unchanged during scoring; no reference-driven retries or inserted answers.

The final sample has 14/19 contents overlapping GE66 and uses the PDF text layer as reference, not independent human ground truth. Whole-page Tesseract already scores 19/19 on this sample; this validates preserved behavior rather than a gain over that baseline. It does not supersede earlier failed layouts or certify arbitrary-document/full-PDF OCR. Mixed Thai/Latin readings can still disagree, e.g. `IPO` versus `!00`; these must stay reviewable.

## State and next step

All 22 production catalog/SQLite/Gold hashes unchanged; verified five-plan GE66 databases and Text-layer backups retained. No new SQLite promotion or main merge. Next: independent Latin-word image evidence for mixed-script Thai titles and Thai-mark disagreement 90643017, followed by an independently chosen broader sample; retain unresolved rows without hard-coded words.

Local ignored evidence: `.superpowers/ge66-independent-evidence-diagnostics/`, `.superpowers/ge66-independent-evidence-new-pages/` (pre-fix baseline), and `.superpowers/ge66-independent-evidence-final-pages/` (final frozen sample). Raw PDF/images/databases are excluded from this commit.

Official source: https://gened.kmitl.ac.th/wp-content/uploads/2021/08/GE64_KMITL_Thai_program.pdf

PDF SHA256: `3fafa1d07512815bed1d0a7635201934c75d6afce91ff33fca9f4bd656619931`
