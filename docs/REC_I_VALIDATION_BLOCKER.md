# REC-I status: partial gameplay capture; calibration not accepted

**Status:** The writer and transport completed a 19m09s gameplay-length run: 56,970 ordered frames, 779 events, 54 lifecycle records, 35/35 hash-verified chunks, `capture_complete=true`, and zero declared drops or incomplete reasons. Human, Hook, and Titan samples plus actual Human.OnCollisionEnter callbacks were observed. REC-I is still partial and not accepted: sample phase is unverified; the analyzer reports 277 `unexplained_velocity_change` anomalies; and a later health window reached 1.8008 ms p95 against the 1.0 ms criterion at 20 ms fixedDeltaTime. The 53.6163 ms window maximum is below the 60 ms limit. The archive does not identify map/mode, and no video was supplied to calibrate timing or motion. The package default remains disabled; the local plugin was opted in for this run.

## What is ready

- Exact installation: x64 IL2CPP, Unity 2023.1.22f1, IL2CPP metadata 29.1.
- Loader: BepInEx 6.0.0-be.791 started on this installation and generated interop for the installed game.
- Adapter: BepInEx plugin compiled against that local interop. It is passive and opt-in.
- Local writer path: adapter → bounded local named pipe → Python receiver → existing FlightRecorderWriter → hashed aicadets.flight.v1 chunks.
- Level 2 earlier 0.1.5 main-menu smoke (same adapter source, before deterministic-build project properties): 1,982 ordered frames, one verified hashed chunk, `capture_complete=true`, zero drops, zero analyzer anomalies, graceful stop, and zero entities. Eight events comprised seven producer-health samples and one sampled scene change. At fixedDeltaTime about 20 ms, the first five-second health window reported p95 capture work 0.7254 ms and maximum 103.9691 ms; later windows reported p95 0.1726–0.5526 ms and maxima 6.9426–12.7446 ms. These are menu/startup measurements with no actor load and do not establish mission performance.
- Final deterministic package 0.1.5 menu retry: 5,717 frames and 23 events; its chunk verified, but the run ended `receiver_interrupted` and `capture_complete=false` when the game and BepInEx console closed together.
- Supplied gameplay-length trace: 27 entity IDs (6 Titans, 3 Humans, 18 ODM Hooks), 209 observed collision records, 340 sampled hook-state transitions, zero declared drops, zero missing frame markers, and 100% manifest frame coverage.
- One Titan changed from sampled health 1/dead false to health 0/dead true with `Dead` / `die.front`, then was observed destroyed. An AI-controlled Human had 13 observed collision callbacks against that Titan in the preceding 3.56 seconds and was in `Attack` / `attack1_hook_r2` near the death sample. This strongly suggests a cadet kill, but no damage-source or correlated death event was recorded, so attribution is not proven.
- The supplied trace passes the integrity/drop and basic Human/Hook/Titan visibility gates and can support exploratory trajectory/contact review. Calibration still needs a short video cross-check, phase review, and resolution of the p95/anomaly findings.

The H3VR BepInEx 5 Mono files were not copied. AoTTG2 uses its separately installed IL2CPP loader. The recorder package excludes game, loader, and generated interop binaries.

## REC-I validation card

    SESSION: REC-I short passive capture
    SOURCE: codex/flight-recorder-il2cpp-adapter; adapter/build commit 94e033699b0f67387d030e810e35fa422b81dd55
    PACKAGE: AoTTG2 Flight Recorder 0.1.5, x64, Unity 2023.1.22f1, BepInEx 6.0.0-be.791, .NET 6
    GAME CONFIG: BepInEx/config/org.aicadets.aottg2.flight-recorder.cfg; Enabled=true only for this capture, then restore false
    RECEIVER: Copy the example JSON to a new local config, set recording_enabled=true and a new empty output directory; start scripts/start_flight_recorder_receiver.ps1 with that config and verify the pipe is listening
    ADD-ONS: BepInEx Flight Recorder only. Disable AICadetsWaveCadet, CommandPanel, M2Watcher, Probe, Traversal, all other experimental .cl add-ons, and unrelated plugins
    SESSION PRIVACY: Offline/solo if available, otherwise a private master-host lobby with no other participants. Never use a public lobby or capture other players' data
    MODE / MAP: City 1 / Training / Waves with vanilla mission logic; create at least one Titan if this mode supports local/private play. Do not enable M2 AI gameplay code
    SAFE ACTION: From a safe spawn, record 30–60 seconds: stand and rotate briefly; make one short walk/run in open space; launch one ODM hook at static architecture, hold/reattach briefly, then release. Avoid combat for this first movement pass
    WARM-UP: Capture at the main menu for at least 10 simulation seconds (two health windows) before entering the private session. Keep the first window as startup data; evaluate later windows as steady state
    LAUNCH ORDER: (1) confirm game is closed and Enabled=false; (2) set receiver recording_enabled=true and start receiver; (3) set only game Enabled=true; (4) launch AoTTG2; (5) verify plugin/run/pipe handshake at menu; (6) enter only the private vanilla session
    FIRST 30–60 SECONDS: Check frames at measured fixed interval; active scene change has sampled-poll evidence; local Human ID is stable; Hook appears after census and its state/anchor fields change; Titan appears if spawned and owned by local master; collision event appears only if Human.OnCollisionEnter fires; no controls or physics are altered
    EXPECTED DATA: About 50 adapter callbacks per simulation second when fixedDeltaTime is about 0.02 seconds. Coverage is limited to allowed Humans, local-master AI Titans, owner-linked Hooks, and allowed projectiles. First-seen spawn is inferred by census; sampled Hook/scene transitions are not direct callback events
    PERFORMANCE: Require zero transport/frame/control drops, zero unexplained step gaps, verified chunk hashes, capture_complete=true, and no unresolved analyzer anomalies. Health events report capture_work_ms_p95/max over the latest 256 callbacks. After the first startup health window, require steady-state p95 <= 5% of fixedDeltaTime and max <= 3x fixedDeltaTime. Preserve the first window separately. The latest 20 ms-step gameplay run had later-window p95 up to 1.8008 ms (above the 1.0 ms limit) and maximum up to 53.6163 ms (below the 60 ms limit); it also had 277 unexplained_velocity_change anomalies requiring review. These are callback-work values, not full frame time. Treat threshold breaches or visible sustained stutter/control delay as stop-and-review, not a pass.
    VIDEO: No video accompanied the latest trace. A short screen recording remains needed to compare direction, stopping, hook timing, and observation phase.
    TRACE REVIEW: Run runtime/python.exe tools/analyze_flight.py on the run directory or ZIP. Check run metadata, chunk_manifest.json hashes, ordered steps, gaps/drop counters, IDs/lifecycle evidence, phase, sampled scene/hook-transition evidence, health p95/max, and capture_complete
    STOP / ROLLBACK: Stop receiver cleanly; set Enabled=false after the game closes. If controls/stutter/loader errors appear, stop the session, preserve logs and incomplete trace, then run remove_flight_recorder.ps1. It removes only unchanged manifest-listed recorder DLLs and leaves BepInEx/interop untouched
    RETURN: Zip the run folder (chunk JSONL, chunk_manifest.json, metadata.json, writer_state.json), analysis output, BepInEx/LogOutput.log, receiver log, exact config with local paths redacted, short motion video, package SHA-256, and observed performance notes. Do not include game binaries or other players' data

### Acceptance boundaries

The supplied trace passes integrity/drop and basic Human/Hook/Titan visibility checks and can support exploratory physical-trajectory/contact review. It does not validate M2 decisions or prove damage attribution. Do not treat REC-I as passed until observation phase, video cross-check, performance thresholds, and unexplained motion anomalies are resolved. An absent damage event remains absent evidence; a velocity change is not promoted to a collision.

## Rollback and current machine state

The plugin is installed only under BepInEx/plugins/AoTTG2FlightRecorder, with an install manifest hashing the two plugin DLLs. The local game config is currently Enabled = true after this capture; set it false when not recording. The receiver is stopped after the run's graceful stop, so start it before the next game launch. To remove the plugin, close the game and run the package's remove_flight_recorder.ps1 against the same GameRoot; it refuses modified or unlisted files. BepInEx and generated interop are separate loader dependencies and are not removed by that plugin rollback script.
