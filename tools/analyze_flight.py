#!/usr/bin/env python3
"""AoTTG AI Cadets Flight Recorder v1 *reference-format* analyzer.

This reads synthetic or future recorder output; it does not implement an in-game
Unity recorder and is NOT evidence that engine-level capture works in AoTTG2.
Python 3.10+, stdlib only. Accepts run folder, .zip bundle, or JSONL file.

Usage:
    python tools/analyze_flight.py example_run --out report
    python tools/analyze_flight.py run.zip --out report --focus-time 17.5
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import contextlib
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from pathlib import PurePosixPath
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flight_attribution import KillAttributionCollector

SCHEMA = "aicadets.flight.v1"
CHUNK_INDEX_SCHEMA = "aicadets.flight.chunk-index.v1"
CHUNK_INDEX_NAME = "chunk_manifest.json"
MAX_ANOMALIES = 2000
CAPTURE_PERFORMANCE_STARTUP_SECONDS = 15.0
CAPTURE_P95_LIMIT_MS = 1.0
CAPTURE_SAMPLE_MAX_LIMIT_MS = 60.0


def vec(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(not isinstance(a, (int, float)) or not math.isfinite(a) for a in value)):
        raise ValueError("expected finite numeric Vector3")
    return tuple(float(x) for x in value)


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def nonnegative_count(value):
    number = finite_number(value)
    return max(0, int(number)) if number is not None else 0


def producer_health_summary(records, metadata, fixed_delta_times, entity_count,
                            producer_queue_capacity=None, producer_queue_max_bytes=None):
    valid = []
    for record in records:
        game_time = finite_number(record.get("t"))
        wall_time = finite_number(record.get("wall_monotonic_elapsed_seconds"))
        p95 = finite_number(record.get("capture_work_ms_p95"))
        maximum = finite_number(record.get("capture_work_ms_maximum"))
        if game_time is None or wall_time is None or p95 is None or maximum is None:
            continue
        valid.append({**record, "t": game_time,
                      "wall_monotonic_elapsed_seconds": wall_time,
                      "capture_work_ms_p95": p95,
                      "capture_work_ms_maximum": maximum})

    post_start = [record for record in valid
                  if record["wall_monotonic_elapsed_seconds"] > CAPTURE_PERFORMANCE_STARTUP_SECONDS]
    worst_p95 = max(post_start, key=lambda record: record["capture_work_ms_p95"], default=None)
    worst_sample = max(valid, key=lambda record: record["capture_work_ms_maximum"], default=None)
    max_sample_post_start = max(post_start, key=lambda record: record["capture_work_ms_maximum"], default=None)
    writer_stats = metadata.get("writer_stats", {})
    writer_limits = metadata.get("writer_limits", {})
    if not isinstance(writer_stats, dict):
        writer_stats = {}
    if not isinstance(writer_limits, dict):
        writer_limits = {}

    p95_failures = [record for record in post_start
                    if record["capture_work_ms_p95"] > CAPTURE_P95_LIMIT_MS]
    dropped_frames = max((nonnegative_count(record.get("dropped_frames")) for record in valid), default=0)
    dropped_controls = max((nonnegative_count(record.get("dropped_control_messages")) for record in valid), default=0)
    dropped_frames = max(dropped_frames,
                         nonnegative_count(writer_stats.get("queue_dropped_frames"))
                         + nonnegative_count(writer_stats.get("storage_dropped_frames")))
    dropped_samples = (nonnegative_count(writer_stats.get("queue_dropped_entity_samples"))
                       + nonnegative_count(writer_stats.get("storage_dropped_entity_samples")))
    queue_depth = max((nonnegative_count(record.get("queue_depth")) for record in post_start), default=0)
    queue_bytes = max((nonnegative_count(record.get("queue_bytes")) for record in post_start), default=0)
    producer_queue_depth_max_sampled = max(
        (nonnegative_count(record.get("queue_depth")) for record in valid), default=0)
    producer_queue_high_water_bytes = max(
        (nonnegative_count(record.get("queue_high_water_bytes")) for record in valid), default=0)
    writer_queue_high_water_depth = nonnegative_count(writer_stats.get("max_queue_depth"))
    writer_queue_high_water_bytes = nonnegative_count(writer_stats.get("max_queue_bytes"))
    queue_capacity = finite_number(writer_limits.get("queue_capacity"))
    max_queue_bytes = finite_number(writer_limits.get("max_queue_bytes"))
    writer_queue_bounded = ((queue_capacity is None or writer_queue_high_water_depth <= queue_capacity)
                            and (max_queue_bytes is None or writer_queue_high_water_bytes <= max_queue_bytes)
                            and not writer_stats.get("storage_exhausted", False)
                            and writer_stats.get("fatal_error") in (None, ""))
    producer_queue_capacity = finite_number(producer_queue_capacity)
    producer_queue_max_bytes = finite_number(producer_queue_max_bytes)
    producer_queue_limits_recorded = (producer_queue_capacity is not None
                                      and producer_queue_max_bytes is not None)
    producer_queue_within_limits = None
    if producer_queue_limits_recorded:
        producer_queue_within_limits = (
            producer_queue_depth_max_sampled <= producer_queue_capacity
            and producer_queue_high_water_bytes <= producer_queue_max_bytes)
    queue_bounded = (writer_queue_bounded and producer_queue_within_limits
                     if producer_queue_within_limits is not None else None)

    reasons = []
    if not valid:
        reasons.append("no valid producer-health records")
    if not post_start:
        reasons.append("no producer-health windows after the first 15 seconds of monotonic capture time")
    if p95_failures:
        reasons.append(f"{len(p95_failures)} post-start producer-health windows exceed {CAPTURE_P95_LIMIT_MS:.1f} ms p95")
    if worst_sample and worst_sample["capture_work_ms_maximum"] > CAPTURE_SAMPLE_MAX_LIMIT_MS:
        reasons.append(f"maximum reported capture-work sample exceeds {CAPTURE_SAMPLE_MAX_LIMIT_MS:.1f} ms")
    if dropped_frames or dropped_controls or dropped_samples:
        reasons.append("producer or writer reported dropped frames, samples, or control messages")
    if not writer_queue_bounded:
        reasons.append("writer queue or storage/fatal-error bounds failed")
    if producer_queue_within_limits is False:
        reasons.append("observed producer queue exceeded the configured capacity or byte limit")
    elif producer_queue_within_limits is None:
        reasons.append("producer queue limits were not provided; producer queue boundedness is unverified")
    if not metadata.get("capture_complete", False):
        reasons.append("capture is incomplete")
    if entity_count < 2:
        reasons.append("fewer than one Human and one Titan were tracked; M2 workload performance is unverified")

    thresholds_available = bool(valid and post_start)
    gate_status = "unavailable"
    if thresholds_available:
        threshold_or_transport_failure = (bool(p95_failures)
                                          or bool(worst_sample and worst_sample["capture_work_ms_maximum"] > CAPTURE_SAMPLE_MAX_LIMIT_MS)
                                          or bool(dropped_frames or dropped_controls or dropped_samples)
                                          or not writer_queue_bounded
                                          or producer_queue_within_limits is False
                                          or not metadata.get("capture_complete", False))
        if threshold_or_transport_failure:
            gate_status = "fail"
        elif producer_queue_within_limits is None or entity_count < 2:
            gate_status = "inconclusive"
        else:
            gate_status = "pass"

    return {
        "producer_health_records": len(records),
        "valid_producer_health_records": len(valid),
        "post_15s_windows": len(post_start),
        "post_15s_windows_over_p95_limit": len(p95_failures),
        "p95_limit_ms": CAPTURE_P95_LIMIT_MS,
        "individual_sample_limit_ms": CAPTURE_SAMPLE_MAX_LIMIT_MS,
        "worst_post_15s_p95_ms": worst_p95["capture_work_ms_p95"] if worst_p95 else None,
        "worst_post_15s_p95_window": ({"step": worst_p95.get("step"), "t": worst_p95.get("t"),
                                        "wall_monotonic_elapsed_seconds": worst_p95.get("wall_monotonic_elapsed_seconds"),
                                        "capture_work_ms_p95": worst_p95.get("capture_work_ms_p95"),
                                        "capture_work_ms_maximum": worst_p95.get("capture_work_ms_maximum")}
                                       if worst_p95 else None),
        "maximum_reported_sample_ms": worst_sample["capture_work_ms_maximum"] if worst_sample else None,
        "maximum_reported_sample_window": ({"step": worst_sample.get("step"), "t": worst_sample.get("t"),
                                             "wall_monotonic_elapsed_seconds": worst_sample.get("wall_monotonic_elapsed_seconds"),
                                             "capture_work_ms_p95": worst_sample.get("capture_work_ms_p95"),
                                             "capture_work_ms_maximum": worst_sample.get("capture_work_ms_maximum")}
                                            if worst_sample else None),
        "maximum_reported_sample_after_15s_ms": (max_sample_post_start["capture_work_ms_maximum"]
                                                   if max_sample_post_start else None),
        "post_15s_max_queue_depth": queue_depth,
        "post_15s_max_queue_bytes": queue_bytes,
        "producer_queue_max_sampled_depth": producer_queue_depth_max_sampled,
        "producer_queue_high_water_bytes": producer_queue_high_water_bytes,
        "producer_queue_capacity": producer_queue_capacity,
        "producer_queue_max_bytes": producer_queue_max_bytes,
        "producer_queue_limits_recorded": producer_queue_limits_recorded,
        "producer_queue_within_limits": producer_queue_within_limits,
        "writer_queue_high_water_depth": writer_queue_high_water_depth,
        "writer_queue_high_water_bytes": writer_queue_high_water_bytes,
        "writer_queue_capacity": queue_capacity,
        "writer_max_queue_bytes": max_queue_bytes,
        "reported_dropped_frames": dropped_frames,
        "reported_dropped_entity_samples": dropped_samples,
        "reported_dropped_control_messages": dropped_controls,
        "writer_fatal_error": writer_stats.get("fatal_error"),
        "writer_storage_exhausted": bool(writer_stats.get("storage_exhausted", False)),
        "capture_complete": bool(metadata.get("capture_complete", False)),
        "tracked_entities": entity_count,
        "writer_queue_bounded": writer_queue_bounded,
        "queue_bounded": queue_bounded,
        "gate_status": gate_status,
        "gate_reasons": reasons,
        "fixed_delta_time_seconds": (sorted(set(fixed_delta_times)) if fixed_delta_times else []),
    }


def timing_summary(health_records, frame_count, counters, fixed_delta_times, calibration_candidates,
                   same_step_collision_events, m2_event_count, sample_phase_verified):
    valid = []
    for record in health_records:
        game_time = finite_number(record.get("t"))
        wall_time = finite_number(record.get("wall_monotonic_elapsed_seconds"))
        if game_time is not None and wall_time is not None:
            valid.append((game_time, wall_time))
    valid.sort(key=lambda pair: pair[1])
    wall_monotonic = all(right[1] > left[1] for left, right in zip(valid, valid[1:]))
    correlation = None
    slope = None
    if len(valid) >= 2:
        game = [pair[0] for pair in valid]
        wall = [pair[1] for pair in valid]
        mean_game = sum(game) / len(game)
        mean_wall = sum(wall) / len(wall)
        covariance = sum((g - mean_game) * (w - mean_wall) for g, w in valid)
        game_variance = sum((g - mean_game) ** 2 for g in game)
        wall_variance = sum((w - mean_wall) ** 2 for w in wall)
        if game_variance > 0:
            slope = covariance / game_variance
        if game_variance > 0 and wall_variance > 0:
            correlation = covariance / math.sqrt(game_variance * wall_variance)
    return {
        "frame_markers": frame_count,
        "frame_step_gap_occurrences": counters.get("anomaly_missing_frame_steps", 0),
        "nonmonotonic_frame_time_occurrences": counters.get("anomaly_nonmonotonic_frame_time", 0),
        "fixed_step_time_mismatch_occurrences": counters.get("anomaly_fixed_step_time_mismatch", 0),
        "fixed_delta_time_seconds": sorted(set(fixed_delta_times)),
        "producer_health_wall_clock_points": len(valid),
        "producer_health_wall_clock_monotonic": wall_monotonic if len(valid) >= 2 else None,
        "producer_health_game_time_wall_time_correlation": correlation,
        "game_seconds_per_wall_second_slope": slope,
        "first_health_game_time": valid[0][0] if valid else None,
        "last_health_game_time": valid[-1][0] if valid else None,
        "first_health_wall_elapsed_seconds": valid[0][1] if valid else None,
        "last_health_wall_elapsed_seconds": valid[-1][1] if valid else None,
        "phase_calibration_candidate_events": calibration_candidates,
        "same_step_sample_precedes_collision_events": same_step_collision_events,
        "m2_controller_or_watcher_event_records": m2_event_count,
        "runtime_observation_phase_calibrated": bool(sample_phase_verified),
    }


def magnitude(v):
    return math.sqrt(sum(x * x for x in v))


class Reader:
    def __init__(self, source):
        self.source = Path(source)
        self.archive = None
        self.archive_root = PurePosixPath(".")
        self.archive_manifest_name = None
        if self.source.is_file() and self.source.suffix.lower() == ".zip":
            self.archive = zipfile.ZipFile(self.source)
            manifest_names = [n for n in self.archive.namelist()
                              if PurePosixPath(n).name == CHUNK_INDEX_NAME]
            if len(manifest_names) == 1:
                self.archive_manifest_name = manifest_names[0]
                self.archive_root = PurePosixPath(manifest_names[0]).parent
        elif not self.source.exists():
            raise FileNotFoundError(self.source)

    def close(self):
        if self.archive:
            self.archive.close()

    def _archive_name(self, name):
        return (self.archive_root / PurePosixPath(name)).as_posix()

    def files(self):
        if self.archive:
            # Resolve chunk names relative to the manifest, allowing a run ZIP to
            # contain one enclosing directory without changing manifest paths.
            files = []
            for archive_name in self.archive.namelist():
                path = PurePosixPath(archive_name)
                if self.archive_manifest_name:
                    try:
                        name = path.relative_to(self.archive_root).as_posix()
                    except ValueError:
                        continue
                else:
                    name = archive_name
                if name.endswith((".jsonl", ".jsonl.gz")):
                    files.append(name)
            # The writer must name chunks monotonically (e.g. 000001.jsonl).
            return sorted(files)
        if self.source.is_dir():
            return sorted(p.relative_to(self.source).as_posix() for p in self.source.rglob("*")
                          if p.is_file() and str(p).endswith((".jsonl", ".jsonl.gz")))
        return [self.source.name]

    def metadata(self):
        if self.archive:
            names = [n for n in self.archive.namelist() if n.endswith("metadata.json")]
            if not names:
                return {}
            preferred = (self.archive_root / "metadata.json").as_posix()
            name = preferred if preferred in names else sorted(names, key=lambda n: (n.count("/"), n))[0]
            return json.loads(self.archive.read(name))
        path = self.source / "metadata.json" if self.source.is_dir() else self.source.parent / "metadata.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def read_bytes(self, name):
        if self.archive:
            return self.archive.read(self._archive_name(name))
        path = self.source / name if self.source.is_dir() else self.source
        return path.read_bytes()

    def chunk_manifest(self):
        if self.archive:
            names = [n for n in self.archive.namelist() if PurePosixPath(n).name == CHUNK_INDEX_NAME]
            if not names:
                return None
            if len(names) != 1:
                raise ValueError("Run ZIP must contain at most one chunk_manifest.json")
            return json.loads(self.archive.read(names[0]))
        if self.source.is_dir():
            paths = sorted(self.source.rglob(CHUNK_INDEX_NAME))
            if not paths:
                return None
            if len(paths) != 1:
                raise ValueError("Run directory must contain at most one chunk_manifest.json")
            return json.loads(paths[0].read_text(encoding="utf-8"))
        return None

    @contextlib.contextmanager
    def open(self, name):
        if self.archive:
            with self.archive.open(self._archive_name(name)) as raw:
                if name.endswith(".gz"):
                    with gzip.GzipFile(fileobj=raw) as zf:
                        with io.TextIOWrapper(zf, encoding="utf-8-sig", errors="replace") as f:
                            yield f
                else:
                    with io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace") as f:
                        yield f
        elif name.endswith(".gz"):
            path = self.source / name if self.source.is_dir() else self.source
            with gzip.open(path, "rt", encoding="utf-8-sig", errors="replace") as f:
                yield f
        else:
            path = self.source / name if self.source.is_dir() else self.source
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                yield f


def verify_chunks(reader, files):
    """Verify optional stored-byte hashes and sizes; never hide rejected chunks."""
    manifest = reader.chunk_manifest()
    if manifest is None:
        return files, {"status": "not_provided", "failures": [], "unindexed": [],
                       "expected_frames": None, "entries": {}}
    if manifest.get("manifest_schema") != CHUNK_INDEX_SCHEMA:
        raise ValueError(f"Unsupported chunk manifest schema: {manifest.get('manifest_schema')!r}")
    entries = manifest.get("chunks")
    if not isinstance(entries, list):
        raise ValueError("chunk_manifest.json requires a chunks array")
    by_name = {}
    failures = []
    expected_frames = 0
    expected_frames_known = True
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("chunk manifest entries must be objects")
        name = entry.get("file")
        if (not isinstance(name, str) or not name or name.startswith("/")
                or ".." in PurePosixPath(name).parts or "\\" in name):
            raise ValueError("chunk manifest contains an unsafe file path")
        if name in by_name:
            raise ValueError(f"duplicate chunk manifest entry: {name}")
        by_name[name] = entry
        count = entry.get("frame_count")
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            expected_frames += count
        else:
            expected_frames_known = False
            failures.append({"file": name, "reason": "invalid_manifest_frame_count"})
        for field in ("first_step", "last_step"):
            value = entry.get(field)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                failures.append({"file": name, "reason": f"invalid_manifest_{field}"})
    file_set = set(files)
    valid = []
    for name, entry in by_name.items():
        if name not in file_set:
            failures.append({"file": name, "reason": "missing_chunk"})
            continue
        try:
            data = reader.read_bytes(name)
        except (OSError, KeyError, zipfile.BadZipFile, RuntimeError) as exc:
            failures.append({"file": name, "reason": f"unreadable_chunk: {exc}"})
            continue
        expected_size = entry.get("bytes")
        expected_hash = entry.get("sha256")
        problems = []
        if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0:
            problems.append("invalid_manifest_size")
        elif len(data) != expected_size:
            problems.append(f"size_mismatch expected={expected_size} actual={len(data)}")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            problems.append("invalid_manifest_sha256")
        elif hashlib.sha256(data).hexdigest().lower() != expected_hash.lower():
            problems.append("sha256_mismatch")
        if problems:
            failures.append({"file": name, "reason": "; ".join(problems)})
        else:
            valid.append(name)
    unindexed = sorted(file_set - set(by_name))
    status = "verified" if not failures and not unindexed else "partial"
    return valid, {"status": status, "failures": failures, "unindexed": unindexed,
                   "expected_frames": expected_frames if expected_frames_known else None,
                   "entries": by_name}


def expanded(raw):
    """v1 accepts both one frame per line and one entity sample per line."""
    typ = raw.get("type")
    if typ == "frame":
        common = {k: raw[k] for k in ("t", "step", "phase", "fixed_delta_time") if k in raw}
        yield {"type": "frame_marker", **common}
        for item in raw.get("samples", []):
            yield {"type": "sample", **common, **item}
    else:
        yield raw


def analyze(source, out, focus_time=None, focus_window=2.0,
            producer_queue_capacity=None, producer_queue_max_bytes=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    reader = Reader(source)
    try:
        metadata = reader.metadata()
        if metadata and metadata.get("schema_version") != SCHEMA:
            raise ValueError(f"Unsupported schema_version: {metadata.get('schema_version')!r}")
        all_files = reader.files()
        if not all_files:
            raise ValueError("No JSONL chunks found")
        files, integrity = verify_chunks(reader, all_files)
        counters = Counter()
        anomalies = []
        last = {}
        track_stats = defaultdict(lambda: {"samples": 0, "path": 0., "max_speed": 0., "gaps": 0,
                                           "first_t": None, "last_t": None, "kind": "unknown", "first": None, "last": None})
        contacts = defaultdict(lambda: deque(maxlen=512))
        attribution = KillAttributionCollector()
        actions = {}
        latest_step = None
        latest_time = None
        dropped = 0  # legacy/unspecified gap counts retained for compatibility
        dropped_frames = 0
        dropped_entity_samples = 0
        observed_frame_steps = 0
        observed_frame_step_ids = set()
        last_frame_step = None
        last_frame_time = None
        parse_errors = 0
        focus_count = 0
        event_rows = []
        producer_health_records = []
        frame_fixed_delta_times = []
        phase_calibration_candidates = 0
        same_step_collision_events = 0
        m2_event_record_count = 0
        started = set()
        ended = set()
        observed_kinds = set()

        def anomaly(kind, t, entity, detail, confidence="indication"):
            counters["anomaly_" + kind] += 1
            if len(anomalies) < MAX_ANOMALIES:
                anomalies.append({"kind": kind, "t": t, "entity": entity, "detail": detail,
                                  "confidence": confidence})

        for failure in integrity["failures"]:
            anomaly("chunk_integrity_failure", None, "",
                    f"file={failure['file']} reason={failure['reason']}", "confirmed")
        for name in integrity["unindexed"]:
            anomaly("unindexed_chunk", None, "", f"file={name} is not listed in the chunk manifest", "confirmed")

        with open(out / "focus.csv", "w", newline="", encoding="utf-8") as focus_file:
            focus_writer = csv.writer(focus_file)
            focus_writer.writerow(["step", "t", "entity", "kind", "px", "py", "pz", "vx", "vy", "vz", "state", "ai_state"])
            for name in files:
                counters["chunks"] += 1
                chunk_frame_steps = []
                with reader.open(name) as handle:
                    for line_no, line in enumerate(handle, 1):
                        if not line.strip():
                            continue
                        try:
                            raw = json.loads(line)
                            if not isinstance(raw, dict) or "type" not in raw:
                                raise ValueError("missing record type")
                        except (ValueError, TypeError) as exc:
                            parse_errors += 1
                            anomaly("unreadable_record", latest_time, "", f"{name}:{line_no} {exc}", "confirmed")
                            continue
                        if not isinstance(raw.get("type"), str):
                            anomaly("invalid_record_type", latest_time, "", f"{name}:{line_no}", "confirmed")
                            continue
                        try:
                            records = list(expanded(raw))
                        except (TypeError, ValueError) as exc:
                            anomaly("invalid_frame_record", latest_time, "", f"{name}:{line_no} {exc}", "confirmed")
                            continue
                        for rec in records:
                            typ = rec.get("type")
                            counters[typ] += 1
                            t = rec.get("t")
                            step = rec.get("step")
                            if t is not None:
                                if isinstance(t, bool) or not isinstance(t, (int, float)):
                                    anomaly("invalid_time", latest_time, "", f"{name}:{line_no}", "confirmed")
                                    continue
                                t = float(t)
                                if not math.isfinite(t):
                                    anomaly("invalid_time", latest_time, "", f"{name}:{line_no}", "confirmed")
                                    continue
                                latest_time = t
                            if step is not None:
                                if isinstance(step, bool) or not isinstance(step, int):
                                    anomaly("invalid_step", t, "", f"{name}:{line_no}", "confirmed")
                                    continue
                                latest_step = step
                            if typ == "frame_marker":
                                observed_frame_steps += 1
                                if step is not None:
                                    observed_frame_step_ids.add(step)
                                    chunk_frame_steps.append(step)
                                if last_frame_step is not None and step is not None:
                                    if step <= last_frame_step:
                                        anomaly("out_of_order_frame", t, "", f"step={step} prev={last_frame_step}", "confirmed")
                                    elif step > last_frame_step + 1:
                                        anomaly("missing_frame_steps", t, "", f"steps={last_frame_step + 1}..{step - 1}", "confirmed")
                                fixed_dt = rec.get("fixed_delta_time", metadata.get("fixed_delta_time"))
                                if fixed_dt is not None:
                                    try:
                                        fixed_dt = float(fixed_dt)
                                        if not math.isfinite(fixed_dt) or fixed_dt <= 0:
                                            raise ValueError("fixed_delta_time must be finite and positive")
                                        frame_fixed_delta_times.append(fixed_dt)
                                        if (last_frame_step is not None and step == last_frame_step + 1
                                                and last_frame_time is not None and t is not None):
                                            elapsed = t - last_frame_time
                                            tolerance = max(0.001, fixed_dt * 0.05)
                                            if abs(elapsed - fixed_dt) > tolerance:
                                                anomaly("fixed_step_time_mismatch", t, "",
                                                        f"elapsed={elapsed:.6f} fixed_delta_time={fixed_dt:.6f}", "confirmed")
                                    except (TypeError, ValueError) as exc:
                                        anomaly("invalid_fixed_delta_time", t, "", str(exc), "confirmed")
                                if last_frame_time is not None and t is not None and t <= last_frame_time:
                                    anomaly("nonmonotonic_frame_time", t, "", f"previous_frame_time={last_frame_time}", "confirmed")
                                last_frame_step = step
                                last_frame_time = t
                                if rec.get("phase") != "post_physics":
                                    counters["uncalibrated_phase"] += 1
                                    counters["phase_" + str(rec.get("phase", "missing"))] += 1
                                else:
                                    counters["phase_post_physics"] += 1
                                continue
                            if typ == "gap":
                                count = max(0, int(rec.get("count", 0)))
                                unit = rec.get("unit")
                                frame_count = rec.get("dropped_frames")
                                sample_count = rec.get("dropped_entity_samples")
                                if isinstance(frame_count, int) and not isinstance(frame_count, bool):
                                    dropped_frames += max(0, frame_count)
                                elif unit == "frames":
                                    dropped_frames += count
                                if isinstance(sample_count, int) and not isinstance(sample_count, bool):
                                    dropped_entity_samples += max(0, sample_count)
                                elif unit == "entity_samples":
                                    dropped_entity_samples += count
                                elif unit not in ("frames", "entity_samples"):
                                    dropped += count
                                first = rec.get("first_step")
                                last_gap = rec.get("last_step")
                                step_range = f" steps={first}..{last_gap}" if first is not None or last_gap is not None else ""
                                anomaly("recorder_gap", t, "", f"count={count}{step_range} reason={rec.get('reason', 'unspecified')}", "confirmed")
                                continue
                            if typ == "entity":
                                entity = str(rec.get("id", ""))
                                if rec.get("action") == "spawn":
                                    started.add(entity)
                                if rec.get("action") == "despawn":
                                    ended.add(entity)
                                event_rows.append([t, step, typ, entity, rec.get("action"), rec.get("evidence", "observed"), "", "", ""])
                                continue
                            if typ == "event":
                                name_of_event = str(rec.get("event", ""))
                                entity = str(rec.get("id", ""))
                                evidence = str(rec.get("evidence", "unknown"))
                                correlation_id = rec.get("correlation_id")
                                correlation_id = (str(correlation_id) if correlation_id not in (None, "") else None)
                                event_ids = rec.get("ids")
                                event_ids = event_ids if isinstance(event_ids, list) else []
                                event_rows.append([t, step, typ, entity, name_of_event, evidence,
                                                   correlation_id or "", rec.get("actor", ""),
                                                   json.dumps(event_ids, separators=(",", ":"))])
                                counters["event_" + name_of_event] += 1
                                attribution.observe_event(rec)
                                event_fields = rec.get("fields")
                                event_fields = event_fields if isinstance(event_fields, dict) else {}
                                if name_of_event == "producer_health":
                                    producer_health_records.append(rec)
                                if name_of_event == "collision":
                                    candidate = rec.get("phase_calibration_candidate", event_fields.get("phase_calibration_candidate"))
                                    same_step = rec.get("same_step_sample_precedes_collision_callback",
                                                        event_fields.get("same_step_sample_precedes_collision_callback"))
                                    if candidate is True:
                                        phase_calibration_candidates += 1
                                    if same_step is True:
                                        same_step_collision_events += 1
                                event_name_lower = name_of_event.lower()
                                m2_named = any(marker in event_name_lower for marker in
                                               ("aicadetsm2", "m2_", "watcher", "controller", "reposition", "ground_route"))
                                m2_structured = ("cadet" in rec or "cadet" in event_fields
                                                 or ("order_seq" in rec and "target_id" in rec)
                                                 or ("order_seq" in event_fields and "target_id" in event_fields))
                                if m2_named or m2_structured:
                                    m2_event_record_count += 1
                                involved = list(event_ids) + ([entity] if entity else [])
                                actor_id = rec.get("actor")
                                if isinstance(actor_id, str) and actor_id:
                                    involved.append(actor_id)
                                nested_fields = rec.get("fields")
                                nested_fields = nested_fields if isinstance(nested_fields, dict) else {}
                                for key in ("other_character_id", "target_id", "victim_id", "other_entity_id"):
                                    value = rec.get(key, nested_fields.get(key))
                                    if isinstance(value, str) and value:
                                        involved.append(value)
                                if (name_of_event in ("collision", "contact") and evidence == "observed"
                                        and isinstance(step, int) and not isinstance(step, bool)):
                                    for target in dict.fromkeys(value for value in involved if isinstance(value, str)):
                                        contacts[str(target)].append(step)
                                if name_of_event in ("damage", "death") and evidence == "observed":
                                    actor = str(rec.get("actor", ""))
                                    active = actions.get(actor)
                                    if (active and active[0] == "attack" and correlation_id
                                            and active[4] == correlation_id):
                                        actions.pop(actor, None)
                                if name_of_event in ("command", "attack_input", "hook_launch"):
                                    action = str(rec.get("action", name_of_event))
                                    if name_of_event == "attack_input":
                                        action = "attack"
                                    elif name_of_event == "hook_launch":
                                        action = "hook"
                                    if entity and entity in last and evidence == "observed":
                                        actions[entity] = (action, t, last[entity][2], step, correlation_id)
                                if name_of_event in ("hook_attached", "hook_released", "order_applied", "motion_cancelled"):
                                    active = actions.get(entity)
                                    if (name_of_event == "hook_attached" and evidence == "observed"
                                            and active and active[0] == "hook" and correlation_id
                                            and active[4] == correlation_id):
                                        actions.pop(entity, None)
                                    if (name_of_event == "motion_cancelled" and evidence == "observed"
                                            and active and correlation_id and active[4] == correlation_id):
                                        actions.pop(entity, None)
                                continue
                            if typ != "sample":
                                anomaly("unknown_record_type", t, "", f"type={typ} {name}:{line_no}", "confirmed")
                                continue
                            entity = str(rec.get("id", ""))
                            if not entity or step is None or t is None:
                                anomaly("invalid_sample", t, entity, f"missing id/step/time at {name}:{line_no}", "confirmed")
                                continue
                            try:
                                pos = vec(rec.get("pos"))
                                vel = vec(rec.get("vel")) if rec.get("vel") is not None else None
                            except ValueError as exc:
                                anomaly("invalid_sample", t, entity, f"{name}:{line_no}: {exc}", "confirmed")
                                continue
                            attribution.observe_sample(rec)
                            stat = track_stats[entity]
                            stat["samples"] += 1
                            stat["kind"] = str(rec.get("kind", stat["kind"]))
                            observed_kinds.add(stat["kind"])
                            if stat["first_t"] is None:
                                stat["first_t"] = t
                                stat["first"] = pos
                            stat["last_t"], stat["last"] = t, pos
                            if vel is not None:
                                stat["max_speed"] = max(stat["max_speed"], magnitude(vel))
                            previous = last.get(entity)
                            if previous:
                                prev_step, prev_t, prev_pos, prev_vel = previous
                                if step <= prev_step:
                                    anomaly("out_of_order_sample", t, entity, f"step={step} prev={prev_step}", "confirmed")
                                else:
                                    expected_stride = max(1, int(rec.get("stride", 1)))
                                    if step - prev_step > expected_stride:
                                        stat["gaps"] += step - prev_step - expected_stride
                                    stat["path"] += distance(pos, prev_pos)
                                    if vel is not None and prev_vel is not None and step - prev_step <= expected_stride:
                                        impulse = distance(vel, prev_vel)
                                        if impulse >= 8:
                                            # This is a motion discontinuity, not proof of a collision.
                                            plausible = any(abs(step - c) <= 1 for c in contacts[entity])
                                            if not plausible:
                                                anomaly("unexplained_velocity_change", t, entity,
                                                        f"delta_v={impulse:.3f} no confirmed matching contact yet; gas/hook/AI impulses possible")
                            last[entity] = (step, t, pos, vel)
                            if entity in actions:
                                action, action_t, action_pos, action_step, action_correlation = actions[entity]
                                if t - action_t >= (1.0 if action in ("attack", "hook") else 2.0):
                                    if action == "attack":
                                        anomaly("attack_outcome_unconfirmed", t, entity,
                                                "no attributed damage/death linked within observation window")
                                    elif action == "hook":
                                        anomaly("hook_attachment_unconfirmed", t, entity,
                                                "no observed hook_attached linked within observation window")
                                    elif distance(action_pos, pos) < 1.0:
                                        anomaly("command_no_motion", t, entity,
                                                f"action={action} displacement={distance(action_pos, pos):.3f}")
                                    actions.pop(entity, None)
                            if focus_time is not None and abs(t - focus_time) <= focus_window:
                                focus_writer.writerow([step, t, entity, stat["kind"], *pos,
                                                       *(vel if vel else ("", "", "")),
                                                       rec.get("state", ""), rec.get("ai_state", "")])
                                focus_count += 1
                entry = integrity["entries"].get(name)
                if entry:
                    observed_first = chunk_frame_steps[0] if chunk_frame_steps else None
                    observed_last = chunk_frame_steps[-1] if chunk_frame_steps else None
                    expected_count = entry.get("frame_count")
                    problems = []
                    if (isinstance(expected_count, int) and not isinstance(expected_count, bool)
                            and expected_count >= 0):
                        if len(chunk_frame_steps) != expected_count:
                            problems.append(f"frame_count expected={expected_count} actual={len(chunk_frame_steps)}")
                    for field, observed in (("first_step", observed_first), ("last_step", observed_last)):
                        expected = entry.get(field)
                        if (isinstance(expected, int) and not isinstance(expected, bool)
                                and expected != observed):
                            problems.append(f"{field} expected={expected} actual={observed}")
                    if problems:
                        detail = "; ".join(problems)
                        integrity["failures"].append({"file": name, "reason": f"chunk_index_mismatch: {detail}"})
                        integrity["status"] = "partial"
                        anomaly("chunk_index_mismatch", None, "", f"file={name} {detail}", "confirmed")

        for entity, state in sorted(actions.items()):
            action, action_t, action_pos, action_step, action_correlation = state
            anomaly("unresolved_action_at_capture_end", latest_time, entity,
                    f"action={action} at_t={action_t} (capture ended before outcome was established)")
        with (out / "timeline.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t", "step", "type", "entity", "event", "evidence", "correlation_id", "actor", "ids"])
            w.writerows(event_rows)
        with (out / "tracks.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["entity", "kind", "samples", "first_t", "last_t", "path_distance", "net_distance", "max_speed", "missing_entity_steps"])
            for entity, s in sorted(track_stats.items()):
                w.writerow([entity, s["kind"], s["samples"], s["first_t"], s["last_t"],
                            round(s["path"], 5), round(distance(s["first"], s["last"]), 5),
                            round(s["max_speed"], 5), s["gaps"]])
        missing_track_steps = sum(s["gaps"] for s in track_stats.values())
        expected_frames = integrity["expected_frames"]
        frame_coverage = None
        if expected_frames is not None:
            frame_coverage = min(1.0, len(observed_frame_step_ids) / expected_frames) if expected_frames else 1.0
            if len(observed_frame_step_ids) < expected_frames:
                anomaly("frame_coverage_incomplete", latest_time, "",
                        f"observed={len(observed_frame_step_ids)} expected={expected_frames}; rejected or missing chunks may account for the difference",
                        "confirmed")
        if observed_frame_steps == 0:
            anomaly("no_frame_markers", latest_time, "", "cannot certify global physics-step coverage", "confirmed")
        kill_attributions = attribution.deaths
        attribution_counts = Counter(item["attribution_status"] for item in kill_attributions)
        build_name = metadata.get("game_build")
        if not isinstance(build_name, str) or not build_name.strip() or build_name == "unknown":
            fingerprint = metadata.get("installed_build_fingerprint", {})
            if isinstance(fingerprint, dict):
                unity = fingerprint.get("unity_version")
                architecture = fingerprint.get("architecture")
                build_parts = [str(value) for value in (unity, architecture)
                               if isinstance(value, str) and value.strip()]
                build_name = " / ".join(build_parts) if build_parts else "unknown"
            else:
                build_name = "unknown"
        incomplete_reasons = metadata.get("incomplete_reasons", [])
        if not isinstance(incomplete_reasons, list):
            incomplete_reasons = []
        incomplete_reasons = [item for item in incomplete_reasons
                              if isinstance(item, dict) and isinstance(item.get("reason"), str)]
        performance = producer_health_summary(producer_health_records, metadata,
                                              frame_fixed_delta_times, len(track_stats),
                                              producer_queue_capacity, producer_queue_max_bytes)
        timing = timing_summary(producer_health_records, observed_frame_steps, counters,
                                frame_fixed_delta_times, phase_calibration_candidates,
                                same_step_collision_events, m2_event_record_count,
                                metadata.get("sample_phase_verified", False))
        summary = {"schema_version": SCHEMA, "run_id": metadata.get("run_id", "unknown"),
                   "capture_tier": metadata.get("capture_tier", "unverified"),
                   "game_build": build_name,
                   "runtime_observation_phase": metadata.get("runtime_observation_phase", "unknown"),
                   "sample_phase_verified": bool(metadata.get("sample_phase_verified", False)),
                   "step_source": metadata.get("step_source", "unknown"),
                   "timestamp_clock": metadata.get("timestamp_clock", "unknown"),
                   "discovery_interval_seconds": metadata.get("discovery_interval_seconds"),
                   "incomplete_reasons": incomplete_reasons,
                   "files": len(all_files), "valid_chunks": len(files), "frames": observed_frame_steps,
                   "frame_coverage_ratio": frame_coverage,
                   "expected_frames_from_manifest": expected_frames,
                   "integrity_status": integrity["status"],
                   "integrity_failures": len(integrity["failures"]),
                   "unindexed_chunks": len(integrity["unindexed"]),
                   "observed_entity_kinds": sorted(observed_kinds),
                   "declared_excluded_classes": metadata.get("coverage", {}).get("excluded_classes", []),
                   "entities": len(track_stats), "events": counters["event"],
                   "reported_dropped_samples": dropped + dropped_entity_samples,
                   "reported_dropped_frames": dropped_frames,
                   "reported_dropped_entity_samples": dropped_entity_samples,
                   "missing_per_entity_sample_steps": missing_track_steps,
                   "parse_errors": parse_errors, "anomaly_total": sum(v for k, v in counters.items() if k.startswith("anomaly_")),
                   "anomalies_returned": len(anomalies), "focus_samples": focus_count,
                   "sampled_titan_death_transitions": len(kill_attributions),
                   "kill_attribution_status_counts": dict(attribution_counts),
                   "producer_performance": performance,
                   "timing_and_calibration": timing,
                   "capture_complete": bool(metadata.get("capture_complete", False)),
                   "evidence_limitations": [
                       "Trajectory and command telemetry are not full deterministic Unity physics replay.",
                       "Velocity-change anomalies are not confirmed contacts; observed collision records are correlated by actor and target where IDs are available.",
                       "Kill attribution from sampled state, contacts, and attack state is heuristic; direct causality requires a correlated damage/death event.",
                       "Entity step gaps can be expected only if a declared lower-rate sampling policy applies.",
                       "A no-frame-marker or uncalibrated capture cannot prove per-physics-step completeness.",
                   ]}
        (out / "coverage.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        (out / "anomalies.json").write_text(json.dumps(anomalies, indent=2) + "\n", encoding="utf-8")
        (out / "kill_attributions.json").write_text(json.dumps(kill_attributions, indent=2) + "\n", encoding="utf-8")
        top = Counter(a["kind"] for a in anomalies)
        rows = ["# AoTTG AI Cadets — flight recorder analysis (reference format)", "",
                f"- Run: `{summary['run_id']}`", f"- Tier: `{summary['capture_tier']}`",
                f"- Game build: `{summary['game_build']}`", f"- Chunk files: {summary['files']}",
                f"- Integrity: `{summary['integrity_status']}` ({summary['valid_chunks']} valid; {summary['integrity_failures']} rejected; {summary['unindexed_chunks']} unindexed)",
                f"- Frame markers: {summary['frames']}", f"- Tracked entities: {summary['entities']}",
                f"- Frame coverage ratio: {summary['frame_coverage_ratio']}",
                f"- Event records: {summary['events']}",
                f"- Declared dropped frames: {dropped_frames}",
                f"- Declared dropped entity samples: {dropped_entity_samples + dropped}",
                f"- Missing per-entity steps (raw): {missing_track_steps}",
                f"- Malformed records: {parse_errors}", f"- Capture complete flag: {summary['capture_complete']}",
                f"- Observation phase: `{summary['runtime_observation_phase']}` (verified: {summary['sample_phase_verified']})",
                f"- Step source: `{summary['step_source']}`",
                "", "## Anomalies (bounded sample)", ""]
        rows += [f"- `{k}`: {v}" for k, v in top.most_common()] or ["- None flagged"]
        rows += ["", "## Sampled Titan deaths and attribution candidates", ""]
        if kill_attributions:
            for death in kill_attributions:
                rows.append(f"- `{death['target_id']}` at t={death['t']:.3f}s, step {death['step']}: "
                            f"{death['attribution_status']} ({', '.join(death['death_signals'])}).")
                for candidate in death["candidates"]:
                    rows.append(f"  - Candidate `{candidate['actor_id']}`: {candidate['evidence_classification']}; "
                                f"AI={candidate['ai_controlled_near_death']}; "
                                f"observed target collisions={candidate['observed_target_collision_count']}; "
                                f"sampled attack={candidate['attack_state_sampled']}; "
                                f"distance at death={candidate['distance_at_death_units']} units.")
                rows.append("  - Contact and sampled attack state support inference; they do not prove damage causality.")
        else:
            rows.append("- No sampled Titan alive-to-dead transition was found.")
        perf = summary["producer_performance"]
        rows += ["", "## Producer performance", "",
                 f"- Gate status: **{perf['gate_status']}**",
                 f"- Producer-health windows: {perf['producer_health_records']} total; {perf['post_15s_windows']} after the first {CAPTURE_PERFORMANCE_STARTUP_SECONDS:.0f} monotonic seconds",
                 f"- Post-start windows above {perf['p95_limit_ms']:.1f} ms p95: {perf['post_15s_windows_over_p95_limit']}",
                 f"- Worst post-start p95: {perf['worst_post_15s_p95_ms']} ms",
                 f"- Maximum reported individual capture-work sample: {perf['maximum_reported_sample_ms']} ms",
                 f"- Producer queue: maximum sampled depth {perf['producer_queue_max_sampled_depth']}; high-water bytes {perf['producer_queue_high_water_bytes']}; configured caps {perf['producer_queue_capacity']} entries / {perf['producer_queue_max_bytes']} bytes",
                 f"- Writer queue: high-water depth {perf['writer_queue_high_water_depth']}, {perf['writer_queue_high_water_bytes']} bytes against {perf['writer_queue_capacity']} entries / {perf['writer_max_queue_bytes']} bytes; post-start sampled depth/bytes maximum {perf['post_15s_max_queue_depth']} / {perf['post_15s_max_queue_bytes']}",
                 f"- Reported drops: frames {perf['reported_dropped_frames']}, entity samples {perf['reported_dropped_entity_samples']}, control messages {perf['reported_dropped_control_messages']}",
                 f"- Tracked entities: {perf['tracked_entities']}"]
        rows += [f"- Gate finding: {reason}" for reason in perf["gate_reasons"]] or ["- Gate findings: all recorded thresholds passed."]
        timing = summary["timing_and_calibration"]
        rows += ["", "## Timing and calibration", "",
                 f"- Frame-step gap incidents: {timing['frame_step_gap_occurrences']}; nonmonotonic game-time incidents: {timing['nonmonotonic_frame_time_occurrences']}; fixed-step time mismatches: {timing['fixed_step_time_mismatch_occurrences']}",
                 f"- Fixed delta time observed: {timing['fixed_delta_time_seconds']}",
                 f"- Health wall-clock points: {timing['producer_health_wall_clock_points']}; wall clock monotonic: {timing['producer_health_wall_clock_monotonic']}; Pearson game-time/wall-time correlation: {timing['producer_health_game_time_wall_time_correlation']}; game seconds per wall second slope: {timing['game_seconds_per_wall_second_slope']}",
                 f"- Same-step collision calibration candidates: {timing['phase_calibration_candidate_events']}; samples observed before collision callback in the same step: {timing['same_step_sample_precedes_collision_events']}",
                 f"- M2 controller/watcher event records in this trace: {timing['m2_controller_or_watcher_event_records']}",
                 "- Calibration procedure: correlate a naturally occurring, independently observed collision or ground-contact transition with the actor's same-step and following-step samples and the corresponding callback, then compare fixed-step ordinal, game time, and monotonic wall time. Do not create synthetic physics or alter transforms/velocity.",
                 f"- Calibration result: {'not performed; observation phase remains unverified' if not summary['sample_phase_verified'] else 'sample phase marked verified in metadata'}."]
        if summary["incomplete_reasons"]:
            rows += ["", "## Incomplete capture reasons", ""]
            rows += [f"- `{item['reason']}` (count: {item.get('count', 1)})"
                     for item in summary["incomplete_reasons"]]
        rows += ["", "## Interpretation", "", "This analyzer is an independently tested offline prototype."
                 " A verified chunk establishes trace integrity, not complete or calibrated engine capture.",
                 "Collision estimates and absent damage do not establish causes."
                 " Calibrate observation phase, entity coverage, callbacks, and performance before drawing gameplay conclusions.", ""]
        (out / "report.md").write_text("\n".join(rows), encoding="utf-8")
        return summary
    finally:
        reader.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="Run folder, zip, or a JSONL chunk")
    parser.add_argument("--out", default="flight_report")
    parser.add_argument("--focus-time", type=float, help="Export entity samples around a game time")
    parser.add_argument("--focus-window", type=float, default=2.0)
    parser.add_argument("--producer-queue-capacity", type=int,
                        help="producer queue entry cap from the local configuration used for this run")
    parser.add_argument("--producer-queue-max-bytes", type=int,
                        help="producer queue byte cap from the local configuration used for this run")
    args = parser.parse_args()
    summary = analyze(args.source, args.out, args.focus_time, args.focus_window,
                      args.producer_queue_capacity, args.producer_queue_max_bytes)
    print(json.dumps(summary, indent=2))
    print(f"Report: {Path(args.out) / 'report.md'}")


if __name__ == "__main__":
    main()
