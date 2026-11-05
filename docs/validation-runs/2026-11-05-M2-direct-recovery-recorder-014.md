# Validation Card — M2 Direct recovery and Flight Recorder 0.1.14

SESSION: `M2-DIRECT-RECOVERY-20261105-014`
SCOPE: One-cadet M2 Direct grounded movement, bounded opposite-side recovery, Hold interruption, Engine comparison, recorder performance/timing, and watcher rotation. No multi-cadet, rescue, personality, or M3 gameplay.
GAME: Run 05 used AoTTG2 `1.2.3` / Unity `2023.1.22f1`, in a user-confirmed private master-host City 1 / Training / Waves lobby with one human-controlled player, one owned cadet, one ordinary Titan, Wave 1 set to one Titan, and the three required add-ons only. The watcher observed `driver=Direct` and the one-cadet EngageDirect acknowledgement. A saved settings snapshot was not captured.
M2: Candidate build `M2-locomotion-1-f8combo-6-opposite-back-diagonal-retry`, commit `6862516ca7bbf56db81bd661afb8a23002b9afc1`; local CI-equivalent checks and GitHub Actions run `42082484024` passed. Live validation remains open. The previously installed M2 build was `M2-locomotion-1-f8combo-5-shorter-opposite-retry`.
RECORDER: 0.1.14 source commit `7b59701131aa328c2e329863ad827e3bc275780e`; package ZIP SHA-256 `6C8CDBA42CE0422384D511E6875692AB43477C20489F75ECAED730627515798C`; 50/50 manifest hashes verify and the ZIP has 51 entries including the manifest. Installed plugin SHA-256 `92F8954509F3A84DE1EA6EA0AA6E35633971EABA80433208E18E0CECE8D92AB5`; transport SHA-256 `980A90B1B255E7A914722D797DB899D48395752DC455EC814A1621DB9E7EEFE0`. Version 0.1.14 is installed but not yet observed loading in game. The previous installed 0.1.13 run `0f641e245f0f4c0a9c3dab23d08c355e` was structurally complete and stopped cleanly, but failed performance and timing acceptance.
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
| `72c1c04816b040e984ba25dde909c7b0` | Direct pursuit / one F8 `Engage + Direct` order | One order acknowledgement, sequence 1; observed 360.69 units net cadet displacement and same-target distance 410.4487→44.4841 over the sampled post-order interval. The geometry was not independently labeled clear ground. | Physical movement and same-target progress pass; clear-ground geometry partial; recovery not exercised |
| next controlled run | Known W3-style blocked corner | `ground_route_blocked`; first `reposition_end moved<2`; exactly one opposite-side retry with a different logged goal and same Titan; at least 2 units of displacement from retry start; renewed same-target progress. If retry is under 2, confirm bounded safe Observe and no third attempt; mark recovery fail. | Not exercised in run 05; still open |
| next controlled run | Hold interruption | Issue Hold during measured ground movement; verify `Idle` cancellation and cessation of further ground movement; verify Engage and Explore still work afterward. | Not run |
| next controlled run | Engine regression | Comparable fresh `Engage + Engine`; compare displacement, target gain, path length, reversals, and recovery. `MoveTo`/`ai_state=MoveTo` alone is state/API evidence only. | Not run |
| `72c1c04816b040e984ba25dde909c7b0` | Combat reachability | No attack-attempt event and no sampled Titan alive-to-dead transition; the Titan remained alive in the available watcher/recorder evidence. | No attack, damage, or kill claim |
| `72c1c04816b040e984ba25dde909c7b0` | Watcher persistence | Watch0 plus Watch1–Watch41 copied; 41 active linked segments (indexes 0–40), all links verified; maximum 382,272 bytes. BepInEx and Unity Player logs saved; neither contains the overflow warning text. | Segment size and link pass; separate Custom Logic console state and unrelated-property preservation remain unverified |
| `0f641e245f0f4c0a9c3dab23d08c355e` | Installed recorder 0.1.13 / Direct run | 24,846 frames; 24/24 chunks valid; no frame gaps, drops, or fatal errors; clean stop and bounded queue. Failed p95 (51/97 post-15-second windows above 1.0 ms; worst p95 4.311 ms) and max sample 87.7007 ms. Phase label `fixed_update_pre_physics`, `sample_phase_verified=false`; no controlled calibration. | Structural pass; performance fail; timing unverified |
| `72c1c04816b040e984ba25dde909c7b0` | Installed recorder 0.1.14 | 37/37 chunks; 37,706 frames; no gaps, mismatches, drops, or writer fatal; bounded queues and clean stop. 77/149 post-15-second p95 windows exceed 1.0 ms; worst p95 4.9976 ms; maximum individual sample 131.6034 ms. Phase `fixed_update_pre_physics`, `sample_phase_verified=false`; no controlled calibration. | Structural/stop pass; performance fail; timing unverified |

## Candidate deployment before run 05

- Candidate WaveCadet is installed at `Documents/Aottg2/CustomAddon/AICadetsWaveCadet.cl`, SHA-256 `965E5B57A19917302F089EBB90902A2C637E096D245B3AC173EE3EF3DEC0B752`. The prior installed file is preserved at `Documents/Aottg2/Recorders/validation/M2-DIRECT-RECOVERY-20261105/gameplay-f8combo6-run-pending/rollback/AICadetsWaveCadet.before-f8combo6.cl`, SHA-256 `866C3BC8B3C9DDA0465633EB85B5B4E7D8C188B79CDD14FA53FA3FFB185C2CA9`.
- CommandPanel remains SHA-256 `8E6EB2B708F6A67BF7C9D5D7E0BD23B9DCBA1418910239CBDAAE6AE96EC1E17C`; M2Watcher remains SHA-256 `B6BD148511EA59203F6A3ACBFE0C8886E73C32C6CF4E71D08D9DBE15CCC24489`.
- Flight Recorder 0.1.14 is installed through the guarded installer. Its pre-0.1.14 DLL/config rollback is preserved under `recorder-0.1.13-c5-run-04/rollback/installed-0.1.13-before-0.1.14`. The local receiver is started before the game. Current receiver PID is 21640, with a new output directory at `Documents/Aottg2/Recorders/validation/M2-DIRECT-RECOVERY-20261105/recorder-0.1.14-c6-run-05/recordings`.
- Run 05 was performed on AoTTG2 `1.2.3` / Unity `2023.1.22f1`. The user confirmed a private master-host lobby with one human-controlled player, City 1 / Training / Waves, one owned cadet, one ordinary Titan, Wave 1 count 1, and the three required add-ons. The watcher recorded `driver=Direct`; the order acknowledgement was `EngageDirect`, sequence 1. The installed add-on hashes are recorded in the local run artifact manifest. A saved settings snapshot and gameplay video were not captured.
- After normal game exit, the producer finalized and receiver shut down cleanly. The Flight Recorder `Enabled` setting was restored to `false`; the post-run config SHA-256 is recorded locally.

## Run 05 results — `72c1c04816b040e984ba25dde909c7b0`

- **Static/API:** the pre-run M2 and recorder checks listed below passed. They do not verify live Custom Logic parsing or physical behavior.
- **Installed recorder / package:** clean restart observed Flight Recorder 0.1.14 and Chainloader startup complete; local receiver accepted hello sequence 1. Final `capture_complete=true`, 37/37 chunk hashes verified in the sealed ZIP, 37,706 frames, 1.0 frame coverage, zero missing steps, fixed-time mismatches, dropped frames/entity samples, malformed records, incomplete reasons, or writer fatal errors. Receiver accepted stop sequence 39,044. Writer finalized all 37,706 frames and 1,294 events; queue depth and bytes remained below configured caps. The recorder ZIP is `run-72c1c04816b040e984ba25dde909c7b0-sealed.zip`, SHA-256 `6F3AAED3BEA5639B698CA3444D8993361ED32351728AD3759E911CE63CF26970`.
- **Performance:** fail. 77/149 post-15-second producer-health windows exceed 1.0 ms capture-work p95; worst p95 4.9976 ms; maximum sample 131.6034 ms. Stage maxima include frame sampling 121.3798 ms, discovery 33.987 ms, and serialization/queue 38.3894 ms. Do not reduce thresholds or discard samples to make this pass.
- **Timing:** unverified. Metadata remains `fixed_update_pre_physics`, `sample_phase_verified=false`. Fixed step/game time/wall correlation are continuous (37,706 ordinals; fixed delta 0.019999992; Pearson correlation 0.9999893952; slope 1.0032651585), but there is no independent controlled physics transition or M2 watcher/controller event in this recorder trace. The 341 candidate and 344 same-step-before-callback collision observations do not calibrate phase.
- **Physical movement:** pass for measured Direct pursuit progress, with clear-ground start geometry not independently verified. Watcher sequence 1 acknowledged the one-cadet `EngageDirect` order against the same Titan. Across 424 post-order samples, target distance changed from 410.4487 to 44.4841 (minimum 8.7370), cadet net displacement was 360.69 units, and sampled path length was 2,836.27 units. No repeated command-thrashing was found in the inspected trace.
- **Recovery / Hold / Engine:** recovery not exercised (no `ground_route_blocked`, reposition, or exhausted-recovery event by the 300-second watcher cap); this is not a retry pass. Hold interruption/post-Hold orders and the physical Engine comparison were not run. These are the remaining live M2 gates.
- **Combat:** no attack-attempt event or sampled Titan alive-to-dead transition was observed. No hit, damage, or kill is claimed.
- **Watcher persistence:** 42 local files, with Watch0 as a separate watcher-start record and Watch1–Watch41 as a linked 41-segment active chain (indexes 0–40). Every predecessor link matches and every file is below 1 MB; largest file 382,272 bytes. BepInEx and Unity Player logs were saved and contain no `SaveToFile exceeded 1 mb limit` text. A separately captured Custom Logic console state and unrelated `PersistentData` property comparison are not available, so those sub-gates remain unverified.
- **Artifacts / privacy:** sealed recorder ZIP, analysis report, 42 watcher files plus SHA-256 manifest, final BepInEx and Unity Player logs, startup handshake, configs, and deployment/hash snapshot are under `Documents/Aottg2/Recorders/validation/M2-DIRECT-RECOVERY-20261105/recorder-0.1.14-c6-run-05`. Raw private telemetry and logs remain local; no player display name is included in this card. No gameplay video or saved-settings snapshot was captured.

## Static results

- M2: `python scripts/check_probe.py`, `python scripts/check_traversal.py`, `python scripts/check_traversal_reliable.py`, `python scripts/check_wave_m2.py`, `python tools/recovery_preflight.py --addons addons --persistent <empty directory>`, `python -m unittest discover -s tests -v` (144 tests), `git show --check HEAD`, and `git diff --check` passed. GitHub Actions run `42082484024` passed. These checks do not validate Custom Logic parsing or live physics.
- Recorder 0.1.14: 123 Python tests, Python compile checks, .NET 6/.NET 8 transport builds, transport smoke, Windows pipe/writer/analyzer smoke, PowerShell parsing, Unity IL2CPP plugin build with zero warnings/errors, and `git diff --check` passed. GitHub Actions run `42082711362` passed. None establish installed-runtime performance or phase.

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
