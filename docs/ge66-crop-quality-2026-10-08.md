# GE66 crop and voting fix ? 2026-10-08

The GE64 development test previously selected a clipped English title for 90644054. Pixel inspection showed the row bottom cut through English glyphs; the vote tie favored the unsupported crop over the correct whole-page OCR.

## Changes
- `ge66_crop_quality.safe_row_crop` completes glyph bands at top/bottom boundaries using rendered pixels only, adds blank margins, and flags boundaries that cannot be safely expanded.
- Row retries retain crop-quality metadata. A changed crop policy requires a fresh output directory to preserve old images/cache provenance.
- Candidate voting rejects flagged clipped observations. Equal-support ties retain the original view after the existing engine preference; all-clipped rows produce review entries without a candidate.
- No correction dictionaries, reference values or manual field fills were introduced.

## Validation
- Saved development row: bottom expanded from 1872 to 1883; fresh Tesseract reads the complete English title.
- Re-selecting the original 57-course development observations: 56/57 to 57/57 all fields exact. This is a regression result, not held-out accuracy.
- Crop, selection and parser regressions: 26 passed.
- Frozen new-page test on official GE64 Thai PDF pages 18/22/28: 57/57 codes, 57/57 Thai, 54/57 English and 57/57 credit structures. All-field exactness 54/57. Pages 18 and 28 each pass 19/19; page 22 passes 16/19.
- Remaining English errors: 90642112 and 90642113 read AI as Al; 90642117 reads 21st as 21%. All three are in the review queue. No post-score fix or reference-driven retry was performed.
- Zero-error gate fails. 56/57 course contents overlap GE66, so this tests unseen page images/layout rather than entirely unseen course content. Text-layer oracle is not independent human ground truth.
- All 22 production catalog/DB/Gold checksums unchanged, including the already promoted five-plan GE66 OCR databases.

## Evidence and next steps
Original, regression and new-page artifacts are local ignored folders `.superpowers/ge66-heldout-20261008/`, `.superpowers/ge66-crop-regression/` and `.superpowers/ge66-unseen-pages-after-crop/` respectively. The new test freezes prompt, model, crop/vote hashes and source PDF hash before recognition, then scores only after completion.

Source PDF: https://gened.kmitl.ac.th/wp-content/uploads/2021/08/GE64_KMITL_Thai_program.pdf
SHA256: 3fafa1d07512815bed1d0a7635201934c75d6afce91ff33fca9f4bd656619931

Next: calibrate independent English-line evidence and engine-family support, retaining ambiguous rows for review; validate on a different untouched sample. Do not claim automatic arbitrary-document OCR is complete. Main is not merged; these tools remain on dev/tests.
