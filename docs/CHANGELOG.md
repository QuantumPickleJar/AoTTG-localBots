# Changelog

## v0.1.1 — Costume lookup fix (2026-10-29)

- Fix the first in-game report (`AICadetsProbe.addon:57`): replace blank custom costume lookup `(0, "")` with bundled preset `(1, "Levi")`.
- Add a static CI regression assertion against blank character presets.
- Document that the engine wrapper may dereference null after failed costume resolution.
- Not yet verified in-game; movement, gas and hook logic unchanged.

## v0.1.0 — Initial probe

- First experimental add-on that spawns a Scout, finds a surface, launches one ODM hook and logs results.
