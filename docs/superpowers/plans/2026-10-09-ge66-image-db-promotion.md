# GE66 Image OCR Database Promotion Plan

> **For agentic workers:** Use superpowers:executing-plans inline; one final whole-change reviewer covers this extension and the OCR repair plan. Steps use checkboxes.

**Goal:** Replace the GE66 Text-layer catalog in the five canonical dev/tests SQLite databases with the already verified full 303-course image OCR catalog.
**Architecture:** Verify all 909 fields against archived raw observations and candidate values. Back up the original catalog/DBs, stage transactionally in SQLite copies, preserve schema/other curriculum data, compare backend answers, then install only checked files with rollback on failure.
**Tech Stack:** Python standard library (sqlite3, pathlib, hashlib, JSON), existing deterministic curriculum backend. No schema migration, new dependencies or model requests.
**Spec:** User's additional request to use OCR in the current DB instead of Text Layer after fixing OCR; initial dev/tests-only/frontend protection still applies.

## Global Constraints
- Work only in the dev/tests worktree; the existing source checkout and feature/lab11-frontend remain read-only.
- Use the full GE66 edition2566 catalog, not partial GE64 samples. BIT has no GE66 catalog and remains unchanged.
- Five targets: AIT, DSBA/coop, DSBA/no_coop, IT/coop, IT/no_coop curriculum.db; only existing GE66 elective course name/credit rows may change.
- Preserve course/plan/prerequisite/program tables, unrelated elective groups, IDs, schema, Gold, and original OCR evidence.
- Existing full GE66 data is historical development-verified OCR: 303/303 exact,909 fields raw-traceable, no manual field fills. No new whole-PDF/unseen accuracy claim.
- Prepare backups/staging/manifest before replacing target data; reject input/target drift; provide a checked restore path.

## Review Focus
- Partial/wrong-edition catalogs must never erase existing courses.
- Every selected catalog field must match actual archived OCR, including literal curly apostrophes.
- Migration must retain other tables, elective groups, IDs and schema.
- Changed live/staged/backup hashes must block install/restore; partial install failure must restore prior files.
- Source checkout already has OCR DBs: never copy entire source DBs or mutate the frontend checkout.

### Task 1: Reversible migration tooling
**Files:** scripts/ge66_promote_db.py, tests/test_ge66_db_promotion.py.
**Interfaces:** verify_catalog(catalog,candidate,observations,summary,expected=303) rejects partial/untraceable data; stage_database(source,destination,catalog) updates only existing GE66 elective course fields in a copy; install/restore consume hash-checked manifests.
- [x] Add and observe failing raw-provenance, scope preservation, transactional refusal and drift/rollback regressions.
- [x] Implement minimal standard-library helpers; run full related OCR and migration tests. Expected: green and no live writes.
- [x] Commit the tested tooling checkpoint.

### Task 2: Full-catalog preparation and comparison
**Files:** ignored outputs/ge66_db_test_migration_20261009, docs/ge66-db-promotion-2026-10-09.md/json; staged runs/ge66_catalog.json and ge66_ocr_provenance.json.
**Interfaces:** prepare CLI consumes the unchanged existing source OCR catalog/candidate/raw evidence, creates five backups and staged copies plus a manifest.
- [x] Verify303 unique records,909 raw fields, page/SU metadata and historical source evidence hashes. Expected: full coverage; reference is comparison only.
- [x] Back up original Text-layer files and prepare five copies; verify integrity/FKs/non-GE snapshots/schema. Expected:303 GE66 rows each, BIT and source hashes unchanged.
- [x] Compare four deterministic backend catalog questions per target. Expected:20/20 answers/rows match previous data after NFKC/whitespace-only normalization.
- [x] Write reviewable metrics, rollback instructions and actual scope limitations.

### Task 3: Final review, apply and deliver
**Files:** five curriculum.db targets, runs/ge66_catalog.json/provenance, Lab7B_Lab8B_ocr_system/GE66_OCR_DATA.md, both plans/reports, PROGRESS.md and append-only timeline.
**Interfaces:** original fresh reviewer resumes after the usage reset and reviews the complete OCR+DB range once; checked manifest installs the reviewed staging only.
- [x] Resume the original required whole-change reviewer (initial attempt hit quota before a verdict); handle Critical/Important in one RED-GREEN pass and ledger minors/rulings.
- [x] Apply the manifest after review and recheck live data/schema/other tables, all seven program DBs and backup restore validation. Expected: five use303 OCR rows; BIT/source unchanged.
- [x] Run relevant regression checks, exact file allowlist and diff --check; commit/push HEAD:dev/tests and verify remote SHA/clean tree/frontend ref.
