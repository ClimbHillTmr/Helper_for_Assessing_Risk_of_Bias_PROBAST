# Contributing to Medical Research Harness

Thank you for contributing to **Medical Research Harness** (`skills/medical-research-harness/`). This toolkit provides deterministic manifest auditing, cross-phase workflow orchestration, read-only project auditing, and verbatim-citation-verified literature engineering-risk analysis for clinical prediction research.

## Core Design Principles & Boundaries

1. **Zero Third-Party Runtime Dependencies**: All core scripts in `skills/medical-research-harness/scripts/` must use the Python 3.10+ standard library only. Do not add model training, clinical decision support, or automated data-cleaning modules to this repository.
2. **Strict Patient Privacy & Data Isolation**: Never include patient-level rows, row-level predictions, embeddings, maintainer local paths, or credentials in code, tests, skills, or commit history. All repository tests must use isolated synthetic fixtures or legally licensed public Open Access (CC BY 4.0) JATS XML snapshots.
3. **Epistemic Integrity**:
   - Deterministic software checks verify file hashes, manifest membership invariants, and run-registry reconciliation; they never grant scientific approval (`scientific_acceptance: false`, `execution_authorized: false`).
   - Do not silently alter study populations, endpoints, index times, predictor availability windows, split structures, or primary metrics to make a check pass.
   - Retain all failed, aborted, negative, and unexecuted (`NOT_RUN`) attempts in reconciliation outputs.
4. **Synchronized Skill Artifacts**: Any change to CLI contracts or phase gates must synchronize `SKILL.md`, `references/`, `assets/`, and corresponding offline tests.

## Running the Offline Verification Suite

Before submitting a pull request, run the offline verification suite from the repository root (requires Python 3.10+ only). If you installed the CLI package (`python3 -m pip install -e .`), verify both the CLI self-test entrypoint and the full standalone script suite:

```bash
# Installed CLI self-test entrypoint (optional if running zero-install)
medical-research-harness selftest
medical-research-harness selftest --out build/selftest-demo

# Direct zero-install standard-library test suite
python3 skills/medical-research-harness/scripts/test_check_bundle.py
python3 skills/medical-research-harness/scripts/test_study.py
python3 skills/medical-research-harness/scripts/test_workflow.py
python3 skills/medical-research-harness/scripts/test_project_audit.py
python3 skills/medical-research-harness/scripts/test_decision_agent.py
HERMES_ADAPTER_ROOT=/nonexistent python3 skills/medical-research-harness/scripts/test_hermes_decision_adapter.py -v
python3 skills/medical-research-harness/scripts/test_laya_decision_adapter.py -v
python3 skills/medical-research-harness/scripts/test_literature.py
python3 skills/medical-research-harness/scripts/test_literature_design.py -v
python3 skills/medical-research-harness/scripts/test_literature_model_adapter.py
python3 skills/medical-research-harness/scripts/test_literature_recovery.py
python3 tests/test_literature_boundaries.py
python3 tests/test_literature_p2_repairs.py
python3 tests/test_literature_offline_resume.py
python3 tests/review_probes.py --out build/review-probes-check
```

Note: `--out` directories must not exist prior to execution.

## Reporting Issues

When reporting bugs or proposing methodological rules, specify:
- Which component is affected (`medical-research-harness` CLI / `mrh`, `study.py`, `workflow.py`, `check_bundle.py`, `project_audit.py`, `literature.py`, `literature_design.py`, or `decision_agent.py`).
- A minimal synthetic reproducer (never include private patient data).
- The expected deterministic diagnostic or failure state.
