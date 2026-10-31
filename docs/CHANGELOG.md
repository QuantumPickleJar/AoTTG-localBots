## M2 navdiag-3 (unreleased)

- Defer airborne no-anchor replanning until landing or a bounded timeout; preserve the target and avoid burning recovery attempts before physics can advance.
- Probe both recovery corridors before dispatching a ground waypoint; pause if both are blocked. Add game-time fixed-tick health telemetry without altering personality settings or the documented baseline callback frequency.
- Watch5 also identifies an M1R demo without an M2 controller. Narrow-alley movement and attacks still need in-game validation.

## M2 navdiag-2 (unreleased)

- Prevent rapid target/recovery ping-pong with a six-second stationary observation before retrying. Detect inefficient closed-loop ground pursuit from path length versus net displacement and pause rather than continue circling.
- Watch3 captured an actual attack attempt but no confirmed damage; its first 3000 decision events saturated after repeated anchor/recovery failures. Live confirmation of the new pause and circle heuristic remains outstanding.

## M2 navdiag-1 (unreleased)

- Identified installed 97e9e16 files and concurrently enabled M1 demos in the Watch5 investigation. Added visible F8 build/profile reporting and passive owned-cadet roster records to distinguish stale controllers and demo bots.
- Added scoped Engine/Direct ground-pursuit comparison buttons. Direct is an opt-in, obstacle-checked diagnostic using ordinary Move input; Engine remains default and Explore remains unchanged.
- Restored 5 Hz moving observations within the bounded longer recorder. Added tests for driver scope, Hold, blocked routes, controller shutdown and visible configuration. Root cause of native spiralling remains unconfirmed; use M2_NAVIGATION_AB_TEST.md.

## M2 tactical pursuit and profile foundation (unreleased)

- Probe existing ODM anchor geometry during distant ground pursuit without cancelling ground navigation on an empty probe.
- Measure directional pursuit progress; keep the current target through bounded ground repositioning before abandoning it. Momentum and obstruction influence new acquisition only.
- Add named profiles with 1–5 persistence, aerial preference, and reposition skill settings. Defaults retain explicit Explore behavior and hard movement/resource/attack limits.
- Watch3/4 and video findings, profile combinations, rollback and next field trials are documented in M2_BEHAVIOR_PROFILES.md. Engine spiral steering and combat remain unverified.

## M2 Watch1 follow-up (unreleased)

- Documented observed Engage movement and Explore stall without inferring target-directed progress from position alone. One spawned cadet is current design; multi-cadet cooperation is not yet implemented.
- Extended the optional watcher to five minutes / 2000 records and added per-cadet, timestamped target and navigation status. Publish a bounded per-cadet controller decision trace by default for the optional local watcher. The collector still needs live interpreter and performance validation.

## M2 Search & Destroy follow-up (unreleased)

- Fixed a source-level pursuit loop that immediately cancelled ground fallback after an unsuccessful anchor search within the 68-unit ODM threshold. Added timed pursuit, stall-to-patrol recovery, and target ban. The actual cause of the reported live Engage failure remains unconfirmed.
- Treat a missing target after an attack as lost, not a confirmed kill; log callback attribution independently. Retain physical attacks and the Explore navigation path.
- Stop navigation on supply timeout, approach marked supply points more closely, and retain observed-gas-only refill verification. Added a bounded opt-in M2 watcher and mission/event diagnostics. Live attack and resupply remain unverified.

# Changelog

## M2 Wave-mode combat prototype â€” unreleased, pending gameplay validation

- Add `addons/AICadetsWaveCadet.cl` as an isolated M2 prototype:
  - autonomous target acquisition from `Game.Titans`
  - bounded target retries/replans and target banning cooldown
  - traversal-driven approach/retreat/recovery using M1-style hook/gas control
  - attack attempt with `Human.Attack(true/false)` and callback-based damage/death observation
  - mission snapshots and bounded machine-readable diagnostics
  - optional local run report persistence (`SaveRunReport`)
- Add `docs/M2_API_MATRIX.md` with documented vs inferred API evidence.
- Add `docs/M2_TESTING.md` with Wave-mode acceptance scenarios.
- Extend static/source-driven validation:
  - `scripts/check_wave_m2.py`
  - `tests/test_wave_m2.py`

## M1 reliability candidate + recovery preflight â€” unreleased, pending gameplay validation

- Preserve recovered baseline files unchanged:
  - `addons/AICadetsTraversal.cl` blob `4c1d23c628d18f98500d2c3f20f5d954c1ea17fd`
  - `addons/AICadetsWatcher.cl` blob `5b3e1720b6e3d66b4fc35d0c9957306b67203b57`
- Add `addons/AICadetsTraversalReliable.cl` with:
  - improved anchor rejection for body clearance / intermediate obstacle / blocked exit
  - bounded recovery states (`RecoverPlan`, `RecoverAttach`, `RecoverBurst`)
  - extended observe window and dangerous-fall recovery trigger
  - explicit result classes: `success`, `recoverable_interruption`, `safe_termination`, `failure`
  - bounded machine-readable controller event telemetry (`[AI Cadets M1R] ...`)
- Add read-only recovery tooling and docs from PR #5:
  - `tools/recovery_preflight.py`
  - `tests/test_recovery_preflight.py`
  - `docs/V4_RECOVERY.md`
- Add `tools/analyze_m1_run.py` and tests to correlate controller event logs with watcher traces.
- Extend docs for A/B gameplay validation matrix, installation, rollback, and evidence classification.

## M1 two-anchor experiment â€” unreleased, awaiting gameplay validation

- Add separate `AICadetsTraversal.cl`; preserve the confirmed v0.1.1 probe byte-for-byte.
- Two sequential left-hook cycles with a velocity-directed second search, finite deadlines, resource/ownership checks, collision abort and explicit cleanup.
- Add per-leg diagnostics, final metrics, conservative duplicate prevention and documented migration limitations.
- Add pinned API-name/arity checks and source-driven mocked control-flow tests to CI; these do not establish in-game compatibility.
- Add [manual acceptance and rollback instructions](M1_TESTING.md).

## v0.1.1 â€” Costume lookup fix (2026-10-29)

- Fix the first in-game report (`AICadetsProbe.addon:57`): replace blank custom costume lookup `(0, "")` with bundled preset `(1, "Levi")`.
- Add a static CI regression assertion against blank character presets.
- Document that the engine wrapper may dereference null after failed costume resolution.
- **Verified in-game (2026-10-29):** one Scout spawned, hook launched and attached, short gas burst, release, displacement 43.68573, gas used 0.4518585. Repeatability and multiplayer untested; movement, gas and hook logic unchanged from v0.1.0.

## v0.1.0 â€” Initial probe

- First experimental add-on that spawns a Scout, finds a surface, launches one ODM hook and logs results.
