# M2 City Wave field-test recovery — global acquisition and long-range pursuit

## Why M2 seemed idle

In the Oct 30 City 1 / Training / Waves video, the M2 bot repeatedly printed:

`state=AcquireTarget event=target_none reason=no_alive_titan` followed by `Regroup`.

The old `AcquireTarget` discarded **every Titan farther than 220 world units from the cadet** and then used the misleading `no_alive_titan` reason even if the roster contained alive but distant Titans. Walking the *human player* nearer to a Titan does not change the cadet's distance.

The uploaded `AICadetsM1Watch0(1).txt` and `AICadetsM1Watch2.txt` are **v3 M1-only recordings** (`AICadetsM1`), not M2 telemetry. Their two-hook flights cannot establish whether `AICadetsWaveCadet` moved, acquired a target, or attacked.

## Patch behavior

- Search **all** living Titans in `Game.Titans`, regardless of initial separation. `distance` affects *ranking*, not eligibility.
- Log `listed`, `alive`, `banned`, and nearest nape distance on empty selection; distinguish `no_alive_titans` from `all_candidates_temporarily_banned`.
- Throttle no-target polling to 2.5 seconds to prevent chat budget saturation, and mission snapshots to 5 seconds.
- Allow up to 30 bounded two-hook traversal attempts per distant target (max configurable 40), rather than 5.
- Continue steering toward the nape during the second leg, while blending some horizontal momentum.
- Probe lateral City-building surfaces when the forward rays yield no usable anchor.
- Change heading between bounded recovery attempts to avoid repeating the same obstructed path.
- Preserve original M1 controller and observer untouched, and no direct position/velocity writes, teleports, resource refills or mission-script edits.

## First real lobby test (important)

**Only enable `AICadetsWaveCadet` at first.** Disable `AICadetsTraversal`, `AICadetsTraversalReliable`, `AICadetsProbe`, and the original `AICadetsWatcher` while isolating M2. They are independent add-ons; M2 does not require the M1 add-ons to be running. The v3 watcher only follows a bot literally named `AICadetsM1`.

1. Back up the old `AICadetsWaveCadet.cl` and install the file from **this branch** to `Documents/AoTTG2/Addons/`.
2. Create a fresh **private** City 1 / Training / Waves lobby, initial master host, normal physics. Wait until ordinary Titans have spawned and the player is alive.
3. Expect `[AI Cadets M2] cadet_spawned`, then `target_selected ... distance=...` even if the Titan is far away.
4. Expect `PlanApproach -> traverse_start -> hook_launch` or a documented `anchor_search_failed` / `traverse_end` outcome. Following two-hook travel, expect new `PlanApproach` attempts while meaningful progress is made.
5. If still no target, copy a **full** `target_none` event:
   - `listed=0 alive=0`: the Custom Logic `Game.Titans` roster is empty at that moment. Compare with HUD and game mode; investigate mode/spawn visibility before changing navigation.
   - `listed>0 alive=0`: there are roster members but none report alive.
   - `alive>0 banned>0`: temporarily excluded after failed traversal; observe until ban expires.
   - `target_selected` but `anchor_search_failed`: target discovery works; City geometry/path planning is next.
6. **Do not** infer a confirmed collision from v3 `possible_impact`; it is only a velocity/linecast clue. Do not infer a hit/kill from attack animation without damage/death callback.
7. Keep `SaveRunReport=false` for first isolation so file I/O cannot mask initialization faults. Capture M2 chat lines, HUD, and 20–40 seconds of video. Optionally enable it after a successful run; note that current M2 only saves its report at termination.

## Acceptance gates

- [ ] M2-only bot spawns without modifying player spawn.
- [ ] Alive, distant Titans are discovered (previous >220-unit regression).
- [ ] At least one `traverse_start` and physical hook launch towards a distant target.
- [ ] Meaningful target-distance progress over multiple maneuvers; no infinite static repetition.
- [ ] If a route is obstructed, bounded failure/recovery is logged without looping unboundedly.
- [ ] Nearer Titan is reacquired as appropriate on death/movement.
- [ ] Attack and mission accounting scenarios remain **untested** until genuinely exercised in-game.
- [ ] Regression checks run: `python -m unittest discover -s tests -v`.

## Limitations

This is a navigation-enabling field patch, **not proof that M2 combat is accepted**. A global target selector is not a complete all-map pathfinder. The 30-traversal cap limits the amount of search and flight; distant targets with no forward/lateral anchor may still be unreachable. If the roster shows zero Titans in the correct game mode despite the HUD showing live Titans, inspect actual runtime game-mode lists rather than assuming there is another undocumented Titan enumeration API. Preserve the original source as rollback; do not merge to main before gameplay evidence.
