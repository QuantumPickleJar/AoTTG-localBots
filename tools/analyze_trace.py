#!/usr/bin/env python3
"""Local AoTTG AI Cadets v3/v4 diagnostic summarizer. Python stdlib only.

Usage: python tools/analyze_trace.py AICadetsM1Watch7.txt --out flight_report
Parses the known PersistentData JSON text file; never uploads or edits it.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import re
from pathlib import Path
from collections import Counter

VEC_RE = re.compile(r"\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)")
TSTAMP_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s+(.*)$")
KINDS = ("initial", "sample", "transition", "change")


def vector(text: str, key: str):
    match = re.search(r"\b" + re.escape(key) + r"=\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)", text)
    return tuple(float(v) for v in match.groups()) if match else None


def num(text: str, key: str):
    match = re.search(r"\b" + re.escape(key) + r"=(-?\d+(?:\.\d+)?)\b", text)
    return float(match.group(1)) if match else None


def word(text: str, key: str):
    match = re.search(r"\b" + re.escape(key) + r"=([^ \t\n]+)", text)
    return match.group(1) if match else None


def norm(p):
    return math.sqrt(sum(v * v for v in p))


def dist(a, b):
    return norm(tuple(x - y for x, y in zip(a, b)))


def decode_property(value):
    if not isinstance(value, str):
        return ""
    return value[7:] if value.startswith("string:") else value


def load(path: Path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        source = json.loads(text)
    except json.JSONDecodeError:
        if "AICadetsWatcher v" in text:
            return text, "", "raw_text"
        raise ValueError("Expected AoTTG PersistentData JSON with AICadetsM1WatchTrace property")
    if not isinstance(source, dict):
        raise ValueError("PersistentData payload must be a JSON object")
    watch = decode_property(source.get("AICadetsM1WatchTrace", ""))
    controller = decode_property(source.get("AICadetsM1DecisionTrace", ""))
    if not watch:
        raise ValueError("Missing AICadetsM1WatchTrace; check the selected file")
    return watch, controller, "persistent_data_json"


def events(trace: str, source: str):
    out = []
    for linenum, line in enumerate(trace.splitlines(), 1):
        m = TSTAMP_RE.match(line)
        if not m:
            continue
        t, msg = float(m.group(1)), m.group(2)
        out.append({"t": t, "source": source, "kind": msg.split(" ", 1)[0], "msg": msg, "line": linenum})
    return out


def analyze(watch: str, controller: str):
    w = events(watch, "watcher")
    c = events(controller, "controller")
    captures = [x for x in w if x["kind"] in KINDS and vector(x["msg"], "pos")]
    positions = [vector(x["msg"], "pos") for x in captures]
    gases = [num(x["msg"], "gas") for x in captures]
    velocities = [vector(x["msg"], "vel") for x in captures]
    speeds = [norm(v) for v in velocities if v]
    hooks = []
    previous = None
    for item in captures:
        current = word(item["msg"], "hooked")
        if current is not None and current != previous:
            if previous is not None:
                hooks.append({"t": item["t"], "event": "attached" if current == "true" else "released"})
            previous = current
    contacts = [x for x in w if x["kind"] in ("possible_impact", "possible_surface_contact", "landing_like_impulse", "landing_velocity_change", "hook_transition_impulse", "hook_transition_velocity_change", "hook_transition_near_surface", "unexplained_velocity_change", "velocity_impulse_unknown")]
    selected = [x for x in c if "anchor_selected " in x["msg"]]
    rejected = [x for x in c if "candidate rejected=" in x["msg"]]
    finish = [word(x["msg"], "reason") for x in c if "finish reason=" in x["msg"]]
    terminated = [x for x in w if x["kind"] in ("watch_end", "watch_timeout", "record_limit_reached", "scout_dead_or_despawned", "ownership_lost", "master_lost")]
    displacement = dist(positions[0], positions[-1]) if len(positions) >= 2 else None
    horizontal = math.hypot(positions[-1][0] - positions[0][0], positions[-1][2] - positions[0][2]) if len(positions) >= 2 else None
    sample_path = sum(dist(a, b) for a, b in zip(positions, positions[1:]))
    goodgas = [v for v in gases if v is not None]
    last_release = next((e["t"] for e in reversed(hooks) if e["event"] == "released"), None)
    contact_after_release = [x for x in contacts if last_release is not None and 0 <= x["t"] - last_release <= 0.6 and x["kind"] in ("possible_surface_contact", "possible_impact")]
    risk_hits = [x for x in captures if (word(x["msg"], "riskray") or "") not in ("", "not_sampled", "clear", "skip_slow")]
    risk_near_contact = [x for x in risk_hits if any(0 <= impact["t"] - x["t"] <= 0.5 for impact in contacts)]
    kinds = Counter(x["kind"] for x in w)
    issues = []
    if contact_after_release:
        issues.append("A likely surface-contact impulse occurred within 0.6 s after final hook release. Check whether the controller was in Observe (collision guard is bypassed there in PR #3); the risk ray may detect a surface but does not prove contact.")
    if risk_near_contact:
        issues.append(f"{len(risk_near_contact)} forward risk-ray hits occurred within 0.5 s before detected velocity impulses. Compare controller state and guard activation rather than assuming a linecast is a contact callback.")
    if any("guard_inactive state=Observe" in x["msg"] for x in c):
        issues.append("Instrumented controller explicitly reports the collision guard is inactive during Observe; impacts during that interval require a separate safety analysis.")
    if not c:
        issues.append("Missing controller decision trace: anchor candidates, safety decisions, state changes, and command intent cannot be established from this run.")
    if len(hooks) >= 4:
        issues.append("Both hook attachment/release cycles were observed. This is maneuver evidence, not proof of waypoint arrival, safe landing, or repeatable success.")
    if terminated and terminated[-1]["kind"] == "watch_timeout":
        issues.append("Watch window expired by design. Do not infer controller success/failure from watcher timeout.")
    if any("ray=none" in e["msg"] or "map_hit=none" in e["msg"] for e in contacts):
        issues.append("At least one sudden deceleration had no confirming map-layer ray hit; it may be a landing, missed surface, or other physics impulse.")
    return {
        "watcher_version": watch.splitlines()[0].split(";")[0],
        "watcher_events": len(w), "controller_events": len(c), "record_counts": dict(kinds),
        "duration": (w[-1]["t"] - w[0]["t"]) if len(w) >= 2 else None,
        "flight_duration_observed": captures[-1]["t"] - captures[0]["t"] if len(captures) > 1 else None,
        "displacement_3d": displacement, "displacement_horizontal": horizontal,
        "path_length_lower_bound_sampled": sample_path,
        "gas_used": goodgas[0] - goodgas[-1] if len(goodgas) > 1 else None,
        "peak_speed_sampled": max(speeds) if speeds else None,
        "hooks": hooks, "impact_clues": contacts, "risk_hits": risk_hits,
        "controller_selected_anchors": len(selected),
        "controller_candidate_rejections": len(rejected),
        "controller_finish_reasons": finish,
        "watcher_stop": terminated[-1]["kind"] if terminated else "not_recorded",
        "issues": issues,
        "timeline": sorted(w + c, key=lambda e: (e["t"], 0 if e["source"] == "controller" else 1)),
    }


def f(value, suffix=""):
    return (f"{value:.2f}{suffix}" if isinstance(value, (float, int)) else "unavailable")


def report(result, name):
    r = result
    out = [f"# AI Cadets M1 flight diagnostic — {name}", "", "## Summary", "",
           f"- Source: {r['watcher_version']}; {r['watcher_events']} watcher events, {r['controller_events']} controller events.",
           f"- 3D displacement: {f(r['displacement_3d'])} world units; horizontal: {f(r['displacement_horizontal'])} units.",
           f"- Sampled path length (lower bound): {f(r['path_length_lower_bound_sampled'])} units; peak sampled speed: {f(r['peak_speed_sampled'])} units/s.",
           f"- Gas consumed (observed): {f(r['gas_used'])} units.",
           f"- Hook transitions: {len(r['hooks'])}; candidate selections logged: {r['controller_selected_anchors']}; candidate rejections logged: {r['controller_candidate_rejections']}.",
           f"- Controller finish reasons: {', '.join(r['controller_finish_reasons']) or 'NOT OBSERVED'}; watcher stopped: {r['watcher_stop']}.",
           "", "## Hook events", ""]
    out += [f"- t={f(h['t'])}: {h['event']}" for h in r["hooks"]] or ["- None observed."]
    out += ["", "## Physics impulses (inferred; not collision callbacks)", ""]
    out += [f"- t={f(e['t'])} {e['msg']}" for e in r["impact_clues"]] or ["- None above configured threshold."]
    out += ["", "## Forward risk-ray hits (proximity, not collision)", ""]
    out += [f"- t={f(e['t'])} {e['msg']}" for e in r["risk_hits"][:15]] or ["- None observed or unavailable in the older watcher."]
    out += ["", "## Development findings", ""]
    out += [f"- {x}" for x in r["issues"]] or ["- No flagged pattern. This does not establish safe navigation."]
    out += ["", "## Evidence limits", "",
            "AoTTG Custom Logic runtime is not simulated by this analyzer. Sampled positions and map-layer linecasts are evidence, not exact physical collision callbacks. Controller decision events exist only when the instrumented controller is enabled. Comparisons between runs require matching map, starting pose and settings.", ""]
    return "\n".join(out)


def compact_prompt(r, name):
    return f"""# Single-pass M1 improvement prompt — AoTTG-localBots

Act as a careful AoTTG2 Custom Logic developer. Modify ONLY one bounded M1 behavior based on the evidence below; return a minimal patch and test checklist. Do NOT start M2 combat or M3 boss behavior before M1 traversal is reliable. Preserve the v0.1.1 probe, master-only AI mutation, no teleports/velocity writes/refills, no nonconsensual telemetry, and the addon interface. Do not claim an in-game test from a static check. Official APIs must be confirmed rather than invented.

Evidence file: {name} ({r['watcher_version']}). Watcher events={r['watcher_events']}; controller events={r['controller_events']}; hook transitions={len(r['hooks'])}; candidate rejects={r['controller_candidate_rejections']}; controller outcome={r['controller_finish_reasons'] or 'UNKNOWN (no controller trace)'}.
Measured: horizontal displacement={f(r['displacement_horizontal'])}; 3D displacement={f(r['displacement_3d'])}; gas use={f(r['gas_used'])}; peak sampled speed={f(r['peak_speed_sampled'])}; watcher stop={r['watcher_stop']}.

Specific anomalies / uncertainties:
""" + "\n".join(f"- {x}" for x in r["issues"]) + f"""

Collision-related evidence (timestamped):
""" + "\n".join(f"- t={f(e['t'])}: {e['msg']}" for e in r["impact_clues"][:12]) + """

Task: (1) separate facts from hypotheses; (2) identify ONE highest-value controller or observer defect to address, with a guardrail against regressions; (3) modify the smallest code surface; (4) provide static tests and a three-run manual in-game test matrix (clear route, obstructed route, ground/landing), including expected telemetry and rollback; (5) state what evidence would establish M1 completion. No broad architecture rewrite, no speculative new API, no merge before gameplay validation.
"""


def run(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("watch_file", type=Path)
    ap.add_argument("--out", type=Path, default=Path("flight_report"))
    args = ap.parse_args(argv)
    watch, controller, _ = load(args.watch_file)
    r = analyze(watch, controller)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.md").write_text(report(r, args.watch_file.name), encoding="utf-8")
    (args.out / "compact_prompt.md").write_text(compact_prompt(r, args.watch_file.name), encoding="utf-8")
    with (args.out / "timeline.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["t", "source", "kind", "msg", "line"])
        writer.writeheader()
        writer.writerows(r["timeline"])
    serializable = {k:v for k,v in r.items() if k != "timeline"}
    (args.out / "metrics.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"Report: {args.out / 'report.md'}")
    print(f"Short prompt: {args.out / 'compact_prompt.md'}")
    print(f"Controller trace: {'present' if controller else 'missing (expected on v3)'}")


if __name__ == "__main__":
    run()
