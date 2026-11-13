"""Zero-dependency CLI entrypoint for Medical Research Harness."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import __version__

SUBCOMMAND_SCRIPTS: dict[str, tuple[str, str]] = {
    "study": (
        "study.py",
        "Compile study tasks, audit manifests (planned/executed), run preflight, and summarize attempts",
    ),
    "workflow": (
        "workflow.py",
        "Chain stage checks, manifest audits, evidence bundle validation, and stage handoffs",
    ),
    "check-bundle": (
        "check_bundle.py",
        "Validate stage evidence_bundle.json integrity and SHA-256 digests",
    ),
    "project-audit": (
        "project_audit.py",
        "Run read-only static AST leakage scanning and deterministic manifest/run reconciliation",
    ),
    "literature": (
        "literature.py",
        "Run verbatim-anchored literature risk-of-bias extraction (dry-run by default)",
    ),
    "literature-design": (
        "literature_design.py",
        "Extract multi-layer structured study design and section-aware evidence spans",
    ),
    "literature-offline": (
        "literature_offline.py",
        "Resume or inspect hash-verified offline literature preparation checkpoints",
    ),
    "decision-agent": (
        "decision_agent.py",
        "Run shadow-mode semantic verification over deterministic gate artifacts",
    ),
}


def resolve_skill_root() -> Path:
    """Locate the bundled or repository skill directory containing SKILL.md."""
    pkg_dir = Path(__file__).resolve().parent
    bundled = pkg_dir / "_skill_bundle"
    if (bundled / "SKILL.md").is_file():
        return bundled

    repo_skill = pkg_dir.parents[1] / "skills" / "medical-research-harness"
    if (repo_skill / "SKILL.md").is_file():
        return repo_skill

    raise FileNotFoundError(
        "Could not locate medical-research-harness skill bundle "
        f"(checked {bundled} and {repo_skill})."
    )


def _format_help() -> str:
    lines = [
        f"medical-research-harness {__version__}",
        "",
        "Methodological toolkit and CLI for clinical prediction research design,",
        "provenance-locked manifest auditing, reproducible run reconciliation,",
        "and verbatim-citation literature risk analysis.",
        "",
        "Epistemic Safety Notice:",
        "  Automated checks verify deterministic structural, manifest, and digest",
        "  constraints only (execution_authorized: false, scientific_acceptance: false).",
        "  Passing CLI checks or selftests never grants clinical validity, low risk",
        "  of bias, or scientific approval.",
        "",
        "Usage:",
        "  medical-research-harness [--version] [--help] <subcommand> [args...]",
        "  mrh [--version] [--help] <subcommand> [args...]",
        "",
        "Subcommands:",
    ]
    for name, (_script, desc) in SUBCOMMAND_SCRIPTS.items():
        lines.append(f"  {name:<20} {desc}")
    lines.append(
        f"  {'selftest':<20} Run offline synthetic integrity and study walkthrough self-tests (--out DIR)"
    )
    lines.append(
        f"  {'skill-path':<20} Print resolved path to the medical-research-harness skill directory"
    )
    lines.extend(
        [
            "",
            "Examples:",
            "  medical-research-harness --version",
            "  medical-research-harness selftest",
            "  medical-research-harness study --help",
            "  medical-research-harness check-bundle path/to/evidence_bundle.json",
            "  mrh project-audit --help",
        ]
    )
    return "\n".join(lines)


def _run_bundled_script(skill_root: Path, script_name: str, args: list[str]) -> int:
    script_path = skill_root / "scripts" / script_name
    if not script_path.is_file():
        print(f"error: bundled script not found: {script_path}", file=sys.stderr)
        return 2
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", str(script_path), *args],
        env=env,
        check=False,
    )
    return completed.returncode


def _run_selftest(skill_root: Path, args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="medical-research-harness selftest",
        description=(
            "Run offline synthetic evidence-bundle and study walkthrough self-tests "
            "(execution_authorized: false, scientific_acceptance: false)."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional new directory to persist synthetic study walkthrough artifacts.",
    )
    parsed = parser.parse_args(args)

    rc_bundle = _run_bundled_script(skill_root, "test_check_bundle.py", [])
    if rc_bundle != 0:
        return rc_bundle

    study_args: list[str] = []
    if parsed.out is not None:
        study_args.extend(["--out", str(parsed.out)])
    rc_study = _run_bundled_script(skill_root, "test_study.py", study_args)
    if rc_study != 0:
        return rc_study

    print(
        f"PASS: medical-research-harness {__version__} selftest completed "
        "(execution_authorized: false, scientific_acceptance: false)"
    )
    return 0


def _run_skill_path(skill_root: Path, args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="medical-research-harness skill-path",
        description="Print the resolved path to the bundled medical-research-harness skill directory.",
    )
    parser.parse_args(args)
    print(skill_root)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args[0] in ("-h", "--help"):
        print(_format_help())
        return 0

    if args[0] in ("-V", "--version"):
        if len(args) > 1:
            print("error: --version takes no additional arguments", file=sys.stderr)
            return 2
        print(f"medical-research-harness {__version__}")
        return 0

    subcommand, sub_args = args[0], args[1:]

    try:
        skill_root = resolve_skill_root()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if subcommand == "selftest":
        return _run_selftest(skill_root, sub_args)

    if subcommand == "skill-path":
        return _run_skill_path(skill_root, sub_args)

    if subcommand in SUBCOMMAND_SCRIPTS:
        script_name, _desc = SUBCOMMAND_SCRIPTS[subcommand]
        return _run_bundled_script(skill_root, script_name, sub_args)

    valid = ", ".join([*SUBCOMMAND_SCRIPTS.keys(), "selftest", "skill-path"])
    print(
        f"error: unknown subcommand '{subcommand}'. Valid subcommands: {valid}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
