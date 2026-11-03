# Flight Recorder local transport

## Scope and evidence

The current bridge connects the read-only BepInEx IL2CPP adapter to the existing Python FlightRecorderWriter. Unity/game APIs are accessed only on the injected Unity callback thread; copied primitive JSON payloads are enqueued for the background named-pipe producer. The receiver calls the existing writer and preserves the aicadets.flight.v1 frame/event/lifecycle format and hashed chunk manifest.

The final package 0.1.5 passed an installed main-menu smoke with 1,982 ordered frames, one verified chunk, 8 events, zero loss, a graceful stop, and no game entities. The first health window reported a 103.9691 ms capture-work maximum; later windows ranged from 6.9426 to 12.7446 ms. This is Level 2 transport/startup evidence; it does not establish actor coverage or gameplay collision callbacks. See [the adapter audit](FLIGHT_RECORDER_ADAPTER_PLAN.md) and [REC-I card](REC_I_VALIDATION_BLOCKER.md).

## Protocol v1

The producer sends one UTF-8 JSON object per line:

    {"protocol":"aicadets.flight.transport.v1","run_id":"32-hex-uuid","sequence":1,"kind":"hello","payload":{"writer_schema":"aicadets.flight.v1","producer":"..."}}

Messages are bounded to 1 MiB. run_id is a UUID in N form. Sequence numbers increase across reconnects. Supported kinds are hello, frame, event, lifecycle, gap, health, and stop. Payloads map to the existing FrameSnapshot, RecorderEvent, and EntityLifecycleRecord types without filling absent fields.

The receiver acknowledges each accepted envelope with its run_id and ack_sequence. The producer keeps the same message at the head of its bounded queue until that acknowledgment arrives. After a broken connection it retries; the receiver de-duplicates identical recent sequence/payload pairs. A sequence gap, rejected message, malformed line, or unreported frame loss marks the run incomplete. A process restart does not resume a prior run: start a new run_id and leave the old run directory intact for recovery.

Producer defaults are 512 queue slots and 4 MiB, with reserved capacity for control messages. Frames that cannot fit are counted and later reported as an explicit gap envelope. If critical control messages cannot fit, the producer reports a fatal transport state and capture stops; it must not claim a complete run. The Python writer retains its own bounded queue, storage quota, hash manifest, and interrupted-write recovery.

## Windows pipe security and operation

The receiver uses a duplex Windows named pipe, a protected DACL granting the current Windows user, and PIPE_REJECT_REMOTE_CLIENTS. It does not bind a TCP socket or upload data. The producer uses a background thread for pipe I/O; Unity objects must already have been copied to primitive JSON before enqueue. No transport call waits for pipe availability on the Unity callback thread.

Copy configs/flight-recorder-transport.example.json to a local private config, select a new empty output directory, and set recording_enabled=true only for an opted-in private capture. The package includes Python 3.14.10 x64 embeddable plus a launcher; this does not change PATH or install a system-wide Python. Start the receiver from the extracted package:

    .\scripts\start_flight_recorder_receiver.ps1 -PackageRoot "C:\Local\Path\AoTTG2-FlightRecorder-0.1.5" -ConfigPath "C:\Local\Path\flight-recorder-transport.json"

The launcher starts the receiver hidden, waits until the local pipe is ready, and writes stdout/stderr logs beside the config. After a run, use the package runtime to inspect the output:

    .\runtime\python.exe .\tools\analyze_flight.py "C:\Local\Path\recordings\run-<run-id>" --out "C:\Local\Path\analysis"

The config and output path are local. Do not include installation paths, proprietary game files, or another player's data in a shared archive.

## Current status and tests

- The .NET producer and Unity plugin build locally; the Unity plugin compiles against interop generated from the exact installed x64 Unity 2023.1.22f1 build.
- Python protocol/writer suite: 107 tests pass.
- Windows pipe-to-writer smoke passes with both the task-local Python 3.14.10 runtime and the final package's embedded runtime.
- Package receiver launcher smoke passes: it became ready, accepted hello/frame/event/stop messages, wrote a verified chunk, and exited cleanly.
- Installed-runtime package 0.1.5 menu smoke passed. It confirms BepInEx/plugin startup, Unity FixedUpdate calls, local handshake, frame writing/hash integrity, health reporting and graceful shutdown. There were no entities because no lobby or mission was entered.

No gameplay movement, Human/Titan/Hook sampling, or collision callback firing is claimed. REC-I Level 3 remains pending the owner's private calibration.
