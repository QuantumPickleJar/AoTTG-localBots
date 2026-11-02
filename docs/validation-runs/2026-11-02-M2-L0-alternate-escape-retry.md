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

- Outcome: **NOT YET RUN**.
- Direct obstacle reproduced: yes / no.
- Retry telemetry and different goal: pass / fail / inconclusive.
- Physical displacement and same-target progress after attempt 2: pass / fail / inconclusive.
- Engine regression: pass / fail / inconclusive.
- Evidence filenames / run IDs: pending.
- Limitations: Direct and Engine remain sensitive to route, spawn and Titan geometry. Two clear-ray candidates do not prove NavMesh reachability. This check does not validate attacks, damage attribution, or Titan kills.

## Rollback

- Source rollback: restore `addons/AICadetsWaveCadet.cl` from commit `ebda598f9bfe8ace0d7749c676e8df9b0352f98e` (the pre-retry f8combo-2 source).
- Installed rollback: copy `C:\Users\vmorr\AppData\Local\Temp\AoTTG-M2-EscapeRetry-rollback-20261102-135601\AICadetsWaveCadet.cl` back to the installed `CustomAddon` path, then restart AoTTG2.
