# Mixed-script word evidence and larger table evaluation

The mixed Thai/Latin title for 90643025 now reads `เส้นทางสู่ IPO` from image OCR. The complete title's Tesseract word box locates the Latin token; English-only PSM6/7 both read `IPO`. These reads agree with Typhoon's independent complete-title reading. No expected spelling, case conversion, course-specific correction, or reference text enters recognition.

## Implementation

- Isolated Latin-token images retain raw readings, coordinates and image hashes. Only unique, non-overlapping text anchors with matching PSM6/7 readings can replace a token in that engine's own title. Repeated/subword anchors and multiword insertions are rejected. All variants remain one Tesseract family.
- Convert a recognized `|` immediately following a valid GE code into row formatting. Pipes in titles and malformed code lines remain untouched. Raw OCR files are retained; this is delimiter conversion, not spelling repair.
- Narrow vertical table rules spanning the inspection band no longer count as clipped glyphs. Returned crop pixels remain unchanged; genuine clipped text still triggers expansion/review.
- Targeted retries consume these image-derived readings while preserving the existing strict cross-engine selection policy. These are dev tools; no application/SQLite promotion.

## Known development results

- The preserved original pages 25/30/31 baseline remains 21/23 complete exact. Its incomplete Thai-only region readings are retained in the original directory and replaced with fresh complete-region reads in a separate development experiment.
- Development selection is now 22/23 complete exact: all 22 selected Thai/English/credit records match the evaluation reference, no extra codes. 90643017 remains withheld (`ลีน` versus `ลืน`). 90643025 stays in the audit queue because historical readings disagree, despite unique cross-engine support for the selected complete value. Three creditless Audit cross-references remain outside catalog schema.
- Native, grayscale, threshold, resized/isolated Thai image probes and official Tesseract best Thai/script weights did not resolve the vowel automatically. Raw attempts and model hashes are retained; no manual substitution was accepted.
- 61 focused parser/crop/selection/script regressions passed; verified again against the dev-worktree files.
- Replayed 19 existing plain-catalog crop cases through both crop guards: identical returned pixels and boundary metadata, zero differences.

## Broader evaluation protocol

Use [official GE64 Thai PDF](https://gened.kmitl.ac.th/wp-content/uploads/2021/08/GE64_KMITL_Thai_program.pdf), SHA256 `3fafa1d07512815bed1d0a7635201934c75d6afce91ff33fca9f4bd656619931`.

- An alternate official April edition had identical catalog-page pixels 14–31; it was rejected as fresh image evidence.
- Initial table run stopped after observing pages 129/130, before extracting reference text. Its frozen plan, raw images/readings and interruption record are retained. PSM6 dropped table rows and an observed column separator contaminated names. PSM4 and delimiter conversion were chosen from those preflight images, without reference scoring.
- Freeze eight untouched appendix comparison-table pages 131–138, helper/runner hashes, prompts/model/options, geometry and retry policy before recognition. Pages 128/129/130/155 are explicitly preflight and excluded from the final sample.
- Recognize images first; retries depend on absent families or engine disagreement. Save unapproved candidates/review queue and recognition-complete marker before extracting the PDF text layer for evaluation. Course content overlaps previous catalogs; this tests new page images/layout, not wholly unseen semantic content or arbitrary full-text OCR.

Result: **100/110 complete exact**, 103 selected, seven withheld. English and credits are exact for all 103 selected records; three selected Thai titles remain wrong. There are 27 audit entries, zero HTTP/truncation failures and no extra codes. All ten failed/withheld courses are flagged; no unflagged semantic failure in this sample. Zero-error gate fails.

| Variant | Selected / 110 | Complete exact |
|---|---:|---:|
| Candidate after independent evidence | 103 | 100 |
| Tesseract PSM4, same delimiter formatting | 107 | 97 |
| Typhoon chunks before retries | 101 | 97 |

Raw unformatted Tesseract scoring is retained separately (2 complete exact) and is not a fair recognition-only comparison: table separators contaminate Thai names. Same-format scoring avoids overstating the candidate's improvement.

- Withheld: 90642056, 90642079, 90642112, 90642113, 90642117, 90642119, 90642157.
- Selected Thai errors: 90642058 (wrapped title lost its first line), 90642091 (Thai character recognition), 90642159 (tight separator attached to the title). These are development cases for the next pass; frozen outputs were not repaired after scoring.
- Per-page complete exact: 12/14, 14/14, 12/14, 14/14, 10/14, 14/14, 14/14, 10/12.
- 93/110 course contents overlap GE66. The reference is the PDF text layer, not independent human transcription. This is a new table-image/layout sample, not wholly unseen course content.
- The evaluator initially rejected an old-course `-` placeholder. The original assertion/reader and initial baseline report are retained; only reference formatting/reporting changed. Candidate SHA256 stayed `03586e4a8d311040aa9fb1a20e52ddcfc4336de8d9a9db9bf1997757b8303674`; all 309 candidate field values trace to OCR observations. No reference-driven retries or post-score recognition changes.

## Evidence and delivery

Local ignored evidence: `.superpowers/ge66-word-evidence-diagnostics/`, `ge66-word-evidence-known-development/`, `ge66-word-evidence-appendix-pages/` (interrupted preflight), and `ge66-word-evidence-final-appendix/` (frozen final sample).

All 15 currently existing protected catalog/SQLite/Gold hashes remain unchanged. Seven old retry databases were archived independently before this task's snapshot. The verified five-plan GE66 databases and text-layer backups are retained. Source cleanup HEAD is 0014f27; this delivery only changes dev/tests tools/tests/report. No main merge.

Next, in order: preserve complete table-cell/row coverage for wrapped Thai titles and tight separators; obtain independent Thai-character and Latin/raised-word evidence for the flagged cases (including 90643017); then freeze untouched pages 139–146 or another genuinely new image source before any further data promotion.

## Follow-up table-row crop fix (2026-10-08)

- Use adjacent image-detected horizontal rules to crop full table cells, retaining wrapped Thai lines. Missing boundaries fall back to the existing bounded crop and quality guard.
- Remove a table pipe immediately after a valid GE code even when OCR leaves no spaces. Thai title extraction uses the row's Thai word boxes and strong vertical cell rules to exclude code and credit columns.
- Replayed image-derived development crops for 90642058, 90642091 and 90642159 without changing frozen candidates or references. New Typhoon row-crop reads for 90642091 and 90642159 match the evaluation-only PDF text layer; Tesseract variants also read those spellings. 90642058 now retains both lines, but its Thai word reading differs from the PDF text layer, so it remains flagged.
- 64 focused parser, crop, selection and script-evidence regressions pass. No fresh 139-146 scored run was performed; no SQLite/Gold/catalog promotion. Next: investigate remaining Thai disagreements, then freeze and score an untouched page set before any promotion.
