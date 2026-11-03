"""Deterministic fault and format checks for the Unity-independent writer."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from analyze_flight import analyze  # noqa: E402
from flight_writer import (  # noqa: E402
    EntitySample,
    FlightRecorderWriter,
    FrameSnapshot,
    RecorderEvent,
    RecorderOverloadError,
    StableEntityRegistry,
    recover_run,
)
from replay_decisions import read_pairs  # noqa: E402


def sample(entity_id="human:1:1", *, x=0.0, extra=None):
    return EntitySample(entity_id, "human", [x, 0, 0], [1, 0, 0], state="Run", extra=extra or {})


def frame(step, count=2):
    return FrameSnapshot(step, step / 50.0, "synthetic", tuple(
        sample(f"human:{index}:1", x=step * 0.01 + index) for index in range(count)
    ), fixed_delta_time=0.02)


class FlightWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make_writer(self, name="run", **kwargs):
        options = {
            "max_storage_bytes": 4 * 1024 * 1024,
            "control_reserve_bytes": 64 * 1024,
            "chunk_target_bytes": 8 * 1024,
            "max_chunks": 8,
        }
        options.update(kwargs)
        return FlightRecorderWriter(self.root / name, **options)

    def test_writer_output_verifies_with_reader_and_is_immutable(self):
        values = [1, 2]
        entity = EntitySample("human:1:1", "human", [0, 1, 2], extra={"nested": {"trail": values}})
        values.append(3)
        copied = FrameSnapshot(1, 0.02, "synthetic", [entity], 0.02)
        with self.assertRaises((AttributeError, TypeError)):
            entity.extra.items[0][1].items[0][1].items += (4,)
        writer = self.make_writer()
        self.assertEqual(writer.submit_frame(copied), "accepted")
        writer.submit_event(RecorderEvent(
            "command_intent", 0.02, entity_id="human:1:1", step=1,
            correlation_id="cmd-1", evidence="observed", fields={"command": "MoveTo"},
        ))
        stats = writer.close()
        self.assertTrue(stats["written_frames"] == 1)
        report = analyze(self.root / "run", self.root / "analysis")
        self.assertEqual(report["integrity_status"], "verified")
        self.assertEqual(report["frames"], 1)
        record = json.loads(next((self.root / "run").glob("chunk-*.jsonl")).read_text().splitlines()[0])
        self.assertEqual(record["samples"][0]["nested"]["trail"], [1, 2])

    def test_stable_ids_change_after_despawn_and_reuse_of_source_handle(self):
        registry = StableEntityRegistry()
        first, spawn1 = registry.spawn("human", 17, 0.0, 1)
        despawn = registry.despawn(first, 0.02, 2)
        second, spawn2 = registry.spawn("human", 17, 0.04, 3)
        self.assertNotEqual(first, second)
        self.assertEqual((spawn1.action, despawn.action, spawn2.action), ("spawn", "despawn", "spawn"))
        self.assertEqual(registry.active_ids(), (second,))
        writer = self.make_writer()
        for event in (spawn1, despawn, spawn2):
            writer.submit_lifecycle(event)
        writer.close()
        result = analyze(self.root / "run", self.root / "lifecycle_analysis")
        self.assertEqual(result["integrity_status"], "verified")
        self.assertEqual(result["entities"], 0)

    def test_missing_source_steps_are_explicit_frames_not_fabricated_samples(self):
        writer = self.make_writer()
        writer.submit_frame(frame(1))
        writer.submit_frame(frame(4))
        stats = writer.close()
        self.assertEqual(stats["source_missing_frames"], 2)
        report = analyze(self.root / "run", self.root / "analysis")
        self.assertEqual(report["reported_dropped_frames"], 2)
        self.assertEqual(report["reported_dropped_entity_samples"], 0)
        self.assertEqual(report["entities"], 2)
        records = [json.loads(line) for path in (self.root / "run").glob("chunk-*.jsonl")
                   for line in path.read_text().splitlines()]
        gap = next(record for record in records if record["type"] == "gap")
        self.assertEqual((gap["first_step"], gap["last_step"], gap["count"], gap["unit"]),
                         (2, 3, 2, "frames"))

    def test_queue_saturation_is_counted_and_written_as_a_gap(self):
        writer = self.make_writer(queue_capacity=1, max_queue_bytes=64 * 1024, max_gap_ranges=2)
        entered = threading.Event()
        release = threading.Event()
        original = writer._store_record
        blocked = {"once": False}

        def slow_store(record, **kwargs):
            if record.get("type") == "frame" and not blocked["once"]:
                blocked["once"] = True
                entered.set()
                release.wait(3)
            return original(record, **kwargs)

        writer._store_record = slow_store
        writer.submit_frame(frame(1))
        self.assertTrue(entered.wait(2), "worker did not begin the first write")
        self.assertEqual(writer.submit_frame(frame(2)), "accepted")
        self.assertEqual(writer.submit_frame(frame(3)), "queue_saturated")
        self.assertEqual(writer.submit_frame(frame(4)), "queue_saturated")
        release.set()
        stats = writer.close()
        self.assertEqual(stats["queue_dropped_frames"], 2)
        report = analyze(self.root / "run", self.root / "analysis")
        self.assertEqual(report["reported_dropped_frames"], 2)
        self.assertEqual(report["reported_dropped_entity_samples"], 4)
        self.assertFalse(report["capture_complete"])

    def test_reserved_control_capacity_accepts_event_while_frame_queue_is_full(self):
        writer = self.make_writer(queue_capacity=8, max_queue_bytes=64 * 1024,
                                  control_queue_reserve_slots=1, control_queue_reserve_bytes=4096,
                                  event_timeout=0.0)
        entered = threading.Event()
        release = threading.Event()
        original = writer._store_record
        blocked = {"once": False}

        def slow_store(record, **kwargs):
            if record.get("type") == "frame" and not blocked["once"]:
                blocked["once"] = True
                entered.set()
                release.wait(3)
            return original(record, **kwargs)

        writer._store_record = slow_store
        writer.submit_frame(frame(1, count=1))
        self.assertTrue(entered.wait(2))
        for step in range(2, 9):
            self.assertEqual(writer.submit_frame(frame(step, count=1)), "accepted")
        writer.submit_event(RecorderEvent("decision_result", 0.18, entity_id="human:0:1",
                                          step=9, decision_id="d-9", fields={"choice": "hold"}))
        release.set()
        stats = writer.close()
        self.assertEqual(stats["queue_dropped_frames"], 0)
        self.assertEqual(stats["written_events"], 1)
        records = [json.loads(line) for path in (self.root / "run").glob("chunk-*.jsonl")
                   for line in path.read_text().splitlines()]
        event_index = next(i for i, record in enumerate(records) if record.get("type") == "event")
        self.assertEqual(sum(record.get("type") == "frame" for record in records[:event_index]), 8)

    def test_frame_larger_than_queue_budget_is_explicitly_gapped(self):
        writer = self.make_writer(queue_capacity=2, max_queue_bytes=1024)
        self.assertEqual(writer.submit_frame(frame(1, count=1)), "frame_exceeds_queue_limit")
        stats = writer.close()
        self.assertEqual(stats["oversized_queue_frames"], 1)
        self.assertEqual(stats["queue_dropped_frames"], 1)
        report = analyze(self.root / "run", self.root / "analysis")
        self.assertEqual(report["reported_dropped_frames"], 1)
        self.assertEqual(report["reported_dropped_entity_samples"], 1)

    def test_source_gap_and_queue_saturation_keep_both_reasons(self):
        writer = self.make_writer(queue_capacity=1, max_queue_bytes=64 * 1024, max_gap_ranges=2)
        entered = threading.Event()
        release = threading.Event()
        original = writer._store_record
        blocked = {"once": False}

        def slow_store(record, **kwargs):
            if record.get("type") == "frame" and not blocked["once"]:
                blocked["once"] = True
                entered.set()
                release.wait(3)
            return original(record, **kwargs)

        writer._store_record = slow_store
        writer.submit_frame(frame(1))
        self.assertTrue(entered.wait(2))
        writer.submit_frame(frame(2))
        self.assertEqual(writer.submit_frame(frame(4)), "queue_saturated")
        release.set()
        writer.close()
        records = [json.loads(line) for path in (self.root / "run").glob("chunk-*.jsonl")
                   for line in path.read_text().splitlines()]
        combined = next(record for record in records if record.get("type") == "gap")
        self.assertEqual(combined["reason"], "source_step_gap_and_queue_saturated")
        self.assertEqual((combined["first_step"], combined["last_step"], combined["dropped_frames"]), (3, 4, 2))

    def test_storage_limit_is_bounded_and_final_gap_survives(self):
        writer = self.make_writer("limited", max_storage_bytes=128 * 1024,
                                  control_reserve_bytes=32 * 1024, chunk_target_bytes=16 * 1024,
                                  max_chunks=4, queue_capacity=256, max_queue_bytes=8 * 1024 * 1024)
        for step in range(1, 2000):
            writer.submit_frame(frame(step, count=16))
            if writer.stats()["storage_exhausted"]:
                break
        stats = writer.close()
        actual_size = sum(path.stat().st_size for path in (self.root / "limited").iterdir() if path.is_file())
        self.assertLessEqual(actual_size, 128 * 1024)
        self.assertTrue(stats["storage_dropped_frames"] > 0)
        self.assertTrue(stats["storage_exhausted"])
        report = analyze(self.root / "limited", self.root / "limited_analysis")
        self.assertGreater(report["reported_dropped_frames"], 0)

    def test_bounded_storage_loss_ledger_preserves_totals_without_inventing_step_ranges(self):
        writer = self.make_writer("loss_ledger", max_gap_ranges=1)
        writer._record_storage_loss(1, frame(1, count=2))
        writer._record_storage_loss(3, frame(3, count=3))
        writer.close()
        records = [json.loads(line) for path in (self.root / "loss_ledger").glob("chunk-*.jsonl")
                   for line in path.read_text().splitlines()]
        gap = next(record for record in records if record.get("type") == "gap")
        self.assertEqual(gap["reason"], "storage_limit_ranges_unlocated")
        self.assertEqual((gap["dropped_frames"], gap["dropped_entity_samples"]), (2, 5))
        self.assertNotIn("first_step", gap)
        self.assertNotIn("last_step", gap)
        report = analyze(self.root / "loss_ledger", self.root / "loss_ledger_analysis")
        self.assertEqual(report["reported_dropped_frames"], 2)
        self.assertEqual(report["reported_dropped_entity_samples"], 5)

    def test_incomplete_decision_stays_incomplete_in_replay_reader(self):
        writer = self.make_writer()
        writer.submit_frame(frame(1, count=1))
        writer.submit_event(RecorderEvent(
            "decision_input", 0.02, entity_id="human:0:1", step=1,
            decision_id="d-1", fields={"policy_version": "m2-production"},
        ))
        writer.close()
        _, rows, problems = read_pairs(self.root / "run")
        self.assertEqual(len(rows), 1)
        self.assertIn("invalid_decision_input", {problem["kind"] for problem in problems})
        self.assertIn("missing_decision_result", {problem["kind"] for problem in problems})
        self.assertNotIn("profile", rows[0]["decision_input"])
        self.assertNotIn("candidates", rows[0]["decision_input"])

    def test_recovery_salvages_complete_lines_and_marks_known_tail_gap(self):
        run = self.root / "interrupted"
        run.mkdir()
        (run / "metadata.json").write_text(json.dumps({"schema_version": "aicadets.flight.v1",
                                                         "run_id": "interrupted", "capture_complete": False}))
        (run / "chunk_manifest.json").write_text(json.dumps({"manifest_schema": "aicadets.flight.chunk-index.v1",
                                                               "chunks": []}))
        (run / "writer_state.json").write_text(json.dumps({"last_submitted_step": 3}))
        good = "".join(json.dumps(frame(step, count=1).to_record(), separators=(",", ":")) + "\n"
                        for step in (1, 2)).encode()
        torn = (json.dumps(frame(3, count=1).to_record(), separators=(",", ":"))[:45]).encode()
        (run / "chunk-000001.jsonl.partial").write_bytes(good + torn)
        recovered = recover_run(run, expected_last_step=3)
        self.assertEqual(recovered["recovered_frames"], 2)
        self.assertEqual(recovered["truncated_bytes"], len(torn))
        self.assertEqual(recovered["missing_frame_ranges"], [{"first_step": 3, "last_step": 3, "count": 1}])
        report = analyze(run, self.root / "recovered_analysis")
        self.assertEqual(report["integrity_status"], "verified")
        self.assertEqual(report["frames"], 2)
        self.assertEqual(report["reported_dropped_frames"], 1)
        self.assertFalse(report["capture_complete"])

    def test_checkpoint_step_is_not_mistaken_for_final_crash_step(self):
        run = self.root / "unknown_tail"
        run.mkdir()
        (run / "metadata.json").write_text(json.dumps({"schema_version": "aicadets.flight.v1",
                                                         "run_id": "unknown-tail", "capture_complete": False}))
        (run / "chunk_manifest.json").write_text(json.dumps({"manifest_schema": "aicadets.flight.chunk-index.v1",
                                                               "chunks": []}))
        (run / "writer_state.json").write_text(json.dumps({"last_submitted_step": 10,
                                                             "checkpoint_is_not_final": True}))
        payload = (json.dumps(frame(10, count=1).to_record(), separators=(",", ":")) + "\n").encode()
        (run / "chunk-000001.jsonl.partial").write_bytes(payload)
        report = recover_run(run)
        self.assertTrue(report["unknown_tail_loss"])
        self.assertEqual(report["missing_frame_ranges"], [])

    def test_recovery_reindexes_complete_chunk_renamed_before_manifest(self):
        run = self.root / "rename_crash"
        run.mkdir()
        (run / "metadata.json").write_text(json.dumps({"schema_version": "aicadets.flight.v1",
                                                         "run_id": "rename-crash", "capture_complete": False}))
        (run / "chunk_manifest.json").write_text(json.dumps({"manifest_schema": "aicadets.flight.chunk-index.v1",
                                                               "chunks": []}))
        payload = (json.dumps(frame(1, count=1).to_record(), separators=(",", ":")) + "\n").encode()
        (run / "chunk-000001.jsonl").write_bytes(payload)
        report = recover_run(run, expected_last_step=1)
        self.assertEqual(report["unindexed_complete_chunks"], [])
        result = analyze(run, self.root / "rename_analysis")
        self.assertEqual(result["integrity_status"], "verified")
        self.assertEqual(result["frames"], 1)

    def test_corrupt_chunk_is_rejected_without_hiding_independent_chunks(self):
        writer = self.make_writer("corrupt", chunk_target_bytes=2048, max_chunks=10)
        for step in range(1, 80):
            writer.submit_frame(frame(step, count=2))
        writer.close()
        chunks = sorted((self.root / "corrupt").glob("chunk-*.jsonl"))
        self.assertGreaterEqual(len(chunks), 2)
        payload = chunks[0].read_bytes()
        chunks[0].write_bytes(payload.replace(b"synthetic", b"corrupt!", 1))
        recovery = recover_run(self.root / "corrupt", expected_last_step=79)
        self.assertEqual(len(recovery["corrupt_indexed_chunks"]), 1)
        report = analyze(self.root / "corrupt", self.root / "corrupt_analysis")
        self.assertEqual(report["integrity_status"], "partial")
        self.assertGreater(report["valid_chunks"], 0)
        self.assertEqual(report["integrity_failures"], 1)

    def test_gap_ledger_saturation_raises_instead_of_losing_observation(self):
        writer = self.make_writer(queue_capacity=1, max_queue_bytes=4096, max_gap_ranges=1,
                                  event_timeout=0.0)
        entered = threading.Event()
        release = threading.Event()
        original = writer._store_record
        blocked = {"once": False}

        def slow_store(record, **kwargs):
            if record.get("type") == "frame" and not blocked["once"]:
                blocked["once"] = True
                entered.set()
                release.wait(3)
            return original(record, **kwargs)

        writer._store_record = slow_store
        writer.submit_frame(frame(1, count=1))
        self.assertTrue(entered.wait(2))
        writer.submit_frame(frame(2, count=1))
        self.assertEqual(writer.submit_frame(frame(4, count=1)), "queue_saturated")
        with self.assertRaises(RecorderOverloadError):
            writer.submit_frame(frame(5, count=1), accounting_timeout=0.0)
        release.set()
        stats = writer.close()
        self.assertEqual(stats["queue_dropped_frames"], 1)
        self.assertEqual(stats["source_missing_frames"], 1)
        self.assertEqual(stats["enqueued_frames"], 2)

    def test_external_incomplete_reason_survives_graceful_writer_close(self):
        writer = self.make_writer("incomplete")
        writer.submit_frame(frame(1, count=1))
        writer.mark_incomplete("transport_message_sequence_gap", details={
            "first_missing_sequence": 4, "last_missing_sequence": 5,
        })
        writer.mark_incomplete("transport_message_sequence_gap", details={
            "first_missing_sequence": 9, "last_missing_sequence": 9,
        })
        writer.close()

        metadata = json.loads((self.root / "incomplete" / "metadata.json").read_text())
        self.assertFalse(metadata["capture_complete"])
        self.assertEqual(metadata["incomplete_reasons"], [{
            "reason": "transport_message_sequence_gap", "count": 2,
            "first_details": {"first_missing_sequence": 4, "last_missing_sequence": 5},
            "last_details": {"first_missing_sequence": 9, "last_missing_sequence": 9},
        }])


if __name__ == "__main__":
    unittest.main()
