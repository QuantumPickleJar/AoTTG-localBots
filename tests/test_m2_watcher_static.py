"""Static safety checks for optional, read-only M2 observer."""
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M1 = ROOT / "addons" / "AICadetsWatcher.cl"
M2 = ROOT / "addons" / "AICadetsM2Watcher.cl"

def blob_sha(path):
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\\0" + data).hexdigest()

class M2WatcherStaticTests(unittest.TestCase):
    def test_v3_m1_watcher_unchanged(self):
        # Original v3 watcher remains the known-good rollback baseline.
        self.assertEqual(blob_sha(M1), "5b3e1720b6e3d66b4fc35d0c9957306b67203b57")

    def test_m2_watcher_is_passive_and_namespace_isolated(self):
        src = M2.read_text()
        self.assertIn("addon AICadetsM2Watcher", src)
        self.assertIn('AICadetsM2WatchTrace', src)
        self.assertIn('AICadetsM2Watch', src)
        self.assertIn('human.Name == "AICadetsM2-1"', src)
        self.assertNotIn('human.Name == "AICadetsM1"', src)
        self.assertNotIn("PersistentData.Clear", src)
        for token in ("SpawnHumanAt(", "LaunchHookLeft(", "UseGas(", "Jump(", "Attack("):
            self.assertNotIn(token, src)

if __name__ == "__main__":
    unittest.main()
