# Validation Card — M2 opposite-side retry and Flight Recorder 0.1.13

SESSION: `M2-DIRECT-RECOVERY-20261104-FOLLOWUP`
SCOPE: Single-cadet M2 grounded Direct pursuit, one bounded opposite-side recovery retry, interruption, recorder performance/timing, and watcher rotation. No multi-cadet, rescue, personality, or M3 gameplay.
GAME: AoTTG2 product build `1.2.3` / Unity `2023.1.22f1` observed in the previous run. Reconfirm the actual build after restart.
M2: `M2-locomotion-1-f8combo-5-shorter-opposite-retry`; feature commit `a5c0b81f9bbf13b4ce1be05c02c4a6c9f50cf0dc`; record the deployed `.cl` SHA-256 before play.
RECORDER: 0.1.13 diagnostic candidate; record the source commit, package ZIP SHA-256, manifest verification, installed DLL hashes, and run IDs before play. Capture disabled outside the opted-in private run.

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
| `M2-DIR-CLEAR-02` | One `Engage + Direct` on clear ground | Actual displacement, sustained positive same-target target-relative progress, no command thrashing | Pending |
| `M2-DIR-CORNER-02` | W3-style blocked corner, Direct | `ground_route_blocked`; first `reposition_end moved<2`; one opposite-side retry with a distinct logged goal and same Titan; displacement from retry start; at least 2 units and renewed same-target progress. If no route is safe or second movement is under 2, record bounded failure and no third command; that is not a recovery pass. | Pending |
| `M2-DIR-HOLD-02` | Hold during measured ground movement | `Idle` cancellation, cessation of ground motion, then Engage and Explore still work | Pending |
| `M2-ENGINE-COMP-02` | Comparable fresh `Engage + Engine` lobby | Compare physical displacement, target gain, path length, reversals, and recovery. `MoveTo`/`ai_state` alone is API evidence only. | Pending |
| `M2-WATCH-ROTATE-02` | Long private watcher run | Multiple segments below 1 MB, consecutive previous links/numbering, unrelated `PersistentData` keys preserved, and saved Custom Logic console log with no size warning | Pending |
| `FR-PERF-CAL-02` | 0.1.13 during an actor-loaded private M2 run | Installed load after clean restart, clean stop, complete/hash-valid ZIP, no gaps/drops, every post-15-second p95 <=1.0 ms, every sample <=60 ms, bounded queues; record stage timings. For calibration, correlate a natural independently observed physics transition to fixed-step ordinal, game time, wall time, recorder sample, and controller/watcher event. | Pending |

## Recorder limits and evidence

- Preserve schema `aicadets.flight.v1`, local named pipe, recovery behavior, package manifest integrity, and the existing 512-entry / 4 MiB producer and 256-entry / 64 MiB writer limits.
- Do not weaken performance limits or omit stage work. `sample_phase_verified=false` remains until a controlled calibration is reproducibly documented.
- Capture video, watcher files, recorder ZIP, receiver stdout/stderr, BepInEx log, in-game Custom Logic console log, active settings/add-on snapshot, deployed hashes, and this completed card. Redact unrelated identifiers from shared summaries; preserve raw files locally.
- Recorder data alone cannot establish complete actor coverage, collision/attack causality, damage, or kills.

## Results

Static checks and local builds are not live evidence. Record each run above as pass, fail, partial, or inconclusive with artifact names. The prior `m2-0` recovery had a first under-2 displacement of 1.527 units; the opposite-side candidates were blocked and no second command/goal was issued. The 0.1.12 actor-loaded recorder run completed structurally but failed performance (14/67 post-start windows over 1.0 ms p95; worst 2.8867 ms). This card tests the focused shorter opposite-goal search and the separate 0.1.13 performance candidate.
