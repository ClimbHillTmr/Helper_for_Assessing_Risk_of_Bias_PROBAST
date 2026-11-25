# JOSS supplement validation — 2026-11-13

This is a software/document revision record, not scientific acceptance or editorial approval.

- Manuscript: 1,095 whitespace-delimited body words, eight required sections; structural checks pass. DOI checks verify syntax only, ORCID checks verify checksum only.
- All 17 test entrypoints pass in this revision, including the two mandatory minimal checks, recovery tests, and 76 independent-origin regression probes. See validation_results.json. The Hermes live integration test is intentionally skipped without explicit integration enablement.
- The earlier audit's Hermes ProcessLookupError is retained as a failure in the session log; it occurred between /proc existence and content access. The revised observer catches process disappearance at read time; it still fails if a live descendant remains after the observation window. No production adapter behavior was changed.
- Historical literature completion: 4/4 listed file hashes match. Original response-byte retention remains missing; no scientific or semantic validation is implied.
- Local PDF rebuilt with Pandoc/citeproc/XeLaTeX, four pages rendered and visually inspected. Updated architecture figure uses row-level metadata terminology and does not promise identical safety fields on every output. This is not an official JOSS template build.
- Official compilation: Docker socket access denied in this environment. Added an Open Journals draft-action workflow using the documented paper-path interface; not run or reported as passing.
- Fresh read-only review of the changed checker, CI, manuscript, figure labels and test diff found no changes to cohort definitions, research endpoints, splits, approvals, or experimental outputs. The reviewer was the same assistant in a separate inspection pass, not an independent human reviewer.
- Default readiness command deliberately returns exit 1 while the five evidence gates are pending. CI structural-only mode does not bypass or clear those gates.

Reproduce the public regression with a new output directory:

```bash
python3 skills/medical-research-harness/scripts/test_check_bundle.py
python3 skills/medical-research-harness/scripts/test_study.py
python3 tests/test_joss_readiness.py
python3 tests/review_probes.py --out /tmp/mrh-new-review-probes
```

No submission, new release, clinical experiment, or human approval was performed. Author confirmation and editor-reviewable research use remain outstanding as itemized in SUBMISSION_CHECKLIST.md.
