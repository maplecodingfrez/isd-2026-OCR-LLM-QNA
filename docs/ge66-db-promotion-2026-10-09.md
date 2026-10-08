# GE66 image OCR database promotion — 2026-10-09

The user authorized replacing the Text-layer GE66 catalog after the OCR fixes. The dev/tests worktree contains five full GE66/2566 databases. The separate feature/lab11-frontend checkout already uses OCR and remains read-only.

## Prepared evidence and staging

- Full historical GE66 image catalog: 303 unique courses, 909 literal selected fields traceable to archived OCR on the candidate page, zero manual fills. Curly apostrophes in MY DOG’S MY BOSS and MY CAT’S MY BOSS come from their retained Tesseract text/image files.
- This is existing development-verified data, separate from the GE64 frozen-page evaluation; it is not a new unseen whole-document accuracy result.
- Five staged SQLite copies update only names and integer credits of existing GE66 elective courses. Course/group IDs, schema, other elective courses and every other table remain unchanged. Integrity and FK checks pass.
- Four deterministic backend questions per DB: 20/20 rows and answers match previous Text-layer results after NFKC/whitespace normalization. No LLM requests or new models.
- BIT has no GE66 groups; both BIT DBs and Gold remain unchanged. No entire DB is copied from the frontend checkout.
- Regression suite: 124 tests plus 3 subtests pass. Drift refusal, staged scope preservation, partial-install rollback and restoration are covered.

## Install and rollback

Preparation manifest and exact backups are in `outputs/ge66_db_test_migration_20261009/manifest.json`. The manifest is initially prepared: no target DB or catalog has been replaced. Review covers the complete OCR and migration change before install.

```powershell
python scripts/ge66_promote_db.py install --manifest outputs/ge66_db_test_migration_20261009/manifest.json
python scripts/ge66_promote_db.py restore --manifest outputs/ge66_db_test_migration_20261009/manifest.json
# Only when rollback is intended, after stopping DB writers:
python scripts/ge66_promote_db.py restore --manifest outputs/ge66_db_test_migration_20261009/manifest.json --apply
```

Install and restore refuse target, backup or staging hash drift. Existing SQLite sidecars block migration. Each replacement is atomic; an ordinary install exception restores files already replaced. This is an offline local operation: stop DB writers. Multi-file replacement cannot be atomic across a machine/process crash; retain the manifest/backups for recovery. Restore refuses unrelated intervening changes.

The JSON report records exact evidence/file hashes, protected table snapshots and all 20 comparisons. The original OCR evidence and failed fresh evaluations remain preserved.

## Review and broader check

The final fresh whole-change review found no Critical/Important migration issue. All three Important OCR guard findings were fixed with observed RED-to-GREEN regressions; final related suite128 tests plus7 subtests. No deferred minors.

Additional existing backend checks:1042 passed,3 skipped,1 failed (`test_exhausted_sql_retries_report_query_failure`). The same failure was reproduced with the ac01dd3 pre-change backend Git blob before target installation: exhausted SQL retries report not-found instead of a query error. Backend code remains unchanged; this existing general-query behavior is outside the OCR/catalog-data change. The dedicated20/20 catalog comparisons pass.

Full-data rollback rehearsal installed all five303-course DBs and the catalog/provenance in disposable copies, then restored the six original files byte-for-byte and removed the newly created provenance file. Seven backup/target entries checked; actual target files remained unchanged during the rehearsal.

## Installed result

The reviewed manifest was applied only to the five dev/tests target databases and catalog/provenance. Live checks confirm303 GE66 rows in each DB, all protected tables/schema/IDs unchanged,20/20 backend comparisons, and all seven restore entries validated without applying rollback. Both BIT DBs, Gold, source checkout DB/catalog bytes and feature/lab11-frontend ref remain unchanged. Exact installed file hashes are in the JSON report. Full restore rehearsal also passed on disposable copies.

The post-review GE64 page79 transfer sample is separately preserved at2/3 exact, one English punctuation disagreement withheld, no selected errors, coverage gate FALSE. It is not the source of the promoted complete GE66 data, and no partial sample is substituted into the current DB.
