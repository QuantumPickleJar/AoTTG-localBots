#!/usr/bin/env python3
"""Safely snapshot and recycle AoTTG2 M2 watcher PersistentData files.

Archives are byte-exact gzip snapshots with SHA-256 manifests. Source files are
removed only when --prune-verified is explicitly supplied and every selected
file has a verified archive copy. The tool never calls PersistentData.Clear.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA = "aottg.m2-watcher-archive.v1"
WATCH_PREFIX = "AICadetsM2Watch"
WATCHER_FILE_RE = re.compile(
    r"^AICadetsM2Watch(?P<index>[0-9]+)(?P<suffix>\.txt|\.json)?$",
    re.IGNORECASE,
)
SLOT_LIMIT = 100
MAX_SOURCE_BYTES = 16 * 1024 * 1024
DEFAULT_PROCESS_NAME = "AoTTG2.exe"


class ArchiveError(RuntimeError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def default_source() -> Path:
    return Path.home() / "Documents" / "Aottg2" / "PersistentData"


def default_archive_root() -> Path:
    return Path.home() / "Documents" / "Aottg2" / "Recorders" / "M2WatcherArchive"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_separate_roots(source: Path, archive_root: Path) -> tuple[Path, Path]:
    source = source.expanduser().resolve(strict=False)
    archive_root = archive_root.expanduser().resolve(strict=False)
    if source.exists() and not source.is_dir():
        raise ArchiveError(f"PersistentData source is not a directory: {source}")
    try:
        archive_root.relative_to(source)
        raise ArchiveError("Archive directory must be outside the PersistentData source.")
    except ValueError:
        pass
    try:
        source.relative_to(archive_root)
        raise ArchiveError("PersistentData source must be outside the archive directory.")
    except ValueError:
        pass
    return source, archive_root


def watcher_match(name: str) -> re.Match[str] | None:
    return WATCHER_FILE_RE.fullmatch(name)


def inventory(source: Path) -> tuple[list[tuple[int, Path]], list[str]]:
    candidates: list[tuple[int, Path]] = []
    unexpected: list[str] = []
    indexes: dict[int, Path] = {}

    try:
        entries = list(source.iterdir())
    except OSError as exc:
        raise ArchiveError(f"Cannot list PersistentData directory: {exc}") from exc

    for path in entries:
        if not path.name.casefold().startswith(WATCH_PREFIX.casefold()):
            continue
        match = watcher_match(path.name)
        if path.is_symlink() or not path.is_file() or match is None:
            unexpected.append(path.name)
            continue
        index = int(match.group("index"))
        if index in indexes:
            unexpected.extend([indexes[index].name, path.name])
            continue
        indexes[index] = path
        candidates.append((index, path))

    candidates.sort(key=lambda item: (item[0], item[1].name.casefold()))
    return candidates, sorted(set(unexpected), key=str.casefold)


def free_slots(candidates: list[tuple[int, Path]]) -> list[int]:
    occupied = {index for index, _ in candidates if 0 <= index < SLOT_LIMIT}
    return [index for index in range(SLOT_LIMIT) if index not in occupied]


def print_preflight(source: Path) -> int:
    candidates, unexpected = inventory(source)
    available = free_slots(candidates)
    print(f"PersistentData: {source}")
    print(f"Watcher files found: {len(candidates)}")
    print(f"Watcher slots 0-{SLOT_LIMIT - 1}: {SLOT_LIMIT - len(available)} occupied, {len(available)} free")
    if unexpected:
        print(f"Unrecognized watcher-like entries: {len(unexpected)}")
        for name in unexpected:
            print(f"  {name}")
    if unexpected:
        print("Status: BLOCKED — review ambiguous watcher-like entries before archival or pruning.")
        return 2
    if not available:
        print("Status: BLOCKED — archive and verify watcher files before starting an M2 playtest.")
        return 2
    print(f"Status: READY — first free watcher slot is {available[0]}.")
    return 0


def read_stable(path: Path, attempts: int = 4) -> bytes:
    last_problem = "file did not remain stable while being read"
    for attempt in range(attempts):
        try:
            with path.open("rb") as handle:
                before = os.fstat(handle.fileno())
                if before.st_size > MAX_SOURCE_BYTES:
                    raise ArchiveError(
                        f"{path.name} exceeds the safety limit of {MAX_SOURCE_BYTES} bytes."
                    )
                data = handle.read(MAX_SOURCE_BYTES + 1)
                after = os.fstat(handle.fileno())
            current = path.stat()
        except FileNotFoundError:
            raise
        except OSError as exc:
            last_problem = str(exc)
            time.sleep(0.05 * (attempt + 1))
            continue

        stable = (
            len(data) <= MAX_SOURCE_BYTES
            and len(data) == before.st_size == after.st_size == current.st_size
            and before.st_mtime_ns == after.st_mtime_ns == current.st_mtime_ns
            and before.st_ino == after.st_ino == current.st_ino
            and before.st_dev == after.st_dev == current.st_dev
        )
        if stable:
            try:
                with path.open("rb") as second_handle:
                    second_read = second_handle.read(MAX_SOURCE_BYTES + 1)
                    second_stat = os.fstat(second_handle.fileno())
                second_current = path.stat()
            except OSError as exc:
                last_problem = str(exc)
                time.sleep(0.05 * (attempt + 1))
                continue
            if (
                second_read == data
                and len(second_read) <= MAX_SOURCE_BYTES
                and second_stat.st_size == current.st_size
                and second_current.st_size == current.st_size
                and second_stat.st_mtime_ns == current.st_mtime_ns
                and second_current.st_mtime_ns == current.st_mtime_ns
                and second_stat.st_ino == current.st_ino
                and second_current.st_ino == current.st_ino
                and second_stat.st_dev == current.st_dev
                and second_current.st_dev == current.st_dev
            ):
                return data

        last_problem = "file changed during capture"
        time.sleep(0.05 * (attempt + 1))

    raise ArchiveError(f"Could not capture a stable copy of {path.name}: {last_problem}")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write(path, payload)


@contextmanager
def archive_lock(archive_root: Path) -> Iterator[None]:
    archive_root.mkdir(parents=True, exist_ok=True)
    lock_path = archive_root / ".m2-watcher-archive.lock"
    handle = lock_path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ArchiveError("Another M2 watcher archival process is active.") from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ArchiveError("Another M2 watcher archival process is active.") from exc

        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def game_is_running(process_name: str) -> bool:
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                check=False,
                capture_output=True,
                text=True,
                errors="replace",
            )
        except OSError as exc:
            raise ArchiveError(f"Could not query Windows process list: {exc}") from exc
        if result.returncode != 0:
            raise ArchiveError("Windows tasklist failed; refusing to prune PersistentData files.")
        for row in csv.reader(result.stdout.splitlines()):
            if row and row[0].casefold() == process_name.casefold():
                return True
        return False

    try:
        result = subprocess.run(
            ["pgrep", "-x", process_name],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
        )
    except OSError as exc:
        raise ArchiveError(f"Could not query process list with pgrep: {exc}") from exc
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise ArchiveError("pgrep failed; refusing to prune PersistentData files.")


def new_archive_dir(archive_root: Path) -> tuple[str, Path]:
    archive_root.mkdir(parents=True, exist_ok=True)
    for _ in range(8):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
        run_dir = archive_root / archive_id
        try:
            run_dir.mkdir()
            return archive_id, run_dir
        except FileExistsError:
            continue
    raise ArchiveError("Could not allocate a unique archive directory.")


class ArchiveSession:
    def __init__(self, source: Path, archive_root: Path, mode: str):
        self.source = source
        self.archive_id, self.run_dir = new_archive_dir(archive_root)
        self.manifest_path = self.run_dir / "manifest.json"
        self.manifest: dict[str, Any] = {
            "schema": SCHEMA,
            "archive_id": self.archive_id,
            "mode": mode,
            "source_directory": str(source),
            "created_at_utc": now_utc(),
            "updated_at_utc": now_utc(),
            "status": "capturing",
            "slot_limit": SLOT_LIMIT,
            "snapshots": [],
            "latest_snapshot_by_source": {},
            "observed_source_files": [],
            "source_disappearances": [],
            "unrecognized_watcher_entries": [],
            "capture_errors": [],
            "active_capture_errors": {},
            "prune_requested": False,
            "pruned_source_files": [],
        }
        self._snapshot_index: dict[tuple[str, str], dict[str, Any]] = {}
        self._present_names: set[str] = set()
        self._source_signatures: dict[str, tuple[int, int, int, int]] = {}
        self._active_capture_errors: dict[str, str] = {}
        atomic_write_json(self.manifest_path, self.manifest)

    def _save_manifest(self) -> None:
        self.manifest["updated_at_utc"] = now_utc()
        atomic_write_json(self.manifest_path, self.manifest)

    def capture_file(self, path: Path) -> str | None:
        try:
            before = path.stat()
        except FileNotFoundError:
            return None
        signature = (before.st_size, before.st_mtime_ns, before.st_ino, before.st_dev)
        latest_digest = self.manifest["latest_snapshot_by_source"].get(path.name)
        if self._source_signatures.get(path.name) == signature and latest_digest:
            return latest_digest
        try:
            raw = read_stable(path)
            after = path.stat()
        except FileNotFoundError:
            return None
        after_signature = (after.st_size, after.st_mtime_ns, after.st_ino, after.st_dev)
        if signature != after_signature or len(raw) != after.st_size:
            raise ArchiveError("source changed during snapshot; retrying on the next scan")
        digest = sha256(raw)
        key = (path.name, digest)
        existing = self._snapshot_index.get(key)
        if existing is not None:
            if self.manifest["latest_snapshot_by_source"].get(path.name) != digest:
                self.manifest["latest_snapshot_by_source"][path.name] = digest
                self._save_manifest()
            self._source_signatures[path.name] = after_signature
            return digest

        match = watcher_match(path.name)
        if match is None:
            raise ArchiveError(f"Refusing to archive unexpected filename: {path.name}")
        slot = int(match.group("index"))
        relative = Path("snapshots") / f"slot-{slot:04d}" / f"{digest}.gz"
        destination = self.run_dir / relative
        compressed = gzip.compress(raw, compresslevel=1, mtime=0)
        if destination.exists():
            stored = destination.read_bytes()
            if sha256(stored) != sha256(compressed) or gzip.decompress(stored) != raw:
                raise ArchiveError(f"Archive collision or corruption at {relative}")
        else:
            atomic_write(destination, compressed)
        stored = destination.read_bytes()
        decoded = gzip.decompress(stored)
        if decoded != raw or sha256(decoded) != digest:
            raise ArchiveError(f"Archive verification failed for {path.name}")

        record: dict[str, Any] = {
            "source_name": path.name,
            "source_index": slot,
            "source_size_bytes": len(raw),
            "source_sha256": digest,
            "archive_path": relative.as_posix(),
            "archive_size_bytes": len(stored),
            "archive_sha256": sha256(stored),
            "first_seen_at_utc": now_utc(),
            "last_seen_at_utc": now_utc(),
            "times_seen": 1,
        }
        self.manifest["snapshots"].append(record)
        self._snapshot_index[key] = record
        self.manifest["latest_snapshot_by_source"][path.name] = digest
        self._save_manifest()
        self._source_signatures[path.name] = after_signature
        return digest

    def capture_all(self) -> tuple[list[tuple[int, Path]], list[str]]:
        candidates, unexpected = inventory(self.source)
        for name in unexpected:
            if name not in self.manifest["unrecognized_watcher_entries"]:
                self.manifest["unrecognized_watcher_entries"].append(name)

        current_names = {path.name for _, path in candidates}
        vanished = sorted(self._present_names - current_names, key=str.casefold)
        for name in vanished:
            self.manifest["source_disappearances"].append(
                {"source_name": name, "noticed_at_utc": now_utc()}
            )
        for name in vanished:
            self._source_signatures.pop(name, None)
        self._present_names = current_names
        known_names = set(self.manifest["observed_source_files"])
        self.manifest["observed_source_files"] = sorted(
            known_names | current_names, key=str.casefold
        )

        for _, path in candidates:
            try:
                digest = self.capture_file(path)
                if digest is None and path.name not in self.manifest["latest_snapshot_by_source"]:
                    raise ArchiveError("source disappeared before its first verified snapshot")
                if path.name in self._active_capture_errors:
                    self._active_capture_errors.pop(path.name, None)
                    self.manifest["active_capture_errors"] = dict(self._active_capture_errors)
                    self._save_manifest()
            except (ArchiveError, OSError) as exc:
                message = f"{path.name}: {exc}"
                self._active_capture_errors[path.name] = message
                if message not in self.manifest["capture_errors"]:
                    self.manifest["capture_errors"].append(message)
                self.manifest["active_capture_errors"] = dict(self._active_capture_errors)
                self._save_manifest()

        return candidates, unexpected

    def _snapshot_record(self, source_name: str, digest: str) -> dict[str, Any] | None:
        return self._snapshot_index.get((source_name, digest))

    def verify_snapshot(self, record: dict[str, Any]) -> bool:
        relative = Path(record["archive_path"])
        path = (self.run_dir / relative).resolve(strict=False)
        try:
            path.relative_to(self.run_dir.resolve())
        except ValueError:
            return False
        try:
            compressed = path.read_bytes()
            if sha256(compressed) != record["archive_sha256"]:
                return False
            raw = gzip.decompress(compressed)
        except (OSError, EOFError, gzip.BadGzipFile, zlib.error):
            return False
        return (
            len(raw) == record["source_size_bytes"]
            and sha256(raw) == record["source_sha256"]
        )

    def finish(self, prune_verified: bool, process_name: str, settle_seconds: float) -> bool:
        self.manifest["prune_requested"] = prune_verified
        if settle_seconds > 0:
            time.sleep(settle_seconds)
        self.capture_all()

        candidates, unexpected = inventory(self.source)
        current_records: list[tuple[Path, bytes, dict[str, Any]]] = []
        for _, path in candidates:
            try:
                raw = read_stable(path)
            except FileNotFoundError:
                continue
            except (ArchiveError, OSError) as exc:
                message = f"{path.name}: final read failed: {exc}"
                self._active_capture_errors[path.name] = message
                if message not in self.manifest["capture_errors"]:
                    self.manifest["capture_errors"].append(message)
                continue

            digest = sha256(raw)
            record = self._snapshot_record(path.name, digest)
            if record is None or not self.verify_snapshot(record):
                message = f"{path.name}: no verified archive snapshot matches the final source bytes"
                self._active_capture_errors[path.name] = message
                if message not in self.manifest["capture_errors"]:
                    self.manifest["capture_errors"].append(message)
                continue
            self._active_capture_errors.pop(path.name, None)
            current_records.append((path, raw, record))

        final_candidates, final_unexpected = inventory(self.source)
        final_names = {path.name for _, path in final_candidates}
        current_records = [
            item for item in current_records if item[0].name in final_names
        ]
        recorded_names = {path.name for path, _, _ in current_records}
        for _, path in final_candidates:
            if path.name not in recorded_names:
                self._active_capture_errors[path.name] = (
                    f"{path.name}: final inventory lacks a verified snapshot"
                )
        self.manifest["active_capture_errors"] = dict(self._active_capture_errors)
        all_unexpected = sorted(set(unexpected + final_unexpected), key=str.casefold)
        for name in all_unexpected:
            if name not in self.manifest["unrecognized_watcher_entries"]:
                self.manifest["unrecognized_watcher_entries"].append(name)

        if not prune_verified:
            if all_unexpected or self._active_capture_errors:
                self.manifest["status"] = "incomplete_capture"
                self._save_manifest()
                print("Archive incomplete; originals were kept. Review manifest errors before playtesting.")
                return False
            self.manifest["status"] = "complete_unpruned"
            self._save_manifest()
            print(f"Archived {len(self.manifest['snapshots'])} verified watcher snapshots to {self.run_dir}")
            print("Original PersistentData files were kept.")
            return True

        if all_unexpected:
            self.manifest["status"] = "blocked_unrecognized_entries"
            self._save_manifest()
            print("Pruning blocked: unrecognized watcher-like entries need review.")
            return False
        if self._active_capture_errors or len(current_records) != len(final_candidates):
            self.manifest["status"] = "blocked_capture_or_verification_error"
            self._save_manifest()
            print("Pruning blocked: every current watcher file must have a verified archive copy.")
            return False
        if game_is_running(process_name):
            self.manifest["status"] = "blocked_game_running"
            self._save_manifest()
            print("Pruning blocked: the game is still running.")
            return False

        self.manifest["status"] = "verified_ready_to_prune"
        self._save_manifest()
        for path, expected_raw, record in current_records:
            if game_is_running(process_name):
                self.manifest["status"] = "partial_game_restarted_during_prune"
                self._save_manifest()
                print("Pruning stopped because the game process restarted.")
                return False
            if path.is_symlink() or path.resolve().parent != self.source:
                self.manifest["status"] = "blocked_source_path_changed"
                self._save_manifest()
                print(f"Pruning blocked by an unexpected source path: {path}")
                return False
            try:
                current_raw = read_stable(path)
            except (ArchiveError, OSError) as exc:
                self.manifest["status"] = "partial_source_changed_during_prune"
                self._active_capture_errors[path.name] = f"{path.name}: {exc}"
                self.manifest["active_capture_errors"] = dict(self._active_capture_errors)
                self._save_manifest()
                print(f"Pruning stopped because {path.name} changed or became unreadable.")
                return False
            if (
                sha256(current_raw) != record["source_sha256"]
                or current_raw != expected_raw
                or not self.verify_snapshot(record)
            ):
                self.manifest["status"] = "partial_source_changed_during_prune"
                self._save_manifest()
                print(f"Pruning stopped because {path.name} no longer matches its archive.")
                return False
            if game_is_running(process_name):
                self.manifest["status"] = "partial_game_restarted_during_prune"
                self._save_manifest()
                print("Pruning stopped because the game process restarted.")
                return False
            try:
                path.unlink()
            except OSError as exc:
                self.manifest["status"] = "partial_prune_error"
                self.manifest["capture_errors"].append(f"{path.name}: delete failed: {exc}")
                self._save_manifest()
                print(f"Could not remove verified source file {path.name}: {exc}")
                return False
            if path.exists():
                self.manifest["status"] = "partial_prune_error"
                self._save_manifest()
                print(f"Source file remains after removal attempt: {path.name}")
                return False
            self.manifest["pruned_source_files"].append(
                {
                    "source_name": path.name,
                    "source_sha256": record["source_sha256"],
                    "pruned_at_utc": now_utc(),
                }
            )
            self._save_manifest()

        remaining, remaining_unexpected = inventory(self.source)
        self.manifest["remaining_watcher_files"] = [path.name for _, path in remaining]
        self.manifest["remaining_unrecognized_entries"] = remaining_unexpected
        self.manifest["status"] = (
            "complete_pruned"
            if not remaining and not remaining_unexpected
            else "partial_prune_incomplete"
        )
        self._save_manifest()
        if self.manifest["status"] == "complete_pruned":
            slots = free_slots(remaining)
            print(f"Archived and verified {len(current_records)} watcher files: {self.run_dir}")
            if len(slots) == SLOT_LIMIT:
                print("Verified watcher files were removed; slots 0-99 are free.")
            else:
                print(f"Verified archive complete; {len(slots)} of 100 slots are free.")
            return True
        print(f"Archive verified, but watcher files remain in PersistentData: {self.manifest['remaining_watcher_files']}")
        return False


def create_session(source: Path, archive_root: Path, mode: str) -> ArchiveSession:
    session = ArchiveSession(source, archive_root, mode)
    print(f"Archive session: {session.archive_id}")
    print(f"Archive directory: {session.run_dir}")
    return session


def run_archive(source: Path, archive_root: Path, prune: bool, process_name: str) -> int:
    if prune and game_is_running(process_name):
        raise ArchiveError("Close AoTTG2 before running archive with --prune-verified.")
    candidates, unexpected = inventory(source)
    if not candidates:
        print("No M2 watcher files found.")
        if unexpected:
            print(f"Unrecognized watcher-like entries prevent a clean preflight: {unexpected}")
            return 2
        return print_preflight(source)
    session = create_session(source, archive_root, "one_shot")
    session.capture_all()
    ok = session.finish(prune, process_name, 0.0)
    return 0 if ok else 2


def run_monitor(
    source: Path,
    archive_root: Path,
    prune: bool,
    process_name: str,
    poll_seconds: float,
    settle_seconds: float,
    once: bool,
) -> int:
    def archive_existing(mode: str) -> int:
        candidates, unexpected = inventory(source)
        if not candidates and not unexpected:
            return 0
        session = create_session(source, archive_root, mode)
        session.capture_all()
        return 0 if session.finish(prune, process_name, settle_seconds) else 2

    def capture_active_session(mode: str) -> bool:
        session = create_session(source, archive_root, mode)
        while game_is_running(process_name):
            session.capture_all()
            time.sleep(poll_seconds)
        return session.finish(prune, process_name, settle_seconds)

    if game_is_running(process_name):
        print(f"{process_name} is already running; attaching to the active session.")
        print("Slot preparation could not run before this session.")
        if not capture_active_session("attached_active_game"):
            return 2
        if once:
            return 0
        if archive_existing("between_run_slot_cleanup") != 0:
            return 2
        if print_preflight(source) != 0:
            return 2
    else:
        if archive_existing("pre_run_slot_cleanup") != 0:
            return 2
        if print_preflight(source) != 0:
            return 2

    while True:
        print(f"Waiting for {process_name}. Press Ctrl+C to stop.")
        while not game_is_running(process_name):
            time.sleep(poll_seconds)

        print(f"Detected {process_name}; archiving watcher changes during the session.")
        if not capture_active_session("game_session"):
            return 2
        if once:
            return 0

        if archive_existing("between_run_slot_cleanup") != 0:
            return 2
        if print_preflight(source) != 0:
            return 2


def run_restore(source: Path, archive_dir: Path, process_name: str, force_overwrite: bool) -> int:
    if game_is_running(process_name):
        raise ArchiveError("Close AoTTG2 before restoring PersistentData files.")
    archive_dir = archive_dir.expanduser().resolve(strict=True)
    manifest_path = archive_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"Cannot read archive manifest: {exc}") from exc
    if manifest.get("schema") != SCHEMA:
        raise ArchiveError("Archive manifest schema is missing or unsupported.")
    if Path(manifest.get("source_directory", "")).resolve() != source:
        raise ArchiveError("Archive source directory does not match the requested PersistentData directory.")

    snapshots_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in manifest.get("snapshots", []):
        name = record.get("source_name", "")
        digest = record.get("source_sha256", "")
        if watcher_match(name) is None or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ArchiveError("Manifest contains an invalid watcher filename or source hash.")
        snapshots_by_key[(name, digest)] = record

    latest_hashes = manifest.get("latest_snapshot_by_source", {})
    if not isinstance(latest_hashes, dict):
        raise ArchiveError("Manifest latest-snapshot index is invalid.")

    restore_items: list[tuple[Path, bytes]] = []
    for name, digest in sorted(latest_hashes.items(), key=lambda item: item[0].casefold()):
        record = snapshots_by_key.get((name, digest))
        if record is None:
            raise ArchiveError(f"Manifest has no snapshot record for {name}")
        relative = Path(record["archive_path"])
        stored_path = (archive_dir / relative).resolve(strict=True)
        try:
            stored_path.relative_to(archive_dir)
        except ValueError as exc:
            raise ArchiveError("Manifest archive path escapes the selected archive directory.") from exc
        compressed = stored_path.read_bytes()
        if sha256(compressed) != record.get("archive_sha256"):
            raise ArchiveError(f"Compressed archive hash mismatch for {name}")
        try:
            raw = gzip.decompress(compressed)
        except (EOFError, gzip.BadGzipFile, zlib.error) as exc:
            raise ArchiveError(f"Archive payload is corrupt for {name}") from exc
        if len(raw) != record.get("source_size_bytes") or sha256(raw) != digest:
            raise ArchiveError(f"Original-byte verification failed for {name}")
        target = source / name
        if target.is_symlink():
            raise ArchiveError(f"Restore target is a symbolic link: {target}")
        if target.exists() and not target.is_file():
            raise ArchiveError(f"Restore target is not a regular file: {target}")
        if target.exists():
            existing = read_stable(target)
            if sha256(existing) == digest:
                continue
            if not force_overwrite:
                raise ArchiveError(
                    f"{name} already exists with different contents; use --force-overwrite to replace it."
                )
        restore_items.append((target, raw))

    source.mkdir(parents=True, exist_ok=True)
    for target, raw in restore_items:
        atomic_write(target, raw)
        if read_stable(target) != raw:
            raise ArchiveError(f"Restored file failed verification: {target.name}")
    print(f"Restored {len(restore_items)} watcher files from {archive_dir}")
    return 0


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-dir", type=Path, default=default_source())
    parser.add_argument("--archive-root", type=Path, default=default_archive_root())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archive, verify, and optionally recycle M2 watcher PersistentData files."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    preflight = commands.add_parser("preflight", help="Read-only watcher slot inventory.")
    add_common_options(preflight)

    archive = commands.add_parser("archive", help="Archive current watcher files once.")
    add_common_options(archive)
    archive.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    archive.add_argument(
        "--prune-verified",
        action="store_true",
        help="After full byte verification, remove only the archived M2 watcher files.",
    )

    monitor = commands.add_parser(
        "monitor", help="Archive existing files, then monitor successive game sessions."
    )
    add_common_options(monitor)
    monitor.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    monitor.add_argument("--poll-seconds", type=float, default=1.0)
    monitor.add_argument("--settle-seconds", type=float, default=2.0)
    monitor.add_argument("--once", action="store_true", help="Stop after one observed session.")
    monitor.add_argument(
        "--prune-verified",
        action="store_true",
        help="Remove exact watcher source files only after verified archival and game exit.",
    )

    restore = commands.add_parser("restore", help="Restore the latest version of each archived file.")
    add_common_options(restore)
    restore.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    restore.add_argument("--archive-dir", type=Path, required=True)
    restore.add_argument("--force-overwrite", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        source, archive_root = ensure_separate_roots(args.source_dir, args.archive_root)
        if args.command == "preflight":
            return print_preflight(source)
        if args.command == "archive":
            with archive_lock(archive_root):
                return run_archive(source, archive_root, args.prune_verified, args.process_name)
        if args.command == "monitor":
            if args.poll_seconds < 0.1:
                raise ArchiveError("--poll-seconds must be at least 0.1.")
            if args.settle_seconds < 0:
                raise ArchiveError("--settle-seconds cannot be negative.")
            with archive_lock(archive_root):
                return run_monitor(
                    source,
                    archive_root,
                    args.prune_verified,
                    args.process_name,
                    args.poll_seconds,
                    args.settle_seconds,
                    args.once,
                )
        if args.command == "restore":
            with archive_lock(archive_root):
                return run_restore(
                    source, args.archive_dir, args.process_name, args.force_overwrite
                )
        parser.error("Unknown command.")
    except ArchiveError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: filesystem operation failed: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
