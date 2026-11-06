# AoTTG2 IL2CPP Flight Recorder package

**Build:** 0.1.18 cached transform/scene/owner hot-path optimization candidate, compiled against interop generated from the installed AoTTG2 build

**Runtime:** x64, Unity 2023.1.22f1, IL2CPP metadata 29.1, BepInEx 6.0.0-be.791, .NET 6

**Capture default:** disabled

This opt-in package contains the game-side BepInEx IL2CPP plugin, bounded named-pipe producer, Python receiver/writer/analyzer, and a portable Python 3.14.10 x64 embeddable runtime with its license. It excludes AoTTG2 binaries, loader binaries, and generated/proprietary game interop. Versions 0.1.11–0.1.15 retained the `aicadets.flight.v1` fields, local transport, and queue/recovery behavior while successively reducing allocations and adding measured callback stages. Installed 0.1.15 run 06 passed the steady-state p95 limit but failed the unchanged 60 ms maximum-sample gate because a periodic discovery sample reached 79.0452 ms. Version 0.1.16 excludes inactive objects from periodic scene discovery while continuing to sample already tracked entities; installed run 07 failed the p95 gate. Version 0.1.17 preserves per-step hook pose/state records while skipping hook-point, anchor, and character queries for `Disabled` hooks; installed run 08 completed structurally but failed both performance limits. Version 0.1.18 caches tracked transforms, stable scene names, and per-step owner-scope results to reduce repeated Unity/IL2CPP work. It is a candidate only; no runtime improvement is claimed until a fresh installed capture passes every unchanged gate.

## Installed 0.1.17 capture — run 08 (complete; performance and timing gates failed)

The user confirmed a private master-host City 1 / Training / Waves lobby, Wave 1 Titan count 1, one human-controlled participant, one owned cadet, one ordinary Titan, and exactly the WaveCadet, CommandPanel, and M2Watcher add-ons. The freshly installed 0.1.17 plugin loaded on Unity 2023.1.22f1, connected to the local receiver, and stopped cleanly after normal game exit. Run `b30fafba21f64f548a79366901fa2eaa` finalized `capture_complete=true` with 78,416 frames, 579 events, 50/50 hash-verified chunks, no missing steps or time mismatches, zero dropped frames/entity samples/control messages, and no fatal or storage errors. Producer and writer queue high-water marks were 8 entries / 111,034 bytes and 3 / 108,777 bytes, within configured 512 / 4 MiB and 256 / 64 MiB limits.

Performance **failed**: 5 of 311 post-15-second health windows exceeded 1.0 ms p95, the worst p95 was 1.2564 ms, and the maximum individual capture-work sample was 77.8959 ms (60 ms limit). Timing remains unverified: metadata reports `fixed_update_pre_physics` and `sample_phase_verified=false`. The analyzer found 78 calibration candidates and 80 same-step sample-before-collision links, but no controlled independent calibration was performed. The run has clean fixed-step and wall-clock continuity; continuity does not establish sample phase.

The recorder reported scene `Startup`, sampled Humans and ODM hooks, and had no Titan samples or M2 watcher/controller events. The user independently reported that the cadet remained stationary after one `Engage + Direct` command. The installed WaveCadet file predates the focused recovery source change, and the recorder has no sampled target; this is an observed movement failure for the installed version but does not test the new recovery candidate or establish target geometry. No retry, Hold, Engine comparison, attack, damage, death, or watcher persistence result is claimed. The completed local Validation Card, analysis, raw chunks, logs, rollback copies, and sealed ZIP remain on the user's machine; raw files are not uploaded with this package.

Run 08 did not include controlled timing calibration. For the next run, record before the M2 order; the user performs one normal in-game jump and visibly confirms landing; then correlate `Human.OnCollisionEnter(UnityEngine.Collision)` with its fixed-step ordinal, same-step and following-step samples, vertical position/velocity, game time, and monotonic wall time. Compare the corresponding M2 watcher/controller event time when available. Establish a phase only if the independently observed transition and callback/sample ordering agree reproducibly. Until then, keep `sample_phase_verified=false` and PR #16 open.

## Installed 0.1.16 capture — run 07 (completed; gates failed)

The user confirmed a private master-host City 1 / Training / Waves match with one human-controlled participant, one owned cadet, one ordinary Titan, and the three required M2 add-ons. After a fresh game launch, BepInEx loaded plugin 0.1.16 and the local receiver accepted hello sequence 1. Run `ad80bbf379bd4ff9ba36c64172cd8b71` finalized after normal game exit with `capture_complete=true`, 172,813 frames, 123/123 hash-verified chunks, 2,190 events, no frame gaps/time mismatches, zero declared drops, and clean producer/receiver shutdown.

The performance result is a **fail**: 36 of 687 post-15-second windows exceeded the unchanged 1.0 ms p95 limit, with a worst p95 of 1.4775 ms. The maximum reported individual sample was 59.9965 ms, below the 60 ms limit. Producer queue high-water was 13 entries / 175,876 bytes; writer high-water was 32 entries / 1,345,940 bytes. Both were within configured limits with zero drops. The sample also contains 294 observed collision callbacks; 291 have same-step sample-before-callback links. These are candidates, not a calibration.

M2 watcher output in this capture stopped at game time 36.16 in `WaitLanding`, after traversal failed to find a suitable anchor; it recorded real approach movement and positive target progress, but no grounded `ground_route_blocked` or reposition retry. Grounded movement/recovery remains untested in this run. Do not infer attack, damage, kill, or complete actor coverage from this recorder capture.

Version 0.1.17 skips disabled-hook point/anchor/character API reads while preserving every fixed-step frame and sampled Hook.State. Run 07 raw chunks, reports, and logs remain local.

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

       .\scripts\install_flight_recorder.ps1 -GameRoot "C:\Path\To\AoTTG2" -PackageRoot "C:\Path\To\AoTTG2-FlightRecorder-0.1.18"

4. Leave BepInEx/config/org.aicadets.aottg2.flight-recorder.cfg at `Enabled = false` for the startup check. Launch to the menu, verify plug-in version and disabled-capture log entries, then close the game.
5. Copy `configs/flight-recorder-transport.example.json` to a private local config, set `recording_enabled=true`, and choose a new empty output directory. Start the receiver first:

       .\scripts\start_flight_recorder_receiver.ps1 -PackageRoot "C:\Local\Path\AoTTG2-FlightRecorder-0.1.18" -ConfigPath "%USERPROFILE%\Documents\AoTTG2\Recorders\flight-recorder-transport.json"

   `ConfigPath` must be the JSON file. A relative `output_dir` is resolved beside that file, and the launcher prints the resolved directory. For output in `Documents\AoTTG2\Recorders\recordings`, use the JSON in that `Recorders` folder, not the package's `configs` directory.

6. Set plug-in `Enabled = true` only for a private/solo session. Launch AoTTG2 and confirm version, run ID, and pipe handshake before entering the test. Follow [REC-I validation](REC_I_VALIDATION_BLOCKER.md).
7. After the game closes, set `Enabled = false` and analyze the run:

       .\runtime\python.exe .\tools\analyze_flight.py "C:\Local\Path\recordings\run-<run-id>" --out "C:\Local\Path\analysis"

   To check the game-side producer queue against its configured caps, also pass `--producer-queue-capacity` and `--producer-queue-max-bytes` from the exact recorder config used for that run. The report distinguishes those readings from the receiver writer queue. If the limits are not supplied, producer queue boundedness remains unverified.

The bundled receiver runs without changing PATH or installing system-wide Python. It uses a current-user DACL and rejects remote named-pipe clients; no external network or cloud telemetry is used. If the game disconnects without a stop message, the run is marked incomplete and is not resumed or overwritten.

## Rollback

Close the game and run the package's `remove_flight_recorder.ps1` against the same GameRoot. It validates the install receipt and hashes, refuses modified or unlisted files, and removes only the two recorder DLLs and receipt. BepInEx, loader files, generated interop, and user configuration remain separate.

## Validation boundary

Installed 0.1.17 run 08 completed structurally but failed the unchanged 1.0 ms p95 and 60 ms maximum-sample gates; `sample_phase_verified=false` remains. Its stationary-cadet observation used an older installed WaveCadet build and has no Titan or M2 watcher sample. Version 0.1.18 is a cached hot-path optimization candidate and still requires an installed capture. Recorder evidence does not prove complete actor coverage, collision or attack causality, damage, or kills. See [REC-I validation](REC_I_VALIDATION_BLOCKER.md) and the M2/recorder Validation Cards for acceptance limits and rollback steps.
