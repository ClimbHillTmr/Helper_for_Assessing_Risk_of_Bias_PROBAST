#!/usr/bin/env python3
"""Run bounded local research checks; never execute experiments or grant approval."""

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from check_bundle import STAGES, check_bundle
from study import (audit, compile_plan, load, need, preflight,
                   read_plan, reconcile, save, sha256, summary_markdown)


# These are operational actions, not PROBAST answers or scientific verdicts.
ACTIONS = {
    "plan": "Repair the study contract or restore the frozen plan inputs; do not silently recompile a changed protocol.",
    "documents": "Supply the requested phase's evidence bundle and resolve its document or study-identity diagnostics.",
    "planned_audit": "Inspect planned-audit.json; repair the authorized exporter or implementation, then use a new output directory.",
    "preflight": "Supply --lab explicitly and resolve recorded approval, protocol lock, and runner validation; reuse existing approvals.",
    "reconciliation": "Inspect summary.json and reconcile every attempt against the original registry; do not auto-retry failed experiments.",
}
INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError,
                RecursionError, RuntimeError, csv.Error, subprocess.TimeoutExpired)


def document_check(path, phase, plan):
    bundle = load(path)
    errors = check_bundle(bundle, path.parent)
    if not isinstance(bundle, dict) or bundle.get("study_id") != plan["study_id"]:
        errors.append("bundle study identity differs from plan")
    if not isinstance(bundle, dict) or bundle.get("phase") != phase:
        errors.append("bundle phase differs from requested workflow phase")
    if not errors:
        protocol = next(item for item in bundle["artifacts"] if item["role"] == "protocol")
        if ((path.parent / protocol["path"]).resolve() != Path(plan["protocol"]["path"])
                or protocol["sha256"] != plan["protocol"]["sha256"]):
            errors.append("bundle protocol differs from frozen plan protocol")
    return {"ok": not errors, "document_integrity_only": True,
            "bundle_sha256": sha256(path), "errors": errors}


def render(report):
    lines = ["# 自动化检查交接", "", f"状态：`{report['state']}`", "",
             "本报告不授予执行许可，不作科学接受，也不证明登记源完整。", "",
             "| 检查 | 状态 | 产物 |", "|---|---|---|"]
    for name, gate in report["gates"].items():
        lines.append(f"| {name} | {gate['status']} | {gate.get('artifact') or '—'} |")
    lines.extend(["", "## 后续动作", ""])
    lines.extend(f"- {item['action']}" for item in report["next_actions"])
    if report["attempt_counts"]:
        lines.extend(["", "## 登记状态计数", ""])
        lines.extend(f"- {status}: {count}" for status, count in report["attempt_counts"].items())
    return "\n".join(lines) + "\n"


def run_workflow(args):
    # Resolve aliases before reserving output; reports must never become registry entries.
    args.out = args.out.resolve()
    if args.runs is not None:
        need(not args.out.is_relative_to(args.runs.resolve()),
             "workflow output must be outside the run registry")
    # Reserve a new output directory before any external validator can run.
    args.out.mkdir(parents=True, exist_ok=False)
    report = {"format_version": 1, "kind": "research_workflow", "phase": args.phase,
              "ok": False, "state": "BLOCKED", "execution_authorized": False,
              "scientific_validity": "not_assessed", "gates": {}, "next_actions": [],
              "attempt_counts": {}, "plan": None,
              "coverage": "Supplied manifests, evidence documents and registry only; no source-completeness attestation."}
    gates = report["gates"]

    def missing(name, reason, status="blocked"):
        gates[name] = {"status": status, "artifact": None, "diagnostic": reason}

    def check(name, filename, operation):
        try:
            result = operation()
            save(args.out / filename, result)
            gates[name] = {"status": "pass" if result["ok"] else "blocked", "artifact": filename}
            return result
        except INPUT_ERRORS:
            # Raw exceptions may contain patient identifiers or external stderr.
            missing(name, "Invalid, stale or unreadable input; inspect the private source and input contract.", "error")
            return None

    plan_path = args.plan.resolve() if args.plan is not None else args.out / "plan/plan.json"
    try:
        if args.study is not None:
            compile_plan(args.study.resolve(), args.out / "plan")
        plan, _ = read_plan(plan_path)
        report["plan"] = {"path": str(plan_path), "sha256": sha256(plan_path)}
        gates["plan"] = {"status": "pass", "artifact": "plan/plan.json" if args.study else None}
    except INPUT_ERRORS:
        missing("plan", "Invalid or changed plan/study; preserve previous evidence and resolve the contract.", "error")
        plan = None

    if plan is not None:
        if args.bundle is None:
            missing("documents", "No evidence bundle supplied; document checking was not performed.")
        else:
            check("documents", "documents.json", lambda: document_check(args.bundle.resolve(), args.phase, plan))
        if args.fits is None:
            missing("planned_audit", "No planned fit manifest supplied.", "skipped" if args.phase == "results" else "blocked")
        else:
            check("planned_audit", "planned-audit.json", lambda: audit(
                plan_path, Path(plan["frozen_manifests"]["rows"]["path"]),
                Path(plan["frozen_manifests"]["folds"]["path"]), args.fits.resolve(), "planned"))

        if args.phase == "preflight":
            if args.lab is None:
                missing("preflight", "No external validator supplied; approval validation was not performed.")
            elif any(gates[name]["status"] != "pass" for name in ("documents", "planned_audit")):
                missing("preflight", "Resolve evidence and manifest gates before external validation.", "skipped")
            elif not args.lab.is_file():
                missing("preflight", "Explicit validator path is not an existing file.", "error")
            else:
                check("preflight", "preflight.json", lambda: preflight(
                    plan_path, args.out / "planned-audit.json", args.lab.resolve()))
        else:
            # Reconciliation is useful even if a separate document gate fails.
            # It revalidates actual run evidence and never creates executed fit logs.
            if args.runs is None:
                missing("reconciliation", "No registry directory supplied; absence is not an empty registry.")
            else:
                summary = check("reconciliation", "summary.json", lambda: reconcile(plan_path, args.runs.resolve()))
                if summary is not None:
                    report["attempt_counts"] = dict(sorted(Counter(row["status"] for row in summary["attempts"]).items()))
                    with (args.out / "summary.md").open("x", encoding="utf-8") as target:
                        target.write(summary_markdown(summary))

    required = ["plan", "documents", "planned_audit", "preflight"] if args.phase == "preflight" else ["plan", "documents", "reconciliation"]
    # An optional audit, when supplied, must not fail silently.
    if args.phase == "results" and args.fits is not None:
        required.append("planned_audit")
    report["ok"] = all(gates.get(name, {}).get("status") == "pass" for name in required)
    if report["ok"]:
        report["state"] = "AWAITING_EXECUTION" if args.phase == "preflight" else "AWAITING_SCIENTIFIC_REVIEW"
        report["next_actions"] = [{"gate": "handoff", "action": (
            "Use the existing runner within recorded approval, budget and single-writer controls; record every actual fit."
            if args.phase == "preflight" else
            "Perform a fresh independent read-only scientific review, including failed/negative attempts, bias and registry completeness.")}]
    else:
        for name in required:
            if name in gates and gates[name]["status"] != "pass":
                report["next_actions"].append({"gate": name, "action": ACTIONS[name]})
    code = 2 if any(gate["status"] == "error" for gate in gates.values()) else 0 if report["ok"] else 1
    report["exit_code"] = code
    save(args.out / "workflow.json", report)
    with (args.out / "workflow.md").open("x", encoding="utf-8") as target:
        target.write(render(report))
    # Publish last; interrupted or partially written reports have no completion marker.
    completion = {"format_version": 1, "exit_code": code,
                  "artifacts": {str(path.relative_to(args.out)): sha256(path)
                                for path in sorted(args.out.rglob("*")) if path.is_file()}}
    save(args.out / ".completion.tmp", completion)
    (args.out / ".completion.tmp").replace(args.out / "completion.json")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--study", type=Path, help="Compile a new DRAFT plan from this study configuration")
    source.add_argument("--plan", type=Path, help="Reuse and revalidate an existing plan without changing approval")
    parser.add_argument("--phase", choices=[phase for phase in STAGES if phase != "design"], required=True)
    parser.add_argument("--fits", type=Path, help="Planned fits; required for preflight, optional for results")
    parser.add_argument("--bundle", type=Path, help="Evidence bundle for the exact requested phase and study")
    parser.add_argument("--lab", type=Path, help="Explicit trusted external validator; preflight only")
    parser.add_argument("--runs", type=Path, help="Existing registry directory; results only")
    parser.add_argument("--out", type=Path, required=True, help="New output directory; never overwrites evidence")
    args = parser.parse_args()
    if (args.phase == "results" and args.lab is not None) or (args.phase == "preflight" and args.runs is not None):
        parser.error("--lab is preflight-only; --runs is results-only")
    try:
        report = run_workflow(args)
        print(json.dumps({key: report[key] for key in ("ok", "state", "exit_code", "execution_authorized", "scientific_validity")}))
        return report["exit_code"]
    except INPUT_ERRORS:
        print(json.dumps({"ok": False, "state": "BLOCKED", "exit_code": 2,
                          "execution_authorized": False, "scientific_validity": "not_assessed",
                          "error": "Cannot create output or complete report; preserve partial artifacts and choose a new output directory."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
