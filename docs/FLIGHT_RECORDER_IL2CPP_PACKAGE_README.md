# AoTTG2 IL2CPP Flight Recorder package

**Build:** 0.1.6 candidate, compiled against interop generated from the installed AoTTG2 build

**Runtime:** x64, Unity 2023.1.22f1, IL2CPP metadata 29.1, BepInEx 6.0.0-be.791, .NET 6

**Capture default:** disabled

This opt-in package contains the game-side BepInEx IL2CPP plugin, bounded named-pipe producer, Python receiver/writer/analyzer, and a portable Python 3.14.10 x64 embeddable runtime with its license. It excludes AoTTG2 binaries, loader binaries, and generated/proprietary game interop. Version 0.1.6 serializes the immutable frame DTO directly into a bounded UTF-8 protocol envelope, removing an intermediate JSON string and parse/reserialize pass from Unity's callback. This optimization still needs a new installed-game performance measurement; it does not itself clear the gameplay performance gate.

This is a client startup plug-in, not an AoTTG Custom Logic `.cl` add-on selected in a lobby. Keep the game folder writable because BepInEx writes configuration, logs, and generated interop. The guarded recorder installer writes only its two DLLs and receipt into its dedicated plug-in folder.

## Latest gameplay capture

The owner-supplied 0.1.5 trace completed through the writer and transport: 56,970 ordered frame markers, 35/35 SHA-256-verified chunks, 779 events, 54 lifecycle records, and 27 entity IDs (6 Titans, 3 Humans, 18 Hooks). It had no declared drops or missing frame markers and `capture_complete=true`. It contains 209 observed Human collision callbacks and 340 sampled Hook state transitions. Sampling phase remains unverified.

The updated analyzer writes `kill_attributions.json`. It identifies one `strong_inferred_candidate`: a Titan changed from health 1/alive to 0/dead at t=894.299683, step 44,716, with a death state/animation, then was observed destroyed. An AI-controlled Human had 13 observed collisions with that Titan in the prior 3.56 seconds and an attack state/animation sampled near death. This is strong evidence consistent with the cadet getting the kill; no direct damage-source or correlated death callback was recorded, so causality remains inferred.

The earlier analyzer counted 277 `unexplained_velocity_change` anomalies. Correct correlation with the adapter's flattened actor/target fields links 103 velocity changes to observed contacts within one adapter step. **174 remain unresolved** and are kept in the report. They are not labeled as collisions without supporting callbacks.

In that 0.1.5 gameplay capture, a later health window reached 1.8008 ms capture-work p95 at a 20 ms fixed step, exceeding the 1.0 ms criterion; the 53.6163 ms maximum was below the 60 ms limit. The 0.1.6 optimized path has not been measured in-game. The map/mode remains unknown, and the sample phase is `fixed_update_pre_physics_order_unspecified`.

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

The adapter reads Unity/game values on the Unity callback thread and hands primitive data to the pipe worker. It does not write transforms, physics properties, controls, or gameplay state. Sampling runs in a pre-physics FixedUpdate callback, but order relative to AoTTG2 scripts is unknown.

Unavailable or unverified: moving world geometry, Titan-side collision callbacks, direct damage/death/rescue attribution callbacks, structured M2 controller decisions, complete actor/collision coverage, exact physics observation phase, and REC-I performance acceptance. Contact-based kill attribution remains an inference. Existing M2 logs are not promoted into complete decisions.

## Install

1. Close AoTTG2. Confirm BepInEx 6.0.0-be.791 generated BepInEx/interop for this exact installation. Follow the [BepInEx IL2CPP installation guide](https://docs.bepinex.dev/master/articles/user_guide/installation/unity_il2cpp.html); do not copy the H3VR Mono profile.
2. Extract the reviewed package to a local directory.
3. If the previous recorder install exists, close the game and remove it with the matching package's guarded `remove_flight_recorder.ps1`; do not overwrite an existing plugin folder. Then run:

       .\scripts\install_flight_recorder.ps1 -GameRoot "C:\Path\To\AoTTG2" -PackageRoot "C:\Path\To\AoTTG2-FlightRecorder-0.1.6"

4. Leave BepInEx/config/org.aicadets.aottg2.flight-recorder.cfg at `Enabled = false` for the startup check. Launch to the menu, verify plug-in version and disabled-capture log entries, then close the game.
5. Copy `configs/flight-recorder-transport.example.json` to a private local config, set `recording_enabled=true`, and choose a new empty output directory. Start the receiver first:

       .\scripts\start_flight_recorder_receiver.ps1 -PackageRoot "C:\Local\Path\AoTTG2-FlightRecorder-0.1.6" -ConfigPath "C:\Local\Path\flight-recorder-transport.json"

6. Set plug-in `Enabled = true` only for a private/solo session. Launch AoTTG2 and confirm version, run ID, and pipe handshake before entering the test. Follow [REC-I validation](REC_I_VALIDATION_BLOCKER.md).
7. After the game closes, set `Enabled = false` and analyze the run:

       .\runtime\python.exe .\tools\analyze_flight.py "C:\Local\Path\recordings\run-<run-id>" --out "C:\Local\Path\analysis"

The bundled receiver runs without changing PATH or installing system-wide Python. It uses a current-user DACL and rejects remote named-pipe clients; no external network or cloud telemetry is used. If the game disconnects without a stop message, the run is marked incomplete and is not resumed or overwritten.

## Rollback

Close the game and run the package's `remove_flight_recorder.ps1` against the same GameRoot. It validates the install receipt and hashes, refuses modified or unlisted files, and removes only the two recorder DLLs and receipt. BepInEx, loader files, generated interop, and user configuration remain separate.

## Validation boundary

The supplied 0.1.5 run proves a complete writer/transport recording and observed Human/Hook/Titan data. It gives strong but non-causal evidence consistent with a cadet kill. It does not prove direct damage attribution, M2 decision quality, or calibrated physics phase. The 0.1.5 p95 performance result failed the 1.0 ms criterion; the 0.1.6 direct serialization path must be measured in a new private gameplay capture. See [REC-I validation](REC_I_VALIDATION_BLOCKER.md) for the exact card, acceptance limits, and rollback steps.
