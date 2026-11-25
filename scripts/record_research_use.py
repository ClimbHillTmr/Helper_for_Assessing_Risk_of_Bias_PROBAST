#!/usr/bin/env python3
"""Privacy-safe aggregate research-use evidence packager for Track 2 (JOSS).

Pure Python 3.10+ standard library. Inspects completed aggregate outputs from an
external clinical prediction study audited with `medical-research-harness`
(`audit-executed.json`, `summary.json`, `completion.json`, `workflow.json`),
verifies that no raw patient-row manifests, credentials, or false scientific
acceptance flags are included, and writes an editor-reviewable aggregate digest
record.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORBIDDEN_FILENAMES = {
    "rows.csv",
    "folds.csv",
    "fits.csv",
    "planned_fits.csv",
    "executed_fits.csv",
    "predictions.csv",
    "patients.csv",
}

FORBIDDEN_EXTENSIONS = {".parquet", ".feather", ".h5", ".hdf5", ".sqlite", ".db", ".env"}

FORBIDDEN_KEYS = {
    "patient_id",
    "patient_ids",
    "row_id",
    "row_ids",
    "raw_rows",
    "predictions",
    "embeddings",
    "api_key",
    "access_token",
    "password",
    "secret",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan_payload(obj: Any, path_prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            here = f"{path_prefix}.{k}"
            if kl in FORBIDDEN_KEYS:
                violations.append(f"forbidden key {here}")
            if kl == "scientific_acceptance" and v is True:
                violations.append(f"invalid scientific_acceptance=true at {here}")
            violations.extend(_scan_payload(v, here))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            violations.extend(_scan_payload(item, f"{path_prefix}[{idx}]"))
    return violations


def collect_research_use_record(
    study_id: str,
    harness_version: str,
    artifact_paths: list[Path],
    summary_note: str,
    limitations: str,
) -> dict[str, Any]:
    if not study_id.strip():
        raise ValueError("study_id must be non-empty")
    if not artifact_paths:
        raise ValueError("at least one aggregate JSON artifact path is required")

    artifacts: list[dict[str, Any]] = []
    violations: list[str] = []
    has_executed_audit = False

    for raw_path in artifact_paths:
        p = raw_path.resolve()
        if not p.is_file():
            raise FileNotFoundError(f"artifact not found: {raw_path}")
        if p.name.lower() in FORBIDDEN_FILENAMES or p.suffix.lower() in FORBIDDEN_EXTENSIONS:
            violations.append(f"forbidden row-level or sensitive file: {p.name}")
            continue
        if p.suffix.lower() != ".json":
            violations.append(f"only aggregate .json artifacts are supported: {p.name}")
            continue

        data = json.loads(p.read_text(encoding="utf-8"))
        file_violations = _scan_payload(data, p.name)
        violations.extend(file_violations)

        mode = data.get("mode") if isinstance(data, dict) else None
        if mode == "executed" or (
            isinstance(data, dict) and data.get("fresh_executed_audit") is True
        ):
            has_executed_audit = True

        artifacts.append(
            {
                "filename": p.name,
                "sha256": sha256_file(p),
                "size_bytes": p.stat().st_size,
                "top_level_keys": sorted(data.keys()) if isinstance(data, dict) else [],
                "recorded_ok": data.get("ok") if isinstance(data, dict) else None,
                "mode": mode,
                "execution_authorized": (
                    data.get("execution_authorized") if isinstance(data, dict) else False
                ),
                "scientific_acceptance": (
                    data.get("scientific_acceptance") if isinstance(data, dict) else False
                ),
            }
        )

    if violations:
        raise ValueError("Privacy/epistemic safety gate failed: " + "; ".join(violations))

    return {
        "schema_version": 1,
        "study_id": study_id.strip(),
        "harness_version": harness_version.strip(),
        "summary": summary_note.strip(),
        "limitations": limitations.strip(),
        "fresh_executed_audit_detected": has_executed_audit,
        "privacy_gate_passed": True,
        "scientific_acceptance": False,
        "execution_authorized": False,
        "artifacts": artifacts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate aggregate harness artifacts from a real study and emit a "
            "privacy-safe JSON evidence record for JOSS Research Impact tracking."
        )
    )
    parser.add_argument("--study-id", required=True, help="Short study identifier")
    parser.add_argument("--harness-version", default="0.2.0", help="Harness version used")
    parser.add_argument("--summary", required=True, help="Concise factual summary of use")
    parser.add_argument(
        "--limitations",
        required=True,
        help="Explicit limits/failed runs/scope boundaries of the recorded use",
    )
    parser.add_argument("--out", required=True, help="Output JSON path (must not overwrite frozen data)")
    parser.add_argument(
        "artifacts",
        nargs="+",
        help="One or more aggregate JSON files (e.g., audit-executed.json, summary.json, completion.json)",
    )
    args = parser.parse_args(argv)

    out_path = Path(args.out)
    if out_path.exists():
        print(f"ERROR: refusing to overwrite existing output: {out_path}", file=sys.stderr)
        return 2

    try:
        record = collect_research_use_record(
            study_id=args.study_id,
            harness_version=args.harness_version,
            artifact_paths=[Path(a) for a in args.artifacts],
            summary_note=args.summary,
            limitations=args.limitations,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ok": True, "out": str(out_path), "artifacts": len(record["artifacts"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
