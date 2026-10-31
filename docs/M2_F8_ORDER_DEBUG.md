# M2 F8 command menu, real acknowledgement and lobby isolation

## Evidence from the reported failure

In the supplied `AICadetsM1Watch3(1).txt`, the independent v3 **M1** watcher observes an `AICadetsM1` two-hook flight, grounded and stationary at approximately game time 7.88, then idle through `watch_timeout` at 27.26. Its PersistentData JSON includes:

- `AICadetsCmdScope = all`
- `AICadetsCmdMode = Engage`
- `AICadetsCmdSequence = 1`

This proves the command panel placed an order in the shared property store. It **does not** prove that any M2 cadet was present or applied the order: the M1 demo's autonomous one-shot traversal neither listens to M2 orders nor continues after its two hooks. Never infer M2 movement from an M1 watcher.

## What changed

- **F8 tactical menu:** panel hidden on startup, opened/closed with `Input.GetKeyDown("CustomKey/F8")` in `OnFrame`. The menu is anchored left instead of under the upper-right minimap and uses a scrollable 340-pixel command list.
- **Interact during gameplay (safety revision):** Opening F8 **only** shows the menu and calls `Camera.SetCursorVisible(true)`. It no longer calls `Input.SetHumanKeysEnabled(false)` or `Camera.SetCameraLocked(true)` because that combination can seize controls, and losing the toggle key can prevent restoration. Closing F8 unconditionally calls `Input.SetHumanKeysEnabled(true)`, `Camera.SetCameraLocked(false)`, and `Camera.SetCursorVisible(false)` to repair even a desynchronized panel state. Movement remains active while the menu is open; use caution when clicking.
- **Real acknowledgements:** the panel logs `submitted`, not success. After an owned `AICadetsM2-N` controller accepts a matching order and enters a new state, **that controller** writes `AICadetsM2AckSeq-AICadetsM2-N`, `AICadetsM2AckMode-AICadetsM2-N`, and `AICadetsM2AckState-AICadetsM2-N`. A periodic `AICadetsM2Heartbeat-AICadetsM2-N` and `AICadetsM2State-AICadetsM2-N` expose whether the controller is running. The panel shows PENDING until the matching controller acknowledges the exact sequence.
- **M1 warning:** the menu lists the number of visible M1 demos but warns they are not M2-orderable. For this test, disable M1 traversal add-ons.
- **No changes to M0 or M1 gameplay scripts, Titan mission rules, or resource refill behavior.** Existing M2 exploration and supply code is preserved.

## Installation

Back up existing files. Download **both updated** `.cl` scripts from `fix/m2-keymenu-order-ack`:

- `addons/AICadetsWaveCadet.cl`
- `addons/AICadetsCommandPanel.cl`

Put both in `Documents/AoTTG2/Addons`, replacing the earlier versions. In a **fresh private host** Training / City 1 / Waves lobby, enable only these two add-ons for the initial test. Disable `AICadetsTraversal`, `AICadetsTraversalReliable`, `AICadetsProbe`, and both old M1 watchers. Make sure the host spawns and observe the `[AI Cadets M2] cadet_spawned name=AICadetsM2-1` message before issuing orders.

1. Press **F8** (not Pause). Confirm the menu appears on the left, minimap stays visible, and the mouse cursor is usable. The player should never lose keyboard movement or ODM due to the panel; Human keys and camera lock are not changed on open.
2. Inspect the M2 status area. It should show `AICadetsM2-1 [Regroup/AcquireTarget/...]` with a recently updating state. If it says **No owned M2 cadets**, no controllable M2 is present. If the game shows `AICadetsM1` only, that's the old one-shot demonstration; turn it off and enable WaveCadet.
3. Choose **ALL M2 cadets -> HOLD position**. The panel should first display `PENDING #N`, then `APPLIED #N Hold by 1 M2 cadet(s)`. M2 chat must contain **`event=order_received seq=N` and `event=order_applied seq=N ... state=Hold`**. Hold disables new gas, hooks, attack and AI drive; physics momentum is not deleted.
4. Choose **M2 cadet 1 -> EXPLORE map**. Expect `APPLIED #N Explore`, `Explore` state, `explore_step`, then physical movement (ODM if an anchor is available; ground fallback otherwise).
5. Choose **M2 cadet 1 -> ENGAGE Titans**. Expect acknowledgement and `AcquireTarget`. If target acquisition fails, the status should continue into `Explore` during autonomous search, not frozen Hold.
6. With the host at a legitimate station, mark supply and issue **RESUPPLY**. Acknowledgement confirms the command was received, not that gas was replenished; look for `resupply_verified` and measured gas increase before claiming success.
7. Press **F8** again and verify the cursor disappears, camera control and ODM input remain functional. If F8 is not received, use **F9** to force-close and restore controls; the panel also auto-closes after **45 seconds** of game time. Reopen to check the menu remains functional.

## Interpret failures

- **Panel logs submitted but no M2 entity:** selection/install problem, not a failed movement response. Disable M1 demo; look for M2 `cadet_spawned` in chat.
- **M2 entity but NO CONTROLLER HEARTBEAT:** a stale/preexisting bot or disabled/dead add-on, or the controller's `OnTick` stopped. Capture the first runtime/parser error, not just the last chat line.
- **Heartbeat healthy, PENDING no ack:** check exact selected `AICadetsM2-1..4` name, whether the host owns it and `AICadetsCmdSequence` changed; capture M2 `order_ignored` / `order_rejected`.
- **APPLIED but physically stationary:** control-plane solved; diagnose `explore_step`, `traverse_start`, `anchor_search_failed`, `explore_ground` and gas. Use a **M2-specific** watcher or matching video to investigate M2 motion, not an M1 watcher.
- **UI doesn't toggle or cursor still locked:** hit **F9** to force-close; if key events are lost, let the 45-second game-time watchdog close the panel. A game restart with the old command-panel addon disabled is a safe recovery. F8/F9 use `CustomKey` codes, not new built-in rebind entries. Capture the first CL runtime error and check other cursor-controlling addons.

## Acceptance and rollback

- F8 opens/closes an unclipped left-side scroll menu without disabling Human keys or locking the camera; F9 and 45-second watchdog recover a stuck menu; cursor restored on exit.
- Orders change the chosen *owned M2* controller's state and generate per-bot acknowledgements; no confirmation merely from pressing a button.
- Nonmatching M2 bots do not acknowledge a targeted order.
- No new human tracking, no remote upload, no M1 script changes.
- Keep PR draft until validated **in-game**; mocked Python tests check state wiring but cannot prove Unity input focus or controller physics.

Rollback: exit the lobby, restore both backed-up `.cl` files and restart with the previously verified M2-only combination. No game files or binary mods are changed.

## 2026-10-30 input seizure regression and corrective patch

The first F8 implementation called `Input.SetHumanKeysEnabled(false)` and `Camera.SetCameraLocked(true)` when opening the UI. Those global settings can leave the player unable to control their human if input events stop reaching F8 or if another UI intercepts the key. The user observed controls remain seized even after attempting to close the menu.

This revision removes **both global disable/lock calls from OpenMenu**. On starting a fresh host session, `RestoreHumanControls()` also clears any state left by the older panel. On closing the menu or ending the game, the same repair runs regardless of the current `_open` flag.

Emergency recovery methods, in order:
1. **F8** normally closes the panel.
2. **F9** explicitly restores controls and closes the panel (even when internal menu state was desynchronized).
3. **45-second game-time watchdog** closes and restores it from `OnTick` without a click or key event.
4. If the Custom Logic addon itself stopped ticking, exit the lobby, disable the offending `AICadetsCommandPanel.cl` and recreate the lobby. Script-level watchdogs cannot recover an addon that is no longer executing.

**Tradeoff:** while F8 is open, ordinary player controls stay enabled, so mouse clicks may activate player abilities in some configurations. This is safer than globally disabling movement and leaving the user trapped. Avoid testing around combat during panel-interaction verification. Do not revert to global Human input disabling without a proven, independent restoration mechanism.
