# Validation Card — M2 Direct recovery and Flight Recorder 0.1.13

SESSION: `M2-DIRECT-RECOVERY-20261105-FOLLOWUP`
SCOPE: Single-cadet M2 grounded Direct pursuit, one bounded opposite-side recovery retry, interruption, recorder performance/timing, and watcher rotation. No multi-cadet, rescue, personality, or M3 gameplay.
GAME: The user confirmed product build `1.2.3` for corrected watcher run `m2-0`; the current `a21…` lobby build is not separately reconfirmed. Unity `2023.1.22f1` and executable file version `2023.1.22.12665192` are observed in the current BepInEx startup.
M2: `M2-locomotion-1-f8combo-5-shorter-opposite-retry`; feature commit `a5c0b81f9bbf13b4ce1be05c02c4a6c9f50cf0dc`; record the deployed `.cl` SHA-256 before play.
RECORDER: 0.1.13 installed diagnostic candidate, source commit `e0e216dd518cad9569447cd18e7bccc206d94aac`. Package manifest: 50 files verified; archive: 51 files. ZIP SHA-256 `8C7371859C2EE41F6AECEA34915A8A17B9F603B173A9AE00A2B32675F48021F6`. Installed plugin SHA-256 `E5E331BDFCEF4BDE89CF4A29EA2227998C7A8E503F969B0279A0D74A2B97B314`; transport SHA-256 `DF25B8322B8CCEE6BE6444A8053125C33D49A90DE58128A319511CB14634EF9A`. The earlier run `7e1f8066b0074a3b9f2189dad59bafb7` finalized structurally but failed the performance gate and tracked zero actors. A fresh receiver is now connected to game capture run `a21f8d50fcb048c58360fbf347829302`; its gameplay order has not yet been issued.
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
| `m2-0` / `M2-DIR-CLEAR-03` | One `Engage + Direct` in the corrected one-Titan lobby | Watcher records physical pursuit and a large same-target distance reduction; clear-ground geometry, video, and command-thrash gate are not established. | Partial |
| `m2-0` / `M2-DIR-CORNER-03` | Blocked Direct pursuit near City 1 building geometry | Repeated blocked routes and bounded Observe are recorded. No recovery ended under 2 units, so the required opposite-side retry trigger was not exercised; no renewed target progress after later recovery. | Fail |
| `M2-DIR-HOLD-03` | Hold during measured ground movement | `Idle` cancellation, cessation of ground motion, then Engage and Explore still work. | Not run |
| `M2-ENGINE-COMP-03` | Comparable fresh `Engage + Engine` lobby | Compare physical displacement, target gain, path length, reversals, and recovery. `MoveTo`/`ai_state` alone is API evidence only. | Not run |
| `m2-0` / `M2-WATCH-ROTATE-03` | Long private watcher run | 15 numbered segments below 1 MB with previous links; trace ended on no free segment slots. In-game console and unrelated-property preservation remain unverified. | Partial |
| `7e1f8066b0074a3b9f2189dad59bafb7`, `a39bd097ce6b46ae9a261ba7eda31a91`, `a21f8d50fcb048c58360fbf347829302` / `FR-PERF-CAL-03` | 0.1.13 during installed-runtime M2 session | `7e…` is structurally complete but actorless and fails p95; `a39…` is incomplete after queue overflow; `a21…` has a fresh handshake and is awaiting the one Direct order. No calibration yet. | In progress / fail |

## Recorder limits and evidence

- Preserve schema `aicadets.flight.v1`, local named pipe, recovery behavior, package manifest integrity, and the existing 512-entry / 4 MiB producer and 256-entry / 64 MiB writer limits.
- Do not weaken performance limits or omit stage work. `sample_phase_verified=false` remains until a controlled calibration is reproducibly documented.
- Capture video, watcher files, recorder ZIP, receiver stdout/stderr, BepInEx log, in-game Custom Logic console log, active settings/add-on snapshot, deployed hashes, and this completed card. Redact unrelated identifiers from shared summaries; preserve raw files locally.
- Recorder data alone cannot establish complete actor coverage, collision/attack causality, damage, or kills.

## Captures and current launch

- On 2026-11-05, the first capture run `7e1f8066b0074a3b9f2189dad59bafb7` loaded with receiver PID `4428`, accepted hello sequence 1, and later received a clean stop envelope. This was the session before the user corrected Wave 1 Titan count from 3 to 1; it is recorder evidence only, not the corrected gameplay run.
- After the restart, producer run `a39bd097ce6b46ae9a261ba7eda31a91` loaded Flight Recorder 0.1.13 but never connected to a receiver. Its BepInEx log reports `transport_accounting_failure`, 272 dropped frames, one dropped control message, queue depth 512, and queue bytes 128001. The run is incomplete; raw log is preserved under `recorder-0.1.13-c5-run-02\logs`.
- The corrected gameplay session is watcher run `m2-0`, captured in 15 local watcher segments. The user confirmed a private master-host lobby with one human-controlled participant, City 1 / Training / Waves, one owned cadet, Wave 1 corrected to one Titan, and the exact three required add-ons with the other test add-ons disabled. The user confirmed Direct as the effective ground driver. Watcher snapshots later show one Titan, one player human, one owned cadet, and the Direct profile.
- The saved-settings snapshot is redacted and preserved as `gameplay-m2-0\saved-settings-snapshot-redacted.json`. The saved `InGame.json` has selected index 0 (Forest / Waves, no add-ons); set 2 named `m2-test` is City 1 / Waves with the M2 trio and Direct, but stores `StartTitans=3`. The active lobby is recorded from user confirmation and watcher counts, not inferred from that saved preset. The raw room name/password were excluded from the snapshot.
- Current installed hashes and recorder queue limits are preserved in the run manifests. The deployed M2 addon hashes remain those listed above; the recorder package has 50 manifest files verified and 51 ZIP entries.
- A fresh receiver was started before the latest game launch: PID `28216`, local pipe `aicadets-flight-recorder-v1`, output `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261105\recorder-0.1.13-c5-run-03\recordings`. BepInEx loaded 0.1.13 for run `a21f8d50fcb048c58360fbf347829302`; receiver hello sequence 1 is observed. The user reports being in the lobby and having spawned to trigger cadet spawning; no command-panel order had been issued at the last status update.

## Results

Static checks and mocked tests are not live evidence. Keep physical movement, recovery, combat, watcher persistence, recorder, timing, and package integrity as separate results.

### Saved settings, active setup, and package integrity

- The redacted saved-settings snapshot records source-file SHA-256 and excludes room names/passwords. Saved set index 0 is Forest / Waves with no add-ons. Saved set 2 (`m2-test`) is City 1 / Waves with `AICadetsWaveCadet`, `AICadetsCommandPanel`, and `AICadetsM2Watcher`; it also stores `StartTitans=3`, `GroundSteering=Direct`, `Persistence=3`, and `MaxRecoveriesPerTarget=4`. Those saved values do not prove the active session. In the corrected `m2-0` session the user reported changing Wave 1 Titan count to 1, and the watcher recorded `titans=1`, `player_humans=1`, and the owned M2 cadet. With Persistence 3 the source recovery formula yields a budget of 2 even though the preset's maximum is 4.
- The user confirmed the corrected `m2-0` lobby was private and master-hosted, with only them as the human-controlled player. The exact active addon list and Direct driver were user-confirmed; the watcher reports profile `ground=Direct`. The current `a21…` lobby was started after the user was asked to use the same setup; watcher confirmation of its cadet/Titan count and command is pending.
- Installed SHA-256 values at the start of the fresh `a21…` capture: WaveCadet `866C3BC8B3C9DDA0465633EB85B5B4E7D8C188B79CDD14FA53FA3FFB185C2CA9`; CommandPanel `8E6EB2B708F6A67BF7C9D5D7E0BD23B9DCBA1418910239CBDAAE6AE96EC1E17C`; M2Watcher `B6BD148511EA59203F6A3ACBFE0C8886E73C32C6CF4E71D08D9DBE15CCC24489`; Recorder plugin `E5E331BDFCEF4BDE89CF4A29EA2227998C7A8E503F969B0279A0D74A2B97B314`; transport `DF25B8322B8CCEE6BE6444A8053125C33D49A90DE58128A319511CB14634EF9A`. Package ZIP SHA-256 remains `8C7371859C2EE41F6AECEA34915A8A17B9F603B173A9AE00A2B32675F48021F6`.

### Direct pursuit and recovery — watcher run `m2-0`

- One `Engage + Direct` order was recorded as sequence 1 against Titan ID `1005`. Across 319 watcher target-distance observations from game time 1.44 to 100.98 seconds, distance fell from 850 units to below 100 by about 55 seconds, while the cadet's recorded positions changed substantially. This establishes actual movement and same-target pursuit progress in the run; it does not establish a controlled clear-ground geometry or synchronized video evidence.
- The trace contains 9 `ground_route_blocked` events, 6 `reposition_start` / 6 `reposition_end` records, 3 `recover_exhausted`, and 3 `observe_start` events. It contains no `reposition_retry` because no first recovery ended below 2 units. The under-2 opposite-side retry path therefore remains untested in this run.
- At game time 84.0579, recovery attempt 1 for Titan `1005` began at `(306.00, 10.06, 172.64)` with goal `(309.56, 10.06, 186.27)`; it ended at `(301.28, 10.06, 168.53)`, displacement `6.248`, target gain `-9.934`, termination `timeout`.
- After another blocked ground route, a distinct goal `(314.63, 10.06, 158.22)` was selected for attempt 2 while retaining Titan `1005`. From `(306.22, 10.06, 169.53)` it ended at `(301.39, 10.06, 169.47)`, displacement `4.838`, target gain `-1.358`, termination `timeout`. Another blocked route led to `recover_exhausted` and bounded Observe; no third recovery was issued. Because attempt 1 moved more than 2 units, this was not the required under-2-triggered retry sequence. Recovery gate: **fail**; there was no renewed same-target progress after the later recovery attempts.
- The run logged zero `attack_attempt` and zero Titan death records. No combat or kill claim is supported. Hold, post-Hold Engage/Explore, Engine comparison, authority-loss interruption, and low-gas/resupply interruptions were not run.
- No video was captured, and the exact building-corner geometry was not independently verified. `M2-DIR-CLEAR-03` is **partial** for physical pursuit, not a clear-ground pass. `M2-DIR-CORNER-03` is **fail** for recovery/engagement, while the safe bounded stop itself behaved as intended.

### Watcher persistence — run `m2-0`

- `AICadetsM2Watch85.txt` through `AICadetsM2Watch99.txt` are 15 contiguous numbered segments, segment indices 0–14 with previous-file links; each file is below 1 MB and the largest is 140,299 bytes. Raw copies, per-file SHA-256 values, and a ZIP are under `gameplay-m2-0`.
- The final watcher trace says `watch_stopped_no_free_segment_slots`. The in-game Custom Logic console was not saved, so absence of `SaveToFile exceeded 1 mb limit` is **unverified**. Preservation of unrelated `PersistentData` properties is also **unverified** from the available snapshots. Watcher rotation: **partial**.

### Flight Recorder 0.1.13

- Run `7e1f8066b0074a3b9f2189dad59bafb7` loaded after restart, connected to receiver PID `4428`, and received stop sequence `29786`. Its ZIP SHA-256 is `F33BEBF22959E84A0B0441E76DA546DF74B6320ECE842876707655EE91EA6D54`; one chunk hash verifies. It has `capture_complete=true`, 29,665 frame markers, zero step gaps, zero drops, zero malformed records, and clean durable writer finalization. It tracked **zero entities** and had zero M2 controller/watcher events; it predates correction of Wave 1 Titan count and is not M2 gameplay workload evidence.
- Reanalysis passed producer queue caps 512 entries / 4 MiB from the 0.1.13 package: high-water 33 entries / 13,094 bytes. Writer high-water was 22 entries / 12,320 bytes against 256 / 64 MiB. Both queues were bounded with no declared drops or fatal errors. The maximum individual sample was 51.2999 ms, below 60 ms. The strict p95 gate **failed**: 4 of 117 post-start windows exceeded 1.0 ms; worst p95 was 1.4204 ms. Zero tracked Human/Titan actors makes M2 workload performance unverified.
- Step/time continuity was structurally clean: fixed delta `0.019999992` s; zero ordinal gaps, nonmonotonic game-time incidents, or time mismatches; monotonic wall clock, correlation `0.9999999908`, slope `1.0000564`. There were no collision calibration candidates or controller/watcher records. Observation label remains `fixed_update_pre_physics`, `sample_phase_verified=false`; no timing calibration was performed.
- The follow-up producer run `a39bd097ce6b46ae9a261ba7eda31a91` did not connect to a receiver and stopped incomplete after 272 dropped frames, one dropped control message, queue depth 512, and 128,001 queue bytes. Do not analyze it as gameplay recorder evidence.
- Fresh producer run `a21f8d50fcb048c58360fbf347829302` is loaded and connected to receiver PID `28216` (hello seq 1). At 11:01:58 local, the writer had accepted 29,886 frames across 17 chunks (16 durable and one active partial) with no stop yet. The user reports an active lobby and that they spawned to trigger cadet spawning; no Direct order had reached the watcher at this update. Product build, fresh watcher counts, and the gameplay order are not yet correlated. Output and startup logs are under `recorder-0.1.13-c5-run-03`.
- Structural recorder result for `7e…`: **pass**. Performance and timing acceptance: **fail / unverified**. The new `a21…` run remains **in progress**.

### Static checks and remaining gates

- Current branch CI-equivalent checks passed on 2026-11-05: `python scripts/check_probe.py`, `python scripts/check_traversal.py`, `python scripts/check_traversal_reliable.py`, `python scripts/check_wave_m2.py`, `python tools/recovery_preflight.py --addons addons --persistent <empty directory>`, `python -m unittest discover -s tests -v` (143 tests), and `git show --format= --check HEAD`. The recovery preflight found zero Watch files and performed file checks only. `git diff --check` also passed for this card update. These checks do not prove Custom Logic parsing or live physics behavior. Recorder suite previously passed 120 tests and build/transport/package checks; watcher suite previously passed 142 tests.
- The validation card was created and pushed before gameplay. Run artifacts: recorder ZIP and analyzer report under `recorder-0.1.13-c5-run-02`; watcher ZIP `gameplay-m2-0\watcher-m2-0-segments-85-99.zip` (SHA-256 `8EECEA19F72DEB2C040AEC660467D5F1171E79DFA3DA5C89CCE90449E0198CA3`); failed `a39…` log under `logs`; fresh `a21…` receiver/config/preflight under `recorder-0.1.13-c5-run-03`.
- Keep PR #6 draft until a clear-ground progress pass, the exact under-2 retry branch, Hold/post-Hold behavior, and authority gates pass live. Keep PR #16 open but unmerged until an actor-loaded capture passes p95, clean stop/receiver shutdown, and timing calibration. Keep PR #17 draft and do not rebase/merge it until PR #6's final feature head and watcher console/persistence gates are established. Do not begin M3.
