"""Definition-status checks for the M3 catalog; no maneuver is executed."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ManeuverCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / "docs/M3_MANEUVER_CATALOG.json").read_text())

    def test_schema_statuses_ids_and_api_revision(self):
        self.assertEqual(self.catalog["schema_version"], 1)
        self.assertEqual(self.catalog["api_documentation_revision"], "38796d52a99c2dd76ec08a111395628a9151d07e")
        entries = self.catalog["entries"]
        self.assertEqual(len({item["id"] for item in entries}), len(entries))
        for item in entries:
            self.assertIn(item["status"], {"definition_only", "experimental", "validated"})
            self.assertIn("required_commands", item)
            self.assertIn("required_state", item)
            self.assertIn("estimated_gas_cost", item)
            self.assertIn("evidence_required_for_validation", item)

    def test_only_the_historical_m0_reference_is_marked_validated(self):
        validated = [item["id"] for item in self.catalog["entries"] if item["status"] == "validated"]
        self.assertEqual(validated, ["single_hook_m0_reference"])
        self.assertIn("43.68573", next(item["evidence"] for item in self.catalog["entries"]
                                     if item["id"] == "single_hook_m0_reference"))

    def test_unverified_compounds_and_special_primitives_remain_definition_only(self):
        by_id = {item["id"]: item for item in self.catalog["entries"]}
        self.assertEqual(by_id["two_hook_tether"]["status"], "definition_only")
        self.assertEqual(by_id["reel_impulse"]["status"], "definition_only")
        for action_id in ("directional_dash_ground", "jump_then_dash_forward", "airborne_dash_forward"):
            self.assertEqual(by_id[action_id]["status"], "experimental")


if __name__ == "__main__":
    unittest.main()
