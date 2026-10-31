# M2 ground steering investigation: navdiag-1

## Established evidence

Watch5 is an old 500-record / 90-second trace and ends at 85.24 seconds. It contains no per-cadet decision trace. At inspection, both installed WaveCadet and M2Watcher matched commit 97e9e16 after normalizing line endings, not 6061510. Therefore this recording does not validate or invalidate the later aerial-probe and profile changes. The supplied video is approximately 7.92 seconds long.

The saved InGame.json enables AICadetsTraversal, AICadetsTraversalReliable, AICadetsWaveCadet, AICadetsCommandPanel, and AICadetsM2Watcher. The first two are M1 demonstrations that can finish or terminate, not persistent squad controllers. Only one M2 controller heartbeat appears in Watch5. This strongly suggests the additional stationary humans are demo cadets; their identities were not captured by the old watcher. Do not assume all three are M2 agents or label this a squad bug without roster evidence.

The installed game is an IL2CPP build, with GameAssembly.dll rather than a managed Assembly-CSharp.dll. The public engine snapshot linked below is evidence about that source revision, not verification of the installed binary. Its HumanAIController routes MoveToTarget into a MoveTo state. MoveToPosition uses agent steering with randomized angle adjustments when pathfinding is enabled, and a wider randomized angle when disabled. Its Titan target point is associated with the nape. These are concrete candidates for the ground steering behavior, not a confirmed root cause of the observed spirals. Saved TitanSmartMovement is true; that does not expose the active agent's internals.

Source: https://github.com/douglasfelix076/Aottg2-Unity-Hex/blob/2bdac14b029a1cc42800f07e3bb2d271c49c0c7e/Assets/Scripts/Controllers/HumanAIController.cs

## Installed-version check

After updating all three M2 files, restart the game. F8 should show **M2-navdiag-1** and the resolved profile, for example **Steady scout P=3 A=3 R=3 ground=Engine**. OLD/UNKNOWN means the live controller is older or absent; copying files alone does not prove that the active lobby loaded them. The watcher header must say **v3 navdiag-1**, 2000 records and 300 seconds. Moving samples are restored to 0.2-second intervals to capture the reversals. It may hit the record limit before five minutes. Every ten seconds the watcher records owned, recognized M1/M2 identities and controller status. It does not issue movement or record human-player positions.

The profile settings are public fields at the top of AICadetsWaveCadet.cl. F8 displays the resolved values but does not edit personality fields. ProfileName is a label; Persistence, AerialPreference, and RepositionSkill are 1–5 policy parameters. They are not three spawned characters. Keep 3/3/3 during this investigation. No personality calibration can correct an invalid navigation command or an inactive controller.

## Controlled comparison

1. Private City 1 / Training / Waves. Enable only **AICadetsWaveCadet**, **AICadetsCommandPanel**, **AICadetsM2Watcher**. Disable the two M1 traversal demos. Begin a new lobby; expect one M2 cadet.
2. Verify the F8 build/profile and watcher header. Leave the default **Engine** ground driver selected. Issue Engage toward a distant Titan and record 20–30 seconds of ground movement in a clear street, keeping the bot and minimap in view.
3. Select that same M2 cadet and choose **GROUND: direct steering test** in F8. Continue recording another 20–30 seconds. This does not issue Engage, override Hold, or change the target by itself. It restarts a current ground segment using direct Move inputs; other navigation states switch when they next enter ground pursuit.
4. Select **GROUND: engine navigation** and compare once more. Repeat in a fresh lobby with similar starting geometry. Keep the same profile and game movement settings. ODM probes, target motion and obstacle encounters are confounders: compare ground intervals with matching state/geometry, not the whole run blindly.
5. Send the new watcher file and video. Look for build/driver identifiers, ground_driver_changed, motion_command, pursuit_progress, travel_probe and owned_cadet records. Target position and timestamps allow checking whether distance closes rather than merely measuring movement.

**Direct mode is diagnostic**, not a general path planner. It uses documented Human.Move(direction: Vector3) on each grounded tick toward the target's planar bearing, with a short obstacle probe and bounded recovery. Engine mode uses Human.MoveToTarget(target: Object, range: float). Direct mode clears the native MoveTo state once before issuing input. It does not write position, velocity, gas or health. Near the target or a blocked corridor it stops and recovers; it does not steer through walls. Explore, supply and recovery waypoint movement retain their existing engine navigation, so ground=Direct does not imply every state uses direct inputs. The comparison can implicate the native target-following stack, but does not isolate its exact internal routine or prove a cure for all geometry.

Official action contracts: https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/Entities/Human.md

Hold, death, authority loss, gas diversion, target invalidation and physical attack checks remain authoritative. Termination now also idles an owned cadet while master, stopping residual movement input. Automated controller tests do not validate the installed game's parser, frame ordering, steering or combat. Keep PR #6 unmerged pending live validation.


## Watch2/Watch3 follow-up: navdiag-2

Both supplied captures identify navdiag-1 and only Engine driver changes. They do not establish a direct-versus-engine result. Watch3 records an `attack_attempt` at distance 8.73 and an `attack_result confirmed_damage=false`, without evidence of a hit or kill. It also records 456 failed anchor searches and 90 recovery-exhausted events in the captured first 3000 decisions, ending at game time 149.26 while the watcher continued. The single temporary-ban slot and immediate reacquisition let different targets cycle rapidly; transitions were not proof of movement.

Navdiag-2 pauses inputs for six seconds after retry/recovery exhaustion before reacquisition. During target ground pursuit, it measures path length at controller ticks and net displacement over five seconds. At least 30 units of path with net displacement under half that path triggers `circling_detected`, idles and observes for six seconds. This is a heuristic; tight legitimate turns can trigger it, and slow spirals may evade it. Logs include path, displacement and forward progress. Hold and low-gas diversion still preempt the pause. The observer stands in place; higher-ground planning is not implemented.

Engine steering remains the default. F8 should show M2-navdiag-2, and the watcher header v3 navdiag-2. For a direct test compare matched, unobstructed, grounded segments: target-distance change, path versus displacement, obstacle/recovery events and engine/direct labels. Direct mode changes the steering method and target bearing, so differences cannot identify the exact native internal cause. The supplied report shows no direct selection. Five-hertz watcher samples plus target geometry and decision events can diagnose many runs without video, but occlusion, exact collision and attack visuals remain outside their evidence; preserve video when those questions matter. Controller traces stop at 3000 events and watcher files can hit their own cap early.


## Watch4/Watch5: airborne retries and update rate

Both captures identify navdiag-2. Watch4 records a grounded target pursuit with zero movement for two five-second windows and reposition results of 0 and 1.26 units. It cannot by itself identify the obstacle geometry. Watch5 identifies an owned `AICadetsM1R` with `no_M2_controller` alongside M2-1; the watcher is not a complete observer for arbitrary humans. No M2 terminal failure is recorded in either file. The M1R demonstration is not governed by M2 orders; disable M1 add-ons for the isolated test.

The M2 controller already uses the documented `OnTick()` fixed-update callback, nominally 0.02 game seconds. `OnFrame()` is render-rate dependent and is not a safe substitute for this control loop. More polling would not fix a state machine that retries faster than physics can change. See https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/callbacks/main.md.

A concrete timing issue appears in Watch5 at game time 26.48–26.56: while falling, repeated no-anchor approach/recovery probes consumed the target's recovery budget in approximately 0.08 seconds. Navdiag-3 waits for landing for up to four game seconds after an airborne no-anchor failure, then replans with the same target. A timeout pauses observation; Hold, low gas, ownership loss and target loss remain preemptive. The wait does not claim landing or write movement/position. On grounded recovery, both candidate lateral corridors are now probed; if both are blocked the cadet pauses and temporarily bans the target rather than directing a waypoint through the second obstacle. This is not a general narrow-alley path planner.

`tick_health` records callback count, game-time window and maximum game-time gap every ten game seconds, including Hold. This assesses observed game-time scheduling, not real wall-clock responsiveness or every subsystem's rate. Target scans, physics collision checks, anchor probes and telemetry each retain their own deliberate timing, independent of personality. If the reported cadence differs from the documented default, correlate it with game speed and logs before changing it.

Next: load M2-navdiag-3 and watcher v3 navdiag-3 in a fresh game session, enable only WaveCadet, CommandPanel and M2Watcher, and verify F8 build. In City 1 / Training / Waves record one open-street target and one between buildings. Check `landing_wait`, `landing_complete`, `reposition_blocked`, `tick_health`, target distance and attack outcome. Check Hold and low gas during WaitLanding. Do not claim pathfinding, attack damage, kill or refill until observed.
