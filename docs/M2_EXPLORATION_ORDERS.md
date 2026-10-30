# M2 Explorer + host orders: City/Waves field test

## Why this exists

The earlier M2 controller required a living Titan within a hard 220-unit selection radius; `target_none reason=no_alive_titan` hid both roster-empty and too-far cases. The predecessor branch `fix/m2-global-target-acquisition` removes that limit and reports `listed/alive/banned/nearest`.

This branch adds an actual **Explore** state as a fallback when no eligible Titan is observable. Rather than remaining in Regroup, the bot cycles between four goal-bearing patrol maneuvers, attempts real M1-style two-hook ODM segments, and falls back to the documented `Human.Move(direction)` while grounded if usable anchors are repeatedly unavailable. Maneuvers are delegated to a small `ChooseExploreHeading` policy function with a numbered pattern; new named skills may replace this without changing mission/combat control. There is no teleport, velocity write, supply refill, or mission-script modification.

During autonomous **Engage** mode (the default), Explore periodically rescans all alive Titans and transitions to target approach upon detection. A manual **Explore** order means *scout/patrol only* until the host issues **Engage**. This avoids accidentally attacking a Titan when the host has specifically ordered reconnaissance. **Hold** turns off ODM/attack inputs and idles the cadet; previously acquired momentum still obeys physics.

## Optional command panel

`addons/AICadetsCommandPanel.cl` uses documented UI `GetRootVisualElement`, `VisualElement`, `Label`, and `Button(text, clickEvent)`. It is host-only, separately selectable, and never issues movement calls.

Choose a recipient using one of the buttons **All cadets**, **M2 Cadet 1**, **M2 Cadet 2**, **M2 Cadet 3**, **M2 Cadet 4**. Then press **ENGAGE Titans**, **EXPLORE map**, or **HOLD position**.

Buttons publish three local/shared PersistentData properties in order:
- `AICadetsCmdScope` (`all` or the exact name `AICadetsM2-N`)
- `AICadetsCmdMode` (`Engage`, `Explore`, `Hold`)
- `AICadetsCmdSequence` (monotonic commit sequence)

Every owned M2 cadet independently observes the sequence and only responds if the scope matches its own name or `all`. No network or disk export is triggered by the command panel. Do not manually call `PersistentData.Clear()`, as the collection is shared. UI button binding in a Custom Logic *addon* (rather than a Main mode) is not yet confirmed in-game; this is why the command panel is separately enabled after movement validation.

The M2 controller's own chat logs `order_received` and state transitions. The v3 M1 watcher does NOT track M2 cadets.

## Incremental test procedure

### Test A — M2 exploration ONLY (critical)

1. Back up the installed `AICadetsWaveCadet.cl`.
2. Install `addons/AICadetsWaveCadet.cl` **from branch `feat/m2-exploration-and-orders`**, NOT from `main`.
3. Enable only **AICadetsWaveCadet** in a new private City 1 / Training / Waves lobby, master client. Disable M1 Probe, Traversal, Reliable, original Watcher, and the command panel.
4. Verify it spawns once, then watch:
   - If `listed=0 alive=0`, the bot should enter **Explore** and issue `explore_step`; if a hookable wall exists, `traverse_start mode=explore` and `hook_launch`; otherwise bounded failures followed by `explore_ground`.
   - If `alive>0`, expect `target_selected` regardless of distance, `traverse_start mode=approach`, and actual hook attempts.
   - When a Titan spawns during exploration, expect automatic **AcquireTarget → PlanApproach** without restarting the lobby.
5. Do NOT infer successful attack or wave credit merely from hook travel. Compare with HUD and video. Do not test with extra add-ons until this baseline succeeds.

### Test B — Optional host command panel

1. Recreate the lobby with **AICadetsWaveCadet** and **AICadetsCommandPanel**, both from `feat/m2-exploration-and-orders`.
2. Confirm a panel titled `AI Cadets M2 Orders` appears for the master client.
3. Select **All cadets → HOLD position**: expect `order_received mode=Hold`, `Hold`, and no new inputs (existing momentum may remain).
4. Select **M2 Cadet 1 → EXPLORE map**: expect `order_received mode=Explore` and patrol actions, even without a Titan.
5. Select **M2 Cadet 1 → ENGAGE Titans**: expect `AcquireTarget`; either select a Titan or return to automatic exploration while searching.
6. If multiple M2 instances exist in a controlled lobby, select a specific cadet and confirm **other cadets do not change mode**. Do not start extra M1 scripts to create bots for this test.

### Test C — Optional M2 watcher

Separate PR `feat/m2-independent-watcher` adds `AICadetsM2Watcher.cl`, a passive variant of the known-good v3 observer that watches `AICadetsM2-1..4`. Install it only after A and B succeed; it was intentionally kept out of this branch to avoid reintroducing the simultaneous script-change regression. New files are `AICadetsM2WatchN`. Review the saved Shared PersistentData before sharing.

## Report these exact fields

- Git commit or branch / game build / map and game mode.
- Add-ons enabled (A, B or C), who is host, realism setting.
- First `cadet_spawned`, `target_none`, `target_selected`, `explore_step`, `traverse_start`, `hook_launch`, and `order_received` lines.
- Whether the HUD shows live Titans and whether the cadet physically progresses.
- Any line-numbered runtime/parse exception.
- Short matching video and M2-specific trace if available.

## Safeguards and boundaries

The four patrol patterns are an intentionally simple initial maneuver policy, **not** trained exploration or a full path planner. Ground fallback uses `Human.Move` documented game controls but is not yet observed in-game. A lack of forward/lateral hookable surfaces can still block ODM; a nearby obstacle can block grounded running. The panel uses UI methods documented for Custom Logic, but add-on callback binding must be validated live.

This feature is a testable M2 navigation slice, not proof that nape strikes, kill attribution, and wave progression have passed. Keep the prior `main` files for immediate rollback and never merge a PR based solely on mock/static tests.
