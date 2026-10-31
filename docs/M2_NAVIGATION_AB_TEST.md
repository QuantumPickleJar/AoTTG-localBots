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
