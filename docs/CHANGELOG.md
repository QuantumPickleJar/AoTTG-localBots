# Changelog

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
