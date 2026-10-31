"""Safety checks for the optional passive M2 observer."""
import unittest
from pathlib import Path

class M2WatcherTests(unittest.TestCase):
    def test_passive_bounded_m2_observer(self):
        src = (Path(__file__).resolve().parents[1] / "addons/AICadetsM2Watcher.cl").read_text()
        for token in ("AICadetsM2WatchTrace", "AICadetsM2RunId-", "GetAIState()", "_records >= 2000", "AICadetsM2TargetInfo-", "AICadetsM2Navigation-"):
            self.assertIn(token, src)
        for token in ("PersistentData.Clear(", "SpawnHumanAt(", "LaunchHookLeft(", "UseGas(", "Attack(", ".MoveTo("):
            self.assertNotIn(token, src)
