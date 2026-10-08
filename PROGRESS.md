# OCR progress on dev/tests

Continuation in this worktree; prior source-branch logs were read only and remain in their original location.

## Saved-evidence selection replay (2026-10-08 22:29)
- Continued only in `dev/tests` from `e331e5b`; inspected the two pending selector/test diffs before edits. Added conservative Thai/English substring conflict review and English/clipped-observation regressions.
- Saved evidence pages 139-146: frozen 97/104 exact; current guard 93/104 exact, all 93 selected correct, eleven withheld, 23 review entries, no extra codes. Four newly withheld codes: 90643011, 90643016, 90643024, 90643030. All 279 fields trace to OCR; original ten evidence input hashes unchanged. Gate fails; development replay, not a fresh held-out score.
- Frozen normalized candidate content/score reproduced; raw Thai 90644061 differs only in NFKC-equivalent sara-am representation. No claim of identical candidate bytes. PDF text-layer oracle; 93/104 content overlap; no new recognition or reference fills.
- Tests: 50 local tooling passed; 67 combined passed with read-only source parser. dev/tests parser lacks eight existing format fixes: direct combined run 59 passed / 8 failed after the two added regressions. Source/parser/database/catalog/Gold/main unchanged; no database access or fresh production hash verification.
- Evidence report: `docs/ge64-pages139-146-replay-2026-10-08.json`; method and limits: `docs/ge66-word-evidence-2026-10-08.md`. Next: independent evidence for withheld rows, then a genuinely untouched sample. Delivery commit/push will be verified after scoped staging.

## Image OCR follow-up (2026-10-09 02:49)
- Previous replay delivery c2cfac2 was pushed and verified. Integrated only the existing parse_ge_ocr fixes; eight old format failures resolved. Added pixel table-cell bounds, image code-anchor left bounds, full-width English fallback and complete-title agreement regression.
- Known pages 139-146: shipped-helper development diagnostics 101/104 exact, all 101 selected correct; 90643017, 90643027, 90643037 withheld. Local unshipped one-peer experiment 102/104; do not present it as shipped/fresh accuracy. Original saved evidence unchanged.
- Initial 147-154 layout attempt interrupted during 149 and retained with frozen sources/40 cached responses, no full score/reference. Fresh frozen 150-154 completed: 42 occurrences/34 codes; 90643006 has conflicting PDF titles, excluded from aggregate. 30/33 unambiguous exact, 31 selected, error 90642113 English association, two unambiguous withheld, no extra codes/transport failures. Page 154 contains no course rows. Gate fails; no reference-driven recognition changes.
- 75 focused standalone tests passed; no database/API suite. No frontend, database, catalog/Gold promotion or main merge. Reports: docs/ge64-table-cell-followup-2026-10-09.md and docs/ge64-followup-summary-2026-10-09.json.
- Next: image-only diagnosis of selected association error and independent evidence for withheld titles before another frozen sample. Commit/push follows scoped staging and remote verification.
