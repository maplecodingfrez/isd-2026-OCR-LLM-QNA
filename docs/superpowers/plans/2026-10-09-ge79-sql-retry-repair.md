# Page79 literal English and SQL retry repair

> **For agentic workers:** Use superpowers:executing-plans inline, one fresh final whole-change reviewer, observed RED/GREEN and verification-before-completion.

**Goal:** Resolve page79's withheld90642125 English title from image evidence and distinguish exhausted SQL retries from a successful empty query.
**Architecture:** Enlarge all-ink-bounded English pixels2x with white padding before either engine reads; retain every punctuation pixel, wrapped line and original crop metadata. Change only the exhausted-retry answer branch; keep errors and ordinary empty-results behavior.
**Tech Stack:** Existing Pillow/Tesseract/Typhoon and Python standard-library backend. Current Pillow docs consulted via Context7.
**Spec:** User explicitly requests fixing both remaining limitations. Existing dev/tests-only, source/frontend protection and authorized commit/push remain.

## Review Focus
- A real period or apostrophe must survive image scaling; no title string editing, dictionary/reference fills or weaker independent-family voting.
- Blank crops and wrapped lines must remain safe; frozen page79 failure must stay unchanged.
- SQL failures must remain errors after two attempts; second-attempt success and valid empty queries must clear errors and behave normally.
- All existing DB/catalog/Gold bytes stay unchanged: this is code repair only.

### Task 1: Exhausted SQL failure semantics
**Files:** lab8b_curriculum_db.py, tests/test_lab8b_electives.py.
- [x] Reproduce existing failure and add successful-empty/retry-recovery regressions.
- [x] Change only exhausted-retry answer, preserve errors; run related backend suite and commit.

### Task 2: Pixel-preserving English recognition
**Files:** scripts/ge66_english_evidence.py, scripts/ge64_image_trial.py, tests/test_ge_english_evidence.py, tests/fixtures/ge79_english_title.png.
- [x] Add failing real-image and synthetic punctuation/wrap/blank regressions.
- [x] Bound all foreground pixels including tiny punctuation, upscale2x and pad; retain metadata and engine voting. Run whole focused suite and commit.
- [x] Rerun79 in a new development directory to3/3, then freeze untouched80 under final source hashes. Preserve old failed scores.

### Task 3: Review and delivery
- [x] Complete untouched80=3/4 and preserve its failed score; repair90642128 in separate development1/1, compose4/4, then freeze/score untouched81 under final policy. Verify all hashes before delivery.
**Files:** new report/plan, PROGRESS.md, append .claude-mem/timeline.md; link historical completion report.
- [x] One fresh final reviewer; author closes declined final checks and fixes observed80 count-mismatch gap in the single RED/GREEN fix pass.134 OCR tests+7subtests; complete1179passed/3skipped/7subtests. Record decisions/minors.
- [x] Verify protected DB/catalog/Gold/source hashes, exact14-file allowlist, tests and diff checks; commit/push dev/tests. Completion is gated by post-push remoteSHA/clean tree check; final message reports actual delivery.

**Final fix pass:** scripts/ge66_script_evidence.py and tests/test_ge_script_evidence.py add all-image-word recovery for unaligned short titles (max8), without Tesseract text fills. Preserve initial80 failure; final new-image validation uses81.
