# M1 reliability design (v4.1 recovery baseline + reliability candidate)

## Scope and baseline protection

- `addons/AICadetsTraversal.cl` (blob `4c1d23c628d18f98500d2c3f20f5d954c1ea17fd`) remains the recovered, known-good traversal baseline.
- `addons/AICadetsWatcher.cl` (blob `5b3e1720b6e3d66b4fc35d0c9957306b67203b57`) remains the recovered, known-good independent watcher baseline.
- `addons/AICadetsProbe.cl` remains unchanged M0.
- Reliability work is isolated in `addons/AICadetsTraversalReliable.cl` for A/B gameplay validation without replacing the recovery baseline.

## Controller state machine (reliability candidate)

`WaitHost → Settle → Attach → Burst → Coast → Attach → Burst → Observe → Done`

plus bounded recovery substates:

`RecoverPlan → RecoverAttach → RecoverBurst` (max configured retries; default 1).

Outcome classes are explicit:

- `success` (`completed`, `completed_with_recovery`)
- `recoverable_interruption` (interruption before bounded recovery decision)
- `safe_termination` (cleanup-first stop where rescue is unavailable/unsafe)
- `failure` (invalid settings, host timeout, or hard sequence timeout)

## Reliability changes in `AICadetsTraversalReliable.cl`

1. **Second-anchor reliability**
   - Keeps the five deterministic primary candidates.
   - Adds candidate rejection for:
     - too near/far, too low/high, poor alignment, too close to previous anchor
     - immediate body-clearance obstruction
     - intermediate obstacle on the path
     - blocked short exit path near the anchor
   - Uses actual horizontal velocity for leg-2 heading when speed is meaningful.

2. **Bounded recovery**
   - Recovery triggers from:
     - missing leg-2 anchor
     - attach timeout/hook loss
     - coast deadline or prolonged low momentum
     - dangerous fall detected during Observe (`velocity.Y <= -28`, speed >= 30) with resources available
   - Recovery uses a separate bounded candidate set and deadlines.
   - If recovery cannot be attempted safely (no gas/hook/budget/anchor), controller terminates safely with a specific reason.

3. **Post-release safety window**
   - Observe window is configurable (`ObserveSeconds`, default 2.0), addressing the prior risk that 1 second can miss post-release danger.

4. **No physics cheats**
   - No teleportation, position writes, velocity writes, gas refill, or undocumented force APIs.
   - Cleanup is still `UseGas(false)`, `ReleaseHookLeft()`, `ReleaseHookRight()`, with explicit note that this cannot instantly cancel momentum.

## Decision telemetry (controller-side, bounded)

`AICadetsTraversalReliable.cl` emits machine-readable lines:

`[AI Cadets M1R] t=<gameTime> state=<state> leg=<n> event=<event> ...`

Bounded by:

- `Diagnostics` toggle (default true)
- hard cap of 160 controller log events
- per-leg cap of 8 anchor rejection logs

Events include:

- state transitions
- anchor selection and rejection reasons
- hook launch/attach/release
- termination class and reason

Independent watcher telemetry remains separate and unchanged.

## API evidence and signatures

Reviewed against official docs revision `ded03751aee1b1179141aeb534faa2f1fc266aff` in `tests/api_contract.json`:

- [Game](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Game/Game.md):
  - `function SpawnHumanAt(costume: int, costumeName: string, loadout: string, position: Vector3, rotationY: float = 0) -> Human`
  - `function Print(message: Object)`
- [Human](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md):
  - `function AimAt(position: Vector3)`
  - `function Jump()`
  - `function Idle()`
  - `function LaunchHookLeft(aimPoint: Vector3)`
  - `function UseGas(useGas: bool)`
  - `function ReleaseHookLeft()`
  - `function ReleaseHookRight()`
- [Character](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Character.md):
  - `function SetDisplayName(name: string, showTag: bool = True)`
- [Physics](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Game/Physics.md):
  - `function LineCast(start: Vector3, end: Vector3, collideWith: string) -> LineCastHitResult`
- [Vector3](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Collections/Vector3.md):
  - `function Normalize(value: Vector3) -> Vector3`
  - `function Dot(a: Vector3, b: Vector3) -> float`
  - `function Distance(a: Vector3, b: Vector3) -> float`

## Automated checks

Run from repo root:

```sh
python scripts/check_probe.py
python scripts/check_traversal.py
python scripts/check_traversal_reliable.py
python tools/recovery_preflight.py
python -m unittest discover -s tests -v
git diff --check
```

Notes:

- Static scripts validate API-name/arity usage and source invariants.
- `check_traversal_reliable.py` additionally verifies baseline blob hashes for `AICadetsTraversal.cl` and `AICadetsWatcher.cl`.
- Tests are source-driven mocks, not AoTTG2 runtime certification.

## Known limits requiring gameplay verification

- `Physics.LineCast` indicates query hits, not collision callbacks or guaranteed hookability.
- Recovery still cannot guarantee rescue once momentum is committed.
- Ownership/master changes still stop safely; no migration takeover is implemented.
- Reliability candidate and baseline must be validated through the M1 gameplay matrix before replacing baseline usage.
