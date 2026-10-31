# M2 Explorer + host orders: City/Waves field test

## Why this exists

The earlier M2 controller required a living Titan within a hard 220-unit selection radius; `target_none reason=no_alive_titan` hid both roster-empty and too-far cases. The predecessor branch `fix/m2-global-target-acquisition` removes that limit and reports `listed/alive/banned/nearest`.

This branch adds an actual **Explore** state as a fallback when no eligible Titan is observable. Rather than remaining in Regroup, the bot cycles between four goal-bearing patrol maneuvers, attempts real M1-style two-hook ODM segments, and falls back to the documented `Human.Move(direction)` while grounded if usable anchors are repeatedly unavailable. Maneuvers are delegated to a small `ChooseExploreHeading` policy function with a numbered pattern; new named skills may replace this without changing mission/combat control. There is no teleport, velocity write, supply refill, or mission-script modification.

During autonomous **Engage** mode (the default), Explore periodically rescans all alive Titans and transitions to target approach upon detection. A manual **Explore** order means *scout/patrol only* until the host issues **Engage**. This avoids accidentally attacking a Titan when the host has specifically ordered reconnaissance. **Hold** turns off ODM/attack inputs and idles the cadet; previously acquired momentum still obeys physics.

## Optional command panel

`addons/AICadetsCommandPanel.cl` uses documented UI `GetRootVisualElement`, `VisualElement`, `Label`, and `Button(text, clickEvent)`. It is host-only, separately selectable, and never issues movement calls.

Choose a recipient using one of the buttons **All cadets**, **M2 Cadet 1**, **M2 Cadet 2**, **M2 Cadet 3**, **M2 Cadet 4**. Then press **ENGAGE Titans**, **EXPLORE map**, **HOLD position**, or **RESUPPLY now**. The panel also has **MARK supply here** to register the living host's current world position as a candidate supply station for the current lobby. The marker is **not proof** that a native supply collider exists there.

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

## Supply search, routing and verified refill (new)

- **Low gas threshold:** The cadet automatically diverts into `SeekSupply` at or below `ResupplyTriggerGas=38`; manual **RESUPPLY now** issues the same request, scoped to All or one M2 instance. Emergency `MinGasReserve` now prevents gas-intensive ODM while the cadet uses grounded supply routing; it no longer immediately deletes the AI's ability to return to a station.
- **Discovery:** Call documented `Map.FindMapObjectsByComponent("SupplyStation")` to select the nearest accessible custom-map station. This API may **not** include built-in City 1 scene supply stations. When the list is empty, stand **at a real station** with your own host character and click **MARK supply here**. This transmits a session-only world-position hint via PersistentData; the controller can route toward it. Only the most recently marked host station is retained in this initial slice.
- **Navigation:** While grounded, use `Human.MoveTo(waypoint, stoppingRange)` toward the station, with bounded progress monitoring and alternating left/right detours if stationary for 8 seconds. When airborne with sufficient remaining gas, use normal physical ODM with the `supply` traverse mode. This is a hybrid waypoint router, **not** a complete map-wide navmesh implementation. It can still fail in awkward geometry.
- **Resupplying:** Temporarily enable the documented `Human.AutoRefillGas` flag while seeking supply; the `SupplyStation` component determines if and when a refill really happens inside its collision region. Never write `CurrentGas`, invoke `RefillImmediate`, spawn resources, or grant gas based on coordinates alone. A successful `resupply_verified` event requires actual `CurrentGas` increase. Restore the previous `AutoRefillGas` setting after supply completion, cancellation, or controlled termination.
- **Failure handling:** If the marked station is false/inactive, emit `supply_not_refilling` and continue bounded foot exploration; if search exceeds 100 seconds, stop safely with a reason. If no candidate station exists, `ExploreSupply` tries to discover one every six seconds and uses physical ground travel. Do not loop indefinitely.
- **Resume:** Successful resupply returns to `AcquireTarget` for Engage orders or `Explore` for explicit patrol orders. The cadet doesn't claim combat success just because it refilled.
- **UI scope:** Use **All cadets** or choose **M2 Cadet 1–4** before Resupply. This initial M2 addon spawns one cadet; additional instances must be separately validated before team-control acceptance.

### City 1 resupply lobby trial

1. In a new private Training / City 1 / Waves lobby, enable **AICadetsWaveCadet** and (only after M2-alone works) **AICadetsCommandPanel**, both from this same branch. Disable the M1 demo bots and old M1 watcher.
2. Locate a working supply station with your own character; stand within its refill area. Press **MARK supply here**.
3. Select **M2 Cadet 1** (or **All**) and press **RESUPPLY now**. If the bot already has full gas, you can still observe routing, but do not expect a positive gas increase until resources are actually consumed.
4. Expect `resupply_requested`, `supply_selected source=host_marked_unverified`, repeated `supply_ground_route` or physical `traverse_start mode=supply`, `supply_arrived`, then `resupply_verified` only on observed increase.
5. If it reports `supply_not_refilling`, confirm the marked position really overlaps a functional station trigger; do not silently increase resources. If `supply_not_visible`, station discovery was empty: the host marker may not have been sent or is not present in this game session.
6. Finally, test **Hold** while returning to station, then **Engage** to resume. Retest after lobby recreation. Film the M2 cadet, show the exact M2 chat events, and note whether built-in stations appear in the component enumeration.

**Status:** Static/mocked checks only; M2 UI, native supply triggers, and City routing need gameplay validation before merging.


## Field-test correction

Explore movement has been reported in-game; the successful movement mechanism is not yet isolated. Search & Destroy shares the existing Explore maneuvers, while explicit Explore remains noncombat and Hold cancels inputs. The source-level 68-unit fallback cancellation has been corrected; target stalls cause a temporary ban and a physical patrol attempt. These are source and mock-validated changes awaiting a live M2 replay. The supply stopping radius is now 2 units to try to reach the marked location more closely; proximity still does not prove a trigger overlap. Failed or unavailable supply still times out safely and restores the previous auto-refill setting. See `M2_MOVEMENT_DIAGNOSTICS.md` for the field procedure and limits.
