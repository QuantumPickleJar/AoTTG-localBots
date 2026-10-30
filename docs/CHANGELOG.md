# Changelog

## M2 Wave-mode combat prototype — unreleased, pending gameplay validation

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

## M1 reliability candidate + recovery preflight — unreleased, pending gameplay validation

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

## M1 two-anchor experiment — unreleased, awaiting gameplay validation

- Add separate `AICadetsTraversal.cl`; preserve the confirmed v0.1.1 probe byte-for-byte.
- Two sequential left-hook cycles with a velocity-directed second search, finite deadlines, resource/ownership checks, collision abort and explicit cleanup.
- Add per-leg diagnostics, final metrics, conservative duplicate prevention and documented migration limitations.
- Add pinned API-name/arity checks and source-driven mocked control-flow tests to CI; these do not establish in-game compatibility.
- Add [manual acceptance and rollback instructions](M1_TESTING.md).

## v0.1.1 — Costume lookup fix (2026-10-29)

- Fix the first in-game report (`AICadetsProbe.addon:57`): replace blank custom costume lookup `(0, "")` with bundled preset `(1, "Levi")`.
- Add a static CI regression assertion against blank character presets.
- Document that the engine wrapper may dereference null after failed costume resolution.
- **Verified in-game (2026-10-29):** one Scout spawned, hook launched and attached, short gas burst, release, displacement 43.68573, gas used 0.4518585. Repeatability and multiplayer untested; movement, gas and hook logic unchanged from v0.1.0.

## v0.1.0 — Initial probe

- First experimental add-on that spawns a Scout, finds a surface, launches one ODM hook and logs results.
