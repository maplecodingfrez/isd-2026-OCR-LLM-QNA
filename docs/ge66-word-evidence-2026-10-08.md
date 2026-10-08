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

## Saved-evidence replay (2026-10-08 22:29)

The pending selector diff refuses a Thai or English title when one eligible normalized reading is a strict substring of another, even when the shorter reading has cross-engine support. It withholds the record rather than choosing either spelling. Flagged clipped observations remain excluded. This is deliberately conservative: complete-title agreement also stays withheld if an eligible shorter reading conflicts. Tests cover Thai/English truncation and clipped-observation exclusion.

Re-evaluated official GE64 pages **139-146** from the existing `ge66-word-evidence-pages139-146` observations and evaluation-only reference. No new OCR, model calls, reference-driven retries or expected-value fills. Original observations, candidate, references, report and frozen scripts were preserved; ten input hashes are recorded in `ge64-pages139-146-replay-2026-10-08.json`.

| Selection | Selected / expected | All fields exact | Withheld | Review entries |
|---|---:|---:|---:|---:|
| Frozen policy | 97/104 | 97/104 (97/97 selected) | 7 | 23 |
| Current substring guard | 93/104 | 93/104 (93/93 selected) | 11 | 23 |

All 279 selected fields trace to saved OCR observations. No extra codes or selected field errors. Newly withheld: **90643011, 90643016, 90643024, 90643030**. This reduces coverage by four records; it does not improve exactness on this already-correct selected baseline. The zero-error gate fails because eleven courses remain withheld. The original report records zero recognition failures; replay makes no recognition requests.

The frozen selector reproduces the original score and normalized content, but not identical raw strings: Thai 90644061 differs between precomposed `ำ` and combining `ํา`. Both are equivalent under the existing NFKC comparison. The original candidate bytes were retained; this replay does not claim byte-identical candidate reproduction.

Per-page current exact/expected: 139: 13/14; 140: 8/14; 141: 7/10; 142: 12/12; 143: 14/14; 144: 14/14; 145: 13/14; 146: 12/12.

The original baselines remain historical: same-format Tesseract 95/104, chunk Typhoon 99/104. Reference content overlaps GE66 in 93/104 courses. The reference is the PDF text layer, not independent human ground truth. Recognition was originally frozen, but this selection policy changed after evidence was available; the current result is a development replay, not a fresh held-out score or full-document certification.

Validation: **50 local tooling tests passed**, and **67 combined tests passed** with `GE66_SOURCE_ROOT` pointing read-only at the existing source checkout. Direct combined testing against the parser shipped on dev/tests gives 59 passed / 8 existing parser-format failures (initial run before two added regressions: 57/8). Those parser fixes reside on the source branch; no parser code was copied or changed here. Reproduce tooling checks with:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'D:\DSBA 3rd Year\Works\ocr_system (all)\ocr_system\.venv\Scripts\python.exe' -m pytest -q tests/test_ge_ocr_crop_quality.py tests/test_ge_ocr_selection.py tests/test_ge_english_evidence.py tests/test_ge_script_evidence.py -p no:cacheprovider
```

For combined integration add `tests/test_ge_ocr_formats.py` and set `GE66_SOURCE_ROOT` to the existing source checkout. This reads its parser only. Replay scoring loads saved `observations.json`, calls `select`, then loads `reference-evaluation-only.json` and calls `ge66_ocr_audit.metrics(reference, records, [{'text': ' '.join(observations)}])`; per-page scoring uses saved occurrence references and observations filtered by page. Do not rerun the old scorer in place: it writes the original evidence report.

No source-branch edits, database access, catalog/Gold changes, data promotion or main merge. Prior production-hash claims were not rechecked in this database-free replay. `PROGRESS.md` and `.claude-mem/timeline.md` were absent in this worktree; scoped continuation entries were created here without modifying or copying the source branch's historical logs. Next: obtain independent image evidence for the eleven withheld records, evaluate the coverage tradeoff, then freeze a genuinely untouched sample before promotion.

## Follow-up on 2026-10-09

[Image follow-up report](ge64-table-cell-followup-2026-10-09.md): standalone parser fixes and known-page image diagnostics reach 101/104 exact with shipped helpers. Frozen new pages 150-154 reach 30/33 unambiguous exact, including one selected English association error; a conflicting PDF code is excluded explicitly. Both gates remain closed. Original evidence is preserved.
