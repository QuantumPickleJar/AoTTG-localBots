# AoTTG2 IL2CPP Flight Recorder package

**Build:** 0.1.17 disabled-hook sampling optimization candidate, compiled against interop generated from the installed AoTTG2 build

**Runtime:** x64, Unity 2023.1.22f1, IL2CPP metadata 29.1, BepInEx 6.0.0-be.791, .NET 6

**Capture default:** disabled

This opt-in package contains the game-side BepInEx IL2CPP plugin, bounded named-pipe producer, Python receiver/writer/analyzer, and a portable Python 3.14.10 x64 embeddable runtime with its license. It excludes AoTTG2 binaries, loader binaries, and generated/proprietary game interop. Versions 0.1.11–0.1.15 retained the `aicadets.flight.v1` fields, local transport, and queue/recovery behavior while successively reducing allocations and adding measured callback stages. Installed 0.1.15 run 06 passed the steady-state p95 limit but failed the unchanged 60 ms maximum-sample gate because a periodic discovery sample reached 79.0452 ms. Version 0.1.16 excludes inactive objects from periodic scene discovery while continuing to sample already tracked entities; its fresh installed run 07 still fails the p95 gate. Version 0.1.17 keeps per-step hook pose/state records but skips hook-point, anchor, and character queries for `Disabled` hooks. It is a candidate only; no runtime improvement is claimed until a fresh installed capture passes every gate.

## Installed 0.1.16 capture — run 07 (interim; capture still open)

The user confirmed a private master-host City 1 / Training / Waves match with one human-controlled participant, one owned cadet, one ordinary Titan, and the three required M2 add-ons. After a fresh game launch, BepInEx loaded plugin 0.1.16 and the local receiver accepted hello sequence 1. The user issued one Direct Engage order. At the latest live snapshot, 109,907 frame records were parsed with contiguous ordinals and exact 0.0199999929-second spacing; 437 producer-health records included 435 post-15-second windows. Capture is not finalized, chunk hashes are not yet final-verified, and clean stop is pending.

The interim performance result is a **fail**: 22 of 435 post-15-second windows exceed the unchanged 1.0 ms p95 limit, with a worst p95 of 1.4775 ms. The largest reported individual sample is 59.9965 ms, below 60 ms at this snapshot. No frame or control drops were reported. Queue high-water was 11 entries / 175,876 bytes, below the configured 512 entries / 4 MiB. The sample also contains 294 observed collision callbacks on the AI cadet; 291 have a same-step sample before the callback and a same-step actor sample. These are phase-calibration candidates, not a final verified timing result until the controlled calibration and clean final report are documented.

M2 watcher output in this capture stopped at game time 36.16 in `WaitLanding`, after traversal failed to find a suitable anchor; it recorded real approach movement and positive target progress, but no grounded `ground_route_blocked` or reposition retry. Grounded movement/recovery remains untested in this run. Do not infer attack, damage, kill, or complete actor coverage from this recorder capture.

Version 0.1.17 skips the disabled-hook point/anchor/character API reads while preserving every fixed-step frame and sampled Hook.State. Its source/build checks and a new installed-runtime capture are pending. Run 07 raw chunks and watcher files remain local until the user exits normally and finalization and analysis complete.

## Installed 0.1.15 capture — run 06

After a clean restart, BepInEx loaded plugin 0.1.15 and the local receiver accepted hello sequence 1. The user operated a private master-host M2 lobby and later exited normally. The writer finalized `capture_complete=true` with 24,247 frames, 10/10 hash-verified chunks, zero missing frame steps, zero declared drops, no malformed/incomplete/fatal records, and clean producer/receiver stop. Sealed local ZIP SHA-256: `F24188704D6AFE4937C964EB410C3D90BEE076C5950292A820427EFAF120C5C3`.

Performance is a **fail**: 0 of 95 post-15-second p95 windows exceeded 1.0 ms and the worst p95 was 0.9527 ms, but the maximum capture-work sample was 81.3031 ms (limit 60 ms). The worst rolling discovery sample was 79.0452 ms; frame-sampling maximum was 15.2999 ms and serialization/queue maximum was 47.8422 ms. The captured active plugin config (`artifacts-54ba9419295a4ec8b05d5769b1bc9990/logs/recorder-plugin-config-active-run06.cfg`, SHA-256 `7F6B4503E22F7A424BEC6195E0906DD21150C411E56A35CD9DEFFEDAD945D682`) sets producer limits to 512 entries / 4 MiB. Re-analysis with those exact limits is retained at `analysis-configured-queue-limits/report.md`: high-water was 5 entries / 64,995 bytes, within limits, with zero drops. Writer high-water was 2 entries / 43,824 bytes against 256 entries / 64 MiB. Queue bounds pass; the capture-work sample gate fails.

Timing remains **unverified**: phase is `fixed_update_pre_physics`, `sample_phase_verified=false`; 24,247 ordinals have no frame-step gaps or time mismatches, fixed delta is `0.019999992`, wall time is monotonic, game/wall correlation is `0.9999861078`, and slope is `1.0066108918`. The run did not include a controlled physics-phase calibration or M2 watcher events in the recorder trace. Same-step collision candidates do not calibrate phase. The capture tracked seven entities and does not establish complete actor coverage, collision/attack causality, damage, or kills. The active config was restored to `Enabled=false`; post-run SHA-256 is `EF7D38689B5C55D7C24EAA3BAEB6B6ACD460509A5F3815D2897442EDC7AE162B`.

## Prior installed 0.1.14 capture

Run `72c1c04816b040e984ba25dde909c7b0` loaded 0.1.14 after a clean restart; BepInEx logged Unity `2023.1.22f1`, Chainloader startup completed, and the local receiver accepted hello sequence 1. After normal game exit, the receiver accepted stop sequence 39,044. The finalized writer state is `capture_complete=true`, `is_final=true`, with 37,706 durable frames, 37/37 chunks, and 1,294 events. The sealed local ZIP SHA-256 is `6F3AAED3BEA5639B698CA3444D8993361ED32351728AD3759E911CE63CF26970`; every chunk hash was reverified from within the ZIP against its manifest. There are no fixed-step gaps, fixed-time mismatches, dropped frames/entity samples, malformed records, incomplete reasons, or writer fatal error. Producer and writer queue highs remain below their configured caps. These are structural, package, load, and shutdown passes only.

The performance gate failed: 77 of 149 post-15-second health windows exceeded 1.0 ms p95; worst p95 was 4.9976 ms and the maximum capture-work sample was 131.6034 ms. Rolling stage maxima were 121.3798 ms for frame sampling, 33.987 ms for discovery, and 38.3894 ms for serialization/queue. Timing continuity was clean (37,706 ordinals, fixed delta `0.019999992`, no game-time mismatch, wall-clock monotonic, correlation `0.9999893952`, slope `1.0032651585`), but metadata remains `fixed_update_pre_physics`, `sample_phase_verified=false`. No independent controlled transition or M2 controller event was present; the 341 candidate and 344 same-step-before-callback collision observations do not establish phase.

The user-operated watcher recorded Direct pursuit and sustained progress for one cadet against one Titan, but this is separate gameplay evidence. No recorder actor-coverage, collision causality, attack causality, damage, or kill claim follows from this capture. Raw run ZIP, analysis, watcher files, and game logs remain local in the run05 artifact directory. The recorder opt-in setting is restored to `Enabled = false`.

## Previous installed 0.1.13 capture

Run `0f641e245f0f4c0a9c3dab23d08c355e` loaded the installed plugin after a clean restart, connected to the local receiver, and finalized after the game exited. The writer accepted 24,846 durable frames and stopped cleanly; 24/24 chunks validate, frame coverage is 1.0, and there are no frame-step gaps, fixed-time mismatches, dropped frames/entity samples, source-missing frames, queue overflows, or fatal writer errors. Queue high-water stayed within configured bounds.

The performance gate failed: 51 of 97 post-15-second health windows exceeded 1.0 ms p95; worst p95 was 4.311 ms and the maximum individual capture-work sample was 87.7007 ms. Timing continuity was structurally clean, but the phase is unverified: the metadata says `fixed_update_pre_physics` and `sample_phase_verified=false`. No controlled independent transition calibrated the phase. Recorder evidence does not establish complete actor coverage, collision or attack causality, damage, or kills. The 0.1.14 optimization candidate was followed by the 0.1.15 source candidate; neither is accepted until an installed actor-loaded run passes unchanged gates.

The 0.1.11 clean-start run `1ad84008622a4d4d9e06cae2a25ffac6` loaded and stopped cleanly with `capture_complete=true`, 39,509 frames, one verified chunk, no frame gaps or declared drops, and bounded queues. It tracked zero entities and had no M2 events, so it was not an M2 workload or phase-calibration run. Of 156 producer-health windows after 15 monotonic seconds, 2 exceeded the 1.0 ms p95 limit; the worst p95 was 2.8658 ms and the worst reported individual sample was 91.2873 ms. The performance gate therefore failed. The `fixed_update_pre_physics` phase label is descriptive only; `sample_phase_verified=false` remains until a controlled natural physics transition establishes phase.

The 0.1.12 user-operated actor-loaded run `eefc8131fe93455d89bca3d5261af70c` loaded after a clean restart and stopped cleanly. It produced 17,123 frames in 16 hash-verified chunks, 1.0 frame coverage, 1,072 events, zero frame gaps, zero declared drops, and `capture_complete=true`. It tracked 28 entities, including a Human and Titan. Performance failed: 14/67 post-15-second health windows exceeded 1.0 ms p95; worst p95 was 2.8867 ms and maximum sample was 59.6039 ms. The producer and writer queues remained bounded, with no drops or fatal errors. Timing continuity was clean (0.019999992-second fixed delta, no ordinal/time mismatches, monotonic wall clock, Pearson correlation 0.9999706711, slope 1.0086115), but the run was not a controlled phase calibration; `sample_phase_verified=false` remains. The session was confirmed private with only the owner present. Active add-ons, map/mode, host role, and effective driver were not independently observed.

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
- Measures capture-work last/p95/max over a rolling 256-callback window. Version 0.1.13 also reports discovery, frame-sampling, and serialization/queue stage p95/max diagnostics. Version 0.1.14 samples `GetCurrentAnimation()` at most every five fixed steps and records the source step. Version 0.1.15 keeps the scope cache step-tagged, reduces the frame buffer estimate, and measures periodic health serialization/queueing as callback work; each health record reports the ring before its own callback sample is appended. Stage readings and lower-rate optional fields do not replace or weaken the gate and do not measure total game frame time.

Entity first-seen lifecycle is inferred from the 0.5-second discovery census. Inactive objects are excluded from new discovery in 0.1.16 and may first appear after becoming active; already tracked objects remain sampled until destruction or capture-scope exit. Transient objects between censuses may be missed. Disabled Hooks retain per-step pose and state samples, while optional hook-point, anchor, and character fields are omitted until the Hook.State becomes active. IDs are stable within one run and are not cross-run identities.

The adapter reads Unity/game values on the Unity callback thread and hands primitive data to the pipe worker. It does not write transforms, physics properties, controls, or gameplay state. Sampling runs in Unity `FixedUpdate`; Unity documents physics calculations after `FixedUpdate` when using the `FixedUpdate` simulation mode. Version 0.1.13 records the actual `Physics.simulationMode` string. Relative ordering among other `FixedUpdate` scripts remains unspecified. The runtime phase label and simulation mode alone do not calibrate actor samples against a physical transition; keep `sample_phase_verified=false` until a controlled natural transition is reproducibly correlated.

Unavailable or unverified: moving world geometry, Titan-side collision callbacks, direct damage/death/rescue attribution callbacks, structured M2 controller decisions, complete actor/collision coverage, exact physics observation phase, and REC-I performance acceptance. Contact-based kill attribution remains an inference. Existing M2 logs are not promoted into complete decisions.

## Install

1. Close AoTTG2. Confirm BepInEx 6.0.0-be.791 generated BepInEx/interop for this exact installation. Follow the [BepInEx IL2CPP installation guide](https://docs.bepinex.dev/master/articles/user_guide/installation/unity_il2cpp.html); do not copy the H3VR Mono profile.
2. Extract the reviewed package to a local directory.
3. Run the guarded installer. It automatically removes a previous recorder install after verifying its receipt, DLL hashes, and folder contents. It refuses modified or unmanaged installations for manual review:

       .\scripts\install_flight_recorder.ps1 -GameRoot "C:\Path\To\AoTTG2" -PackageRoot "C:\Path\To\AoTTG2-FlightRecorder-0.1.17"

4. Leave BepInEx/config/org.aicadets.aottg2.flight-recorder.cfg at `Enabled = false` for the startup check. Launch to the menu, verify plug-in version and disabled-capture log entries, then close the game.
5. Copy `configs/flight-recorder-transport.example.json` to a private local config, set `recording_enabled=true`, and choose a new empty output directory. Start the receiver first:

       .\scripts\start_flight_recorder_receiver.ps1 -PackageRoot "C:\Local\Path\AoTTG2-FlightRecorder-0.1.17" -ConfigPath "%USERPROFILE%\Documents\AoTTG2\Recorders\flight-recorder-transport.json"

   `ConfigPath` must be the JSON file. A relative `output_dir` is resolved beside that file, and the launcher prints the resolved directory. For output in `Documents\AoTTG2\Recorders\recordings`, use the JSON in that `Recorders` folder, not the package's `configs` directory.

6. Set plug-in `Enabled = true` only for a private/solo session. Launch AoTTG2 and confirm version, run ID, and pipe handshake before entering the test. Follow [REC-I validation](REC_I_VALIDATION_BLOCKER.md).
7. After the game closes, set `Enabled = false` and analyze the run:

       .\runtime\python.exe .\tools\analyze_flight.py "C:\Local\Path\recordings\run-<run-id>" --out "C:\Local\Path\analysis"

   To check the game-side producer queue against its configured caps, also pass `--producer-queue-capacity` and `--producer-queue-max-bytes` from the exact recorder config used for that run. The report distinguishes those readings from the receiver writer queue. If the limits are not supplied, producer queue boundedness remains unverified.

The bundled receiver runs without changing PATH or installing system-wide Python. It uses a current-user DACL and rejects remote named-pipe clients; no external network or cloud telemetry is used. If the game disconnects without a stop message, the run is marked incomplete and is not resumed or overwritten.

## Rollback

Close the game and run the package's `remove_flight_recorder.ps1` against the same GameRoot. It validates the install receipt and hashes, refuses modified or unlisted files, and removes only the two recorder DLLs and receipt. BepInEx, loader files, generated interop, and user configuration remain separate.

## Validation boundary

The supplied 0.1.5 run proves a complete writer/transport recording and observed Human/Hook/Titan data. It does not prove direct damage attribution, M2 decision quality, or calibrated physics phase. Installed 0.1.11 through 0.1.15 runs do not all pass the unchanged performance gates; run 06 on 0.1.15 passed steady-state p95 and producer/writer queue bounds, but exceeded the 60 ms individual-sample limit. Installed 0.1.16 run 07 is still open and its interim analysis fails the 1.0 ms p95 gate. Its same-step collision records provide timing-calibration candidates, but the final controlled calibration and report remain pending. Version 0.1.17 is a disabled-hook sampling optimization candidate; it has no installed-runtime result yet. See [REC-I validation](REC_I_VALIDATION_BLOCKER.md) and the M2/recorder Validation Cards for acceptance limits and rollback steps.
