"""Regression coverage for Flight v1 kill attribution and collision matching."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from analyze_flight import analyze  # noqa: E402


class KillAttributionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def human(t, step, state="Attack"):
        return {
            "id": "human:ai-cadet:1", "kind": "human", "step": step, "t": t,
            "pos": [0.0, 0.0, 0.0], "state": state,
            "ai_controlled": True, "animation_game_method": "Armature|attack1_hook_r2",
        }

    @staticmethod
    def titan(t, step, dead=False):
        return {
            "id": "titan:target:1", "kind": "titan", "step": step, "t": t,
            "pos": [2.0, 0.0, 0.0], "state": "Dead" if dead else "Idle",
            "current_health": 0 if dead else 1, "dead_flag": dead,
            "animation_game_method": "Amarture_VER2|die.front" if dead else "Amarture_VER2|idle",
        }

    def run_records(self, name, records):
        source = self.root / name
        source.mkdir()
        (source / "000001.jsonl").write_text(
            "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
        report = self.root / (name + "_report")
        analyze(source, report)
        return report

    def test_repeated_observed_titan_contacts_and_attack_state_are_strong_inference(self):
        actor = "human:ai-cadet:1"
        target = "titan:target:1"
        records = [
            {"type": "frame", "step": 1, "t": 0.02, "phase": "fixture",
             "samples": [self.human(0.02, 1), self.titan(0.02, 1)]},
            {"type": "event", "event": "collision", "evidence": "observed", "actor": actor,
             "other_character_id": target, "other_character_class": "Characters.BaseTitan",
             "step": 1, "t": 0.02},
            {"type": "event", "event": "collision", "evidence": "observed", "actor": actor,
             "other_character_id": target, "other_character_class": "Characters.BaseTitan",
             "step": 2, "t": 0.04},
            {"type": "frame", "step": 2, "t": 0.04, "phase": "fixture",
             "samples": [self.human(0.04, 2), self.titan(0.04, 2)]},
            {"type": "event", "event": "collision", "evidence": "observed", "actor": actor,
             "other_character_id": target, "other_character_class": "Characters.BaseTitan",
             "step": 3, "t": 0.06},
            {"type": "frame", "step": 3, "t": 0.06, "phase": "fixture",
             "samples": [self.human(0.06, 3), self.titan(0.06, 3, dead=True)]},
        ]
        report = self.run_records("strong_inference", records)
        deaths = json.loads((report / "kill_attributions.json").read_text())
        self.assertEqual(len(deaths), 1)
        death = deaths[0]
        self.assertEqual(death["attribution_status"], "strong_inferred_candidate")
        self.assertFalse(death["direct_kill_attribution_observed"])
        self.assertEqual(death["evidence"], "sampled_state_transition")
        self.assertEqual(death["candidates"][0]["actor_id"], actor)
        self.assertEqual(death["candidates"][0]["evidence_classification"], "strong_inference")
        self.assertEqual(death["candidates"][0]["observed_target_collision_count"], 3)

    def test_attack_state_without_target_contact_does_not_attribute_death(self):
        records = [
            {"type": "frame", "step": 1, "t": 0.02, "phase": "fixture",
             "samples": [self.human(0.02, 1), self.titan(0.02, 1)]},
            {"type": "frame", "step": 2, "t": 0.04, "phase": "fixture",
             "samples": [self.human(0.04, 2), self.titan(0.04, 2, dead=True)]},
        ]
        report = self.run_records("no_contact", records)
        death = json.loads((report / "kill_attributions.json").read_text())[0]
        self.assertEqual(death["attribution_status"], "unattributed")
        self.assertEqual(death["candidates"], [])

    def test_matching_observed_damage_event_is_reported_separately(self):
        actor = "human:ai-cadet:1"
        target = "titan:target:1"
        records = [
            {"type": "frame", "step": 1, "t": 0.02, "phase": "fixture",
             "samples": [self.human(0.02, 1), self.titan(0.02, 1)]},
            {"type": "event", "event": "death", "evidence": "observed", "actor": actor,
             "target_id": target, "step": 2, "t": 0.04},
            {"type": "frame", "step": 2, "t": 0.04, "phase": "fixture",
             "samples": [self.human(0.04, 2), self.titan(0.04, 2, dead=True)]},
        ]
        report = self.run_records("direct_death", records)
        death = json.loads((report / "kill_attributions.json").read_text())[0]
        self.assertEqual(death["attribution_status"], "direct_death_attribution_observed")
        self.assertTrue(death["direct_kill_attribution_observed"])

    def test_adapter_collision_fields_correlate_velocity_change_to_both_actors(self):
        actor = "human:ai-cadet:1"
        target = "titan:target:1"
        records = [
            {"type": "frame", "step": 1, "t": 0.02, "phase": "fixture",
             "samples": [{"id": actor, "kind": "human", "pos": [0, 0, 0], "vel": [0, 0, 0]},
                         {"id": target, "kind": "titan", "pos": [1, 0, 0], "vel": [0, 0, 0]}]},
            {"type": "event", "event": "collision", "evidence": "observed", "actor": actor,
             "fields": {"other_character_id": target, "other_character_class": "Characters.BaseTitan"},
             "step": 1, "t": 0.02},
            {"type": "frame", "step": 2, "t": 0.04, "phase": "fixture",
             "samples": [{"id": actor, "kind": "human", "pos": [0, 0, 0], "vel": [9, 0, 0]},
                         {"id": target, "kind": "titan", "pos": [1, 0, 0], "vel": [9, 0, 0]}]},
        ]
        report = self.run_records("collision_correlation", records)
        anomalies = json.loads((report / "anomalies.json").read_text())
        velocity_anomalies = [item for item in anomalies if item["kind"] == "unexplained_velocity_change"]
        self.assertEqual(velocity_anomalies, [])


if __name__ == "__main__":
    unittest.main()
