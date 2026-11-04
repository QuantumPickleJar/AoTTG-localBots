#!/usr/bin/env python3
"""Local named-pipe bridge from immutable adapter messages to flight_writer.

The Windows pipe is local-only, rejects remote clients, and uses a DACL for
the current user. No game/Unity references cross this process boundary.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from collections import OrderedDict
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
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flight_writer import EntityLifecycleRecord, EntitySample, FlightRecorderWriter, FrameSnapshot, RecorderEvent, WriterError


PROTOCOL = "aicadets.flight.transport.v1"
FLIGHT_SCHEMA = "aicadets.flight.v1"
MAX_ENVELOPE_BYTES = 1024 * 1024
MAX_READ_BYTES = 64 * 1024
MAX_SEQUENCE = 2**63 - 1
KINDS = {"hello", "frame", "event", "lifecycle", "gap", "health", "stop"}
_PIPE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class TransportProtocolError(ValueError):
    """A malformed, oversized, or out-of-order transport message."""


def _raise_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def parse_envelope(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_ENVELOPE_BYTES:
        raise TransportProtocolError("message is empty or exceeds the 1 MiB limit")
    try:
        obj = json.loads(raw.decode("utf-8", errors="strict"),
                         object_pairs_hook=_unique_object, parse_constant=_raise_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise TransportProtocolError(f"invalid UTF-8 JSON envelope: {exc}") from exc
    if not isinstance(obj, dict):
        raise TransportProtocolError("envelope must be a JSON object")
    if set(obj) != {"protocol", "run_id", "sequence", "kind", "payload"}:
        raise TransportProtocolError("envelope members do not match transport v1")
    if obj["protocol"] != PROTOCOL:
        raise TransportProtocolError("unsupported transport protocol")
    run_id = obj["run_id"]
    if not isinstance(run_id, str):
        raise TransportProtocolError("run_id must be a UUID in N format")
    try:
        if uuid.UUID(run_id).hex != run_id.lower() or len(run_id) != 32:
            raise ValueError("not N format")
    except ValueError as exc:
        raise TransportProtocolError("run_id must be a UUID in N format") from exc
    sequence = obj["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or not 1 <= sequence <= MAX_SEQUENCE:
        raise TransportProtocolError("sequence must be a positive signed 64-bit integer")
    if not isinstance(obj["kind"], str) or obj["kind"] not in KINDS:
        raise TransportProtocolError("unknown message kind")
    if not isinstance(obj["payload"], dict):
        raise TransportProtocolError("payload must be a JSON object")
    return obj


def _required_string(obj: Mapping[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise TransportProtocolError(f"{key} must be a non-empty string")
    return value


def _nonnegative_int(obj: Mapping[str, Any], key: str) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TransportProtocolError(f"{key} must be a non-negative integer")
    return value


def _frame_from_payload(payload: Mapping[str, Any]) -> FrameSnapshot:
    allowed = {"step", "t", "phase", "fixed_delta_time", "samples"}
    if set(payload) - allowed or not {"step", "t", "phase", "samples"}.issubset(payload):
        raise TransportProtocolError("frame payload has missing or unknown members")
    samples = payload["samples"]
    if not isinstance(samples, list):
        raise TransportProtocolError("frame.samples must be an array")
    parsed: list[EntitySample] = []
    core = {"id", "kind", "pos", "vel", "rot", "ang_vel", "state", "ai_state", "extra"}
    for row in samples:
        if not isinstance(row, dict):
            raise TransportProtocolError("each frame sample must be an object")
        if not {"id", "kind", "pos"}.issubset(row):
            raise TransportProtocolError("each frame sample requires id, kind, and pos")
        extra = row.get("extra", {})
        if not isinstance(extra, dict):
            raise TransportProtocolError("sample.extra must be an object")
        extra = {**extra, **{key: value for key, value in row.items() if key not in core}}
        parsed.append(EntitySample(
            row["id"], row["kind"], row["pos"], row.get("vel"), row.get("rot"),
            row.get("ang_vel"), row.get("state"), row.get("ai_state"), extra,
        ))
    return FrameSnapshot(payload["step"], payload["t"], payload["phase"], tuple(parsed),
                         payload.get("fixed_delta_time"))


class FlightTransportReceiver:
    """Validates transport ordering and forwards primitive messages to the writer."""

    def __init__(self, output_root: str | Path, *, writer_options: Mapping[str, Any] | None = None):
        self.output_root = Path(output_root)
        self.writer_options = dict(writer_options or {})
        self.writer: FlightRecorderWriter | None = None
        self.run_id: str | None = None
        self.last_sequence = 0
        self.connection_count = 0
        self.stopped = False
        self._seen: OrderedDict[int, bytes] = OrderedDict()
        self._lock = threading.RLock()

    def _mark_incomplete(self, reason: str, details: Mapping[str, Any] | None = None) -> None:
        if self.writer is not None:
            try:
                self.writer.mark_incomplete(reason, details=details)
            except WriterError:
                # The worker's fatal path already records writer_error where possible.
                # Do not mask that first failure with a secondary closing-state error.
                if not self.writer.worker_failed:
                    raise

    def _record_sequence_gap(self, first: int, last: int, received: int, payload: Mapping[str, Any]) -> None:
        details = {"first_missing_sequence": first, "last_missing_sequence": last,
                   "received_sequence": received}
        self._mark_incomplete("transport_message_sequence_gap", details)
        observed_t = payload.get("reported_at_t", payload.get("t"))
        if isinstance(observed_t, (int, float)) and not isinstance(observed_t, bool):
            self.writer.submit_event(RecorderEvent(
                "transport_message_sequence_gap", float(observed_t),
                step=payload.get("reported_at_step", payload.get("step")),
                evidence="observed", fields=details,
            ))

    def accept_line(self, raw: bytes, *, new_pipe_connection: bool = False) -> bool:
        """Consume one line; rotate to a new run only on a new connection's first hello."""
        with self._lock:
            if self.stopped:
                raise TransportProtocolError("message received after stop")
            digest = hashlib.sha256(raw).digest()
            try:
                envelope = parse_envelope(raw.rstrip(b"\r\n"))
                run_id = envelope["run_id"]
                sequence = envelope["sequence"]
                kind = envelope["kind"]
                payload = envelope["payload"]
                if kind == "hello" and payload.get("writer_schema") != FLIGHT_SCHEMA:
                    raise TransportProtocolError("producer does not declare aicadets.flight.v1 compatibility")
                if self.run_id is not None and run_id != self.run_id:
                    if not (new_pipe_connection and kind == "hello" and sequence == 1):
                        raise TransportProtocolError("run_id changed within one pipe connection")
                    self.close_uncleanly("producer_disconnected_before_stop", details={
                        "previous_run_id": self.run_id,
                        "next_run_id": run_id,
                    })
                    self.writer = None
                    self.run_id = None
                    self.last_sequence = 0
                    self.connection_count = 0
                    self.stopped = False
                    self._seen.clear()
                if sequence <= self.last_sequence:
                    if self._seen.get(sequence) == digest:
                        return True  # Repeated write after a broken pipe; already committed.
                    self._mark_incomplete("transport_duplicate_or_reordered_message",
                                          {"sequence": sequence, "last_sequence": self.last_sequence})
                    raise TransportProtocolError("duplicate or reordered sequence has different bytes")
                if self.writer is None and kind != "hello":
                    raise TransportProtocolError("first message must be hello")
                if self.writer is None:
                    self.run_id = run_id
                    self.output_root.mkdir(parents=True, exist_ok=True)
                    run_dir = self.output_root / f"run-{run_id}"
                    producer = payload.get("producer", "unknown")
                    if not isinstance(producer, str) or len(producer) > 128:
                        raise TransportProtocolError("hello.producer must be a short string")
                    capture_tier = payload.get("capture_tier", "transport_only")
                    if not isinstance(capture_tier, str) or not capture_tier or len(capture_tier) > 128:
                        raise TransportProtocolError("hello.capture_tier must be a short string")
                    timestamp_clock = payload.get("timestamp_clock")
                    step_source = payload.get("step_source")
                    discovery_interval = payload.get("discovery_interval_seconds")
                    if timestamp_clock is not None and (not isinstance(timestamp_clock, str) or not timestamp_clock or len(timestamp_clock) > 256):
                        raise TransportProtocolError("hello.timestamp_clock must be a short string when supplied")
                    if step_source is not None and (not isinstance(step_source, str) or not step_source or len(step_source) > 256):
                        raise TransportProtocolError("hello.step_source must be a short string when supplied")
                    if discovery_interval is not None and (
                            isinstance(discovery_interval, bool) or not isinstance(discovery_interval, (int, float))
                            or not math.isfinite(discovery_interval) or discovery_interval <= 0):
                        raise TransportProtocolError("hello.discovery_interval_seconds must be a positive finite number")
                    metadata = {
                        "transport_protocol": PROTOCOL,
                        "producer": producer,
                        "producer_version": payload.get("producer_version"),
                        "installed_build_fingerprint": payload.get("installed_build_fingerprint"),
                        "declared_coverage": payload.get("declared_coverage", {}),
                        "runtime_observation_phase": payload.get("runtime_observation_phase"),
                        "local_transport": "windows_named_pipe",
                        "capture_tier_declared_by_producer": capture_tier,
                    }
                    if timestamp_clock is not None:
                        metadata["timestamp_clock"] = timestamp_clock
                    if step_source is not None:
                        metadata["step_source"] = step_source
                    if discovery_interval is not None:
                        metadata["discovery_interval_seconds"] = discovery_interval
                    opts = dict(self.writer_options)
                    opts.setdefault("capture_tier", capture_tier)
                    opts.setdefault("metadata", metadata)
                    self.writer = FlightRecorderWriter(run_dir, run_id=run_id, **opts)
                if sequence > self.last_sequence + 1:
                    first = self.last_sequence + 1
                    last = sequence - 1
                    if kind == "gap":
                        first_declared = _nonnegative_int(payload, "first_sequence")
                        last_declared = _nonnegative_int(payload, "last_sequence")
                        if first_declared != first or last_declared != last:
                            self._record_sequence_gap(first, last, sequence, payload)
                            raise TransportProtocolError("gap range does not match the missing transport sequences")
                        else:
                            self._accept_gap(payload, first_declared, last_declared)
                    else:
                        self._record_sequence_gap(first, last, sequence, payload)
                elif kind == "gap":
                    # A gap marker without missing sequence IDs is still a reported frame loss.
                    first_declared = _nonnegative_int(payload, "first_sequence")
                    last_declared = _nonnegative_int(payload, "last_sequence")
                    if first_declared > last_declared:
                        raise TransportProtocolError("gap sequence range is reversed")
                    self._accept_gap(payload, first_declared, last_declared)
                self._dispatch(kind, payload)
                self.last_sequence = sequence
                self._seen[sequence] = digest
                while len(self._seen) > 128:
                    self._seen.popitem(last=False)
                if kind == "stop":
                    self.stopped = True
                    self.writer.close()
                    return False
                self.connection_count += 1 if kind == "hello" else 0
                return True
            except Exception as exc:
                if self.writer is not None and not isinstance(exc, TransportProtocolError):
                    self._mark_incomplete("transport_receiver_error", {"error": str(exc)[:512]})
                raise

    def _accept_gap(self, payload: Mapping[str, Any], first_sequence: int, last_sequence: int) -> None:
        dropped_frames = _nonnegative_int(payload, "dropped_frames")
        first_step = payload.get("first_step")
        last_step = payload.get("last_step")
        if dropped_frames < 1:
            raise TransportProtocolError("gap must account for at least one dropped frame")
        if (isinstance(first_step, bool) or not isinstance(first_step, int) or first_step < 0
                or isinstance(last_step, bool) or not isinstance(last_step, int) or last_step < first_step):
            raise TransportProtocolError("gap requires a valid inclusive frame-step range")
        details = {
            "first_sequence": first_sequence, "last_sequence": last_sequence,
            "dropped_frames": dropped_frames, "first_step": first_step, "last_step": last_step,
            "dropped_entity_samples": payload.get("dropped_entity_samples"),
        }
        self._mark_incomplete("transport_frame_loss", details)
        reported_t = payload.get("reported_at_t")
        reported_step = payload.get("reported_at_step")
        if isinstance(reported_t, (int, float)) and not isinstance(reported_t, bool):
            self.writer.submit_event(RecorderEvent(
                "transport_frame_gap", float(reported_t), step=reported_step,
                evidence="observed", fields=details,
            ))

    def _dispatch(self, kind: str, payload: Mapping[str, Any]) -> None:
        if kind == "hello":
            if payload.get("writer_schema") != FLIGHT_SCHEMA:
                raise TransportProtocolError("producer does not declare aicadets.flight.v1 compatibility")
            return
        if kind == "frame":
            frame = _frame_from_payload(payload)
            self.writer.submit_frame(frame)
            return
        if kind == "event":
            allowed = {"event", "t", "id", "step", "actor", "ids", "correlation_id",
                       "decision_id", "evidence", "fields"}
            if set(payload) - allowed or not {"event", "t"}.issubset(payload):
                raise TransportProtocolError("event payload has missing or unknown members")
            fields = payload.get("fields", {})
            if not isinstance(fields, dict):
                raise TransportProtocolError("event.fields must be an object")
            self.writer.submit_event(RecorderEvent(
                payload["event"], payload["t"], payload.get("id"), payload.get("step"),
                payload.get("actor"), tuple(payload.get("ids", ())), payload.get("correlation_id"),
                payload.get("decision_id"), payload.get("evidence"), fields,
            ))
            return
        if kind == "lifecycle":
            allowed = {"action", "id", "kind", "t", "step", "evidence"}
            if set(payload) != allowed:
                raise TransportProtocolError("lifecycle requires action, id, kind, t, step, and evidence")
            self.writer.submit_lifecycle(EntityLifecycleRecord(
                payload["action"], payload["id"], payload["kind"], payload["t"],
                payload["step"], payload["evidence"],
            ))
            return
        if kind == "gap":
            return
        if kind == "health":
            if payload.get("evidence") != "observed" or not isinstance(payload.get("t"), (int, float)):
                raise TransportProtocolError("health requires a source timestamp and evidence=observed")
            self.writer.submit_event(RecorderEvent(
                "producer_health", payload["t"], step=payload.get("step"), evidence="observed",
                fields={key: value for key, value in payload.items() if key not in {"t", "step", "evidence"}},
            ))
            return
        if kind == "stop":
            graceful = payload.get("graceful")
            if not isinstance(graceful, bool):
                raise TransportProtocolError("stop.graceful must be boolean")
            dropped_frames = _nonnegative_int(payload, "dropped_frames")
            dropped_controls = _nonnegative_int(payload, "dropped_control_messages")
            if not graceful:
                self._mark_incomplete("producer_stopped_uncleanly", {"reason": payload.get("reason")})
            if dropped_frames:
                self._mark_incomplete("producer_reported_dropped_frames",
                                      {"dropped_frames": dropped_frames,
                                       "first_step": payload.get("first_dropped_step"),
                                       "last_step": payload.get("last_dropped_step")})
            if dropped_controls:
                self._mark_incomplete("producer_reported_dropped_control_messages",
                                      {"dropped_control_messages": dropped_controls})
            return
        raise TransportProtocolError(f"unsupported message kind {kind}")

    def close_uncleanly(self, reason: str,
                        details: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        with self._lock:
            if self.writer is None or self.stopped:
                return None
            self._mark_incomplete(reason, details=details)
            try:
                stats = self.writer.close()
            except WriterError:
                if not self.writer.worker_failed:
                    raise
                stats = self.writer.stats()
            self.stopped = True
            return stats


if os.name == "nt":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    class _SidAndAttributes(ctypes.Structure):
        _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]

    class _TokenUser(ctypes.Structure):
        _fields_ = [("User", _SidAndAttributes)]

    class _SecurityAttributes(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p),
                    ("bInheritHandle", wintypes.BOOL)]

    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    _kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    _kernel32.GetDriveTypeW.restype = wintypes.UINT
    _advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    _advapi32.OpenProcessToken.restype = wintypes.BOOL
    _advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    _advapi32.GetTokenInformation.restype = wintypes.BOOL
    _kernel32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                            wintypes.DWORD, ctypes.POINTER(_SecurityAttributes)]
    _kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
    _kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    _kernel32.ConnectNamedPipe.restype = wintypes.BOOL
    _kernel32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _kernel32.ReadFile.restype = wintypes.BOOL
    _kernel32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _kernel32.WriteFile.restype = wintypes.BOOL
    _kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    _kernel32.FlushFileBuffers.restype = wintypes.BOOL
    _kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
    _kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p
    _advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    _advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD)]
    _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL


class WindowsNamedPipeServer:
    """Single-instance local byte pipe with current-user DACL and bounded line parsing."""

    def __init__(self, name: str, receiver: FlightTransportReceiver):
        if os.name != "nt":
            raise OSError("Windows named pipes are available only on Windows")
        if not _PIPE_NAME.fullmatch(name):
            raise ValueError("pipe name must contain only letters, digits, dot, underscore, or hyphen")
        self.name = name
        self.receiver = receiver
        self.pipe_path = rf"\\.\pipe\{name}"
        self._stopping = threading.Event()

    def stop(self) -> None:
        self._stopping.set()

    @staticmethod
    def _security_attributes() -> tuple[_SecurityAttributes, int, int]:
        token = wintypes.HANDLE()
        if not _advapi32.OpenProcessToken(_kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid_text = wintypes.LPWSTR()
        descriptor = ctypes.c_void_p()
        try:
            needed = wintypes.DWORD()
            _advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
            if not needed.value:
                raise ctypes.WinError(ctypes.get_last_error())
            buffer = ctypes.create_string_buffer(needed.value)
            if not _advapi32.GetTokenInformation(token, 1, buffer, needed, ctypes.byref(needed)):
                raise ctypes.WinError(ctypes.get_last_error())
            user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
            if not _advapi32.ConvertSidToStringSidW(user.User.Sid, ctypes.byref(sid_text)):
                raise ctypes.WinError(ctypes.get_last_error())
            sddl = f"D:P(A;;GA;;;{sid_text.value})"
            if not _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                    sddl, 1, ctypes.byref(descriptor), None):
                raise ctypes.WinError(ctypes.get_last_error())
            attrs = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), descriptor, False)
            return attrs, descriptor.value, int(token.value)
        except BaseException:
            _kernel32.CloseHandle(token)
            if descriptor:
                _kernel32.LocalFree(descriptor)
            raise
        finally:
            if sid_text:
                _kernel32.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))

    def _new_pipe(self) -> int:
        attrs, descriptor, token = self._security_attributes()
        try:
            # PIPE_ACCESS_DUPLEX; byte mode; nonblocking polling; reject remote clients.
            mode = 0x00000000 | 0x00000001 | 0x00000008
            handle = _kernel32.CreateNamedPipeW(self.pipe_path, 0x00000003, mode, 1,
                                                MAX_READ_BYTES, MAX_READ_BYTES, 0, ctypes.byref(attrs))
            if ctypes.cast(handle, ctypes.c_void_p).value == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            return int(ctypes.cast(handle, ctypes.c_void_p).value)
        finally:
            _kernel32.LocalFree(descriptor)
            _kernel32.CloseHandle(wintypes.HANDLE(token))

    def _consume_client(self, handle: int) -> None:
        pending = bytearray()
        buffer = ctypes.create_string_buffer(MAX_READ_BYTES)
        read_count = wintypes.DWORD()
        new_pipe_connection = True
        print("Flight Recorder producer connected", flush=True)
        while not self._stopping.is_set():
            ok = _kernel32.ReadFile(wintypes.HANDLE(handle), buffer, MAX_READ_BYTES,
                                    ctypes.byref(read_count), None)
            if not ok:
                error = ctypes.get_last_error()
                if error == 232:  # ERROR_NO_DATA: nonblocking pipe has no bytes yet.
                    self._stopping.wait(0.005)
                    continue
                if error in (109, 233):  # broken/disconnected client
                    return
                raise ctypes.WinError(error)
            if not read_count.value:
                self._stopping.wait(0.005)
                continue
            pending.extend(buffer.raw[:read_count.value])
            if len(pending) > MAX_ENVELOPE_BYTES and b"\n" not in pending:
                self.receiver._mark_incomplete("oversized_transport_line",
                                                {"buffered_bytes": len(pending)})
                return
            while True:
                newline = pending.find(b"\n")
                if newline < 0:
                    break
                line = bytes(pending[:newline]).rstrip(b"\r")
                del pending[:newline + 1]
                try:
                    envelope = parse_envelope(line)
                    previous_run_id = self.receiver.run_id
                    keep_serving = self.receiver.accept_line(
                        line, new_pipe_connection=new_pipe_connection)
                    new_pipe_connection = False
                    self._write_ack(handle, envelope["run_id"], envelope["sequence"], True)
                    if envelope["kind"] in {"hello", "gap", "stop"}:
                        print(f"Flight Recorder received {envelope['kind']} seq={envelope['sequence']}", flush=True)
                    if (envelope["kind"] == "hello" and previous_run_id is not None
                            and envelope["run_id"] != previous_run_id):
                        print(f"Finalized disconnected run {previous_run_id} as incomplete; "
                              f"accepted new run {envelope['run_id']}", flush=True)
                    if not keep_serving:
                        _kernel32.FlushFileBuffers(wintypes.HANDLE(handle))
                        self.stop()
                        return
                except Exception as exc:
                    try:
                        rejected = parse_envelope(line)
                        self._write_ack(handle, rejected["run_id"], rejected["sequence"], False,
                                        f"{type(exc).__name__}: {exc}"[:512])
                    except Exception:
                        pass
                    self.receiver.close_uncleanly("transport_protocol_error")
                    raise
                if len(pending) > MAX_ENVELOPE_BYTES:
                    self.receiver._mark_incomplete("oversized_transport_line",
                                                    {"buffered_bytes": len(pending)})
                    return
        if pending:
            self.receiver._mark_incomplete("truncated_transport_line", {"buffered_bytes": len(pending)})
        print("Flight Recorder producer disconnected", flush=True)

    @staticmethod
    def _write_ack(handle: int, run_id: str, sequence: int, accepted: bool, error: str | None = None) -> None:
        response: dict[str, Any] = {
            "protocol": PROTOCOL, "run_id": run_id,
            "ack_sequence": sequence, "accepted": accepted,
        }
        if error is not None:
            response["error"] = error
        data = json.dumps(response, separators=(",", ":")).encode("utf-8") + b"\n"
        offset = 0
        buffer = ctypes.create_string_buffer(data)
        while offset < len(data):
            written = wintypes.DWORD()
            ok = _kernel32.WriteFile(wintypes.HANDLE(handle),
                                     ctypes.cast(ctypes.byref(buffer, offset), ctypes.c_void_p),
                                     len(data) - offset, ctypes.byref(written), None)
            if ok and written.value:
                offset += written.value
                continue
            error_code = ctypes.get_last_error()
            if error_code == 232:
                time.sleep(0.005)
                continue
            raise ctypes.WinError(error_code)

    def serve_forever(self) -> None:
        while not self._stopping.is_set():
            handle = self._new_pipe()
            try:
                connected_to_client = False
                while not self._stopping.is_set():
                    connected = _kernel32.ConnectNamedPipe(wintypes.HANDLE(handle), None)
                    if connected:
                        connected_to_client = True
                        break
                    error = ctypes.get_last_error()
                    if error == 535:  # ERROR_PIPE_CONNECTED: client won the connect race.
                        connected_to_client = True
                        break
                    if error == 536:  # ERROR_PIPE_LISTENING (PIPE_NOWAIT); retain this instance.
                        self._stopping.wait(0.01)
                        continue
                    if error == 232:  # Client connected and closed before the server observed it.
                        break
                    raise ctypes.WinError(error)
                if connected_to_client and not self._stopping.is_set():
                    self._consume_client(handle)
            finally:
                _kernel32.DisconnectNamedPipe(wintypes.HANDLE(handle))
                _kernel32.CloseHandle(wintypes.HANDLE(handle))


def _load_config(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read config: {exc}") from exc
    if not isinstance(config, dict) or config.get("recording_enabled") is not True:
        raise SystemExit("recording is opt-in; set recording_enabled to true in the local config")
    allowed = {"recording_enabled", "pipe_name", "output_dir", "writer_limits"}
    if set(config) - allowed:
        raise SystemExit(f"unknown configuration members: {sorted(set(config) - allowed)}")
    pipe_name = config.get("pipe_name", "aicadets-flight-recorder-v1")
    if not isinstance(pipe_name, str) or not _PIPE_NAME.fullmatch(pipe_name):
        raise SystemExit("pipe_name contains invalid characters")
    output_dir = config.get("output_dir")
    if not isinstance(output_dir, str) or not output_dir.strip():
        raise SystemExit("output_dir must be a non-empty local path")
    root = Path(output_dir).expanduser()
    if not root.is_absolute():
        root = (path.parent / root).resolve()
    if os.name == "nt":
        drive = root.drive
        if not drive or drive.startswith("\\\\"):
            raise SystemExit("output_dir must be on a local Windows volume, not a UNC path")
        drive_root = drive + "\\"
        drive_type = _kernel32.GetDriveTypeW(drive_root)
        if drive_type not in (2, 3, 6):  # removable, fixed, or RAM disk
            raise SystemExit("output_dir must be on a local volume, not a mapped/network drive")
    limits = config.get("writer_limits", {})
    if not isinstance(limits, dict):
        raise SystemExit("writer_limits must be an object")
    supported = {"queue_capacity", "max_queue_bytes", "chunk_target_bytes", "max_storage_bytes", "max_chunks"}
    if set(limits) - supported:
        raise SystemExit(f"unknown writer limit keys: {sorted(set(limits) - supported)}")
    return {"pipe_name": pipe_name, "output_root": root}, limits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="local, opt-in JSON configuration")
    args = parser.parse_args(argv)
    options, limits = _load_config(args.config.resolve())
    receiver = FlightTransportReceiver(options["output_root"], writer_options=limits)
    server = WindowsNamedPipeServer(options["pipe_name"], receiver)
    print(f"Flight Recorder receiver listening on local pipe {server.pipe_path}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()
        receiver.close_uncleanly("receiver_interrupted")
    except Exception as exc:
        server.stop()
        receiver.close_uncleanly("receiver_fatal_error")
        print(f"Flight Recorder receiver stopped: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2
    if not receiver.stopped:
        receiver.close_uncleanly("receiver_stopped_before_producer_stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
