# M2 movement dispatch verification: City 1 / Training / Waves

## Present verified status

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

1. Private host, City 1 / Training / Waves; record 30–60 seconds of video including the bot and chat.
2. After M2-1 appears, press F8, select M2-1, press **EXPLORE**, close F8 with F8 or F9 if necessary.
3. Expect `order_applied ... mode=Explore`, then `explore_step`. A successful hook search yields `hook_launch`. Three consecutive empty/collision-halted hook attempts should lead to `motion_command kind=ground_explore ... ai_state=MoveTo`.
4. After five seconds of `ExploreGround`, look for `motion_observed kind=ground_explore moved=...`. It is **movement proof only if moved is significantly above zero**, not when the FSM changes state.
5. Choose ENGAGE for faraway Titans. The bot should enter `ApproachGround` with `motion_command kind=ground_target ... ai_state=MoveTo`; once close, start real ODM. Record `motion_observed` and actual position delta.
6. If the AI state says `MoveTo` but observed distance stays below 1 unit during five seconds, inspect installed game logic, AI navmesh/floor level, collider obstruction, character animation state, authority, and whether the AI component has finished initializing. This is **not** a target-selection or command-routing problem.
7. If logs show `ai_state=Idle` after a `motion_command`, inspect subsequent `Human.Idle()` call sites. Distinguish action canceled by script from engine rejecting AI movement.
8. If no `motion_command` appears, investigate `ExploreStep` and `BeginTraverseLeg` transitions, `LeftHookReady`, `anchor_search_failed`, and the configured number of no-anchor failures.

## Work mode / local VS Code instructions

The next phase requires comparing runtime **positions over time**, not just status messages. In Work mode with an authorized local repository/game-files connection, read `AGENTS.md`, the current PR #6 and this file, then inspect locally available AoTTG2 log/video output. The ChatGPT VS Code extension does not automatically make the user's entire disk accessible from an unrelated chat; verify the actual workspace permissions.

If the repository can be tested against the live game, prioritize one owned human NPC, no Titans, with a **simple physically controlled straight-line MoveTo trial** (5–10 seconds), and a separate verified wall-hook trial. Correlate events by bot name, host, run ID, tick and game-time; measure position, velocity, ownership and AI state. Never bypass engine AI physics with direct position writes.

Keep changes under the **single existing M2 branch** `feat/m2-exploration-and-orders` and its draft PR #6. Do not merge until live movement is demonstrated. Original M1 scripts remain untouched.
