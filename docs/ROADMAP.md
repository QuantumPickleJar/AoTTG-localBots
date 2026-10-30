# Roadmap

## M0 — Minimal runtime proof
- [x] Add-on parses in the tested AoTTG2 build (2026-10-29).
- [x] One `[BOT]` Scout spawns in the tested host session.
- [ ] Other multiplayer client sees same Scout (test only in opt-in private lobby).
- [x] Linecast finds a genuine surface in the tested scenario.
- [x] Left hook launches, attaches, short gas burst activates, and hook releases (one successful run).
- [x] Logs displacement and gas usage at completion without reported console errors (one successful run; timeout path untested).
- [ ] Restarting a round does not duplicate Scouts.

## M1 — Physical maneuver reliability
- [ ] Stable initial positioning with no collision spawn.
- [ ] 10 test attempts on 3 different map surfaces.
- [ ] Add second anchor and controlled hand-off.
- [ ] Add fall/collision recovery and gas safeguards.
- [ ] Add realism settings profile, test rather than assume rules.

## M2 — Wave mode
- [ ] Determine mission accounting for bot kills, alive humans, game over, respawn.
- [ ] Target Titan, approach, attack nape, retreat.
- [ ] Add simple team support / target reservations.
- [ ] Ensure bots never prevent mission completion unintentionally.

## M3 — Boss missions (Annie / Colossal)
- [ ] Identify boss state transitions, attack windows, weakpoints.
- [ ] Distinguish survivability and objective support from merely dealing damage.
- [ ] Verify bot contribution in victory / loss logic.

## M4 — Racing
- [ ] Reach checkpoints; record completion, time, collisions, gas use, route efficiency.
- [ ] Add named maneuvers and skill-profile parameters.
- [ ] Incorporate high-skill human demonstrations only if later available.

## M5 — Optional telemetry and cooperative logistics
- [ ] Separate, disabled-by-default local **self** telemetry (movement, hooks, timings).
- [ ] Explicit, informed opt-in before any export or network upload.
- [ ] No collection from other multiplayer participants without their own consent.
- [ ] Optional route demonstration import with attribution / permission.
- [ ] Gas-canister support as a gameplay proposal: distinguish simulated player supply sharing from an actual physical canister mechanic, which may require engine changes.
- [ ] Normal-mode consented team gas indicators; realism mode restricts omniscient gas information (e.g., explicit help requests rather than full teammate HUD).

## Non-goals initially
- ML training, hosted inference, gathering gameplay data without consent, source-game binary patching, or running in public servers without permission.
