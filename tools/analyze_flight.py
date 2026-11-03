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
import zipfile

SCHEMA = "aicadets.flight.v1"
CHUNK_INDEX_SCHEMA = "aicadets.flight.chunk-index.v1"
CHUNK_INDEX_NAME = "chunk_manifest.json"
MAX_ANOMALIES = 2000


def vec(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(not isinstance(a, (int, float)) or not math.isfinite(a) for a in value)):
        raise ValueError("expected finite numeric Vector3")
    return tuple(float(x) for x in value)


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


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


def analyze(source, out, focus_time=None, focus_window=2.0):
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
        contacts = defaultdict(lambda: deque(maxlen=64))
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
                                event_rows.append([t, step, typ, entity, name_of_event, evidence,
                                                   correlation_id or "", rec.get("actor", ""),
                                                   json.dumps(rec.get("ids", []), separators=(",", ":"))])
                                counters["event_" + name_of_event] += 1
                                involved = list(rec.get("ids", [])) + ([entity] if entity else [])
                                if name_of_event in ("collision", "contact") and evidence == "observed":
                                    for target in involved:
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
                   "capture_complete": bool(metadata.get("capture_complete", False)),
                   "evidence_limitations": [
                       "Trajectory and command telemetry are not full deterministic Unity physics replay.",
                       "Unexplained velocity changes are not confirmed contacts.",
                       "No automatic attribution of damage/death or rescue without explicit evidence.",
                       "Entity step gaps can be expected only if a declared lower-rate sampling policy applies.",
                       "A no-frame-marker or uncalibrated capture cannot prove per-physics-step completeness.",
                   ]}
        (out / "coverage.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        (out / "anomalies.json").write_text(json.dumps(anomalies, indent=2) + "\n", encoding="utf-8")
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
    args = parser.parse_args()
    summary = analyze(args.source, args.out, args.focus_time, args.focus_window)
    print(json.dumps(summary, indent=2))
    print(f"Report: {Path(args.out) / 'report.md'}")


if __name__ == "__main__":
    main()
