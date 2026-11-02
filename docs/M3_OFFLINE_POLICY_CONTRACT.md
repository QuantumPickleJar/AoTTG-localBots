# M3 offline composition and rescue contract

**Status:** definition and synthetic-test work only. This contract does not change `AICadetsWaveCadet.cl`, does not implement a game-side executor, and does not establish real rescue behavior. M2 PR #6 remains untouched and draft.

## Profile schema v1

`tools/m3_policy_contract.py` validates a complete JSON-compatible profile. It has four independent groups:

- `skill`: perception, tracking, timing, reaction, precision, recovery.
- `movement_style`: arc and ground preferences, left/right bias, landing preference.
- `personality`: continuous `rescue_priority`, aggression, risk tolerance, cooperation, persistence, gas conservation and exploration.
- `loadout`: weapon and special observations, with a source marker.

All values in skill, style (except left/right bias), and personality are explicitly in `[0, 1]`; `left_right_bias` is in `[-1, 1]`. Missing groups, extra values, nonfinite numbers, or out-of-range values fail validation. Migration from schema 0 preserves only its explicit personality values. It fills remaining preferences with neutral defaults and marks the live loadout `unknown`; it never infers a special from a preset name.

Example safety-conscious combat profile:

```json
{
  "schema_version": 1,
  "id": "combat_cautious",
  "skill": {"perception": 0.7, "tracking": 0.7, "timing": 0.6, "reaction": 0.6, "precision": 0.7, "recovery": 0.8},
  "movement_style": {"arc_preference": 0.7, "ground_preference": 0.3, "left_right_bias": 0.0, "landing_preference": 0.7},
  "personality": {"rescue_priority": 0.1, "aggression": 0.8, "risk_tolerance": 0.2, "cooperation": 0.5, "persistence": 0.6, "gas_conservation": 0.7, "exploration": 0.3},
  "loadout": {"weapon": "unknown", "special": "unknown", "observed": false, "source": "unknown"}
}
```

Example support-focused but risk-averse profile:

```json
{
  "schema_version": 1,
  "id": "support_cautious",
  "skill": {"perception": 0.7, "tracking": 0.6, "timing": 0.5, "reaction": 0.7, "precision": 0.6, "recovery": 0.8},
  "movement_style": {"arc_preference": 0.4, "ground_preference": 0.6, "left_right_bias": 0.0, "landing_preference": 0.8},
  "personality": {"rescue_priority": 0.9, "aggression": 0.3, "risk_tolerance": 0.15, "cooperation": 0.9, "persistence": 0.6, "gas_conservation": 0.8, "exploration": 0.4},
  "loadout": {"weapon": "unknown", "special": "unknown", "observed": false, "source": "unknown"}
}
```

`rescue_priority` is independent from aggression and risk tolerance. Personality and style only affect ranking after capability, readiness, resource, state and safety filters. The reference selector is deterministic: score ties use a stable hash of the recorded seed, decision index and maneuver ID. Its bounded novelty penalty is at most 15% and never removes an option.

The live `Human.Weapon`, `Human.CurrentSpecial`, cooldown fields and `Human.IsCarried` are documented in the official API revision cited by [M3 primitive API evidence](M3_PRIMITIVE_API_EVIDENCE.md). A usable-special flag still requires a verified runtime observation; an unknown or changed loadout cannot reuse a prior plan. `SpecialEnum.Carry` and `ActivateSpecial()` do not prove pickup, carried state, transport or release.

## Catalog and selector boundary

`docs/M3_MANEUVER_CATALOG.json` keeps stable IDs, required commands/state, status and evidence needs. The status rules are:

- `definition_only`: never eligible for execution.
- `experimental`: eligible only in a deliberate isolated probe or offline planning; never dispatchable by normal game policy.
- `validated`: eligible for normal selection only when current live capabilities, equipment, cooldown, state, resources and scene safety all pass.

The reference functions implement eligibility and soft scoring only. They do not call Unity/Custom Logic and they are not wired to the production M2 controller. This separation avoids claiming that a passing Python comparison proves actual movement.

## Rescue opportunity and outcome model

`RescueOpportunity` requires a stable opportunity/victim identity, optional threat identity, evidence kind, uncertainty, observation time, reaction window, expiry, feasible intervention descriptions, travel feasibility, safety and gas budgets, reservation state and a measured outcome object. Each `Intervention` records status, travel-time estimate and uncertainty, gas cost, risk, command requirements, special/weapon requirements and extra Carry/clearance gates.

The planner rejects stale or uncertain observations, expired/reserved opportunities, infeasible travel, unknown command/equipment/readiness, unvalidated Carry, unknown gas cost and unsafe interventions. Carry remains blocked whenever an intervention requests the Carry special until CARRY-I succeeds, even if a catalog entry is accidentally marked validated or omits its explicit Carry-validation flag. A low `rescue_priority` still permits an urgent, survivable intervention. A high `rescue_priority` cannot bypass survival risk, gas reserve, capability or physical-validation gates.

An interrupt proposal records the suspended maneuver/target and holds one bounded commitment to prevent order thrash. Completing the offline plan returns a **resume candidate requiring live revalidation**; it does not issue a hook release, stop gas, retarget, or resume movement. Those physical transitions remain a runtime/API evidence gate.

Attempt, grab-state change, threat interruption, victim survival and causally supported rescue are distinct. `rescue_confirmed` requires observed intervention start, observed victim survival after a window, an explicit causal link, and confidence of at least 0.75; the protective state change must be observed grab clearance or interruption of a credible imminent threat. Survival alone is reported as `victim_survived_unattributed`.

## Current gates

- COMP-I profile/capability and synthetic rescue tests run offline; no gameplay session is needed.
- CARRY-I remains blocked until installed-build support and actual special behavior are physically checked.
- RESCUE-E remains blocked until a safe interruption/retarget/recovery path is validated, the REC-I recorder is calibrated, and intervention outcomes are observable.
- No multi-cadet behavior is implemented. Reservation arbitration tests use a synthetic owner only.
