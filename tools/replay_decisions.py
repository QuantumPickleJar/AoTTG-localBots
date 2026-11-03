#!/usr/bin/env python3
"""Flight v1 -> personality/maneuver replay contract.

This does NOT simulate Unity physics or implement the project's production policy.
It only extracts exact recorded planner observations/results and permits offline
unit-test policies to receive the same serialized input objects. Synthetic
traces prove adapter mechanics, NOT accuracy of the game-side mock.

Usage: python tools/replay_decisions.py example_replay --out replay_report
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import importlib
import json
import math
from pathlib import Path
from typing import Callable, Any

from analyze_flight import Reader, SCHEMA
from m3_policy_contract import ContractError, profile_hash, validate_profile


class ReplayError(ValueError):
    pass


def _finite_float(v, path):
    if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v):
        raise ReplayError(f"{path} must be a finite number")
    return float(v)


def validate_input(event: dict) -> dict:
    """Require decision context emitted by runtime, not reconstructed guesses."""
    if event.get('type') != 'event' or event.get('event') != 'decision_input':
        raise ReplayError('not a decision_input event')
    for field in ('decision_id', 'id', 'policy_version'):
        if not isinstance(event.get(field), str) or not event[field]:
            raise ReplayError(f'missing string {field}')
    for field in ('step', 't'):
        _finite_float(event.get(field), field)
    profile = event.get('profile')
    if not isinstance(profile, dict):
        raise ReplayError('missing profile object')
    try:
        validate_profile(profile)
    except ContractError as err:
        raise ReplayError(f'profile does not match M3 profile schema v1: {err}') from err
    actual_profile_hash = profile_hash(profile)
    recorded_profile_hash = event.get('profile_hash')
    if not isinstance(recorded_profile_hash, str) or recorded_profile_hash != actual_profile_hash:
        raise ReplayError('profile_hash does not match the validated serialized profile')
    candidates = event.get('candidates')
    if not isinstance(candidates, list):
        raise ReplayError('missing candidate list')
    seen = set()
    for c in candidates:
        if not isinstance(c, dict) or not isinstance(c.get('id'), str) or not c['id']:
            raise ReplayError('candidates require stable ids')
        if c['id'] in seen:
            raise ReplayError(f"duplicate candidate id {c['id']}")
        seen.add(c['id'])
        if c.get('status') not in ('definition_only', 'experimental', 'validated'):
            raise ReplayError(f"candidate {c['id']} missing validation status")
        if not isinstance(c.get('eligible'), bool):
            raise ReplayError(f"candidate {c['id']} must record an actual capability gate")
        if not isinstance(c.get('eligibility_reasons'), list) or not all(
                isinstance(reason, str) for reason in c['eligibility_reasons']):
            raise ReplayError(f"candidate {c['id']} missing eligibility reasons")
        if not isinstance(c.get('mechanically_supported'), bool):
            raise ReplayError(f"candidate {c['id']} must record mechanical support")
        if c['status'] == 'definition_only' and c['eligible']:
            raise ReplayError(f"definition-only candidate {c['id']} cannot be eligible")
        if not c['mechanically_supported'] and c['eligible']:
            raise ReplayError(f"unsupported candidate {c['id']} cannot be eligible")
        metrics = c.get('metrics', {})
        if not isinstance(metrics, dict):
            raise ReplayError(f"candidate {c['id']} metrics must be an object")
        for name, value in metrics.items():
            _finite_float(value, f"candidate {c['id']}.metrics.{name}")
    observations = event.get('observations')
    if not isinstance(observations, dict):
        raise ReplayError('missing recorded observation object')
    if not isinstance(event.get('state_version'), str) or not event['state_version']:
        raise ReplayError('missing planner state_version')
    if not isinstance(event.get('profile_hash'), str) or not event['profile_hash']:
        raise ReplayError('missing profile_hash')
    return event


def read_pairs(source) -> tuple[dict, list[dict], list[dict]]:
    """Read monotonic chunks; do not pretend missing events make complete decisions."""
    with_meta = Reader(source)
    try:
        meta = with_meta.metadata()
        if meta and meta.get('schema_version') != SCHEMA:
            raise ReplayError('unsupported flight schema')
        decisions = {}
        problems = []
        entity_frames = set()
        for chunk in with_meta.files():
            with with_meta.open(chunk) as handle:
                for ln, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except (ValueError, TypeError) as err:
                        problems.append({'kind': 'invalid_json', 'location': f'{chunk}:{ln}', 'detail': str(err)})
                        continue
                    if not isinstance(record, dict):
                        problems.append({'kind': 'not_object', 'location': f'{chunk}:{ln}'})
                        continue
                    if record.get('type') == 'frame':
                        step = record.get('step')
                        for s in record.get('samples', []):
                            if isinstance(s, dict) and s.get('id'):
                                entity_frames.add((step, s['id']))
                        continue
                    if record.get('type') != 'event':
                        continue
                    typ = record.get('event')
                    if typ == 'm2_source_observation':
                        replayability = record.get('replayability', {})
                        source = record.get('source')
                        problems.append({
                            'kind': 'm2_observation_not_replayable',
                            'source_event_id': source.get('event_sequence') if isinstance(source, dict) else None,
                            'missing': replayability.get('missing_fields', []) if isinstance(replayability, dict) else [],
                            'detail': 'M2 LogEvent observations do not contain the complete decision replay input contract.',
                        })
                        continue
                    if typ not in ('decision_input', 'decision_result', 'action_outcome'):
                        continue
                    key = (record.get('id'), record.get('decision_id'))
                    if not all(isinstance(x, str) and x for x in key):
                        problems.append({'kind': 'missing_correlation_id', 'location': f'{chunk}:{ln}'})
                        continue
                    row = decisions.setdefault(key, {'id': key[0], 'decision_id': key[1]})
                    if typ in row:
                        problems.append({'kind': 'duplicate_event', 'decision_id': key[1], 'event': typ})
                        continue
                    row[typ] = record
        result = []
        for (entity, d_id), row in sorted(decisions.items()):
            inp = row.get('decision_input')
            if inp:
                try:
                    validate_input(inp)
                except ReplayError as err:
                    problems.append({'kind': 'invalid_decision_input', 'decision_id': d_id, 'detail': str(err)})
                row['has_entity_frame_at_input_step'] = (inp['step'], entity) in entity_frames
                if not row['has_entity_frame_at_input_step']:
                    problems.append({'kind': 'missing_matching_physics_frame', 'decision_id': d_id})
            else:
                problems.append({'kind': 'missing_decision_input', 'decision_id': d_id})
            end = row.get('decision_result')
            if end is None:
                problems.append({'kind': 'missing_decision_result', 'decision_id': d_id})
            elif not isinstance(end.get('choice'), str):
                problems.append({'kind': 'missing_choice', 'decision_id': d_id})
            if inp and end and end.get('policy_version') != inp.get('policy_version'):
                problems.append({'kind': 'policy_version_mismatch', 'decision_id': d_id})
            result.append(row)
        return meta, result, problems
    finally:
        with_meta.close()


def replay_with_policy(rows: list[dict], policy: Callable[[dict], str]) -> list[dict]:
    """Never compare policy versions or decisions without full inputs."""
    matches = []
    for row in rows:
        inp = row.get('decision_input')
        end = row.get('decision_result')
        if not inp or not end:
            continue
        try:
            validate_input(inp)
            predicted = policy(inp)
            if not isinstance(predicted, str):
                raise ReplayError('policy must return a choice ID string')
            actual = end.get('choice')
            scope = ('python_reference_policy_demo' if policy is reference_policy
                     else f"offline_policy:{getattr(policy, '__name__', policy.__class__.__name__)}")
            matches.append({'id': row['id'], 'decision_id': row['decision_id'],
                            'recorded_choice': actual, 'replay_choice': predicted,
                            'agrees': predicted == actual,
                            'physics_frame_present': row['has_entity_frame_at_input_step'],
                            'policy_version': inp['policy_version'],
                            'comparison_scope': scope,
                            'production_m2_parity': 'not_evaluated'})
        except ReplayError as exc:
            matches.append({'decision_id': row['decision_id'], 'error': str(exc)})
    return matches


def reference_policy(inp: dict) -> str:
    """DEMO ONLY. NOT AoTTG M2 policy. Hard gates precede a simple personality score."""
    p = inp['profile']['personality']
    rp = float(p.get('rescue_priority', 0.5))
    risk_tolerance = float(p.get('risk_tolerance', 0.5))
    gas_conservation = float(p.get('gas_conservation', 0.5))
    best = None
    for c in inp['candidates']:
        if not c['eligible'] or c['status'] == 'definition_only':
            continue
        if not c.get('mechanically_supported', False):
            continue
        # Only canned replay tests use these already-observed, dimensionless features.
        metrics = c.get('metrics', {})
        risk = float(metrics.get('risk', 0.0))
        cost = float(metrics.get('gas_cost', 0.0))
        score = (float(metrics.get('rescue', 0.0)) * rp * 4
                 + float(metrics.get('combat', 0.0)) * (1-rp) * 4
                 + float(metrics.get('progress', 0.0))
                 - risk * (1-risk_tolerance) * 5
                 - cost * gas_conservation)
        ranked = (-score, c['id'])  # stable tie-break for deterministic replay
        if best is None or ranked < best[0]:
            best = (ranked, c['id'])
    return best[1] if best else 'hold'


def run(source, out, policy=None):
    meta, pairs, problems = read_pairs(source)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    scenarios = [r['decision_input'] for r in pairs if 'decision_input' in r]
    (out/'scenarios.json').write_text(json.dumps(scenarios, indent=2)+'\n', encoding='utf-8')
    (out/'contract_problems.json').write_text(json.dumps(problems, indent=2)+'\n', encoding='utf-8')
    comparisons = replay_with_policy(pairs, policy) if policy else []
    (out/'policy_replay.json').write_text(json.dumps(comparisons, indent=2)+'\n', encoding='utf-8')
    outcome_count = sum('action_outcome' in row for row in pairs)
    policy_scope = ('not_run' if policy is None else
                    'python_reference_policy_demo' if policy is reference_policy else
                    f"offline_policy:{getattr(policy, '__name__', policy.__class__.__name__)}")
    summary = {'schema_version': SCHEMA, 'run_id': meta.get('run_id', 'unknown'),
               'capture_tier': meta.get('capture_tier', 'unknown'),
               'planner_decisions': len(pairs), 'inputs': len(scenarios),
               'results': sum('decision_result' in r for r in pairs),
               'measured_outcomes': outcome_count, 'problems': len(problems),
               'm2_observations_not_replayable': sum(p.get('kind') == 'm2_observation_not_replayable' for p in problems),
               'physics_frame_correlated': sum(r.get('has_entity_frame_at_input_step', False) for r in pairs),
               'replay_agreement': sum(r.get('agrees', False) for r in comparisons),
               'replay_checked': sum('agrees' in r for r in comparisons),
               'policy_comparison_scope': policy_scope,
               'production_m2_policy_parity': 'not_evaluated_by_python_replay',
               'warning': 'Policy agreement tests decisions, NOT accuracy of mocked physics or gameplay.'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source')
    ap.add_argument('--out', default='replay_report')
    ap.add_argument('--demo-policy', action='store_true', help='Compare with the illustrative Python reference policy; this is not M2 production-policy parity')
    a = ap.parse_args()
    print(json.dumps(run(a.source, a.out, reference_policy if a.demo_policy else None), indent=2))


if __name__ == '__main__':
    main()
