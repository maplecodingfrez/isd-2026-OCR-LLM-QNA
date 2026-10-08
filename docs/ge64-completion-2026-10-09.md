# GE64 OCR completion - 2026-10-09

Scope: dev/tests worktree only. No frontend, database access, main merge, Gold/catalog promotion or dependency/model installation.

## Root causes and implemented behavior

- Code detections are merged by overlapping pixel positions, not by unique code. Repeated codes now terminate adjacent rows. Every code occurrence receives its own row recognition and separate cache namespace.
- Field evidence refuses images containing multiple course codes. Thai crops stop before the first separate English title line; English crops stop before later Thai faculty/appendix prose. Whole-page/chunk observations remain raw audit evidence and cannot vote into a bounded occurrence from another row.
- Printed page/row occurrences vote separately. A unique catalog rejects conflicting printed titles explicitly; it never selects one using an oracle.
- Wrapped raised words require a reliable same-line baseline and consistent other title-word heights. Initial Thai marks are read from a connected pixel cluster by two literal segmentation modes; the base consonant must stay identical. Punctuation word readings come entirely from Typhoon images, with Tesseract supplying geometry only. Multi-word replacement responses are refused.
- English has an alternate uppercase-character-set OCR hypothesis in the same Tesseract family. Raw case-sensitive readings remain intact. No string uppercasing or course-specific name substitutions are used; cross-family voting and the existing shorter-title guard still govern conflicts.
- Completion markers hash candidate, observations and occurrence candidate before reference extraction. Scoring checks them, scores repeats as a page/code multiset, counts missing/extra occurrences, and refuses empty/failing samples as passing gates.

## Verified known pages 139-146

Literal image-glyph follow-up selected 104/104, all fields exact after NFKC/whitespace comparison, no extra/missing courses or selected differences, and 312 selected values trace to raw OCR observations. This closes all eleven original withholding cases. The original saved evidence remains unchanged; the new observations and selected candidate are separate development artifacts.

90643017: the isolated initial Thai base+mark cluster has matching PSM8/13 readings, preserving the base consonant and replacing only observed marks. 90643027: an isolated Typhoon word image reads `MAN ,`; the remaining tokens come from its own whole-image reading, not Tesseract text. 90643037: wrapped raised glyphs are read from separate base/raised image strips using a validated baseline. All variants of one engine remain one family.

These are known-page development results against the official PDF text layer, not independent human ground truth or untouched accuracy. Raw observation/candidate/source/image hashes are retained in the portable summary and local frozen evidence.

## Preserved failed attempts

The earlier 147-154 fixed-column attempt remains historical evidence, with no completed score. This completion run also retains a broad-chunk HTTP timeout before candidate creation and a repeated-code partial-field exception caused by an unused broad conflict calculation. Neither has a completed full-sample score. Their sources, partial responses and interruption records remain locally; neither is rewritten as a passing run.

The single-row retry uses a new frozen plan. Only raw caches with identical image, prompt, model and request options are reused for development; previous candidates and reference values are never recognition inputs.

## Repaired printed occurrences on known pages 150-153

The combined development replay is 42/42 printed occurrences exact, with no missing/extra occurrences or selected differences. It combines 21 legacy page-scoped observations from pages 150/152 with 21 newly bounded occurrences: 19 on pages 151/153 and the two printed copies of 90642012 on page 152. The 19-row and two-row isolated reruns separately pass their occurrence gates. This is not a new untouched 42-row trial.

All 33 unambiguous unique courses are exact. The canonical catalog gate remains closed because 90643006 has two genuinely different printed Thai titles: page 150 `การบริหารจัดการยุคใหม่และภาวะผู้นำ`; page 153 `การจัดการและผู้นำสมัยใหม่`. Both occurrences are correct and retained. Resolving the source's canonical title requires an authoritative source decision; no reference-driven guess or database promotion is made.

The selected wrong English association of 90642113 is repaired through bounded title images and agreement between independent engine families. The titles of 90642132 and 90643030 are complete. Wider row readings are retained for audit; bounded field observations supersede them only with two independent families. English fields are bounded by the initial contiguous English word lines to exclude later footer marks.

The initial untouched 32-35 run contained skill tables/prose with no course anchors and exposed an empty-run finalization failure: observations were not written before hashing. That failed run has no completion marker or score and is preserved as `fresh-pages32-35/interrupted-empty-finalization.json`. A regression now verifies that empty artifacts finalize safely and that 0/0 cannot pass. A new untouched sample 72-75 was frozen before rendering; no reference text was opened during recognition.

## Preserved first untouched trial and image-only repair

Frozen pages 72-75 completed recognition before PDF text extraction. All 13 selected courses/occurrences are exact; two Thai titles are withheld (90642102 and 90642105), two missing withheld records, no selected differences, extra occurrences or transport failures. Both zero-error gates are closed at 13/15. Three recognition artifact hashes verified before and after scoring; nine source snapshots match the original frozen plan.

The follow-up keeps that frozen run unchanged. Additional half-size unanimous PSM8/13 raw-line reads recover a literal Tesseract title for 90642105. These modes refuse wrapped lines and preserve unsupported leading punctuation without voting or stripping it. A half-size Typhoon title hypothesis alone remains inconclusive for 90642102. A terminal cluster image independently reads `บ`, while the rest of the title comes from Typhoon's own whole-image response. This is a literal glyph replacement, with no Tesseract spelling fill or course-specific rule. Multi-character responses, Latin endings and wrapped lines are refused by the terminal probe.

The separate known-page development candidate is 15/15 unique and occurrence exact with both gates passing. Original 72-75 artifacts and the intermediate 14-selected development attempt remain preserved; the corrected 15/15 is not an untouched score. Seven new regressions were observed red before implementation; the complete related suite is 111 passed. The next untouched 76-77 sample was frozen after these fixes, before rendering/reference extraction.

## Preserved second untouched trial and printed-spelling repair

Frozen pages 76-77 select 6/7 courses/occurrences, all six exact, no extra occurrences or transport failures. The sole withheld field is English 90642118: Tesseract reads the printed `BUSSINESS`, while Typhoon normalizes it to `BUSINESS`. Both whole-sample gates remain closed; page 76 separately scores 3/3 and page 77 3/4. All seven reference courses overlap GE66 content, so this measures new image/layout transfer rather than unseen course names.

The word retry exposed a geometry defect: its blank margin included part of the preceding word's last letter. Word margins now stop between adjacent OCR boxes, including other lines, and overlapping boxes are refused. A central blank column divides a single word into two pixel parts; both raw Typhoon responses must be single alphanumeric strings, which concatenate without dictionary correction, case conversion or Tesseract character fills. The bounded parts read `BUSS` and `INESS`. A separate development candidate scores 7/7 with both gates passing; the original 6/7 frozen sample stays unchanged.

Four geometry/split regressions and three freshness regressions were observed red, then green. PDF-matched local plans now supplement the historical page exclusion list across output directories. Completed/reference-opened outputs cannot resume as fresh; reruns require development scope and a new output plan. Planned pages count conservatively as used. A final single untouched page 78 was declared and frozen after these fixes; its small scope must not imply arbitrary-document accuracy.

## Final frozen untouched page 78

The declared single-page sample completes recognition before reference extraction and scores **4/4 unique courses and 4/4 printed occurrences exact**. Both zero-error gates pass: no missing/extra records, selected differences, withheld fields, reference conflicts or transport failures. All 12 selected field values trace to raw occurrence-qualified OCR observations. Three completion artifact hashes and ten frozen source snapshots verify; candidates/observations remain immutable through scoring.

Three of four course titles/content overlap GE66. This is a small new-image/layout sample against the official PDF text layer, not independent human ground truth, unseen-content accuracy or a guarantee for arbitrary documents. Earlier frozen scores 13/15 and 6/7 remain failed; their 15/15 and 7/7 repairs are separate known-page development candidates. All selected errors and withheld fields discovered in this work have an image-backed repair; the genuine printed source conflict 90643006 remains explicit rather than guessed canonical data.

Portable metrics, plans, immutable artifact hashes and source snapshot hashes are in [ge64-completion-summary-2026-10-09.json](ge64-completion-summary-2026-10-09.json). The tracked plan is [2026-10-09-ge64-ocr-completion.md](superpowers/plans/2026-10-09-ge64-ocr-completion.md). Raw images/model responses remain local under the ignored evidence directories; no full PDF or model files are committed.

## Validation scope

The full related suite comprises six database-free OCR modules (118 passing tests at the spelling/history checkpoint). No database/API suite, production catalog promotion, Gold change, dependency/model installation, frontend modification or main merge is part of this work. Exactness removes NFKC-equivalent/whitespace differences while preserving case, punctuation and Thai marks. Raw files retain their original characters.

## Reproduction

```powershell
$python = 'D:\DSBA 3rd Year\Works\ocr_system (all)\ocr_system\.venv\Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $python -m pytest -q tests/test_ge_ocr_formats.py tests/test_ge_ocr_crop_quality.py tests/test_ge_ocr_selection.py tests/test_ge_english_evidence.py tests/test_ge_script_evidence.py tests/test_ge_ocr_occurrence_scoring.py -p no:cacheprovider
& $python scripts/ge64_completion_evidence.py --observations $knownObservations --regions $knownRegions --output $newGlyphOutput
& $python scripts/ge64_score_trial.py --output $newGlyphOutput --reference $savedEvaluationReference
& $python scripts/ge64_image_trial.py --pdf $pdf --output $newRun --pages 78
& $python scripts/ge64_score_trial.py --output $newRun --pdf $pdf
```

The commands show the original frozen page-78 procedure; page 78 is now known and requires `--development` for a new reproduction plan. A new fresh trial must choose other unused pages. Use new ignored output directories. Known-page reruns require `--development` and stay development even when reference extraction follows recognition. Broad chunks are optional through `--chunk-rows`; default recognition is individual rows. Full PDFs/images/responses remain local under `outputs/ge64_test_completion_20261009/`.

## Final whole-change review

The fresh reviewer found three Important guard gaps: an unread upper Thai title could promote a footer after English; a multi-course response could supply required-row votes; empty/malformed successful OCR responses could leave the gate open. Each has a failing regression followed by a passing fix. Required multi-row responses are now refused and recorded as failures; empty runner responses close scoring gates; empty region responses abort completion. The complete related suite passes128 tests plus7 subtests. No Critical findings or deferred minors were raised.

Page78 remains the historical four-record frozen result under its original source snapshots. Guard changes receive a new untouched page79 trial rather than rewriting earlier artifacts. The `report_sha256` metadata in the historical summary hashes `score.json`, not the runner completion `report.json`.

## Subsequent DB authorization

The no-DB statements above describe the completed OCR phase before the user's later authorization. See [the separate GE66 promotion report](ge66-db-promotion-2026-10-09.md) for the full303-course evidence, five targets, backups and rollback verification. Partial GE64 samples never replace the current GE66 catalog.

## Final-policy untouched page79

After the three review guard fixes, untouched page79 was frozen at6f5037e and recognized before extracting reference text. Result:2/3 exact and selected, zero selected errors/extra codes/transport failures, one English title withheld (90642125). Both full-coverage gates remain FALSE. Six selected fields trace to raw OCR; three completion hashes and ten source snapshots verified. All three reference courses overlap GE66 content: this tests new page images, not unseen course content.

Image-only diagnosis: Tesseract's bounded reading adds a terminal period, while independent Typhoon reads the same literal title without it. The retained image shows why independent confirmation is still necessary. The complete-title conflict guard correctly withholds rather than editing punctuation or borrowing a reference answer. This is a preserved failing coverage gate, not a new passing accuracy claim or a blocker to the separately verified full GE66 catalog. The final policy does not promise automatic certification of every unseen title.
