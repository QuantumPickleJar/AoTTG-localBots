# AI Cadets — AoTTG2 starter v0.1.1

An experimental, local-first **AoTTG2 Custom Logic add-on** for one AI Scout's first ODM maneuver. This project is independently developed and is not endorsed by the AoTTG2 team.

**Status:** **Milestone M0 single-host ODM maneuver confirmed in game on 2026-10-29** (report: `docs/TEST_REPORT.md`). The Scout spawned, launched and attached a hook, used gas, released, and traveled 43.68573 game units while using 0.4518585 gas units. Multi-client synchronization, repeatability, and realism mode remain **untested**. AoTTG2 uses a Custom Logic dialect (this `.cl` is **not** ordinary C# or a Unity DLL).

## Run the first test

**M1 experiment:** `addons/AICadetsTraversal.cl` adds two consecutive anchors on a separate add-on. It is **awaiting in-game validation**. Follow [the M1 test procedure](docs/M1_TESTING.md) and [design/API notes](docs/M1_DESIGN.md). Enable only one AI Cadets add-on at a time. The instructions below remain the known-good M0 regression test.

1. Download/copy `addons/AICadetsProbe.cl` to `Documents/AoTTG2/Addons/` (create folder if necessary). Do not put this in the `CustomLogic` game-mode directory.
2. Open AoTTG2 and create a **private** game, selecting a quiet map with a nearby wall or substantial tree. Choose the normal game mode as you ordinarily would. The official docs indicate add-ons are configurable in the **General** panel of game creation.
3. Turn on the **AICadetsProbe** add-on. If prompted, leave the defaults. For the initial test, **do not enable realism mode**; that is a separate later acceptance test.
4. Spawn as a **human** on the game host/master client. Stand facing a visible, hookable wall roughly 15–50 in-game units ahead; a line from the Scout toward the wall should not intersect another player or Titan. The Scout will appear to your right.
5. Observe the on-screen chat/console: `Scout spawned` → `Hook launched` → `Hook attached` → `Gas off` → `Probe finished`.
6. Record what happened and any console errors (see `docs/TEST_REPORT.md`). Restart the round to try a new anchor surface.

If the addon fails to compile or spawns but cannot hook, please **do not substitute arbitrary API guesses**. Record the exact line/error and use the official documentation to make a targeted correction. **Fix in v0.1.1:** the first version passed `costume=0, costumeName=""` to `Game.SpawnHumanAt`. Inspection of the publicly available AoTTG2 source fork shows `SpawnAIHumanAt` looks for an **exact named costume preset** and returns `null` if none matches, whereupon the Custom Logic wrapper may throw a `NullReferenceException`. v0.1.1 uses `costume=1, costumeName="Levi"`, a named preset in the fork's `HumanCustom.json`. This costume fix was verified in an in-game test; the source fork may still differ from future live builds. If you customize/remove built-in preset sets or the live build uses different names, try the name of a known existing Costume1 preset; do not use a blank name.

This is a test-only workaround; later we should expose character preset selection as an add-on setting with safe validation, rather than defaulting every AI Scout to Levi.

## Reported bug, fix, and successful test

- v0.1.0 failed at add-on line 57 with `Object reference not set to an instance of an object` in `Game.SpawnHumanAt`.
- Likely root cause: the empty named costume does not resolve; the game attempts to wrap `null`.
- v0.1.1 changes that **one spawn argument pair**; ODM timing and logic are unchanged.
- To retest: replace your existing `Documents/AoTTG2/Addons/AICadetsProbe.cl` with the new one, recreate the game/round, and record the next message or error. No installation of Unity, Harmony, or a separate mod loader was necessary for the successful test.
- Public source used for diagnosis: [InGameManager.SpawnAIHumanAt](https://github.com/douglasfelix076/Aottg2-Unity-Hex/blob/main/Assets/Scripts/GameManagers/InGameManager.cs), [CustomLogicHumanBuiltin constructor](https://github.com/douglasfelix076/Aottg2-Unity-Hex/blob/main/Assets/Scripts/CustomLogic/Builtin/Entities/CustomLogicHumanBuiltin.cs), [preset data](https://github.com/douglasfelix076/Aottg2-Unity-Hex/blob/main/Assets/StreamingAssets/Presets/HumanCustom.json). This fork is not necessarily the live AoTTG2 source; behavior may differ.

## What it does and doesn't do

- Spawns **one** AI human from the master client and labels it `[BOT] Scout 01`.
- After a delay, probes a surface along the host's forward direction, launches its **left** hook, waits for actual hook attachment, applies a brief gas burst, and releases.
- Logs success/failure stages, distance traveled, and gas used.
- Does **not** navigate automatically, acquire Titans, score kills, modify player gas, record player actions, upload data, or integrate with specific mission objectives yet.

## Why an add-on?

Unlike a standalone custom game-mode script (`class Main`), an `addon` can be selected alongside a built-in game mode. We can therefore investigate Waves, Annie, and Colossal gameplay **without intentionally replacing their mission scripts**. Mission participation and victory/failure accounting still require real tests.

## Development environment

VS Code has the community extension [AoTTG 2 Custom Logic](https://marketplace.visualstudio.com/items?itemName=Jagerente.aottg2cl) for Custom Logic syntax, editing, and bundling imports. Each experiment is a self-contained `.cl` add-on with no build-time dependencies. GitHub Actions runs static API/structure checks, M0 hash protection and source-driven mocked control-flow tests; **it cannot validate the AoTTG2 interpreter or hooks in-game**. Local check commands and limitations are in [M1_DESIGN.md](docs/M1_DESIGN.md#automated-checks).

## Source references

- Official Custom Logic: https://github.com/AoTTG-2/CustomLogicDocumentation
- Official add-on guide: https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/custom-logic-tutorial/addons.md
- Official Human API: https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/Entities/Human.md
- Official Game API: https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/Game/Game.md
- Official callback docs: https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/callbacks/main.md
- Official examples: https://github.com/AoTTG-2/AoTTG2-Example-Content/tree/main/Addons

## Roadmap

See `docs/ROADMAP.md`, `docs/DATA_POLICY.md`, and `docs/TEST_REPORT.md`. The project is local-only and does not require rented compute.
