# M2 locomotion stabilization: Pass 1

- Build tag: `M2-locomotion-1`
- Development branch: `feat/m2-exploration-and-orders`
- Scope: M2 ground pursuit and ownership of its movement commands. No personality system or M1 controller was changed.

## Findings from Watch20 and the recording

`AICadetsM2Watch20.txt` identifies the run as `M2-combat-arc-5`, with the owned M2 cadet pursuing Titan 1006 from about 413 units away. ODM traversal made substantial progress. At game time 18.48, after no suitable anchor was found, the controller entered `ApproachGround` and issued one persistent Engine command: `MoveToTarget(titan, 4.0)`. It remained in `MoveTo` while the controller sampled movement; there is no repeated M2 `Idle`/`MoveToTarget` command cycle in this interval.

At 23.48, the trace reports about 60.18 units of forward progress and 56.35 units of target-distance gain. At 28.48, it reports about 59.53 units of path, 6.36 units of displacement, and negative target-distance gain (-2.62), then reports `circling_detected`, bans 1006, and observes before selecting distant 1007 at about 34.50. There is no `attack_attempt` in the recorded decision trace. The clip sampled across its duration shows the cadet ground-bound near city geometry and on-screen M2 state output; it does not show a physical strike. The clip and game-time trace do not provide a frame-accurate shared clock, so visual moments are not assigned exact trace timestamps.

The watcher records 19 abrupt velocity changes without a confirmed map hit in its probes. That makes these changes unexplained by the recorded probes; it does not prove that the game physics reported no contact anywhere. The trace also places the cadet near ground height while the Titan nape is more than 12 units above it.

### Confirmed defects and conditional causes

- **Confirmed in the run:** the close fallback requested a 4-unit stop range while the cadet was ground-bound and far below the nape. The command used the Titan object, not a reachable ground waypoint. The request did not reach an arrival event before the circle detector abandoned the target.
- **Strong, source-supported defect; installed behavior remains unverified:** the pinned public `HumanAIController` source resolves Titan following around the nape and tests `MoveTo` arrival in three dimensions. With the observed vertical gap, a grounded cadet cannot meet a 4-unit 3D arrival radius. The installed AoTTG2 binary is IL2CPP and is not proven to match that source revision, so this remains a conditional explanation for the missing arrival.
- **Engine steering is a plausible contributor, not a confirmed installed-game root cause:** that same source adds a randomized movement-angle offset of up to ±5 degrees when smart pathfinding is enabled and up to ±45 degrees when disabled. The saved `TitanSmartMovement` value is true, but the local settings file was modified after this recording and the active runtime flag was not captured. The watcher’s velocity reversals are consistent with a steering problem but do not isolate the source.
- **Not supported as the primary cause in this interval:** M2 command thrashing. The decision trace shows a persistent Engine request and no repeated M2 movement cancellation while the route degraded. It does show that the circle policy immediately banned the target after a poor sample, turning one bad route into a distant retarget.
- **Not implicated by this run:** attack execution. The trace contains no attack attempt; locomotion failure occurred before a strike was requested.

The public engine reference is [HumanAIController.cs at commit `2bdac14`](https://github.com/douglasfelix076/Aottg2-Unity-Hex/blob/2bdac14b029a1cc42800f07e3bb2d271c49c0c7e/Assets/Scripts/Controllers/HumanAIController.cs). It is evidence about that source snapshot, not the installed executable. The documented Custom Logic calls used here are [`Human.Move(direction: Vector3)`, `Human.MoveTo(position: Vector3, range: float)`, `Human.Idle()`, and `Human.GetAIState()`](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Human.md).

## Pass 1 changes

- Ground pursuit is selected by planar distance to the Titan base. It no longer uses the cadet-to-nape 3D distance to decide whether grounded travel is needed.
- Ground waypoints use the Titan base XZ projected to the cadet's current Y. Normal approach arrives at the existing 68-unit ground threshold; no-anchor fallback arrives within 18 planar units. Neither ground command targets the nape object.
- `Direct` is now the default ground combat driver. While grounded, it repeatedly requests `Human.Move()` toward the current planar bearing. A short forward map probe diverts blocked routes to the existing bounded recovery. It uses ordinary game input and never writes character position, velocity, gas, or health.
- `Engine` remains available through the F8 comparison order, but now uses `Human.MoveTo(projectedGroundGoal, arrivalRange)` with periodic refresh. It no longer uses `MoveToTarget` for ground pursuit.
- Ground command ownership is explicit. Starting/restarting a segment clears an old engine navigation state; leaving `ApproachGround` idles the owned cadet and logs why. Hold, recovery, ODM, target loss, resupply, and other state exits therefore cancel the ground command through the same transition path.
- A circle or stall now enters the existing bounded recovery while retaining the selected Titan. The circle detector no longer immediately bans the Titan. A later ban remains possible only through bounded recovery exhaustion.
- `motion_command` distinguishes the requested API call from evidence of acceptance. Engine mode records the post-call AI state; `Human.Move` and `Human.Idle` return no acknowledgement, so Direct mode records `acceptance=not_exposed`. `motion_observed` and `pursuit_progress` report actual position change, path, planar distance, nape distance, velocity, and target gain. `motion_cancelled` records the Idle request, reason, and observed state afterward. Existing watcher event names and status properties remain compatible.

## Automated verification

The focused source-driven M2 suite covers reachable projected goals, planar arrival despite nape height, stationary and moving Titans, repeatable steering, unproductive ground progress, Hold cancellation, recovery routing, and retained Explore/order behavior. Full repository checks are recorded with the commit. These checks translate Custom Logic into a mock harness; they do not execute the installed game's parser, physics, steering, navigation, or combat.

## Required live verification

Use a fresh private master-host lobby in City 1 / Training / Waves. Back up the deployed M2 files first. Enable only `AICadetsWaveCadet`, `AICadetsCommandPanel`, and optionally `AICadetsM2Watcher`; leave the M1 demos disabled. Start from the branch files and verify F8 shows `M2-locomotion-1` and the expected profile. The current local `Settings/InGame.json` still stores `GroundSteering=Engine` from the earlier run; addon settings can override source defaults. Issue F8 `GROUND: direct steering (default)` and confirm the published profile says `ground=Direct` before the Direct trial. The saved settings file was left unchanged.

1. With one stationary Titan in a clear street, issue Engage and record video plus the watcher file. Expect `motion_command request=Human.Move acceptance=not_exposed`, repeated positive `target_gain` during successful closing, and `motion_observed` with real displacement. No `MoveToTarget` should appear for ground combat.
2. Let a no-anchor fallback approach the Titan. Verify its logged ground goal has the cadet's Y, its 18-unit arrival is planar to the Titan base, and it transitions at that range even if the nape remains above strike range. A ground arrival is not an attack or an attack-range claim.
3. Repeat a matched segment with F8 `GROUND: engine steering test`. Verify `request=Human.MoveTo` and `ai_state_after=MoveTo`; compare target-distance gain, path versus displacement, reversals, and recovery events in similar open geometry. The state observation is evidence of the engine navigation state, not proof of arrival.
4. Issue Hold during ground movement. Verify an `Idle` cancellation and no further ground motion, then verify Engage/Explore and the other F8 orders still work. Also interrupt ground movement with ODM, recovery, and low-gas resupply.
5. Repeat with a moving Titan and a blocked route. Check target-relative gain, obstruction routing, bounded recovery, and that a poor segment does not immediately ban the Titan. Preserve all logs and note the AoTTG2 build and movement settings.

Rollback by restoring the backed-up M2 files or checking out the prior PR head before this commit (`7bf204bd8525b2262b3a3f1bba3af1eb041bd7e3`). M1 files were not changed. Keep PR #6 in draft until the live checklist passes.

## Pass 2 risks

Direct bearing control is a coherent grounded controller, not a city-wide path planner. The single forward probe cannot prove full-body clearance, negotiate every corner, or choose a route around all obstacles; recovery remains finite. Live tests must establish whether `Human.Move` produces stable engine motion on slopes and through narrow streets. They must also verify that projected ground arrival leads to a viable physical ODM/strike plan and that F8, Hold, Explore, Resupply, ownership, and recovery transitions cancel or resume motion correctly. If the engine still reverses or stalls under Direct mode, collect a matched trace before deciding whether collision geometry, movement API semantics, host simulation, or the local binary's native steering requires a different approach.
