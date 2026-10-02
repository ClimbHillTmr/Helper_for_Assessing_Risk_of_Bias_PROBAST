#!/usr/bin/env python3
"""Executable synthetic walkthrough. All run snapshots and metrics are simulated."""

import argparse
import copy
import csv
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from study import fingerprint, load, save, sha256


def walkthrough(root, lab=None):
    skill = Path(__file__).resolve().parents[1]
    script = skill / "scripts/study.py"
    root.mkdir(parents=True, exist_ok=False)
    (root / "project").mkdir()
    (root / "project/analysis.py").write_text("raise SystemExit('Synthetic placeholder; no model execution')\n")
    (root / "protocol.md").write_text("# SYNTHETIC SOFTWARE DEMONSTRATION\nNo patient data, model fitting or actual scientific approval.\n")
    config = load(skill / "assets/example_study.json")
    save(root / "study.json", config)
    cases = []

    def run(arguments, expected, case):
        result = subprocess.run([sys.executable, str(script)] + list(map(str, arguments)),
                                cwd=root.parent, capture_output=True, text=True, check=False)
        assert not result.stderr, result.stderr
        assert result.returncode == expected, (case, result.returncode, result.stdout)
        assert "SYNTHETIC_PRIVATE_" not in result.stdout
        cases.append(case)
        return json.loads(result.stdout)

    def write_csv(name, rows):
        with (root / name).open("w", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    rows = []
    for i, day in enumerate([0, 1, 2, 3, 40, 80]):
        index = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
        rows.append({"row_id": f"SYNTHETIC_PRIVATE_R{i}", "patient_id": f"SYNTHETIC_PRIVATE_P{i}",
                     "split": "train" if i < 4 else "validation" if i == 4 else "test",
                     "index_time": index.isoformat(), "feature_max_time": (index - timedelta(hours=1)).isoformat(),
                     "label_start_time": (index + timedelta(hours=1)).isoformat(),
                     "label_end_time": (index + timedelta(days=7)).isoformat()})
    folds = [{"fold_id": fold, "row_id": row["row_id"],
              "role": "train" if fold == "final" or (i < 2) == (fold == "cv1") else "validation"}
             for fold in ("cv1", "cv2", "final") for i, row in enumerate(rows[:4])]
    fits = [{"experiment_id": eid, "operation": "scaler", "fold_id": item["fold_id"], "row_id": item["row_id"]}
            for eid in ("baseline", "sensitivity") for item in folds if item["role"] == "train"]
    write_csv("rows.csv", rows)
    write_csv("folds.csv", folds)
    write_csv("fits.csv", fits)
    run(["plan", root / "study.json", "--out", root / "plan"], 0, "compile draft tasks")
    run(["plan", root / "study.json", "--out", root / "plan"], 2, "refuse output overwrite")
    plan_path = root / "plan/plan.json"
    plan = load(plan_path)
    locked_files = [plan["protocol"], *plan["frozen_manifests"].values()]
    audit_args = ["audit", plan_path, "--mode", "planned", "--rows", root / "rows.csv", "--folds", root / "folds.csv", "--fits", root / "fits.csv"]
    run(audit_args + ["--out", root / "audit-clean.json"], 0, "clean manifest audit")
    bad_rows, bad_fits = copy.deepcopy(rows), copy.deepcopy(fits)
    bad_rows[4]["patient_id"] = bad_rows[0]["patient_id"]
    bad_rows[0]["feature_max_time"] = bad_rows[0]["label_start_time"]
    bad_fits.append({"experiment_id": "baseline", "operation": "scaler", "fold_id": "cv1", "row_id": rows[2]["row_id"]})
    write_csv("candidate-rows.csv", bad_rows)
    write_csv("fits.csv", bad_fits)
    candidate_args = audit_args.copy()
    candidate_args[candidate_args.index("--rows") + 1] = root / "candidate-rows.csv"
    run(candidate_args + ["--out", root / "audit-violations.json"], 1, "reject three planted leakage defects")
    bad_report = load(root / "audit-violations.json")
    assert bad_report["violations"] == {"feature_after_index": 1, "fit_outside_training_fold": 1, "patient_overlap": 1, "frozen_rows_changed": 1}
    assert "SYNTHETIC_PRIVATE_" not in json.dumps(bad_report)
    write_csv("fits.csv", fits)
    write_csv("incomplete-folds.csv", folds[1:])
    candidate_args = audit_args.copy()
    candidate_args[candidate_args.index("--folds") + 1] = root / "incomplete-folds.csv"
    run(candidate_args + ["--out", root / "audit-incomplete-fold.json"], 1, "reject incomplete fold membership")
    crossing = copy.deepcopy(rows)
    crossing[0]["label_end_time"] = rows[5]["index_time"]
    write_csv("crossing-rows.csv", crossing)
    candidate_args = audit_args.copy()
    candidate_args[candidate_args.index("--rows") + 1] = root / "crossing-rows.csv"
    run(candidate_args + ["--out", root / "audit-label-crossing.json"], 1, "reject label window crossing into later split")

    runner_check = "skipped: no external validator supplied with --lab"
    if lab is not None:
        ready_args = ["preflight", plan_path, "--audit", root / "audit-clean.json", "--lab", lab]
        run(ready_args + ["--out", root / "preflight-draft.json"], 1, "runner rejects unapproved draft tasks")
        save(root / "protocol-lock.json", {"files": locked_files, "approved_by": "SYNTHETIC FIXTURE ONLY"})
        for entry in plan["tasks"]:
            task_path = root / "plan" / entry["path"]
            task = load(task_path)
            task["approval"] = {"status": "APPROVED", "by": "SYNTHETIC FIXTURE ONLY", "evidence": "software test, not human approval"}
            task_path.write_text(json.dumps(task))
        run(ready_args + ["--out", root / "preflight-synthetic.json"], 0, "exercise existing runner validation without executing")
        runner_check = "passed: installed ResearchLab validate-task, synthetic artifacts only"
        with (root / "fits.csv").open("a") as output:
            output.write("scaler,cv1,changed\n")
        run(ready_args + ["--out", root / "preflight-stale.json"], 2, "block stale audit after manifest changes")
        write_csv("fits.csv", fits)

    # Only this isolated fixture has pretend approval/run records. Never write ResearchLab's registry.
    registry = root / "simulated-runs"
    registry.mkdir()
    for i, entry in enumerate(plan["tasks"]):
        task = load(root / "plan" / entry["path"])
        task["approval"] = {"status": "APPROVED", "by": "SYNTHETIC FIXTURE, NOT HUMAN APPROVAL", "evidence": "simulated only"}
        rid = f"synthetic-run-{i}"
        directory = registry / rid
        directory.mkdir()
        save(directory / "start.json", {"run_id": rid, "task": task, "git_commit": "synthetic-only",
             "git_status": "", "protocol": {"files": locked_files}})
        save(directory / "finish.json", {"status": "EXECUTED" if i == 0 else "FAILED", "exit_code": 0 if i == 0 else 1,
                                         "reason": None if i == 0 else "simulated failure"})
        if i == 0:
            write_csv("executed-fits.csv", [item for item in fits if item["experiment_id"] == "baseline"])
            run(["audit", plan_path, "--mode", "executed", "--experiment-id", "baseline", "--run-id", rid,
                 "--rows", root / "rows.csv", "--folds", root / "folds.csv", "--fits", root / "executed-fits.csv",
                 "--out", directory / "audit.json"], 0, "bind executed fit audit to one run")
            save(directory / "metrics.json", {"run_id": rid, "task_design_sha256": fingerprint(task),
                "name": "synthetic_auc", "estimate": 0.72, "lower": 0.61, "upper": 0.80,
                "n": 100, "ci_method": "invented interval for software fixture"})
    summary_args = ["summarize", plan_path, "--runs", registry]
    run(summary_args + ["--out", root / "summary"], 0, "retain successful and failed attempts")
    report = load(root / "summary/summary.json")
    assert [r["status"] for r in report["attempts"]] == ["EXECUTED", "FAILED"]
    assert report["attempts"][1]["metric"] is None
    assert report["attempts"][1]["exit_code"] == 1 and report["attempts"][1]["finish_record"]
    audit_path = registry / "synthetic-run-0/audit.json"
    executed_audit = load(audit_path)
    audit_path.write_text(json.dumps(load(root / "audit-clean.json")))
    run(summary_args + ["--out", root / "summary-planned-as-executed"], 1, "reject planned evidence substituted for execution")
    audit_path.write_text(json.dumps(executed_audit))
    metric_path = registry / "synthetic-run-0/metrics.json"
    metric = load(metric_path)
    invalid = dict(metric, run_id="wrong-run")
    metric_path.write_text(json.dumps(invalid))
    run(summary_args + ["--out", root / "summary-wrong-metric"], 1, "reject a metric from another run")
    metric_path.write_text(json.dumps(metric))
    finish_path = registry / "synthetic-run-1/finish.json"
    complete_finish = load(finish_path)
    finish_path.write_text(json.dumps({"status": "FAILED", "reason": "simulated failure"}))
    run(summary_args + ["--out", root / "summary-no-failed-exit"], 1, "reject missing failed-attempt exit evidence")
    finish_path.write_text(json.dumps(dict(complete_finish, exit_code=0)))
    run(summary_args + ["--out", root / "summary-inconsistent-exit"], 1, "reject failed status with zero exit")
    finish_path.unlink()
    run(summary_args + ["--out", root / "summary-interrupted"], 1, "retain an unfinished attempt")
    save(finish_path, complete_finish)
    start_path = registry / "synthetic-run-0/start.json"
    complete_start = load(start_path)
    for tag, value in (("missing", None), ("null", None), ("wrong-type", False)):
        invalid_start = copy.deepcopy(complete_start)
        if tag == "missing":
            invalid_start.pop("git_status")
        else:
            invalid_start["git_status"] = value
        start_path.write_text(json.dumps(invalid_start))
        run(summary_args + ["--out", root / ("summary-code-state-" + tag)], 1, "reject " + tag + " code-state evidence")
    invalid_start = dict(complete_start, git_status="?? changed", code_snapshot_sha256="not-a-digest")
    start_path.write_text(json.dumps(invalid_start))
    run(summary_args + ["--out", root / "summary-dirty-snapshot"], 1, "reject malformed dirty-code snapshot identity")
    start_path.write_text(json.dumps(complete_start))
    truncated_plan = copy.deepcopy(plan)
    truncated_plan["tasks"].pop()
    save(root / "plan/omitted-task.json", truncated_plan)
    run(["summarize", root / "plan/omitted-task.json", "--runs", registry, "--out", root / "summary-omitted"], 2,
        "reject derived-plan omission against source experiment set")
    reversed_folds = copy.deepcopy(folds)
    for item in reversed_folds:
        if item["fold_id"] != "final":
            item["role"] = "validation" if item["role"] == "train" else "train"
    write_csv("changed-folds.csv", reversed_folds)
    changed_fits = [{"experiment_id": "baseline", "operation": "scaler", "fold_id": item["fold_id"], "row_id": item["row_id"]}
                    for item in reversed_folds if item["role"] == "train"]
    write_csv("changed-fits.csv", changed_fits)
    run(["audit", plan_path, "--mode", "executed", "--experiment-id", "baseline", "--run-id", "synthetic-run-0",
         "--rows", root / "rows.csv", "--folds", root / "changed-folds.csv", "--fits", root / "changed-fits.csv",
         "--out", root / "audit-changed-folds.json"], 1, "reject internally clean but unapproved replacement folds")
    substituted = copy.deepcopy(executed_audit)
    substituted["inputs"]["folds"] = {"path": str(root / "changed-folds.csv"), "sha256": sha256(root / "changed-folds.csv")}
    substituted["inputs"]["fits"] = {"path": str(root / "changed-fits.csv"), "sha256": sha256(root / "changed-fits.csv")}
    audit_path.write_text(json.dumps(substituted))
    run(summary_args + ["--out", root / "summary-substituted-folds"], 1, "summary independently rejects substituted fold identities")
    audit_path.write_text(json.dumps(executed_audit))
    new_config = copy.deepcopy(config)
    new_config["experiments"].append(dict(config["experiments"][1], id="not-run"))
    new_config["audit"]["expected_fits"].extend(dict(item, experiment_id="not-run")
                                               for item in config["audit"]["expected_fits"] if item["experiment_id"] == "sensitivity")
    save(root / "study-extra.json", new_config)
    run(["plan", root / "study-extra.json", "--out", root / "plan-extra"], 0, "compile unexecuted planned task")
    run(["summarize", root / "plan-extra/plan.json", "--runs", registry, "--out", root / "summary-missing"], 1,
        "surface a planned task with no attempt")
    missing = load(root / "summary-missing/summary.json")
    assert missing["attempts"][-1]["status"] == "NOT_RUN"
    (root / "protocol.md").write_text("Changed protocol\n")
    run(audit_args + ["--out", root / "audit-drift.json"], 2, "block protocol drift")
    (root / "protocol.md").write_text("# SYNTHETIC SOFTWARE DEMONSTRATION\nNo patient data, model fitting or actual scientific approval.\n")
    run(summary_args + ["--out", root / "summary-final"], 0, "reconcile restored final fixture identities")
    save(root / "checks.json", {"synthetic_only": True, "passed": cases, "runner_integration": runner_check,
         "planted_violations": bad_report["violations"], "real_study_validation": False})
    print(json.dumps({"synthetic_checks_passed": len(cases), "output": str(root)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="New directory for a persistent synthetic walkthrough")
    parser.add_argument("--lab", type=Path, help="Optional trusted external ResearchLab-compatible lab.py")
    args = parser.parse_args()
    if args.lab is not None:
        args.lab = args.lab.resolve()
        if not args.lab.is_file():
            parser.error("--lab must name an existing trusted validator script")
    if args.out:
        walkthrough(args.out.resolve(), args.lab)
    else:
        with tempfile.TemporaryDirectory() as directory:
            walkthrough(Path(directory) / "demo", args.lab)


if __name__ == "__main__":
    main()
