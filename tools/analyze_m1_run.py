#!/usr/bin/env python3
"""Correlate controller event logs with watcher observations."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PREFIX = "[AI Cadets M1R]"


class Event:
    def __init__(self, t: float, source: str, text: str, confidence: str):
        self.t = t
        self.source = source
        self.text = text
        self.confidence = confidence


def parse_controller(path: Path) -> list[Event]:
    events: list[Event] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if PREFIX not in raw:
            continue
        line = raw[raw.index(PREFIX) + len(PREFIX) :].strip()
        match = re.search(r"\bt=([0-9.]+)\b", line)
        if match:
            t = float(match.group(1))
            confidence = "verified"
        else:
            t = 0.0
            confidence = "verified"
        events.append(Event(t=t, source="controller", text=line, confidence=confidence))
    return events


def parse_watcher(path: Path) -> list[Event]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    trace = str(payload.get("AICadetsM1WatchTrace", ""))
    events: list[Event] = []
    for raw in trace.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        match = re.match(r"^([0-9.]+)\s+(.+)$", raw)
        if not match:
            continue
        t = float(match.group(1))
        text = match.group(2)
        confidence = "inferred"
        if text.startswith("watch_started") or text.startswith("scout_found") or text.startswith("sample ") or text.startswith("change "):
            confidence = "observed"
        events.append(Event(t=t, source="watcher", text=text, confidence=confidence))
    return events


def classify(text: str) -> str:
    if "possible_impact" in text or "hook_transition_near_surface" in text or "landing_velocity_change" in text:
        return "inferred"
    if "result_class=" in text or "state_transition" in text or "hook_launch" in text or "hook_attached" in text or "hook_release" in text:
        return "verified"
    return "observed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller-log", type=Path, required=True, help="Path to copied chat log lines containing [AI Cadets M1R]")
    parser.add_argument("--watch-file", type=Path, required=True, help="Path to AICadetsM1Watch*.txt JSON file")
    parser.add_argument("--output", type=Path, default=None, help="Optional output path for timeline markdown")
    args = parser.parse_args()

    rows = parse_controller(args.controller_log) + parse_watcher(args.watch_file)
    rows.sort(key=lambda e: e.t)
    lines = [
        "| t_game | source | confidence | event |",
        "|---:|---|---|---|",
    ]
    for event in rows:
        confidence = classify(event.text) if event.source == "controller" else event.confidence
        lines.append(f"| {event.t:.2f} | {event.source} | {confidence} | {event.text.replace('|', '/')} |")
    output = "\n".join(lines) + "\n"
    if args.output is None:
        print(output, end="")
    else:
        args.output.write_text(output, encoding="utf-8")
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
