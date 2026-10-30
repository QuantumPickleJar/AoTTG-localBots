import json
import tempfile
import unittest
from pathlib import Path

import importlib.util

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "tools" / "analyze_m1_run.py"
spec = importlib.util.spec_from_file_location("analyze_m1_run", MODULE)
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)


class M1EventReportTests(unittest.TestCase):
    def test_parse_and_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controller = root / "controller.log"
            controller.write_text(
                "\n".join(
                    [
                        "[AI Cadets M1R] t=3.86 state=Attach leg=1 event=hook_launch mode=primary",
                        "[AI Cadets M1R] t=4.52 state=Burst leg=1 event=hook_release mode=primary",
                    ]
                )
            )
            watcher = root / "AICadetsM1Watch7.txt"
            watcher.write_text(
                json.dumps(
                    {
                        "AICadetsM1WatchTrace": "AICadetsWatcher v3\n2.66 scout_found\n5.02 hook_transition_near_surface dt=0.02\n"
                    }
                )
            )
            rows = analyzer.parse_controller(controller) + analyzer.parse_watcher(watcher)
            rows.sort(key=lambda e: e.t)
            self.assertEqual([round(x.t, 2) for x in rows], [2.66, 3.86, 4.52, 5.02])
            self.assertEqual(analyzer.classify(rows[-1].text), "inferred")


if __name__ == "__main__":
    unittest.main()
