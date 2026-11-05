# REC-I status: capture attribution improved; performance gate remains open

## 2026-11-04 status update

The supplied 0.1.10 run is structurally complete (20 verified chunks, 20,878 frames, 901 events, no declared drops or frame-step gaps, about 417.54 seconds), but it fails performance: 59 of 81 post-15-second health windows exceed 1.0 ms p95; the worst p95 is 5.7656 ms and the worst individual sample is 65.7773 ms. Its phase is `fixed_update_pre_physics_order_unspecified` and `sample_phase_verified=false`; ZIP completeness does not calibrate timing.

The 0.1.11 candidate reuses the per-entity sample DTOs, arrays, extra payload, and frame list, and labels samples `fixed_update_pre_physics`. Unity 2023.1 documents that physics calculations occur after `FixedUpdate` ([API](https://docs.unity3d.com/2023.1/Documentation/ScriptReference/MonoBehaviour.FixedUpdate.html), [execution-order manual](https://docs.unity3d.com/2023.1/Documentation/Manual/ExecutionOrder.html)). The controlled runtime correlation with an ordinary physics transition and same-step M2 watcher/controller events is still pending. Keep `sample_phase_verified=false` and PR #16 open until that calibration and the performance/package gates pass.

## Current evidence

The owner-supplied 0.1.5 gameplay recording completed cleanly through the writer and transport: 56,970 ordered frame markers, 779 events, 54 lifecycle records, 35/35 SHA-256-verified chunks, 27 entity IDs, no reported frame or entity drops, and `capture_complete=true`. It contains Humans, Titans, Hooks, 209 observed Human collision callbacks, and 340 sampled Hook state transitions.

The updated analyzer now writes `kill_attributions.json`. Reanalysis finds one **strong inferred candidate** for a sampled Titan death at t=894.299683, step 44,716: Titan health changed 1→0 and its dead flag/state/death animation changed; an AI-controlled Human had 13 observed collision callbacks with that Titan from t=890.3597 to 893.9197 and an attack state/animation sampled near the death. The trace contains no direct damage-source or correlated death callback, so the recorder reports inference, not proven causality.

The prior analyzer counted 277 `unexplained_velocity_change` findings because it did not resolve the adapter's flattened actor/target fields. The corrected correlation links 103 of those velocity changes to observed contact callbacks within one adapter step. **174 remain unresolved** and stay visible in the report; they are not re-labeled as collisions or explained by assumption.

The same 0.1.5 capture's later health window reached 1.8008 ms capture-work p95 at a 20 ms fixed step, above the 1.0 ms criterion; maximum was 53.6163 ms, below the 60 ms limit. A later installed-game log from plugin 0.1.5 reports `control_reserve_exhausted_before_frame_gap`; treat that separate attempt as incomplete. A subsequent 0.1.8 run connected and wrote 8,197 durable frames and 282 events in six verified chunks, but stopped incomplete after `PermissionError` replacing `writer_state.json`; one submitted frame was not durable. A 0.1.9 installed-game session wrote many verified chunks, but the game disconnected without a stop envelope and the receiver left its latest chunk partial. Version 0.1.10 retains the earlier writer fixes and adds a five-second reconnect window; it seals the durable prefix and marks the run incomplete if the producer does not return. **No completed 0.1.10 gameplay performance result exists yet.** Sample phase remains `fixed_update_pre_physics_order_unspecified`, map/mode is unknown, and no video was included.

The 0.1.7 DLLs are now installed on disk in the inspected game copy, but the current game process started before installation and logged `0 plugins to load`. Runtime loading remains unconfirmed until the game is restarted.

## Current implementation state

- PR #15 is merged into `main`; PR #16 targets `main` and retains the adapter-only diff.
- The offline analyzer emits `kill_attributions.json` and a report section. It uses sampled alive→dead transitions, observed target-specific collisions, sampled AI/attack state, and explicitly correlated direct events when present. It preserves the provenance of each signal and labels contact-based attribution as inference.
- The Unity adapter and writer schema remain unchanged by the analyzer output. No M2 gameplay code or installed game file is changed by this work.
- The current candidate package version is 0.1.11. Keep game recording disabled except during the deliberately opted-in private validation session.

## REC-I validation card

    SESSION: REC-I short passive capture and performance check
    SOURCE: PR #16 branch codex/flight-recorder-il2cpp-adapter; use the commit recorded in package-manifest.json
    PACKAGE: AoTTG2 Flight Recorder 0.1.11 candidate, x64, Unity 2023.1.22f1, BepInEx 6.0.0-be.791, .NET 6
    DEPLOY: Close the game copy, then run the 0.1.11 install_flight_recorder.ps1. It automatically replaces a prior install only when its receipt and DLL hashes verify and the folder contains no extra files. It refuses modified or unmanaged folders for manual review.
    GAME CONFIG: BepInEx/config/org.aicadets.aottg2.flight-recorder.cfg; set Enabled=true only for this capture and restore false afterward
    RECEIVER: Pass the private JSON file under Documents/AoTTG2/Recorders to start_flight_recorder_receiver.ps1. The launcher prints the resolved output directory; use a new local output folder and verify the pipe-ready message before launching the game
    ADD-ONS: Enable exactly AICadetsWaveCadet, AICadetsCommandPanel, and AICadetsM2Watcher. Disable AICadetsProbe, AICadetsTraversal, AICadetsTraversalReliable, AICadetsWatcher, and every other test add-on.
    SESSION PRIVACY: Fresh private master-host lobby for each variant, with no other clients. Never use a public lobby or capture other players' data.
    MODE / MAP: City 1 / Training / Waves, one owned cadet, and one ordinary Titan. Preserve the built-in mission script.
    LAUNCH ORDER: (1) close game and verify recorder Enabled=false; (2) start receiver on its new output folder; (3) set only recorder Enabled=true; (4) launch AoTTG2; (5) observe the plugin version, run ID, and pipe handshake after clean restart; (6) enter a fresh private lobby and verify active add-ons and effective driver in the UI.
    FIRST 30–60 SECONDS: Record fixed-step ordinals, game time, monotonic wall time, M2 watcher/controller event timestamps, and physical movement. For phase calibration, correlate a naturally occurring human/world collision or ground-contact transition with the actor's same-step and following-step samples and the corresponding collision/watcher event. If there is no independently observable transition, leave the phase unverified. Do not create synthetic physics or alter transforms/velocity.
    PERFORMANCE: Preserve the first startup health window separately. At steady state require capture_work_ms_p95 <= 5% of fixedDeltaTime (1.0 ms at 20 ms) and maximum <= 3x fixedDeltaTime (60 ms at 20 ms), zero transport/frame/control drops, no unexplained step gaps, valid chunk hashes, and `capture_complete=true`. Any control overflow remains a failed/incomplete capture even if the reserved gap and stop records are preserved. Stop and review if sustained stutter or control delay appears. This is callback work, not total Unity frame time.
    TRACE REVIEW: Run `runtime/python.exe tools/analyze_flight.py <run-folder-or-zip> --out <analysis-folder>`. Review manifest/hash integrity, frame order, drops/gaps, identity/lifecycle coverage, phase, collision and Hook evidence, health p95/max, M2 event correlation, unresolved velocity changes, and `kill_attributions.json`. A contact-based candidate remains inferred. Document the calibration procedure and result in the report; do not claim full actor coverage, collision/attack causality, damage, or kills from this recorder alone.
    STOP / ROLLBACK: Close the game and allow the receiver to finalize; if no stop record arrives, it waits five seconds for reconnect, seals the durable prefix as incomplete, and exits. Restore Enabled=false. Preserve incomplete output on failure. If the plugin causes errors or visible performance trouble, close the game and use the matching guarded remove script; it removes only unchanged manifest-listed recorder DLLs and receipt.
    RETURN: Run ZIP, analysis folder including `kill_attributions.json`, watcher files, console log, settings snapshot, deployed hashes, BepInEx/LogOutput.log, receiver stdout/stderr logs, redacted recorder config, short calibration video, package ZIP SHA-256, and completed Validation Card. Keep output in a fresh receiver folder; verify the receiver reports a stop and `writer_state.json` has `is_final=true` before archiving. Do not include game binaries or other players' data.

## Acceptance boundary

The supplied 0.1.5 recording establishes successful writer/transport operation and gives strong, non-causal evidence consistent with a cadet kill. It does not establish direct damage attribution, calibrated physics phase, REC-I performance acceptance, or M2 decision quality. The supplied 0.1.10 capture fails the performance and timing gates. The 0.1.11 reusable storage changes must be measured in the installed game before the performance gate is called resolved. The 174 unmatched velocity changes remain explicit review findings.

## Installed-machine handling

Version 0.1.9 was installed and exercised in-game; the run exposed the disconnect-finalization gap. Version 0.1.10 was installed and produced the supplied complete structural capture, but it failed the current performance and timing gates. Version 0.1.11 is being prepared with a package manifest and hashes; verify upgrade/rollback through its guarded installer and preserve BepInEx and generated interop during rollback.
