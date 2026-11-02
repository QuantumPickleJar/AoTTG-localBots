"""M3 profile, capability and rescue contract mocks; no game policy is executed."""
import copy
import unittest

from tools.m3_policy_contract import (
    ContractError, EquipmentSnapshot, Intervention, MeasuredOutcome, PlannerMemory,
    RescueOpportunity, RuntimeSnapshot, check_maneuver_eligibility,
    classify_rescue_outcome, default_profile, finish_rescue, migrate_profile,
    plan_rescue, profile_hash, rank_maneuvers, validate_profile,
)


def eligible_state(**overrides):
    value = {
        "alive": True,
        "grounded": True,
        "can_dodge": True,
        "available_commands": ["Human.Dodge()", "Human.Jump()", "Human.Dash(direction: Vector3)"],
        "gas_fraction": 0.8,
        "safety_budget": 0.5,
        "clearance": True,
        "special_ready": True,
        "loadout": {"weapon": "Blade", "special": "Carry", "observed": True, "source": "live_api"},
    }
    value.update(overrides)
    return value


def maneuver(action_id, status="validated", **extra):
    value = {
        "id": action_id,
        "status": status,
        "required_commands": [],
        "required_state": ["alive"],
        "utility": {"progress": 1.0, "combat": 0.0, "rescue": 0.0, "risk": 0.0, "gas_cost": 0.0},
    }
    value.update(extra)
    return value


def runtime(**overrides):
    value = {
        "alive": True,
        "available_commands": ("Human.Attack", "Human.Move", "Human.ActivateSpecial"),
        "equipment": EquipmentSnapshot("Blade", "None", True, True, 0.0),
        "current_gas": 1.0,
        "gas_reserve": 0.1,
        "carry_physically_validated": False,
        "safe_route": True,
    }
    value.update(overrides)
    return RuntimeSnapshot(**value)


def attack_option(**overrides):
    value = {
        "id": "attack_threat",
        "status": "experimental",
        "travel_eta": 0.4,
        "eta_uncertainty": 0.1,
        "gas_cost": 0.05,
        "risk": 0.15,
        "required_commands": ("Human.Attack",),
        "requires_gas": True,
    }
    value.update(overrides)
    return Intervention(**value)


def evade_option(**overrides):
    value = {
        "id": "evade_cover",
        "status": "experimental",
        "travel_eta": 0.5,
        "eta_uncertainty": 0.1,
        "gas_cost": 0.0,
        "risk": 0.1,
        "required_commands": ("Human.Move",),
        "requires_clearance": True,
    }
    value.update(overrides)
    return Intervention(**value)


def opportunity(options=None, **overrides):
    value = {
        "opportunity_id": "rescue-1",
        "victim_id": "human-victim-1",
        "threat_id": "titan-1",
        "evidence": "confirmed_grab",
        "uncertainty": 0.1,
        "observed_at": 1.0,
        "reaction_window": 5.0,
        "expires_at": 8.0,
        "interventions": tuple(options or (attack_option(), evade_option())),
        "travel_feasible": True,
        "gas_budget": 0.8,
        "safety_budget": 0.5,
    }
    value.update(overrides)
    return RescueOpportunity(**value)


class CompositionContractTests(unittest.TestCase):
    def test_profile_has_independent_groups_and_unknown_loadout_default(self):
        profile = validate_profile(default_profile("cadet-test"))
        self.assertIn("rescue_priority", profile["personality"])
        self.assertEqual(profile["loadout"], {
            "weapon": "unknown", "special": "unknown", "observed": False, "source": "unknown"})
        self.assertNotEqual(profile_hash(profile), profile_hash({**profile, "id": "different"}))

    def test_invalid_or_missing_profile_values_fail_closed(self):
        profile = default_profile()
        profile["personality"]["rescue_priority"] = 1.1
        with self.assertRaises(ContractError):
            validate_profile(profile)
        profile = default_profile()
        del profile["movement_style"]["ground_preference"]
        with self.assertRaises(ContractError):
            validate_profile(profile)
        profile = default_profile()
        profile["loadout"] = {"weapon": "Blade", "special": "Carry", "observed": False, "source": "unknown"}
        with self.assertRaises(ContractError):
            validate_profile(profile)

    def test_schema_zero_migration_preserves_personality_but_not_guessed_special(self):
        migrated = migrate_profile({"schema_version": 0, "name": "legacy", "rescue_priority": 0.9,
                                    "risk_tolerance": 0.2, "aggression": 0.6})
        self.assertEqual(migrated["id"], "legacy")
        self.assertEqual(migrated["personality"]["rescue_priority"], 0.9)
        self.assertEqual(migrated["personality"]["risk_tolerance"], 0.2)
        self.assertEqual(migrated["loadout"]["special"], "unknown")

    def test_cooldown_and_live_equipment_change_gate_special_mid_run(self):
        carry = maneuver("carry_extract", required_special="Carry")
        state = eligible_state(special_ready=False)
        result = check_maneuver_eligibility(carry, state)
        self.assertFalse(result["eligible"])
        self.assertIn("special_readiness_not_confirmed", result["reasons"])
        changed = eligible_state(loadout={"weapon": "Blade", "special": "None", "observed": True, "source": "live_api"})
        result = check_maneuver_eligibility(carry, changed)
        self.assertIn("special_mismatch", result["reasons"])

    def test_carry_is_hard_gated_even_if_a_catalog_entry_is_mislabeled_validated(self):
        carry = maneuver("carry_extract", required_special="Carry")
        state = eligible_state(carry_physically_validated=False)
        result = check_maneuver_eligibility(carry, state)
        self.assertFalse(result["eligible"])
        self.assertIn("carry_not_physically_validated", result["reasons"])

    def test_definition_only_never_dispatches_and_experimental_is_probe_only(self):
        defined = maneuver("two_hook", "definition_only")
        experimental = maneuver("dash", "experimental")
        result = rank_maneuvers(default_profile(), [defined, experimental], eligible_state())
        self.assertIsNone(result["selected_id"])
        probe = rank_maneuvers(default_profile(), [experimental], eligible_state(), allow_experimental=True)
        self.assertEqual(probe["selected_id"], "dash")

    def test_no_viable_option_holds_and_only_safe_option_wins(self):
        unsafe = maneuver("unsupported", required_commands=["Human.Teleport"])
        result = rank_maneuvers(default_profile(), [unsafe], eligible_state())
        self.assertEqual(result["status"], "hold_no_eligible_maneuver")
        safe = maneuver("single_safe", utility={"progress": -1.0})
        result = rank_maneuvers(default_profile(), [unsafe, safe], eligible_state())
        self.assertEqual(result["selected_id"], "single_safe")

    def test_rescue_priority_changes_preference_but_safety_gate_remains_hard(self):
        rescue = maneuver("rescue", utility={"progress": 0.2, "combat": 0.0, "rescue": 1.0,
                                              "risk": 0.1, "gas_cost": 0.0})
        attack = maneuver("attack", utility={"progress": 0.2, "combat": 1.0, "rescue": 0.0,
                                              "risk": 0.1, "gas_cost": 0.0})
        combat_profile = default_profile()
        combat_profile["personality"]["rescue_priority"] = 0.0
        combat_profile["personality"]["aggression"] = 1.0
        support_profile = default_profile()
        support_profile["personality"]["rescue_priority"] = 1.0
        self.assertEqual(rank_maneuvers(combat_profile, [rescue, attack], eligible_state())["selected_id"], "attack")
        self.assertEqual(rank_maneuvers(support_profile, [rescue, attack], eligible_state())["selected_id"], "rescue")
        unsafe_rescue = copy.deepcopy(rescue)
        unsafe_rescue["utility"]["risk"] = 1.0
        result = rank_maneuvers(support_profile, [unsafe_rescue], eligible_state())
        self.assertIsNone(result["selected_id"])

    def test_low_gas_blocks_costly_maneuver_without_excluding_the_only_safe_fallback(self):
        costly = maneuver("costly", min_gas_fraction=0.3)
        fallback = maneuver("safe_fallback")
        result = rank_maneuvers(default_profile(), [costly, fallback], eligible_state(gas_fraction=0.1))
        self.assertEqual(result["selected_id"], "safe_fallback")
        rejected = next(x for x in result["ranked"] if x["id"] == "costly")
        self.assertIn("gas_below_maneuver_minimum", rejected["reasons"])

    def test_seeded_replays_repeat_and_novelty_is_soft(self):
        options = [maneuver("left"), maneuver("right")]
        first = rank_maneuvers(default_profile(), options, eligible_state(), seed=17, decision_index=3)
        again = rank_maneuvers(default_profile(), options, eligible_state(), seed=17, decision_index=3)
        self.assertEqual(first["selected_id"], again["selected_id"])
        repeated = rank_maneuvers(default_profile(), [maneuver("only")], eligible_state(),
                                  recent_ids=["only"], seed=17)
        self.assertEqual(repeated["selected_id"], "only")
        row = repeated["ranked"][0]
        self.assertGreater(row["novelty_penalty"], 0.0)
        self.assertLessEqual(row["novelty_penalty"], 0.15)


class RescueContractTests(unittest.TestCase):
    def test_confirmed_grab_can_interrupt_but_experimental_plan_cannot_dispatch(self):
        memory = PlannerMemory(current_maneuver="tether_arc", current_target_id="titan-old")
        combat_profile = default_profile()
        combat_profile["personality"]["rescue_priority"] = 0.0
        combat_profile["personality"]["aggression"] = 1.0
        intervention = attack_option(risk=0.05, gas_cost=0.0)
        plan, memory = plan_rescue(combat_profile, opportunity((intervention,)), "cadet-1", 1.2, runtime(), memory)
        self.assertEqual(plan.action, "interrupt_for_rescue")
        self.assertEqual(plan.selected_intervention, "attack_threat")
        self.assertFalse(plan.dispatchable)
        self.assertEqual(plan.interrupted_maneuver, "tether_arc")
        self.assertEqual(memory.suspended_maneuver, "tether_arc")

    def test_credible_imminent_grab_uses_safe_feasible_cover(self):
        profile = default_profile()
        profile["personality"]["rescue_priority"] = 0.85
        opp = opportunity(evidence="credible_imminent_impact", uncertainty=0.2,
                          interventions=(evade_option(),))
        plan, _ = plan_rescue(profile, opp, "cadet-1", 2.0, runtime())
        self.assertEqual(plan.action, "select_rescue")
        self.assertEqual(plan.selected_intervention, "evade_cover")

    def test_impossible_eta_or_unsafe_risk_is_rejected(self):
        too_late = attack_option(travel_eta=9.0)
        risky = evade_option(risk=0.9)
        opp = opportunity((too_late, risky))
        plan, _ = plan_rescue(default_profile(), opp, "cadet-1", 1.1, runtime())
        self.assertEqual(plan.action, "continue_current")
        reasons = {reason for row in plan.ranked for reason in row["reasons"]}
        self.assertIn("travel_exceeds_reaction_window", reasons)
        self.assertTrue({"safety_budget_unknown_or_exceeded", "profile_risk_limit_exceeded"} & reasons)

    def test_reservation_prevents_two_rescuers_claiming_the_same_victim(self):
        opp = opportunity(reservation_state="reserved", reservation_owner="cadet-2", reservation_expires_at=5.0)
        plan, _ = plan_rescue(default_profile(), opp, "cadet-1", 2.0, runtime())
        self.assertEqual(plan.action, "continue_current")
        self.assertIn("reserved_by:cadet-2", plan.reasons)

    def test_low_gas_blocks_intervention_and_unknown_cost_fails_closed(self):
        only_attack = opportunity((attack_option(),), gas_budget=0.05)
        plan, _ = plan_rescue(default_profile(), only_attack, "cadet-1", 1.2,
                              runtime(current_gas=0.1, gas_reserve=0.1))
        self.assertEqual(plan.action, "continue_current")
        unknown = opportunity((attack_option(gas_cost=None),))
        plan, _ = plan_rescue(default_profile(), unknown, "cadet-1", 1.2, runtime())
        self.assertIn("gas_cost_or_budget_unknown", plan.ranked[0]["reasons"])

    def test_unsupported_carry_and_unready_special_stay_gated(self):
        carry = Intervention("carry", "definition_only", 0.2, 0.1, 0.0, 0.1,
                             ("Human.ActivateSpecial",), "Carry", None,
                             requires_carry_validation=True)
        opp = opportunity((carry,))
        plan, _ = plan_rescue(default_profile(), opp, "cadet-1", 1.2,
                              runtime(equipment=EquipmentSnapshot("Blade", "Carry", True, True, 0.0)))
        self.assertEqual(plan.action, "continue_current")
        self.assertIn("definition_only_never_dispatch", plan.ranked[0]["reasons"])
        self.assertIn("carry_not_physically_validated", plan.ranked[0]["reasons"])
        distract = Intervention("distract", "experimental", 0.2, 0.1, 0.0, 0.1,
                                ("Human.ActivateSpecial",), "Distract")
        opp = opportunity((distract,))
        plan, _ = plan_rescue(default_profile(), opp, "cadet-1", 1.2,
                              runtime(equipment=EquipmentSnapshot("Blade", "Distract", True, False, 0.8)))
        self.assertIn("special_readiness_or_cooldown_unconfirmed", plan.ranked[0]["reasons"])

    def test_changed_opportunity_retargets_without_reinterrupting_and_commitment_prevents_thrashing(self):
        memory = PlannerMemory(current_maneuver="orbit", current_target_id="titan-1")
        first = opportunity()
        plan, memory = plan_rescue(default_profile(), first, "cadet-1", 1.2, runtime(), memory)
        self.assertEqual(plan.action, "interrupt_for_rescue")
        plan, memory = plan_rescue(default_profile(), first, "cadet-1", 1.5, runtime(), memory)
        self.assertEqual(plan.action, "continue_rescue")
        self.assertEqual(memory.suspended_maneuver, "orbit")
        second = opportunity(opportunity_id="rescue-2", victim_id="human-victim-2", threat_id="titan-2")
        plan, memory = plan_rescue(default_profile(), second, "cadet-1", 2.1, runtime(), memory)
        self.assertEqual(plan.action, "retarget_rescue")
        self.assertEqual(memory.suspended_maneuver, "orbit")

    def test_interruption_recovery_requires_revalidation_and_does_not_mark_survival_as_rescue(self):
        memory = PlannerMemory(current_maneuver="nape_intercept", current_target_id="titan-1")
        opp = opportunity()
        _, memory = plan_rescue(default_profile(), opp, "cadet-1", 1.2, runtime(), memory)
        survivor_only = MeasuredOutcome(intervention_started=True, victim_alive_after_window=True,
                                        causal_link=None, confidence=0.9)
        self.assertEqual(classify_rescue_outcome(survivor_only), "victim_survived_unattributed")
        result = finish_rescue(memory, opp.opportunity_id, survivor_only, resume_target_still_valid=True)
        self.assertEqual(result["resume_candidate"], "nape_intercept")
        self.assertTrue(result["requires_revalidation"])
        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["outcome"], "victim_survived_unattributed")

    def test_causal_rescue_requires_grab_clear_living_victim_and_linked_evidence(self):
        confirmed = MeasuredOutcome(True, True, True, causal_link=True, confidence=0.9)
        survivor_only = MeasuredOutcome(True, False, True, causal_link=None, confidence=0.9)
        self.assertEqual(classify_rescue_outcome(confirmed), "rescue_confirmed")
        self.assertEqual(classify_rescue_outcome(survivor_only), "victim_survived_unattributed")

    def test_preventing_an_imminent_threat_can_be_causally_confirmed(self):
        prevented = MeasuredOutcome(intervention_started=True, victim_alive_after_window=True,
                                    causal_link=True, confidence=0.9, threat_interrupted=True)
        uncertain = MeasuredOutcome(intervention_started=True, victim_alive_after_window=True,
                                    causal_link=None, confidence=0.9, threat_interrupted=True)
        self.assertEqual(classify_rescue_outcome(prevented), "rescue_confirmed")
        self.assertEqual(classify_rescue_outcome(uncertain),
                         "threat_interrupted_survival_or_causality_unconfirmed")

    def test_expired_opportunity_does_not_interrupt_current_maneuver(self):
        memory = PlannerMemory(current_maneuver="orbit")
        plan, _ = plan_rescue(default_profile(), opportunity(expires_at=2.0), "cadet-1", 2.0, runtime(), memory)
        self.assertEqual(plan.action, "continue_current")
        self.assertEqual(memory.current_maneuver, "orbit")


if __name__ == "__main__":
    unittest.main()
