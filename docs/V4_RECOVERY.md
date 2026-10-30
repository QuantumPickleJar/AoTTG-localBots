# M1 v4 regression: recovery and A/B isolation (2026-10-30)

## Reported symptoms
- M1 Scout no longer spawned after installing downloadable v4 ZIP.
- The host player spawned beneath the map.
- No new watcher file appeared.

The failing game parser/console output has not been supplied, so **root cause is unknown**. The external v4 ZIP changed BOTH the M1 controller (new PersistentData decision-trace writes) and the watcher (higher-frequency sampling and risk probes). Do not treat either change as proven culpable. Neither script explicitly moves the host player, so establish the under-map symptom with no add-ons first.

## Recovered exact baseline
The two unchanged .cl files already on feat/m1-observer are:
- addons/AICadetsTraversal.cl: Git blob SHA 4c1d23c628d18f98500d2c3f20f5d954c1ea17fd
- addons/AICadetsWatcher.cl: Git blob SHA 5b3e1720b6e3d66b4fc35d0c9957306b67203b57

These correspond to the earlier v3 watcher recording that showed two observed hook attachment/release pairs. This does not establish that restoring them fixes player spawning; test it.

## Reproduction matrix
| Run | Enabled | Expected |
| --- | --- | --- |
| A | Neither addon | Player normally spawns; no Scout; no new Watch file. Under-map spawning here suggests map/game mode/spawn, not these addons. |
| B | v3 watcher only | Player spawns, no Scout; Watch file should contain watch_started before eventual no-Scout timeout (master client). |
| C | baseline traversal only | Player spawns; one Scout attempts two hooks. No watcher file expected. |
| D | Both baseline addons | Player spawns; one Scout; watcher file contains watch_started and scout_found. |

Recreate a private lobby for EACH run with the same known-good map, normal physics, realism off, master host, and no other movement/supply add-ons. Capture the FIRST parser/runtime error with line number, the first chat message, bot presence, player spawn, file creation, and run letter. If A still spawns under map, pause M1 debugging.

The v3 watcher searches PersistentData/AICadetsM1Watch0..99 and avoids overwriting existing files; archive old files outside Documents/AoTTG2/PersistentData if every slot is occupied. SaveToFile uses shared PersistentData, so inspect before sharing.

## Safety and follow-up
- Preserve untouched M0 probe and original v3 M1 script hashes.
- Do not deploy the unverified downloadable v4 instrumented controller.
- The Python offline analyzer may process v3 Watch files without changing game scripts. It cannot reconstruct unlogged controller decisions.
- Add future controller decision telemetry ONLY as an isolated, separately verified PR; do not change controller and watcher simultaneously.
- PRs #3 and #4 remain subject to in-game acceptance; no claim that local static tests validate AoTTG Custom Logic runtime.
