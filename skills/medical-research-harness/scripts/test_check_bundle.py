#!/usr/bin/env python3
"""Synthetic integrity regressions, not a medical validity evaluation."""

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from check_bundle import check_bundle, sha256


def main():
    skill = Path(__file__).resolve().parents[1]
    script = skill / "scripts/check_bundle.py"
    template = json.loads((skill / "assets/evidence_bundle.json").read_text())
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        assert check_bundle(template, base), "empty template must not pass"
        bundle = copy.deepcopy(template)
        bundle["study_id"] = "synthetic-only"
        bundle["phase"] = "results"
        for item in bundle["artifacts"]:
            path = base / (item["role"] + ".md")
            path.write_text("Synthetic evidence, no medical conclusions.\n")
            item.update(status="available", path=path.name,
                        sha256=sha256(path), locator="line 1")
        assert not check_bundle(bundle, base)
        manifest = base / "evidence_bundle.json"

        def run(value):
            manifest.write_text(json.dumps(value) if not isinstance(value, str) else value)
            result = subprocess.run(
                [sys.executable, str(script), str(manifest)],
                cwd=base.parent, text=True, capture_output=True, check=False,
            )
            assert not result.stderr, result.stderr
            output = json.loads(result.stdout)
            assert output["execution_authorized"] is False
            assert output["scientific_validity"] == "not_assessed"
            return result.returncode, output

        assert run(bundle)[0] == 0, "paths must resolve relative to bundle, not cwd"
        missing = copy.deepcopy(bundle)
        missing["artifacts"].pop()
        assert run(missing)[0] == 1, "results require independent review"
        draft = copy.deepcopy(bundle)
        for item in draft["artifacts"][4:]:
            item["status"] = "planned"
        draft["phase"] = "design"
        assert run(draft)[0] == 0
        draft["phase"] = "preflight"
        assert run(draft)[0] == 1, "planned audits are not execution evidence"

        for field, value in [("phase", []), ("format_version", True), ("artifacts", {})]:
            bad = copy.deepcopy(bundle)
            bad[field] = value
            assert run(bad)[0] == 1
        duplicate = copy.deepcopy(bundle)
        duplicate["artifacts"].append(duplicate["artifacts"][0])
        assert run(duplicate)[0] == 1
        assert run('{"phase":"design","phase":"results"}')[0] == 1
        malformed_code, malformed_output = run('{"secret":"DO_NOT_PRINT", broken}')
        assert malformed_code == 1
        assert "DO_NOT_PRINT" not in json.dumps(malformed_output)
        assert run('{"format_version":NaN}')[0] == 1
        unknown = copy.deepcopy(bundle)
        unknown["artifacts"][0]["role"] = "DO_NOT_PRINT"
        assert "DO_NOT_PRINT" not in json.dumps(run(unknown)[1])

        waiver = copy.deepcopy(bundle)
        waiver["artifacts"][0].update(status="not_applicable", note="unsupported waiver")
        assert run(waiver)[0] == 1, "protocol cannot be waived"
        item = next(a for a in waiver["artifacts"] if a["role"] == "split_audit")
        waiver["artifacts"][0]["status"] = "available"
        item.update(status="not_applicable", note="Synthetic reason, needs human review")
        assert run(waiver)[0] == 0
        item["note"] = ""
        assert run(waiver)[0] == 1

        (base / "protocol.md").write_text("Changed evidence.\n")
        assert run(bundle)[0] == 1, "changed files must invalidate the bundle"
        (base / "protocol.md").unlink()
        assert run(bundle)[0] == 1, "absent evidence must fail"
    print("PASS: synthetic stage, integrity, input and diagnostic checks; no scientific validation")


if __name__ == "__main__":
    main()
