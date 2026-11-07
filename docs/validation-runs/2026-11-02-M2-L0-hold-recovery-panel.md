# Validation Card — F8 Hold and Recovery commands

SESSION ID: M2-L0-20261102-HR
GOAL / CHANGED BEHAVIOR: Keep one-click Hold and add one-click Recovery + Resume Engage. The controller uses its existing bounded route selection and resumes autonomous target acquisition/approach after the command.
BRANCH / EXACT COMMIT / REPORTED BUILD: `feat/m2-exploration-and-orders` / `a5e1b20842654f3bee77f0be92176f609e54bbdb` / `M2-locomotion-1-f8combo-2-holdrecovery`.
TEST PROFILE: M2-L0.

FILES TO COPY (source -> installed add-on location):
- `addons/AICadetsWaveCadet.cl` -> `C:\Users\vmorr\Documents\Aottg2\CustomAddon\AICadetsWaveCadet.cl`
- `addons/AICadetsCommandPanel.cl` -> `C:\Users\vmorr\Documents\Aottg2\CustomAddon\AICadetsCommandPanel.cl`
- `addons/AICadetsM2Watcher.cl` -> `C:\Users\vmorr\Documents\Aottg2\CustomAddon\AICadetsM2Watcher.cl` (unchanged)

ENABLE IN GAME:
- `AICadetsWaveCadet`
- `AICadetsCommandPanel`
- `AICadetsM2Watcher`

DISABLE IN GAME:
- `AICadetsProbe`
- `AICadetsTraversal`
- `AICadetsTraversalReliable`
- `AICadetsWatcher`
- All other active test add-ons

MAP / MODE / HOST / RELEVANT SETTINGS: Fresh private master-host lobby, City 1 / Training / Waves; one owned M2 cadet and a stationary Titan in a clear street, then a reproducible building-corner route. Record the AoTTG2 product build, lobby privacy, loaded add-ons, and saved settings. Keep native `AIEnabled` and `UsePathfinding` unchanged.

PRECONDITIONS: Verify the panel reports `M2-locomotion-1-f8combo-2-holdrecovery`, `ground=Direct` or `ground=Engine`, and one owned cadet. Run each driver in a fresh lobby with comparable target and start geometry.

ACTIONS (one variable per A/B run):
1. Select `ENGAGE + DIRECT` or `ENGAGE + ENGINE` once and confirm the order acknowledgement.
2. During measured ground pursuit, click `HOLD position` once. Do not issue manual movement or another steering command.
3. After the hold acknowledgement, click `RECOVER + RESUME ENGAGE` once. The controller must choose and execute its existing bounded recovery/reposition logic, then continue autonomous Engage.
4. Repeat the same sequence with the other driver in a fresh lobby. Preserve video and watcher logs for each run.

EXPECTED PHYSICAL RESULT: Hold cancels owned movement and the cadet settles. Recovery begins without player movement input, retains a valid target where possible, selects a clear bounded route, and resumes pursuit. If the target was lost, it returns to target acquisition and continues Engage. An acknowledgement, `MoveTo` state, or animation alone is insufficient; record displacement, target gain, path, and obstacle outcome.

EXPECTED LOG EVENTS: Hold: `order_received mode=Hold`, `order_applied mode=Hold`, `motion_cancelled reason=user_hold`, and observed stop. Recovery: `order_received mode=Recovery`, `manual_recovery_requested`, `state_transition ... to=Recover`, bounded `escape_route` / `reposition_start` / `reposition_end` where available, and subsequent `PlanApproach` or `AcquireTarget`. Preserve any `recover_exhausted` result as a failure or partial outcome; do not bypass the recovery budget.

FAILURE / INTERRUPT CASES: Hold fails to stop movement; Recovery is rejected or unacknowledged; recovery repeats the blocked route without progress; target identity changes unexpectedly; player input is needed to steer/restart; or the cadet does not resume autonomous Engage.

ARTIFACTS TO RETURN: Watch file for each driver, video showing panel and cadet/target, current settings, exact game build, and active add-on list.

PASS / FAIL / PARTIAL / INCONCLUSIVE CRITERIA: Pass Hold only with acknowledgement and observed stop. Pass Recovery only with acknowledgement, autonomous recovery/resume, and measured movement or a clear documented no-route outcome. Report Direct/Engine comparison separately; mark it inconclusive if route conditions differ. No live validation has been performed for this revision yet.

ROLLBACK FILES OR COMMIT: Restore `AICadetsWaveCadet.cl` and `AICadetsCommandPanel.cl` from `C:\Users\vmorr\AppData\Local\Temp\AoTTG-M2-HoldRecovery-rollback-20261102-130500`; `AICadetsM2Watcher.cl` is unchanged.

DEPLOYMENT PREPARED: The two updated files have been copied to `C:\Users\vmorr\Documents\Aottg2\CustomAddon`. WaveCadet SHA-256: `6B0160568948653428E6B1A3DDE9128A571EF93C2F368CFE227035BFFC9C79B7`. CommandPanel SHA-256: `8E6EB2B708F6A67BF7C9D5D7E0BD23B9DCBA1418910239CBDAAE6AE96EC1E17C`. Restart AoTTG2 before testing so it loads the new build tag and panel button.

LOCAL SOURCE CHECKS: `python -m unittest discover -s tests` passed all 140 tests; `git diff --check` passed. These checks exercise translated Custom Logic and mocks, not the installed game parser or physical behavior.

## Live result addendum — November 2 Watch30 / Watch0 / Watch1

RESULT: **PARTIAL.** The new build loaded and the panel commands were accepted. The manual recovery request did execute a bounded reposition and returned to autonomous Engage. Hold's physical stop is unverified because it was issued during `WaitLanding`, before active ground movement. Ground pursuit is not accepted: Watch30 reports circling and later exhausts recovery near the ground-arrival threshold. No attack was attempted in these records.

- Watch30 is the same run as `no-hhold-engage-engine-2026.11.02 - 13.17.00.68.mp4`, as reported by the user. It reports build `M2-locomotion-1-f8combo-2-holdrecovery`, Engine sequence 1, ten measured ground-motion samples and one `circling_detected`. Engine recorded early samples of 25.01 displacement / 24.31 target gain, 69.87 / 63.98, and 69.90 / 63.35. At t=95.596, path was 58.085 for 2.989 displacement with -0.284 target gain; bounded recovery moved 4.033 and pursuit resumed with positive gain. At t=117.372, the cadet crossed the fallback radius at 17.850 planar / 24.326 nape distance. The next anchor search failed; the subsequent fallback was already within 18 units and recovery was exhausted with `no_anchor_at_ground_arrival`. No attack/damage/death event followed.
- Watch0 records Hold sequence 2 while controller state was `WaitLanding`; the Hold order applied, but there was no active ground command to cancel or physical stop to verify. Recovery sequence 3 applied from Hold with target 1005 retained. It selected an escape route, moved 14.98 units, and transitioned to `PlanApproach`. After a later blocked route exhausted recovery, the controller entered Observe and reacquired a target automatically. A later manual Engage (sequence 4) and Engine preset (sequence 5) make the rest of Watch0 unsuitable as a clean Direct/Engine comparison.
- Watch1 accepts Direct sequence 6 while in Observe, but contains no `motion_observed` or `pursuit_progress` samples. It records eight blocked routes and three exhausted recoveries; this run does not establish Direct physical pursuit. Watch0 does contain one Direct interval at t=77.699 with 70.269 displacement and +70.269 target gain, but it is separated from Engine by manual orders and is not a matched A/B.
- Across these three logs there are zero attack attempts and zero damage/death observations. The supplied Engine video shows the M2 panel and physical traversal, but the watcher trace is the measured movement source. Game product version, saved lobby settings and exact enabled/disabled add-ons remain uncaptured.

DIAGNOSIS: Engine is the stronger observed ground driver in these runs, but the comparison remains uncontrolled because Watch0 changes drivers mid-session and Watch1 has no measured Direct segment. The confirmed close failure is anchor acquisition after reaching a ground approach point, not a failed damage outcome. The one circling segment is bounded and followed by measurable recovery; it is not evidence of a permanent steering reversal. Preserve the current controller while the next run isolates the failed no-anchor condition and tests Hold during active ground movement. Do not advance to combat changes until ground pursuit and Hold/recovery acceptance improve.
