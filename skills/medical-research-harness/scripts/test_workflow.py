#!/usr/bin/env python3
"""Offline integration tests; all approvals, records and metrics are synthetic."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from check_bundle import STAGES
from study import load, save, sha256
from test_study import walkthrough


SCRIPT = Path(__file__).with_name("workflow.py")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "synthetic"
        with contextlib.redirect_stdout(io.StringIO()):
            walkthrough(self.root)
        self.plan = self.root / "plan/plan.json"
        self.runs = self.root / "simulated-runs"
        self.index = 0
        self.validator = self.root / "synthetic-validator.py"
        # Isolated test validator, never a production approval source.
        self.validator.write_text(
            "import json, pathlib, sys\n"
            "assert sys.argv[1] == 'validate-task'\n"
            "p = pathlib.Path(__file__).with_name('validator-called')\n"
            "p.write_text('synthetic validation only')\n"
            "t = json.loads(pathlib.Path(sys.argv[2]).read_text())\n"
            "print('SYNTHETIC_PRIVATE_EXTERNAL_OUTPUT')\n"
            "raise SystemExit(0 if t['approval']['status'] == 'APPROVED' else 1)\n",
            encoding="utf-8")

    def bundle(self, phase="results"):
        roles = set()
        for stage, values in STAGES.items():
            roles.update(values)
            if stage == phase:
                break
        result = {"format_version": 1, "study_id": "SYNTHETIC-DEMO", "phase": phase,
                  "artifacts": [{"role": role, "status": "available", "path": "protocol.md",
                                 "sha256": sha256(self.root / "protocol.md"),
                                 "locator": "Synthetic fixture only", "note": "Not scientific evidence"}
                                for role in sorted(roles)]}
        path = self.root / f"bundle-{phase}.json"
        path.write_text(json.dumps(result), encoding="utf-8")
        return path

    def invoke(self, extra=(), expected=0, phase="results", bundle=True, source=None, runs=True):
        self.index += 1
        out = self.root / f"workflow-{self.index}"
        args = [sys.executable, str(SCRIPT), *(source or ["--plan", str(self.plan)]),
                "--phase", phase, "--out", str(out)]
        if bundle:
            args += ["--bundle", str(self.bundle(phase))]
        if phase == "results" and runs:
            args += ["--runs", str(self.runs)]
        args += list(map(str, extra))
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("SYNTHETIC_PRIVATE_", result.stdout)
        for path in out.rglob("*.json"):
            self.assertNotIn("SYNTHETIC_PRIVATE_", path.read_text())
        report = load(out / "workflow.json")
        completion = load(out / "completion.json")
        self.assertEqual(completion["exit_code"], expected)
        self.assertEqual(completion["artifacts"], {str(p.relative_to(out)): sha256(p)
                                                  for p in out.rglob("*") if p.is_file() and p.name != "completion.json"})
        self.assertFalse(report["execution_authorized"])
        self.assertEqual(report["scientific_validity"], "not_assessed")
        return report, out

    def approve_fixture(self):
        plan = load(self.plan)
        save(self.root / "protocol-lock.json", {"files": [plan["protocol"], *plan["frozen_manifests"].values()]})
        for entry in plan["tasks"]:
            path = self.plan.parent / entry["path"]
            task = load(path)
            task["approval"] = {"status": "APPROVED", "by": "SYNTHETIC TEST ONLY", "evidence": "not human approval"}
            path.write_text(json.dumps(task), encoding="utf-8")

    def test_results_keep_failure_and_require_scientific_review(self):
        before = {p: sha256(p) for p in self.plan.parent.iterdir() if p.is_file()}
        report, out = self.invoke()
        self.assertEqual(report["state"], "AWAITING_SCIENTIFIC_REVIEW")
        self.assertEqual(report["attempt_counts"], {"EXECUTED": 1, "FAILED": 1})
        self.assertEqual(before, {p: sha256(p) for p in before})
        self.assertTrue((out / "summary.md").is_file())

    def test_no_bundle_is_not_pass_but_still_reconciles(self):
        report, _ = self.invoke(bundle=False, expected=1)
        self.assertEqual(report["gates"]["reconciliation"]["status"], "pass")
        self.assertEqual(report["state"], "BLOCKED")

    def test_wrong_study_and_phase_and_protocol_rejected(self):
        for field, value in (("study_id", "other-study"), ("phase", "design"), ("protocol", "other")):
            with self.subTest(field=field):
                path = self.bundle()
                data = load(path)
                if field == "protocol":
                    other = self.root / "other.md"
                    other.write_text("Different synthetic protocol", encoding="utf-8")
                    item = next(x for x in data["artifacts"] if x["role"] == "protocol")
                    item.update(path="other.md", sha256=sha256(other))
                else:
                    data[field] = value
                path.write_text(json.dumps(data), encoding="utf-8")
                report, _ = self.invoke(["--bundle", path], bundle=False, expected=1)
                self.assertEqual(report["gates"]["documents"]["status"], "blocked")

    def test_preflight_missing_runner_is_blocked(self):
        report, _ = self.invoke(["--fits", self.root / "fits.csv"], phase="preflight", expected=1)
        self.assertEqual(report["gates"]["planned_audit"]["status"], "pass")
        self.assertEqual(report["gates"]["preflight"]["status"], "blocked")

    def test_draft_rejected_and_existing_approval_reused(self):
        args = ["--fits", self.root / "fits.csv", "--lab", self.validator]
        report, _ = self.invoke(args, phase="preflight", expected=1)
        self.assertEqual(report["state"], "BLOCKED")
        self.approve_fixture()
        report, _ = self.invoke(args, phase="preflight")
        self.assertEqual(report["state"], "AWAITING_EXECUTION")
        self.assertTrue((self.root / "validator-called").exists())

    def test_failed_audit_prevents_validator_call(self):
        with (self.root / "fits.csv").open("a", encoding="utf-8") as target:
            target.write("baseline,scaler,cv1,SYNTHETIC_PRIVATE_R5\n")
        report, _ = self.invoke(["--fits", self.root / "fits.csv", "--lab", self.validator], phase="preflight", expected=1)
        self.assertEqual(report["gates"]["planned_audit"]["status"], "blocked")
        self.assertFalse((self.root / "validator-called").exists())

    def test_invalid_input_produces_private_safe_checkpoint(self):
        (self.root / "fits.csv").write_text("SYNTHETIC_PRIVATE_BROKEN\n", encoding="utf-8")
        report, _ = self.invoke(["--fits", self.root / "fits.csv"], phase="preflight", expected=2)
        self.assertEqual(report["gates"]["planned_audit"]["status"], "error")

    def test_protocol_drift_does_not_recompile(self):
        (self.root / "protocol.md").write_text("Changed", encoding="utf-8")
        report, out = self.invoke(expected=2)
        self.assertEqual(report["gates"]["plan"]["status"], "error")
        self.assertFalse((out / "plan").exists())

    def test_new_study_compiles_draft_without_execution(self):
        report, out = self.invoke(["--fits", self.root / "fits.csv"], phase="preflight", expected=1,
                                  source=["--study", str(self.root / "study.json")])
        self.assertEqual(report["gates"]["plan"]["status"], "pass")
        compiled = load(out / "plan/plan.json")
        self.assertTrue(all(load(out / "plan" / e["path"])["approval"]["status"] == "DRAFT" for e in compiled["tasks"]))

    def test_all_failed_is_reconciled_not_scientifically_accepted(self):
        finish = self.runs / "synthetic-run-0/finish.json"
        finish.write_text(json.dumps({"status": "FAILED", "exit_code": 1, "reason": None}))
        report, _ = self.invoke()
        self.assertEqual(report["attempt_counts"], {"FAILED": 2})
        self.assertEqual(report["state"], "AWAITING_SCIENTIFIC_REVIEW")

    def test_unfinished_and_not_run_are_visible(self):
        (self.runs / "synthetic-run-1/finish.json").unlink()
        report, _ = self.invoke(expected=1)
        self.assertEqual(report["attempt_counts"]["RUNNING"], 1)
        empty = self.root / "empty-runs"
        empty.mkdir()
        report, _ = self.invoke(["--runs", empty], runs=False, expected=1)
        self.assertEqual(report["attempt_counts"], {"NOT_RUN": 2})

    def test_missing_registry_and_wrong_audit_mode(self):
        report, _ = self.invoke(runs=False, expected=1)
        self.assertEqual(report["gates"]["reconciliation"]["status"], "blocked")
        report, _ = self.invoke(["--runs", self.root / "absent"], runs=False, expected=2)
        self.assertEqual(report["gates"]["reconciliation"]["status"], "error")
        path = self.runs / "synthetic-run-0/audit.json"
        path.write_bytes((self.root / "audit-clean.json").read_bytes())
        report, _ = self.invoke(expected=1)
        self.assertEqual(report["gates"]["reconciliation"]["status"], "blocked")

    def test_draft_cannot_pass_with_accept_all_validator(self):
        self.validator.write_text("raise SystemExit(0)\n", encoding="utf-8")
        report, out = self.invoke(["--fits", self.root / "fits.csv", "--lab", self.validator],
                                  phase="preflight", expected=1)
        self.assertEqual(report["gates"]["preflight"]["status"], "blocked")
        self.assertFalse(load(out / "preflight.json")["ok"])

    def test_forged_executed_pass_is_recomputed(self):
        fits = self.root / "executed-fits.csv"
        with fits.open("a", encoding="utf-8") as target:
            target.write("baseline,scaler,cv1,SYNTHETIC_PRIVATE_R5\n")
        path = self.runs / "synthetic-run-0/audit.json"
        forged = load(path)
        forged["inputs"]["fits"]["sha256"] = sha256(fits)
        path.write_text(json.dumps(forged), encoding="utf-8")
        report, _ = self.invoke(expected=1)
        self.assertEqual(report["gates"]["reconciliation"]["status"], "blocked")

    def test_forged_planned_pass_is_recomputed(self):
        from study import InputError, preflight
        fits = self.root / "fits.csv"
        with fits.open("a", encoding="utf-8") as target:
            target.write("baseline,scaler,cv1,SYNTHETIC_PRIVATE_R5\n")
        path = self.root / "audit-clean.json"
        forged = load(path)
        forged["inputs"]["fits"]["sha256"] = sha256(fits)
        path.write_text(json.dumps(forged), encoding="utf-8")
        with self.assertRaises(InputError):
            preflight(self.plan, path, self.validator)
        self.assertFalse((self.root / "validator-called").exists())

    def test_registry_output_overlap_leaves_no_residue(self):
        for relative in ("report", "nested/report"):
            out = self.runs / relative
            result = subprocess.run([sys.executable, str(SCRIPT), "--plan", str(self.plan),
                                     "--phase", "results", "--runs", str(self.runs),
                                     "--out", str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stderr, "")
            self.assertFalse(out.exists())
            self.assertFalse((self.runs / "nested").exists())
        self.invoke()  # Rejected output did not poison later reconciliation.

    def test_interrupted_report_has_no_completion_marker(self):
        from argparse import Namespace
        from unittest.mock import patch
        import workflow
        out = self.root / "interrupted-workflow"
        args = Namespace(out=out, phase="results", study=None, plan=self.plan,
                         bundle=self.bundle(), fits=None, lab=None, runs=self.runs)
        with patch.object(workflow, "render", side_effect=OSError("SYNTHETIC_PRIVATE_WRITE_ERROR")):
            with self.assertRaises(OSError):
                workflow.run_workflow(args)
        self.assertTrue((out / "workflow.json").exists())
        self.assertFalse((out / "completion.json").exists())

    def test_existing_output_refused_before_validator(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--plan", str(self.plan),
                                 "--phase", "preflight", "--lab", str(self.validator),
                                 "--out", str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "validator-called").exists())


if __name__ == "__main__":
    unittest.main()
