# Page79 English title and exhausted SQL retry repair — 2026-10-09

The user requested fixing the two limitations left by e1c91b0. Work stays in the dev/tests worktree; the five promoted GE66 databases and both BIT databases are not modified.

## Root causes and changes

- Page79 course90642125: the bounded English title has approximately22-pixel-high glyphs. Tesseract reads an invented terminal period; the retained image and independent Typhoon read have no period. Removing only blank margins did not help. Scaling the retained image2x makes Tesseract PSM6/7 read the literal title correctly.
- English regions now bound every nonwhite pixel (including tiny punctuation), upscale2x and add20-pixel white padding before either engine reads. Wrapped lines and original source crop metadata remain. No title string edits, dictionary rules, reference fills, engine-family changes or weaker conflict gates.
- The exhausted second SQL attempt returned the same NOT_FOUND text as a successful empty query. It now explains that the question could not be converted for searching and asks the user to rephrase, retaining the actual error. Valid empty results still return NOT_FOUND with error=None; second-attempt recovery is tested. No retries, SQL guards, model configuration or database schema are changed.

## Verification

The observed backend regression fails before the fix and passes after it. Broader backend suite:1045 passed,3 skipped, no failures. Additional retry boundary tests require one call for a valid empty query, two for recovered failure, and exactly two with no fabricated rows/answer/citations for exhausted failure.

Image tests fail before the new helper and pass afterward. They include the actual retained title image, isolated punctuation pixels, wrapped lines and blank regions. Final related OCR/migration suite:134 passed plus7 subtests. Tesseract is real for the image regression; slow model calls are mocked only in unit tests. Current Pillow and pytest documentation were consulted via Context7.

## Actual image results

| Evidence | Exact / expected | Status |
| --- | --- | --- |
| Original frozen79 | 2/3 | Preserved unchanged; no selected error |
| Separate development79 | 3/3 | Both coverage gates pass |
| Initial untouched80, before word recovery | 3/4 | Preserved unchanged; missing90642128 English; no selected error |
| Separate development80 target90642128 | 1/1 | Both gates pass; four independent word images reread |
| Development80 composition | 4/4 | Three original correct records plus new target evidence; never a fresh result |
| Final frozen untouched81 | 3/3 | Both coverage gates pass; no selected error |

Page80 revealed a second recoverable gap: Typhoon omitted comma/AND from the bounded whole title; the old retry refused four image word boxes versus three returned tokens. The final helper rereads every bounded word image for unaligned short titles, capped at8. Tesseract provides geometry only; every composed token comes from a new raw Typhoon image response. Empty or injected multiword responses and excessive work remain refused. Three regressions were observed RED before the change and GREEN after it. The actual responses are `ECOLOGY ,`, `CONSERVATION`, `AND`, `ENVIRONMENTALISM`. Their raw punctuation is retained; existing comparison normalization handles whitespace around punctuation.

All recognition completed before reference extraction/scoring. Every selected field traces to raw OCR, with three completion hashes and ten source snapshots verified per run. Page79 and initial80 share all reference content with the GE66 catalog. Final81 content overlap is 3/3. These are new image checks, not independent human ground truth or certification of every document/page. The companion JSON records exact scores, hashes, snapshots and the development composition inputs.

## Final verification and review

Complete12-module backend/OCR suite:1179 passed,3 skipped,7 subtests,zero failures45.96s. The exhausted-retry backend test and successful-empty/recovery boundary tests all pass. Real Tesseract image regression passes; unit-model mocks do not substitute for the separately recorded actual Typhoon image runs.

One fresh whole-change reviewer inspected e1c91b0..7dc76bb: no Critical/Important/Minor findings. It independently checked11 image tests,24 protected hashes and the development79 artifacts. Pending final evidence/log/delivery checks were assigned to the author. The author regraded the actual initial80 result into an Important recovery gap, fixed it once with three RED/GREEN cases and the complete suite; no second review is claimed for2290432. No deferred minors.

The24 protected DB/catalog/provenance/Gold/source file hashes match the starting values. Five dev/tests GE66 databases retain the previously promoted303-course OCR catalog; BIT remains unchanged. These code fixes do not require another data promotion. Source/frontend ref and append-only timeline prefix are checked. Final diff is limited to14 related files; delivery follows remote divergence/scoped staging checks and is verified by remoteSHA/clean tree. Existing configured commit identity is used, with no Co-Authored-By trailer added. Raw local evidence and execution ledger remain ignored rather than deleted.

## Execution decisions and costs

- Ruling: Execute inline and deliver to dev/tests under continuing authorization; cost: reversible scoped code changes and authorized shared-branch push.
- Ruling: Preserve previous page79 failed frozen result; rerun as development and use untouched80 for final-policy transfer; cost: more local OCR time and still limited sample, no arbitrary-document accuracy claim.
- Ruling: Preserve ignored execution evidence rather than deleting it; cost: local disk usage.
- Ruling: Move completed fresh80 scoring to final verification task while its frozen recognition runs; code/tests and development79 are complete for whole-change review. Cost: reviewer may decline final80 outcome; root must independently verify its immutable artifacts and actual gates before delivery.
- Final: Ruling: Reviewer declined pending fresh80/logs/remote checks; root must verify each before delivery underTask3. Cost: author performs final artifact/delivery verification, not the fresh reviewer.
- Final: Ruling: Small sample does not establish arbitrary-document OCR accuracy; cost: transfer beyond sampled page images remains unverified.
- Final: Ruling: Regrade declined fresh80 outcome as Important retry recovery gap: bounded Typhoon omits AND/comma and word retry refuses any count mismatch. Add all-image-word literal recovery with8boxcap in the single final fix pass, never Tesseract field fills. Cost: extra model requests and final new-policy validation.
- Final: Ruling: Retain failed fresh80=3/4 and score repaired90642128 as known-page development; freeze untouched81 for final policy. Cost: another small sample and local model time; no relabeling failed80 as held-out success.
