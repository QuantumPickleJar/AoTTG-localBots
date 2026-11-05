# AoTTG2 IL2CPP Flight Recorder package

**Build:** 0.1.12 candidate, compiled against interop generated from the installed AoTTG2 build

**Runtime:** x64, Unity 2023.1.22f1, IL2CPP metadata 29.1, BepInEx 6.0.0-be.791, .NET 6

**Capture default:** disabled

This opt-in package contains the game-side BepInEx IL2CPP plugin, bounded named-pipe producer, Python receiver/writer/analyzer, and a portable Python 3.14.10 x64 embeddable runtime with its license. It excludes AoTTG2 binaries, loader binaries, and generated/proprietary game interop. Version 0.1.11 retained the 0.1.10 queue, stop, and reconnect behavior and reused per-entity sample buffers and frame storage while preserving the `aicadets.flight.v1` payload fields. Version 0.1.12 removes Unity's implicit InstanceID sort from the periodic discovery census while preserving inactive-object discovery and the explicit entity-ID ordering used for output. Unity documents `FindObjectsSortMode.None` as the least resource-intensive option and notes that result order is not guaranteed ([`FindObjectsByType`](https://docs.unity3d.com/ja/2023.1/ScriptReference/Object.FindObjectsByType.html), [`FindObjectsSortMode.None`](https://docs.unity3d.com/ja/2023.1/ScriptReference/FindObjectsSortMode.None.html)). This optimization has not yet had an installed-runtime performance retest.

The 0.1.11 clean-start run `1ad84008622a4d4d9e06cae2a25ffac6` loaded and stopped cleanly with `capture_complete=true`, 39,509 frames, one verified chunk, no frame gaps or declared drops, and bounded queues. It tracked zero entities and had no M2 events, so it was not an M2 workload or phase-calibration run. Of 156 producer-health windows after 15 monotonic seconds, 2 exceeded the 1.0 ms p95 limit; the worst p95 was 2.8658 ms and the worst reported individual sample was 91.2873 ms. The performance gate therefore failed. The `fixed_update_pre_physics` phase label is descriptive only; `sample_phase_verified=false` remains until a controlled natural physics transition establishes phase.

This is a client startup plug-in, not an AoTTG Custom Logic `.cl` add-on selected in a lobby. Keep the game folder writable because BepInEx writes configuration, logs, and generated interop. The guarded recorder installer writes only its two DLLs and receipt into its dedicated plug-in folder. The game does not start the Python receiver; the game plug-in only connects to its local named pipe, so start the receiver before launching AoTTG2 with capture enabled.

## Latest gameplay capture

The owner-supplied 0.1.5 trace completed through the writer and transport: 56,970 ordered frame markers, 35/35 SHA-256-verified chunks, 779 events, 54 lifecycle records, and 27 entity IDs (6 Titans, 3 Humans, 18 Hooks). It had no declared drops or missing frame markers and `capture_complete=true`. It contains 209 observed Human collision callbacks and 340 sampled Hook state transitions. Sampling phase remains unverified.

The updated analyzer writes `kill_attributions.json`. It identifies one `strong_inferred_candidate`: a Titan changed from health 1/alive to 0/dead at t=894.299683, step 44,716, with a death state/animation, then was observed destroyed. An AI-controlled Human had 13 observed collisions with that Titan in the prior 3.56 seconds and an attack state/animation sampled near death. This is strong evidence consistent with the cadet getting the kill; no direct damage-source or correlated death callback was recorded, so causality remains inferred.

A later installed-game log is from plugin 0.1.5 and reports `control_reserve_exhausted_before_frame_gap`; treat that attempt as incomplete. A 0.1.8 run connected and left six verified chunks, but was incomplete after Windows denied replacing `writer_state.json`. Version 0.1.9 was subsequently installed and recorded a live session, but the game disconnected without a stop envelope; the receiver left the run open with an unindexed partial chunk. This exposed that the old receiver finalized a disconnected run only when a later run connected. Version 0.1.10 adds a reconnect grace timeout and seals the durable prefix as incomplete when no producer returns. It does not turn an interrupted run into a complete capture.

The earlier analyzer counted 277 `unexplained_velocity_change` anomalies. Correct correlation with the adapter's flattened actor/target fields links 103 velocity changes to observed contacts within one adapter step. **174 remain unresolved** and are kept in the report. They are not labeled as collisions without supporting callbacks.

In that 0.1.5 gameplay capture, a later health window reached 1.8008 ms capture-work p95 at a 20 ms fixed step, exceeding the 1.0 ms criterion; the 53.6163 ms maximum was below the 60 ms limit. The 0.1.8 optimized and queue-reservation paths, 0.1.9 writer retry, and 0.1.10 disconnect finalization have not passed a completed in-game REC-I measurement. The supplied 0.1.10 capture is a structural pass but fails the capture-work threshold; it also leaves `sample_phase_verified=false`. The map/mode remains unknown in those historical runs.

## Captured scope and limits

- Samples eligible locally owned Humans and local-master AI Humans/Titans. Remote player-controlled characters and AI on non-master clients are excluded.
- Discovers owner-linked Hooks from each Human's left/right HookUseable lists; samples Hook transform, state, hook point, and anchor. Hook transitions are sampled differences, not direct hook callbacks.
- Samples projectiles only when their owner passes the local ownership filter.
- Records Transform position/rotation. Linear/angular velocity comes only from a non-kinematic root Rigidbody; kinematic and transform-only objects are labeled separately.
- Samples Human/Titan state, AI/team, health, dead/grounded flags, current speed and animation, Human gas, Hook state, and the projectile game velocity field.
- Emits Human.OnCollisionEnter Harmony postfix events with callback provenance, relative velocity, impulse, contact count, and collider identity. This callback fired in the supplied run, but coverage is not complete and player-versus-player collisions are omitted.
- Polls active scene changes at FixedUpdate boundaries. Scene and Hook transition times are detection/sample times; brief transitions may be missed.
- Measures capture-work last/p95/max over a rolling 256-callback window. This covers discovery, sampling, serialization and queue submission, not total game frame time.

Entity first-seen lifecycle is inferred from the 0.5-second discovery census. Destruction is recorded when Unity's object-null state is observed; transient objects between censuses may be missed. IDs are stable within one run and are not cross-run identities.

The adapter reads Unity/game values on the Unity callback thread and hands primitive data to the pipe worker. It does not write transforms, physics properties, controls, or gameplay state. Sampling runs in Unity `FixedUpdate`, documented in Unity 2023.1 as occurring before physics calculations. The relative order among other `FixedUpdate` scripts is not set. The `fixed_update_pre_physics` label resolves the old “order unspecified” phase name; correlation with a controlled physics transition and M2 events is still required for `sample_phase_verified=true`.

Unavailable or unverified: moving world geometry, Titan-side collision callbacks, direct damage/death/rescue attribution callbacks, structured M2 controller decisions, complete actor/collision coverage, exact physics observation phase, and REC-I performance acceptance. Contact-based kill attribution remains an inference. Existing M2 logs are not promoted into complete decisions.

## Install

1. Close AoTTG2. Confirm BepInEx 6.0.0-be.791 generated BepInEx/interop for this exact installation. Follow the [BepInEx IL2CPP installation guide](https://docs.bepinex.dev/master/articles/user_guide/installation/unity_il2cpp.html); do not copy the H3VR Mono profile.
2. Extract the reviewed package to a local directory.
3. Run the guarded installer. It automatically removes a previous recorder install after verifying its receipt, DLL hashes, and folder contents. It refuses modified or unmanaged installations for manual review:

       .\scripts\install_flight_recorder.ps1 -GameRoot "C:\Path\To\AoTTG2" -PackageRoot "C:\Path\To\AoTTG2-FlightRecorder-0.1.12"

4. Leave BepInEx/config/org.aicadets.aottg2.flight-recorder.cfg at `Enabled = false` for the startup check. Launch to the menu, verify plug-in version and disabled-capture log entries, then close the game.
5. Copy `configs/flight-recorder-transport.example.json` to a private local config, set `recording_enabled=true`, and choose a new empty output directory. Start the receiver first:

       .\scripts\start_flight_recorder_receiver.ps1 -PackageRoot "C:\Local\Path\AoTTG2-FlightRecorder-0.1.12" -ConfigPath "%USERPROFILE%\Documents\AoTTG2\Recorders\flight-recorder-transport.json"

   `ConfigPath` must be the JSON file. A relative `output_dir` is resolved beside that file, and the launcher prints the resolved directory. For output in `Documents\AoTTG2\Recorders\recordings`, use the JSON in that `Recorders` folder, not the package's `configs` directory.

6. Set plug-in `Enabled = true` only for a private/solo session. Launch AoTTG2 and confirm version, run ID, and pipe handshake before entering the test. Follow [REC-I validation](REC_I_VALIDATION_BLOCKER.md).
7. After the game closes, set `Enabled = false` and analyze the run:

       .\runtime\python.exe .\tools\analyze_flight.py "C:\Local\Path\recordings\run-<run-id>" --out "C:\Local\Path\analysis"

The bundled receiver runs without changing PATH or installing system-wide Python. It uses a current-user DACL and rejects remote named-pipe clients; no external network or cloud telemetry is used. If the game disconnects without a stop message, the run is marked incomplete and is not resumed or overwritten.

## Rollback

Close the game and run the package's `remove_flight_recorder.ps1` against the same GameRoot. It validates the install receipt and hashes, refuses modified or unlisted files, and removes only the two recorder DLLs and receipt. BepInEx, loader files, generated interop, and user configuration remain separate.

## Validation boundary

The supplied 0.1.5 run proves a complete writer/transport recording and observed Human/Hook/Titan data. It gives strong but non-causal evidence consistent with a cadet kill. It does not prove direct damage attribution, M2 decision quality, or calibrated physics phase. Both the supplied 0.1.10 run and the installed 0.1.11 run fail the 1.0 ms p95 performance criterion; 0.1.12 removes discovery sorting but still needs an installed private-game performance retest. Timing calibration also remains open. See [REC-I validation](REC_I_VALIDATION_BLOCKER.md) and the repository's 2026-11-04 M2/recorder Validation Card for acceptance limits and rollback steps.
