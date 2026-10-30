"""Verify source-identical rollback and read-only recovery checks."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "tools" / "recovery_preflight.py"
spec = importlib.util.spec_from_file_location("recovery_preflight", MODULE)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)

class RecoveryPreflightTests(unittest.TestCase):
    def test_original_controller_and_watcher_not_modified(self):
        for name, expected in preflight.EXPECTED.items():
            path = ROOT / "addons" / name
            self.assertTrue(path.is_file())
            self.assertEqual(preflight.git_blob_sha(path), expected)
        self.assertEqual([level for level, _ in preflight.verify_addons(ROOT / "addons") if level == "ERROR"], [])

    def test_modified_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in preflight.EXPECTED:
                (root / name).write_bytes((ROOT / "addons" / name).read_bytes())
            self.assertEqual([x[0] for x in preflight.verify_addons(root)][:2], ["PASS", "PASS"])
            (root / "AICadetsWatcher.cl").write_text("changed")
            self.assertIn("ERROR", [x[0] for x in preflight.verify_addons(root)])

    def test_watcher_without_scout_is_distinct_from_no_watcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "AICadetsM1Watch7.txt"
            file.write_text(json.dumps({"AICadetsM1WatchTrace": "string:AICadetsWatcher v3\\n0 watch_started\\n45 watch_timeout"}))
            results = preflight.inspect_watches(root)
            self.assertTrue(any("watch_started present" in message for _, message in results))
            self.assertTrue(any("scout_found absent" in message for _, message in results))

if __name__ == "__main__":
    unittest.main()
