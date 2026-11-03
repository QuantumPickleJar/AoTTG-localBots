# Flight Recorder local transport

## Scope

This implementation connects an immutable primitive-data producer to the
existing Python `FlightRecorderWriter`. It does not include the Unity plugin,
game-object registry, physics callback, or AoTTG2 entity mapping. The Windows
smoke test sends synthetic records; its successful trace is transport evidence,
not an installed-game recording.

## Protocol v1

The producer sends one UTF-8 JSON object per line:

```json
{"protocol":"aicadets.flight.transport.v1","run_id":"32-hex-uuid","sequence":1,"kind":"hello","payload":{"writer_schema":"aicadets.flight.v1","producer":"..."}}
```

Messages are bounded to 1 MiB. `run_id` is a UUID in `N` form. Sequence numbers
increase across reconnects. Supported kinds are `hello`, `frame`, `event`,
`lifecycle`, `gap`, `health`, and `stop`. Frame/event/lifecycle payloads map to
the existing `FrameSnapshot`, `RecorderEvent`, and `EntityLifecycleRecord`
types without filling absent fields.

The receiver acknowledges each accepted envelope with its `run_id` and
`ack_sequence`. The producer keeps the same message at the head of its bounded
queue until that acknowledgment arrives. After a broken connection it retries;
the receiver de-duplicates identical recent sequence/payload pairs. A sequence
gap, rejected message, malformed line, or unreported frame loss marks the run
incomplete. A process restart does not resume a prior run: start a new `run_id`
and leave the old run directory intact for recovery.

Producer defaults are 512 queue slots and 4 MiB, with 32 slots and 256 KiB
reserved for control messages. Frames that cannot fit are counted and later
reported as an explicit `gap` envelope. If critical control messages cannot fit,
the producer reports a fatal transport state and the capture owner must stop;
it must not claim a complete run. The Python writer retains its own bounded
queue, storage quota, hash manifest, and interrupted-write recovery.

## Windows pipe security and operation

The receiver uses one duplex Windows named pipe, a protected DACL granting the
current Windows user, and `PIPE_REJECT_REMOTE_CLIENTS`. It does not bind a TCP
socket or upload data. The producer uses a background thread for pipe I/O;
Unity objects must already have been copied to primitive JSON before enqueue.
No transport call waits for pipe availability on the Unity callback thread.

Copy `configs/flight-recorder-transport.example.json` to a local private config,
select a new empty output directory, and set `recording_enabled` to `true` only
for an explicitly opted-in capture. Start the receiver with:

```powershell
py -3 tools/flight_transport.py --config "C:\Local\Path\flight-recorder-transport.json"
```

After a run, inspect the output with:

```powershell
py -3 tools/analyze_flight.py "C:\Local\Path\recordings\run-<run-id>" --out "C:\Local\Path\analysis"
```

The config and output path are local. Do not include installation paths,
proprietary game files, or another player's data in a shared archive.

## Current status and tests

- `plugin/FlightRecorder.TransportClient` builds for .NET 6 and .NET 8.
- The C# smoke program verifies ordered hello/event/stop messages with
  acknowledgments.
- `tests/transport_windows_smoke.ps1` runs a C# producer through the Windows
  named pipe into the Python writer, then checks the hashed chunk with the
  existing analyzer.
- Python protocol tests cover message limits, duplicates, lifecycle/frame/
  event mapping, explicit sequence gaps, frame-step gaps, and incomplete-run
  metadata.

These checks do not exercise BepInEx, IL2CPP interop, Unity objects, actual
physics timing, or AoTTG2. The sidecar is not a stand-alone recorder until a
compatible game-side producer exists.
