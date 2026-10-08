# GE66 OCR data and Text-layer backup

The five canonical SQLite databases (AIT, DSBA coop/no-coop, IT coop/no-coop)
load their GE66 elective catalog from verified image OCR by Tesseract and Typhoon.
The catalog contains 303 courses; all 909 Thai-name, English-name and complete
credit fields trace to raw OCR. The Text-layer catalog was used for development
evaluation, never as OCR prompt content or replacement field values.

Only the GE66 groups and their courses were reloaded. Course plans, prerequisites,
other elective groups, program graduation requirements, BIT and retry databases
were preserved. This does not certify OCR of the entire PDF or other documents.
The database schema stores integer credits; the complete lecture/lab/self-study
structure and S/U flags remain in `runs/ge66_catalog.json`.

`runs/ge66_ocr_provenance.json` records catalog/database checksums, the previous
Text-layer checksums and the local backup location. Evidence is on `dev/tests`
at commit `c5cb3aa`. The original tracked data is available in Git at `2a7af2e`.
Local backup copies, staging copies and restore helpers are ignored by Git.

## Verify or restore on the migration machine

Run from the project root. This first command verifies all five SQLite backups,
their integrity and checksums, and the original catalog without changing data:

```powershell
$ge66Record = Get-Content 'Lab7B_Lab8B_ocr_system/runs/ge66_ocr_provenance.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$ge66Restore = Join-Path $ge66Record.text_layer_backup 'restore_text_layer.py'
.venv\Scripts\python.exe -X utf8 -B $ge66Restore --root .
```

To restore the Text-layer databases and catalog, close database writers and run:

```powershell
.venv\Scripts\python.exe -X utf8 -B $ge66Restore --root . --apply
```

The helper refuses to overwrite live data changed after promotion or a backup
whose checksum no longer matches. It retains the OCR provenance in the backup
directory when restoring. A fresh clone uses the committed OCR databases; the
local backup directory exists only on the machine that performed the migration.

Validation: 1,014 regressions passed; 20/20 backend comparisons and 20/20 live API
Q&A comparisons matched the Text-layer backups, GE search passed for all five
plans, and all seven program endpoints remained available. Backups were verified
with the restore helper in its read-only mode.
