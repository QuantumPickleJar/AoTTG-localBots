"""Lightweight source checks; do not establish game parser or persistence semantics."""
import re
import unittest
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

if __name__ == '__main__':
    unittest.main()
