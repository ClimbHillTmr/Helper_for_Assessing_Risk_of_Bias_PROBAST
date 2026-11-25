# Real Clinical Study Integration Guide (Track 2 — JOSS Research-Use Evidence)

This guide defines the privacy-preserving, non-invasive procedure for integrating `medical-research-harness` into an authorized clinical prediction repository (such as an internal hemodialysis or longitudinal clinical risk-modeling study) to produce auditable, editor-reviewable **aggregate** research-use evidence without modifying study protocols or exposing patient data.

## 1. Strict Privacy & Protocol Boundaries

1. **Zero Protocol Mutation**: Do not alter cohorts, outcomes, index times, splits, primary metrics, or stopping rules to satisfy the harness.
2. **Private Manifests Stay Local**: Exported `rows.csv`, `folds.csv`, and `fits.csv` contain row-level metadata (`patient_id`, timestamps, fold assignments) and **must never** be copied into this repository or shared publicly.
3. **Executed Evidence Only**: Planned fit tables (`--mode planned`) check pre-execution design hygiene only. Real research-use evidence requires fresh post-execution verification (`study audit --mode executed`) bound to actual run logs plus `study summarize` retaining failed, aborted, and unexecuted runs.

## 2. Four-Step Non-Invasive Audit Workflow

Run inside a dedicated output folder inside the target clinical repository:

```bash
# 1. Freeze protocol & cohort/fold identities (produces DRAFT only)
medical-research-harness study plan --out audit_v1/plan path/to/study.json

# 2. Audit planned fit scopes before execution
medical-research-harness study audit --mode planned \
  --plan audit_v1/plan/plan.json \
  --fits path/to/planned_fits.csv \
  --out audit_v1/audit-planned.json

# 3. After authorized experiments run, audit actual fit memberships
medical-research-harness study audit --mode executed \
  --plan audit_v1/plan/plan.json \
  --fits path/to/executed_fits.csv \
  --out audit_v1/audit-executed.json

# 4. Reconcile all attempts (SUCCESS / FAILED / ABORTED / NOT_RUN)
medical-research-harness study summarize \
  --plan audit_v1/plan/plan.json \
  --runs path/to/runs.json \
  --out audit_v1/summary
```

## 3. Packaging Editor-Reviewable Aggregate Evidence

Use [`scripts/record_research_use.py`](../scripts/record_research_use.py) to verify that only aggregate JSON diagnostics (zero `rows.csv`/`folds.csv`/`fits.csv`, zero `patient_id` keys, `scientific_acceptance: false`) are hashed into a portable evidence record:

```bash
python3 scripts/record_research_use.py \
  --study-id "<target-study-id>" \
  --harness-version "0.2.0" \
  --summary "<what protocol, cohort-audit, and run-reconciliation checks ran>" \
  --limitations "<explicit scope boundaries, unresolved items, and non-clinical-acceptance note>" \
  --out build/evidence/<target-study-id>.json \
  /path/to/target_study/audit_v1/audit-executed.json \
  /path/to/target_study/audit_v1/summary/summary.json
```

After a fresh read-only review of the output JSON, document the verified aggregate findings in [`Paper/joss/RESEARCH_USE_EVIDENCE.md`](../Paper/joss/RESEARCH_USE_EVIDENCE.md) and update [`Paper/joss/research_use_inventory.json`](../Paper/joss/research_use_inventory.json).
