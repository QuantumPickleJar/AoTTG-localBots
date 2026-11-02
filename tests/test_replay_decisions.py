"""Recorded-state replay contracts; synthetic inputs are not gameplay evidence."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from replay_decisions import read_pairs, validate_input, replay_with_policy, reference_policy, run, ReplayError


class ReplayContractTests(unittest.TestCase):
    def setUp(self):
        self.meta,self.rows,self.problems=read_pairs(ROOT/'examples/flight_recorder/example_replay')
        self.inp=self.rows[0]['decision_input']

    def test_extracts_exact_recorded_scenario_and_measured_outcome(self):
        self.assertEqual(len(self.rows),1)
        self.assertEqual(self.problems,[])
        self.assertTrue(self.rows[0]['has_entity_frame_at_input_step'])
        self.assertEqual(self.rows[0]['action_outcome']['status'],'in_progress')

    def test_recorded_and_replayed_choices_match(self):
        match=replay_with_policy(self.rows,reference_policy)
        self.assertEqual(match[0]['recorded_choice'],'intercept_grab')
        self.assertTrue(match[0]['agrees'])

    def test_profile_metamorphic_support_vs_combat(self):
        focused=copy.deepcopy(self.inp)
        focused['profile']['personality']['rescue_priority']=0.0
        self.assertEqual(reference_policy(focused),'attack_titan')
        self.assertEqual(reference_policy(self.inp),'intercept_grab')

    def test_mechanical_carry_gate_outweighs_altruism(self):
        focused=copy.deepcopy(self.inp)
        focused['candidates'][0]['eligible']=False
        focused['candidates'][1]['eligible']=False
        self.assertEqual(reference_policy(focused),'hold')

    def test_only_one_viable_action_wins_even_with_low_personality_preference(self):
        focused=copy.deepcopy(self.inp)
        focused['profile']['personality']['rescue_priority']=0.0
        focused['candidates'][1]['eligible']=False
        self.assertEqual(reference_policy(focused),'intercept_grab')

    def test_rejects_profile_out_of_range_and_duplicate_maneuver(self):
        focused=copy.deepcopy(self.inp)
        focused['profile']['personality']['rescue_priority']=1.2
        with self.assertRaises(ReplayError): validate_input(focused)
        focused=copy.deepcopy(self.inp)
        focused['candidates'].append(copy.deepcopy(focused['candidates'][0]))
        with self.assertRaises(ReplayError): validate_input(focused)

    def test_reports_missing_recorder_frames_and_result(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            (d/'metadata.json').write_text(json.dumps({'schema_version':'aicadets.flight.v1','run_id':'missing'}))
            (d/'000001.jsonl').write_text(json.dumps(self.inp)+'\n')
            _,rows,problems=read_pairs(d)
            kinds={p['kind'] for p in problems}
            self.assertIn('missing_matching_physics_frame',kinds)
            self.assertIn('missing_decision_result',kinds)

    def test_exports_fixtures_and_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            res=run(ROOT/'examples/flight_recorder/example_replay',Path(td),reference_policy)
            self.assertEqual(res['planner_decisions'],1)
            self.assertEqual(res['replay_agreement'],1)
            self.assertEqual(res['physics_frame_correlated'],1)
            self.assertEqual(len(json.loads((Path(td)/'scenarios.json').read_text())),1)

if __name__ == '__main__': unittest.main()
