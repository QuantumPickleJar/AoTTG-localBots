# Validation Card — atomic F8 Engage presets

STATUS: HISTORICAL DRAFT. M2-L0 is still partial on the current `f8combo-2` build. Do not use this older M2-C1 / `f8combo-1` card until the current M2-L0 ground and recovery gates pass; the active follow-up is `2026-11-02-M2-L0-clean-ground-followup.md`.

SESSION ID: M2-C1-20261102-F8
GOAL / CHANGED BEHAVIOR: One F8 action sets the selected steering driver and issues Engage as one controller command.
BRANCH / EXACT COMMIT / REPORTED BUILD: `feat/m2-exploration-and-orders` / working tree based on `ba0ba05469f604496680e972bbcb2cafee8e9bf7` / `M2-locomotion-1-f8combo-1`.
TEST PROFILE: M2-C1.

FILES TO COPY (source -> installed add-on location):
- `addons/AICadetsWaveCadet.cl` -> `C:\Users\vmorr\Documents\Aottg2\CustomAddon\AICadetsWaveCadet.cl`
- `addons/AICadetsCommandPanel.cl` -> `C:\Users\vmorr\Documents\Aottg2\CustomAddon\AICadetsCommandPanel.cl`
- `addons/AICadetsM2Watcher.cl` -> `C:\Users\vmorr\Documents\Aottg2\CustomAddon\AICadetsM2Watcher.cl` (unchanged; already matches the branch)

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

MAP / MODE / HOST / RELEVANT SETTINGS: Fresh private master-host lobby, City 1 / Training / Waves. Keep titan count, spawn conditions, loadout, and other movement settings comparable across the two trials. Earlier preflight found a saved preset with `GroundSteering=Engine`; the combined button should set the selected runtime driver regardless of that saved value. The later settings snapshot is documented in the live result addendum and does not verify the test lobby.

PRECONDITIONS: Restart into a fresh lobby for each steering variant. Confirm F8 reports `M2-locomotion-1-f8combo-1`, the selected M2 profile, one owned M2 cadet, and the active driver after the command.

ACTIONS (one variable per A/B run):
1. Select the same recipient scope in F8 for each trial.
2. Run A: press `ENGAGE + DIRECT` once. Do not separately press a ground-driver button or Engage.
3. Run B: recreate comparable conditions in a fresh lobby and press `ENGAGE + ENGINE` once.
4. Observe each cadet while it acquires and pursues a titan. Keep Hold as a separate manual command; it is not part of either preset.

EXPECTED PHYSICAL RESULT: Each single click should both engage titan acquisition and select the displayed steering driver. The cadet should physically move toward a target; a command acknowledgement, `MoveTo` state, or animation by itself is not proof of movement. Compare displacement, target-distance gain, path length, circling/reversals, and obstacle recovery. Do not infer an A/B winner from unmatched scenes.

EXPECTED LOG EVENTS: One command sequence per click; `engage_preset_applied preset=EngageDirect ground=Direct effective_mode=Engage` or `preset=EngageEngine ground=Engine`; `order_applied` acknowledging the same preset; published profile with the corresponding `ground=` value; actual `motion_observed` / `pursuit_progress` during ground pursuit. Direct uses `Human.Move`; Engine uses `Human.MoveTo` and may report `ai_state_after=MoveTo`.

FAILURE / INTERRUPT CASES: No M2 acknowledgement, rejected order, wrong driver in the published profile, cadet fails to acquire a target, no physical displacement, or interruption by a later command. Verify Hold still stops the cadet when issued separately.

ARTIFACTS TO RETURN: New watcher file, F8/build/profile evidence, video with the cadet and target visible, and saved game settings relevant to spawn conditions.

PASS / FAIL / PARTIAL / INCONCLUSIVE CRITERIA: Pass the combined-command behavior only if a single click is acknowledged with the intended driver and Engage becomes active. Report locomotion separately: require measured displacement and target-relative progress to claim physical pursuit. Mark the A/B comparison inconclusive if conditions differ materially or evidence is missing.

ROLLBACK FILES OR COMMIT: Restore `AICadetsWaveCadet.cl` and `AICadetsCommandPanel.cl` from `C:\Users\vmorr\AppData\Local\Temp\AoTTG-M2-F8Combo-rollback-20261102-123919`; keep the previously deployed M2 watcher. The source change is confined to those two add-ons.

## Live result addendum — Watch26–Watch29 and November 2 clips

RESULT: **PASS for the one-click F8 preset and acknowledgement; PARTIAL for physical movement; INCONCLUSIVE for the Direct-versus-Engine comparison and full M2-L0 acceptance.**

- Startup identifiers: all four watcher records report controller build `M2-locomotion-1-f8combo-1`. The watcher header itself remains `AICadetsM2Watcher v3 combat-arc-5`. Installed copies of WaveCadet, CommandPanel, and M2Watcher were present at test review. The product-level AoTTG2 version and exact runtime add-on enable/disable list were not captured.
- Direct: Watch26 sequence 2 and Watch27 sequence 3 each log `EngageDirect` applied. Watch26 measures 45.84 displacement / 46.66 path / +33.89 target gain. Watch27 measures 119.67 displacement / 132.26 path / +104.78 target gain. Watch29 sequence 5 also applies `EngageDirect` but records no physical-motion sample.
- Engine: Watch28 sequence 4 logs `EngageEngine` applied and records ten motion/progress samples. The first sample measures 131.04 displacement / 158.98 path / +119.64 target gain. Later samples vary; some show near-zero movement or negative gain. `ai_state=MoveTo` is not counted as movement proof.
- All four logs have zero `circling_detected` and zero Hold orders. Direct records repeated blocked routes and exhausted recovery. Engine also records blocked/recovery activity, including exhausted recovery. Neither driver has passed a controlled obstacle-recovery test. Watch26 records four attack attempts, all with `confirmed_damage=false`.
- The clip named `engage-engine-2026.11.02 - 12.49.57.65.mp4` displays `APPLIED #5 EngageDirect`; Watch28 contains only Engine sequence 4. This clip is not paired with Watch28. Watch29 separately confirms Direct sequence 5.
- On-disk deployed-file SHA-256 values: WaveCadet `3B54F3700F12C1FF50C7FEC1F9596FD023EBF7EF5D4C15BC938EC0841EA2AA0A`; CommandPanel `F8C0C980E02D04BB3870269AEC439D3B686284CB6EEA5A94DC004C93C3DF01C5`; M2Watcher `612EA1E155B8380C4423DBBAC29B823CCCE5BDFF043B0C6CA4E44CB4B129BD6B`. WaveCadet and CommandPanel contain the expected `f8combo-1` tag and combined-button handlers. The two corresponding source files are currently deleted from the checkout, so deployed-to-working-copy hash parity could not be checked.
- The latest `Player.log` reports Unity `2023.1.22f1`, with no AoTTG2 product/build ID found. It logs native Human/Titan NavMesh-agent startup warnings; the records do not map those warnings to the M2 cadet. Saved `Settings/InGame.json` currently selects Forest / Waves, lists no add-ons, and contains no `GroundSteering` value, so it does not verify the active City 1 test settings.

NEXT VALIDATION: repeat a matched Direct/Engine run with the same stationary target and start distance, capture the exact AoTTG2 product version and active add-on list, then issue Hold during measured ground movement. Keep native AI flags unchanged. Capture a separate result for obstacle recovery and do not infer attack success from animation or proximity.
