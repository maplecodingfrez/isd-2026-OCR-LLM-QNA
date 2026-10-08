## 2026-10-08 22:29 - Saved-evidence OCR selection replay
- Continued only in `dev/tests` from `e331e5b`; inspected the two pending selector/test diffs before edits. Added conservative Thai/English substring conflict review and English/clipped-observation regressions.
- Saved evidence pages 139?146: frozen 97/104 exact; current guard 93/104 exact, all 93 selected correct, eleven withheld, 23 review entries, no extra codes. Four newly withheld codes: 90643011, 90643016, 90643024, 90643030. All 279 fields trace to OCR; original ten evidence input hashes unchanged. Gate fails; development replay, not a fresh held-out score.
- Frozen normalized candidate content/score reproduced; raw Thai 90644061 differs only in NFKC-equivalent sara-am representation. No claim of identical candidate bytes. PDF text-layer oracle; 93/104 content overlap; no new recognition or reference fills.
- Tests: 50 local tooling passed; 67 combined passed with read-only source parser. dev/tests parser lacks eight existing format fixes: direct combined run 59 passed / 8 failed after the two added regressions. Source/parser/database/catalog/Gold/main unchanged; no database access or fresh production hash verification.
- Evidence report: `docs/ge64-pages139-146-replay-2026-10-08.json`; method and limits: `docs/ge66-word-evidence-2026-10-08.md`. Next: independent evidence for withheld rows, then a genuinely untouched sample. Delivery commit/push will be verified after scoped staging.
tags: OCR, GE64, GE66, regression, review, dev/tests

## 2026-10-09 02:49 - Image OCR follow-up
- Previous replay delivery c2cfac2 was pushed and verified. Integrated only the existing parse_ge_ocr fixes; eight old format failures resolved. Added pixel table-cell bounds, image code-anchor left bounds, full-width English fallback and complete-title agreement regression.
- Known pages 139-146: shipped-helper development diagnostics 101/104 exact, all 101 selected correct; 90643017, 90643027, 90643037 withheld. Local unshipped one-peer experiment 102/104; do not present it as shipped/fresh accuracy. Original saved evidence unchanged.
- Initial 147-154 layout attempt interrupted during 149 and retained with frozen sources/40 cached responses, no full score/reference. Fresh frozen 150-154 completed: 42 occurrences/34 codes; 90643006 has conflicting PDF titles, excluded from aggregate. 30/33 unambiguous exact, 31 selected, error 90642113 English association, two unambiguous withheld, no extra codes/transport failures. Page 154 contains no course rows. Gate fails; no reference-driven recognition changes.
- 75 focused standalone tests passed; no database/API suite. No frontend, database, catalog/Gold promotion or main merge. Reports: docs/ge64-table-cell-followup-2026-10-09.md and docs/ge64-followup-summary-2026-10-09.json.
- Next: image-only diagnosis of selected association error and independent evidence for withheld titles before another frozen sample. Commit/push follows scoped staging and remote verification.
tags: OCR, GE64, image-evidence, failed-gate, dev/tests

## 2026-10-09 05:33 - OCR final review and GE66 DB promotion
- Completed image-only known pages139-146 development104/104;42/42 printed occurrences150-153, genuine90643006 canonical Thai conflict retained. No spelling/reference field fills.
- Preserved earlier fresh failures13/15 and6/7; separate development repairs15/15 and7/7; historical frozen page78=4/4.
- Final fresh whole-change review:3Important OCR findings fixed with observed RED/GREEN tests (footer after missed Thai, multi-course row votes, empty/malformed responses). No Critical/Important DB findings or deferred minors. Final related suite128tests+7subtests passes.
- Final-policy frozen page79=2/3 exact, one English punctuation disagreement withheld, zero selected errors/failures; both coverage gatesFALSE. Raw OCR and ten snapshots preserved. No arbitrary-document/human-GT accuracy claim.
- Later explicit DB authorization applied full historical GE66/2566 imageOCR303courses/909rawfields to five dev/tests DBs and catalog/provenance. Live backend20/20; IDs/schema/other data unchanged. Seven checked restore entries; full five-DB byte-exact restore rehearsal passes. BIT/Gold/source/frontend untouched.
- Broader backend1042passed/3skipped/1pre-existing failure: exhausted SQL retries returns not-found. Reproduced on ac01dd3 backend Git blob; unrelated backend behavior unchanged.
- Original ten pages139-146 evidence hashes unchanged. Append-only timeline preserved including2026-10-08 22:29. Scoped delivery stays ondev/tests; no main merge or frontend deployment.
- Reports: docs/ge64-completion-2026-10-09.md, docs/ge66-db-promotion-2026-10-09.md; complete decisions/costs: docs/ge64-ge66-execution-decisions-2026-10-09.md.
tags: OCR, GE64, GE66, DB, rollback, review, dev/tests

## 2026-10-09 06:06 - Page79 English and SQL retry repair
- Page79 separate development3/3, both gates pass; original frozen2/3 retained unchanged.
- Initial untouched80=3/4 retained; new short-title word-image recovery repairs target1/1, known-page composition4/4. Each composed token is actual Typhoon output, no Tesseract/reference field fills.
- Final untouched81=3/3, both gates pass, zero errors/failures; recognition before reference extraction; raw completion/snapshot hashes verified. PDF Text Layer evaluation only; no arbitrary-document completeness claim.
- Exhausted SQL retries now report query failure, not successful not-found; valid-empty/recovery paths pass. Complete backend/OCR1179passed/3skipped/7subtests,zero failures.
- One fresh whole-change review; author fixes observed80 gap with3RED/GREEN regressions and final suite; no deferred minors.24 protected DB/catalog/Gold/source hashes unchanged; frontend ref untouched; timeline append-only.
- Scoped14-file delivery only todev/tests; existing commit identity, no Co-Authored-By trailer. Post-push remoteSHA and clean tree verification required; no DB mutation in this repair.
- Report: docs/ge79-sql-retry-repair-2026-10-09.md and companion JSON; plan records execution and decisions/costs.
tags: OCR, GE64, SQL-retry, dev/tests
