"""Offline tests for privacy-safe aggregate research-use evidence packaging."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "record_research_use", ROOT / "scripts/record_research_use.py"
)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


class RecordResearchUseTests(unittest.TestCase):
    def test_accepts_clean_executed_aggregate_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit-executed.json"
            audit.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "mode": "executed",
                        "execution_authorized": False,
                        "scientific_acceptance": False,
                        "violation_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            out = root / "evidence_record.json"
            rc = MOD.main(
                [
                    "--study-id",
                    "synthetic-clinical-demo",
                    "--summary",
                    "Aggregate executed-fit check on synthetic fixture.",
                    "--limitations",
                    "Synthetic fixture only; not clinical validation.",
                    "--out",
                    str(out),
                    str(audit),
                ]
            )
            self.assertEqual(rc, 0)
            rec = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(rec["privacy_gate_passed"])
            self.assertTrue(rec["fresh_executed_audit_detected"])
            self.assertFalse(rec["scientific_acceptance"])
            self.assertEqual(len(rec["artifacts"]), 1)

    def test_rejects_patient_id_and_row_level_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_json = root / "leaky.json"
            bad_json.write_text(
                json.dumps({"patient_ids": ["P001", "P002"], "ok": True}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "forbidden key"):
                MOD.collect_research_use_record(
                    "bad", "0.2.0", [bad_json], "sum", "lim"
                )

            rows_csv = root / "rows.csv"
            rows_csv.write_text("row_id,patient_id\n1,P001\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "forbidden row-level"):
                MOD.collect_research_use_record(
                    "bad-csv", "0.2.0", [rows_csv], "sum", "lim"
                )

    def test_rejects_false_scientific_acceptance_and_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_accept = root / "bad.json"
            bad_accept.write_text(
                json.dumps({"ok": True, "scientific_acceptance": True}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "scientific_acceptance=true"):
                MOD.collect_research_use_record(
                    "bad-acc", "0.2.0", [bad_accept], "sum", "lim"
                )

            clean = root / "clean.json"
            clean.write_text(json.dumps({"ok": True, "mode": "executed"}), encoding="utf-8")
            existing = root / "exists.json"
            existing.write_text("{}\n", encoding="utf-8")
            rc = MOD.main(
                [
                    "--study-id",
                    "no-clobber",
                    "--summary",
                    "s",
                    "--limitations",
                    "l",
                    "--out",
                    str(existing),
                    str(clean),
                ]
            )
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
