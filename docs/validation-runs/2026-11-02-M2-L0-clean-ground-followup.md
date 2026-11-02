# Validation Card — clean ground approach, active Hold, and autonomous recovery

SESSION ID: M2-L0-20261102-CLEAN
GOAL / CHANGED BEHAVIOR: Re-test the committed one-click Direct/Engine presets, verify Hold during active ground movement, and isolate the close no-anchor fallback in open geometry. No controller behavior changes are included in this test.
BRANCH / EXACT COMMIT / REPORTED BUILD: `feat/m2-exploration-and-orders` / `a5e1b20842654f3bee77f0be92176f609e54bbdb` / `M2-locomotion-1-f8combo-2-holdrecovery`.
TEST PROFILE: M2-L0.

FILES TO COPY (source -> installed add-on location):
- `addons/AICadetsWaveCadet.cl` -> `C:\Users\vmorr\Documents\Aottg2\CustomAddon\AICadetsWaveCadet.cl` (SHA-256 `6B0160568948653428E6B1A3DDE9128A571EF93C2F368CFE227035BFFC9C79B7`)
- `addons/AICadetsCommandPanel.cl` -> `C:\Users\vmorr\Documents\Aottg2\CustomAddon\AICadetsCommandPanel.cl` (SHA-256 `8E6EB2B708F6A67BF7C9D5D7E0BD23B9DCBA1418910239CBDAAE6AE96EC1E17C`)
- `addons/AICadetsM2Watcher.cl` -> `C:\Users\vmorr\Documents\Aottg2\CustomAddon\AICadetsM2Watcher.cl` (unchanged; SHA-256 `612EA1E155B8380C4423DBBAC29B823CCCE5BDFF043B0C6CA4E44CB4B129BD6B`)

ENABLE IN GAME:
- `AICadetsWaveCadet`
- `AICadetsCommandPanel`
- `AICadetsM2Watcher`

DISABLE IN GAME:
- `AICadetsProbe`
- `AICadetsTraversal`
- `AICadetsTraversalReliable`
- `AICadetsWatcher`
- Every other active test add-on

MAP / MODE / HOST / RELEVANT SETTINGS: Fresh private master-host lobby, City 1 / Training / Waves; one owned M2 cadet and one stationary ordinary Titan in a clear street. The on-disk `m2-test` preset is City1 / Waves, has exactly the M2 trio, `GroundSteering=Direct`, and `TitanSmartMovement=true`; select Training for this session. Keep saved settings and native `AIEnabled` / `UsePathfinding` unchanged. Confirm the in-game enabled-add-on list, reported build tag, current driver, and lobby settings before starting. Do not use `bot-test-city` unless `AICadetsWatcher` is disabled; that preset enables it.

PRECONDITIONS: Confirm the panel shows `M2-locomotion-1-f8combo-2-holdrecovery`, one owned cadet, and the expected M2 add-on set. Start A/B trials from similar cadet-to-Titan geometry in separate fresh lobbies. Leave video and watcher logging running.

ACTIONS (one variable per run):
1. **Direct run:** click `ENGAGE + DIRECT` once. Give no more movement orders. Let the cadet pursue in the clear street until it completes a ground interval and reaches its first close ODM/anchor decision, or until 90 seconds elapse.
2. **Engine run:** restart the lobby with comparable geometry, click `ENGAGE + ENGINE` once, and use the same observation window. Do not issue Hold or Recovery during either A/B run.
3. **Hold/recovery run:** restart again, click `ENGAGE + ENGINE` once, and wait until active ground movement is confirmed by `motion_observed`. Click `HOLD position` once; after the cadet settles, click `RECOVER + RESUME ENGAGE` once. Then give no more orders and observe autonomous movement and target reacquisition for 30 seconds.

EXPECTED PHYSICAL RESULT: Compare measured displacement, path, and target-relative gain for Direct and Engine in clear geometry. Record whether the cadet reaches the 18-unit planar fallback radius, whether a physical ODM anchor attaches afterward, and whether pursuit resumes if no anchor is found. Hold passes only if active ground movement stops after the Hold order. Recovery passes only if the controller selects and performs its bounded route without steering input, then resumes Engage or automatically reacquires a target. Ground arrival, a `MoveTo` state, hook launch, or hook attachment alone does not establish a nape hit.

EXPECTED LOG EVENTS: Startup build/profile; `EngageDirect` / `EngageEngine` order acknowledgements; `motion_command`, `motion_observed`, `pursuit_progress`, `circling_detected`, `motion_segment_done`, `anchor_search_failed`, `hook_launch`, `hook_attached`, `recover_exhausted`; for the Hold run, `order_applied mode=Hold`, `motion_cancelled reason=user_hold`, observed stop, `manual_recovery_requested`, `reposition_start` / `reposition_end`, and resumed approach. Preserve any `attack_attempt`, attack state, damage attribution, or kill result if they occur, without treating animation as damage.

FAILURE / INTERRUPT CASES: Driver differs from the selected preset; the command is acknowledged but produces no displacement; repeated path without positive target gain; sustained circling or target loss; no anchor in clear geometry; recovery budget exhausts before autonomous approach resumes; Hold is issued outside active movement; movement continues after Hold; or the player must manually steer after Recovery.

ARTIFACTS TO RETURN: Separate Watch files and videos for Direct, Engine, and Hold/Recovery; panel startup/build and order acknowledgements; screenshot of active add-ons and lobby settings; saved preset name and `GroundSteering`; AoTTG2 product version (Unity version alone is insufficient); note the first fallback distance and every anchor / recovery outcome.

PASS / FAIL / PARTIAL / INCONCLUSIVE CRITERIA: Pass the ground comparison only when both runs show measured displacement and at least two consecutive intervals of positive target gain in comparable open geometry, without persistent circling or unrecovered route failure. Pass Hold only with active-motion cancellation and observed stop. Pass Recovery only with autonomous physical reposition and resumed Engage. Mark partial if movement occurs but the close anchor path or an interruption fails; mark inconclusive if driver, settings, add-on inventory, or geometry cannot be matched. Do not advance to M2-C1 attack acceptance until the M2-L0 ground and recovery gates pass.

ROLLBACK FILES OR COMMIT: Restore `AICadetsWaveCadet.cl` and `AICadetsCommandPanel.cl` from `C:\Users\vmorr\AppData\Local\Temp\AoTTG-M2-HoldRecovery-rollback-20261102-130500`; restore prior source from base commit `027ac43b2d77cbbaaa33b5a403b11de92177ea84` if needed. `AICadetsM2Watcher.cl` is unchanged.

CURRENT RESULT: **PARTIAL** — W3/W4/W5 were run on build `M2-locomotion-1-f8combo-2-holdrecovery`. W3 Direct reproduces wall blockage and near-zero recovery displacement. W4 Engine has strong initial pursuit but later negative target gain after a target switch. W5 confirms a physical Hold stop and recovery displacement, followed by `collision_risk` recovery exhaustion. See `2026-11-02-M2-L0-W3-W5-wall-encounter.md`. The planned clear-street matched A/B was not completed; do not treat these as a controlled comparison.
