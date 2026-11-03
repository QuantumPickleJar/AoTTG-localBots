#!/usr/bin/env python3
"""Bounded, Unity-independent writer for the aicadets.flight.v1 JSONL format.

The writer consumes copied primitive snapshots only. It has no Unity imports,
keeps a bounded handoff queue, accounts for frame loss, and commits hashed
chunks independently. It is a runtime-independent reference/sidecar core, not
a game plugin or evidence that AoTTG2 can load a recorder.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
import uuid
from typing import Any, Mapping, Sequence
from urllib.parse import quote


SCHEMA = "aicadets.flight.v1"
MANIFEST_SCHEMA = "aicadets.flight.chunk-index.v1"
WRITER_VERSION = "0.1.0"
_RESERVED_SAMPLE_KEYS = {"id", "kind", "pos", "vel", "rot", "ang_vel", "state", "ai_state"}
_RESERVED_EVENT_KEYS = {
    "type", "event", "t", "step", "id", "actor", "ids", "correlation_id",
    "decision_id", "evidence",
}


class WriterError(RuntimeError):
    pass


class RecorderOverloadError(WriterError):
    """A caller must retain/retry this observation; it was not accepted."""


class RecorderStorageLimitError(WriterError):
    """The configured storage limit prevents accepting another event."""


@dataclass(frozen=True, slots=True)
class FrozenMap:
    items: tuple[tuple[str, Any], ...]


@dataclass(frozen=True, slots=True)
class FrozenSequence:
    items: tuple[Any, ...]


def _freeze_json(value: Any, depth: int = 0) -> Any:
    if depth > 20:
        raise ValueError("snapshot JSON nesting exceeds 20 levels")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("snapshot values must be finite")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("snapshot object keys must be strings")
        return FrozenMap(tuple((key, _freeze_json(value[key], depth + 1)) for key in sorted(value)))
    if isinstance(value, (list, tuple)):
        return FrozenSequence(tuple(_freeze_json(item, depth + 1) for item in value))
    raise TypeError(f"unsupported snapshot value type: {type(value).__name__}")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, FrozenMap):
        return {key: _thaw_json(item) for key, item in value.items}
    if isinstance(value, FrozenSequence):
        return [_thaw_json(item) for item in value.items]
    return value


def _mapping(value: Mapping[str, Any] | None) -> FrozenMap:
    frozen = _freeze_json(value or {})
    if not isinstance(frozen, FrozenMap):
        raise TypeError("expected an object")
    return frozen


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _vector(value: Sequence[float] | None, length: int, label: str) -> tuple[float, ...] | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or len(value) != length:
        raise ValueError(f"{label} must contain {length} numeric values")
    return tuple(_finite(component, f"{label}[{index}]") for index, component in enumerate(value))


def _estimate(value: Any) -> int:
    """Conservative Python heap estimate for already-frozen JSON primitives."""
    if isinstance(value, FrozenMap):
        return sys.getsizeof(value) + sys.getsizeof(value.items) + sum(
            sys.getsizeof(k) + _estimate(v) + 32 for k, v in value.items)
    if isinstance(value, FrozenSequence):
        return sys.getsizeof(value) + sys.getsizeof(value.items) + sum(_estimate(v) for v in value.items)
    if isinstance(value, (tuple, list)):
        return sys.getsizeof(value) + sum(_estimate(v) for v in value)
    if isinstance(value, (str, bytes, int, float, bool)) or value is None:
        return sys.getsizeof(value)
    return sys.getsizeof(value) + 64


@dataclass(frozen=True, slots=True)
class EntitySample:
    """Immutable primitive sample for one stable per-spawn entity ID."""
    entity_id: str
    kind: str
    pos: tuple[float, float, float]
    vel: tuple[float, float, float] | None = None
    rot: tuple[float, float, float, float] | None = None
    ang_vel: tuple[float, float, float] | None = None
    state: str | None = None
    ai_state: str | None = None
    extra: FrozenMap = field(default_factory=lambda: FrozenMap(()))

    def __post_init__(self):
        if not isinstance(self.entity_id, str) or not self.entity_id.strip():
            raise ValueError("entity_id must be a stable non-empty string")
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("kind must be a non-empty string")
        pos = _vector(self.pos, 3, "pos")
        if pos is None:
            raise ValueError("pos is required for each entity sample")
        object.__setattr__(self, "pos", pos)
        object.__setattr__(self, "vel", _vector(self.vel, 3, "vel"))
        object.__setattr__(self, "rot", _vector(self.rot, 4, "rot"))
        object.__setattr__(self, "ang_vel", _vector(self.ang_vel, 3, "ang_vel"))
        for name in ("state", "ai_state"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or None")
        extra = self.extra
        if not isinstance(extra, FrozenMap):
            extra = _mapping(extra)
        collisions = _RESERVED_SAMPLE_KEYS.intersection(key for key, _ in extra.items)
        if collisions:
            raise ValueError(f"extra sample fields override reserved fields: {sorted(collisions)}")
        object.__setattr__(self, "extra", extra)

    @property
    def estimated_bytes(self) -> int:
        return (384 + sys.getsizeof(self.entity_id) + sys.getsizeof(self.kind)
                + sys.getsizeof(self.pos) + sum(sys.getsizeof(v) for v in self.pos)
                + (sys.getsizeof(self.vel) + sum(sys.getsizeof(v) for v in self.vel) if self.vel else 0)
                + (sys.getsizeof(self.rot) + sum(sys.getsizeof(v) for v in self.rot) if self.rot else 0)
                + (sys.getsizeof(self.ang_vel) + sum(sys.getsizeof(v) for v in self.ang_vel) if self.ang_vel else 0)
                + (sys.getsizeof(self.state) if self.state is not None else 0)
                + (sys.getsizeof(self.ai_state) if self.ai_state is not None else 0)
                + _estimate(self.extra))

    def to_record(self) -> dict[str, Any]:
        row: dict[str, Any] = {"id": self.entity_id, "kind": self.kind, "pos": list(self.pos)}
        for key in ("vel", "rot", "ang_vel"):
            value = getattr(self, key)
            if value is not None:
                row[key] = list(value)
        for key in ("state", "ai_state"):
            value = getattr(self, key)
            if value is not None:
                row[key] = value
        row.update(_thaw_json(self.extra))
        return row


@dataclass(frozen=True, slots=True)
class FrameSnapshot:
    """Copied immutable frame; no Unity/game object references are retained."""
    step: int
    t: float
    phase: str
    samples: tuple[EntitySample, ...]
    fixed_delta_time: float | None = None

    def __post_init__(self):
        if isinstance(self.step, bool) or not isinstance(self.step, int) or self.step < 0:
            raise ValueError("step must be a non-negative integer")
        object.__setattr__(self, "t", _finite(self.t, "t"))
        if not isinstance(self.phase, str) or not self.phase:
            raise ValueError("phase must be a non-empty string")
        samples = tuple(self.samples)
        if any(not isinstance(item, EntitySample) for item in samples):
            raise TypeError("samples must contain only EntitySample values")
        ids = [item.entity_id for item in samples]
        if len(ids) != len(set(ids)):
            raise ValueError("a frame cannot contain duplicate entity IDs")
        if self.fixed_delta_time is not None:
            dt = _finite(self.fixed_delta_time, "fixed_delta_time")
            if dt <= 0:
                raise ValueError("fixed_delta_time must be positive")
            object.__setattr__(self, "fixed_delta_time", dt)
        object.__setattr__(self, "samples", samples)

    @property
    def estimated_bytes(self) -> int:
        return 384 + sys.getsizeof(self.samples) + sum(sample.estimated_bytes for sample in self.samples)

    def to_record(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "type": "frame", "step": self.step, "t": self.t,
            "phase": self.phase, "samples": [sample.to_record() for sample in self.samples],
        }
        if self.fixed_delta_time is not None:
            row["fixed_delta_time"] = self.fixed_delta_time
        return row


@dataclass(frozen=True, slots=True)
class RecorderEvent:
    """Structured flight event; optional replay fields remain genuinely optional."""
    name: str
    t: float
    entity_id: str | None = None
    step: int | None = None
    actor: str | None = None
    ids: tuple[str, ...] = ()
    correlation_id: str | None = None
    decision_id: str | None = None
    evidence: str | None = None
    fields: FrozenMap = field(default_factory=lambda: FrozenMap(()))

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("event name must be a non-empty string")
        object.__setattr__(self, "t", _finite(self.t, "event.t"))
        if self.step is not None and (isinstance(self.step, bool) or not isinstance(self.step, int) or self.step < 0):
            raise ValueError("event step must be a non-negative integer or None")
        for name in ("entity_id", "actor", "correlation_id", "decision_id", "evidence"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or None")
        if isinstance(self.ids, (str, bytes)):
            raise TypeError("event ids must be a sequence of IDs, not a string")
        ids = tuple(self.ids)
        if any(not isinstance(value, str) or not value for value in ids):
            raise ValueError("event ids must be non-empty strings")
        object.__setattr__(self, "ids", ids)
        fields = self.fields if isinstance(self.fields, FrozenMap) else _mapping(self.fields)
        collisions = _RESERVED_EVENT_KEYS.intersection(key for key, _ in fields.items)
        if collisions:
            raise ValueError(f"event fields override reserved fields: {sorted(collisions)}")
        object.__setattr__(self, "fields", fields)

    @property
    def estimated_bytes(self) -> int:
        text = (self.name, self.entity_id, self.actor, self.correlation_id,
                self.decision_id, self.evidence)
        return 384 + sum(sys.getsizeof(value) for value in text if value is not None) + _estimate(self.fields) + _estimate(self.ids)

    def to_record(self) -> dict[str, Any]:
        row: dict[str, Any] = {"type": "event", "event": self.name, "t": self.t}
        optional = {
            "step": self.step, "id": self.entity_id, "actor": self.actor,
            "ids": list(self.ids) if self.ids else None,
            "correlation_id": self.correlation_id, "decision_id": self.decision_id,
            "evidence": self.evidence,
        }
        row.update({key: value for key, value in optional.items() if value is not None})
        row.update(_thaw_json(self.fields))
        return row


@dataclass(frozen=True, slots=True)
class EntityLifecycleRecord:
    action: str
    entity_id: str
    kind: str
    t: float
    step: int | None = None
    evidence: str = "observed"

    def __post_init__(self):
        if self.action not in {"spawn", "despawn"}:
            raise ValueError("lifecycle action must be spawn or despawn")
        if not self.entity_id or not self.kind:
            raise ValueError("lifecycle requires an entity ID and kind")
        if not isinstance(self.evidence, str) or not self.evidence:
            raise ValueError("lifecycle evidence must be a non-empty string")
        object.__setattr__(self, "t", _finite(self.t, "lifecycle.t"))
        if self.step is not None and (isinstance(self.step, bool) or not isinstance(self.step, int) or self.step < 0):
            raise ValueError("lifecycle step must be a non-negative integer or None")

    @property
    def estimated_bytes(self) -> int:
        return 384 + sys.getsizeof(self.entity_id) + sys.getsizeof(self.kind) + sys.getsizeof(self.action)

    def to_record(self) -> dict[str, Any]:
        row = {"type": "entity", "id": self.entity_id, "kind": self.kind,
               "action": self.action, "t": self.t, "evidence": self.evidence}
        if self.step is not None:
            row["step"] = self.step
        return row


class StableEntityRegistry:
    """Assign monotonically generated IDs so reused source handles never collide."""
    def __init__(self):
        self._lock = threading.Lock()
        self._generation: dict[tuple[str, str], int] = {}
        self._active: dict[str, tuple[str, str]] = {}
        self._anonymous = 0

    def spawn(self, kind: str, source_id: str | int | None, t: float,
              step: int | None = None) -> tuple[str, EntityLifecycleRecord]:
        if not isinstance(kind, str) or not kind:
            raise ValueError("kind must be a non-empty string")
        with self._lock:
            if source_id is None:
                self._anonymous += 1
                source = f"anonymous-{self._anonymous}"
            else:
                source = str(source_id)
            key = (kind, source)
            generation = self._generation.get(key, 0) + 1
            entity_id = f"{kind}:{quote(source, safe='._-')}:{generation}"
            if entity_id in self._active:
                raise WriterError(f"duplicate live entity identity: {entity_id}")
            self._generation[key] = generation
            self._active[entity_id] = key
        return entity_id, EntityLifecycleRecord("spawn", entity_id, kind, t, step)

    def despawn(self, entity_id: str, t: float, step: int | None = None) -> EntityLifecycleRecord:
        with self._lock:
            key = self._active.pop(entity_id, None)
            if key is None:
                raise KeyError(f"entity is not active: {entity_id}")
        return EntityLifecycleRecord("despawn", entity_id, key[0], t, step)

    def active_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._active))


@dataclass(slots=True)
class _QueueItem:
    sequence: int
    record: FrameSnapshot | RecorderEvent | EntityLifecycleRecord
    estimated_bytes: int
    category: str


@dataclass(slots=True)
class _GapNotice:
    sequence: int
    first_step: int | None
    last_step: int | None
    frames: int
    samples: int | None
    reason: str

    def to_record(self) -> dict[str, Any]:
        known_samples = self.samples is not None
        row = {
            "type": "gap",
            "count": self.samples if known_samples else self.frames,
            "unit": "entity_samples" if known_samples else "frames",
            "dropped_frames": self.frames,
            "dropped_entity_samples": self.samples,
            "reason": self.reason,
        }
        if self.first_step is not None and self.last_step is not None:
            row["first_step"] = self.first_step
            row["last_step"] = self.last_step
        return row


class FlightRecorderWriter:
    """Bounded producer/worker writer for immutable snapshots and events.

    Frame queue submission is non-blocking and becomes an explicit ``gap``
    record when capacity is unavailable. If the bounded gap ledger is full,
    the caller waits only for its accounting timeout and receives an error if
    the loss still cannot be recorded. Events block for a bounded timeout and
    raise if they cannot be accepted. Unity/game objects are never accepted.
    """
    def __init__(self, output_dir: str | Path, *, run_id: str | None = None,
                 capture_tier: str = "runtime_independent_writer",
                 metadata: Mapping[str, Any] | None = None,
                 queue_capacity: int = 256, max_queue_bytes: int = 64 * 1024 * 1024,
                 control_queue_reserve_slots: int | None = None,
                 control_queue_reserve_bytes: int | None = None,
                 chunk_target_bytes: int = 8 * 1024 * 1024,
                 max_storage_bytes: int = 1024 * 1024 * 1024,
                 control_reserve_bytes: int = 256 * 1024,
                 max_chunks: int = 128, max_gap_ranges: int = 1024,
                 event_timeout: float = 5.0, checkpoint_interval: float = 1.0):
        self.output_dir = Path(output_dir)
        if self.output_dir.exists() and any(self.output_dir.iterdir()):
            raise FileExistsError(f"output directory must be new or empty: {self.output_dir}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for name, value, low in (("queue_capacity", queue_capacity, 1),
                                 ("max_queue_bytes", max_queue_bytes, 1024),
                                 ("chunk_target_bytes", chunk_target_bytes, 512),
                                 ("max_storage_bytes", max_storage_bytes, 4096),
                                 ("control_reserve_bytes", control_reserve_bytes, 1024),
                                 ("max_chunks", max_chunks, 2),
                                 ("max_gap_ranges", max_gap_ranges, 1)):
            if isinstance(value, bool) or not isinstance(value, int) or value < low:
                raise ValueError(f"{name} must be an integer >= {low}")
        if control_reserve_bytes >= max_storage_bytes // 2:
            raise ValueError("control reserve must be less than half the storage limit")
        if control_queue_reserve_slots is None:
            control_queue_reserve_slots = min(16, queue_capacity // 8)
        if control_queue_reserve_bytes is None:
            control_queue_reserve_bytes = min(256 * 1024, max_queue_bytes // 8)
        if (isinstance(control_queue_reserve_slots, bool) or not isinstance(control_queue_reserve_slots, int)
                or not 0 <= control_queue_reserve_slots < queue_capacity):
            raise ValueError("control_queue_reserve_slots must be in [0, queue_capacity)")
        if (isinstance(control_queue_reserve_bytes, bool) or not isinstance(control_queue_reserve_bytes, int)
                or not 0 <= control_queue_reserve_bytes < max_queue_bytes):
            raise ValueError("control_queue_reserve_bytes must be in [0, max_queue_bytes)")
        if chunk_target_bytes > max_storage_bytes - control_reserve_bytes:
            raise ValueError("chunk target exceeds available storage payload budget")
        self.queue_capacity = queue_capacity
        self.max_queue_bytes = max_queue_bytes
        self.control_queue_reserve_slots = control_queue_reserve_slots
        self.control_queue_reserve_bytes = control_queue_reserve_bytes
        self.chunk_target_bytes = chunk_target_bytes
        self.max_storage_bytes = max_storage_bytes
        self.control_reserve_bytes = control_reserve_bytes
        self.max_chunks = max_chunks
        self.max_gap_ranges = max_gap_ranges
        self.event_timeout = float(event_timeout)
        self.checkpoint_interval = float(checkpoint_interval)
        if not math.isfinite(self.event_timeout) or self.event_timeout < 0:
            raise ValueError("event_timeout must be finite and non-negative")
        if not math.isfinite(self.checkpoint_interval) or self.checkpoint_interval < 0.1:
            raise ValueError("checkpoint_interval must be finite and at least 0.1 seconds")
        self.run_id = run_id or uuid.uuid4().hex
        self.capture_tier = capture_tier
        if not isinstance(capture_tier, str) or not capture_tier:
            raise ValueError("capture_tier must be a non-empty string")
        frozen_meta = _thaw_json(_freeze_json(metadata or {}))
        for reserved in ("schema_version", "run_id", "capture_tier", "capture_complete", "writer_limits"):
            if reserved in frozen_meta:
                raise ValueError(f"metadata cannot override {reserved}")
        now = datetime.now(timezone.utc).isoformat()
        self._metadata: dict[str, Any] = {
            **frozen_meta, "schema_version": SCHEMA, "run_id": self.run_id,
            "capture_tier": capture_tier, "capture_complete": False,
            "sample_phase_verified": False, "writer_core_version": WRITER_VERSION,
            "started_at_utc": now,
            "writer_limits": {
                "queue_capacity": queue_capacity, "max_queue_bytes": max_queue_bytes,
                "control_queue_reserve_slots": control_queue_reserve_slots,
                "control_queue_reserve_bytes": control_queue_reserve_bytes,
                "chunk_target_bytes": chunk_target_bytes, "max_storage_bytes": max_storage_bytes,
                "control_reserve_bytes": control_reserve_bytes, "max_chunks": max_chunks,
                "max_gap_ranges": max_gap_ranges,
            },
        }
        initial_metadata_bytes = len(json.dumps(self._metadata, ensure_ascii=False, sort_keys=True,
                                                indent=2, allow_nan=False).encode("utf-8"))
        reserve_floor = 16 * 1024 + max_chunks * 512 + initial_metadata_bytes * 2
        if control_reserve_bytes < reserve_floor:
            raise ValueError(f"control_reserve_bytes must be >= {reserve_floor} for metadata and {max_chunks} chunks")
        self._manifest: dict[str, Any] = {"manifest_schema": MANIFEST_SCHEMA, "chunks": []}
        self._lock = threading.Condition()
        self._queue: deque[_QueueItem] = deque()
        self._queued_bytes = 0
        self._pending_gaps: deque[_GapNotice] = deque()
        self._next_sequence = 0
        self._last_submitted_step: int | None = None
        self._accepting = True
        self._closing = False
        self._storage_exhausted = False
        self._storage_reason: str | None = None
        self._worker_error: BaseException | None = None
        self._thread = threading.Thread(target=self._worker, name="flight-recorder-writer", daemon=True)
        self._stats: dict[str, Any] = {
            "enqueued_frames": 0, "written_frames": 0, "enqueued_events": 0,
            "written_events": 0, "written_lifecycle_records": 0,
            "queue_dropped_frames": 0, "queue_dropped_entity_samples": 0,
            "oversized_queue_frames": 0,
            "source_missing_frames": 0, "storage_dropped_frames": 0,
            "storage_dropped_entity_samples": 0, "rejected_events": 0,
            "rejected_event_names": [], "max_queue_depth": 0,
            "max_queue_bytes": 0, "chunks": 0, "chunk_bytes": 0,
            "writer_seconds": 0.0, "fatal_error": None,
        }
        self._chunk_file = None
        self._chunk_partial: Path | None = None
        self._chunk_index = 0
        self._chunk_bytes = 0
        self._chunk_frames = 0
        self._chunk_first_step: int | None = None
        self._chunk_last_step: int | None = None
        self._chunk_hash = hashlib.sha256()
        self._payload_bytes = 0
        self._last_store_failure: str | None = None
        self._final_state_persisted = False
        self._last_checkpoint = time.monotonic()
        self._storage_losses: list[_GapNotice] = []
        self._write_json_atomic(self.output_dir / "metadata.json", self._metadata)
        self._write_json_atomic(self.output_dir / "chunk_manifest.json", self._manifest)
        self._write_state_atomic()
        self._thread.start()

    def __enter__(self) -> "FlightRecorderWriter":
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _write_json_atomic(self, path: Path, value: Any) -> None:
        temp = path.with_name(path.name + ".tmp")
        payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                              allow_nan=False) + "\n").encode("utf-8")
        if self._logical_directory_bytes() + len(payload) > self.max_storage_bytes:
            raise RecorderStorageLimitError(f"control file exceeds configured storage limit: {path.name}")
        with open(temp, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)

    def _logical_directory_bytes(self) -> int:
        """Count persisted bytes plus buffered chunk bytes in the current run."""
        total = 0
        for path in self.output_dir.iterdir():
            if path.is_file():
                try:
                    total += path.stat().st_size
                except FileNotFoundError:
                    pass
        if self._chunk_file is not None and self._chunk_partial is not None:
            try:
                persisted = self._chunk_partial.stat().st_size
            except FileNotFoundError:
                persisted = 0
            total += max(0, self._chunk_bytes - persisted)
        return total

    def _write_state_atomic(self) -> None:
        with self._lock:
            state = {
                "run_id": self.run_id,
                "last_submitted_step": self._last_submitted_step,
                "last_durable_step": self._chunk_last_step,
                "is_final": self._final_state_persisted,
                "accepted_frames": self._stats["enqueued_frames"],
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        self._write_json_atomic(self.output_dir / "writer_state.json", state)

    def _checkpoint_durable(self) -> None:
        """Flush a partial chunk before advertising its last durable step."""
        if self._chunk_file is not None:
            self._chunk_file.flush()
            os.fsync(self._chunk_file.fileno())
        self._write_state_atomic()

    def _check_worker(self) -> None:
        if self._worker_error is not None:
            raise WriterError(f"flight writer worker failed: {self._worker_error}") from self._worker_error
        if not self._accepting:
            raise WriterError("flight recorder is closed")

    def _next_seq(self) -> int:
        self._next_sequence += 1
        return self._next_sequence

    def _queue_fits(self, estimated_bytes: int, *, control: bool = False) -> bool:
        slot_limit = self.queue_capacity if control else self.queue_capacity - self.control_queue_reserve_slots
        byte_limit = self.max_queue_bytes if control else self.max_queue_bytes - self.control_queue_reserve_bytes
        return (len(self._queue) < slot_limit
                and self._queued_bytes + estimated_bytes + 128 <= byte_limit)

    def _append_item(self, record, estimated_bytes: int, category: str) -> int:
        sequence = self._next_seq()
        accounted_bytes = estimated_bytes + 128  # queue node and item object overhead
        self._queue.append(_QueueItem(sequence, record, accounted_bytes, category))
        self._queued_bytes += accounted_bytes
        self._stats["max_queue_depth"] = max(self._stats["max_queue_depth"], len(self._queue))
        self._stats["max_queue_bytes"] = max(self._stats["max_queue_bytes"], self._queued_bytes)
        self._lock.notify_all()
        return sequence

    def _add_gap_notice(self, notice: _GapNotice, timeout: float | None = None) -> None:
        deadline = time.monotonic() + (self.event_timeout if timeout is None else timeout)
        while True:
            if self._pending_gaps:
                last = self._pending_gaps[-1]
                if (last.reason == notice.reason and last.sequence + 1 == notice.sequence
                        and last.first_step is not None and last.last_step is not None
                        and last.last_step + 1 == notice.first_step
                        and notice.first_step is not None and notice.last_step is not None
                        and (last.samples is None) == (notice.samples is None)):
                    last.sequence = notice.sequence
                    last.last_step = notice.last_step
                    last.frames += notice.frames
                    if last.samples is not None:
                        last.samples += notice.samples
                    self._lock.notify_all()
                    return
            if len(self._pending_gaps) < self.max_gap_ranges:
                self._pending_gaps.append(notice)
                self._lock.notify_all()
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RecorderOverloadError("bounded gap ledger is full; retain and retry this observation")
            self._lock.wait(remaining)
            self._check_worker()

    def submit_frame(self, frame: FrameSnapshot, *, accounting_timeout: float | None = None) -> str:
        if not isinstance(frame, FrameSnapshot):
            raise TypeError("submit_frame accepts a copied FrameSnapshot, not a Unity/game object")
        estimate = frame.estimated_bytes
        with self._lock:
            self._check_worker()
            if self._last_submitted_step is not None and frame.step <= self._last_submitted_step:
                raise ValueError(f"frame steps must increase: {frame.step} <= {self._last_submitted_step}")
            prior_step = self._last_submitted_step
            if self._storage_exhausted:
                seq = self._next_seq()
                self._record_storage_loss(seq, frame, self._storage_reason or "storage_limit")
                self._last_submitted_step = frame.step
                self._stats["storage_dropped_frames"] += 1
                self._stats["storage_dropped_entity_samples"] += len(frame.samples)
                return "storage_limit"
            source_gap = None
            if prior_step is not None and frame.step > prior_step + 1:
                missing = frame.step - prior_step - 1
                source_gap = _GapNotice(self._next_sequence + 1, prior_step + 1, frame.step - 1,
                                        missing, None, "source_step_gap")
            queue_fits = self._queue_fits(estimate)
            too_large = estimate + 128 > self.max_queue_bytes
            if source_gap is not None and not queue_fits:
                seq = self._next_seq()
                reason = ("source_step_gap_and_frame_exceeds_queue_limit" if too_large
                          else "source_step_gap_and_queue_saturated")
                notice = _GapNotice(seq, source_gap.first_step, frame.step, source_gap.frames + 1,
                                    None, reason)
                self._add_gap_notice(notice, accounting_timeout)
                self._last_submitted_step = frame.step
                self._stats["source_missing_frames"] += source_gap.frames
                self._stats["queue_dropped_frames"] += 1
                self._stats["queue_dropped_entity_samples"] += len(frame.samples)
                if too_large:
                    self._stats["oversized_queue_frames"] += 1
                    return "frame_exceeds_queue_limit"
                return "queue_saturated"
            if source_gap is not None:
                source_gap.sequence = self._next_seq()
                self._add_gap_notice(source_gap, accounting_timeout)
                self._stats["source_missing_frames"] += source_gap.frames
            if not queue_fits:
                seq = self._next_seq()
                reason = "frame_exceeds_queue_limit" if too_large else "queue_saturated"
                notice = _GapNotice(seq, frame.step, frame.step, 1, len(frame.samples), reason)
                self._add_gap_notice(notice, accounting_timeout)
                self._last_submitted_step = frame.step
                self._stats["queue_dropped_frames"] += 1
                self._stats["queue_dropped_entity_samples"] += len(frame.samples)
                if too_large:
                    self._stats["oversized_queue_frames"] += 1
                    return "frame_exceeds_queue_limit"
                return "queue_saturated"
            self._append_item(frame, estimate, "frame")
            self._last_submitted_step = frame.step
            self._stats["enqueued_frames"] += 1
            return "accepted"

    def _submit_control(self, record: RecorderEvent | EntityLifecycleRecord,
                        category: str, timeout: float | None = None) -> None:
        estimate = record.estimated_bytes
        if estimate + 128 > self.max_queue_bytes:
            with self._lock:
                self._check_worker()
                self._stats["rejected_events"] += 1
                event_name = record.name if isinstance(record, RecorderEvent) else record.action
                names = self._stats["rejected_event_names"]
                if len(names) < 128:
                    names.append(event_name[:128])
            raise RecorderOverloadError("control record exceeds max_queue_bytes; it was not accepted")
        wait_for = self.event_timeout if timeout is None else max(0.0, timeout)
        deadline = time.monotonic() + wait_for
        with self._lock:
            self._check_worker()
            if self._storage_exhausted:
                self._stats["rejected_events"] += 1
                event_name = record.name if isinstance(record, RecorderEvent) else record.action
                names = self._stats["rejected_event_names"]
                if len(names) < 128:
                    names.append(event_name[:128])
                raise RecorderStorageLimitError("control record not accepted after storage limit")
            while not self._queue_fits(estimate, control=True):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._stats["rejected_events"] += 1
                    event_name = record.name if isinstance(record, RecorderEvent) else record.action
                    names = self._stats["rejected_event_names"]
                    if len(names) < 128:
                        names.append(event_name[:128])
                    raise RecorderOverloadError("event queue remained full; event was not accepted")
                self._lock.wait(remaining)
                self._check_worker()
                if self._storage_exhausted:
                    self._stats["rejected_events"] += 1
                    event_name = record.name if isinstance(record, RecorderEvent) else record.action
                    names = self._stats["rejected_event_names"]
                    if len(names) < 128:
                        names.append(event_name[:128])
                    raise RecorderStorageLimitError("control record not accepted after storage limit")
            self._append_item(record, estimate, category)
            if category == "event":
                self._stats["enqueued_events"] += 1

    def submit_event(self, event: RecorderEvent, *, timeout: float | None = None) -> None:
        if not isinstance(event, RecorderEvent):
            raise TypeError("submit_event accepts a structured RecorderEvent")
        self._submit_control(event, "event", timeout)

    def submit_lifecycle(self, event: EntityLifecycleRecord, *, timeout: float | None = None) -> None:
        if not isinstance(event, EntityLifecycleRecord):
            raise TypeError("submit_lifecycle accepts an EntityLifecycleRecord")
        self._submit_control(event, "lifecycle", timeout)

    def _record_storage_loss(self, sequence: int, frame: FrameSnapshot, reason: str = "storage_limit") -> None:
        self._accumulate_storage_loss(_GapNotice(sequence, frame.step, frame.step, 1,
                                                 len(frame.samples), reason))

    def _accumulate_storage_loss(self, notice: _GapNotice) -> None:
        for loss in reversed(self._storage_losses):
            if (loss.reason == notice.reason and loss.first_step is not None and loss.last_step is not None
                    and notice.first_step is not None and notice.last_step is not None
                    and loss.last_step + 1 == notice.first_step
                    and (loss.samples is None) == (notice.samples is None)):
                loss.sequence = min(loss.sequence, notice.sequence)
                loss.last_step = notice.last_step
                loss.frames += notice.frames
                if loss.samples is not None:
                    loss.samples += notice.samples
                return
        if len(self._storage_losses) < self.max_gap_ranges:
            self._storage_losses.append(notice)
            return

        # Preserve exact totals under the bounded ledger, but discard step bounds
        # rather than imply that unobserved steps between disjoint losses were lost.
        all_notices = [*self._storage_losses, notice]
        reasons = {item.reason for item in all_notices}
        total_samples = (sum(item.samples for item in all_notices)
                         if all(item.samples is not None for item in all_notices) else None)
        total_frames = sum(item.frames for item in all_notices)
        sequence = min(item.sequence for item in all_notices)
        reason = next(iter(reasons)) if len(reasons) == 1 else "multiple_loss_reasons_unlocated"
        if len(reasons) == 1:
            reason = f"{reason}_ranges_unlocated"
        self._storage_losses[:] = [_GapNotice(sequence, None, None, total_frames, total_samples, reason)]

    def _open_chunk(self, *, emergency: bool = False) -> bool:
        chunk_limit = self.max_chunks if emergency else self.max_chunks - 1
        if self._chunk_index >= chunk_limit:
            self._storage_reason = "chunk_count_limit"
            return False
        self._chunk_index += 1
        self._chunk_partial = self.output_dir / f"chunk-{self._chunk_index:06d}.jsonl.partial"
        self._chunk_file = open(self._chunk_partial, "xb", buffering=1024 * 1024)
        self._chunk_bytes = 0
        self._chunk_frames = 0
        self._chunk_first_step = None
        self._chunk_last_step = None
        self._chunk_hash = hashlib.sha256()
        return True

    def _finalize_chunk(self) -> None:
        if self._chunk_file is None or self._chunk_partial is None or self._chunk_bytes == 0:
            if self._chunk_file is not None:
                self._chunk_file.close()
                self._chunk_file = None
            if self._chunk_partial is not None and self._chunk_partial.exists():
                self._chunk_partial.unlink()
            self._chunk_partial = None
            return
        self._chunk_file.flush()
        os.fsync(self._chunk_file.fileno())
        self._chunk_file.close()
        self._chunk_file = None
        final = self.output_dir / f"chunk-{self._chunk_index:06d}.jsonl"
        os.replace(self._chunk_partial, final)
        entry: dict[str, Any] = {
            "file": final.name, "bytes": self._chunk_bytes,
            "sha256": self._chunk_hash.hexdigest(), "frame_count": self._chunk_frames,
        }
        if self._chunk_first_step is not None:
            entry["first_step"] = self._chunk_first_step
            entry["last_step"] = self._chunk_last_step
        self._manifest["chunks"].append(entry)
        self._write_json_atomic(self.output_dir / "chunk_manifest.json", self._manifest)
        self._stats["chunks"] = len(self._manifest["chunks"])
        self._stats["chunk_bytes"] = self._payload_bytes
        self._chunk_partial = None
        self._write_state_atomic()

    def _store_record(self, record: dict[str, Any], *, emergency: bool = False) -> bool:
        self._last_store_failure = None
        try:
            line = (json.dumps(record, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        except (TypeError, ValueError) as err:
            raise WriterError(f"record cannot be serialized: {err}") from err
        if len(line) > self.chunk_target_bytes:
            self._last_store_failure = "record_exceeds_chunk_target"
            return False
        used = self._logical_directory_bytes()
        normal_limit = self.max_storage_bytes - self.control_reserve_bytes
        emergency_limit = self.max_storage_bytes - max(1024, self.control_reserve_bytes // 2)
        if not emergency and used + len(line) > normal_limit:
            self._last_store_failure = "storage_limit"
            return False
        if emergency and used + len(line) > emergency_limit:
            self._last_store_failure = "storage_limit"
            return False
        if self._chunk_file is not None and self._chunk_bytes and self._chunk_bytes + len(line) > self.chunk_target_bytes:
            self._finalize_chunk()
        if self._chunk_file is None and not self._open_chunk(emergency=emergency):
            self._last_store_failure = self._storage_reason or "chunk_count_limit"
            return False
        self._chunk_file.write(line)
        self._chunk_hash.update(line)
        self._chunk_bytes += len(line)
        self._payload_bytes += len(line)
        if record.get("type") == "frame":
            self._chunk_frames += 1
            step = record["step"]
            self._chunk_first_step = step if self._chunk_first_step is None else min(self._chunk_first_step, step)
            self._chunk_last_step = step if self._chunk_last_step is None else max(self._chunk_last_step, step)
            self._stats["written_frames"] += 1
        elif record.get("type") == "event":
            self._stats["written_events"] += 1
        elif record.get("type") == "entity":
            self._stats["written_lifecycle_records"] += 1
        return True

    def _gap_record(self, notice: _GapNotice) -> dict[str, Any]:
        return {"t": None, **notice.to_record()}

    def _classify_storage_failure(self, item: _QueueItem) -> None:
        reason = self._last_store_failure or "storage_limit"
        if reason == "record_exceeds_chunk_target":
            if isinstance(item.record, FrameSnapshot):
                with self._lock:
                    self._record_storage_loss(item.sequence, item.record, reason)
                    self._stats["storage_dropped_frames"] += 1
                    self._stats["storage_dropped_entity_samples"] += len(item.record.samples)
                    self._lock.notify_all()
            else:
                with self._lock:
                    self._stats["rejected_events"] += 1
                    event_name = item.record.name if isinstance(item.record, RecorderEvent) else item.record.action
                    if len(self._stats["rejected_event_names"]) < 128:
                        self._stats["rejected_event_names"].append(event_name[:128])
                    self._lock.notify_all()
            return
        if isinstance(item.record, FrameSnapshot):
            with self._lock:
                self._storage_exhausted = True
                self._storage_reason = self._storage_reason or reason
                self._record_storage_loss(item.sequence, item.record, reason)
                self._stats["storage_dropped_frames"] += 1
                self._stats["storage_dropped_entity_samples"] += len(item.record.samples)
                self._lock.notify_all()
        else:
            with self._lock:
                self._storage_exhausted = True
                self._storage_reason = self._storage_reason or reason
                self._stats["rejected_events"] += 1
                names = self._stats["rejected_event_names"]
                event_name = item.record.name if isinstance(item.record, RecorderEvent) else item.record.action
                if len(names) < 128:
                    names.append(event_name[:128])
                self._lock.notify_all()

    def _persist_gap(self, notice: _GapNotice) -> None:
        start = time.monotonic()
        if self._storage_exhausted or not self._store_record(self._gap_record(notice)):
            with self._lock:
                self._storage_exhausted = True
                self._storage_reason = self._storage_reason or "storage_limit"
                self._accumulate_storage_loss(notice)
                self._lock.notify_all()
        self._stats["writer_seconds"] += time.monotonic() - start

    def _persist_item(self, item: _QueueItem) -> None:
        start = time.monotonic()
        if self._storage_exhausted:
            self._classify_storage_failure(item)
        else:
            try:
                record = item.record.to_record()
                if not self._store_record(record):
                    self._classify_storage_failure(item)
            except BaseException:
                raise
        self._stats["writer_seconds"] += time.monotonic() - start

    def _take_next(self) -> tuple[str, _QueueItem | _GapNotice] | None:
        with self._lock:
            while True:
                gap_before_queue = bool(
                    self._pending_gaps
                    and (not self._queue or self._pending_gaps[0].sequence < self._queue[0].sequence)
                )
                if gap_before_queue:
                    notice = self._pending_gaps.popleft()
                    self._lock.notify_all()
                    return ("gap", notice)
                if self._queue:
                    item = self._queue.popleft()
                    self._queued_bytes -= item.estimated_bytes
                    self._lock.notify_all()
                    return ("item", item)
                if self._pending_gaps:
                    notice = self._pending_gaps.popleft()
                    self._lock.notify_all()
                    return ("gap", notice)
                if self._closing:
                    return None
                self._lock.wait(timeout=0.1)

    def _worker(self) -> None:
        try:
            while True:
                next_item = self._take_next()
                if next_item is None:
                    break
                category, item = next_item
                if category == "gap":
                    self._persist_gap(item)
                else:
                    self._persist_item(item)
                if time.monotonic() - self._last_checkpoint >= self.checkpoint_interval:
                    self._last_checkpoint = time.monotonic()
                    self._checkpoint_durable()
            for loss in self._storage_losses:
                if not self._store_record(self._gap_record(loss), emergency=True):
                    raise WriterError("control reserve could not fit final loss-accounting gap")
            self._finalize_chunk()
            self._metadata.update({
                "capture_complete": not self._storage_exhausted
                    and self._stats["queue_dropped_frames"] == 0
                    and self._stats["source_missing_frames"] == 0
                    and self._stats["storage_dropped_frames"] == 0
                    and self._stats["rejected_events"] == 0,
                "stopped_at_utc": datetime.now(timezone.utc).isoformat(),
                "stop_reason": self._storage_reason or "graceful_stop",
                "writer_stats": self.stats(),
            })
            self._write_json_atomic(self.output_dir / "metadata.json", self._metadata)
            self._final_state_persisted = True
            self._write_state_atomic()
        except BaseException as err:
            with self._lock:
                self._worker_error = err
                self._stats["fatal_error"] = f"{type(err).__name__}: {err}"
                self._accepting = False
                self._closing = True
                self._lock.notify_all()
            try:
                self._finalize_chunk()
                self._metadata.update({"capture_complete": False,
                                       "stop_reason": "writer_error",
                                       "writer_error": self._stats["fatal_error"],
                                       "writer_stats": self.stats()})
                self._write_json_atomic(self.output_dir / "metadata.json", self._metadata)
            except BaseException:
                pass

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {**self._stats, "queue_depth": len(self._queue),
                    "queue_bytes": self._queued_bytes,
                    "pending_gap_ranges": len(self._pending_gaps),
                    "storage_exhausted": self._storage_exhausted,
                    "max_storage_bytes": self.max_storage_bytes,
                    "control_queue_reserve_slots": self.control_queue_reserve_slots,
                    "control_queue_reserve_bytes": self.control_queue_reserve_bytes,
                    "payload_bytes": self._payload_bytes}

    def close(self, timeout: float | None = 30.0) -> dict[str, Any]:
        with self._lock:
            if not self._closing:
                self._accepting = False
                self._closing = True
                self._lock.notify_all()
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise TimeoutError("flight writer did not stop before close timeout")
        if self._worker_error is not None:
            raise WriterError(f"flight writer failed: {self._worker_error}") from self._worker_error
        return self.stats()


def _read_record_lines(payload: bytes) -> tuple[list[bytes], list[dict[str, Any]]]:
    """Return complete valid JSONL lines and recovery diagnostics."""
    valid: list[bytes] = []
    problems: list[dict[str, Any]] = []
    lines = payload.splitlines(keepends=True)
    for index, raw in enumerate(lines, 1):
        complete = raw.endswith(b"\n")
        candidate = raw[:-1] if complete else raw
        if candidate.endswith(b"\r"):
            candidate = candidate[:-1]
        if not complete:
            step_match = re.search(rb'"step"\s*:\s*(\d+)', candidate)
            type_match = re.search(rb'"type"\s*:\s*"([^"]+)"', candidate)
            problems.append({"kind": "truncated_tail", "line": index,
                             "bytes": len(raw), "record_type": type_match.group(1).decode() if type_match else None,
                             "step": int(step_match.group(1)) if step_match else None})
            continue
        try:
            record = json.loads(candidate)
            if not isinstance(record, dict) or not isinstance(record.get("type"), str):
                raise ValueError("record must be an object with a string type")
        except (ValueError, TypeError, UnicodeDecodeError) as err:
            step_match = re.search(rb'"step"\s*:\s*(\d+)', candidate)
            type_match = re.search(rb'"type"\s*:\s*"([^"]+)"', candidate)
            problems.append({"kind": "invalid_complete_record", "line": index,
                             "detail": str(err), "record_type": type_match.group(1).decode() if type_match else None,
                             "step": int(step_match.group(1)) if step_match else None})
            continue
        valid.append(raw if raw.endswith(b"\n") else raw + b"\n")
    return valid, problems


def _manifest_entry(path: Path, relative: str, lines: Sequence[bytes]) -> dict[str, Any]:
    data = b"".join(lines)
    frame_steps = []
    for line in lines:
        try:
            record = json.loads(line)
        except (ValueError, TypeError):
            continue
        if record.get("type") == "frame" and isinstance(record.get("step"), int):
            frame_steps.append(record["step"])
    entry: dict[str, Any] = {"file": relative, "bytes": len(data),
                             "sha256": hashlib.sha256(data).hexdigest(),
                             "frame_count": len(frame_steps)}
    if frame_steps:
        entry["first_step"] = min(frame_steps)
        entry["last_step"] = max(frame_steps)
    return entry


def recover_run(run_dir: str | Path, *, expected_last_step: int | None = None) -> dict[str, Any]:
    """Recover complete records from partial/unindexed chunks without rewriting them.

    The source partials are renamed to ``*.recovered-source`` after salvage so
    recovery is idempotent. An unknown tail is reported as unknown, not guessed.
    """
    root = Path(run_dir)
    metadata_path = root / "metadata.json"
    if not metadata_path.is_file():
        raise RecoveryError("metadata.json is missing")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as err:
        raise RecoveryError(f"metadata.json is unreadable: {err}") from err
    if metadata.get("schema_version") != SCHEMA:
        raise RecoveryError("unsupported flight schema")
    manifest_path = root / "chunk_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("manifest_schema") != MANIFEST_SCHEMA or not isinstance(manifest.get("chunks"), list):
            raise RecoveryError("chunk manifest schema is invalid")
    else:
        manifest = {"manifest_schema": MANIFEST_SCHEMA, "chunks": []}
    indexed = {entry["file"]: entry for entry in manifest["chunks"] if isinstance(entry, dict) and isinstance(entry.get("file"), str)}
    for name in indexed:
        if Path(name).name != name or name in {".", ".."} or "\\" in name:
            raise RecoveryError(f"unsafe chunk path in manifest: {name!r}")
    report: dict[str, Any] = {
        "run_id": metadata.get("run_id"), "status": "recovered",
        "recovered_chunks": [], "recovered_records": 0,
        "recovered_frames": 0, "truncated_bytes": 0,
        "invalid_complete_records": 0, "corrupt_indexed_chunks": [],
        "unindexed_complete_chunks": [], "missing_frame_ranges": [],
        "unknown_tail_loss": False,
    }
    trusted_steps: list[int] = []
    declared_gaps: list[tuple[int, int]] = []
    for name, entry in indexed.items():
        path = root / name
        if not path.is_file():
            report["corrupt_indexed_chunks"].append({"file": name, "reason": "missing"})
            continue
        data = path.read_bytes()
        if (len(data) != entry.get("bytes") or hashlib.sha256(data).hexdigest() != entry.get("sha256")):
            report["corrupt_indexed_chunks"].append({"file": name, "reason": "size_or_hash_mismatch"})
            continue
        lines, _ = _read_record_lines(data)
        for line in lines:
            rec = json.loads(line)
            if rec.get("type") == "frame" and isinstance(rec.get("step"), int):
                trusted_steps.append(rec["step"])
            if rec.get("type") == "gap" and isinstance(rec.get("first_step"), int) and isinstance(rec.get("last_step"), int):
                declared_gaps.append((rec["first_step"], rec["last_step"]))

    partials = sorted(root.glob("chunk-*.jsonl.partial"))
    next_index = max([int(m.group(1)) for path in root.glob("chunk-*.jsonl*")
                      if (m := re.search(r"chunk-(\d+)", path.name))] or [0])
    recovered_lines: list[bytes] = []
    for partial in partials:
        payload = partial.read_bytes()
        valid, problems = _read_record_lines(payload)
        recovered_lines.extend(valid)
        report["truncated_bytes"] += sum(p["bytes"] for p in problems if p["kind"] == "truncated_tail")
        report["invalid_complete_records"] += sum(p["kind"] == "invalid_complete_record" for p in problems)
        for problem in problems:
            if problem.get("record_type") == "frame" and isinstance(problem.get("step"), int):
                report.setdefault("lost_frame_steps", []).append(problem["step"])
        report.setdefault("partial_sources", []).append(partial.name)
        archive = partial.with_name(partial.name + ".recovered-source")
        os.replace(partial, archive)
        report.setdefault("archived_sources", []).append(archive.name)

    # A crash can occur after an atomic chunk rename but before manifest update.
    for chunk in sorted(root.glob("chunk-*.jsonl")):
        relative = chunk.relative_to(root).as_posix()
        if relative in indexed:
            continue
        lines, problems = _read_record_lines(chunk.read_bytes())
        if problems or not lines:
            report["unindexed_complete_chunks"].append({"file": relative, "valid_records": len(lines), "problems": problems})
            continue
        entry = _manifest_entry(chunk, relative, lines)
        manifest["chunks"].append(entry)
        indexed[relative] = entry
        for line in lines:
            rec = json.loads(line)
            if rec.get("type") == "frame" and isinstance(rec.get("step"), int):
                trusted_steps.append(rec["step"])

    for line in recovered_lines:
        rec = json.loads(line)
        if rec.get("type") == "frame" and isinstance(rec.get("step"), int):
            trusted_steps.append(rec["step"])
            report["recovered_frames"] += 1
        report["recovered_records"] += 1

    # Account for exact missing step intervals between observed frames.
    missing: list[tuple[int, int]] = []
    observed = sorted(set(trusted_steps))
    for left, right in zip(observed, observed[1:]):
        if right > left + 1:
            first, last = left + 1, right - 1
            if not any(a <= first and b >= last for a, b in declared_gaps):
                missing.append((first, last))
    trusted_set = set(observed)
    known_lost = set(report.get("lost_frame_steps", []))
    for step in sorted(known_lost):
        if step in trusted_set or any(first <= step <= last for first, last in declared_gaps):
            continue
        if not any(first <= step <= last for first, last in missing):
            missing.append((step, step))
    state_path = root / "writer_state.json"
    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            report["unknown_tail_loss"] = True
    checkpoint_step = state.get("last_submitted_step")
    expected = expected_last_step if expected_last_step is not None else checkpoint_step
    if isinstance(expected, int) and not isinstance(expected, bool) and observed:
        if expected > observed[-1]:
            first, last = observed[-1] + 1, expected
            if not any(a <= first and b >= last for a, b in declared_gaps):
                missing.append((first, last))
        elif expected < observed[-1]:
            report["unknown_tail_loss"] = True
    elif isinstance(expected, int) and not isinstance(expected, bool):
        # A final step alone cannot reveal the beginning of a run with no surviving frames.
        report["unknown_tail_loss"] = True
    if (not metadata.get("capture_complete", False) and expected_last_step is None
            and not state.get("is_final", False)):
        # Non-final writer_state.json is a checkpoint, not the final submitted step after a crash.
        report["unknown_tail_loss"] = True

    # Coalesce overlaps from independently inferred and explicitly lost steps.
    merged_missing: list[tuple[int, int]] = []
    for first, last in sorted(missing):
        if merged_missing and first <= merged_missing[-1][1] + 1:
            merged_missing[-1] = (merged_missing[-1][0], max(merged_missing[-1][1], last))
        else:
            merged_missing.append((first, last))
    missing = merged_missing

    report["missing_frame_ranges"] = [{"first_step": first, "last_step": last,
                                       "count": last - first + 1}
                                      for first, last in missing]
    if recovered_lines or missing:
        recovery_records = list(recovered_lines)
        for first, last in missing:
            gap = {"type": "gap", "count": last - first + 1, "unit": "frames",
                   "dropped_frames": last - first + 1, "dropped_entity_samples": None,
                   "first_step": first, "last_step": last,
                   "reason": "recovery_detected_missing_steps"}
            recovery_records.append((json.dumps(gap, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        next_index += 1
        recovered_name = f"chunk-{next_index:06d}-recovered.jsonl"
        recovered_path = root / recovered_name
        payload = b"".join(recovery_records)
        with open(recovered_path, "xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        entry = _manifest_entry(recovered_path, recovered_name, recovery_records)
        manifest["chunks"].append(entry)
        report["recovered_chunks"].append(recovered_name)

    manifest["chunks"].sort(key=lambda item: item["file"])
    temp_manifest = manifest_path.with_name(manifest_path.name + ".tmp")
    temp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_manifest, manifest_path)
    metadata.update({"capture_complete": False, "recording_interrupted": True,
                     "recovery_status": report["status"]})
    temp_meta = metadata_path.with_name(metadata_path.name + ".tmp")
    temp_meta.write_text(json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_meta, metadata_path)
    (root / "recovery_report.json").write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


class RecoveryError(WriterError):
    pass
