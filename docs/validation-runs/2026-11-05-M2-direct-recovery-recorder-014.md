# Validation Card — M2 Direct recovery and Flight Recorder 0.1.14

SESSION: `M2-DIRECT-RECOVERY-20261105-014`
SCOPE: One-cadet M2 Direct grounded movement, bounded opposite-side recovery, Hold interruption, Engine comparison, recorder performance/timing, and watcher rotation. No multi-cadet, rescue, personality, or M3 gameplay.
GAME: Previous user-confirmed session was a private master-host City 1 / Training / Waves lobby with one human-controlled player, one owned cadet, one ordinary Titan, Wave 1 set to one Titan, and the three required add-ons only. Product build was previously reported as `1.2.3`; capture it again from the active run. Unity `2023.1.22f1` was observed in the recorder startup log.
M2: Candidate build `M2-locomotion-1-f8combo-6-opposite-back-diagonal-retry`; commit is pending tests and live validation. Existing installed M2 build was `M2-locomotion-1-f8combo-5-shorter-opposite-retry`.
RECORDER: 0.1.14 hot-path candidate is not yet packaged, installed, or runtime-validated. Prior installed 0.1.13 run `0f641e245f0f4c0a9c3dab23d08c355e` was structurally complete and stopped cleanly, but failed performance and timing acceptance. Package path, hash, and installed hashes must be recorded after packaging/deployment.
PRIVACY: Use a fresh private master-host lobby for every gameplay variant. Only the user's human-controlled player may be present. Raw logs, watcher data, and recorder files remain local unless explicitly approved.

## Preconditions

- Create a fresh private lobby for each variant; confirm the local player is master host and the only human-controlled player.
- Use City 1 / Training / Waves, one owned cadet, one ordinary Titan, Wave 1 Titan count 1, and comparable start geometry. Record the actual AoTTG2 product build.
- Enable exactly `AICadetsWaveCadet`, `AICadetsCommandPanel`, and `AICadetsM2Watcher`.
- Disable `AICadetsProbe`, `AICadetsTraversal`, `AICadetsTraversalReliable`, `AICadetsWatcher`, and every other active test add-on.
- Record the saved settings snapshot and independently verify the effective runtime ground driver. Do not infer active settings from saved presets.
- Record installed add-on and recorder hashes, recorder version, and each run ID before issuing orders.
- If a close-to-building spawn prevents the cadet from spawning, invalidate the attempt, restart the round, verify the cadet exists, and record the replacement run ID and start position.
- Do not manually steer or issue Recovery during movement tests. Do not use teleports, direct transform/velocity writes, fake damage/kills, or synthetic physics. Preserve master-client authority, mission scripts, M1 baselines, and all rollback files.

## Run matrix

| Run ID | Variant | Required observation | Status |
|---|---|---|---|
| pending | Clear-ground `Engage + Direct` | One F8 order; measured physical displacement; sustained positive same-target progress; no repeated command thrashing. | Not run on candidate build |
| pending | Known W3-style blocked corner | `ground_route_blocked`; first `reposition_end moved<2`; exactly one opposite-side retry with a different logged goal and same Titan; at least 2 units of displacement from retry start; renewed same-target progress. If retry is under 2, confirm bounded safe Observe and no third attempt; mark recovery fail. | Not run on candidate build |
| pending | Hold interruption | Issue Hold during measured ground movement; verify `Idle` cancellation and cessation of further ground movement; verify Engage and Explore still work afterward. | Not run on candidate build |
| pending | Engine regression | Comparable fresh `Engage + Engine`; compare displacement, target gain, path length, reversals, and recovery. `MoveTo`/`ai_state=MoveTo` alone is state/API evidence only. | Not run on candidate build |
| pending | Combat reachability | If locomotion reaches an attack window, record attack attempts and observed animation/state. Do not label animation, proximity, or `confirmed_damage=false` as a hit; require independently attributed damage/death evidence for a kill. | Not run |
| pending | Watcher persistence | Long private run creates multiple segments; verify no `SaveToFile exceeded 1 mb limit`, each segment below 1 MB, sequence/previous links, preservation of unrelated `PersistentData`, and save the game console log. | Not run on candidate build |
| `0f641e245f0f4c0a9c3dab23d08c355e` | Installed recorder 0.1.13 / Direct run | 24,846 frames; 24/24 chunks valid; no frame gaps, drops, or fatal errors; clean stop and bounded queue. Failed p95 (51/97 post-15-second windows above 1.0 ms; worst p95 4.311 ms) and max sample 87.7007 ms. Phase label `fixed_update_pre_physics`, `sample_phase_verified=false`; no controlled calibration. | Structural pass; performance fail; timing unverified |
| pending | Installed recorder 0.1.14 | Clean plugin load and receiver handshake; complete hash-valid ZIP; no gaps/drops; every post-15-second p95 <= 1.0 ms; no sample > 60 ms; bounded queues; clean producer/receiver stop; calibrated phase. | Not run |

## Recorder timing and performance gate

- Preserve `aicadets.flight.v1`, local named-pipe transport, recovery behavior, queue bounds, package-manifest integrity, and all producer/receiver loss accounting. Do not weaken thresholds or omit expensive samples.
- Confirm the installed plugin loads after a clean game restart and record the exact plugin version and hashes.
- Use a controlled calibration event with a known fixed-step event or independently observable physics transition to establish sample ordering relative to the physics update. Correlate fixed-step ordinals, game time, wall time, recorder frames, and M2 watcher/controller timestamps.
- Do not infer phase from a complete ZIP or event order alone. Keep `sample_phase_verified=false` if the controlled result is inconclusive, and keep recorder acceptance **blocked**.
- Document calibration procedure, observed phase, fixed-step continuity, game-time continuity, wall-clock correlation, and M2-event relationship in the report.
- The recorder does not establish complete actor coverage, collision or attack causality, damage, or kills.

## Artifacts to retain locally

- Video of each gameplay variant, watcher files and per-file hashes, recorder ZIP and analysis report, receiver stdout/stderr, BepInEx and game Custom Logic console logs, runtime settings/add-on snapshot, deployed-file hashes, and this completed Validation Card.
- Separate result labels for static/API checks, recorder runtime, timing calibration, watcher persistence, physical movement, combat, and package integrity.
- Do not publish player display names or raw private telemetry in PR descriptions. PRs may name local artifact paths, hashes, counts, and outcomes.

## Previous run result

- User confirmed the app exited. Producer run `0f641e245f0f4c0a9c3dab23d08c355e` finalized with `capture_complete=true`, stop reason `graceful_stop`, 24,846 durable frames, last fixed step 24,846, no declared frame/entity drops, no source-missing frames, bounded queue, and clean receiver exit. All 24 chunk hashes validate; frame coverage is 1.0; zero step gaps or fixed-time mismatches. Game/wall correlation was `0.9999924733`, slope `1.0022686138`.
- Performance failed: 51/97 post-15-second health windows exceeded the 1.0 ms p95 limit; worst p95 was 4.311 ms and the maximum sample was 87.7007 ms. Worst sample stages included discovery 87.6343 ms and frame sampling 83.5092 ms. Queue depth/bytes remained bounded with no drops or fatal errors.
- Timing is **unverified**: metadata says `fixed_update_pre_physics`, but `sample_phase_verified=false`. Same-step observations are not independent calibration.
- The corrected private session's single `Engage + Direct` order was sequence 1 against Titan view ID 1005. After `ground_route_blocked`, the first recovery ended at under 2 units; `reposition_retry_blocked` recorded `command_dispatched=false`, then the controller entered bounded Observe. The retry/recovery gate is **fail**. This run does not establish clear-ground success, sustained target-relative progress after retry, attack, damage, or kill.
- Watcher Watch1–Watch23 form an ordered active chain with previous-file links. Watch0 is a separate pre-cadet watcher start. All 24 files are below 1 MB, maximum 310,227 bytes. The BepInEx log was preserved; the in-game Custom Logic console was not independently captured, so the size-warning gate and unrelated-property preservation remain unverified. Artifacts are under `Documents/Aottg2/Recorders/validation/M2-DIRECT-RECOVERY-20261105/recorder-0.1.13-c5-run-04/artifacts-0f641e245f0f4c0a9c3dab23d08c355e`; sealed run ZIP SHA-256 `89220BD08A1B8A850551CB54C0D38C47778C7AD851D687AFADB87BA609882169`.
- The recorder source candidate 0.1.14 reduces repeated animation/state work and caches capture-scope decisions within each fixed-step sample. This is an optimization candidate only; installed runtime performance remains unverified until the fresh capture passes the unchanged gate.

## Rollback

- Gameplay: revert only the focused Direct recovery commit after it is recorded; preserve earlier M2 feature commits and all other work. Before deploying the candidate WaveCadet file, save the installed file with its SHA-256 under this run's `rollback` directory. Restore that exact saved file and verify its hash to roll back.
- Recorder: retain the existing 0.1.13 rollback bundle. Install the 0.1.14 package only with AoTTG2 closed and the guarded installer; record the installer-created rollback files and hashes. Restore the saved 0.1.13 DLLs if package integrity, load, or capture fails.
