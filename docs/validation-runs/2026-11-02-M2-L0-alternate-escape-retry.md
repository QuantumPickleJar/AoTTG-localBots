# Validation Card — M2 alternate-side ground escape retry

SESSION ID: M2-L0-20261102-ESCAPE-RETRY

GOAL / CHANGED BEHAVIOR: After the first ground escape route produces less than 2 units of physical displacement, spend the existing second recovery attempt on the opposite-side route. If that route also produces less than 2 units, ban the target temporarily and observe; do not loop.

BRANCH / EXACT COMMIT / REPORTED BUILD: `feat/m2-exploration-and-orders` / `1ed9e7666d09b0d47a1b4fe3c01406d65f8459bc` / `M2-locomotion-1-f8combo-3-escape-retry`.
TEST PROFILE: **M2-L0**.

## Files to deploy and verify

- Deploy `addons/AICadetsWaveCadet.cl` to `C:\Users\vmorr\Documents\Aottg2\CustomAddon\AICadetsWaveCadet.cl`. Deployed SHA-256: `0CEE1C59489E23585F9653078AC5B5EDB3348D2A46BA88E0FC0E5872F413D2AC`.
- `AICadetsCommandPanel.cl` is already present and hash-matches this branch: `8E6EB2B708F6A67BF7C9D5D7E0BD23B9DCBA1418910239CBDAAE6AE96EC1E17C`.
- `AICadetsM2Watcher.cl` is already present and hash-matches this branch: `612EA1E155B8380C4423DBBAC29B823CCCE5BDFF043B0C6CA4E44CB4B129BD6B`.
- WaveCadet's installed predecessor was backed up at `C:\Users\vmorr\AppData\Local\Temp\AoTTG-M2-EscapeRetry-rollback-20261102-135601\AICadetsWaveCadet.cl` (SHA-256 `6B0160568948653428E6B1A3DDE9128A571EF93C2F368CFE227035BFFC9C79B7`).

## Add-ons

**Enable exactly:**

- `AICadetsWaveCadet`
- `AICadetsCommandPanel`
- `AICadetsM2Watcher`

**Disable:**

- `AICadetsProbe`
- `AICadetsTraversal`
- `AICadetsTraversalReliable`
- `AICadetsWatcher`
- Every other active test add-on

The saved `m2-test` preset is City1 / Waves with the M2 trio and Direct steering. The currently selected saved preset is `Set 1` (Forest / Waves, no add-ons). Do not use `bot-test-city` without removing `AICadetsWatcher`; that preset enables the M1 watcher and sets Engine.

## Lobby and preconditions

- Restart AoTTG2 before the run. The game process was running when the WaveCadet file was deployed, so the loaded Custom Logic could still be cached.
- Create a **fresh private master-host** lobby: City 1 / Training / Waves, one owned cadet, one ordinary Titan, and no other clients for this M2-L0 test.
- Record the AoTTG2 product build, lobby privacy, enabled add-ons, saved preset, and ground steering value. Do not infer these from the saved file alone.
- Keep native `AIEnabled` and `UsePathfinding` settings unchanged. Confirm the F8 panel shows build `M2-locomotion-1-f8combo-3-escape-retry` and the selected ground driver before starting.
- Use the same building/alley encounter as W3 as closely as practical. Do not manually steer, issue Recovery, or reposition the cadet after Engage begins; the new behavior must run autonomously.

## Actions

1. In a fresh lobby, use the F8 **Engage + Direct** one-click action. Keep the panel/build identifier and cadet visible in the recording. Let the run continue through the blocked route and both bounded recovery attempts, up to 90 seconds if needed.
2. Restart into another fresh private lobby with the same map, mode, add-on list, target conditions, and approximate start geometry. Change only the driver by using **Engage + Engine** once. Capture physical movement and target-relative progress as a regression comparison.
3. Save the full M2 watcher logs and both videos. Include product build, settings, run IDs, and whether the obstacle encounter reproduced.

## Expected telemetry and physical outcome

- Direct logs `ground_route_blocked`, `reposition_start` attempt 1, and `reposition_end moved<2` at the known obstacle.
- It then logs `reposition_retry ... next_attempt=2`, starts attempt 2 with a different goal, and retains the same Titan through the retry.
- **Physical acceptance:** watcher position samples show at least 2 units of displacement from the second reposition start, followed by renewed same-target approach and positive target-relative progress. A `MoveTo` state or command by itself does not pass.
- If attempt 2 also moves less than 2 units, the expected bounded behavior is to enter Observe and temporarily ban that Titan without a third escape retry. This is a safe stop but **does not pass obstacle recovery**.
- Engine is a regression check only, not a controlled steering winner comparison. Measure actual displacement and target gain; API command/state logs alone do not count.

## Result and evidence fields

- Outcome: **PARTIAL** — build and one-click mode selection passed; persistent ground obstruction and recovery exhaustion remain; the alternate no-displacement retry branch was not exercised.
- Startup/build: Watch6 reports `M2-locomotion-1-f8combo-3-escape-retry`, `ground=Direct`, and `EngageDirect` applied as sequence 1. Watch7 reports the same build, `ground=Engine`, and `EngageEngine` applied as sequence 2. Both identify one owned cadet and target 1005.
- **Direct / Watch6:** one measured ground-pursuit interval at t=20.260 moved 51.875 units (path 67.298) and gained 19.149 units on Titan 1005. The run later recorded 14 `ground_route_blocked`, 10 reposition starts/ends, and five `recover_exhausted`. Every `reposition_end` recorded at least 8.408 units of physical displacement (maximum 39.880); there were zero `reposition_retry` events. The new `<2`-unit retry condition therefore did not run. The repeated blockage locations are not the W3 coordinates, so this does not reproduce the same corner. Two attack attempts occurred at 4.735 and 4.563 units; both reported `confirmed_damage=false`. The second observed an Attack animation, which still does not prove damage.
- **Engine / Watch7:** zero `ground_route_blocked`, 12 measured pursuit intervals, two recovery moves of 23.133 and 14.814 units, zero `reposition_retry`, and one `recover_exhausted reason=ground_not_advancing` at t=116.113. Early movement was real: t=23.280 recorded 42.136 units displaced and +4.809 target gain. Near the Titan, distance remained around 305–344 units; target gains were mostly near zero or negative after t=53.821, including -15.268 and -21.930 after the first reposition. This is physical movement without sustained closing progress, not an Engine pass.
- Retry telemetry and different goal: **not exercised**; neither log contains `reposition_retry`, and all measured reposition moves exceeded 2 units.
- Physical displacement / target progress: Direct had one measured pursuit interval and repeated physical recovery moves but continued to hit blocked routes and exhaust recovery. Engine had repeated physical displacement but failed to sustain target gain and exhausted recovery. Ground-recovery gate: **not passed**; the specific under-2-unit retry change remains untested.
- Evidence filenames: `AICadetsM2Watch6.txt`, `AICadetsM2Watch7.txt`, `engage-direct-2026.11.02 - 14.16.15.76.mp4`, `engage-direct-2026.11.02 - 14.17.01.77.mp4`, `engage-engine-2026.11.02 - 14.19.26.78.mp4`. Product build, lobby privacy and the complete enabled-add-on list are not recorded.
- Limitations / next focused check: W6 began a long pursuit from approximately `(-11, 10, -555)` toward a Titan initially near `(361, 10, 508)`; it is not the W3 close-corner setup. Repeat Direct at the known W3 corner/start geometry to produce the observed under-2-unit escape and verify the alternate goal and physical result. Do not add another gameplay change before that condition is tested. Neither run validates damage or Titan kills.

## Rollback

- Source rollback: restore `addons/AICadetsWaveCadet.cl` from commit `ebda598f9bfe8ace0d7749c676e8df9b0352f98e` (the pre-retry f8combo-2 source).
- Installed rollback: copy `C:\Users\vmorr\AppData\Local\Temp\AoTTG-M2-EscapeRetry-rollback-20261102-135601\AICadetsWaveCadet.cl` back to the installed `CustomAddon` path, then restart AoTTG2.
