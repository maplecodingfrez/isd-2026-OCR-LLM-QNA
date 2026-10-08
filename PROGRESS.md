# OCR progress on dev/tests

Continuation in this worktree; prior source-branch logs were read only and remain in their original location.

## Saved-evidence selection replay (2026-10-08 22:29)
- Continued only in `dev/tests` from `e331e5b`; inspected the two pending selector/test diffs before edits. Added conservative Thai/English substring conflict review and English/clipped-observation regressions.
- Saved evidence pages 139?146: frozen 97/104 exact; current guard 93/104 exact, all 93 selected correct, eleven withheld, 23 review entries, no extra codes. Four newly withheld codes: 90643011, 90643016, 90643024, 90643030. All 279 fields trace to OCR; original ten evidence input hashes unchanged. Gate fails; development replay, not a fresh held-out score.
- Frozen normalized candidate content/score reproduced; raw Thai 90644061 differs only in NFKC-equivalent sara-am representation. No claim of identical candidate bytes. PDF text-layer oracle; 93/104 content overlap; no new recognition or reference fills.
- Tests: 50 local tooling passed; 67 combined passed with read-only source parser. dev/tests parser lacks eight existing format fixes: direct combined run 59 passed / 8 failed after the two added regressions. Source/parser/database/catalog/Gold/main unchanged; no database access or fresh production hash verification.
- Evidence report: `docs/ge64-pages139-146-replay-2026-10-08.json`; method and limits: `docs/ge66-word-evidence-2026-10-08.md`. Next: independent evidence for withheld rows, then a genuinely untouched sample. Delivery commit/push will be verified after scoped staging.
