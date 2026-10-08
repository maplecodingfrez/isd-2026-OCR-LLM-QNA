# GE64 table-cell OCR follow-up - 2026-10-09

Work is confined to `dev/tests`. No source-branch edits, database access, catalog/Gold promotion or main merge.

## Parser and recognition changes

Integrated only `parse_ge_ocr` from the existing source checkout. The rest of that module is unchanged (AST comparison verified). This brings observed inline/wrapped bilingual fields, standalone codes, credit wrappers, entities, literal punctuation and guarded HTML continuations into the standalone tests branch. Eight existing format failures were reproduced before integration. No values were copied from a reference catalog.

Strong vertical pixel rules now delimit a unique wide central title cell. English extraction keeps its full width and every line below image-recognized Thai, excluding the surrounding code/credit rules without deleting glyph pixels. Blank margins are tolerated; ambiguous/no-rule cases retain the full row width. The crop remains document-specific.

The substring guard now checks the uniquely agreed title. A complete title supported by both engine families may beat a shorter single-family fragment. An agreed shorter title with any conflicting longer reading remains withheld. Two competing agreed values remain withheld. Repeated variants do not become independent engines.

Pillow, PyMuPDF and pytesseract documentation was retrieved through Context7 before code calling those libraries was written. No dependencies/models were installed or downloaded.

## Known pages 139-146: development evidence

All eleven previously withheld courses received new title-cell image reads from Tesseract and Typhoon. New field-only observations replace their old geometry in a separate development experiment; raw old observations and the original frozen candidate/report remain intact. Credits remain observed values, never fabricated. A further native 600-DPI round used image-recognized anchors and pixel row/cell bounds. Reference text was used only for scoring after each recognition round.

| Stage | Exact / expected | Selected exact | Withheld |
|---|---:|---:|---:|
| Previous saved-evidence guard replay | 93/104 | 93/93 | 11 |
| New title-cell reads | 100/104 | 100/100 | 4 |
| Native image follow-up, shipped helpers | 101/104 | 101/101 | 3 |
| Additional local isolated/one-peer experiment | 102/104 | 102/102 | 2 |

The shipped-helper development result retains 90643017 (Thai vowel), 90643027 (English comma) and 90643037 (wrapped raised glyphs) for review. An explicitly local single-peer raised-glyph experiment supplies an independent Tesseract reading for 90643037; it is not integrated into the frozen trial or shipped helper. Best-model Thai and isolated Typhoon punctuation probes did not establish agreement for the other two. Preserve these refusals; do not count repeated Typhoon variants as a new engine or normalize away meaningful punctuation/Thai marks.

All selected field values are traceable to raw image OCR. Zero selected errors/extra codes on the development reference. These pages were already evaluated and contain 93/104 GE66 content overlap; the reference is the PDF text layer, not independent human ground truth. These are development results, not untouched accuracy or a production approval. The zero-error gate remains closed.

## Interrupted layout baseline and fresh page images 150-154

The initial plan was pages 147-154. The user paused during page 148 and later resumed with image/prompt/model/options-matching caches. Image-only inspection proved the fixed left columns omit the code and leading glyphs on the new layout. That attempt was stopped during page 149 and preserved as interrupted layout-failure evidence with exact frozen source snapshots; pages 147-149 are now development images. It has no completed full-sample accuracy score, and no reference text was opened.

The retry uses full-page Tesseract plus left boundaries derived from observed code-box positions and glyph height. Plain-row English uses full row width; clear table cells still use pixel rules. Three new regression failures were reproduced before those geometry fixes. A new plan freezes all sources/prompt/model/PDF before rendering untouched pages 150-154; it explicitly excludes the newly used 147-149 pages as well as all earlier samples.

The completed frozen sample has 42 printed occurrences, 34 unique course codes, and 33 unambiguous reference courses. Code 90643006 has two different printed Thai titles on pages 150 and 153; both are preserved in the summary, excluded from aggregate scoring, and the candidate withholds that code. Page 154 is an appendix heading with no course rows.

Candidate: 31 selected, 30 exact against the 33 unambiguous courses, no extra codes, and two unambiguous courses withheld (90642132, 90643030). One selected error: 90642113 has observed English `MODERN ENTREPRENEURS` instead of printed `ROBOTICS AND AI`. Agreement between engine families did not prevent this association error. All 93 selected fields still trace exactly to raw OCR; traceability is not correctness. Seven review entries include three withheld codes; no HTTP/truncation failures.

Per-page exact/expected: 150 = 13/13; 151 = 8/10; 152 = 9/9; 153 = 5/7; 154 = 0/0. These occurrence scores include page-specific reference titles, unlike the unique aggregate. Raw Tesseract and same-format Tesseract each score 27/33; raw Typhoon scores 30/33. Reference content overlap is 29/33 with the existing GE66 catalog: new page images are not wholly new course content. The zero-error gate fails. No recognition retry or policy change was made after reference extraction.

The evaluation reader initially refused faculty prose after trailing credits, then duplicate course occurrence counts, then a genuine conflicting reference title. Only the scorer changed: trailing credit terminates names; repeated codes remain occurrences; conflicting reference titles are explicitly reported rather than choosing one. Recognition sources match their frozen hashes and candidate/observation bytes remain unchanged. The compact metrics, immutable hashes, frozen plan and reference conflict are in [ge64-followup-summary-2026-10-09.json](ge64-followup-summary-2026-10-09.json).

Remaining work: diagnose the 90642113 row association from images, obtain independent evidence for the withheld titles, and then freeze another untouched sample. This run is completed evidence of a failing gate, not a production approval.

The original fixed-column failure remains retained in `fresh-pages147-154/interrupted-layout-failure.json` with source snapshots and 40 cached responses. The new `fresh-anchor-pages150-154` result is separate; no answers or reference geometry were used to change crops. Full-page images, anchors, raw responses, failures and scoring inputs remain locally under ignored `outputs/ge64_test_followup_20261008/`.

## Verification and reproduction

75 focused parser/crop/selection/English/script-evidence tests passed on this branch without `GE66_SOURCE_ROOT` or database/API access. New failures were observed before the full-cell and complete-title fixes. AST checks confirmed no parser-module change outside `parse_ge_ocr`; frozen source hashes are checked again by scoring.

```powershell
$python = 'D:\DSBA 3rd Year\Works\ocr_system (all)\ocr_system\.venv\Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
Remove-Item Env:GE66_SOURCE_ROOT -ErrorAction SilentlyContinue
& $python -m pytest -q tests/test_ge_ocr_formats.py tests/test_ge_ocr_crop_quality.py tests/test_ge_ocr_selection.py tests/test_ge_english_evidence.py tests/test_ge_script_evidence.py -p no:cacheprovider
& $python scripts/ge64_image_trial.py --pdf $pdf --output $run --pages 150 151 152 153 154
& $python scripts/ge64_score_trial.py --output $run --pdf $pdf
```

Set `$pdf` to the existing official GE64 PDF and `$run` to a new ignored output directory. Current development diagnostics can be scored with `--reference <saved-evaluation-only.json>` after their completion marker. Never run a new policy over an old cache: plan/cache identity guards refuse it. The scorer opens the text layer only after recognition completes and preserves candidate/observation bytes. Tests/scripts/reports are included in delivery; raw PDFs/images/responses remain local.

Production database hashes were deliberately not reopened/rechecked in this database-free task. Prior production verification is historical and does not certify this new OCR sample.

## Later completion

The later [OCR completion report](ge64-completion-2026-10-09.md) records the image-only repairs and separate development/frozen evaluations. The failures above remain historical evidence. The subsequent user-authorized [GE66 DB promotion](ge66-db-promotion-2026-10-09.md) is a separate phase using the complete303-course GE66 catalog, not the partial GE64 sample.
