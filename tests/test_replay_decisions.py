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
from m2_trace_adapter import M2TraceError, parse_log_event, write_observation_run


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
            self.assertEqual(res['policy_comparison_scope'],'python_reference_policy_demo')
            self.assertEqual(res['production_m2_policy_parity'],'not_evaluated_by_python_replay')
            self.assertEqual(len(json.loads((Path(td)/'scenarios.json').read_text())),1)

    def test_reference_policy_agreement_is_labeled_separately_from_m2_source_behavior(self):
        result=replay_with_policy(self.rows,reference_policy)[0]
        self.assertTrue(result['agrees'])
        self.assertEqual(result['comparison_scope'],'python_reference_policy_demo')
        self.assertEqual(result['production_m2_parity'],'not_evaluated')

    def test_replay_requires_complete_m3_profile_and_matching_profile_hash(self):
        focused=copy.deepcopy(self.inp)
        del focused['profile']['personality']['risk_tolerance']
        with self.assertRaisesRegex(ReplayError,'M3 profile schema v1'):
            validate_input(focused)
        focused=copy.deepcopy(self.inp)
        focused['profile_hash']='0'*64
        with self.assertRaisesRegex(ReplayError,'profile_hash does not match'):
            validate_input(focused)

    def test_m2_line_adapter_preserves_partial_observations_and_marks_them_unreplayable(self):
        line=('build=M2-locomotion-1 driver=Direct id=17 mode=Engage t=1.25 '
              'run=run-3 cadet=AICadetsM2-1 state=PlanApproach target=101 '
              'event=approach_goal_updated previous=Vector(X=1, Y=2, Z=3) '
              'goal=Vector(X=4, Y=5, Z=6) nape=Vector(X=7, Y=8, Z=9)')
        observation=parse_log_event(line)
        self.assertEqual(observation['event'],'m2_source_observation')
        self.assertEqual(observation['source']['event_sequence'],'17')
        self.assertEqual(observation['source']['run_id'],'run-3')
        self.assertEqual(observation['observed']['target_view_id'],'101')
        self.assertEqual(observation['details']['previous'],'Vector(X=1, Y=2, Z=3)')
        self.assertEqual(observation['replayability']['status'],'unreplayable')
        self.assertNotIn('decision_input',observation)
        self.assertNotIn('decision_id',observation)
        self.assertNotIn('step',observation)
        self.assertNotIn('profile',observation)

    def test_replay_reader_reports_m2_observations_instead_of_silently_dropping_them(self):
        line=('build=M2-locomotion-1 driver=Direct id=18 mode=Engage t=1.30 '
              'run=run-3 cadet=AICadetsM2-1 state=PlanApproach target=101 '
              'event=target_selected view_id=101 distance=42 listed=2 alive=2')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/'m2.log'
            source.write_text(line+'\n',encoding='utf-8')
            trace=root/'adapted'
            write_observation_run(source,trace)
            metadata,rows,problems=read_pairs(trace)
        self.assertEqual(metadata['capture_tier'],'custom_logic_m2_log_events_only')
        self.assertEqual(rows,[])
        problem=next(p for p in problems if p['kind']=='m2_observation_not_replayable')
        self.assertEqual(problem['source_event_id'],'18')
        self.assertIn('candidate_set_and_gate_results',problem['missing'])

    def test_m2_adapter_rejects_non_log_lines_without_guessing(self):
        with self.assertRaises(M2TraceError):
            parse_log_event('target_selected target=101 distance=42')

if __name__ == '__main__': unittest.main()
