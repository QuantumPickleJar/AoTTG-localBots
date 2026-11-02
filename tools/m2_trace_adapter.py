#!/usr/bin/env python3
"""Preserve M2 LogEvent output as observation-only flight events.

This adapter does not create decision_input records. The M2 Custom Logic trace
does not emit the versioned M3 profile, candidate gate results, stable decision
IDs, or same-step physics frames required by tools/replay_decisions.py.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from typing import Iterable

from analyze_flight import SCHEMA


SOURCE_FORMAT = "aicadets.m2-log-event.v1"
_PREFIX = re.compile(
    r"^build=(?P<build>\S+) driver=(?P<driver>\S+) id=(?P<event_sequence>\d+) "
    r"mode=(?P<mode>\S+) t=(?P<game_time>\S+) run=(?P<run_id>\S+) "
    r"cadet=(?P<cadet_name>[^ ]*) state=(?P<state>\S+) target=(?P<target>\S+) "
    r"event=(?P<event_name>\S+)(?:\s+(?P<raw_details>.*))?$"
)
# Detail keys in LogEvent call sites are lowercase snake_case. Lowercase-only
# starts keep formatted vector components such as ``Vector(X=..., Y=...)`` as
# part of the original value rather than mistaking X/Y/Z for event fields.
_DETAIL_KEY = re.compile(r"(?:^|\s)([a-z][A-Za-z0-9_]*)=")
_REQUIRED_DECISION_FIELDS = [
    "stable_spawn_entity_id",
    "decision_id",
    "policy_version",
    "state_version",
    "profile_hash",
    "complete_m3_profile_v1",
    "candidate_set_and_gate_results",
    "physics_step_and_matching_entity_frame",
]


class M2TraceError(ValueError):
    pass


def _parse_details(raw: str) -> dict[str, str]:
    """Split only on observed key boundaries; keep each value byte-for-text exact."""
    result: dict[str, str] = {}
    matches = list(_DETAIL_KEY.finditer(raw))
    for index, match in enumerate(matches):
        key = match.group(1)
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        if key in result:
            raise M2TraceError(f"duplicate M2 detail key: {key}")
        result[key] = raw[value_start:value_end].strip()
    return result


def parse_log_event(line: str) -> dict:
    """Parse one exact LogEvent line without deriving unlogged controller state."""
    original = line.rstrip("\r\n")
    payload = original
    marker = "[AI Cadets M2] "
    if payload.startswith(marker):
        payload = payload[len(marker):]
    match = _PREFIX.fullmatch(payload)
    if not match:
        raise M2TraceError("line does not match the current AICadetsWaveCadet.LogEvent prefix")
    values = match.groupdict()
    try:
        game_time = float(values["game_time"])
    except ValueError as err:
        raise M2TraceError("M2 game-time field is not numeric") from err
    if not math.isfinite(game_time):
        raise M2TraceError("M2 game-time field must be finite")
    details_raw = values.pop("raw_details") or ""
    source = {
        "format": SOURCE_FORMAT,
        "build_tag": values.pop("build"),
        "event_sequence": values.pop("event_sequence"),
        "run_id": values.pop("run_id"),
        "cadet_name": values.pop("cadet_name"),
        "game_time": values.pop("game_time"),
    }
    observed = {
        "driver": values.pop("driver"),
        "order_mode": values.pop("mode"),
        "controller_state": values.pop("state"),
        "target_view_id": values.pop("target"),
        "event_name": values.pop("event_name"),
        "game_time_seconds": game_time,
    }
    if values:
        raise M2TraceError("unrecognized LogEvent prefix fields: " + ", ".join(sorted(values)))
    return {
        "type": "event",
        "event": "m2_source_observation",
        "source": source,
        "observed": observed,
        "details": _parse_details(details_raw),
        "raw_details": details_raw,
        "raw_line": original,
        "replayability": {
            "status": "unreplayable",
            "reason_code": "m2_log_event_is_observation_only",
            "missing_fields": list(_REQUIRED_DECISION_FIELDS),
        },
    }


def adapt_lines(lines: Iterable[str]) -> list[dict]:
    observations = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            observations.append(parse_log_event(line))
        except M2TraceError as err:
            raise M2TraceError(f"line {line_number}: {err}") from err
    return observations


def write_observation_run(source: Path, out: Path) -> dict:
    """Write a clearly incomplete flight-v1 event-only run without overwriting."""
    if out.exists() and any(out.iterdir()):
        raise M2TraceError(f"output directory is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    observations = adapt_lines(source.read_text(encoding="utf-8").splitlines())
    if not observations:
        raise M2TraceError("input contains no M2 LogEvent lines")
    run_ids = {row["source"]["run_id"] for row in observations}
    metadata = {
        "schema_version": SCHEMA,
        "capture_tier": "custom_logic_m2_log_events_only",
        "capture_complete": False,
        "sample_phase_verified": False,
        "source_format": SOURCE_FORMAT,
        "record_count": len(observations),
        "decision_replay_ready": False,
    }
    if len(run_ids) == 1:
        metadata["run_id"] = next(iter(run_ids))
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    with (out / "000001.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in observations:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="PersistentData export or copied M2 Print log")
    parser.add_argument("--out", type=Path, required=True, help="New or empty output directory")
    args = parser.parse_args()
    print(json.dumps(write_observation_run(args.source, args.out), indent=2))


if __name__ == "__main__":
    main()
