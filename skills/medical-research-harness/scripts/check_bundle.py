#!/usr/bin/env python3
"""Check evidence documents and digests; never grant scientific approval."""

import argparse
import hashlib
import json
import re
from pathlib import Path


STAGES = {
    "design": {"protocol", "data_dictionary", "bias_plan", "analysis_plan"},
    "preflight": {
        "approval", "protocol_lock", "task_spec", "run_registration",
        "data_identity", "data_audit", "split_audit", "preprocessing_audit",
    },
    "results": {
        "run_record", "metrics", "bias_assessment", "result_summary",
        "independent_review",
    },
}
ROLES = set().union(*STAGES.values())
OPTIONAL = {"split_audit", "preprocessing_audit"}
FIELDS = {"role", "status", "path", "sha256", "locator", "note"}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def reject_constant(_value):
    raise ValueError("non-finite JSON number")


def check_bundle(bundle, base):
    """Return diagnostics without printing document contents or study metadata."""
    errors = []
    if not isinstance(bundle, dict) or set(bundle) != {
        "format_version", "study_id", "phase", "artifacts"
    }:
        return ["bundle: expected exactly format_version, study_id, phase, artifacts"]
    if type(bundle["format_version"]) is not int or bundle["format_version"] != 1:
        errors.append("format_version: expected integer 1")
    if not isinstance(bundle["study_id"], str) or not bundle["study_id"].strip():
        errors.append("study_id: required nonempty string")
    phase = bundle["phase"]
    if not isinstance(phase, str) or phase not in STAGES:
        return errors + ["phase: expected design, preflight or results"]
    if not isinstance(bundle["artifacts"], list):
        return errors + ["artifacts: expected list"]

    required = set()
    for stage, roles in STAGES.items():
        required.update(roles)
        if stage == phase:
            break
    supplied = {}
    for index, item in enumerate(bundle["artifacts"]):
        label = f"artifact[{index}]"
        if not isinstance(item, dict) or set(item) != FIELDS:
            errors.append(f"{label}: expected role, status, path, sha256, locator, note")
            continue
        if any(not isinstance(item[key], str) for key in FIELDS):
            errors.append(f"{label}: all fields must be strings")
            continue
        role = item["role"]
        if role not in ROLES:
            errors.append(f"{label}: unknown role")
            continue
        label = role  # Only known fixed vocabulary enters diagnostics.
        if role in supplied:
            errors.append(f"{label}: duplicate role")
            continue
        supplied[role] = item
        status = item["status"]
        if status not in {"available", "planned", "missing", "not_applicable"}:
            errors.append(f"{label}: unknown status")
            continue
        if status in {"planned", "missing"}:
            if role in required:
                errors.append(f"{label}: current phase requires evidence")
            continue
        if status == "not_applicable":
            if role not in OPTIONAL:
                errors.append(f"{label}: this role cannot be waived")
            if not item["note"].strip():
                errors.append(f"{label}: waiver requires a scientific reason")
        if not item["locator"].strip():
            errors.append(f"{label}: required locator within evidence document")
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            errors.append(f"{label}: expected lowercase SHA-256")
            continue
        path = Path(item["path"])
        if not item["path"].strip() or path.is_absolute():
            errors.append(f"{label}: required relative evidence path")
            continue
        try:
            target = (base / path).resolve()
            if not target.is_file() or target.stat().st_size == 0:
                errors.append(f"{label}: evidence must be a nonempty regular file")
            elif sha256(target) != item["sha256"]:
                errors.append(f"{label}: evidence digest mismatch")
        except (OSError, ValueError, RuntimeError):
            errors.append(f"{label}: cannot read evidence file")
    for role in sorted(required - supplied.keys()):
        errors.append(f"{role}: missing required role")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Path to evidence_bundle.json")
    args = parser.parse_args()
    try:
        bundle = json.loads(
            args.bundle.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object, parse_constant=reject_constant,
        )
        errors = check_bundle(bundle, args.bundle.resolve().parent)
    except (OSError, ValueError, RecursionError, RuntimeError):
        errors = ["bundle: cannot read valid evidence JSON"]
    print(json.dumps({
        "document_integrity_pass": not errors,
        "execution_authorized": False,
        "scientific_validity": "not_assessed",
        "errors": errors,
    }, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
