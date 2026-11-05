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

    def test_zip_bundle_with_manifest_and_enclosing_directory(self):
        frame = {"type": "frame", "step": 1, "t": 0.02, "phase": "post_physics", "samples": [
            {"id": "human:1:1", "kind": "human", "pos": [0, 0, 0], "vel": [0, 0, 0]}]}
        payload = (json.dumps(frame) + "\n").encode("utf-8")
        metadata = {"schema_version": "aicadets.flight.v1", "run_id": "nested-zip",
                    "capture_complete": True}
        manifest = {"manifest_schema": "aicadets.flight.chunk-index.v1", "chunks": [{
            "file": "chunk-000001.jsonl", "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(), "frame_count": 1,
            "first_step": 1, "last_step": 1}]}
        bundle = self.root / "nested-run.zip"
        with zipfile.ZipFile(bundle, "w") as zf:
            zf.writestr("nested-run/metadata.json", json.dumps(metadata))
            zf.writestr("nested-run/chunk_manifest.json", json.dumps(manifest))
            zf.writestr("nested-run/chunk-000001.jsonl", payload)

        result = analyze(bundle, self.root / "nested_zip_report")
        self.assertEqual(result["frames"], 1)
        self.assertEqual(result["entities"], 1)
        self.assertEqual(result["valid_chunks"], 1)
        self.assertEqual(result["integrity_status"], "verified")
        self.assertEqual(result["unindexed_chunks"], 0)

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

    def test_producer_performance_gate_uses_monotonic_startup_and_all_sample_maxima(self):
        src = self.root / "health_gate"
        src.mkdir()
        metadata = {
            "schema_version": "aicadets.flight.v1",
            "run_id": "health-gate",
            "capture_complete": True,
            "sample_phase_verified": False,
            "runtime_observation_phase": "fixed_update_pre_physics",
            "writer_limits": {"queue_capacity": 256, "max_queue_bytes": 64 * 1024 * 1024},
            "writer_stats": {"max_queue_depth": 4, "max_queue_bytes": 2048,
                             "queue_dropped_frames": 0, "storage_dropped_frames": 0,
                             "queue_dropped_entity_samples": 0, "storage_dropped_entity_samples": 0,
                             "fatal_error": None, "storage_exhausted": False},
        }
        frame = {"type": "frame", "step": 1, "t": 0.02, "fixed_delta_time": 0.02,
                 "samples": [
                     {"id": "human:1:1", "kind": "human", "pos": [0, 0, 0]},
                     {"id": "titan:2:1", "kind": "titan", "pos": [5, 0, 0]},
                 ]}
        health = [
            {"type": "event", "event": "producer_health", "step": 1, "t": 0.02,
             "wall_monotonic_elapsed_seconds": 10.0, "capture_work_ms_p95": 9.0,
             "capture_work_ms_maximum": 70.0, "queue_depth": 2, "queue_bytes": 512},
            {"type": "event", "event": "producer_health", "step": 2, "t": 0.04,
             "wall_monotonic_elapsed_seconds": 20.0, "capture_work_ms_p95": 1.0,
             "capture_work_ms_maximum": 59.9, "queue_depth": 3, "queue_bytes": 768},
            {"type": "event", "event": "producer_health", "step": 3, "t": 0.06,
             "wall_monotonic_elapsed_seconds": 25.0, "capture_work_ms_p95": 1.001,
             "capture_work_ms_maximum": 60.1, "queue_depth": 4, "queue_bytes": 1024},
        ]
        (src / "metadata.json").write_text(json.dumps(metadata))
        (src / "000001.jsonl").write_text("\n".join(json.dumps(row) for row in [frame, *health]) + "\n")

        result = analyze(src, self.root / "health_gate_report",
                         producer_queue_capacity=512, producer_queue_max_bytes=4 * 1024 * 1024)
        report = (self.root / "health_gate_report/report.md").read_text()
        performance = result["producer_performance"]
        self.assertEqual(performance["post_15s_windows"], 2)
        self.assertEqual(performance["post_15s_windows_over_p95_limit"], 1)
        self.assertEqual(performance["maximum_reported_sample_ms"], 70.0)
        self.assertEqual(performance["gate_status"], "fail")
        self.assertTrue(performance["queue_bounded"])
        self.assertEqual(performance["producer_queue_max_sampled_depth"], 4)
        self.assertEqual(performance["writer_queue_high_water_depth"], 4)
        self.assertEqual(performance["writer_queue_high_water_bytes"], 2048)
        self.assertFalse(result["sample_phase_verified"])
        self.assertIn("Calibration result: not performed; observation phase remains unverified.", report)
        self.assertIn("maximum reported capture-work sample exceeds 60.0 ms", report)

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
