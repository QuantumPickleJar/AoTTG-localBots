# Flight Recorder local transport

## Scope and evidence

The current bridge connects the read-only BepInEx IL2CPP adapter to the existing Python FlightRecorderWriter. Unity/game APIs are accessed only on the injected Unity callback thread. Version 0.1.9 hands a copied primitive DTO to the producer, which serializes it once into a bounded UTF-8 protocol envelope; the background worker performs pipe I/O. Ordinary frames and controls leave two queue slots and 16 KiB available for frame-gap accounting and a final stop record. The Python writer retries transient `PermissionError` failures during atomic JSON replacement with bounded backoff. If the error persists, the run remains incomplete, and receiver cleanup retains the primary writer failure rather than raising a second closing-state error. The installer replaces only a prior receipt-verified, unchanged recorder installation. The receiver calls the existing writer and preserves the `aicadets.flight.v1` frame/event/lifecycle format and hashed chunk manifest. The direct serialization, queue, and rename-retry changes still need measurement in an installed-game mission.

An earlier 0.1.5 build from the same adapter source passed an installed main-menu smoke with 1,982 ordered frames, one verified chunk, 8 events, zero loss, a graceful stop, and no game entities. The first health window reported a 103.9691 ms capture-work maximum; later windows ranged from 6.9426 to 12.7446 ms. The final deterministic 0.1.5 package also started and wrote 5,717 ordered menu frames and 23 events to a SHA-256-verified chunk with no entities, drops, or analyzer anomalies, but the run was explicitly marked incomplete (`receiver_interrupted`) after the game and BepInEx console were closed together. This is Level 2 startup/transport evidence, not a clean-shutdown pass, and it does not establish actor coverage or gameplay collision callbacks. See [the adapter audit](FLIGHT_RECORDER_ADAPTER_PLAN.md) and [REC-I card](REC_I_VALIDATION_BLOCKER.md).

## Protocol v1

The producer sends one UTF-8 JSON object per line:

    {"protocol":"aicadets.flight.transport.v1","run_id":"32-hex-uuid","sequence":1,"kind":"hello","payload":{"writer_schema":"aicadets.flight.v1","producer":"..."}}

Messages are bounded to 1 MiB. run_id is a UUID in N form. Sequence numbers increase across reconnects. Supported kinds are hello, frame, event, lifecycle, gap, health, and stop. Payloads map to the existing FrameSnapshot, RecorderEvent, and EntityLifecycleRecord types without filling absent fields.

The receiver acknowledges each accepted envelope with its run_id and ack_sequence. The producer keeps the same message at the head of its bounded queue until that acknowledgment arrives. After a broken connection it retries; the receiver de-duplicates identical recent sequence/payload pairs. A sequence gap, rejected message, malformed line, or unreported frame loss marks the run incomplete. If a different producer connects with a new run_id after the previous pipe client disconnected without sending stop, the receiver finalizes that prior run as incomplete and begins a separate run directory. A valid stop ends the receiver; start the receiver again for the next capture. A receiver process restart does not resume a prior run, and its existing run directory is left intact for recovery.

Producer defaults are 512 queue slots and 4 MiB, with 32 slots and 256 KiB held back from frames for ordinary controls. Ordinary controls also leave two slots and 16 KiB protected for critical gap and stop messages. Frames that cannot fit are counted and later reported as an explicit gap envelope. If ordinary control capacity overflows, the producer marks the capture incomplete, preserves a pending gap and final stop using critical capacity when available, and records dropped-control counts. Repeated critical use can still exhaust the bounded queue; the producer then fails closed. The Python writer retains its own bounded queue, storage quota, hash manifest, and interrupted-write recovery.

## Windows pipe security and operation

The receiver uses a duplex Windows named pipe, a protected DACL granting the current Windows user, and PIPE_REJECT_REMOTE_CLIENTS. It does not bind a TCP socket or upload data. The producer uses a background thread for pipe I/O; the frame DTO contains copied primitive values and no Unity object references. No transport call waits for pipe availability on the Unity callback thread. Queued `ReadOnlyMemory<byte>` is backed by an immutable-per-message `ArrayBufferWriter<byte>` retained until acknowledgement.

Copy configs/flight-recorder-transport.example.json to a local private config, select a new empty output directory, and set recording_enabled=true only for an opted-in private capture. The package includes Python 3.14.10 x64 embeddable plus a launcher; this does not change PATH or install a system-wide Python. Start the receiver from the extracted package:

       .\scripts\start_flight_recorder_receiver.ps1 -PackageRoot "C:\Local\Path\AoTTG2-FlightRecorder-0.1.9" -ConfigPath "C:\Local\Path\flight-recorder-transport.json"

The launcher starts the receiver hidden, waits until the local pipe is ready, and writes stdout/stderr logs beside the config. After a run, use the package runtime to inspect the output:

    .\runtime\python.exe .\tools\analyze_flight.py "C:\Local\Path\recordings\run-<run-id>" --out "C:\Local\Path\analysis"

The config and output path are local. Do not include installation paths, proprietary game files, or another player's data in a shared archive.

## Current status and tests

- The .NET producer and Unity plugin build locally; the Unity plugin compiles against interop generated from the exact installed x64 Unity 2023.1.22f1 build.
- Python protocol/writer/analyzer suite: 117 tests pass, including transient Windows rename retry and fatal-writer receiver cleanup.
- The ordered pipe/backpressure smoke covers critical slot and byte reservation exhaustion; the Windows pipe-to-writer recovery smoke passes with the workspace and packaged Python runtimes.
- The 0.1.7 packaged receiver/writer/analyzer passed a two-session local pipe smoke, including incomplete-run recovery and chunk verification. Version 0.1.8 retained that transport and added automatic verified replacement in the installer. Version 0.1.9 adds bounded atomic-replace retries and fatal-writer cleanup handling; its 49-file package and disposable upgrade/rollback check passed.
- Installed-runtime package 0.1.5 menu smoke passed. The supplied 0.1.5 gameplay trace completed with verified chunks. A later 0.1.5 plugin log reports `control_reserve_exhausted_before_frame_gap`; that attempt is incomplete. The latest 0.1.8 run connected and wrote 8,197 frames and 282 events across six verified chunks, then ended incomplete after `PermissionError` replacing `writer_state.json`; one enqueued frame was not durable. Version 0.1.9 startup, recovery, and performance await private validation.

The supplied 0.1.5 gameplay capture did observe Humans, Titans, Hooks, and Human collision callbacks. It suggests a cadet kill without direct damage attribution. REC-I Level 3 remains pending a new private 0.1.9 performance and phase calibration.
