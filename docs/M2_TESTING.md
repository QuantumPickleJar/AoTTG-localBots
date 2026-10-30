# M2 Wave-mode manual test matrix

Use `addons/AICadetsWaveCadet.cl` with M1 files preserved as rollback.

## Required run metadata

- AoTTG2 build
- map and game mode
- realism/physics settings
- add-ons enabled
- run ID from `[AI Cadets M2]` logs
- result line and reason

## Scenario matrix

1. Single cadet, one ordinary titan.
2. Single cadet, multiple titans.
3. Moving-target reacquisition.
4. Missed nape attack.
5. Confirmed nape hit (damage callback observed).
6. Confirmed titan death and wave HUD/counter consistency.
7. Unsafe approach triggering recovery/replan.
8. Repeated `collision_risk` without infinite retries.
9. Low gas termination.
10. Hook unavailable termination.
11. Cadet death cleanup.
12. Last titan eliminated and next-wave progression behavior.
13. Host/player death and defeat behavior.
14. Round restart without duplicate cadets.
15. Two-cadet coordination test (consenting private multiplayer) after solo pass.

## Expected M2 telemetry categories

- state transitions
- target selected/lost/banned
- traverse start/end and outcomes
- attack attempt and result classification
- mission snapshots (titan/human counts)
- termination class and reason

## Acceptance notes

- `result_class=safe_termination` may be valid when preserving safety.
- `confirmed_damage=false` after an attack attempt is not a kill.
- A successful movement request does not imply arrival at nape strike geometry.
- Static tests and log parsing do not replace in-game acceptance.
