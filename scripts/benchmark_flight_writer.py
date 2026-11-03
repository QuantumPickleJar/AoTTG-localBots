#!/usr/bin/env python3
"""Paced synthetic throughput and crash-recovery benchmark for flight_writer."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
try:
    import resource
except ImportError:  # Windows has no resource module.
    resource = None
import subprocess
import sys
import tempfile
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from flight_writer import EntitySample, FlightRecorderWriter, FrameSnapshot, recover_run  # noqa: E402
from analyze_flight import analyze  # noqa: E402


def build_frame(step: int, hz: int, entity_count: int) -> FrameSnapshot:
    t = step / hz
    samples = tuple(
        EntitySample(
            entity_id=f"human:{entity}:1", kind="human",
            pos=(entity * 1.5 + t * 0.25, (entity % 4) * 0.1, entity % 7),
            vel=(0.25, 0.0, 0.0), state="Run", ai_state="Synthetic",
        )
        for entity in range(entity_count)
    )
    return FrameSnapshot(step, t, "synthetic_benchmark", samples, 1.0 / hz)


def recovery_probe(path: Path, hz: int, entity_count: int, recovery_frames: int) -> dict:
    path.mkdir(parents=True)
    metadata = {"schema_version": "aicadets.flight.v1", "run_id": "recovery-probe",
                "capture_tier": "synthetic_benchmark", "capture_complete": False}
    (path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (path / "chunk_manifest.json").write_text(json.dumps({
        "manifest_schema": "aicadets.flight.chunk-index.v1", "chunks": []
    }), encoding="utf-8")
    (path / "writer_state.json").write_text(json.dumps({"last_submitted_step": recovery_frames}), encoding="utf-8")
    partial = path / "chunk-000001.jsonl.partial"
    with partial.open("wb") as stream:
        for step in range(1, recovery_frames):
            record = build_frame(step, hz, entity_count).to_record()
            stream.write((json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode())
        torn = json.dumps(build_frame(recovery_frames, hz, entity_count).to_record(),
                          sort_keys=True, separators=(",", ":")).encode()[:96]
        stream.write(torn)
        stream.flush()
        os.fsync(stream.fileno())
    started = time.perf_counter()
    # The synthetic fixture knows its exact final step; pass that observed bound
    # explicitly. A real post-crash run cannot treat a periodic writer checkpoint
    # as the final submitted step.
    report = recover_run(path, expected_last_step=recovery_frames)
    elapsed = time.perf_counter() - started
    recovery_bytes = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    analysis = analyze(path, path / "analysis")
    return {
        "recovery_seconds": elapsed,
        "recovered_frames": report["recovered_frames"],
        "recovered_frames_per_second": report["recovered_frames"] / elapsed if elapsed else None,
        "truncated_tail_bytes": report["truncated_bytes"],
        "missing_frame_ranges": report["missing_frame_ranges"],
        "unknown_tail_loss": report["unknown_tail_loss"],
        "manifest_integrity": analysis["integrity_status"],
        "recovery_artifact_bytes": recovery_bytes,
    }


def child_case(out: Path, hz: int, entity_count: int, duration: float) -> dict:
    total_frames = int(round(hz * duration))
    writer = FlightRecorderWriter(
        out / "recording", run_id=f"bench-{hz}-{entity_count}",
        capture_tier="synthetic_benchmark", queue_capacity=512,
        max_queue_bytes=128 * 1024 * 1024,
        chunk_target_bytes=8 * 1024 * 1024,
        max_storage_bytes=512 * 1024 * 1024,
        control_reserve_bytes=256 * 1024, max_chunks=128,
        metadata={"benchmark": True, "benchmark_hz": hz, "tracked_entities": entity_count},
    )
    submit_latency = []
    tracemalloc.start()
    rss_start = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None
    started = time.perf_counter()
    for step in range(1, total_frames + 1):
        deadline = started + (step - 1) / hz
        remaining = deadline - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)
        sample_frame = build_frame(step, hz, entity_count)
        before = time.perf_counter()
        writer.submit_frame(sample_frame)
        submit_latency.append(time.perf_counter() - before)
    stats = writer.close()
    elapsed = time.perf_counter() - started
    _, peak_allocated = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None
    run_size = sum(p.stat().st_size for p in (out / "recording").rglob("*") if p.is_file())
    recovery_frames = max(25, min(total_frames, hz))
    recovery = recovery_probe(out / "recovery", hz, entity_count, recovery_frames)
    ordered_latency = sorted(submit_latency)
    p95 = ordered_latency[min(len(ordered_latency) - 1, math.ceil(len(ordered_latency) * 0.95) - 1)]
    return {
        "hz_target": hz, "tracked_entities": entity_count, "duration_seconds": duration,
        "submitted_frames": total_frames, "written_frames": stats["written_frames"],
        "written_entity_samples": stats["written_frames"] * entity_count,
        "elapsed_seconds_including_drain": elapsed,
        "producer_updates_per_second": total_frames / elapsed if elapsed else None,
        "writer_records_per_second": stats["written_frames"] / stats["writer_seconds"] if stats["writer_seconds"] else None,
        "entity_samples_per_second": stats["written_frames"] * entity_count / elapsed if elapsed else None,
        "recording_bytes": run_size,
        "bytes_per_frame": run_size / stats["written_frames"] if stats["written_frames"] else None,
        "bytes_per_entity_sample": run_size / (stats["written_frames"] * entity_count) if stats["written_frames"] else None,
        "python_peak_tracemalloc_bytes": peak_allocated,
        "process_peak_rss_kib": rss_peak,
        "process_rss_peak_delta_kib": max(0, rss_peak - rss_start) if rss_peak is not None else None,
        "max_queued_bytes_accounted": stats["max_queue_bytes"],
        "max_queue_depth": stats["max_queue_depth"],
        "submit_latency_p95_ms": p95 * 1000,
        "queue_dropped_frames": stats["queue_dropped_frames"],
        "storage_dropped_frames": stats["storage_dropped_frames"],
        "capture_complete": json.loads((out / "recording" / "metadata.json").read_text())["capture_complete"],
        "recovery": recovery,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="directory for benchmark artifacts and metrics.json")
    parser.add_argument("--duration", type=float, default=3.0,
                        help="paced seconds for each Hz/entity scenario (default: 3)")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--hz", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--entities", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        if args.out is None or args.hz is None or args.entities is None:
            parser.error("internal child invocation requires --out, --hz and --entities")
        print(json.dumps(child_case(args.out, args.hz, args.entities, args.duration), sort_keys=True))
        return
    if args.duration <= 0 or not math.isfinite(args.duration):
        parser.error("--duration must be a finite number greater than zero")
    out = args.out or Path(tempfile.mkdtemp(prefix="aicadets-flight-bench-"))
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for hz in (50, 100):
        for entity_count in (30, 50, 100):
            case_dir = out / f"case-{hz}hz-{entity_count}entities"
            case_dir.mkdir()
            command = [sys.executable, str(Path(__file__).resolve()), "--child", "--out", str(case_dir),
                       "--hz", str(hz), "--entities", str(entity_count), "--duration", str(args.duration)]
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
            result = json.loads(completed.stdout.strip().splitlines()[-1])
            results.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)
    payload = {"benchmark": "aicadets_flight_writer_synthetic_v1", "python": sys.version.split()[0],
               "platform": sys.platform, "duration_per_case_seconds": args.duration,
               "cases": results}
    (out / "metrics.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"metrics: {out / 'metrics.json'}")


if __name__ == "__main__":
    main()
