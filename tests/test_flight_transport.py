"""Protocol and writer-bridge checks; Windows pipe ACL/runtime smoke is separate."""
import json
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from analyze_flight import analyze  # noqa: E402
from flight_transport import (  # noqa: E402
    DISCONNECT_RECONNECT_GRACE_SECONDS,
    FlightTransportReceiver,
    MAX_ENVELOPE_BYTES,
    PROTOCOL,
    TransportProtocolError,
    parse_envelope,
)


def envelope(run_id, sequence, kind, payload):
    return json.dumps({"protocol": PROTOCOL, "run_id": run_id, "sequence": sequence,
                       "kind": kind, "payload": payload}, separators=(",", ":")).encode()


def hello(run_id):
    return envelope(run_id, 1, "hello", {
        "producer": "test-adapter", "producer_version": "test",
        "writer_schema": "aicadets.flight.v1",
        "runtime_observation_phase": "fixed_update_pre_physics",
        "declared_coverage": {"human": "unverified-test-fixture"},
    })


def frame(step, t, x):
    return {"step": step, "t": t, "phase": "fixed_update_pre_physics",
            "fixed_delta_time": 0.02,
            "samples": [{"id": "human:fixture:1", "kind": "human", "pos": [x, 0, 0],
                         "vel": [1, 0, 0], "rot": [0, 0, 0, 1], "extra": {"source": "fixture"}}]}


class FlightTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run_id = uuid.uuid4().hex
        self.receiver = FlightTransportReceiver(self.root / "recordings", writer_options={
            "max_storage_bytes": 4 * 1024 * 1024,
            "control_reserve_bytes": 64 * 1024,
            "chunk_target_bytes": 8 * 1024,
            "max_chunks": 8,
        })

    def tearDown(self):
        if self.receiver.writer is not None and not self.receiver.stopped:
            self.receiver.close_uncleanly("test_teardown")
        self.temp.cleanup()

    def test_protocol_rejects_duplicates_oversize_and_wrong_shapes(self):
        with self.assertRaises(TransportProtocolError):
            parse_envelope(b'{"protocol":"aicadets.flight.transport.v1","protocol":"x"}')
        with self.assertRaises(TransportProtocolError):
            parse_envelope(b"x" * (MAX_ENVELOPE_BYTES + 1))
        with self.assertRaises(TransportProtocolError):
            parse_envelope(json.dumps({"protocol": PROTOCOL, "run_id": self.run_id,
                                       "sequence": True, "kind": "hello", "payload": {}}).encode())

    def test_new_run_id_is_rejected_without_a_new_pipe_connection(self):
        self.receiver.accept_line(hello(self.run_id))
        with self.assertRaises(TransportProtocolError):
            self.receiver.accept_line(hello(uuid.uuid4().hex))

    def test_explicit_frame_gap_and_writer_schema_round_trip(self):
        self.assertTrue(self.receiver.accept_line(hello(self.run_id)))
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 2, "lifecycle", {
            "action": "spawn", "id": "human:fixture:1", "kind": "human", "t": 0.02,
            "step": 0, "evidence": "observed",
        })))
        first = envelope(self.run_id, 3, "frame", frame(0, 0.02, 0.0))
        self.assertTrue(self.receiver.accept_line(first))
        self.assertTrue(self.receiver.accept_line(first))  # Retry after a broken pipe is idempotent.
        self.assertTrue(self.receiver.accept_line(first + b"\r\n"))
        self.assertTrue(self.receiver.accept_line(first + b"\n"))
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 6, "gap", {
            "first_sequence": 4, "last_sequence": 5, "dropped_frames": 2,
            "first_step": 1, "last_step": 2, "dropped_entity_samples": None,
            "reported_at_t": 0.08, "reported_at_step": 3,
        })))
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 7, "frame", frame(3, 0.08, 0.06))))
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 8, "event", {
            "event": "controller_command", "t": 0.08, "id": "human:fixture:1",
            "evidence": "observed", "fields": {"command": "move"},
        })))
        self.assertFalse(self.receiver.accept_line(envelope(self.run_id, 9, "stop", {
            "graceful": True, "reason": "game_shutdown", "dropped_frames": 0,
            "dropped_control_messages": 0,
        })))

        run_dir = self.root / "recordings" / f"run-{self.run_id}"
        metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
        self.assertFalse(metadata["capture_complete"])
        self.assertEqual(metadata["schema_version"], "aicadets.flight.v1")
        self.assertTrue(any(item["reason"] == "transport_frame_loss"
                            for item in metadata["incomplete_reasons"]))
        report_dir = self.root / "analysis"
        result = analyze(run_dir, report_dir)
        self.assertEqual(result["integrity_status"], "verified")
        records = [json.loads(line) for chunk in run_dir.glob("*.jsonl")
                   for line in chunk.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sum(row.get("type") == "frame" for row in records), 2)
        self.assertTrue(any(row.get("event") == "transport_frame_gap" for row in records))
        command = next(row for row in records if row.get("event") == "controller_command")
        self.assertNotIn("decision_id", command)
        self.assertTrue(any(row.get("type") == "gap" and row.get("reason") == "source_step_gap"
                            for row in records))

    def test_unmarked_message_sequence_loss_marks_run_incomplete(self):
        self.receiver.accept_line(hello(self.run_id))
        self.receiver.accept_line(envelope(self.run_id, 2, "frame", frame(0, 0.02, 0.0)))
        self.receiver.accept_line(envelope(self.run_id, 4, "event", {
            "event": "observed_event", "t": 0.04, "evidence": "observed", "fields": {},
        }))
        self.receiver.accept_line(envelope(self.run_id, 5, "stop", {
            "graceful": True, "reason": "game_shutdown", "dropped_frames": 0,
            "dropped_control_messages": 0,
        }))
        metadata = json.loads((self.root / "recordings" / f"run-{self.run_id}" / "metadata.json").read_text())
        self.assertFalse(metadata["capture_complete"])
        self.assertTrue(any(item["reason"] == "transport_message_sequence_gap"
                            for item in metadata["incomplete_reasons"]))

    def test_worker_failure_is_preserved_without_receiver_cleanup_cascade(self):
        self.receiver.accept_line(hello(self.run_id))
        writer = self.receiver.writer

        def fail_checkpoint():
            raise PermissionError(5, "Access is denied", "writer_state.json")

        writer._checkpoint_durable = fail_checkpoint
        writer.checkpoint_interval = 0.0
        self.receiver.accept_line(envelope(self.run_id, 2, "frame", frame(0, 0.0, 0.0)))

        deadline = time.monotonic() + 3.0
        while not writer.worker_failed and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertTrue(writer.worker_failed, "writer worker did not enter the injected fatal path")

        stats = self.receiver.close_uncleanly("receiver_fatal_error")
        self.assertTrue(self.receiver.stopped)
        self.assertIn("PermissionError", stats["fatal_error"])
        run_dir = self.root / "recordings" / f"run-{self.run_id}"
        metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
        self.assertFalse(metadata["capture_complete"])
        self.assertEqual(metadata["stop_reason"], "writer_error")
        self.assertIn("PermissionError", metadata["writer_error"])

    def test_new_producer_run_finalizes_disconnected_run_before_accepting_hello(self):
        first_run_id = uuid.uuid4().hex
        second_run_id = uuid.uuid4().hex
        self.assertTrue(self.receiver.accept_line(hello(first_run_id), new_pipe_connection=True))
        self.assertTrue(self.receiver.accept_line(envelope(
            first_run_id, 2, "frame", frame(1, 0.02, 0.0))))

        self.assertTrue(self.receiver.accept_line(hello(second_run_id), new_pipe_connection=True))
        first_dir = self.root / "recordings" / f"run-{first_run_id}"
        first_metadata = json.loads((first_dir / "metadata.json").read_text(encoding="utf-8"))
        self.assertFalse(first_metadata["capture_complete"])
        self.assertTrue(any(item["reason"] == "producer_disconnected_before_stop"
                            for item in first_metadata["incomplete_reasons"]))
        self.assertEqual(analyze(first_dir, self.root / "first-run-analysis")["integrity_status"],
                         "verified")

        self.assertTrue(self.receiver.accept_line(envelope(
            second_run_id, 2, "frame", frame(1, 0.02, 1.0))))
        self.assertFalse(self.receiver.accept_line(envelope(second_run_id, 3, "stop", {
            "graceful": True, "reason": "game_shutdown", "dropped_frames": 0,
            "dropped_control_messages": 0,
        })))
        second_dir = self.root / "recordings" / f"run-{second_run_id}"
        second_metadata = json.loads((second_dir / "metadata.json").read_text(encoding="utf-8"))
        self.assertTrue(second_metadata["capture_complete"])
        self.assertEqual(analyze(second_dir, self.root / "second-run-analysis")["integrity_status"],
                         "verified")

    def test_disconnected_run_finalizes_incomplete_after_reconnect_grace(self):
        self.receiver.accept_line(hello(self.run_id), new_pipe_connection=True)
        self.receiver.accept_line(envelope(self.run_id, 2, "frame", frame(1, 0.02, 0.0)))
        self.receiver.note_client_disconnected(now=100.0)

        self.assertFalse(self.receiver.finalize_disconnected_if_expired(
            now=100.0 + DISCONNECT_RECONNECT_GRACE_SECONDS - 0.01))
        self.assertFalse(self.receiver.stopped)
        self.assertTrue(self.receiver.finalize_disconnected_if_expired(
            now=100.0 + DISCONNECT_RECONNECT_GRACE_SECONDS))
        self.assertTrue(self.receiver.stopped)

        run_dir = self.root / "recordings" / f"run-{self.run_id}"
        metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
        state = json.loads((run_dir / "writer_state.json").read_text(encoding="utf-8"))
        self.assertFalse(metadata["capture_complete"])
        self.assertTrue(any(item["reason"] == "producer_disconnected_before_stop"
                            for item in metadata["incomplete_reasons"]))
        self.assertTrue(state["is_final"])
        self.assertEqual(analyze(run_dir, self.root / "disconnected-run-analysis")["integrity_status"],
                         "verified")

    def test_same_run_reconnect_cancels_disconnect_finalization(self):
        self.receiver.accept_line(hello(self.run_id), new_pipe_connection=True)
        self.receiver.accept_line(envelope(self.run_id, 2, "frame", frame(1, 0.02, 0.0)))
        self.receiver.note_client_disconnected(now=100.0)

        self.assertTrue(self.receiver.accept_line(hello(self.run_id), new_pipe_connection=True))
        self.assertFalse(self.receiver.finalize_disconnected_if_expired(
            now=100.0 + DISCONNECT_RECONNECT_GRACE_SECONDS + 1.0))
        self.assertTrue(self.receiver.accept_line(envelope(
            self.run_id, 3, "frame", frame(2, 0.04, 1.0))))
        self.assertFalse(self.receiver.accept_line(envelope(self.run_id, 4, "stop", {
            "graceful": True, "reason": "game_shutdown", "dropped_frames": 0,
            "dropped_control_messages": 0,
        })))
        run_dir = self.root / "recordings" / f"run-{self.run_id}"
        metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
        self.assertTrue(metadata["capture_complete"])

    def test_partial_il2cpp_capture_payload_keeps_provenance_and_optional_fields(self):
        hello_payload = {
            "producer": "AoTTG2 Flight Recorder",
            "producer_version": "0.1.5",
            "writer_schema": "aicadets.flight.v1",
            "capture_tier": "partial_il2cpp_periodic_discovery_v1",
            "runtime_observation_phase": "fixed_update_pre_physics_order_unspecified",
            "physics_simulation_mode": "FixedUpdate",
            "timestamp_clock": "UnityEngine.Time.fixedTimeAsDouble",
            "step_source": "adapter FixedUpdate callback ordinal",
            "discovery_interval_seconds": 0.5,
            "declared_coverage": {
                "entity_classes": ["human_local_or_ai", "titan_local_or_ai", "odm_hook", "projectile"],
                "entity_lifecycle": {
                    "first_seen": "inferred_first_seen_by_periodic_census",
                    "destroyed": "observed_unity_object_destroyed",
                    "transient_between_censuses": "may_be_missed",
                },
            },
        }
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 1, "hello", hello_payload)))
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 2, "lifecycle", {
            "action": "spawn", "id": "human:instance-21:1", "kind": "human",
            "t": 0.02, "step": 1, "evidence": "inferred_first_seen_by_periodic_census",
        })))
        frame_payload = {
            "step": 1,
            "t": 0.02,
            "phase": "fixed_update_pre_physics_order_unspecified",
            "fixed_delta_time": 0.02,
            "samples": [
                {
                    "id": "human:instance-21:1", "kind": "human", "pos": [1, 2, 3],
                    "rot": [0, 0, 0, 1], "vel": [0.1, 0.2, 0.3], "ang_vel": [0, 0, 0],
                    "state": "Running", "extra": {
                        "ai_controlled": True, "current_gas_game_property": 87.5,
                        "velocity_source": "UnityEngine.Rigidbody.velocity",
                        "motion_mode": "root_rigidbody_dynamic",
                    },
                },
                {
                    "id": "odm_hook:instance-29:1", "kind": "odm_hook", "pos": [4, 5, 6],
                    "rot": [0, 0, 0, 1], "state": "Hooked", "extra": {
                        "owner_id": "human:instance-21:1",
                        "hook_point_game_method": [4, 5, 6],
                        "anchor_transform_position": [7, 8, 9],
                    },
                },
                {
                    "id": "titan:instance-34:1", "kind": "titan", "pos": [9, 8, 7],
                    "extra": {"motion_mode": "root_transform_no_rigidbody",
                              "velocity_unavailable_reason": "no root Rigidbody component found"},
                },
                {
                    "id": "projectile:instance-42:1", "kind": "projectile", "pos": [3, 2, 1],
                    "extra": {"projectile_velocity_game_property": [5, 0, 0],
                              "projectile_velocity_provenance": "game field; not Rigidbody velocity"},
                },
            ],
        }
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 3, "frame", frame_payload)))
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 4, "event", {
            "event": "collision", "t": 0.021, "step": 1,
            "actor": "human:instance-21:1", "evidence": "observed",
            "fields": {"callback_type": "UnityEngine.Collision",
                       "callback_source": "Characters.Human.OnCollisionEnter(UnityEngine.Collision); Harmony postfix",
                       "actor_source_instance_id": 21,
                       "contact_count": 1,
                       "relative_velocity": [0, -2, 0], "impulse": [0, 1, 0]},
        })))
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 5, "health", {
            "t": 0.03, "step": 1, "evidence": "observed",
            "health_source": "local PipePublisher counters", "queue_depth": 1,
            "queue_bytes": 256, "dropped_frames": 0,
            "capture_work_ms_last": 0.1, "capture_work_ms_p95": 0.25,
            "capture_work_ms_maximum": 1.2, "capture_work_sample_count": 256,
        })))
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 6, "event", {
            "event": "hook_state_sampled_change", "t": 0.04, "step": 2,
            "actor": "odm_hook:instance-29:1",
            "evidence": "sampled_Hook.State_difference_between_adjacent_FixedUpdate_callbacks",
            "fields": {"previous_state": "Launched", "current_state": "Hooked",
                       "observation_mode": "sampled_game_field_transition; not a direct hook callback"},
        })))
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 7, "event", {
            "event": "active_scene_sampled_change", "t": 0.041, "step": 2,
            "evidence": "sampled_active_scene_change_between_fixed_update_callbacks",
            "fields": {"previous_scene_name": "Menu", "active_scene_name": "City",
                       "observation_mode": "active_scene_poll_at_adapter_fixed_update"},
        })))
        self.assertFalse(self.receiver.accept_line(envelope(self.run_id, 8, "stop", {
            "graceful": True, "reason": "test_complete", "dropped_frames": 0,
            "dropped_control_messages": 0,
        })))

        run_dir = self.root / "recordings" / f"run-{self.run_id}"
        report = analyze(run_dir, self.root / "adapter-report")
        self.assertEqual(report["integrity_status"], "verified")
        metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["schema_version"], "aicadets.flight.v1")
        self.assertEqual(metadata["capture_tier"], "partial_il2cpp_periodic_discovery_v1")
        self.assertEqual(metadata["timestamp_clock"], "UnityEngine.Time.fixedTimeAsDouble")
        self.assertEqual(metadata["step_source"], "adapter FixedUpdate callback ordinal")
        self.assertEqual(metadata["discovery_interval_seconds"], 0.5)
        self.assertEqual(metadata["physics_simulation_mode"], "FixedUpdate")
        self.assertEqual(metadata["declared_coverage"]["entity_lifecycle"]["first_seen"],
                         "inferred_first_seen_by_periodic_census")
        records = [json.loads(line) for chunk in run_dir.glob("*.jsonl")
                   for line in chunk.read_text(encoding="utf-8").splitlines()]
        hook = next(row for row in records if row.get("type") == "frame")["samples"][1]
        transform_only = next(row for row in records if row.get("type") == "frame")["samples"][2]
        self.assertEqual(hook["state"], "Hooked")
        self.assertNotIn("vel", hook)
        self.assertNotIn("vel", transform_only)
        collision = next(row for row in records if row.get("event") == "collision")
        self.assertEqual(collision["evidence"], "observed")
        self.assertIn("Human.OnCollisionEnter", collision["callback_source"])
        self.assertEqual(collision["actor_source_instance_id"], 21)
        hook_change = next(row for row in records if row.get("event") == "hook_state_sampled_change")
        self.assertIn("sampled_", hook_change["evidence"])
        self.assertNotEqual(hook_change["evidence"], "observed")
        scene_change = next(row for row in records if row.get("event") == "active_scene_sampled_change")
        self.assertIn("sampled_", scene_change["evidence"])
        health = next(row for row in records if row.get("event") == "producer_health")
        self.assertEqual(health["health_source"], "local PipePublisher counters")
        self.assertEqual(health["capture_work_ms_p95"], 0.25)
        self.assertEqual(health["capture_work_ms_maximum"], 1.2)
        self.assertEqual(health["capture_work_sample_count"], 256)
        self.assertFalse(any("decision" in row.get("event", "") for row in records))


if __name__ == "__main__":
    unittest.main()
