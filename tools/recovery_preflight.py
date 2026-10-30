#!/usr/bin/env python3
"""Read-only local verification for the known-good M1 Custom Logic files."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

EXPECTED = {
    "AICadetsTraversal.cl": "4c1d23c628d18f98500d2c3f20f5d954c1ea17fd",
    "AICadetsWatcher.cl": "5b3e1720b6e3d66b4fc35d0c9957306b67203b57",
}

def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def verify_addons(folder: Path):
    results = []
    for filename, expected in EXPECTED.items():
        path = folder / filename
        if not path.is_file():
            results.append(("ERROR", filename + ": missing"))
        elif git_blob_sha(path) == expected:
            results.append(("PASS", filename + ": byte-for-byte verified baseline"))
        else:
            results.append(("ERROR", filename + ": modified or wrong version"))
    if not folder.is_dir():
        results.append(("ERROR", "Addons directory not found"))
    else:
        for path in folder.rglob("*.cl"):
            if path.parent != folder and path.name in EXPECTED:
                results.append(("WARN", "Nested duplicate: " + str(path)))
        if (folder / "AICadetsProbe.cl").exists():
            results.append(("INFO", "Disable AICadetsProbe during M1 trials"))
    return results

def inspect_watches(folder: Path):
    if not folder.is_dir():
        return [("WARN", "PersistentData directory not found")]
    files = sorted(folder.glob("AICadetsM1Watch*"), key=lambda x: x.stat().st_mtime, reverse=True)
    result = [("INFO", "Found " + str(len(files)) + " Watch files")]
    occupied = set()
    for file in files:
        match = re.fullmatch(r"AICadetsM1Watch(\d+)(?:\.txt)?", file.name)
        if match:
            occupied.add(int(match.group(1)))
    if all(i in occupied for i in range(100)):
        result.append(("WARN", "Watch0..Watch99 all occupied; archive files to free a slot"))
    if files:
        file = files[0]
        result.append(("INFO", "Newest: " + file.name))
        try:
            payload = json.loads(file.read_text(encoding="utf-8-sig"))
            trace = str(payload.get("AICadetsM1WatchTrace", ""))
            result.append(("PASS" if "watch_started" in trace else "WARN",
                           "watch_started present" if "watch_started" in trace else "watch_started absent"))
            result.append(("PASS" if "scout_found" in trace else "WARN",
                           "scout_found present" if "scout_found" in trace else "scout_found absent"))
        except (OSError, ValueError):
            result.append(("WARN", "Could not read latest Watch file as JSON"))
    return result

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    root = Path.home() / "Documents" / "AoTTG2"
    p.add_argument("--addons", type=Path, default=root / "Addons")
    p.add_argument("--persistent", type=Path, default=root / "PersistentData")
    args = p.parse_args(argv)
    status = verify_addons(args.addons) + inspect_watches(args.persistent)
    for level, message in status:
        print("[" + level + "] " + message)
    print("Only file checks were performed. Live AoTTG execution is unverified.")
    return 1 if any(level == "ERROR" for level, _ in status) else 0

if __name__ == "__main__":
    raise SystemExit(main())
