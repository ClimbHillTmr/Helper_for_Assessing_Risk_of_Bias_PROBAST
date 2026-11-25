# Research-use evidence register

Checked 2026-11-13. This register separates historical use, software verification, and scientific acceptance. No clinical performance or independent adoption claim is made.

| Evidence | What is supported | Limits / remaining work |
|---|---|---|
| [Two-article pilot](../../docs/literature-live-result-v1.md) | Historical developer-led literature workflow use; locally retained completion and report | PARTIAL; original response bytes absent; exact citations do not establish semantic validity; old implementation |
| [MedBias-Laya record](../../docs/action-plan-v3-medbias-laya.md) | Historical documentation of study/project-audit use; local study summary records ok=true | Current source manifests and fit logs not freshly re-audited; linked project-audit artifact missing; benchmark claims not endorsed here |
| [Public regression suite](../../tests/review_probes.py) | Reproducible synthetic integrity and rejection tests | Not research adoption, clinical validation, or expert agreement |

The companion [aggregate inventory](research_use_inventory.json) records fresh file-hash checks against the historical literature completion record. These checks establish consistency with that record only. The private research tree is not included. Hashes alone do not make the original research artifacts publicly reproducible or prove they were faithfully generated.

Next: select an authorized research use, reconcile all runs against the approved protocol and actual fit logs, obtain a fresh read-only scientific review, and prepare aggregate editor-reviewable evidence using [real-study-integration-guide.md](../../docs/real-study-integration-guide.md) and `scripts/record_research_use.py`. Do not replace missing executed evidence with planned memberships. Keep original partial/failed runs. A colleague installation report and documented user feedback would strengthen usability evidence but cannot substitute for real research use.
