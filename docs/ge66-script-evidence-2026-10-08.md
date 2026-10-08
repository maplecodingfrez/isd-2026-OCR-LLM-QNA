# Script-region OCR evidence - 2026-10-08

Thai title ties previously preferred Typhoon even when its reading disagreed with a correct Tesseract reading. English superscript glyphs were merged into digits or punctuation. The new image-only helper reads Thai title regions separately and measures connected ink components relative to the English line baseline. Raised components and base text are OCR-read separately; no suffix dictionary, course-specific correction, case conversion or reference fill is used.

## Changes

- `ge66_script_evidence.py`: Thai regions from image-recognized word boxes; raised-glyph strips from pixel geometry; raw part readings and boxes retained. Generic region model requests retain image/prompt/model/options provenance and reject truncated/stale cached responses.
- `ge66_targeted_retry.py`: append field-only Thai reads from Tesseract/Typhoon and raised English reads from Tesseract. Field-only observations cannot vote for other fields. Changed region geometry requires fresh output directories. Original observations remain retained.
- `ge66_select_candidate.py`: conflicting Thai and English require exactly one value supported by distinct engine families. Two competing cross-engine values remain withheld. Single-engine nonconflicting candidates still require review; candidate output remains unapproved.

## Evidence

43 focused parser/crop/selection/English/script-region regressions passed in 2.27 seconds, including raised-letter case preservation, inconclusive-geometry refusal, partial-field voting, ambiguous Thai withholding, cache provenance and truncation rejection.

Known-page development regression: GE64 90642056 now reads `EPIDEMICS IN THE 21st CENTURY` from raw `21` + `st` image reads, agreeing with prior Typhoon. 90642093 now reads the same Thai title with both engines on an automatically located Thai image region. Both original failures are fixed. Stricter name agreement exposes competing Thai evidence on 90642062 and 90642091: 55/57 records selected and all 55 exact; two withheld. These are development results, not a fresh score.

Frozen new-page sample: official GE64 Thai PDF pages **20/24/26**, 300 DPI, original OCR prompt and fixed local Typhoon model. Retries selected only by image anchors and engine disagreement/missing evidence. OCR/candidate completed before PDF text-layer reference extraction.

| Output | Courses parsed / 55 | Thai exact | English exact | Credits exact | All fields exact |
|---|---:|---:|---:|---:|---:|
| Candidate | 54 | 54 | 54 | 54 | 54 |
| Whole-page Tesseract | 54 | 53 | 52 | 54 | 51 |
| Chunk Typhoon | 42 | 42 | 40 | 42 | 40 |

Pages: 20 = 19/19, 24 = 18/18, 26 = 17/18 complete exact. One withheld row, 90643037, remains ambiguous in English (`21st` versus `21ST`). All selected records are exact, all remaining failure is flagged for review. Six review entries retain other disagreements. There were zero HTTP/truncation failures. **Zero-error promotion gate fails because one course is withheld.**

Reference-reader corrections were evaluation-only: exclude numbered group headings and support standalone course codes. The initial failed assertion and invalid intermediate score/reference were retained locally. Candidate SHA256 remained `ba25d42667bc2194cfcddcff4b7fe3ef3a93d1c82d7eab888d14a9161a90735e`; frozen recognition/selection was not changed after scoring.

## Scope and next step

45/55 course contents overlap GE66. This is new-page/layout evidence against PDF text-layer reference, not independent human ground truth or entirely unseen content. Regions still use GE-specific horizontal geometry; raised-glyph splitting requires a clear peer baseline and separate connected components. It cannot resolve all typography or arbitrary-document tables.

All 22 production catalog/SQLite/Gold hashes unchanged; the verified five-plan GE66 databases and Text-layer backups remain retained. No new SQLite promotion and no main merge. Next: independent image evidence for remaining case/Thai disagreements, then another untouched evaluation; never insert expected words to resolve ambiguity.

Local ignored evidence: `.superpowers/ge66-script-region-diagnostics/` and `.superpowers/ge66-script-evidence-new-pages/` (plan, hashes, images, responses, part readings, reference and reports). Raw images/PDF/SQLite are not included in this commit.

Source PDF: https://gened.kmitl.ac.th/wp-content/uploads/2021/08/GE64_KMITL_Thai_program.pdf

PDF SHA256: `3fafa1d07512815bed1d0a7635201934c75d6afce91ff33fca9f4bd656619931`
