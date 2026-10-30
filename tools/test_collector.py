import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import analyze_trace as analyzer

ROOT = Path(__file__).parent.parent


class FlightRecorderTests(unittest.TestCase):
    def test_decodes_actual_persistent_data_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'trace.txt'
            p.write_text(json.dumps({'AICadetsM1WatchTrace': 'string:AICadetsWatcher v4\n0 watch_started\n1 sample pos=(0.00, 0.00, 0.00) vel=(0.00, 0.00, 0.00) gas=115 hooked=false\n2 transition pos=(3.00, 0.00, 4.00) vel=(3.00, 0.00, 4.00) gas=114 hooked=true\n3 watch_end reason=watch_timeout', 'AICadetsM1DecisionTrace': 'string:controller\n1.5 seq=1 state=Attach leg=1 anchor_selected point=(3.00, 1.00, 4.00)\n2.5 seq=2 state=Observe leg=1 finish reason=completed'}), encoding='utf-8')
            watch, ctrl, _ = analyzer.load(p)
            r = analyzer.analyze(watch, ctrl)
            self.assertEqual(r['displacement_3d'], 5.0)
            self.assertEqual(r['gas_used'], 1.0)
            self.assertEqual(r['controller_selected_anchors'], 1)
            self.assertEqual(r['controller_finish_reasons'], ['completed'])

    def test_collision_after_release_detected(self):
        w = '''AICadetsWatcher v3
0 sample pos=(0, 0, 0) vel=(0, 0, 0) gas=115 hooked=false
1 change pos=(0, 2, 0) vel=(0, 2, 0) gas=114 hooked=true
2 change pos=(0, 2, 4) vel=(0, 2, 10) gas=113 hooked=false
2.15 possible_impact pre_vel=(0, 2, 10) post_vel=(0, 2, 0) delta_v=10 layer=MapObjects hit=(0, 2, 5)
3 watch_timeout'''
        r = analyzer.analyze(w, '')
        self.assertTrue(any('0.6 s after' in x for x in r['issues']))
        self.assertEqual(r['controller_events'], 0)

    def test_original_game_scripts_exact_hashes_and_no_mutations(self):
        expected = {
            'AICadetsTraversal.cl': '4c1d23c628d18f98500d2c3f20f5d954c1ea17fd',
            'AICadetsWatcher.cl': '5b3e1720b6e3d66b4fc35d0c9957306b67203b57',
        }
        for filename, sha in expected.items():
            data = (ROOT / 'addons' / filename).read_bytes()
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            self.assertEqual(blob, sha, filename)
        watcher = (ROOT / 'addons/AICadetsWatcher.cl').read_text()
        traversal = (ROOT / 'addons/AICadetsTraversal.cl').read_text()
        self.assertNotIn('PersistentData.Clear(', watcher + traversal)
        self.assertNotIn('LaunchHookLeft(', watcher)
        self.assertNotIn('UseGas(', watcher)
        self.assertNotIn('ReleaseHookLeft(', watcher)
        self.assertNotIn('Game.SpawnHumanAt(', watcher)
        self.assertNotIn('Network.MyPlayer', watcher)
        self.assertNotIn('AICadetsM1DecisionTrace', watcher + traversal)
        self.assertIn('function CollisionRisk()', traversal)
        self.assertEqual(traversal.count('LaunchHookLeft('), 1)
        self.assertEqual(traversal.count('UseGas(true)'), 1)
        for src in (watcher, traversal):
            self.assertEqual(src.count('{'), src.count('}'))

    def test_read_only_preflight_with_expected_scripts(self):
        from recovery_preflight import verify_addons, inspect_watches
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for filename in ('AICadetsTraversal.cl', 'AICadetsWatcher.cl'):
                (folder / filename).write_bytes((ROOT / 'addons' / filename).read_bytes())
            checks = verify_addons(folder)
            self.assertEqual([x[0] for x in checks], ['PASS', 'PASS'])
            (folder / 'AICadetsWatcher.cl').write_text('v4 bad')
            checks = verify_addons(folder)
            self.assertIn('ERROR', [x[0] for x in checks])
            pd = folder / 'PersistentData'
            pd.mkdir()
            (pd / 'AICadetsM1Watch0.txt').write_text(json.dumps({'AICadetsM1WatchTrace': 'string:AICadetsWatcher v3\n0 watch_started\n45 watch_timeout'}), encoding='utf-8')
            findings = inspect_watches(pd)
            self.assertTrue(any('watch_started' in msg for _, msg in findings))
            self.assertTrue(any('lacks scout_found' in msg for _, msg in findings))

    def test_report_output(self):
        r = analyzer.analyze('AICadetsWatcher v4\n0 watch_started\n1 watch_timeout', '')
        self.assertIn('NOT OBSERVED', analyzer.report(r, 'run.txt'))
        self.assertIn('single-pass', analyzer.compact_prompt(r, 'run.txt').lower())


if __name__ == '__main__':
    unittest.main()
