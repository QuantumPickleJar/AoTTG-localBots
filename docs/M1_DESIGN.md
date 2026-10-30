# M1 implementation and validation boundary

## Plan and controller

1. Preserve M0 and implement a separate selectable add-on.
2. Reuse the working named Levi spawn and left-hook/gas commands.
3. Use a bounded deterministic state machine and five candidates per search.
4. Add source-driven mocked control-flow tests, pinned API checks, and gameplay instructions.

`WaitHost → Settle → Attach → Burst → Coast → Attach → Burst → Observe → Done`.
Every failure ends in `Done`; no retry or automatic respawn. Helpers separate selection (`ConsiderAnchor`, `MapHit`), execution (`BeginLeg`, `StopODM`), and diagnostics (`LogSnapshot`, `Finish`) without a new framework.

| Stage | Bound / behavior |
| --- | --- |
| WaitHost | 30 seconds; initial master only; one spawn attempt latched before the API call |
| Settle | 1 second; resources/ownership/alive checks |
| Attach | At most 3 seconds; gas starts only after `IsHookedLeft` |
| Burst | Default 0.6 seconds, validated maximum 0.8; release within 10 units of anchor |
| Coast | At least 0.12 seconds; hook must be ready and detached; abort by 1 second |
| Observe | Inputs already off; sample for 1 second, then finish |
| Entire spawned sequence | 12-second watchdog; checked every tick |
| Done | No tick-driven commands or reinitialization |

The second search uses measured horizontal velocity above speed 2; below that it retains the previous heading. Five rays cover straight, ±0.45 lateral, higher straight, and +0.8 lateral directions (fixed deterministic right bias). Selection favors forward alignment and distance. Reject hits below four units above the character, closer than 15 units, outside configured reach, less than 12 units from the previous anchor, or with horizontal alignment below 0.35. The default 70-unit reach is inherited as an experimental cap, **not a documented universal hook range**. Attachment remains the actual reach/hookability check.

Each ray checks both MapObjects and MapEditor and chooses the nearest hit. The short collision guard checks actual velocity at 10 Hz (0.2 seconds of travel plus two units), using a line one unit above the character. Selection performs ten linecasts per leg; the guard uses two per check. There is no all-map scan or path planner. The one startup AI list scan avoids spawning over an existing tagged M1 Scout.

## Limitations to measure in game

- A linecast surface is not necessarily hookable. There is no invented hookability API; attachment has a deadline.
- The collision guard is a single line, not a body-volume sweep or full ballistic/rope trajectory. It can miss edges, initial overlaps, moving characters, or future curved motion. Spawn checking only covers a short offset line, not ground support or a capsule overlap.
- Releasing controls cannot brake momentum or guarantee a landing. This iteration has abort/release recovery, not a fall-rescue maneuver. No realism setting is overridden or assumed safe.
- Mutations require both master authority and `IsMine`. No takeover occurs on promotion. After authority loss, cleanup may be impossible under documented rules; the log explicitly says so. Migration, disconnects and mission accounting remain unvalidated.
- Lifecycle behavior is deliberately conservative: repeated start on an existing instance stops; a new instance refuses an existing live `AICadetsM1`. A lobby recreation is the fallback. The game must still be tested for instance/character reset order.
- Engine exceptions (including missing Levi preset) cannot be handled with an undocumented try/catch API. The spawn latch prevents repeated attempts, but an exception inside a movement/cleanup API can interrupt the script. Capture the error and end the test lobby if this happens.

## API evidence

Reviewed official docs at commit `ded03751aee1b1179141aeb534faa2f1fc266aff`; exact selected declarations and source URLs live in `tests/api_contract.json`. These references establish the interface, not compatibility with every installed game build.

- [Game](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Game/Game.md): `function SpawnHumanAt(costume: int, costumeName: string, loadout: string, position: Vector3, rotationY: float = 0) -> Human`; `function Print(message: Object)`; `AIHumans`.
- [Human](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md): `function AimAt(position: Vector3)`, `function Jump()`, `function Idle()`, `function LaunchHookLeft(aimPoint: Vector3)`, `function UseGas(useGas: bool)`, `function ReleaseHookLeft()`, `function ReleaseHookRight()`; `CurrentGas`, `LeftHookEnabled`, `LeftHookReady`, `IsHookedLeft`.
- [Character](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Character.md): `function SetDisplayName(name: string, showTag: bool = True)`; `Name`, `IsMine`, `IsAlive`, `Position`, `Velocity`, `Forward`, `Right`. Only the owner may modify fields or call functions.
- [Physics](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Game/Physics.md): `function LineCast(start: Vector3, end: Vector3, collideWith: string) -> LineCastHitResult`.
- [Vector3](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Collections/Vector3.md): `function Normalize(value: Vector3) -> Vector3`, `function Dot(a: Vector3, b: Vector3) -> float`, `function Distance(a: Vector3, b: Vector3) -> float`; vector component, magnitude and normalization properties.
- [Callbacks](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/callbacks/main.md): `OnTick()` runs at fixed updates (documented 0.02 seconds); deadlines use `Time.GameTime`.
- [Add-on guide](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/custom-logic-tutorial/addons.md) and [official InfiniteSupply example](https://github.com/AoTTG-2/AoTTG2-Example-Content/blob/9b1b156cab41261d399028cd1ca5564f70724a4c/Addons/InfiniteSupply.cl): add-on callbacks/settings and human access conventions. Supply changes from the example are intentionally not used.

## Automated checks

Run from the repository root (Python standard library only):

```sh
python scripts/check_probe.py
python scripts/check_traversal.py
python -m unittest discover -s tests -v
git diff --check
```

`check_traversal.py` protects M0's exact SHA-256, validates selected API member names and positional arity against a reviewed, offline contract, rejects unknown receivers, checks source structure/whitespace, and limits loop/candidate/spawn counts. It does not type-check arbitrary expressions or automatically detect future upstream API changes. Update the contract only after reviewing official docs.

`cl_harness.py` translates only the small statement subset used here into Python so tests exercise the **actual source branches**, with synthetic clock, character and linecast observations. Tests cover two successful cycles, metrics, timeouts, lost hooks, missing anchors, death/despawn, low gas, collision abort, nearest-layer selection, anchor rejection, duplicate prevention, authority loss, and no commands after termination. Validator mutation tests reject example typos and bad argument counts. This is not an AoTTG2 interpreter; Python semantics, mocks and manually supplied observations cannot certify CL parsing, live API behavior, physics, network synchronization, or realism safety. See [M1_TESTING.md](M1_TESTING.md) for the acceptance gate.
