# Validation Card — M2 Direct recovery and Flight Recorder 0.1.13

SESSION: `M2-DIRECT-RECOVERY-20261105-FOLLOWUP`
SCOPE: Single-cadet M2 grounded Direct pursuit, one bounded opposite-side recovery retry, interruption, recorder performance/timing, and watcher rotation. No multi-cadet, rescue, personality, or M3 gameplay.
GAME: AoTTG2 product build `1.2.3` / Unity `2023.1.22f1` from the prior startup log; reconfirm after this launch.
M2: `M2-locomotion-1-f8combo-5-shorter-opposite-retry`; feature commit `a5c0b81f9bbf13b4ce1be05c02c4a6c9f50cf0dc`; record the deployed `.cl` SHA-256 before play.
RECORDER: 0.1.13 installed diagnostic candidate, source commit `e0e216dd518cad9569447cd18e7bccc206d94aac`. Package manifest: 50 files verified; archive: 51 files. ZIP SHA-256 `8C7371859C2EE41F6AECEA34915A8A17B9F603B173A9AE00A2B32675F48021F6`. Installed plugin SHA-256 `E5E331BDFCEF4BDE89CF4A29EA2227998C7A8E503F969B0279A0D74A2B97B314`; transport SHA-256 `DF25B8322B8CCEE6BE6444A8053125C33D49A90DE58128A319511CB14634EF9A`. Flight Recorder 0.1.13 is installed. The local config is staged with `[Capture] Enabled=true` for this launch; verify the enabled startup and pipe handshake before any gameplay order.
DEPLOYED ADD-ONS: WaveCadet `866C3BC8B3C9DDA0465633EB85B5B4E7D8C188B79CDD14FA53FA3FFB185C2CA9`; CommandPanel `8E6EB2B708F6A67BF7C9D5D7E0BD23B9DCBA1418910239CBDAAE6AE96EC1E17C`; M2Watcher `B6BD148511EA59203F6A3ACBFE0C8886E73C32C6CF4E71D08D9DBE15CCC24489`.

## Preconditions

- Start a fresh private lobby for every variant; confirm the local player is master host and only the user is present. Do not capture other players' telemetry.
- Use City 1 / Training / Waves, one owned cadet, one ordinary Titan, and comparable geometry. Confirm the actual active add-on list and F8 effective ground driver in-game.
- Enable exactly `AICadetsWaveCadet`, `AICadetsCommandPanel`, and `AICadetsM2Watcher`.
- Disable `AICadetsProbe`, `AICadetsTraversal`, `AICadetsTraversalReliable`, `AICadetsWatcher`, and every other test add-on.
- The user reports a close-to-building spawn can prevent the cadet from spawning. If the cadet is absent, invalidate that attempt, restart the round, verify the cadet exists, and record the replacement run ID/start position. Do not interpret a failed spawn as a movement failure.
- No manual steering or Recovery. Do not use teleports, transform/velocity writes, fake damage/kills, or synthetic physics. Preserve master-client authority, mission scripts, M1 baselines, and existing rollback files.

## Run matrix

| Run ID | Variant | Required evidence | Status |
|---|---|---|---|
| `M2-DIR-CLEAR-03` | One `Engage + Direct` on clear ground | Actual displacement, sustained positive same-target target-relative progress, no command thrashing | Pending |
| `M2-DIR-CORNER-03` | W3-style blocked corner, Direct | `ground_route_blocked`; first `reposition_end moved<2`; one opposite-side retry with a distinct logged goal and same Titan; displacement from retry start; at least 2 units and renewed same-target progress. If no route is safe or second movement is under 2, record bounded failure and no third command; that is not a recovery pass. | Pending |
| `M2-DIR-HOLD-03` | Hold during measured ground movement | `Idle` cancellation, cessation of ground motion, then Engage and Explore still work | Pending |
| `M2-ENGINE-COMP-03` | Comparable fresh `Engage + Engine` lobby | Compare physical displacement, target gain, path length, reversals, and recovery. `MoveTo`/`ai_state` alone is API evidence only. | Pending |
| `M2-WATCH-ROTATE-03` | Long private watcher run | Multiple segments below 1 MB, consecutive previous links/numbering, unrelated `PersistentData` keys preserved, and saved Custom Logic console log with no size warning | Pending |
| `FR-PERF-CAL-03` | 0.1.13 during an actor-loaded private M2 run | Installed load after clean restart, clean stop, complete/hash-valid ZIP, no gaps/drops, every post-15-second p95 <=1.0 ms, every sample <=60 ms, bounded queues; record stage timings. For calibration, correlate a natural independently observed physics transition to fixed-step ordinal, game time, wall time, recorder sample, and controller/watcher event. | Pending |

## Recorder limits and evidence

- Preserve schema `aicadets.flight.v1`, local named pipe, recovery behavior, package manifest integrity, and the existing 512-entry / 4 MiB producer and 256-entry / 64 MiB writer limits.
- Do not weaken performance limits or omit stage work. `sample_phase_verified=false` remains until a controlled calibration is reproducibly documented.
- Capture video, watcher files, recorder ZIP, receiver stdout/stderr, BepInEx log, in-game Custom Logic console log, active settings/add-on snapshot, deployed hashes, and this completed card. Redact unrelated identifiers from shared summaries; preserve raw files locally.
- Recorder data alone cannot establish complete actor coverage, collision/attack causality, damage, or kills.

## Current setup before the next run

- The user reports AoTTG2 is shut and ready for a new recording. The installed config is staged with `[Capture] Enabled=true` (SHA-256 `3E8D52C93F1E55DD4CEC21F1C8AD5CF6C3B308CD0D773A6AFD0A8149651A2DE6`). Its prior disabled-state copy remains at `rollback\installed-0.1.13-before-capture\org.aicadets.aottg2.flight-recorder.cfg` (SHA-256 `024486167F6A9CD554B46B166F5C903805E6D1C716E40C635A8C3FF0CFABE7C7`).
- The last observed BepInEx startup loaded Flight Recorder 0.1.13 with capture disabled. It is historical load evidence only; an enabled startup, receiver handshake, and capture are not yet observed.
- Use a fresh local receiver and output folder: `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261105\recorder-0.1.13-c5-run-02`. Start the receiver before launching the game and record its PID/stdout/stderr.
- The previous game-window screenshot capture timed out. Confirm actual product build, private master-host state, sole human participant, City 1 / Training / Waves, exactly the three listed Custom Logic add-ons, active settings, and effective ground driver in the new session; do not infer them from saved presets or the prior run.
- The user confirmed only the earlier `m2-0` lobby was private with them present. This does not establish privacy or host state for the new lobby. No new gameplay run has begun.

## Results

Static checks and local builds are not live evidence. Record each run above as pass, fail, partial, or inconclusive with artifact names.

- Earlier c4 `m2-0` recovery was a live failure: first-attempt displacement was 1.527 units; all opposite-side candidates were blocked, no second command/goal was issued, and the bounded safe-observation path ended without a third retry. User confirmed that lobby was private with only them present; whether the close-building spawn issue affected it is unknown.
- A separate earlier actor-loaded 0.1.12 run completed structurally but failed performance: 14/67 post-start health windows exceeded 1.0 ms p95; worst p95 was 2.8867 ms.
- Supplied run `a19d79cbcb9a4ecbbec2e5dd9a07def2` is a structural pass and performance/timing failure: 20 hash-verified chunks, 20,878 frames, 18 tracked entities, 901 events, 417.54 fixed-step seconds, zero dropped frames or entity samples, zero per-entity step gaps, and `capture_complete=true`. The current analyzer produced `prior-run-a19-reanalysis/report.md` in the local follow-up folder.
- The 15-second performance filter differs by clock: game time `t > 15` gives 59/81 windows above 1.0 ms p95 (the user-supplied count); recorder-start-relative monotonic wall time `> 15` gives 60/82, which is the analyzer gate. Both fail. Worst p95 is 5.7656 ms and maximum sample 65.7773 ms.
- Wall-clock health points are monotonic, game/wall correlation is 0.9999702499 with slope 1.0102223, and the trace has zero ordinal gaps, nonmonotonic game-time incidents, or fixed-step mismatches. Phase remains `fixed_update_pre_physics_order_unspecified` with `sample_phase_verified=false`; there were zero same-step collision calibration candidates and zero M2 controller/watcher events.
- Producer queue high-water was 53 entries / 573,489 bytes, but its configured caps are missing from metadata, so boundedness against limits is unverified. Writer queue high-water was 3 entries / 112,768 bytes against 256 / 64 MiB.

The current card tests the focused shorter opposite-goal search and the separate 0.1.13 performance candidate. Do not claim complete actor coverage, collision/attack causality, damage, or kills from this recorder alone.
