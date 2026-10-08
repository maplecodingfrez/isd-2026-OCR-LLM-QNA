# English OCR evidence and engine-family selection ? 2026-10-08

## Changes
- Added `ge66_english_evidence.english_title_image`: locate the region below image-recognized Thai using Tesseract bounding boxes, retain wrapped English lines, and return no evidence if the boundary/region cannot be recognized. The geometry remains specific to these GE row images.
- Row retries retain a Tesseract eng-only observation scoped to `name_en`; it contributes no extra Thai/credit votes. Changed English-region geometry requires a fresh output directory to preserve evidence.
- Selection ranks distinct engine families rather than number of repeated calls. If competing English values have no unique cross-engine agreement, the row is withheld from the candidate and retained for review. Single-engine/no-conflict observations still remain reviewable; all candidate artifacts are unapproved.
- Field support totals exclude partial observations that do not contain that field. No reference spelling, dictionary substitution, manual field fill or product/database edit was introduced.

## Verification
- Parser/crop/selection/English-region regressions: 32 passed. Additional metadata check reran the affected 10 selection cases, all passed.
- Development diagnostics on the prior page-18/22/28 observations plus eng-only evidence: 54 candidate records, 53 all-field exact; 90642113/90642117 and a further conflicting English row withheld. Remaining single-engine English error is reviewable. This is development evidence, not a passing general-accuracy claim.
- Frozen new-page test: official GE64 Thai PDF pages 19/21/27, 57 expected courses, using image-only full-page/column anchors, chunk/row recognition, eng-only Tesseract and an additional Typhoon read of the English region. Reference opened only after all recognition and selection completed; no reference-driven retries or post-score spelling fixes.
- Candidate: 56/57 courses selected; English 56/56 exact, credit structures 56/56 exact, Thai 55/56 exact. Complete records 55/57 overall. Page results: 18/19, 18/19, 19/19.
- 90642056 withheld for unresolved English agreement; 90642093 Thai title reads a different first consonant. Both are in the review queue. Ten total review entries are retained, including original engine disagreements even when the selected values match reference. Zero-error promotion gate fails.
- 45/57 course contents overlap GE66; this is new page-image/layout evidence, not completely unseen content or independent human ground truth. Raw new-page evidence and frozen code snapshots remain local in `.superpowers/ge66-english-family-new-pages/`.
- All 22 production catalog/DB/Gold hashes unchanged, including the previously promoted five-plan GE66 OCR databases. Main is not merged.

## Source and next steps
Official PDF: https://gened.kmitl.ac.th/wp-content/uploads/2021/08/GE64_KMITL_Thai_program.pdf
SHA256: 3fafa1d07512815bed1d0a7635201934c75d6afce91ff33fca9f4bd656619931

Next: inspect the unresolved English and Thai image evidence, improve Thai selection/recognition without spelling hard-codes, then validate on a different untouched sample. Keep ambiguous rows in review and the verified GE66 production data unchanged.
