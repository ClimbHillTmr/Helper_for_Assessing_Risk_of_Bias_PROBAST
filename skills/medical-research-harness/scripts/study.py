#!/usr/bin/env python3
"""Compile study tasks, audit provenance manifests, and reconcile ResearchLab runs."""

import argparse
import copy
import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

from check_bundle import reject_constant, sha256, unique_object


TASK_FIELDS = set((
    "research_objective scientific_question hypothesis context data_source cohort_definition "
    "outcome predictors temporal_constraints method experiment_design baseline comparison "
    "primary_metric secondary_metrics statistical_test validation_strategy leakage_controls "
    "acceptance_criteria reproducibility_requirements expected_output risks do_not_do "
    "dependencies priority protocol_lock project feature_set split"
).split())
ROW_FIELDS = {"row_id", "patient_id", "split", "index_time", "feature_max_time",
              "label_start_time", "label_end_time"}


class InputError(ValueError):
    """An actionable diagnostic containing only programmer-controlled text."""


def need(condition, message):
    if not condition:
        raise InputError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=unique_object, parse_constant=reject_constant)


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")


def ident(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", value)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def fingerprint(task):
    # Approval/state may change after design; scientific and execution fields may not.
    core = {k: v for k, v in task.items() if k not in {"status", "approval"}}
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def resolve(base, value):
    need(nonempty(value), "required file path")
    return (base / value).resolve()


def prepare_plan(config_path):
    config = load(config_path)
    need(isinstance(config, dict) and set(config) == {
        "study_id", "protocol", "manifests", "task_template", "experiments", "audit"
    }, "study configuration fields do not match the contract")
    need(ident(config["study_id"]), "invalid study_id")
    protocol = resolve(config_path.parent, config["protocol"])
    need(protocol.is_file() and protocol.stat().st_size > 0, "protocol file is absent or empty")
    need(isinstance(config["manifests"], dict) and set(config["manifests"]) == {"rows", "folds"},
         "manifests must identify the frozen rows and folds files")
    frozen = {}
    for key, value in config["manifests"].items():
        path = resolve(config_path.parent, value)
        need(path.is_file() and path.stat().st_size > 0, "frozen manifest is absent or empty")
        frozen[key] = {"path": str(path), "sha256": sha256(path)}
    base = config["task_template"]
    need(isinstance(base, dict) and TASK_FIELDS <= base.keys(), "incomplete ResearchLab task template")
    need(all(base[k] is not None and base[k] != "" for k in TASK_FIELDS), "empty task template field")
    need(isinstance(base["primary_metric"], dict) and nonempty(base["primary_metric"].get("name")),
         "primary_metric.name is required")
    project = resolve(config_path.parent, base["project"])
    need(project.is_dir(), "target project does not exist")
    need(isinstance(config["experiments"], list) and config["experiments"], "experiments are required")
    policy = config["audit"]
    allowed_policy_keys = {"split_order", "patient_disjoint", "chronological", "label_start", "expected_fits", "zero_fit_experiments"}
    need(isinstance(policy, dict) and {"split_order", "patient_disjoint", "chronological", "label_start", "expected_fits"} <= set(policy) <= allowed_policy_keys,
         "audit policy fields do not match the contract")
    splits = policy["split_order"]
    need(isinstance(splits, list) and len(splits) >= 2 and all(ident(s) for s in splits)
         and len(set(splits)) == len(splits) and splits[0] == "train", "invalid split_order")
    need(policy["patient_disjoint"] is True, "v1 audit requires disjoint patients")
    need(type(policy["chronological"]) is bool, "chronological must be boolean")
    need(policy["label_start"] in ("after_index", "at_index"), "unsupported label timing policy")
    expected = policy["expected_fits"]
    zero_fit_list = policy.get("zero_fit_experiments", [])
    need(isinstance(zero_fit_list, list) and all(ident(x) for x in zero_fit_list)
         and len(zero_fit_list) == len(set(zero_fit_list)), "invalid zero_fit_experiments")
    zero_fit_set = set(zero_fit_list)
    need(isinstance(expected, list) and (expected or zero_fit_set), "expected_fits must list every fitted operation/fold")
    pairs = []
    for item in expected:
        need(isinstance(item, dict) and set(item) == {"experiment_id", "operation", "fold_id"}
             and all(ident(v) for v in item.values()), "invalid expected fit operation/fold")
        pairs.append((item["experiment_id"], item["operation"], item["fold_id"]))
    need(len(pairs) == len(set(pairs)), "duplicate expected fit operation/fold")
    tasks, ids = [], set()
    for experiment in config["experiments"]:
        need(isinstance(experiment, dict) and set(experiment) == {
            "id", "purpose", "model", "seed", "parameters", "command"
        }, "experiment fields do not match the contract")
        eid = experiment["id"]
        need(ident(eid) and eid not in ids, "invalid or duplicate experiment id")
        ids.add(eid)
        need(nonempty(experiment["purpose"]) and nonempty(experiment["model"]), "experiment purpose/model required")
        need(type(experiment["seed"]) is int and isinstance(experiment["parameters"], dict), "invalid seed/parameters")
        command = experiment["command"]
        need(isinstance(command, list) and command and all(nonempty(s) for s in command), "command must be an argv list")
        task = copy.deepcopy(base)
        task.update({k: experiment[k] for k in ("model", "seed", "parameters", "command")})
        task.update(task_id=f"{config['study_id']}-{eid}", project=str(project), status="DRAFT",
                    approval={"status": "DRAFT", "by": "", "evidence": ""})
        need(ident(task["task_id"]), "combined task id is too long")
        task["protocol_lock"] = str(resolve(config_path.parent, base["protocol_lock"]))
        task["harness"] = {"study_id": config["study_id"], "purpose": experiment["purpose"],
                           "protocol_sha256": sha256(protocol), "frozen_manifests": frozen}
        tasks.append(task)
    fitted_ids = {item["experiment_id"] for item in expected}
    need((fitted_ids | zero_fit_set) == ids and not (fitted_ids & zero_fit_set),
         "fit policy must cover exactly the planned experiments")
    plan = {"study_id": config["study_id"], "source_config": str(config_path), "config_sha256": sha256(config_path),
            "protocol": {"path": str(protocol), "sha256": sha256(protocol)}, "audit": policy, "frozen_manifests": frozen,
            "tasks": [{"path": t["task_id"] + ".json", "design_sha256": fingerprint(t)} for t in tasks]}
    return plan, tasks


def compile_plan(config_path, out):
    plan, tasks = prepare_plan(config_path)
    out.mkdir(parents=True, exist_ok=False)
    for task, entry in zip(tasks, plan["tasks"]):
        save(out / entry["path"], task)
    save(out / "plan.json", plan)
    return {"ok": True, "draft_tasks": len(tasks), "execution_authorized": False}


def read_plan(path):
    plan = load(path)
    need(isinstance(plan, dict) and ident(plan.get("study_id")), "invalid plan")
    source = Path(plan["source_config"])
    need(sha256(source) == plan["config_sha256"], "study configuration changed after compilation")
    original = load(source)
    need(plan["audit"] == original["audit"] and plan["study_id"] == original["study_id"],
         "derived plan policy differs from source configuration")
    protocol = plan["protocol"]
    need(sha256(Path(protocol["path"])) == protocol["sha256"], "protocol changed after plan creation")
    expected_plan, expected_tasks = prepare_plan(source)
    need(plan == expected_plan, "derived plan differs from source study or frozen manifest identities")
    tasks = {}
    for entry, expected_task in zip(plan["tasks"], expected_tasks):
        task = load(resolve(path.parent, entry["path"]))
        need(fingerprint(task) == entry["design_sha256"], "task design changed after compilation")
        need(fingerprint(task) == fingerprint(expected_task), "task design differs from source experiment")
        need(ident(task["task_id"]) and task["task_id"] not in tasks, "invalid/duplicate planned task")
        tasks[task["task_id"]] = task
    need(tasks, "empty plan")
    return plan, tasks


def table(path, fields, allow_empty=False):
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        need(reader.fieldnames is not None and len(reader.fieldnames) == len(fields)
             and set(reader.fieldnames) == fields, "CSV header does not match the manifest contract")
        rows = list(reader)
    need(rows or allow_empty, "empty audit manifest")
    need(all(set(row) == fields and all(nonempty(v) for v in row.values()) for row in rows),
         "audit manifest contains missing values or malformed records")
    return rows


def time_value(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    need(stamp.utcoffset() is not None, "timestamps require an explicit timezone")
    return stamp


def audit(plan_path, rows_path, folds_path, fits_path, mode, experiment_id=None, run_id=None):
    plan, tasks = read_plan(plan_path)
    need(mode in {"planned", "executed"}, "audit mode must be planned or executed")
    if mode == "executed":
        need(ident(experiment_id) and ident(run_id), "executed audit needs experiment_id and run_id")
        task_id = f"{plan['study_id']}-{experiment_id}"
        need(task_id in tasks, "executed audit references an unplanned experiment")
    else:
        need(experiment_id is None and run_id is None, "planned audit must not claim an executed run")
    policy = plan["audit"]
    zero_fit_exps = set(policy.get("zero_fit_experiments", []))
    # ponytail: O(rows + fold memberships) memory; use external sorting for oversized manifests.
    rows = table(rows_path, ROW_FIELDS)
    folds = table(folds_path, {"fold_id", "row_id", "role"})
    fits = table(fits_path, {"experiment_id", "operation", "fold_id", "row_id"},
                 allow_empty=(mode == "executed" and experiment_id in zero_fit_exps))
    counts = Counter()
    counts["frozen_rows_changed"] = int(sha256(rows_path) != plan["frozen_manifests"]["rows"]["sha256"])
    counts["frozen_folds_changed"] = int(sha256(folds_path) != plan["frozen_manifests"]["folds"]["sha256"])
    by_id, patients, times, label_ends = {}, defaultdict(set), defaultdict(list), defaultdict(list)
    for row in rows:
        rid, split = row["row_id"], row["split"]
        counts["noncanonical_identifier"] += int(any(row[k] != row[k].strip() for k in ("row_id", "patient_id", "split")))
        if rid in by_id:
            counts["duplicate_row_id"] += 1
        by_id[rid] = row
        if split not in policy["split_order"]:
            counts["unknown_split"] += 1
        patients[split].add(row["patient_id"])
        try:
            index, feature, start, end = (time_value(row[k]) for k in
                ("index_time", "feature_max_time", "label_start_time", "label_end_time"))
        except ValueError:
            counts["invalid_timestamp"] += 1
            continue
        times[split].append(index)
        label_ends[split].append(end)
        counts["feature_after_index"] += int(feature > index)
        counts["invalid_label_window"] += int(end <= start)
        counts["invalid_label_start"] += int(
            start <= index if policy["label_start"] == "after_index" else start != index)
    for left, right in combinations(policy["split_order"], 2):
        counts["patient_overlap"] += len(patients[left] & patients[right])
        if policy["chronological"] and times[left] and times[right]:
            counts["nonchronological_split"] += int(max(times[left]) >= min(times[right]))
            counts["label_window_crosses_split"] += int(max(label_ends[left]) >= min(times[right]))
    counts["empty_split"] = sum(not patients[s] for s in policy["split_order"])
    roles, fold_patients, fold_ids = {}, defaultdict(lambda: defaultdict(set)), set()
    for item in folds:
        key = item["fold_id"], item["row_id"]
        fold_ids.add(item["fold_id"])
        counts["duplicate_fold_assignment"] += int(key in roles)
        roles[key] = item["role"]
        if item["role"] not in {"train", "validation"} or item["row_id"] not in by_id:
            counts["invalid_fold_assignment"] += 1
        else:
            row = by_id[item["row_id"]]
            counts["holdout_in_development_fold"] += int(row["split"] != "train")
            fold_patients[item["fold_id"]][item["role"]].add(row["patient_id"])
    for roleset in fold_patients.values():
        counts["fold_patient_overlap"] += len(roleset["train"] & roleset["validation"])
        counts["empty_fold_training_set"] += int(not roleset["train"])
    expected = {(x["experiment_id"], x["operation"], x["fold_id"]) for x in policy["expected_fits"]
                if mode == "planned" or x["experiment_id"] == experiment_id}
    train_ids = {rid for rid, row in by_id.items() if row["split"] == "train"}
    for fold in {fold for _, _, fold in expected}:
        assigned = {rid for fid, rid in roles if fid == fold}
        counts["incomplete_fold_membership"] += len(train_ids - assigned)
        counts["missing_fold_validation"] += int(fold != "final" and not fold_patients[fold]["validation"])
    seen, seen_rows = set(), set()
    for fit in fits:
        pair = fit["experiment_id"], fit["operation"], fit["fold_id"]
        key = fit["fold_id"], fit["row_id"]
        seen.add(pair)
        signature = pair + (fit["row_id"],)
        counts["duplicate_fit_record"] += int(signature in seen_rows)
        seen_rows.add(signature)
        counts["fit_outside_training_fold"] += int(
            roles.get(key) != "train" or by_id.get(fit["row_id"], {}).get("split") != "train")
    all_expected_folds = {x["fold_id"] for x in policy["expected_fits"]}
    counts["missing_fit_operation"] = len(expected - seen)
    counts["unexpected_fit_operation"] = len(seen - expected)
    counts["unlisted_fold"] = len(fold_ids - all_expected_folds)
    failures = {k: v for k, v in sorted(counts.items()) if v}
    fixes = {
        "patient_overlap": "按批准的患者分组重建切分，并使旧验证结果失效。",
        "feature_after_index": "追踪采集/发布/可用时点，修正特征生成器后重新审计。",
        "fit_outside_training_fold": "将该拟合步骤移入训练折，重建全部受影响的验证结果。",
        "fold_patient_overlap": "按患者重建内部折，禁止同患者进入折内训练与验证。",
    }
    return {"ok": not failures, "kind": "manifest_audit", "execution_authorized": False,
            "mode": mode, "run_id": run_id, "experiment_id": experiment_id,
            "task_design_sha256": fingerprint(tasks[task_id]) if mode == "executed" else None,
            "scientific_validity": "not_assessed", "plan_sha256": sha256(plan_path),
            "inputs": {name: {"path": str(path.resolve()), "sha256": sha256(path)}
                       for name, path in (("rows", rows_path), ("folds", folds_path), ("fits", fits_path))},
            "records": len(rows), "split_counts": dict(Counter(r["split"] for r in rows if r["split"] in policy["split_order"])),
            "violations": failures,
            "next_actions": {k: fixes.get(k, "按清单规范修复来源导出或已批准实现，再运行审计。") for k in failures},
            "coverage": "Supplied manifests only; verify completeness and correspondence to executed code separately."}


def verify_audit(report, plan_path, mode):
    need(report.get("kind") == "manifest_audit" and report.get("ok") is True
         and report.get("violations") == {}, "audit failed or is not a supported audit report")
    need(report.get("mode") == mode, "planned fit memberships cannot replace executed fit evidence")
    need(report.get("plan_sha256") == sha256(plan_path), "audit belongs to another plan")
    need(set(report.get("inputs", {})) == {"rows", "folds", "fits"}, "audit input identities are incomplete")
    for item in report["inputs"].values():
        need(sha256(Path(item["path"])) == item["sha256"], "audit input changed; rerun the audit")
    plan, _ = read_plan(plan_path)
    for key, item in plan["frozen_manifests"].items():
        need(report["inputs"][key]["sha256"] == item["sha256"], "audit cohort/folds differ from frozen task identities")
    actual = audit(plan_path, *(Path(report["inputs"][key]["path"]) for key in ("rows", "folds", "fits")),
                   mode, report.get("experiment_id"), report.get("run_id"))
    need(actual == report, "audit report differs from freshly recomputed manifest evidence")


def lock_binds_study(locked, plan):
    required = [plan["protocol"], *plan["frozen_manifests"].values()]
    return all(any(item.get("path") == expected["path"] and item.get("sha256") == expected["sha256"]
                   for item in locked.get("files", [])) for expected in required)


def preflight(plan_path, audit_path, lab_path):
    plan, tasks = read_plan(plan_path)
    report = load(audit_path)
    verify_audit(report, plan_path, "planned")
    failed = []
    for entry, task in zip(plan["tasks"], tasks.values()):
        approval = task.get("approval", {})
        if (not isinstance(approval, dict) or approval.get("status") != "APPROVED"
                or not all(nonempty(approval.get(key)) for key in ("by", "evidence"))):
            failed.append(task["task_id"])
            continue
        locked = load(Path(task["protocol_lock"]))
        need(lock_binds_study(locked, plan), "task lock must bind the protocol and frozen cohort/folds")
        result = subprocess.run([sys.executable, str(lab_path), "validate-task",
                                 str(resolve(plan_path.parent, entry["path"]))],
                                capture_output=True, text=True, timeout=30, check=False)
        if result.returncode != 0:
            failed.append(task["task_id"])
    return {"ok": not failed, "kind": "execution_preflight", "execution_authorized": False,
            "scientific_validity": "not_assessed", "plan_sha256": sha256(plan_path),
            "audit_sha256": sha256(audit_path), "runner_sha256": sha256(lab_path),
            "tasks_rejected_by_runner": failed,
            "next_action": "Attach existing valid approval/lock and resolve runner validation before execution." if failed
                           else "Use the existing runner only within recorded approval; this command starts no experiment."}


def reconcile(plan_path, runs):
    plan, tasks = read_plan(plan_path)
    entries, issues, attempted, run_ids = [], [], set(), set()
    inventory = {}
    for directory in sorted(p for p in runs.iterdir() if p.is_dir()):
        start_path = directory / "start.json"
        if not start_path.exists():
            issues.append("registry directory without start.json; scope cannot be established")
            continue
        start = load(start_path)
        task = start.get("task", {})
        tid = task.get("task_id")
        if tid not in tasks and task.get("harness", {}).get("study_id") != plan["study_id"]:
            continue
        need(ident(tid) and ident(start.get("run_id")), "invalid run/task identity")
        rid = start["run_id"]
        need(rid not in run_ids, "duplicate run_id in registry")
        run_ids.add(rid)
        inventory[rid] = {"start": sha256(start_path)}
        attempted.add(tid)
        finish_path = directory / "finish.json"
        finish = load(finish_path) if finish_path.exists() else {"status": "RUNNING"}
        if finish_path.exists():
            inventory[rid]["finish"] = sha256(finish_path)
        status = finish.get("status")
        need(status in {"EXECUTED", "FAILED", "ABORTED", "INVALID", "RUNNING"}, "invalid run status")
        row = {"task_id": tid, "run_id": rid, "status": status, "metric": None,
               "exit_code": None, "finish_record": str(finish_path) if finish_path.exists() else None}
        row_issues = []
        if tid not in tasks or fingerprint(task) != fingerprint(tasks[tid]):
            row_issues.append("task design differs from plan")
        approval = task.get("approval", {})
        if approval.get("status") != "APPROVED" or not all(nonempty(approval.get(k)) for k in ("by", "evidence")):
            row_issues.append("task snapshot lacks recorded approval")
        if not nonempty(start.get("git_commit")):
            row_issues.append("code revision missing")
        if not isinstance(start.get("git_status"), str):
            row_issues.append("code state is missing or invalid; it cannot be assumed clean")
        elif start["git_status"] and not (isinstance(start.get("code_snapshot_sha256"), str)
                                         and re.fullmatch(r"[0-9a-f]{64}", start["code_snapshot_sha256"])):
            row_issues.append("dirty code requires an immutable SHA-256 code snapshot identity")
        if not lock_binds_study(start.get("protocol", {}), plan):
            row_issues.append("run lock does not bind the planned protocol and cohort/folds")
        if status == "RUNNING":
            row_issues.append("run is unfinished")
        else:
            code = finish.get("exit_code")
            if type(code) is not int or (code == 0) != (status == "EXECUTED"):
                row_issues.append("terminal exit code is missing, invalid or inconsistent with status")
            else:
                row["exit_code"] = code
            if "reason" not in finish or (finish["reason"] is not None and not isinstance(finish["reason"], str)):
                row_issues.append("terminal reason field is missing or invalid")
            row["diagnostic"] = "Inspect private finish.json reason and stderr.log" if status != "EXECUTED" else "Recorded successful exit"
        if status == "EXECUTED":
            audit_path = directory / "audit.json"
            if not audit_path.exists():
                row_issues.append("executed run lacks an executed manifest audit")
            else:
                try:
                    executed_audit = load(audit_path)
                    verify_audit(executed_audit, plan_path, "executed")
                    need(executed_audit.get("run_id") == rid and
                         executed_audit.get("task_design_sha256") == fingerprint(task),
                         "executed audit belongs to a different run/task")
                    inventory[rid]["audit"] = sha256(audit_path)
                except (OSError, ValueError, TypeError, AttributeError, KeyError):
                    row_issues.append("executed manifest audit is invalid, stale or mismatched")
            metric_path = directory / "metrics.json"
            if not metric_path.exists():
                row_issues.append("executed run has no metrics.json")
            else:
                try:
                    metric = load(metric_path)
                except (OSError, ValueError, RecursionError):
                    metric = None
                inventory[rid]["metrics"] = sha256(metric_path)
                expected_metric = tasks.get(tid, task)["primary_metric"]["name"]
                valid = isinstance(metric, dict) and set(metric) == {
                    "run_id", "task_design_sha256", "name", "estimate", "lower", "upper", "n", "ci_method"
                }
                valid = valid and metric["run_id"] == rid and metric["task_design_sha256"] == fingerprint(task)
                valid = valid and metric["name"] == expected_metric and nonempty(metric["ci_method"])
                valid = valid and all(type(metric[k]) in (int, float)
                                      and -sys.float_info.max <= metric[k] <= sys.float_info.max
                                      for k in ("estimate", "lower", "upper"))
                valid = valid and metric["lower"] <= metric["upper"] and type(metric["n"]) is int and metric["n"] > 0
                if valid:
                    row["metric"] = {k: metric[k] for k in ("name", "estimate", "lower", "upper", "n", "ci_method")}
                else:
                    row_issues.append("metrics identity, interval or denominator is invalid")
        row["issues"] = row_issues
        issues.extend(f"{rid}: {issue}" for issue in row_issues)
        entries.append(row)
    for tid in sorted(tasks.keys() - attempted):
        entries.append({"task_id": tid, "run_id": None, "status": "NOT_RUN", "metric": None,
                        "exit_code": None, "finish_record": None,
                        "issues": ["planned task has no registered attempt"]})
        issues.append(f"{tid}: planned task has no registered attempt")
    return {"ok": not issues, "kind": "run_reconciliation", "execution_authorized": False,
            "scientific_validity": "not_assessed", "plan_sha256": sha256(plan_path),
            "source_sha256": inventory, "attempts": entries, "issues": issues,
            "coverage": "All matching start.json snapshots under the supplied registry root; no registry-completeness attestation."}


def summary_markdown(report):
    lines = ["# 实验结果对账", "", "仅汇总登记与聚合结果；科学有效性尚未评估。", "",
             "| Task | Run | Status | Exit | Metric | Estimate [interval] | N |", "|---|---|---|---|---|---|---|"]
    for row in report["attempts"]:
        metric = row["metric"]
        name = str(metric["name"]).replace("|", "\\|").replace("\n", " ") if metric else "—"
        value = f"{metric['estimate']} [{metric['lower']}, {metric['upper']}]" if metric else "—"
        lines.append(f"| {row['task_id']} | {row['run_id'] or '—'} | {row['status']} | {row['exit_code'] if row['exit_code'] is not None else '—'} | {name} | {value} | {metric['n'] if metric else '—'} |")
    lines.extend(["", "## 未解决问题", ""] + ["- " + x for x in report["issues"]])
    if not report["issues"]:
        lines.append("登记与结果可对账；仍需偏倚评估和科学复核。")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan")
    plan_cmd.add_argument("study", type=Path)
    plan_cmd.add_argument("--out", type=Path, required=True)
    audit_cmd = commands.add_parser("audit")
    audit_cmd.add_argument("plan", type=Path)
    audit_cmd.add_argument("--mode", choices=["planned", "executed"], required=True)
    audit_cmd.add_argument("--experiment-id")
    audit_cmd.add_argument("--run-id")
    for field in ("rows", "folds", "fits", "out"):
        audit_cmd.add_argument("--" + field, type=Path, required=True)
    result_cmd = commands.add_parser("summarize")
    result_cmd.add_argument("plan", type=Path)
    result_cmd.add_argument("--runs", type=Path, required=True)
    result_cmd.add_argument("--out", type=Path, required=True)
    preflight_cmd = commands.add_parser("preflight")
    preflight_cmd.add_argument("plan", type=Path)
    for field in ("audit", "lab", "out"):
        preflight_cmd.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            report = compile_plan(args.study.resolve(), args.out)
        elif args.command == "audit":
            report = audit(args.plan.resolve(), args.rows, args.folds, args.fits,
                           args.mode, args.experiment_id, args.run_id)
            save(args.out, report)
        elif args.command == "preflight":
            report = preflight(args.plan.resolve(), args.audit, args.lab)
            save(args.out, report)
        else:
            report = reconcile(args.plan.resolve(), args.runs)
            args.out.mkdir(parents=True, exist_ok=False)
            save(args.out / "summary.json", report)
            (args.out / "summary.md").write_text(summary_markdown(report), encoding="utf-8")
        print(json.dumps({"ok": report["ok"], "output": str(args.out), "execution_authorized": False}))
        return 0 if report["ok"] else 1
    except InputError as error:
        print(json.dumps({"ok": False, "error": str(error), "execution_authorized": False}))
        return 2
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError, csv.Error, subprocess.TimeoutExpired):
        # Never echo input records, identifiers, raw parser exceptions, or credentials.
        print(json.dumps({"ok": False, "error": "Invalid input, changed identity, unreadable file or existing output; see the input contract.",
                          "execution_authorized": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
