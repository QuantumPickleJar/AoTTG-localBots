"""Protocol and writer-bridge checks; Windows pipe ACL/runtime smoke is separate."""
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from analyze_flight import analyze  # noqa: E402
from flight_transport import (  # noqa: E402
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

    def test_explicit_frame_gap_and_writer_schema_round_trip(self):
        self.assertTrue(self.receiver.accept_line(hello(self.run_id)))
        self.assertTrue(self.receiver.accept_line(envelope(self.run_id, 2, "lifecycle", {
            "action": "spawn", "id": "human:fixture:1", "kind": "human", "t": 0.02,
            "step": 0, "evidence": "observed",
        })))
        first = envelope(self.run_id, 3, "frame", frame(0, 0.02, 0.0))
        self.assertTrue(self.receiver.accept_line(first))
        self.assertTrue(self.receiver.accept_line(first))  # Retry after a broken pipe is idempotent.
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


if __name__ == "__main__":
    unittest.main()
