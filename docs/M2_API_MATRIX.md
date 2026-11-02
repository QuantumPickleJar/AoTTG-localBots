# M2 combat and locomotion API evidence matrix

## Sources

- Current CustomLogicDocumentation revision `38796d52a99c2dd76ec08a111395628a9151d07e` (October 31 sync, [integration PR #47](https://github.com/AoTTG-2/CustomLogicDocumentation/pull/47)).
- Historical revision `ded03751aee1b1179141aeb534faa2f1fc266aff` (July 23; the prior M2 API baseline).
- Example content revision `9b1b156cab41261d399028cd1ca5564f70724a4c`

## October 31 AI API audit ([issue #8](https://github.com/QuantumPickleJar/AoTTG-localBots/issues/8))

The docs now put Human AI controls on the shared `Character` base type. The Human type inherits them; their move in the documentation is not evidence that a method disappeared from the installed game.

- `Character.AIEnabled: bool` and `Character.UsePathfinding: bool` are documented as writable. The docs describe automatic behavior and navmesh use, but do not establish current defaults or how either property interacts with this controller. Keep both observational until a one-variable live trial is prepared.
- Native target APIs are documented on `Character`: `GetTarget()`, `SetTarget(target: Object, focusDuration: float = 0)`, `ClearTarget()`, `GetNearestEnemy()`, and `TargetNearestEnemy(focusDuration: float = 0)`, alongside `CurrentTarget`, `DetectRange`, `IsWalking`, and `State`. M2 currently selects Titans with its own policy and retained target identity. Replacing that policy with nearest-native targeting could ignore M2 bans, target priorities, or route checks, so do not substitute it based on documentation alone.
- `Human.Target` remains documented as obsolete; new code should use inherited `GetTarget()` / `SetTarget()`. `Human.Navigation()` is described as one update toward `TargetPosition`, using pathfinding when enabled. It is not a persistent order or an arrival-range check, so it is not a drop-in replacement for M2's owned ground command.
- The inherited movement signatures are `MoveTo(position: Vector3, range: float, ignoreEnemies: bool = False)` and `MoveToTarget(target: Object, range: float, ignoreEnemies: bool = False)`. Existing two-argument calls remain within the documented optional-argument contract. M2 ground pursuit currently uses `MoveTo` with projected ground positions; it does not need `MoveToTarget` for ground pursuit. Keep `ignoreEnemies` at its default in any comparison.
- The inherited signature is `Idle(time: float = -1)`. The new description says it stops native AI movement and targeting; the documented default for Humans is zero seconds. Existing `_cadet.Idle()` calls remain valid calls, but their effect on the installed native target and the timing of an immediately issued `MoveTo` still need observation. M2's selected Titan is separately tracked by its controller; do not assume the native target is unchanged or cleared in the installed runtime.
- `State` and `Grounded` are listed on `Character` and inherited by Human. They were relocated in the docs, not removed from the API.

The existing source checker already resolves Human members through `Object`, `Character`, and `Human`. The contract below should therefore place inherited methods and properties on `Character` and Human-specific calls on `Human`.

### Installed-game boundary and current evidence

The October 31 documentation sync does not identify a game binary change. The installed `Player.log` reports Unity `2023.1.22f1`, but no AoTTG2 product/build identifier was found. It contains repeated “Failed to create agent because it is not close enough to the NavMesh” warnings from native Human and Titan AI controller startup; those warnings are not mapped to the M2 cadet and do not show whether `UsePathfinding` is enabled for it.

The November 2 Watch26–Watch29 records identify the deployed controller tag `M2-locomotion-1-f8combo-1`. Direct and Engine both have observed displacement and some positive target-distance gain. Engine also has near-zero or negative-gain samples; Direct has repeated blocked routes and exhausted recovery. These are separate routes and targets, not a controlled A/B. None of the four logs contains a Hold order or `circling_detected`. These records validate neither the newly documented native target APIs nor changes to `AIEnabled` or `UsePathfinding`.

### Stabilization plan update

Preserve the current Direct and Engine movement paths while first capturing the installed values of `AIEnabled`, `UsePathfinding`, `IsWalking`, `State`, `CurrentTarget`/`GetTarget()`, and `DetectRange`, correlated with M2's selected Titan ID and the existing movement observations. Treat this as diagnostics, not as proof of pathfinding or target ownership. Any later flag or native-target behavior change must isolate one variable in a fresh `M2-L0` run, keep the F8/hold path intact, and compare physical displacement, target gain, blocked-route recovery, and cancellation. Prepare its Validation Card and apply the repository gameplay harness before making that runtime change.

## Documented and directly used

### Mission and roster observation

- [Game.Titans](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Game/Game.md) (list of titans)
- [Game.Humans](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Game/Game.md)
- [Game.PlayerHumans](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Game/Game.md)
- [Game.IsEnding](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Game/Game.md)

### Titan targeting geometry

- [Titan.NapePosition](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Titan.md)
- [Titan.IsCrawler](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Titan.md)
- [Character.ViewID](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Character.md)

### Human combat and locomotion control

- [Human.Attack(attackOn: bool)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Human.md)
- [Human.AimAt(position: Vector3)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Human.md)
- [Human.LaunchHookLeft(aimPoint: Vector3)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Human.md)
- [Human.ReleaseHookLeft()](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Human.md)
- [Human.ReleaseHookRight()](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Human.md)
- [Human.UseGas(useGas: bool)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Human.md)
- [Human.Jump()](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Human.md)
- [Character.Idle(time: float = -1), inherited by Human](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Character.md)

### Geometry and kinematics

- [Physics.LineCast(start, end, collideWith)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Game/Physics.md)
- [Character.Position/Velocity/Forward/Right](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Character.md)
- [Vector3.Distance / Dot / Normalize](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Collections/Vector3.md)

### Combat and mission callbacks

- [OnCharacterDamaged(victim, killer, killerName, damage)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/callbacks/main.md)
- [OnCharacterDie(victim, killer, killerName)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/callbacks/main.md)

## Supported by inspected implementation/examples

- Titan kill accounting is observable with callback events and titan list counts, as shown in:
  - [Titan ExplodeLogic.txt](https://github.com/AoTTG-2/AoTTG2-Example-Content/blob/9b1b156cab41261d399028cd1ca5564f70724a4c/Modes/Titan%20ExplodeLogic.txt)
  - [ExplosiveTitans.cl](https://github.com/AoTTG-2/AoTTG2-Example-Content/blob/9b1b156cab41261d399028cd1ca5564f70724a4c/Addons/ExplosiveTitans.cl)
- Wave-mode style status labels in examples are based on current titan/human counts rather than hidden mission hooks.

## Inferred and requiring gameplay validation

- Reliability of `killer` attribution to an AI cadet during normal blade nape strikes in Wave mode.
- Exact mapping between `OnCharacterDamaged` events and successful nape strike outcomes for AI cadets.
- Whether all mission kill counters credit AI cadet attacks identically across game modes/maps.
- Multi-cadet reservation race conditions in private multiplayer.

## Not used / intentionally avoided in M2 addon

- Directly setting titan or character health for simulated kills.
- Refill APIs ([Human.Refill](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Human.md), `RefillImmediate`) for combat sustain.
- Position/velocity writes as movement shortcuts.
- Built-in mission script replacement.

## Current blocker status

No hard API blocker found for: target acquisition, approach attempts, attack issuing, damage/death observation, and basic mission-state observation.
Remaining blockers are validation blockers (gameplay confirmation), not interface absence.

## M2 resupply and navigation (experimental)

- Official [Character.MoveTo(position, range, ignoreEnemies = false)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Character.md), inherited by Human, moves toward a point. Navigation still needs live testing for City obstacles; our finite detour waypoints are not a general navmesh solver.
- Official [Map.FindMapObjectsByComponent](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Game/Map.md) can return custom map objects carrying a `SupplyStation` component. No evidence yet that built-in City scene stations are included in this collection.
- Official [SupplyStation component example](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/examples/components/supplystation.md) activates gas refill inside its collision region when a human has `AutoRefillGas` enabled. A host-marked station is a navigation hint only; success requires `CurrentGas` to increase via the game's own supply interaction.
- Manual fallback: master host stands at an actual station and presses **MARK supply here** in the M2 command panel. This records only a session-local waypoint, not a verified station entity.
- No direct edits to `CurrentGas`, no `RefillImmediate`, no fabricated supply encounters. If a station is unavailable, the cadet searches on foot with a deadline and eventually safely holds; it does not fake a replenishment.
- Live acceptance still required for `AutoRefillGas` on AI-owned humans, built-in City 1 station discovery, and waypoint/ODM hybrid navigation.


## combat-arc-1 experimental Titan tether

The documented [`Physics.SphereCast(start: Vector3, end: Vector3, radius: float, collideWith: string) -> Object`](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Game/Physics.md) supplies a selected-Titan identity check before a normal hook input. [`Character.State`](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Character.md) and [`Character.CurrentAnimation`](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Entities/Character.md) are separately logged observations. The cast layer, hook collider and orbital physics remain unverified live; hook proximity to the nape does not establish collider identity. See `M2_COMBAT_MANEUVERS.md` for the field checklist and rollback.
