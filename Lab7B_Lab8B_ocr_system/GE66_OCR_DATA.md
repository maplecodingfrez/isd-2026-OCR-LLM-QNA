# GE66 image OCR catalog on dev/tests

The five canonical GE66/2566 plan databases (AIT, DSBA coop/no_coop, IT coop/no_coop) use the full303-course image OCR catalog from `runs/ge66_catalog.json`; provenance is recorded in `runs/ge66_ocr_provenance.json`. BIT has no GE66 catalog and is unchanged.

This catalog was historically development-verified against the official PDF:909 selected fields match archived raw OCR, zero manual fills. Reference was used for development/evaluation, never as an OCR prompt or field fill. This is not a claim of independent human ground truth or unseen whole-document accuracy. GE64 diagnostic samples remain separate.

Migration updates only existing GE66 elective names and integer credits, keeping IDs, schema, other elective rows and all other curriculum tables. Detailed credit structures, page numbers and S/U metadata remain in the catalog. Four deterministic backend questions per target match the previous catalog:20/20.

See [promotion evidence and rollback](../docs/ge66-db-promotion-2026-10-09.md). Backups and checked manifest remain locally under `outputs/ge66_db_test_migration_20261009`; stop writers before migration or restore. Verification-only rollback command:

```powershell
python scripts/ge66_promote_db.py restore --manifest outputs/ge66_db_test_migration_20261009/manifest.json
```

Add `--apply` only when rollback is intended. Restore refuses intervening edits or changed backups. The frontend checkout is read-only and already has image OCR data; this delivery changes dev/tests only.
