"""Offline unit checks for the synthetic flight-trace reference analyzer."""
import json
import hashlib
import csv
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from analyze_flight import analyze, distance, vec  # noqa: E402


class FlightTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_synthetic_multiactor_gap_and_events(self):
        result = analyze(ROOT / "examples/flight_recorder/example_run", self.root / "report", focus_time=0.08)
        self.assertEqual(result["entities"], 2)
        self.assertEqual(result["frames"], 5)
        self.assertEqual(result["events"], 4)
        self.assertEqual(result["reported_dropped_samples"], 2)
        self.assertEqual(result["missing_per_entity_sample_steps"], 2)
        self.assertEqual(result["parse_errors"], 0)
        kinds = {x["kind"] for x in json.loads((self.root / "report/anomalies.json").read_text())}
        self.assertIn("recorder_gap", kinds)
        self.assertIn("missing_frame_steps", kinds)
        self.assertTrue((self.root / "report/tracks.csv").exists())
        self.assertTrue((self.root / "report/focus.csv").exists())

    def test_zip_bundle(self):
        src = ROOT / "examples/flight_recorder/example_run"
        bundle = self.root / "run.zip"
        with zipfile.ZipFile(bundle, "w") as zf:
            for f in src.rglob("*"):
                if f.is_file():
                    zf.write(f, "run/" + f.name)
        result = analyze(bundle, self.root / "fromzip")
        self.assertEqual(result["frames"], 5)
        self.assertEqual(result["entities"], 2)

    def test_incomplete_capture_and_bad_record(self):
        src = self.root / "bad"
        src.mkdir()
        (src / "metadata.json").write_text(json.dumps({"schema_version": "aicadets.flight.v1", "run_id": "broken", "capture_complete": False}))
        good = {"type": "frame", "step": 1, "t": 0.02, "phase": "post_physics", "samples": [
            {"id": "human:1:0", "kind": "human", "pos": [0, 0, 0], "vel": [0, 0, 0]}]}
        (src / "000001.jsonl").write_text(json.dumps(good) + "\n" + "{truncated\n")
        result = analyze(src, self.root / "bad_report")
        self.assertEqual(result["frames"], 1)
        self.assertEqual(result["parse_errors"], 1)
        self.assertFalse(result["capture_complete"])

    def test_installed_build_provenance_and_incomplete_reason_are_reported(self):
        src = self.root / "adapter_run"
        src.mkdir()
        (src / "metadata.json").write_text(json.dumps({
            "schema_version": "aicadets.flight.v1",
            "run_id": "adapter-run",
            "capture_tier": "partial_il2cpp_periodic_discovery_v1",
            "capture_complete": False,
            "installed_build_fingerprint": {"unity_version": "2023.1.22f1", "architecture": "x64"},
            "runtime_observation_phase": "fixed_update_pre_physics_order_unspecified",
            "sample_phase_verified": False,
            "step_source": "adapter FixedUpdate callback ordinal",
            "timestamp_clock": "UnityEngine.Time.fixedTimeAsDouble",
            "discovery_interval_seconds": 0.5,
            "incomplete_reasons": [{"reason": "receiver_interrupted", "count": 1}],
        }))
        (src / "000001.jsonl").write_text(json.dumps({
            "type": "frame", "step": 1, "t": 0.02, "phase": "pre_physics",
            "samples": [],
        }) + "\n")

        result = analyze(src, self.root / "adapter_report")
        report = (self.root / "adapter_report/report.md").read_text()
        self.assertEqual(result["game_build"], "2023.1.22f1 / x64")
        self.assertFalse(result["sample_phase_verified"])
        self.assertEqual(result["runtime_observation_phase"], "fixed_update_pre_physics_order_unspecified")
        self.assertEqual(result["incomplete_reasons"][0]["reason"], "receiver_interrupted")
        self.assertIn("receiver_interrupted", report)
        self.assertNotIn("has not yet been installed", report)

    def test_nonfinite_vectors_rejected(self):
        with self.assertRaises(ValueError):
            vec([float("nan"), 0, 1])
        self.assertAlmostEqual(distance((0, 0, 0), (3, 4, 0)), 5)

    def test_stalled_command_detection(self):
        src = self.root / "stalled"
        src.mkdir()
        entries = [
            {"type": "frame", "step": 1, "t": 0.02, "phase": "post_physics", "samples": [
                {"id": "human:42:0", "kind": "human", "pos": [0, 0, 0], "vel": [0, 0, 0]}]},
            {"type": "event", "step": 1, "t": 0.02, "event": "command", "id": "human:42:0", "action": "MoveTo", "evidence": "observed"},
            {"type": "frame", "step": 101, "t": 2.02, "phase": "post_physics", "samples": [
                {"id": "human:42:0", "kind": "human", "pos": [0.1, 0, 0], "vel": [0, 0, 0]}]},
        ]
        (src / "000001.jsonl").write_text("\n".join(json.dumps(x) for x in entries) + "\n")
        analyze(src, self.root / "stalled_report")
        kinds = [x["kind"] for x in json.loads((self.root / "stalled_report/anomalies.json").read_text())]
        self.assertIn("command_no_motion", kinds)
        self.assertIn("missing_frame_steps", kinds)

    def test_chunk_index_verifies_hash_and_fixed_step_coverage(self):
        src = self.root / "indexed"
        src.mkdir()
        rows = [
            {"type": "frame", "step": 1, "t": 0.02, "fixed_delta_time": 0.02,
             "phase": "post_physics", "samples": [{"id": "human:1:0", "kind": "human", "pos": [0, 0, 0]}]},
            {"type": "frame", "step": 2, "t": 0.04, "fixed_delta_time": 0.02,
             "phase": "post_physics", "samples": [{"id": "human:1:0", "kind": "human", "pos": [1, 0, 0]}]},
        ]
        payload = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
        (src / "000001.jsonl").write_bytes(payload)
        (src / "metadata.json").write_text(json.dumps({"schema_version": "aicadets.flight.v1", "fixed_delta_time": 0.02}))
        (src / "chunk_manifest.json").write_text(json.dumps({
            "manifest_schema": "aicadets.flight.chunk-index.v1",
            "chunks": [{"file": "000001.jsonl", "sha256": hashlib.sha256(payload).hexdigest(),
                        "bytes": len(payload), "frame_count": 2, "first_step": 1, "last_step": 2}],
        }))

        result = analyze(src, self.root / "indexed_report")
        self.assertEqual(result["integrity_status"], "verified")
        self.assertEqual(result["frame_coverage_ratio"], 1.0)
        self.assertEqual(result["observed_entity_kinds"], ["human"])

    def test_corrupt_chunk_is_rejected_and_remaining_chunk_is_recovered(self):
        src = self.root / "partial"
        src.mkdir()
        good = (json.dumps({"type": "frame", "step": 1, "t": 0.02, "phase": "post_physics",
                            "samples": [{"id": "human:1:0", "kind": "human", "pos": [0, 0, 0]}]}) + "\n").encode()
        expected_bad = (json.dumps({"type": "frame", "step": 2, "t": 0.04, "phase": "post_physics",
                                    "samples": [{"id": "human:1:0", "kind": "human", "pos": [1, 0, 0]}]}) + "\n").encode()
        actual_bad = expected_bad.replace(b"[1, 0, 0]", b"[9, 0, 0]")
        (src / "000001.jsonl").write_bytes(good)
        (src / "000002.jsonl").write_bytes(actual_bad)
        (src / "metadata.json").write_text(json.dumps({"schema_version": "aicadets.flight.v1"}))
        (src / "chunk_manifest.json").write_text(json.dumps({
            "manifest_schema": "aicadets.flight.chunk-index.v1",
            "chunks": [
                {"file": "000001.jsonl", "sha256": hashlib.sha256(good).hexdigest(),
                 "bytes": len(good), "frame_count": 1, "first_step": 1, "last_step": 1},
                {"file": "000002.jsonl", "sha256": hashlib.sha256(expected_bad).hexdigest(),
                 "bytes": len(expected_bad), "frame_count": 1, "first_step": 2, "last_step": 2},
            ],
        }))

        result = analyze(src, self.root / "partial_report")
        kinds = {item["kind"] for item in json.loads((self.root / "partial_report/anomalies.json").read_text())}
        self.assertEqual(result["integrity_status"], "partial")
        self.assertEqual(result["valid_chunks"], 1)
        self.assertEqual(result["integrity_failures"], 1)
        self.assertEqual(result["frame_coverage_ratio"], 0.5)
        self.assertIn("chunk_integrity_failure", kinds)
        self.assertIn("frame_coverage_incomplete", kinds)

    def test_manifest_frame_index_is_compared_to_parsed_chunk(self):
        src = self.root / "wrong_index"
        src.mkdir()
        payload = (json.dumps({"type": "frame", "step": 5, "t": 0.1, "phase": "post_physics",
                              "samples": [{"id": "human:1:0", "kind": "human", "pos": [0, 0, 0]}]}) + "\n").encode()
        (src / "000001.jsonl").write_bytes(payload)
        (src / "metadata.json").write_text(json.dumps({"schema_version": "aicadets.flight.v1"}))
        (src / "chunk_manifest.json").write_text(json.dumps({
            "manifest_schema": "aicadets.flight.chunk-index.v1",
            "chunks": [{"file": "000001.jsonl", "sha256": hashlib.sha256(payload).hexdigest(),
                        "bytes": len(payload), "frame_count": 2, "first_step": 1, "last_step": 2}],
        }))
        result = analyze(src, self.root / "wrong_index_report")
        kinds = {item["kind"] for item in json.loads((self.root / "wrong_index_report/anomalies.json").read_text())}
        self.assertEqual(result["integrity_status"], "partial")
        self.assertEqual(result["integrity_failures"], 1)
        self.assertIn("chunk_index_mismatch", kinds)

    def test_invalid_manifest_frame_count_cannot_report_verified_coverage(self):
        src = self.root / "invalid_manifest_count"
        src.mkdir()
        payload = (json.dumps({"type": "frame", "step": 1, "t": 0.02, "phase": "post_physics",
                              "samples": [{"id": "human:1:0", "pos": [0, 0, 0]}]}) + "\n").encode()
        (src / "000001.jsonl").write_bytes(payload)
        (src / "metadata.json").write_text(json.dumps({"schema_version": "aicadets.flight.v1"}))
        (src / "chunk_manifest.json").write_text(json.dumps({
            "manifest_schema": "aicadets.flight.chunk-index.v1",
            "chunks": [{"file": "000001.jsonl", "sha256": hashlib.sha256(payload).hexdigest(),
                        "bytes": len(payload), "frame_count": "1"}],
        }))
        result = analyze(src, self.root / "invalid_manifest_count_report")
        self.assertEqual(result["integrity_status"], "partial")
        self.assertIsNone(result["frame_coverage_ratio"])
        self.assertEqual(result["integrity_failures"], 1)

    def test_frame_level_fixed_delta_time_is_checked(self):
        src = self.root / "frame_delta"
        src.mkdir()
        records = [
            {"type": "frame", "step": 1, "t": 0.02, "fixed_delta_time": 0.02,
             "phase": "post_physics", "samples": [{"id": "human:1:0", "pos": [0, 0, 0]}]},
            {"type": "frame", "step": 2, "t": 0.04, "fixed_delta_time": 0.03,
             "phase": "post_physics", "samples": [{"id": "human:1:0", "pos": [0, 0, 0]}]},
        ]
        (src / "000001.jsonl").write_text("\n".join(json.dumps(row) for row in records) + "\n")
        (src / "metadata.json").write_text(json.dumps({"schema_version": "aicadets.flight.v1"}))
        analyze(src, self.root / "frame_delta_report")
        kinds = {item["kind"] for item in json.loads((self.root / "frame_delta_report/anomalies.json").read_text())}
        self.assertIn("fixed_step_time_mismatch", kinds)

    def test_collision_requires_observed_contact_event_not_velocity_spike(self):
        src = self.root / "events"
        src.mkdir()
        records = []
        for step in range(1, 53):
            t = step * 0.02
            if step == 52:
                records.append({"type": "event", "step": step, "t": t, "event": "collision",
                                "id": "human:attack:0", "ids": ["building:1:0"], "evidence": "observed"})
            records.append({"type": "frame", "step": step, "t": t, "phase": "post_physics",
                            "samples": [
                                {"id": "human:attack:0", "kind": "human", "pos": [step * 0.02, 0, 0],
                                 "vel": [10, 0, 0] if step == 52 else [0, 0, 0]},
                                {"id": "human:hook:0", "kind": "human", "pos": [step * 0.02, 0, 2],
                                 "vel": [10, 0, 0] if step == 52 else [0, 0, 0]},
                            ]})
            if step == 1:
                records += [
                    {"type": "event", "step": step, "t": t, "event": "attack_input", "id": "human:attack:0", "evidence": "observed"},
                    {"type": "event", "step": step, "t": t, "event": "hook_launch", "id": "human:hook:0", "evidence": "observed"},
                ]
        (src / "000001.jsonl").write_text("\n".join(json.dumps(row) for row in records) + "\n")

        analyze(src, self.root / "events_report")
        anomalies = json.loads((self.root / "events_report/anomalies.json").read_text())
        attack = [a for a in anomalies if a["kind"] == "attack_outcome_unconfirmed"]
        hook = [a for a in anomalies if a["kind"] == "hook_attachment_unconfirmed"]
        impulse = [a for a in anomalies if a["kind"] == "unexplained_velocity_change"]
        self.assertEqual(len(attack), 1)
        self.assertEqual(len(hook), 1)
        self.assertEqual([a["entity"] for a in impulse], ["human:hook:0"])
        self.assertEqual(impulse[0]["confidence"], "indication")

    def test_attack_outcome_requires_observed_matching_correlation(self):
        def run_case(name, evidence, outcome_correlation, should_resolve):
            src = self.root / name
            src.mkdir()
            records = [
                {"type": "frame", "step": 1, "t": 0.02, "phase": "post_physics",
                 "samples": [{"id": "human:1:0", "kind": "human", "pos": [0, 0, 0]}]},
                {"type": "event", "step": 1, "t": 0.02, "event": "attack_input",
                 "id": "human:1:0", "correlation_id": "attack-7", "evidence": "observed"},
                {"type": "event", "step": 2, "t": 0.04, "event": "damage", "actor": "human:1:0",
                 "correlation_id": outcome_correlation, "evidence": evidence},
            ]
            for step in range(2, 53):
                records.append({"type": "frame", "step": step, "t": step * 0.02,
                                "phase": "post_physics", "samples": [
                                    {"id": "human:1:0", "kind": "human", "pos": [0, 0, 0]}]})
            (src / "000001.jsonl").write_text("\n".join(json.dumps(row) for row in records) + "\n")
            report = self.root / (name + "_report")
            analyze(src, report)
            anomalies = json.loads((report / "anomalies.json").read_text())
            has_unconfirmed = any(a["kind"] == "attack_outcome_unconfirmed" for a in anomalies)
            self.assertEqual(has_unconfirmed, not should_resolve, name)
            with (report / "timeline.csv").open(newline="", encoding="utf-8") as handle:
                timeline = list(csv.DictReader(handle))
            damage = next(row for row in timeline if row["event"] == "damage")
            self.assertEqual(damage["correlation_id"], outcome_correlation, name)

        run_case("matching_observed_damage", "observed", "attack-7", True)
        run_case("inferred_damage", "inferred", "attack-7", False)
        run_case("unrelated_observed_damage", "observed", "attack-8", False)

    def test_hook_attachment_requires_observed_matching_correlation(self):
        src = self.root / "hook_correlation"
        src.mkdir()
        records = [
            {"type": "frame", "step": 1, "t": 0.02, "phase": "post_physics",
             "samples": [{"id": "human:1:0", "kind": "human", "pos": [0, 0, 0]}]},
            {"type": "event", "step": 1, "t": 0.02, "event": "hook_launch",
             "id": "human:1:0", "correlation_id": "hook-4", "evidence": "observed"},
            {"type": "event", "step": 2, "t": 0.04, "event": "hook_attached",
             "id": "human:1:0", "correlation_id": "other-hook", "evidence": "observed"},
        ]
        for step in range(2, 53):
            records.append({"type": "frame", "step": step, "t": step * 0.02,
                            "phase": "post_physics", "samples": [
                                {"id": "human:1:0", "kind": "human", "pos": [0, 0, 0]}]})
        (src / "000001.jsonl").write_text("\n".join(json.dumps(row) for row in records) + "\n")
        analyze(src, self.root / "hook_correlation_report")
        anomalies = json.loads((self.root / "hook_correlation_report/anomalies.json").read_text())
        self.assertIn("hook_attachment_unconfirmed", {a["kind"] for a in anomalies})


if __name__ == "__main__":
    unittest.main()
