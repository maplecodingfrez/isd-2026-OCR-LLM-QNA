# GE64 OCR Completion Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Repair image row association, acquire literal glyph evidence, preserve conflicting printed occurrences, and verify a frozen untouched sample before scoped dev/tests delivery.
**Architecture:** Geometry comes from image OCR word boxes and pixel rules. Keep every printed code position, recognize bounded individual rows, and retain raw field provenance. Separate page occurrences from the unique catalog; printed title conflicts are explicit review records, never guessed canonical values.
**Tech Stack:** Python standard library, Pillow, PyMuPDF, pytesseract, existing local Typhoon OCR service; no installation.
**Spec:** User request in this session and docs/ge64-table-cell-followup-2026-10-09.md.

## Global Constraints
- Work only in D:\DSBA 3rd Year\Works\_codex_worktrees\dev-tests-commit on dev/tests; do not touch feature/lab11-frontend or databases.
- Reference text is evaluation-only; never fill or correct OCR fields from it. Preserve old frozen runs.
- Retrieve Context7 documentation before changing external-library calls.
- Engine families, not repeated variants, supply independent votes. Meaningful punctuation/Thai marks are literal.
- Commit/push only related source, tests, plans, reports and appended project logs after an allowlist check. No merge or production promotion.

## Review Focus
- A repeated code at another y-position must terminate the previous row.
- Footer Thai after an English title must never become a Thai title region.
- Two engines reading the same wrong multi-row crop must not establish row association.
- Printed titles differing by page remain separate occurrences and unresolved canonical conflicts.
- Failed or empty OCR must keep the gate closed; provenance must be reproducible without raw-response fabrication.

### Task 1: Bound individual image occurrences
**Files:** Modify scripts/ge66_crop_quality.py, scripts/ge66_script_evidence.py, scripts/ge64_image_trial.py; test tests/test_ge_ocr_crop_quality.py, tests/test_ge_script_evidence.py.
**Interfaces:** code_anchor_occurrences(readings) consumes global pixel code boxes and returns y-sorted anchors with code, top, left, height; duplicates at the same location merge, duplicates at another position remain. thai_title_image(image) returns only the initial Thai title block before a separate English line. The runner consumes every occurrence and bounds row retries at the next anchor.
- [x] Add regression fixtures with code 90643021 at y=100 and y=300 plus a duplicate detection at y=102; expected positions [100,300]. Assert no merge for different codes sharing y.
- [x] Add a synthetic title/English/footer OCR-word fixture; assert Thai crop excludes footer pixels and English text. Add a multi-code row refusal fixture.
- [x] Run these regressions and observe failure before implementation. Expected: missing occurrence helper and footer included by old crop.
- [x] Implement position-based merging: sort anchors, merge only equal code with intersecting vertical intervals and adjacent left positions; retain every other anchor. Restrict Thai words to lines before the first separate English line below the first Thai line.
- [x] Update runner to combine code-column and full-page detections through code_anchor_occurrences, retaining code repeats. Recognize each bounded row; never send a multiple-code region as field evidence.
- [x] Run all five database-free OCR test modules. Expected: green. Commit narrow task checkpoint.

### Task 2: Literal glyph evidence and occurrence selection
**Files:** Modify scripts/ge66_script_evidence.py, scripts/ge66_select_candidate.py; create scripts/ge64_completion_evidence.py; tests in tests/test_ge_script_evidence.py and tests/test_ge_ocr_selection.py.
**Interfaces:** select_occurrences(observations) consumes raw page/occurrence-qualified observations and returns selected page records plus reviews; unique catalog output continues to reject conflicting printed names. Completion evidence CLI consumes local images/old raw observations and writes a new isolated run, preserving original bytes.
- [x] Add a wrapped raised-word test whose line has one reliable peer and another line supplies a consistent baseline height; assert actual base/raised OCR readings concatenate literally. Add a conflicting-height refusal test.
- [x] Add occurrence-selection tests with same code and two distinct printed page titles; expected two page records and canonical conflict retained.
- [x] Run regressions red, then implement only validated baseline geometry and occurrence grouping. No ordinal spelling or course-specific replacement rules.
- [x] Acquire bounded native/scale/binarization and word-image reads for all remaining known-page glyph conflicts using existing engines, save raw responses and model/image hashes, then score separately. Reference values never enter recognition prompts.
- [x] Re-evaluate new individual-row reads on pages 150-153 as development evidence. Verify 90642113 association from pixels, 90642132/90643030 completeness, and both 90643006 printed titles. Preserve unresolved fields if images/engines cannot establish them.
- [x] Run all database-free OCR tests, raw-value provenance assertions and immutable-input checks; commit the evidence tooling and regression checkpoint.

### Task 3: Frozen untouched image evaluation
**Files:** Modify scripts/ge64_image_trial.py and scripts/ge64_score_trial.py only as needed for occurrence outputs and strict scoring; tests tests/test_ge_ocr_selection.py; reports docs/ge64-completion-2026-10-09.md and docs/ge64-completion-summary-2026-10-09.json.
**Interfaces:** runner completion marker precedes text-layer extraction; scorer checks frozen sources and immutable candidate/observation hashes and reports occurrence and unique-catalog gates separately.
- [x] Add tests that selection cannot mix titles from different pages and a conflicted unique catalog cannot pass a gate.
- [x] Freeze PDF/model/prompt/source/geometry before opening untouched pages 32-35, then 72-75, 76-77 and page 78 in separately preserved attempts (see ledger rulings). Exclude all previously used pages including 147-154; retain known-page development as a different scope.
- [x] Run full frozen recognition to completion, then extract reference text for scoring. Expected: immutable OCR hashes and complete per-page accounting, with actual correctness/gate recorded honestly.
- [x] If recognition or scoring reveals failures, retain the failed frozen run; diagnose with regression tests and use another untouched frozen sample after fixes. Never rewrite an old run into a passing claim.
- [x] Write exact metrics, reviewed conflicts, unresolved glyphs if any, zero-error gates and local evidence hashes to the portable reports.

### Task 4: Review and deliver
**Files:** Update PROGRESS.md, append .claude-mem/timeline.md, link final report from docs/ge64-table-cell-followup-2026-10-09.md; retain this plan and execution ledger summary.
**Interfaces:** final review consumes complete change range, plan/spec, raw verification evidence and ledger rulings.
- [ ] Dispatch one fresh whole-change reviewer as required by executing-plans; implementer remains inline. Review association, engine independence, reference leakage, occurrence conflicts, gates and scoped paths.
- [ ] Fix critical/important findings with failing regressions followed by green tests; record rulings and deferred minor findings.
- [ ] Run six related OCR modules including new completion tests without DB/API suite, git diff --check, frozen/original hash checks and staged file allowlist. Expected: all checks pass and only related files staged.
- [ ] Commit, push HEAD:dev/tests, compare remote SHA via git ls-remote and verify clean worktree and unchanged frontend branch. Report actual gates and any remaining evidence limitations without claiming arbitrary-document perfection.
