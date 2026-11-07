# Validation Card — M2 blocked Direct recovery and Flight Recorder 0.1.15

SESSION: `M2-BLOCKED-DIRECT-20261105-015`
SCOPE: One-cadet M2 `Engage + Direct` on a W3-style blocked route; bounded opposite-side recovery; recorder 0.1.15 performance and timing calibration; watcher rotation. No multi-cadet, rescue, personality, or M3 gameplay.
GAME: AoTTG2 product build `1.2.3` was read from the installed build's `App_version.data` for run 05; Unity `2023.1.22f1` was observed in BepInEx logs. Recapture both for this new run. User must confirm a fresh private master-host lobby and that they are the only human-controlled player.
M2: Candidate `M2-locomotion-1-f8combo-6-opposite-back-diagonal-retry`, code commit `6862516ca7bbf56db81bd661afb8a23002b9afc1`, current feature head `5fc132b6cde6566828efce65c4af17f06c0df356`. Installed WaveCadet SHA-256 `965E5B57A19917302F089EBB90902A2C637E096D245B3AC173EE3EF3DEC0B752`.
RECORDER: 0.1.15 source commit `53ac15e362ee4023ad485396fa8436e18092031e`; package ZIP SHA-256 `EA831B778F04D58689D9C82A7F8F40D2A687AE64C3289506DE028A2A4965D4BB`; 50/50 manifest files and ZIP entries verified. Installed 0.1.15 plugin SHA-256 `CEE9835C2B55F7362A1FC9CB2C18D2DF570B13352A620DD27A1B12E1999F4319`; transport SHA-256 `AD7407F6DE5B4D899AD9CA7F3ACD2EDC76C6796FFC9B4E351BEFE2C1F991DC2A`; installed-manifest SHA-256 `5CB99D25F1C3124C032D1A9D4C9DB22597AD4B231C9C2BF0BF1144B5BE9622E0`. Recorder config is currently `Enabled = false`, SHA-256 `332769B54DD88F99E7D3D943D56EE6AAA54577AE6E4E264A84A8360D1A780F88`. The fresh installed-runtime load/capture has not started.
PRIVACY: Raw watcher, recorder, video, and game logs stay local. Do not include player display names or raw private telemetry in PR descriptions.

## Preconditions and setup

- Start with AoTTG2 closed. The 0.1.14 recorder DLLs, `install-manifest.json`, and disabled configuration were preserved at `recorder-0.1.15-c7-run-06/rollback/installed-0.1.14-before-0.1.15`; all four hashes verified. The existing 0.1.13 rollback bundle remains intact. The 0.1.15 package was installed through `scripts/install_flight_recorder.ps1`.
- Keep recorder `Enabled = false` until the receiver is listening on the new local output folder. Verify package/install manifest hashes and effective installed DLL hashes. The 0.1.15 default remains disabled.
- Use a fresh private master-host lobby per variant, City 1 / Training / Waves, Wave 1 Titan count 1, one owned cadet, and one ordinary Titan. Confirm the only human-controlled player is the user.
- Enable exactly `AICadetsWaveCadet`, `AICadetsCommandPanel`, and `AICadetsM2Watcher`. Disable `AICadetsProbe`, `AICadetsTraversal`, `AICadetsTraversalReliable`, `AICadetsWatcher`, and every other test add-on. Record active add-ons from the actual run, not from a saved preset.
- Save the active settings snapshot, effective ground driver, product build, lobby privacy/host, enabled add-ons, recorder version, deployed hashes, and both run IDs. The watcher should show `driver=Direct`; do not infer it from the preset.
- Save a before-run inventory/hash of unrelated `PersistentData` properties and files so they can be compared after the watcher test. Preserve all existing rollback files.
- If a close-to-building spawn prevents a cadet from appearing, invalidate that attempt, restart the round, verify one cadet and one Titan, and record the replacement run ID. Do not issue an order before the cadet exists.
- No manual steering or Recovery during the test. No teleport, direct transform or velocity write, fake damage or kill, or synthetic physics.

## Run matrix

| Run ID | Variant | Required observation | Status |
|---|---|---|---|
| pending | Known W3-style blocked corner; one F8 `Engage + Direct` order | `ground_route_blocked`; first `reposition_end moved<2`; exactly one `reposition_retry`; genuinely different second goal; same Titan target; retry displacement measured from retry start; at least 2 units plus renewed same-target progress to pass. If retry is below 2, verify bounded safe Observe and no third retry; mark recovery fail. | Pending user-operated run |
| pending | Installed recorder 0.1.15 during the same private single-cadet workload | Clean plugin load/receiver handshake and stop; complete hash-valid capture; no frame gaps, drops, entity-sample drops, fatal errors, or queue-limit violations; every post-15-second p95 <= 1.0 ms; no sample > 60 ms. | Pending installed runtime |
| pending | Controlled timing observation during natural movement/contact | Correlate a known fixed-step event or independently observed natural physics transition with same-step and following-step actor samples/callback; verify ordinal, game-time, wall-clock continuity, and watcher/controller timestamps. Keep `sample_phase_verified=false` if inconclusive. No synthetic transition. | Pending calibration |
| pending | Watcher persistence during the long run | Multiple numbered segments, all under 1 MB; predecessor links and numbering correct; no overflow warning in saved game logs; unrelated `PersistentData` properties preserved; console/log files saved. | Pending |

## Run 05 baseline

- Direct pursuit run `72c1c04816b040e984ba25dde909c7b0` acknowledged one F8 order, sequence 1. Watcher measured 360.69 units of cadet net displacement and same-target distance `410.4487 → 44.4841` over 424 post-order samples. Clear-ground geometry was not independently labeled. The blocked retry was not exercised before the 300-second watcher cap; this was not a recovery pass.
- Installed recorder 0.1.14 loaded and stopped cleanly, with 37/37 chunks, 37,706 frames, zero gaps/drops, and bounded queues. Performance failed: 77/149 post-15-second p95 windows above 1.0 ms, worst p95 4.9976 ms, maximum sample 131.6034 ms. Timing remains unverified (`fixed_update_pre_physics`, `sample_phase_verified=false`).
- The card for run 05 is [2026-11-05 M2 Direct recovery and Recorder 0.1.14](2026-11-05-M2-direct-recovery-recorder-014.md). Its raw artifacts and ZIP remain local.

## Execution and evidence

- Start the receiver before launching the game. Confirm plugin 0.1.15, run ID, and receiver hello after a clean restart. Only then enter the fresh lobby and issue exactly one `Engage + Direct` order to the one owned cadet.
- Let the controller run without manual steering or Recovery. Record `ground_route_blocked`, first under-2 movement, the single retry goal/target, second displacement and same-target progress, or the bounded second failure. Stop the game normally so producer and receiver can finalize.
- During the same natural blocked-route test, use any naturally occurring collision/ground-contact callback as a calibration candidate. It must be independently observable and correlated to fixed-step samples. Do not mark phase verified from continuity or ZIP completeness alone.
- Keep result labels separate: static/API, installed recorder, performance, timing calibration, watcher persistence, physical movement/recovery, combat, and package integrity. Recorder data alone cannot establish complete actor coverage, collision/attack causality, damage, or kills.
- Return the gameplay video if captured, watcher files and per-file hashes, recorder ZIP and analysis report, BepInEx/Unity/Custom Logic logs, settings snapshot, deployed hashes, receiver logs, rollback hashes, and this completed card. Raw private files stay local.

## Existing source checks

- M2: `python scripts/check_probe.py`, `python scripts/check_traversal.py`, `python scripts/check_traversal_reliable.py`, `python scripts/check_wave_m2.py`, recovery preflight, and `python -m unittest discover -s tests -v` (144 tests) passed on the current feature branch. Actions run `42082484024` passed on the gameplay candidate code commit.
- Recorder 0.1.15: 125 Python tests, compileall, .NET 6/.NET 8 transport builds and smoke, Windows pipe/writer/analyzer recovery smoke, six PowerShell parses, Unity IL2CPP plugin build with zero warnings/errors, package manifest and ZIP hashes, and `git diff --check` passed. These results do not establish game parsing, installed performance, or timing.

## Rollback

- Recorder rollback: close AoTTG2, restore the saved 0.1.14 DLLs and `install-manifest.json` to `BepInEx/plugins/AoTTG2FlightRecorder`, restore the saved config with `Enabled = false`, and verify the pre-install hashes. Do not remove BepInEx, loader files, or generated interop. Keep both the 0.1.14 and older 0.1.13 rollback bundles.
- M2 rollback: restore the preserved pre-`f8combo-6` `AICadetsWaveCadet.cl` from `gameplay-f8combo6-run-pending/rollback` and verify its recorded SHA-256. Do not revert earlier M2 work, M1 files, mission scripts, or unrelated changes.
