"""Conservative, evidence-linked Titan death attribution for Flight v1 traces.

The adapter does not currently observe damage callbacks. This collector therefore
keeps sampled deaths, observed contacts, and sampled attack/AI state separate and
labels contact-based actor attribution as inference.
"""
from __future__ import annotations

from collections import defaultdict, deque
import math


CONTACT_WINDOW_SECONDS = 5.0
ATTACK_WINDOW_SECONDS = 1.5
DIRECT_EVENT_WINDOW_SECONDS = 1.0


def _fields(record: dict, nested_name: str) -> dict:
    nested = record.get(nested_name)
    merged = dict(nested) if isinstance(nested, dict) else {}
    merged.update({key: value for key, value in record.items() if key != nested_name})
    return merged


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _vector(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(_number(part) is None for part in value)):
        return None
    return tuple(float(part) for part in value)


def _distance(a, b):
    if a is None or b is None:
        return None
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _bool(value):
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
    return None


def _is_titan(entity_id: str, kind: str, entity_class: str) -> bool:
    return (kind.lower() in ("titan", "basetitan")
            or "titan" in entity_class.lower()
            or entity_id.lower().startswith("titan:"))


def _is_human(entity_id: str, kind: str, entity_class: str) -> bool:
    return (kind.lower() in ("human", "basehuman")
            or "characters.human" in entity_class.lower()
            or entity_id.lower().startswith("human:"))


def _dead_signals(sample: dict) -> list[str]:
    signals = []
    health = sample.get("health")
    if health is not None and health <= 0:
        signals.append("sampled_health_at_or_below_zero")
    if sample.get("dead_flag") is True:
        signals.append("sampled_dead_flag_true")
    if "dead" in sample.get("state", "").lower():
        signals.append("sampled_state_dead")
    animation = sample.get("animation", "").lower()
    if "die" in animation or "death" in animation:
        signals.append("sampled_death_animation")
    return signals


def _is_attack_sample(sample: dict) -> bool:
    return ("attack" in sample.get("state", "").lower()
            or "attack" in sample.get("animation", "").lower())


class KillAttributionCollector:
    """Collect observed Titan death transitions and rank candidate actor evidence."""

    def __init__(self):
        self.last_samples: dict[str, dict] = {}
        self.collisions_by_target = defaultdict(lambda: deque(maxlen=512))
        self.attack_samples = defaultdict(lambda: deque(maxlen=128))
        self.direct_events_by_target = defaultdict(lambda: deque(maxlen=128))
        self.deaths: list[dict] = []

    def observe_event(self, record: dict) -> None:
        event = str(record.get("event", "")).lower()
        evidence = str(record.get("evidence", "unknown")).lower()
        fields = _fields(record, "fields")
        actor = record.get("actor") or record.get("id")
        actor = str(actor) if actor not in (None, "") else None
        t = _number(record.get("t"))
        raw_step = record.get("step")
        step = raw_step if isinstance(raw_step, int) and not isinstance(raw_step, bool) else None

        if event in ("collision", "contact") and evidence == "observed" and actor:
            targets = []
            for key in ("other_character_id", "target_id", "victim_id", "other_entity_id"):
                value = fields.get(key)
                if isinstance(value, str) and value and value != actor:
                    targets.append(value)
            ids = record.get("ids")
            if isinstance(ids, list):
                targets.extend(str(value) for value in ids
                               if isinstance(value, str) and value and value != actor)
            for target in dict.fromkeys(targets):
                self.collisions_by_target[target].append({
                    "actor_id": actor,
                    "target_id": target,
                    "t": t,
                    "step": step,
                    "evidence": "observed",
                    "callback_source": fields.get("callback_source"),
                    "contact_count": fields.get("contact_count"),
                })

        if event in ("damage", "death") and evidence == "observed" and actor:
            targets = []
            for key in ("target_id", "victim_id", "other_character_id"):
                value = fields.get(key)
                if isinstance(value, str) and value and value != actor:
                    targets.append(value)
            record_id = record.get("id")
            if isinstance(record_id, str) and record_id and record_id != actor:
                targets.append(record_id)
            ids = record.get("ids")
            if isinstance(ids, list):
                targets.extend(str(value) for value in ids
                               if isinstance(value, str) and value and value != actor)
            for target in dict.fromkeys(targets):
                self.direct_events_by_target[target].append({
                    "event": event,
                    "actor_id": actor,
                    "target_id": target,
                    "t": t,
                    "step": step,
                    "evidence": "observed",
                    "correlation_id": record.get("correlation_id"),
                })

    def observe_sample(self, record: dict) -> None:
        fields = _fields(record, "extra")
        entity_id = record.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            return
        t = _number(record.get("t"))
        if t is None:
            return
        kind = str(record.get("kind", "unknown"))
        entity_class = str(fields.get("entity_class", ""))
        state = str(record.get("state", fields.get("state", "")) or "")
        animation = str(fields.get("animation_game_method", record.get("animation", "")) or "")
        health = _number(fields.get("current_health", fields.get("health")))
        dead_flag = _bool(fields.get("dead_flag", fields.get("dead")))
        sample = {
            "id": entity_id,
            "kind": kind,
            "entity_class": entity_class,
            "t": t,
            "step": record.get("step"),
            "pos": _vector(record.get("pos")),
            "state": state,
            "animation": animation,
            "ai_controlled": _bool(fields.get("ai_controlled", fields.get("AI"))),
            "health": health,
            "dead_flag": dead_flag,
        }

        if _is_human(entity_id, kind, entity_class) and _is_attack_sample(sample):
            history = self.attack_samples[entity_id]
            history.append({key: sample[key] for key in
                            ("t", "step", "state", "animation", "ai_controlled", "pos")})

        previous = self.last_samples.get(entity_id)
        signals = _dead_signals(sample)
        if (_is_titan(entity_id, kind, entity_class) and previous and signals
                and not _dead_signals(previous) and self._previous_alive(previous)):
            self.deaths.append(self._attribute_death(sample, previous, signals))

        self.last_samples[entity_id] = sample

    @staticmethod
    def _previous_alive(sample: dict) -> bool:
        if sample.get("dead_flag") is True:
            return False
        if sample.get("health") is not None:
            return sample["health"] > 0
        return bool(sample.get("state")) and not _dead_signals(sample)

    def _attribute_death(self, target: dict, previous: dict, death_signals: list[str]) -> dict:
        target_id = target["id"]
        death_t = target["t"]
        matching_contacts = [contact for contact in self.collisions_by_target[target_id]
                             if contact["actor_id"] and contact["t"] is not None
                             and 0 <= death_t - contact["t"] <= CONTACT_WINDOW_SECONDS]
        contacts_by_actor = defaultdict(list)
        for contact in matching_contacts:
            contacts_by_actor[contact["actor_id"]].append(contact)

        direct_events = [event for event in self.direct_events_by_target[target_id]
                         if event["t"] is not None
                         and 0 <= death_t - event["t"] <= DIRECT_EVENT_WINDOW_SECONDS]
        direct_by_actor = defaultdict(list)
        for event in direct_events:
            direct_by_actor[event["actor_id"]].append(event)

        candidate_ids = set(contacts_by_actor) | set(direct_by_actor)
        candidates = []
        for actor_id in candidate_ids:
            contacts = contacts_by_actor[actor_id]
            attacks = [item for item in self.attack_samples[actor_id]
                       if 0 <= death_t - item["t"] <= ATTACK_WINDOW_SECONDS]
            latest_actor = self.last_samples.get(actor_id)
            if latest_actor and not (0 <= death_t - latest_actor["t"] <= ATTACK_WINDOW_SECONDS):
                latest_actor = None
            ai_observations = [item["ai_controlled"] for item in attacks
                               if item["ai_controlled"] is not None]
            if latest_actor and latest_actor["ai_controlled"] is not None:
                ai_observations.append(latest_actor["ai_controlled"])
            ai_controlled = (True if True in ai_observations else
                             False if ai_observations else None)
            attack_sample = attacks[-1] if attacks else None
            actor_position = latest_actor["pos"] if latest_actor else None
            if actor_position is None and attack_sample:
                actor_position = attack_sample["pos"]
            separation = _distance(actor_position, target["pos"])
            direct_actor_events = direct_by_actor[actor_id]
            if any(item["event"] == "death" for item in direct_actor_events):
                classification = "direct_death_event"
            elif any(item["event"] == "damage" for item in direct_actor_events):
                classification = "observed_damage_near_death"
            elif len(contacts) >= 2 and ai_controlled is True and attack_sample:
                classification = "strong_inference"
            elif contacts and (ai_controlled is True or attack_sample):
                classification = "possible_inference"
            elif contacts:
                classification = "contact_only"
            else:
                classification = "direct_event_only"
            evidence = []
            if contacts:
                evidence.append("observed_collision_with_target")
            if ai_controlled is True:
                evidence.append("sampled_ai_controlled_true_near_death")
            if attack_sample:
                evidence.append("sampled_attack_state_or_animation_near_death")
            if direct_actor_events:
                evidence.append("observed_correlated_damage_or_death_event")
            candidates.append({
                "actor_id": actor_id,
                "evidence_classification": classification,
                "evidence": "observed_events_plus_sampled_state; attribution_is_inferred_unless_direct_event_present",
                "ai_controlled_near_death": ai_controlled,
                "observed_target_collision_count": len(contacts),
                "first_target_collision_t": min((x["t"] for x in contacts), default=None),
                "last_target_collision_t": max((x["t"] for x in contacts), default=None),
                "attack_state_sampled_t": attack_sample["t"] if attack_sample else None,
                "attack_state_sampled": bool(attack_sample),
                "distance_at_death_units": separation,
                "direct_event_count": len(direct_actor_events),
                "direct_events": direct_actor_events,
                "indicators": evidence,
            })

        rank = {"direct_death_event": 0, "observed_damage_near_death": 1,
                "strong_inference": 2, "possible_inference": 3,
                "contact_only": 4, "direct_event_only": 5}
        candidates.sort(key=lambda item: (
            rank[item["evidence_classification"]],
            -item["observed_target_collision_count"],
            item["actor_id"],
        ))
        direct_deaths = [item for item in candidates if item["evidence_classification"] == "direct_death_event"]
        strong = [item for item in candidates if item["evidence_classification"] == "strong_inference"]
        possible = [item for item in candidates if item["evidence_classification"] == "possible_inference"]
        if len(direct_deaths) == 1:
            status = "direct_death_attribution_observed"
        elif len(direct_deaths) > 1:
            status = "ambiguous_direct_death_events"
        elif len(strong) == 1:
            status = "strong_inferred_candidate"
        elif len(strong) > 1:
            status = "ambiguous_strong_candidates"
        elif possible:
            status = "possible_candidates"
        elif candidates:
            status = "contact_or_direct_evidence_without_attribution"
        else:
            status = "unattributed"

        return {
            "type": "titan_death_attribution",
            "target_id": target_id,
            "t": death_t,
            "step": target.get("step"),
            "evidence": "sampled_state_transition",
            "death_signals": death_signals,
            "health_before": previous.get("health"),
            "health_after": target.get("health"),
            "state_before": previous.get("state"),
            "state_after": target.get("state"),
            "animation_after": target.get("animation"),
            "attribution_status": status,
            "direct_kill_attribution_observed": bool(direct_deaths),
            "candidates": candidates,
            "limitations": [
                "Human collision callbacks establish contact, not damage.",
                "Sampled Attack state/animation is not an attack-input or damage event.",
                "Only eligible local Humans and local-master AI are captured; absent remote players cannot be excluded.",
                "No direct damage/death callback was emitted unless listed in direct_events.",
            ],
        }


__all__ = ["KillAttributionCollector"]
