# REC-I status: ready for private gameplay calibration

**Status:** The Unity-side adapter is compiled and packaged; the installed plugin is opt-in and currently configured with Enabled = false. Package 0.1.5 passed a main-menu runtime smoke. REC-I gameplay calibration itself remains unrun.

## What is ready

- Exact installation: x64 IL2CPP, Unity 2023.1.22f1, IL2CPP metadata 29.1.
- Loader: BepInEx 6.0.0-be.791 started on this installation and generated interop for the installed game.
- Adapter: BepInEx plugin compiled against that local interop. It is passive and opt-in.
- Local writer path: adapter → bounded local named pipe → Python receiver → existing FlightRecorderWriter → hashed aicadets.flight.v1 chunks.
- Level 2 final package 0.1.5 smoke: 1,982 ordered frames, one verified hashed chunk, capture_complete=true, zero drops, zero analyzer anomalies, graceful stop, and zero entities at the main menu. Eight events comprised seven producer-health samples and one sampled scene change. At fixedDeltaTime about 20 ms, the first five-second health window reported p95 capture work 0.7254 ms and maximum 103.9691 ms; later windows reported p95 0.1726–0.5526 ms and maxima 6.9426–12.7446 ms. These are menu/startup measurements with no actor load and do not establish mission performance.
- Level 3 needs the owner's short private session and the small local artifacts listed below.

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
    PERFORMANCE: Require zero transport/frame/control drops, zero unexplained step gaps, verified chunk hashes, capture_complete=true, and no analyzer anomalies. Health events report capture_work_ms_p95/max over the latest 256 callbacks. After the first startup health window, require steady-state p95 <= 5% of fixedDeltaTime and max <= 3x fixedDeltaTime. Preserve and report the first window separately. The final menu smoke's first window was p95 0.7254 ms / max 103.9691 ms; later windows were p95 0.1726–0.5526 ms / max 6.9426–12.7446 ms at about 20 ms fixedDeltaTime, with no entities. These callback-work values are not full frame-time measurements. Treat a steady-state threshold breach or visible sustained stutter/control delay during REC-I as stop-and-review, not a pass
    VIDEO: One short screen recording of the safe movement/hook sequence is enough to compare direction, stopping, and hook-state timing
    TRACE REVIEW: Run runtime/python.exe tools/analyze_flight.py on the run directory. Check run metadata, chunk_manifest.json hashes, ordered steps, gaps/drop counters, IDs/lifecycle evidence, phase, sampled scene/hook-transition evidence, health p95/max, and capture_complete
    STOP / ROLLBACK: Stop receiver cleanly; set Enabled=false after the game closes. If controls/stutter/loader errors appear, stop the session, preserve logs and incomplete trace, then run remove_flight_recorder.ps1. It removes only unchanged manifest-listed recorder DLLs and leaves BepInEx/interop untouched
    RETURN: Zip the run folder (chunk JSONL, chunk_manifest.json, metadata.json, writer_state.json), analysis output, BepInEx/LogOutput.log, receiver log, exact config with local paths redacted, short motion video, package SHA-256, and observed performance notes. Do not include game binaries or other players' data

### Acceptance boundaries

The first REC-I pass validates motion and passive snapshots. It does not validate M2 controller decisions, Titan damage, rescue behavior, or every collision type. An absent callback remains absent evidence; a velocity change is not promoted to a collision. Do not proceed to M2 diagnosis until integrity/drop checks pass and local Human/Hook/Titan coverage is visible.

## Rollback and current machine state

The plugin is installed only under BepInEx/plugins/AoTTG2FlightRecorder, with an install manifest hashing the two plugin DLLs. The game config is restored to Enabled = false. To disable, leave it false. To remove the plugin, close the game and run the package's remove_flight_recorder.ps1 against the same GameRoot; it refuses modified or unlisted files. BepInEx and generated interop are separate loader dependencies and are not removed by that plugin rollback script.
