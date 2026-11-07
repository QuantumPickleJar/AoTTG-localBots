# M3 design proposal — character composition, rescue, movement primitives and adaptive choice

Status: **design only**, November 2, 2026. This document does not claim these behaviors exist in AICadetsWaveCadet. Do not alter the untested M2-locomotion-1 runtime in the initial validation pass. M2 PR #6 remains draft.

## Goal and player-visible outcome

One local-first AI cadet should behave like an engaged teammate: move competently using actual physics, notice threats to nearby humans mid-maneuver, choose plausible rescues, act within real ability/loadout restrictions, and develop recognizable personality without scripted outcomes, teleports, fake damage, or forced survival.

The validated base remains M0 single-hook motion. M2-locomotion-1 is staged and awaits first live steering acceptance. Combat nape attack animations have been observed but AI-attributed damage and kills are unconfirmed. No squad, rescue, Carry, gas dash, or procedural-maneuver gameplay is established.

## Four-part character composition model

- **Skill**: perception/target tracking error, anticipation, reaction delay, motor command precision, maneuver confidence, recovery choices; hard, shared physics limits always apply.
- **Movement style**: preference for sweeping arcs, direct approaches, controlled landing, left/right hook use, ground movement, etc. Applies soft ranking among feasible options, not unsupported capabilities.
- **Personality**: rescue_priority (altruism vs combat focus), aggression, risk_tolerance, cooperation, persistence, gas_conservation, exploration. Rescue priority is independent of courage: a compassionate but cautious cadet may find a safer intervention or decline an impossible attempt.
- **Equipped loadout/ability**: actual weapon, special and status, read from the live Human where possible. Defines hard eligibility, including compatibility, readiness and cooldown. Neither name nor costume implies an equipped special. Never silently replace a failed special with a fictional effect.

Use a compact versioned profile schema, with explicit defaults and clamp/range validation. A human-readable example (conceptual data, not ready-to-load .cl):

```json
{
  "schema_version": 1,
  "id": "scout_support_example",
  "skill": {"tracking": 0.7, "reaction": 0.6, "recovery": 0.7},
  "movement_style": {"arc_preference": 0.7, "ground_preference": 0.3, "left_right_bias": 0.0},
  "personality": {
    "rescue_priority": 0.85,
    "aggression": 0.35,
    "risk_tolerance": 0.55,
    "cooperation": 0.9,
    "persistence": 0.5,
    "gas_conservation": 0.75
  },
  "loadout": {"weapon": "Blade", "special": "Carry"}
}
```

## Maneuver catalog — reusable, extensible, and honest

Each maneuver *definition* should include:
- stable id, family, tags/intent, parameter ranges (angles, timing, gas pulses, anchor types), physical goal and exit conditions;
- capability requirements: real command bindings; equipped weapon/special; cooldown/readiness; available gas/blades/hooks; ground/air/Grab/Carried states; target and environment/clearance/line-of-sight prerequisites;
- estimated duration, gas cost, failure/recovery risk, interruptibility, required evidence for success;
- implementation status: `definition_only`, `experimental`, or `validated`. Definition-only items must NEVER be dispatched as executable maneuvers;
- plan executor and recovery/fallback; per-character weighting tags. The catalog describes what a move *can* do; the profile determines how much the cadet *prefers* it.

Selection stages: (1) live capability/loadout filter, (2) scene feasibility and safety checks, (3) personality and style soft scoring, (4) tactical context/risk/gas utility, (5) bounded novelty adjustment among feasible choices, (6) execute with observation and replanning. A changed special invalidates special-only plans immediately, but not universal evasions. `Spin1/2/3`, `DownStrike`, `Escape`, `Carry` are distinct specials; do not assume one is always on Levi or any other named preset.

**Anti-staleness is a soft penalty**, never a cooldown-based exclusion unless a real physical/cooldown/safety constraint demands it. Consider a 5–15% initial repeat-score penalty on equivalent maneuvers, decaying with elapsed time and intervening actions; cap the penalty and let urgent/singular valid actions override it. Repetition is sensible if only one valid solution exists. Track maneuver family and parameter similarity to avoid superficial variants gaming novelty.

Initial families to verify before parameter expansion:
- grounded Dodge (universal if CanDodge/state allows), Jump, Jump + directional Dash/gas, controlled direct ground steer;
- directional air Dash/gas burst, physical map hooks, left/right/both hooks, tether arcs and releases;
- combat intercept and nape strike (existing experimental implementation), evasion and safe fallback;
- rescue approach, threat interruption, post-save extraction; Carry-dependent pickup/transport only after API/engine validation.
Do not assume `Human.Dash(direction)` alone proves gas-burst semantics, gas consumption, exact impulse, invulnerability, or legal state transitions. Measure them.

## Rescue as a strategic objective and high-priority tactical interrupt

Add **RescueOpportunity** as a time-bounded observation, not a fictional success state. Example fields: victim identity, owner/network visibility, cause/threat identity, evidence (grab state, Titan hand, dangerous approach trajectory), time-to-impact estimate with uncertainty, feasible intervention set, reservation/claiming cadet, gas/time/safety budget, and last observed outcome.

Rescue detection:
- *confirmed grabbed*: a human is observed in the documented `Grab` state, after verifying what that means in the current runtime and whether it is accessible to the cadet owner;
- *imminent danger*: predictive risk from actual Titan animation/relative motion and usable map geometry. False positives must be bounded and independently measured, not fabricated guarantees;
- *post-intervention extraction*: human released/alive but in danger, with a physically viable destination.

Behavior variants must work **without** Carry: attack/disable the threat where physically verified, distract/redirect if supported, block/evade, or escort/help cover. With `Carry`, permit actual pickup/transport only after an isolated in-game test confirms `ActivateSpecial()` ability conditions, target acquisition, carried-state observation, and release. The existence of `Human.IsCarried` and `SpecialEnum.Carry` does NOT establish the full rescue method. Do not invoke `Titan.Blind()` or `Titan.Cripple()` to manufacture a physical rescue absent a verified blade hit.

Define rescue decision as expected protection benefit, urgency, probability of physical success, risk to rescuer and victim, opportunity cost of stopping a fight, gas affordability and personality preferences. Rescue priority can raise willingness, but no profile can veto collision/ownership/safety restrictions. Use priority interrupts and bounded commitment to prevent oscillating between attack and rescue every frame. Retain context and momentum when safely possible, and log reasons for acceptance, rejection and interruption. Later squad coordination can claim a rescue opportunity to prevent every cadet converging on one player; no assumption that two cadets already work.

Rescue outcome evidence distinguishes: `opportunity_detected`, `rescue_selected`, `rescue_intervention_started`, `grab_state_cleared`, `victim_alive_after_window`, `carry_started`, `carry_ended`, `rescue_confirmed`, `failed`, `unknown`. Observed survivor timing alone is not enough to claim causal rescue. Do not record player-identifying data by default or imply client-side omniscience.

## Gas economy and evasive primitives

Official documented Human commands include `Jump()`, `Dodge()`, `Dash(direction)`, `UseGas(bool)`, `Move(direction)`, `ActivateSpecial()`; properties include `CurrentGas`, `MaxGas`, `CanDodge`, `CurrentSpecial`, and special cooldown. Exact semantics and cost of combining dash with sustained gas need a dedicated physical probe.

Gas-aware maneuver utility should use observed normalized reserve, expected expenditure, distance/time to real resupply, survival urgency and character-specific `gas_conservation`. Normal situations may discourage gratuitous bursts; imminent fatal threats may spend reserve defensively. Do not treat conservation as a universal hard ban on life-saving movement. Reserve policy should separate safe minimum for retreat from emergency override; all profiles obey actual gas availability and physical mechanics. Stop gas input on interruption, death, round reset, authority loss when legal, or completion.

Measure three distinct events in isolation: grounded Dodge, grounded Jump then directional Dash/gas, and midair directional Dash/gas. Record start state, velocity/acceleration change, displacement, time, gas before/after, landing state and collision. Never equate GroundDodge/AirDodge, Dash, and sustained UseGas without empirical confirmation.

## Concurrent decision architecture (design only)

- Fast physical control: regular state/velocity/hook/collision safety monitoring and active maneuver correction, benchmarked against documented OnTick 0.02s fixed-update callback, but not necessarily evaluated every tick.
- Tactical: reacquire threat motion, update interception, pick rescue/strike/evasion windows, handle interrupts and failed maneuvers, at dynamic bounded cadence plus events.
- Strategic: persistent objectives, survival/resupply, teamwork and personality-driven preferences at low cadence and on significant events.

Use a shared perception snapshot per cadet/cycle, bounded per-frame computational budget, hysteresis/commitment windows and interrupt hierarchy. A high-speed airborne segment may need more frequent checks, but near-imminent grounded threats do too. Reduce unnecessary path probes when little changes. Dynamic decisions must not spam `Idle`/`MoveTo` or reset valid hook arcs. Avoid one heavyweight planner per frame, particularly on mobile; performance acceptance is measured as frame-time overhead and active cadence under load, not target fps promises.

## Milestone sequence and acceptance gates

0. **First test untouched M2-locomotion-1** on feature branch and collect watcher+video. Confirm F8 Direct steering despite saved settings, compare Engine, verify Hold, terrain blockage, movement progress; keep PR #6 draft.
1. Stabilize grounded/airborne movement and *actual* nape attack damage/kill attribution before claiming autonomous combat reliability. Use one atomic fix per observed failure when possible; evidence, live check and rollback per change.
2. Isolated **movement primitive** test add-on for Jump, Dodge, Dash/gas and their combinations; keep baseline M2 untouched. Capture gas and state transitions. Add only verified moves to the executable catalog.
3. Implement versioned **catalog + four profile categories** with hard capability filtering, logged soft scoring and limited novelty penalty. Start one cadet; tests for empty catalog, one valid maneuver, special swap, low gas, emergency override and failure fallback.
4. Build **rescue perception and intervention** first for non-Carry cadets; create reproducible grabbed-player and pre-grab danger tests. Investigate Carry in an isolated probe, only then unlock pickup/extraction variants. Verify victim state/outcome via observation and avoid fake rescues.
5. Add layered, bounded adaptive decision cadence and persistent short-term behavior memory, then multi-cadet arbitration; compare CPU/frame-time budget on desktop and lower-end/mobile platforms as accessible.

Never merge PR #6 on static checks alone. Keep M0/M1 reference files and all previous gameplay logs intact. Prefer sequential, small, independently testable Luna sessions to a single unbounded rewrite.

## Official API references (check actual installed version)

- Human: https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/Entities/Human.md
- Specials: https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/Enums/SpecialEnum.md
- Human states: https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/Enums/HumanStateEnum.md
- Callbacks: https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/callbacks/main.md
- Source-based M2 findings: docs/M2_LOCOMOTION_STABILIZATION.md
- Existing tactic definitions: docs/M2_TACTIC_CATALOG.json
