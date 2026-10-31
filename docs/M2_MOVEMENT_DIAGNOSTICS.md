# M2 movement dispatch verification: City 1 / Training / Waves

## Field-test update and remaining evidence

The user reports that Explore physically moved in-game, and that F8 orders and control restoration work. This is gameplay evidence for Explore, but the available M2 controller trace and matching video were not located, so the specific successful call (ODM versus `MoveTo`) has not been isolated. The installed controller matches the branch baseline. Existing local Watch0â€“7 files identify M1, not M2. Do not treat them as evidence of M2 movement. The current Player log was empty and the previous log contained no M2 events.

A source-level Engage defect is established: inside 68 units, `no_suitable_anchor` started `MoveToTarget`, then `ApproachGroundStep` immediately called `Idle` because the target was already inside 68 units. This can cause rapid planning without physical pursuit. It is a plausible contributor, not a proven diagnosis of the recorded field failure. Ground fallback now uses a separate, bounded segment and stall checks; a stalled target is temporarily banned to allow a ground patrol. Ordinary Explore traversal and `MoveTo` remain in place.

## Earlier investigation (historical)

M2 command-panel `REQUESTED` and controller `order_applied` messages have been observed by the user, but physical movement is **not** observed. A command acknowledgement confirms a change of the Custom Logic controller state, not that the game applied a Human AI movement command.

Static source review of the earlier M2 traversal showed two path issues:

1. `ExploreStep` repeatedly attempted physical ODM even with no anchor. It invoked `StartTraverse` which called `Human.Idle()` and released ground movement.
2. `ExploreGroundMove` issued a short `Human.Move(direction)` command then reset failure count and paused for 2s. The next attempt could cancel the movement. No displacement was measured. Faraway Titans were also pursued by hook-only attempts.

From the documented Human API, `Human.MoveTo(position, range)` and `Human.MoveToTarget(target, range)` start a persistent AI navigation state, while `Human.Idle()` stops it. The public engine implementation of `HumanAIController` at https://github.com/douglasfelix076/Aottg2-Unity-Hex/blob/2bdac14b029a1cc42800f07e3bb2d271c49c0c7e/Assets/Scripts/Controllers/HumanAIController.cs confirms `MoveTo` transitions the AI to an ongoing `MoveTo` state, and `Idle()` clears it. Actual installed game behavior may differ.

## Revision in this branch

`AICadetsWaveCadet.cl` now adds:
- `ApproachGround`: target beyond 68 units starts `MoveToTarget(titan, 24.0)` until near enough for real ODM, or reports stall; nonteleporting, respects AI ownership/host authority.
- `ExploreGround`: when anchor probing repeatedly fails, starts a persistent `MoveTo(waypoint, 4.0)` for a ~9-second bounded segment, without issuing another hook/Idle in the middle.
- `motion_command`, `motion_observed`, `motion_stalled`, and `motion_segment_done` diagnostics with actual position change, velocity magnitude and `GetAIState()`.
- Mocked regressions for target chase, hook transition, and not canceling ongoing ground AI state. These tests do **not** simulate game physics or confirm world displacement.

## First high-signal lobby trial

With only `AICadetsWaveCadet.cl` and `AICadetsCommandPanel.cl` enabled, from `feat/m2-exploration-and-orders`:

1. Private host, City 1 / Training / Waves; record 30Ã¢â‚¬â€œ60 seconds of video including the bot and chat.
2. After M2-1 appears, press F8, select M2-1, press **EXPLORE**, close F8 with F8 or F9 if necessary.
3. Expect `order_applied ... mode=Explore`, then `explore_step`. A successful hook search yields `hook_launch`. Three consecutive empty/collision-halted hook attempts should lead to `motion_command kind=ground_explore ... ai_state=MoveTo`.
4. After five seconds of `ExploreGround`, look for `motion_observed kind=ground_explore moved=...`. It is **movement proof only if moved is significantly above zero**, not when the FSM changes state.
5. Choose ENGAGE for faraway Titans. The bot should enter `ApproachGround` with `motion_command kind=ground_target ... ai_state=MoveTo`; once close, start real ODM. Record `motion_observed` and actual position delta.
6. If the AI state says `MoveTo` but observed distance stays below 1 unit during five seconds, inspect installed game logic, AI navmesh/floor level, collider obstruction, character animation state, authority, and whether the AI component has finished initializing. This is **not** a target-selection or command-routing problem.
7. If logs show `ai_state=Idle` after a `motion_command`, inspect subsequent `Human.Idle()` call sites. Distinguish action canceled by script from engine rejecting AI movement.
8. If no `motion_command` appears, investigate `ExploreStep` and `BeginTraverseLeg` transitions, `LeftHookReady`, `anchor_search_failed`, and the configured number of no-anchor failures.

## Work mode / local VS Code instructions

The next phase requires comparing runtime **positions over time**, not just status messages. In Work mode with an authorized local repository/game-files connection, read `AGENTS.md`, the current PR #6 and this file, then inspect locally available AoTTG2 log/video output. The ChatGPT VS Code extension does not automatically make the user's entire disk accessible from an unrelated chat; verify the actual workspace permissions.

If the repository can be tested against the live game, prioritize one owned human NPC, no Titans, with a **simple physically controlled straight-line MoveTo trial** (5Ã¢â‚¬â€œ10 seconds), and a separate verified wall-hook trial. Correlate events by bot name, host, run ID, tick and game-time; measure position, velocity, ownership and AI state. Never bypass engine AI physics with direct position writes.

Keep changes under the **single existing M2 branch** `feat/m2-exploration-and-orders` and its draft PR #6. Do not merge until live movement is demonstrated. Original M1 scripts remain untouched.


## Next controlled City 1 / Training / Waves test

1. Back up installed addons. Install the branch versions of `AICadetsWaveCadet.cl`, `AICadetsCommandPanel.cl`, and optionally `AICadetsM2Watcher.cl`. Keep `RecordDecisionTrace = true` in the controller for the test. Start a private master-host lobby; disable M1 bots and the M1 watcher. First run without the optional watcher if addon interaction is in doubt.
2. Give EXPLORE with no Titans. Record video and `motion_command`, `motion_observed`, hooks and AI state. Compare timestamps, position and displacement to identify whether walking or ODM produced movement. Then issue HOLD and check movement inputs stop.
3. Give ENGAGE with no Titan, allow patrol, then spawn a Titan. Record acquisition. For a distant target compare initial and later distances and physical positions; test a nearby target with no usable anchor and verify `fallback=True` remains in `ApproachGround` and actual movement occurs. A stationary bot should report a stall, ban and patrol.
4. With a viable anchor, capture launch, attachment, release, approach and `attack_attempt`. Observe HUD and `target_damaged`/`titan_die` callbacks separately. `by_cadet` identifies attribution from the callback; disappearing from the roster alone is not a confirmed kill. Check a surviving or lost target returns to search.
5. Separately consume gas, stand in a functioning station and MARK supply there, then order RESUPPLY. Capture the route, actual overlap and gas before/after. `supply_arrived` is only a distance test, not proof of trigger entry; only `resupply_verified` indicates observed gas increase. Check resumed Explore and Engage separately. A full tank cannot demonstrate refill. Built-in station enumeration and AI refill remain unverified.
6. The optional watcher saves `AICadetsM2WatchN` in `Documents/Aottg2/PersistentData`: one owned M2 cadet, up to 300 seconds or 2000 records, sampled while moving. Correlate run ID, cadet, game time and state with video and controller events. `RecordDecisionTrace` defaults to enabled so the watcher snapshots the bounded controller trace in the shared data. The file may contain unrelated shared properties; inspect it before sharing. It has not been validated in-game. Chat stops after 260 events and trace capture after 3000; event IDs reveal gaps.

Rollback by restoring the backed-up installed addons and disabling the optional watcher. Python tests model controller decisions and do not run game physics or prove attacks, damage, kills, station overlap, or refill.


## Watch1 analysis and extended collection

`AICadetsM2Watch1.txt` captured one owned cadet. From about game time 2.28 to 13.62 it reported Engage / `ApproachGround` / `MoveTo`, with repeated velocity reversals and position changing from roughly (15, 10, -555) to (7, 10, -533). This is physical motion, but the old trace lacks Titan position and controller decisions, so target-directed progress and the reason for the reversals are unknown. An Explore order appears around 13.74; the same cadet then launched, attached and travelled by hooks. Later, around 61.78â€“90.04, it repeatedly remained close to (-282, 10, -370) during Explore and ExploreGround. This establishes an extended local stall in this recording, not its cause. Watch0 and Watch2 also show Engage / MoveTo movement, but have no target geometry.

The controller spawns exactly one cadet. Panel labels for cadets 2â€“4 are future-facing and do not spawn a squad. Multi-cadet cooperation, task allocation, interpreting quick chat, and bot flare use are not implemented. The official `OnChatInput(message: string)` describes local player chat input; it does not establish that radial quick-chat is delivered there or identify a callout position. Official `Game.SpawnProjectileWithOwner(projectileName: string, position: Vector3, rotation: Vector3, velocity: Vector3, gravity: Vector3, liveTime: float, owner: Character, extraParam: Object = null, extraParam2: Object = null)` documents owner-associated flare projectiles and a color argument, but does not establish gameplay flare conventions or an AI human's normal flare action. See https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/callbacks/main.md and https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/Game/Game.md. These interfaces require separate in-game validation before building cooperation around them.

For the next recording, install both updated M2 addons and the command panel, restart the private lobby, and enable the optional watcher. `RecordDecisionTrace` defaults to true: the controller keeps up to 3000 decision events in a per-cadet shared property for the watcher to save. The separate `SaveRunReport` option remains off by default. The watcher captures up to 300 seconds or 2000 records; moving snapshots every 0.5 seconds include last-published target ID, position, nape, distance, navigation goal, order sequence and status timestamp, alongside physical position, velocity, gas and hook state. The controller status is published about once per second, so target coordinates can be stale by that amount; compare the included timestamp. Velocity-change clues are throttled to one per second. The watcher sees the first matching owned M2 cadet, not a squad. Optional tracing writes local shared PersistentData and can affect timing; saved files can include unrelated properties. Inspect before sharing. Disable `RecordDecisionTrace`, `SaveRunReport`, and the watcher to stop this collection.

Run a fresh lobby and let Engage run for at least 2â€“3 minutes without changing modes, including a visible Titan and any stall. Then issue Explore for a separate interval and Hold. Record video with timestamps and keep the resulting `AICadetsM2WatchN` file, which includes the per-cadet controller trace when both are enabled. If logging causes a load or interpreter issue, rerun the original controller without the watcher; report the error. No M2 collector changes here establish real pursuit, attack or cooperation.
