# AI Cadets — gameplay validation harness

**Status:** Operational test-session playbook, November 2, 2026. **This is documentation, not an executable harness or evidence that a game test passed.** Branch: `feat/m2-exploration-and-orders`. Keep M2 PR #6 draft until actual gameplay acceptance.

**Start here:** Run Luna Prompt 1 to inspect and prepare the latest feature-branch deployment, then run profile `M2-L0` *before* Prompt 2. Do **not** merge the PR merely to test. A feature branch can be checked out and copied directly to AoTTG2's Addons folder.

## Rules for every Luna/Codex implementation session

1. Identify which deployed `.cl` files the proposed changes affect, and choose a profile from the matrix below. If no game-executed code changes, static/unit checks may suffice. For actual `.cl` changes, a gameplay test is required before claiming the behavior validated.
2. Before requesting a test, present a **Validation Card** with: profile ID, exact source branch/commit/build tag; files to deploy; **enable** and **disable** sets; map/mode/host settings; steps; expected telemetry *and physical outcome*; known limitations; rollback commit/files; evidence to capture; explicit pass/fail/inconclusive result fields.
3. Only one active controller may own each test cadet. Do not run M0 probe, M1 traversal, M2 WaveCadet and a new movement/Carry probe simultaneously. For every `M2-L0` and `M2-C1` gameplay session, `AICadetsM2Watcher` is **required**. No M2 gameplay acceptance or iteration result counts without a saved, reviewed watcher trace. Before starting, confirm the watcher has a free output slot and preserve existing watcher files in a hash-verified backup. If the watcher fails to start, stops early, or its output is missing or corrupt, mark the gameplay result **inconclusive** and fix telemetry before the next iteration. Observer add-ons must be confirmed passive and compatible with that test; do **not** assume the M2Watcher works with independent probes.
4. Preserve original `.cl` files, a copy of working deployed scripts and existing watcher logs. Protect local changes using `git status` before `git switch` / `git pull --ff-only`. Source branch changes do not auto-deploy to `Documents/AoTTG2/Addons/` unless verified local automation exists.
5. Change **one variable at a time** within A/B sessions (e.g. Direct versus Engine), with the same map, spawn, Titan conditions, settings and approximate geometry as far as possible. Restart the lobby for a clean comparison. Do not equate an API dispatch or attack animation with movement success, blade damage or a rescue.
6. Use a private master-host lobby for initial tests. Avoid testing on unconsenting players or on public servers. Only advance to multiplayer, Waves accounting, or mobile performance after the earlier single-cadet, single-host tests.
7. Record results as `pass`, `fail`, `partial` or `inconclusive` with the required M2 watcher trace and controller events; video is supplementary. If a test fails, the next Luna session should diagnose its evidence **before** introducing additional features. If an M2 run has no valid watcher trace, it cannot pass an acceptance gate.
8. A focused smoke check is required after each **gameplay-changing** revision; a broader regression check is required before merging major milestones. No need to replay the entire matrix for documentation-only, formatting-only, or definition-only catalog changes.

## Current exact add-on inventory (verified in the M2 feature branch)

- `addons/AICadetsProbe.cl`: known-good M0 standalone probe.
- `addons/AICadetsTraversal.cl`: M1 two-anchor baseline controller.
- `addons/AICadetsTraversalReliable.cl`: M1 reliability candidate controller.
- `addons/AICadetsWatcher.cl`: M1 watcher.
- `addons/AICadetsWaveCadet.cl`: M2 runtime controller.
- `addons/AICadetsCommandPanel.cl`: M2 host F8 command panel.
- `addons/AICadetsM2Watcher.cl`: M2 observer.

An add-on file existing in the installed folder is **not** proof that it is disabled in the lobby. Review enabled add-ons in game creation.

## Profiles: exactly what to enable

| Profile | Use it | Enable | Disable | Acceptance focus |
|---|---|---|---|---|
| **M2-L0** | After Prompt 1, *before* Prompt 2 | `AICadetsWaveCadet`, `AICadetsCommandPanel`, `AICadetsM2Watcher` (watcher required) | `AICadetsProbe`, `AICadetsTraversal`, `AICadetsTraversalReliable`, `AICadetsWatcher`, any future active test probes | `M2-locomotion-1`: Direct/Engine A/B, planar approach, stalls, Hold, recovery |
| **M2-C1** | After each Prompt 2 gameplay-code revision | Same M2 trio | All M0/M1 and independent probes | Physical ODM pursue/close/strike; attack animation **and** attributed damage/kill; target recovery |
| **M1-R** | Only when M1 traversal regression is implicated | Exactly **one of** `AICadetsTraversal` or `AICadetsTraversalReliable`, optional `AICadetsWatcher` | Both M2 controller/panel/watcher, `AICadetsProbe`, the *other* M1 controller, all new active probes | Two anchors, release, gas, collisions/recovery, reset |
| **M0-R** | Only when spawn/low-level hook regression is suspected | `AICadetsProbe` alone | All M1/M2 controllers and independent probes; omit watchers unless explicitly justified | Single-hook reference behavior |
| **PRIM-I** | After Prompt 3 creates an *isolated* movement test add-on | **Only** the newly created movement probe; add its dedicated passive logger only if verified | M0/M1/M2 controllers and their mode-specific watchers | Ground Dodge, Jump, directional Dash, `UseGas` pulses, airborne variants, gas costs, state/velocity/displacement |
| **COMP-I** | After Prompt 4 changes only composition parsing/selection code | No gameplay session needed if no runtime behavior changes; run source/mock tests | N/A | Catalog filter, empty/one-option safety, equipped-special swap, novelty soft scoring, gas reserve |
| **COMP-E** | After Prompt 4 affects executable M2 behavior | M2 trio, with one controller-owned cadet | M0/M1 and independent probes | One character: capability filtering, selected maneuver execution and actual fallback; no fictional specials |
| **CARRY-I** | First Prompt 5 rescue milestone | **Only** new dedicated Carry mechanics probe; compatible passive observer if validated | M0/M1/M2 controller add-ons and other active probes | Verify true `Carry` special activation, target selection, `IsCarried`, pickup/transport/release; unsupported behavior remains gated |
| **RESCUE-E** | After Prompt 5 integrates intervention or extraction | M2 trio plus *only if necessary* an independently validated passive rescue observer | M0/M1 and independent active probes | Non-Carry rescue first, then Carry-enabled rescue; observed grabbed/death/survival outcomes and interrupt priorities |
| **ADAPT-E** | After Prompt 6 changes adaptive scheduling/execution | M2 trio; optional verified passive performance instrumentation | M0/M1 and independent active probes | Movement/attack/rescue regressions, event-triggered response, stable control, frame-time/CPU on real devices |
| **MOBILE-R** | When AoTTG2 mobile build permits equivalent test setup | Same tested feature add-ons as that milestone, using supported mobile install method | Conflicting controllers and unproven instrumentation | Gameplay parity, performance, device-specific input/state limitations. Do not assume PC plugin or addon path works on mobile |

**Probe filenames for PRIM-I and CARRY-I are placeholders until created by Luna.** Luna must fill in actual filenames/identifiers in its Validation Card and update this harness before asking the user to enable them. `AICadetsM2Watcher` is tailored to M2, **not** automatically suitable as a logger for isolated probes.

## First required test: M2-L0

- Source: `feat/m2-exploration-and-orders`, gameplay revision `ba0ba05` (`M2-locomotion-1`); later documentation-only commits do not alter the controller.
- Host: fresh private master-host City 1 / Training / Waves; only the M2 trio enabled; saved addon settings may override defaults.
- Ensure the F8 panel reports `M2-locomotion-1` and choose **GROUND: direct steering (default)**; independently verify reported `ground=Direct`.
- **Run A**: stationary Titan in open street, Engage. Inspect actual displacement and `target_gain`, `motion_command request=Human.Move`, `motion_observed`, `pursuit_progress`, absence of `MoveToTarget` ground pursuit. Confirm one no-anchor fallback crosses its **18-unit planar** arrival threshold (not a nape hit claim).
- **Run B**: recreate similar scenario, switch F8 to **GROUND: engine steering test**. Look for `Human.MoveTo`, `ai_state_after=MoveTo`, and compare path length, net displacement, closing distance, reversals and recovery. A state flag does not prove movement.
- **Run C**: test Hold during ground pursuit and verify `motion_cancelled` and actual stop; resume Engage and Explore; verify recovery against building corner, moving Titan, target loss and low-gas diversion when reproducible.
- Record whether ground circling still occurs, and whether a selected target is retained through bounded recovery. Watch20 was evidence from the *previous* version, not proof the new steering fix works.
- Pass only if the claimed behaviors are observed in-game without dangerous regressions. If command strings appear but there is no displacement, mark **fail** or **inconclusive**, not pass.

## Additional session cards

**M2-C1 (after Prompt 2):** start with a single exposed Titan, then moving Titan, then building corner; collect current build ID, `orbit_intercept`, `attack_attempt`, actual Human Attack state, damage/death attribution and HUD/wave consistency. A visible swing without damage is **partial**, not a confirmed combat kill.

**PRIM-I (after Prompt 3):** fresh quiet/clear test area; one movement probe only. Isolate `Dodge`, `Jump`, `Dash(direction)`, `UseGas(true/false)`, Jump-then-Dash, then an airborne dash; record before/after gas, position, velocity, state, duration and outcome. Do not infer the combination works merely because individual commands are documented.

**COMP-E (after Prompt 4):** use one M2 cadet and a catalog containing validated and definition-only options. Test special equipment mismatches, cooldown, low gas, only one feasible maneuver, invalid catalog entry and selection logging. Inspect actual commanded motion: definition-only moves must not execute.

**CARRY-I + RESCUE-E (Prompt 5):** first measure the real Carry special in isolation with an eligible test target; only then test integrated rescue. Run a non-Carry scenario of endangered player, then a Carry-equipped scenario. Record threat, victim state, decision interruption, attack or special activation, post-event victim survival, actual `IsCarried` transitions and whether any rescue is causally supported. A victim surviving is not sufficient evidence the cadet saved them. Use a consenting private test setup; add a second client only where required.

**ADAPT-E + MOBILE-R (Prompt 6):** first run comparable one-cadet desktop scenes before and after the scheduler refactor; check real movement, no control thrash, correct interrupts and action outcomes. Increase to multiple cadets only after they are actually implemented. Benchmark logged computation / frame-time on desktop, then supported Android environments; don't promise mobile FPS or imply support without direct device testing.

## Generic Validation Card — Luna must output this whenever a gameplay check is needed

```text
SESSION ID:
GOAL / CHANGED BEHAVIOR:
BRANCH / EXACT COMMIT / REPORTED BUILD:
TEST PROFILE: [M2-L0 | M2-C1 | M1-R | M0-R | PRIM-I | COMP-E | CARRY-I | RESCUE-E | ADAPT-E | MOBILE-R]
FILES TO COPY (source -> installed add-on location):
ENABLE IN GAME:
DISABLE IN GAME:
MAP / MODE / HOST / RELEVANT SETTINGS:
PRECONDITIONS:
ACTIONS (one variable per A/B run):
EXPECTED PHYSICAL RESULT:
EXPECTED LOG EVENTS:
FAILURE / INTERRUPT CASES:
ARTIFACTS TO RETURN (watch file, screenshots/video, settings, exact log messages):
PASS / FAIL / PARTIAL / INCONCLUSIVE CRITERIA:
ROLLBACK FILES OR COMMIT:
```

## Per-session results record

Use `docs/validation-runs/<date>-<profile>-<short-id>.md` for a short manual report when appropriate; filenames need not contain a player's identity. Store bulky private video and logs outside Git unless intentionally reviewed for publication.

```md
# Validation result
- Session ID:
- Profile:
- Date:
- AoTTG2 build / map / mode / host:
- Commit / build tag:
- Installed files and enabled add-ons:
- Explicitly disabled add-ons:
- Relevant saved settings:
- Test actions and observed physical outcomes:
- Watcher log / video filenames:
- Code-reported commands vs observed motion:
- Outcome: PASS / FAIL / PARTIAL / INCONCLUSIVE
- Verified / observed / inferred:
- Remaining issue and next action:
- Rollback status:
```

## How sessions and prompts connect

```text
Prompt 1 (deploy/preflight only)
  -> M2-L0 live validation
  -> Prompt 2 (only as indicated by M2-L0 findings)
       -> M2-C1 after every material gameplay fix; repeat until reliable enough
  -> Prompt 3 isolated probe -> PRIM-I
  -> Prompt 4 catalog+profile unit checks -> COMP-E if executable M2 changes
  -> Prompt 5 Carry mechanics probe -> CARRY-I
       -> intervention integration -> RESCUE-E (non-Carry, then Carry)
  -> Prompt 6 adaptive scheduler -> ADAPT-E -> MOBILE-R when feasible
```

Do not needlessly delay future isolated design/tests for unrelated unresolved combat if the probe cannot interfere with M2; however, **never claim integrated rescue, special maneuvers or combat are validated until their own physical acceptance gates pass**.

## Related documentation

- [M2 locomotion field procedure](M2_LOCOMOTION_STABILIZATION.md)
- [M2 one-click Hold capture](M2_AUTO_HOLD_CAPTURE.md)
- [M2 full combat acceptance matrix](M2_TESTING.md)
- [M1 reference procedure](M1_TESTING.md)
- [M3 composition and rescue design](M3_COMPOSITION_RESCUE_DESIGN.md)
