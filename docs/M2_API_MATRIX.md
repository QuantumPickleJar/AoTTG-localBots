# M2 combat API evidence matrix

## Sources

- CustomLogicDocumentation revision `ded03751aee1b1179141aeb534faa2f1fc266aff`
- Example content revision `9b1b156cab41261d399028cd1ca5564f70724a4c`

## Documented and directly used

### Mission and roster observation

- [Game.Titans](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Game/Game.md) (list of titans)
- [Game.Humans](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Game/Game.md)
- [Game.PlayerHumans](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Game/Game.md)
- [Game.IsEnding](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Game/Game.md)

### Titan targeting geometry

- [Titan.NapePosition](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Titan.md)
- [Titan.IsCrawler](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Titan.md)
- [Character.ViewID](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Character.md)

### Human combat and locomotion control

- [Human.Attack(attackOn: bool)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md)
- [Human.AimAt(position: Vector3)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md)
- [Human.LaunchHookLeft(aimPoint: Vector3)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md)
- [Human.ReleaseHookLeft()](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md)
- [Human.ReleaseHookRight()](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md)
- [Human.UseGas(useGas: bool)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md)
- [Human.Jump()](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md)
- [Human.Idle()](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md)

### Geometry and kinematics

- [Physics.LineCast(start, end, collideWith)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Game/Physics.md)
- [Character.Position/Velocity/Forward/Right](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Character.md)
- [Vector3.Distance / Dot / Normalize](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Collections/Vector3.md)

### Combat and mission callbacks

- [OnCharacterDamaged(victim, killer, killerName, damage)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/callbacks/main.md)
- [OnCharacterDie(victim, killer, killerName)](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/callbacks/main.md)

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
- Refill APIs ([Human.Refill](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md), `RefillImmediate`) for combat sustain.
- Position/velocity writes as movement shortcuts.
- Built-in mission script replacement.

## Current blocker status

No hard API blocker found for: target acquisition, approach attempts, attack issuing, damage/death observation, and basic mission-state observation.  
Remaining blockers are validation blockers (gameplay confirmation), not interface absence.
