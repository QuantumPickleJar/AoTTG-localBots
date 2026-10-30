"""Lightweight source checks; do not establish game parser or persistence semantics."""
import re
import unittest
import ast
from types import SimpleNamespace as NS
from cl_harness import translate, Vector
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'addons/AICadetsWatcher.cl'

class WatcherChecks(unittest.TestCase):
    def test_scope_and_bounds(self):
        s = SOURCE.read_text()
        self.assertIn('human.Name == "AICadetsM1" && human.IsMine', s)
        self.assertIn('Range(0, 100, 1)', s)
        self.assertIn('PersistentData.FileExists(candidate)', s)
        self.assertIn('Time.GameTime - self._foundAt >= 25.0', s)
        self.assertIn('Time.GameTime + 0.2', s)
        self.assertIn('Time.GameTime + 1.0', s)
        self.assertEqual(s.count('{'), s.count('}'))
        self.assertFalse(re.search(r'PersistentData\.Clear\s*\(', s))
        self.assertFalse(re.search(r'\.(UseGas|LaunchHookLeft|ReleaseHookLeft|Move|Jump)\s*\(', s))
        self.assertIn('possible_impact', s)
        self.assertIn('change >= 8.0', s)
        self.assertIn('Time.GameTime + 0.2', s)
        self.assertIn('Physics.LineCast(start, end, CollideWithEnum.MapObjects)', s)
        self.assertIn('Physics.LineCast(start, end, CollideWithEnum.MapEditor)', s)
        for prop in ('Position', 'Velocity', 'CurrentGas', 'IsHookedLeft', 'IsHookingLeft', 'LeftHookReady', 'Grounded', 'LeftHookPosition'):
            self.assertIn('self._scout.' + prop, s)

class WatcherBehavior(unittest.TestCase):
    def setUp(self):
        # Exercise actual helper bodies with mocked engine state, not CL parsing.
        source = SOURCE.read_text()
        start = source.index('    function SampleInterval()')
        end = source.index('    function Snapshot(')
        fragment = 'addon WatchTest\n{\n' + source[start:end] + '}\n'
        env = {'Time': NS(GameTime=12), 'Convert': NS(ToString=str)}
        exec(translate(fragment), env)
        self.w = env['WatchTest']()

    def test_event_classification(self):
        cases = [((False, True, False, False, False), 'hook_transition_velocity_change'),
                 ((False, True, False, False, True), 'hook_transition_near_surface'),
                 ((False, False, False, True, False), 'landing_velocity_change'),
                 ((False, False, False, False, True), 'possible_impact'),
                 ((False, False, False, False, False), 'unexplained_velocity_change')]
        for args, expected in cases:
            self.assertEqual(self.w.MotionEvent(*args), expected)

    def test_idle_and_motion_rates(self):
        self.w._scout = NS(Grounded=True, Velocity=Vector(0, 0, 0), IsHookedLeft=False, IsHookingLeft=False)
        self.assertEqual(self.w.SampleInterval(), 2.0)
        self.w._scout.Velocity = Vector(1, 0, 0)
        self.assertEqual(self.w.SampleInterval(), 0.2)
        self.w._scout.Grounded = False
        self.w._scout.Velocity = Vector(0, 0, 0)
        self.assertEqual(self.w.SampleInterval(), 0.2)

    def test_record_limit_is_explicit(self):
        self.w._records = 499
        self.w._trace = ''
        self.w.Record('sample')
        self.assertTrue(self.w._finished)
        self.assertIn('record_limit_reached', self.w._trace)
        before = self.w._trace
        self.w.Record('extra')
        self.assertEqual(before, self.w._trace)

if __name__ == '__main__':
    unittest.main()
