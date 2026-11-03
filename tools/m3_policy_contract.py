"""Offline M3 composition and rescue contract.

This is a typed reference for data validation and deterministic mocked planning.
It is not the AICadetsWaveCadet policy, it cannot call AoTTG2, and its choices
must not be wired to a game executor until the separate physical gates pass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any


PROFILE_SCHEMA_VERSION = 1
PROFILE_KEYS = {"schema_version", "id", "skill", "movement_style", "personality", "loadout"}
SKILL_DEFAULTS = {
    "perception": 0.5, "tracking": 0.5, "timing": 0.5,
    "reaction": 0.5, "precision": 0.5, "recovery": 0.5,
}
STYLE_DEFAULTS = {
    "arc_preference": 0.5, "ground_preference": 0.5,
    "left_right_bias": 0.0, "landing_preference": 0.5,
}
PERSONALITY_DEFAULTS = {
    "rescue_priority": 0.5, "aggression": 0.5, "risk_tolerance": 0.5,
    "cooperation": 0.5, "persistence": 0.5, "gas_conservation": 0.5,
    "exploration": 0.5,
}
WEAPONS = {"Blade", "AHSS", "Thunderspear", "unknown"}
SPECIALS = {
    "Potato", "Escape", "Dance", "Distract", "Smell", "Supply", "SmokeBomb",
    "Carry", "Switchback", "Confuse", "DownStrike", "Spin1", "Spin2", "Spin3",
    "BladeThrow", "AHSSTwinShot", "Stock", "None", "unknown",
}


class ContractError(ValueError):
    pass


def _finite(value: Any, label: str, minimum: float | None = None,
            maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ContractError(f"{label} must be a finite number")
    value = float(value)
    if minimum is not None and value < minimum:
        raise ContractError(f"{label} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ContractError(f"{label} must be <= {maximum}")
    return value


def default_profile(profile_id: str = "default") -> dict[str, Any]:
    """Return explicit neutral values and an unknown, never guessed, loadout."""
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "id": profile_id,
        "skill": dict(SKILL_DEFAULTS),
        "movement_style": dict(STYLE_DEFAULTS),
        "personality": dict(PERSONALITY_DEFAULTS),
        "loadout": {"weapon": "unknown", "special": "unknown", "observed": False, "source": "unknown"},
    }


def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, dict):
        raise ContractError("profile must be an object")
    if set(profile) != PROFILE_KEYS:
        missing = sorted(PROFILE_KEYS - set(profile))
        extra = sorted(set(profile) - PROFILE_KEYS)
        raise ContractError(f"profile keys mismatch; missing={missing}, extra={extra}")
    if (isinstance(profile["schema_version"], bool)
            or not isinstance(profile["schema_version"], int)
            or profile["schema_version"] != PROFILE_SCHEMA_VERSION):
        raise ContractError(f"unsupported profile schema_version {profile['schema_version']!r}")
    if not isinstance(profile["id"], str) or not profile["id"].strip():
        raise ContractError("profile.id must be a non-empty string")
    for group_name, defaults in (("skill", SKILL_DEFAULTS),
                                 ("movement_style", STYLE_DEFAULTS),
                                 ("personality", PERSONALITY_DEFAULTS)):
        group = profile[group_name]
        if not isinstance(group, dict) or set(group) != set(defaults):
            missing = sorted(set(defaults) - set(group)) if isinstance(group, dict) else sorted(defaults)
            extra = sorted(set(group) - set(defaults)) if isinstance(group, dict) else []
            raise ContractError(f"{group_name} keys mismatch; missing={missing}, extra={extra}")
        for name, value in group.items():
            low, high = (-1.0, 1.0) if group_name == "movement_style" and name == "left_right_bias" else (0.0, 1.0)
            _finite(value, f"{group_name}.{name}", low, high)
    loadout = profile["loadout"]
    if not isinstance(loadout, dict) or set(loadout) != {"weapon", "special", "observed", "source"}:
        raise ContractError("loadout requires exactly weapon, special, observed and source")
    if (not isinstance(loadout["weapon"], str) or loadout["weapon"] not in WEAPONS
            or not isinstance(loadout["special"], str) or loadout["special"] not in SPECIALS):
        raise ContractError("loadout contains an unknown weapon or special label")
    if not isinstance(loadout["observed"], bool):
        raise ContractError("loadout.observed must be boolean")
    if not isinstance(loadout["source"], str) or loadout["source"] not in {"live_api", "unknown"}:
        raise ContractError("loadout.source must be live_api or unknown")
    if loadout["observed"] and loadout["source"] != "live_api":
        raise ContractError("observed equipment must identify live_api as its source")
    if not loadout["observed"] and (loadout["weapon"] != "unknown" or loadout["special"] != "unknown"):
        raise ContractError("unobserved loadout values must remain unknown")
    if loadout["observed"] and (loadout["weapon"] == "unknown" or loadout["special"] == "unknown"):
        raise ContractError("observed loadout cannot silently omit weapon or special")
    return profile


def migrate_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Migrate legacy schema 0 preferences; preserve no preset/equipment guesses."""
    if not isinstance(raw, dict) or raw.get("schema_version") != 0:
        raise ContractError("only legacy profile schema_version 0 can be migrated")
    profile = default_profile(raw.get("id", raw.get("name", "migrated")))
    legacy_personality = profile["personality"]
    for key in legacy_personality:
        if key in raw:
            legacy_personality[key] = raw[key]
    return validate_profile(profile)


def profile_hash(profile: dict[str, Any]) -> str:
    validate_profile(profile)
    payload = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def check_maneuver_eligibility(maneuver: dict[str, Any], state: dict[str, Any],
                               allow_experimental: bool = False) -> dict[str, Any]:
    """Hard capability/state filter. It never executes or promotes a maneuver."""
    reasons: list[str] = []
    status = maneuver.get("status")
    if status == "definition_only":
        reasons.append("definition_only_never_dispatch")
    elif status == "experimental" and not allow_experimental:
        reasons.append("experimental_probe_only")
    elif status not in {"experimental", "validated"}:
        reasons.append("unknown_implementation_status")
    if state.get("alive") is not True:
        reasons.append("alive_state_not_confirmed")
    commands = state.get("available_commands")
    if not isinstance(commands, (list, tuple, set, frozenset)):
        commands = None
    for command in maneuver.get("required_commands", []):
        if commands is None:
            reasons.append(f"command_support_unknown:{command}")
        elif command not in commands:
            reasons.append(f"command_unavailable:{command}")
    for requirement in maneuver.get("required_state", []):
        key = {"grounded": "grounded", "CanDodge": "can_dodge", "alive": "alive"}.get(requirement)
        if key is None:
            continue
        if state.get(key) is not True:
            reasons.append(f"state_not_confirmed:{requirement}")
    if maneuver.get("requires_clearance") and state.get("clearance") is not True:
        reasons.append("clearance_not_confirmed")
    utility = maneuver.get("utility", {})
    maneuver_risk = maneuver.get("safety_risk", utility.get("risk"))
    if maneuver_risk is not None:
        maneuver_risk = _finite(maneuver_risk, "maneuver.safety_risk", 0.0, 1.0)
        safety_budget = state.get("safety_budget")
        if maneuver_risk > 0.0 and (safety_budget is None or maneuver_risk > _finite(safety_budget, "state.safety_budget", 0.0, 1.0)):
            reasons.append("safety_budget_unknown_or_exceeded")
    min_gas = maneuver.get("min_gas_fraction")
    if min_gas is not None:
        gas_fraction = state.get("gas_fraction")
        if gas_fraction is None:
            reasons.append("gas_fraction_unknown")
        elif _finite(gas_fraction, "state.gas_fraction", 0.0, 1.0) < _finite(min_gas, "min_gas_fraction", 0.0, 1.0):
            reasons.append("gas_below_maneuver_minimum")
    required_special = maneuver.get("required_special")
    equipment = state.get("loadout")
    if required_special:
        if not isinstance(equipment, dict) or equipment.get("observed") is not True:
            reasons.append("special_equipment_unknown")
        elif equipment.get("special") != required_special:
            reasons.append("special_mismatch")
        if state.get("special_ready") is not True:
            reasons.append("special_readiness_not_confirmed")
        if required_special == "Carry" and state.get("carry_physically_validated") is not True:
            reasons.append("carry_not_physically_validated")
    required_weapon = maneuver.get("required_weapon")
    if required_weapon:
        if not isinstance(equipment, dict) or equipment.get("observed") is not True:
            reasons.append("weapon_equipment_unknown")
        elif equipment.get("weapon") != required_weapon:
            reasons.append("weapon_mismatch")
    return {"eligible": not reasons, "reasons": reasons}


def rank_maneuvers(profile: dict[str, Any], maneuvers: list[dict[str, Any]],
                   state: dict[str, Any], recent_ids: list[str] | None = None,
                   seed: int = 0, decision_index: int = 0,
                   allow_experimental: bool = False) -> dict[str, Any]:
    """Deterministic soft ranking after hard gates; no game dispatch is performed."""
    validate_profile(profile)
    recent_ids = recent_ids or []
    ranked = []
    seen = set()
    p = profile["personality"]
    style = profile["movement_style"]
    for maneuver in maneuvers:
        action_id = maneuver.get("id")
        if not isinstance(action_id, str) or not action_id or action_id in seen:
            raise ContractError("maneuvers require unique stable ids")
        seen.add(action_id)
        check = check_maneuver_eligibility(maneuver, state, allow_experimental)
        item = {"id": action_id, "eligible": check["eligible"], "reasons": check["reasons"], "score": None}
        if not check["eligible"]:
            ranked.append(item)
            continue
        utility = maneuver.get("utility", {})
        if not isinstance(utility, dict):
            raise ContractError(f"{action_id}.utility must be an object")
        for key in ("progress", "combat", "rescue", "risk", "gas_cost", "arc_fit", "ground_fit"):
            if key not in utility:
                continue
            low, high = (0.0, 1.0) if key in {"combat", "rescue", "risk", "arc_fit", "ground_fit"} else (None, None)
            _finite(utility[key], f"{action_id}.utility.{key}", low, high)
        base = float(utility.get("progress", 0.0))
        base += float(utility.get("combat", 0.0)) * (0.5 + p["aggression"]) * 3.0
        base += float(utility.get("rescue", 0.0)) * p["rescue_priority"] * 4.0
        base += float(utility.get("arc_fit", 0.0)) * style["arc_preference"]
        base += float(utility.get("ground_fit", 0.0)) * style["ground_preference"]
        base -= float(utility.get("risk", 0.0)) * (1.0 - p["risk_tolerance"]) * 2.0
        base -= float(utility.get("gas_cost", 0.0)) * p["gas_conservation"]
        recent_index = next((i for i, value in enumerate(reversed(recent_ids[-4:])) if value == action_id), None)
        novelty_penalty = 0.15 * (1.0 - recent_index / 4.0) if recent_index is not None else 0.0
        score = base - max(0.0, base) * novelty_penalty
        tie = hashlib.sha256(f"{seed}:{decision_index}:{action_id}".encode("utf-8")).hexdigest()
        item.update({"score": score, "base_score": base, "novelty_penalty": novelty_penalty, "tie_break": tie})
        ranked.append(item)
    eligible = [item for item in ranked if item["eligible"]]
    eligible.sort(key=lambda item: (-item["score"], item["tie_break"], item["id"]))
    rejected = [item for item in ranked if not item["eligible"]]
    return {"selected_id": eligible[0]["id"] if eligible else None,
            "ranked": eligible + rejected,
            "status": "selected" if eligible else "hold_no_eligible_maneuver",
            "randomness": "none; tie-break is a stable hash of saved seed, decision index and id"}


RESCUE_EVIDENCE = {"confirmed_grab", "credible_imminent_impact", "post_intervention"}
OUTCOME_STATES = {"opportunity_detected", "rescue_selected", "rescue_intervention_started",
                  "grab_state_cleared", "threat_interrupted", "victim_alive_after_window",
                  "carry_started", "carry_ended", "rescue_confirmed", "failed", "unknown"}


@dataclass(frozen=True)
class MeasuredOutcome:
    intervention_started: bool | None = None
    grab_state_cleared: bool | None = None
    victim_alive_after_window: bool | None = None
    carry_started: bool | None = None
    carry_ended: bool | None = None
    causal_link: bool | None = None
    failed: bool | None = None
    confidence: float = 0.0
    threat_interrupted: bool | None = None

    def __post_init__(self):
        _finite(self.confidence, "outcome.confidence", 0.0, 1.0)
        for name in ("intervention_started", "grab_state_cleared", "victim_alive_after_window",
                     "carry_started", "carry_ended", "causal_link", "failed", "threat_interrupted"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise ContractError(f"outcome.{name} must be boolean or unknown")


@dataclass(frozen=True)
class Intervention:
    id: str
    status: str
    travel_eta: float
    eta_uncertainty: float
    gas_cost: float | None
    risk: float
    required_commands: tuple[str, ...] = ()
    required_special: str | None = None
    required_weapon: str | None = None
    requires_gas: bool = False
    requires_clearance: bool = False
    requires_carry_validation: bool = False

    def __post_init__(self):
        if not self.id:
            raise ContractError("intervention id is required")
        if self.status not in {"definition_only", "experimental", "validated"}:
            raise ContractError(f"invalid intervention status for {self.id}")
        _finite(self.travel_eta, f"{self.id}.travel_eta", 0.0)
        _finite(self.eta_uncertainty, f"{self.id}.eta_uncertainty", 0.0)
        _finite(self.risk, f"{self.id}.risk", 0.0, 1.0)
        if self.gas_cost is not None:
            _finite(self.gas_cost, f"{self.id}.gas_cost", 0.0)
        if not isinstance(self.required_commands, tuple) or any(not isinstance(x, str) for x in self.required_commands):
            raise ContractError(f"{self.id}.required_commands must be a tuple of strings")


@dataclass(frozen=True)
class RescueOpportunity:
    opportunity_id: str
    victim_id: str
    threat_id: str | None
    evidence: str
    uncertainty: float
    observed_at: float
    reaction_window: float
    expires_at: float
    interventions: tuple[Intervention, ...]
    travel_feasible: bool | None
    gas_budget: float | None
    safety_budget: float | None
    reservation_state: str = "unclaimed"
    reservation_owner: str | None = None
    reservation_expires_at: float | None = None
    measured_outcome: MeasuredOutcome = field(default_factory=MeasuredOutcome)

    def __post_init__(self):
        if not self.opportunity_id or not self.victim_id:
            raise ContractError("opportunity and victim identities are required")
        if self.evidence not in RESCUE_EVIDENCE:
            raise ContractError("unsupported rescue evidence label")
        _finite(self.uncertainty, "opportunity.uncertainty", 0.0, 1.0)
        _finite(self.observed_at, "opportunity.observed_at", 0.0)
        _finite(self.reaction_window, "opportunity.reaction_window", 0.001)
        _finite(self.expires_at, "opportunity.expires_at", self.observed_at)
        if self.expires_at <= self.observed_at:
            raise ContractError("opportunity expires_at must be later than observed_at")
        if not isinstance(self.interventions, tuple) or any(not isinstance(x, Intervention) for x in self.interventions):
            raise ContractError("interventions must be a tuple of Intervention values")
        if len({x.id for x in self.interventions}) != len(self.interventions):
            raise ContractError("intervention ids must be unique within an opportunity")
        if self.travel_feasible is not None and not isinstance(self.travel_feasible, bool):
            raise ContractError("travel_feasible must be true, false or unknown")
        if self.gas_budget is not None:
            _finite(self.gas_budget, "opportunity.gas_budget", 0.0)
        if self.safety_budget is not None:
            _finite(self.safety_budget, "opportunity.safety_budget", 0.0, 1.0)
        if self.reservation_state not in {"unclaimed", "reserved", "released"}:
            raise ContractError("invalid reservation_state")
        if self.reservation_state == "reserved" and not self.reservation_owner:
            raise ContractError("reserved opportunity requires reservation_owner")
        if self.reservation_expires_at is not None:
            _finite(self.reservation_expires_at, "opportunity.reservation_expires_at", 0.0)


@dataclass(frozen=True)
class EquipmentSnapshot:
    weapon: str = "unknown"
    special: str = "unknown"
    observed: bool = False
    special_ready: bool | None = None
    cooldown_ratio: float | None = None

    def __post_init__(self):
        if not isinstance(self.observed, bool):
            raise ContractError("equipment.observed must be boolean")
        if self.observed and (self.weapon not in WEAPONS - {"unknown"} or self.special not in SPECIALS - {"unknown"}):
            raise ContractError("observed equipment needs a known weapon and special")
        if not self.observed and (self.weapon != "unknown" or self.special != "unknown"):
            raise ContractError("unobserved equipment values must remain unknown")
        if self.special_ready is not None and not isinstance(self.special_ready, bool):
            raise ContractError("special_ready must be boolean or unknown")
        if self.cooldown_ratio is not None:
            _finite(self.cooldown_ratio, "equipment.cooldown_ratio", 0.0, 1.0)


@dataclass(frozen=True)
class RuntimeSnapshot:
    alive: bool
    available_commands: tuple[str, ...] | None
    equipment: EquipmentSnapshot = field(default_factory=EquipmentSnapshot)
    current_gas: float | None = None
    gas_reserve: float | None = None
    carry_physically_validated: bool = False
    safe_route: bool | None = None

    def __post_init__(self):
        if not isinstance(self.alive, bool):
            raise ContractError("runtime.alive must be boolean")
        if self.available_commands is not None and not isinstance(self.available_commands, tuple):
            raise ContractError("runtime.available_commands must be a tuple or unknown")
        if self.current_gas is not None:
            _finite(self.current_gas, "runtime.current_gas", 0.0)
        if self.gas_reserve is not None:
            _finite(self.gas_reserve, "runtime.gas_reserve", 0.0)
        if not isinstance(self.carry_physically_validated, bool):
            raise ContractError("carry_physically_validated must be boolean")


@dataclass
class PlannerMemory:
    current_maneuver: str | None = None
    current_target_id: str | None = None
    suspended_maneuver: str | None = None
    suspended_target_id: str | None = None
    active_opportunity_id: str | None = None
    active_intervention_id: str | None = None
    active_dispatchable: bool = False
    commit_until: float = 0.0
    last_outcome: str = "unknown"


@dataclass(frozen=True)
class RescuePlan:
    action: str
    selected_intervention: str | None
    dispatchable: bool
    interrupted_maneuver: str | None
    resume_candidate: str | None
    ranked: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]


def _intervention_rejection(option: Intervention, opportunity: RescueOpportunity,
                            profile: dict[str, Any], actor_id: str, now: float,
                            runtime: RuntimeSnapshot) -> list[str]:
    reasons: list[str] = []
    remaining = opportunity.reaction_window - max(0.0, now - opportunity.observed_at)
    if option.status == "definition_only":
        reasons.append("definition_only_never_dispatch")
    if runtime.available_commands is None:
        if option.required_commands:
            reasons.append("command_support_unknown")
    else:
        for command in option.required_commands:
            if command not in runtime.available_commands:
                reasons.append(f"command_unavailable:{command}")
    if option.required_special:
        if not runtime.equipment.observed:
            reasons.append("special_equipment_unknown")
        elif runtime.equipment.special != option.required_special:
            reasons.append("special_mismatch")
        if runtime.equipment.special_ready is not True:
            reasons.append("special_readiness_or_cooldown_unconfirmed")
    if option.required_weapon:
        if not runtime.equipment.observed:
            reasons.append("weapon_equipment_unknown")
        elif runtime.equipment.weapon != option.required_weapon:
            reasons.append("weapon_mismatch")
    if ((option.requires_carry_validation or option.required_special == "Carry")
            and not runtime.carry_physically_validated):
        reasons.append("carry_not_physically_validated")
    if option.requires_clearance and runtime.safe_route is not True:
        reasons.append("safe_clearance_not_confirmed")
    if option.travel_eta + option.eta_uncertainty >= remaining:
        reasons.append("travel_exceeds_reaction_window")
    if opportunity.safety_budget is None or option.risk > opportunity.safety_budget:
        reasons.append("safety_budget_unknown_or_exceeded")
    profile_risk_limit = 0.15 + 0.65 * profile["personality"]["risk_tolerance"]
    if option.risk > profile_risk_limit:
        reasons.append("profile_risk_limit_exceeded")
    if option.requires_gas:
        if option.gas_cost is None or opportunity.gas_budget is None or runtime.current_gas is None:
            reasons.append("gas_cost_or_budget_unknown")
        else:
            if option.gas_cost > opportunity.gas_budget:
                reasons.append("opportunity_gas_budget_exceeded")
            if runtime.gas_reserve is not None and runtime.current_gas - option.gas_cost < runtime.gas_reserve:
                reasons.append("survival_gas_reserve_would_be_breached")
    return reasons


def plan_rescue(profile: dict[str, Any], opportunity: RescueOpportunity, actor_id: str,
                now: float, runtime: RuntimeSnapshot, memory: PlannerMemory | None = None) -> tuple[RescuePlan, PlannerMemory]:
    """Produce an offline intent proposal; experimental actions stay non-dispatchable."""
    validate_profile(profile)
    _finite(now, "now", 0.0)
    memory = memory or PlannerMemory()
    reasons: list[str] = []
    remaining = opportunity.reaction_window - max(0.0, now - opportunity.observed_at)
    if now >= opportunity.expires_at or remaining <= 0:
        return RescuePlan("continue_current", None, False, None, memory.current_maneuver, (), ("opportunity_expired",)), memory
    if opportunity.reservation_state == "reserved":
        owner_is_self = opportunity.reservation_owner == actor_id
        claim_expired = opportunity.reservation_expires_at is not None and opportunity.reservation_expires_at <= now
        if not owner_is_self and not claim_expired:
            return RescuePlan("continue_current", None, False, None, memory.current_maneuver, (),
                              (f"reserved_by:{opportunity.reservation_owner}",)), memory
    if opportunity.travel_feasible is not True:
        why = "travel_infeasible" if opportunity.travel_feasible is False else "travel_feasibility_unknown"
        return RescuePlan("continue_current", None, False, None, memory.current_maneuver, (), (why,)), memory
    if not runtime.alive:
        return RescuePlan("stop", None, False, None, None, (), ("rescuer_not_alive",)), memory
    if opportunity.evidence == "credible_imminent_impact" and opportunity.uncertainty > 0.5:
        return RescuePlan("continue_current", None, False, None, memory.current_maneuver, (),
                          ("imminent_threat_uncertainty_too_high",)), memory
    if opportunity.evidence == "post_intervention" and opportunity.measured_outcome.intervention_started is not True:
        return RescuePlan("continue_current", None, False, None, memory.current_maneuver, (),
                          ("post_intervention_evidence_without_observed_attempt",)), memory
    if memory.active_opportunity_id == opportunity.opportunity_id and now < memory.commit_until:
        return RescuePlan("continue_rescue", memory.active_intervention_id, memory.active_dispatchable,
                          None, memory.suspended_maneuver, (), ("bounded_rescue_commitment",)), memory

    ranked = []
    for option in opportunity.interventions:
        option_reasons = _intervention_rejection(option, opportunity, profile, actor_id, now, runtime)
        item = {"id": option.id, "status": option.status, "eligible": not option_reasons,
                "reasons": option_reasons, "score": None, "dispatchable": option.status == "validated"}
        if not option_reasons and option.status != "definition_only":
            urgency = max(0.0, min(1.0, 1.0 - remaining / opportunity.reaction_window))
            confidence = 1.0 - opportunity.uncertainty
            rp = profile["personality"]["rescue_priority"]
            risk_tolerance = profile["personality"]["risk_tolerance"]
            gas_conservation = profile["personality"]["gas_conservation"]
            cost = (option.gas_cost or 0.0) if option.gas_cost is not None else 0.0
            evidence_boost = 0.75 if opportunity.evidence == "confirmed_grab" else 0.2
            score = ((1.0 + 3.0 * rp) * urgency * confidence + evidence_boost
                     + 0.1 * profile["personality"]["cooperation"]
                     - option.travel_eta / opportunity.reaction_window
                     - option.risk * (1.0 - risk_tolerance) * 2.0
                     - cost * gas_conservation)
            item["score"] = score
            item["urgency"] = urgency
        ranked.append(item)
    eligible = [x for x in ranked if x["eligible"] and x["score"] is not None]
    eligible.sort(key=lambda x: (-x["score"], x["id"]))
    if not eligible or eligible[0]["score"] <= 0:
        return RescuePlan("continue_current", None, False, None, memory.current_maneuver,
                          tuple(ranked), ("no_positive_safe_intervention",)), memory

    chosen = eligible[0]
    interrupting = memory.active_opportunity_id is None and memory.current_maneuver is not None
    if interrupting and memory.suspended_maneuver is None:
        memory.suspended_maneuver = memory.current_maneuver
        memory.suspended_target_id = memory.current_target_id
    memory.current_maneuver = None
    previous_opportunity = memory.active_opportunity_id
    memory.active_opportunity_id = opportunity.opportunity_id
    memory.active_intervention_id = chosen["id"]
    memory.active_dispatchable = chosen["dispatchable"]
    memory.commit_until = min(opportunity.expires_at, now + 0.75)
    memory.current_target_id = opportunity.threat_id
    if interrupting:
        action = "interrupt_for_rescue"
    elif previous_opportunity and previous_opportunity != opportunity.opportunity_id:
        action = "retarget_rescue"
    elif previous_opportunity == opportunity.opportunity_id:
        action = "continue_rescue"
    else:
        action = "select_rescue"
    return RescuePlan(action, chosen["id"], chosen["dispatchable"],
                      memory.suspended_maneuver if interrupting else None,
                      memory.suspended_maneuver, tuple(ranked),
                      ("proposal_only_no_live_executor",) if not chosen["dispatchable"] else ()), memory


def classify_rescue_outcome(outcome: MeasuredOutcome) -> str:
    """Keep attempt, state transition, survivor observation and causal success separate."""
    if outcome.failed is True:
        return "failed"
    if outcome.intervention_started is not True:
        return "not_started"
    protective_change = outcome.grab_state_cleared is True or outcome.threat_interrupted is True
    if (protective_change and outcome.victim_alive_after_window is True
            and outcome.causal_link is True and outcome.confidence >= 0.75):
        return "rescue_confirmed"
    if outcome.grab_state_cleared is True:
        return "grab_cleared_survival_or_causality_unconfirmed"
    if outcome.threat_interrupted is True:
        return "threat_interrupted_survival_or_causality_unconfirmed"
    if outcome.victim_alive_after_window is True:
        return "victim_survived_unattributed"
    if outcome.carry_started is True and outcome.carry_ended is None:
        return "carry_started_release_unknown"
    return "outcome_unknown"


def finish_rescue(memory: PlannerMemory, opportunity_id: str, outcome: MeasuredOutcome,
                  resume_target_still_valid: bool) -> dict[str, Any]:
    if memory.active_opportunity_id != opportunity_id:
        raise ContractError("cannot finish a rescue opportunity that is not active")
    classification = classify_rescue_outcome(outcome)
    resume = memory.suspended_maneuver if resume_target_still_valid else None
    resume_target = memory.suspended_target_id if resume_target_still_valid else None
    memory.last_outcome = classification
    memory.current_maneuver = resume
    memory.current_target_id = resume_target
    memory.suspended_maneuver = None
    memory.suspended_target_id = None
    memory.active_opportunity_id = None
    memory.active_intervention_id = None
    memory.active_dispatchable = False
    memory.commit_until = 0.0
    return {"outcome": classification, "resume_candidate": resume,
            "resume_target_id": resume_target, "requires_revalidation": resume is not None,
            "execution_performed": False}
