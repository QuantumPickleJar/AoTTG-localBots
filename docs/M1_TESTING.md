# M1: two-anchor gameplay test

**Status: implemented for testing; no M1 in-game result yet.** Issue [#1](https://github.com/QuantumPickleJar/AoTTG-localBots/issues/1) stays open until gameplay acceptance. The v0.1.1 single-hook probe remains byte-for-byte unchanged.

## Install and set up

1. Copy `addons/AICadetsTraversal.cl` from the M1 feature branch into `Documents/AoTTG2/Addons/`. Enable **AICadetsTraversal only** in the game-creation General panel. Disable AICadetsProbe and other movement/supply add-ons; enabling both probes intentionally creates two Scouts.
2. Create a private lobby. Recommended first geometry: **City**, a wide street with staggered buildings, no nearby Titans, and room to coast. If your build labels maps differently, use a quiet city/training map with that geometry. A forest with staggered substantial trunks is a useful second test. A single wall directly across the flight path is a poor two-anchor setup.
3. Use normal physics first, defaults unchanged. Keep realism off for the initial acceptance run; test it separately afterwards with the mode recorded. The script does not change realism, gas capacity, speed, invulnerability, or physics settings.
4. Spawn the host as a human within 30 seconds. The Scout appears four units to the host's right and starts after one second. Face along the intended route as you spawn; the initial heading is captured immediately. Aim for a first visible surface about 25–50 units ahead, above the Scout, with another staggered surface beyond/beside it. Keep the right-hand spawn area clear and avoid rooftops/cliff edges.
5. Watch `AICadetsM1`. Expect two short left-hook arcs, not a planned route or combat. After first release, the Scout coasts at least 0.12 seconds and seeks the second anchor along its horizontal velocity. It may choose another point on the same building if at least 12 units from the previous anchor.

No second jump, teleport, velocity reset, refill, or direct force is used. “completed” means two attachments and releases plus one second of observation; **it does not mean a safe landing, a reached navigation waypoint, or mission readiness**. Momentum and gravity continue after commands stop.

## Expected messages and acceptance

Successful event order:

`Ready` → `leg=1 event=launched` → `attached` → `released` → `leg=2 event=launched` → `attached` → `released` → `result=completed`.

- [ ] Exactly one Scout, with the expected Levi preset; no console/parser error.
- [ ] First hook visibly attaches, short gas burst, release.
- [ ] Second hook is selected and visibly attaches without player intervention.
- [ ] Forward momentum is reasonably continuous; note stalls, reversals, impacts, or poor anchor choices.
- [ ] Final summary reports `attempts=2 attachments=2`, displacement, and plausible gas use.
- [ ] After completion/failure, gas and both hooks remain off. Watch for at least five seconds.
- [ ] Repeat the same setup three times, then try a different street/surface.
- [ ] Restart the round twice and check Scout counts. If add-on instances persist, `repeated_start` intentionally stops the experiment; recreate the lobby. If an earlier tagged Scout persists, `existing_scout_restart_lobby` refuses a duplicate. Report either outcome so lifecycle handling can be tuned to the live build.

Failure-path tests in a separate quiet lobby:

- Face open sky/no usable surface: expect `no_suitable_anchor`, zero or one attempts, no lingering gas.
- Choose a route with no forward second anchor: expect a leg-2 failure, no extra launch/retry loop.
- If an anchor does not attach: expect `attachment_timeout` within three seconds of launch.
- With naturally depleted gas or a deliberately high `MinimumGas` setting: expect `insufficient_odm_resources` before a burst; no resource refill.
- If the Scout dies or disappears, expect `scout_dead`/`scout_missing` and no further maneuver. Missing entities cannot receive cleanup calls.
- An obstructed spawn offset should yield `spawn_path_blocked`. A moving Scout approaching geometry may yield `collision_risk`. This releases inputs; it cannot cancel existing momentum or guarantee survival.
- Invalid settings (e.g. `GasBurstSeconds=10`) must produce `invalid_settings` without spawning.

Only after solo acceptance, repeat with an explicitly consenting second client. Confirm one shared Scout, visible hooks, and the same motion. **Master-client migration is unsupported**: do not use it as a success case. If authority changes during a test, the old client logs `*_cleanup_unavailable` and stops; the new client does not take over. End/recreate that test lobby to clear potentially latched inputs. No claim is made that hooks/gas are safely transferred by the game.

## Capture a useful result

Copy/screenshot the local `[AI Cadets M1]` lines from Ready through the result, plus any full error and line number. A short video showing both arcs is especially useful. Record:

```text
Commit / add-on version:
AoTTG2 build:
Map / mode / realism:
Solo or consenting private multiplayer:
Settings changed:
Spawn spot / facing direction (screenshot):
Result / state / leg:
Attempts / attachments:
Displacement / gas_used:
First arc / second arc observations:
Any impact, lingering gas/hook, duplicate, or parser error:
Round restart outcome:
```

Position, velocity, and remaining gas are printed only for the bot at launch/attachment/release. The final displacement is straight-line distance from the bot's initial position, not path length. Final gas use is initial minus last observed gas; values on death/despawn can lag by one tick. Logs are local `Game.Print`, manually shared by the tester; no player telemetry, file export or upload exists.

## Rollback

Disable/remove `AICadetsTraversal.cl` and recreate the lobby. Enable the unchanged `AICadetsProbe.cl` to repeat M0. No game binaries, mission scripts or saves are modified. Keep the M1 PR unmerged until the two visible attachments and cleanup are validated.
