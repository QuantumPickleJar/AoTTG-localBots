# Character policy foundation and combat-arc-2

## Recorded result

Watch13 and Watch14 contain four `attack_state_observed` events in total with actual blade animation names (Armature|attack2 and Armature|attack1_hook_r2). They also record attached nape-tether arcs with changing radial vectors. Every strike result has no observed damage; no cadet damage or kill is established. Attack inputs began approximately 9.26–10.06 units from the nape. This supports testing a closer intercept, but does not prove distance was the only cause of misses. The four supplied clips were sampled across their durations; they show near-Titan movement and wall contact, but exact video/log synchronization is not established.

## Implementation

Build M2-combat-arc-2 retains the observed tether mechanism and adds a close-intercept phase. At the old AttackRange the arc shifts from predominantly tangential input toward an inward bearing. It keeps the hook while closing and releases for attack within `StrikeCommitRange` (default 5 units), bounded by AttackRange and the existing arc duration and collision/gas checks. All strike entry points use the effective commit range. AttackSetup permits one extra unit of tick-to-tick displacement. Five units is an experimental tuning value, not a documented blade collision radius or proof of a hit. `orbit_intercept` records entry to the close phase.

Ground recovery now checks five candidate segments: the existing forward diagonals, pure left/right, and a backward step. Each candidate is checked at torso and low height against both map layers before MoveTo. This can back away from a wall instead of probing only toward it. If all are blocked, or a dispatched escape produces less than two units of displacement by arrival/timeout, the cadet pauses and temporarily bans that target rather than repeating the same stalled route. These centerline rays do not prove body clearance, navmesh validity, floor support or a complete route around buildings. Hold and resource/authority interruption retain priority; Explore maneuvers are unchanged.

## Personality, skill and style boundary

The current implementation has one cadet. This foundation is for selectable character policy, not evidence that a squad or three character modules are complete.

- **Personality** will rank tactical intents and persistence/risk preferences. It must filter capabilities before ranking; an attractive unavailable tactic cannot become an action.
- **Skill** will tune observed geometry, timing and recovery within hard physical budgets. It cannot grant hits, refill gas, change health, teleport, or bypass ownership checks.
- **Style** will choose among physical approach variants such as left/right tether arcs, map ODM and close intercept. Cosmetic labels alone do not count as executable maneuvers.

`TacticCapability(id)` returns `physical_experimental`, `definition_only`, or `unknown`. `SelectCombatTactic(id)` accepts only executable capabilities and logs the selection; unavailable requests retain the current nape tactic and log `tactic_unavailable`. Public `PreferredTactic` defaults to `NapeStrike`. F8 shows the accepted tactic. At present the selector admits only nape strike, so all actual aim routing remains nape-specific. Future tactics need their own geometry/action/outcome implementation before this gate is opened.

The machine-readable catalog is `M2_TACTIC_CATALOG.json`. Tests compare it with runtime capabilities to prevent silently advertising unimplemented actions.

| Tactic | Intended effect | Approach definition | Current capability |
| --- | --- | --- | --- |
| NapeStrike | Finish target | Map ODM, left/right tether arc, close intercept | Physical experiment; swings observed, damage unverified |
| FaceBlind | Disrupt vision | Front-oblique pass toward verified face hurtbox | Definition only |
| ArmDisable | Reduce reach | Outer-flank pass toward verified arm hurtbox | Definition only; game support for sever/disable must be established |
| AnkleCut | Reduce mobility | Low rear pass toward verified ankle hurtbox | Definition only |

A damage callback by itself cannot prove blinding, limb removal or crippling. Each tactic needs independent outcome observation and correct cadet attribution. Official Titan documentation exposes NapePosition, HeadMount and NeckMount; a head mount is not a verified face hurtbox, and it does not provide calibrated arm/ankle targets. The documented Blind()/Cripple() state-changing methods are not called to simulate successful tactics. Exact support must be investigated before implementing those physical strikes:
https://github.com/AoTTG-2/CustomLogicDocumentation/blob/ded03751aee1b1179141aeb534faa2f1fc266aff/reference/Entities/Titan.md

## Next field run

Restart with only WaveCadet, CommandPanel and M2Watcher, and verify M2-combat-arc-2 in F8 plus combat-arc-2 in the watcher header. Reliable Traversal remains a separate M1 demonstration and is not required.

Use a fresh City 1 / Training / Waves session: first an exposed Titan, then a building corner. Capture `orbit_intercept`, attack distance/state/animation, target_damaged/titan_die attribution, `escape_route candidate=...`, `reposition_end moved=...` and paused outcomes. Keep profile/arc settings fixed initially. A closer attempt can reduce the number of swings if the bot cannot reach the new range; report that rather than assuming a parser error or success. Retest Hold and low-gas diversion during escape and arc. Roll back to e3f6d98 or the backed-up combat-arc-1 files if needed. Static/mock success does not establish live wall escape, blade damage, kills, tactical status effects, or squad cooperation.


## Watch15/16 follow-up: combat-arc-3

Both supplied captures identify combat-arc-2. Watch16 records one Titan-tether intercept and attack input at 43.640 game seconds, 4.568 units from the nape. The human state at input was `Land`, with `Armature|dash_land`; no `attack_state_observed` or damage was recorded during the observation window. This establishes the input was issued during landing and no attack state was observed, not that landing was conclusively the only reason the attack failed. AttackSetup now waits up to 0.8 game seconds for the documented incompatible human states to clear, while rechecking target, range, and obstruction each tick. Timeout enters recovery. Hold, low gas and target loss retain priority. Actual attack eligibility can include additional engine conditions.

Watch16 also records repeated inefficient ground paths at approximately 121.73, 132.79, 143.83, 154.88 and 165.92 game seconds, each followed by a six-second pause and reacquisition of the same target. On `circling_detected`, combat-arc-3 temporarily bans that target for 20 seconds before observation and reacquisition. Other eligible Titans can still be selected and patrol can continue when none qualify. The existing single-target ban is bounded and does not imply a general path planner. Candidate 3 ground escape in Watch16 produced 8.66 units of displacement, while Watch15 had blocked escape and no Titan attack event; these observations do not prove all building-corner cases are solved.

The provided clips are approximately 18.6 and 32.8 seconds; sampled frames show Titan-area and building-side views, but frame-to-game-time alignment with a specific callback is not established. Next run: restart with the same three M2 addons, check F8 `M2-combat-arc-3`, then record an exposed Titan and a corner. Report `attack_wait_ready`, `attack_not_ready`, `attack_state_observed`, damage/death attribution, `circling_detected`, `target_banned`, and subsequent movement. Test Hold and low-gas interruption during readiness waiting. Compare the cadet's actual Human.State and attack animation with the callback; neither a request nor a wait implies a hit.

### Watch17: target persistence, moving targets, and collision evidence

The `M2-combat-arc-3` trace records three nape-range attack inputs and observed `Attack` animations against target 1006, with no damage confirmed in the verification windows. Later, at game time 258.5, a fallback ground segment traveled about 54 units with 16 units of forward displacement, yet the path-efficiency rule classified it as circling and banned that target for 20 seconds. That explains a recorded target switch; the video and game timestamps have not been aligned, so it is not certain this is the exact moment noticed in the clip. The nape distance fell by only about two units during that fallback, so forward displacement alone is not proof of successful interception.

In `M2-combat-arc-4`, a circle ban also requires little forward movement and less than four units of target-distance gain in the five-second sample. A closing Titan no longer counts as a stationary stall solely because the cadet is stationary. The normal grounded command remains `MoveToTarget`; between two physical ODM legs the controller refreshes the selected living Titan's nape and facing before planning the next leg. It does not continuously redirect a hook already in flight. These changes are source-tested, not yet verified in the game.

The sampled video frames show Titans near the gate and buildings but cannot establish whether a particular ray was a false positive. Collision forecasts retain their original reach and priority. New `collision_probe` records include position, velocity, predicted endpoint, and observed map hit; `orbit_probe` now separates range from a map obstruction and records the latter's geometry, as does `attack_blocked`. A probe is a forecast, not proof of a collision or an incorrect ray.

For the next City 1 / Training / Waves run, reload the WaveCadet, command panel, and M2 watcher addons and confirm F8 reports `M2-combat-arc-4`. First issue Engage once against an exposed, moving Titan, then repeat near a gate or building corner. Save the watcher trace; report `pursuit_progress` (including `target_gain`), `approach_goal_updated`, `orbit_probe`, `collision_probe`, `attack_blocked`, attack state/animation and damage callbacks, `circling_detected`, and `target_banned`. Compare target positions across the approach and check whether the cadet closes, attacks, and continues searching without another order. Include a truly circular route to confirm it still pauses, and check that Hold interrupts motion. These source changes do not establish damage, kills, reliable moving-target pursuit, or resupply in live gameplay.
