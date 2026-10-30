# Single-session A/B isolation plan

Recreate the lobby for each row; do not run with duplicate AI Cadets addons. Stay on one known-good map/spawn and the same mode and physics settings. Save exact first compiler/runtime error and line number if any.

| Run | Enabled addons | Expected player | Expected bot | Expected file | Interpretation if not met |
|---|---|---|---|---|---|
| A | Neither M1 traversal nor watcher | Human spawns at ordinary map spawn | None | None | Under-map spawn here points away from the two add-ons; inspect map/room/game mode |
| B | v3 watcher only | Ordinary spawn | None | `watch_started` appears; later timeout if no Scout | No file suggests watcher loading, permissions, wrong host, filename slot or persistence issue |
| C | baseline traversal only | Ordinary spawn | One Scout; normal 2-hook attempt | None | No Scout suggests traversal load/spawn/state/authority error; capture console |
| D | both baseline addons | Ordinary spawn | One Scout | `watch_started`, `scout_found` | Differences only in D point to addon interaction or game timing |

`Documents/AoTTG2/PersistentData/AICadetsM1WatchN.txt` may use a file extension determined by the game. Watch slots 0–99 are never overwritten by design; if all are full, archive old files **outside** the game's PersistentData folder first. Do not delete recordings without backing up.

If the player falls beneath the map in A, stop M1 debugging and isolate map/spawn configuration first. If only B, C or D exhibits the fall, record which one; script involvement becomes more plausible, but source-level causation still needs an error trace.

A normal Watch v3 file contains no controller decision trace. This is expected for the recovery build; use the existing Game.Print controller summary/screenshots to evaluate intent. The v4 enhanced-controller telemetry has been removed deliberately until isolated and validated in-game.
