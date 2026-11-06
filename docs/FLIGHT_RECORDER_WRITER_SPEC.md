# Flight Recorder writer deployment connection

**State:** the offline core, bounded Windows local transport, and opt-in BepInEx IL2CPP adapter are implemented. The adapter is built against the inspected local installation and passed a main-menu startup/transport/writer smoke. This is not a gameplay calibration claim.

## Connection point

`tools/flight_writer.py` is a Python standard-library module. The Unity-facing adapter copies engine state into immutable primitive messages in its injected `MonoBehaviour.FixedUpdate` callback, then hands those messages to the local pipe client. Unity callback ordering relative to the engine physics simulation is not established. The adapter never passes Unity object references, `Transform`, `Rigidbody`, `GameObject`, or mutable game collections to the background writer.

```mermaid
flowchart TD
    A[Injected Unity FixedUpdate callback] --> B[Main-thread primitive snapshot]
    B --> C[Bounded .NET named-pipe client]
    C --> D[FlightRecorderWriter API]
    D --> E[Hashed JSONL chunks]
```

The implemented bridge is `plugin/FlightRecorder.TransportClient` plus `tools/flight_transport.py`; it uses a current-user Windows pipe DACL, rejects remote clients, bounds messages/queues, acknowledges accepted messages, and marks incomplete runs on unaccounted sequence loss. It passed both synthetic end-to-end tests and an installed main-menu smoke. See [FLIGHT_RECORDER_TRANSPORT.md](FLIGHT_RECORDER_TRANSPORT.md) and [the installed-build audit](FLIGHT_RECORDER_ADAPTER_PLAN.md).

## Writer API mapping

| Adapter observation | Writer call | Required data and rule |
|---|---|---|
| One global physics callback | `submit_frame(FrameSnapshot(...))` | One monotonically increasing source step; one time and phase for all samples; copy primitive pose/velocity/state fields. Never synthesize a missing step. |
| Entity spawn/despawn | `submit_lifecycle(EntityLifecycleRecord(...))` | Stable per-spawn ID; emit despawn only when observed. A reused source handle increments its generation. |
| Decision, command or outcome | `submit_event(RecorderEvent(...))` | Preserve source event name, timestamp, step if observed, entity/correlation IDs, evidence grade and exact structured fields. Missing values remain absent. |
| External source or transport loss | `mark_incomplete(reason, details=...)` | Bounded reason ledger; final `capture_complete` is false and metadata preserves first/last bounded details. Do not synthesize a frame for a missing step. |
| Stop/health reporting | `stats()` then `close()` | Surface queue loss, storage exhaustion, rejected events, incomplete capture and final chunk/manifest state to the local operator. |

Stable IDs should use the source actor handle plus a spawn generation, for example `human:73:2`. IDs must not use a reusable display name alone. Entity-kind and source-handle normalization belongs in the adapter; the recorder does not infer identity from position or names.

For a decision input, the adapter may pass the complete, actually observed replay contract as `RecorderEvent.fields`: `policy_version`, `state_version`, validated profile and hash, candidate list with status and real eligibility/mechanical gates, and observations. The event's top-level `id`, `decision_id`, `step` and `t` must refer to the same decision. A replayable record also requires a matching same-step physics frame. If any value is unavailable, omit it and let `tools/replay_decisions.py` report the decision as incomplete. Do not convert the legacy M2 `LogEvent` stream into fabricated decision inputs or claim Python reference-policy agreement as production M2 parity.

## Bounded behavior and operator contract

| Condition | Core behavior | Adapter/operator action |
|---|---|---|
| Frame queue full | `submit_frame` returns `queue_saturated`; a bounded gap is queued with step and sample counts where known. Capacity is reserved for control records. | Surface degraded capture. If the gap ledger is full and the call raises, retain/retry or stop; do not ignore the exception. |
| Event queue full | Uses the reserved control slots/bytes, preserving FIFO order. If still full, waits at most the configured timeout, then raises `RecorderOverloadError`; the event was not accepted. | Retain/retry the exact event or stop with an incomplete run. Never report an unrecorded decision as captured. |
| Storage or chunk cap | Ordinary writes stop; affected frames and rejected controls are accounted for in metadata and reserved final gap records where space remains. | Stop producing telemetry, preserve the run directory and show `capture_complete=false`. |
| Process interruption | Finalized chunks remain independently hash-checked; complete lines in `.partial` chunks can be salvaged; known step gaps are emitted. | Run `recover_run()` on a copy of the stopped run; preserve corrupt and archived source files for diagnosis. |

`max_storage_bytes` is a hard run-directory limit; `control_reserve_bytes` leaves space for the manifest, state, metadata and final loss records. `max_chunks` includes one reserved chunk for emergency accounting. Configure limits from an expected session length and disk budget before game testing; a synthetic benchmark is not a safe default profile for every user's machine.

## Audit gates

### Installed-build audit completed

- The local read-only preflight and loader startup establish x64 IL2CPP, Unity 2023.1.22f1, metadata 29.1, and BepInEx 6.0.0-be.791 compatibility for this exact installation.
- The installed adapter callback is an injected `MonoBehaviour.FixedUpdate`; its ordering relative to physics remains unspecified and must be calibrated against a short video.
- The bounded named-pipe bridge, package, install manifest and hash-checked rollback are built. The H3VR BepInEx 5 Mono files were not reused.

### Requires actual gameplay

- Calibrate callback ordering and timestamps against a short local video; verify and preserve the actual phase label (`fixed_update_pre_physics` if that seam is selected).
- Measure per-step global coverage across representative actors, spawn/despawn and scene transitions; validate explicit gap/drop reporting.
- Exercise decision, command, damage and rescue event provenance in a private master-host session; prove correlation without inferring outcomes.
- Measure game frame time, CPU, memory, queue pressure, storage and shutdown behavior at representative load. Confirm no gameplay mutations and no material performance regression.

The installed AoTTG2 copy ran BepInEx 6.0.0-be.791 on x64 Unity 2023.1.22f1 and generated local IL2CPP interop. An earlier 0.1.5 build from the same adapter source passed a main-menu startup/transport/writer smoke: 1,982 ordered frames, one verified chunk, complete capture, zero drops or analyzer anomalies, graceful shutdown, and no entities at the menu. The first health window included a 103.9691 ms capture-work maximum; subsequent windows ranged from 6.9426 to 12.7446 ms. The final deterministic 0.1.5 package also started and wrote 5,717 ordered menu frames and 23 events to a SHA-256-verified chunk with no entities, drops, or analyzer anomalies, but its run was marked incomplete (`receiver_interrupted`) after the game and BepInEx console were closed together. That retry is not a clean-shutdown pass. The short private REC-I gameplay calibration remains pending. See [the installed-build audit](FLIGHT_RECORDER_ADAPTER_PLAN.md) and [REC-I card](REC_I_VALIDATION_BLOCKER.md). Offline tests and menu smokes do not establish mission physics timing or gameplay coverage.
