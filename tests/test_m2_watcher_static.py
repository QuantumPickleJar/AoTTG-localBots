"""Safety checks for the optional passive M2 observer."""
import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from cl_harness import load_controller, translate, Vector
from test_wave_m2 import Cadet

class M2WatcherTests(unittest.TestCase):
    def test_passive_bounded_m2_observer(self):
        src = (Path(__file__).resolve().parents[1] / "addons/AICadetsM2Watcher.cl").read_text()
        for token in ("AICadetsM2WatchTrace", "AICadetsM2RunId-", "GetAIState()", "_records >= 2000", "AICadetsM2TargetInfo-", "AICadetsM2Navigation-", "_maxTraceChars = 16000", "StartNextSegment()", "String.Length("):
            self.assertIn(token, src)
        for token in ("PersistentData.Clear(", "SpawnHumanAt(", "LaunchHookLeft(", "UseGas(", "Attack(", ".MoveTo("):
            self.assertNotIn(token, src)
        contract = json.loads((Path(__file__).resolve().parent / "api_contract.json").read_text())
        methods = contract["types"]["String"]["methods"]
        self.assertEqual(methods["Length"]["signature"], "function Length(str: string) -> int")
        self.assertEqual(methods["SubstringWithLength"]["signature"],
                         "function SubstringWithLength(str: string, startIndex: int, length: int) -> string")
        tree = ast.parse(translate(src))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "String"):
                spec = methods[node.func.attr]
                self.assertEqual(len(node.args), spec["min_args"], spec["signature"])

    def test_watcher_appends_beyond_full_legacy_range_without_overwriting(self):
        src = (Path(__file__).resolve().parents[1] / "addons/AICadetsM2Watcher.cl").read_text()
        self.assertIn("Range(startIndex, 1000, 1)", src)
        existing = {f"AICadetsM2Watch{i}" for i in range(100)}
        saved = {}
        time = NS(GameTime=0.0)
        persistent = NS(
            FileExists=lambda name: name in existing or name in saved,
            SaveToFile=lambda name, encrypted: saved.setdefault(name, name) is not None,
            GetProperty=lambda key, default: default,
            SetProperty=lambda key, value: None,
        )
        observer = load_controller({
            "Network": NS(IsMasterClient=True), "Time": time,
            "Game": NS(AIHumans=[], Print=lambda message: None),
            "PersistentData": persistent,
            "Convert": NS(ToString=str),
            "String": NS(Length=len, SubstringWithLength=lambda value,start,length: value[start:start+length]),
            "Range": range, "Vector3": Vector,
        }, src, class_name="AICadetsM2Watcher")

        observer.OnGameStart()

        self.assertEqual(observer._file, "AICadetsM2Watch100")
        self.assertEqual(len(existing), 100)
        self.assertIn("AICadetsM2Watch100", saved)
        self.assertEqual(len(saved), 1)

    def test_owned_demo_and_m2_roster_are_distinguished_without_movement(self):
        src = (Path(__file__).resolve().parents[1] / "addons/AICadetsM2Watcher.cl").read_text()
        cadet = Cadet()
        cadet.Name = "AICadetsM2-1"
        cadet.IsHookingLeft = False
        cadet.LeftHookPosition = None
        demo = NS(Name="AICadetsM1", IsMine=True, IsAlive=True, ViewID=888)
        data = {"AICadetsM2State-AICadetsM2-1": "ApproachGround", "AICadetsM2Build-AICadetsM2-1": "M2-navdiag-1"}
        time = NS(GameTime=0.0)
        observer = load_controller({
            "Network": NS(IsMasterClient=True), "Time": time,
            "Game": NS(AIHumans=[cadet, demo], Print=lambda s: None),
            "PersistentData": NS(FileExists=lambda f: False, SaveToFile=lambda f,e: True,
                GetProperty=lambda k,d: data.get(k,d), SetProperty=lambda k,v: data.__setitem__(k,v)),
            "Convert": NS(ToString=str), "String": NS(Length=len, SubstringWithLength=lambda s,start,length: s[start:start+length]),
            "Range": range, "Vector3": Vector,
        }, src, class_name="AICadetsM2Watcher")
        observer.OnGameStart()
        observer.OnTick()
        time.GameTime = 0.02
        observer.OnTick()
        self.assertIn("owned_cadet name=AICadetsM1 view_id=888 alive=True controller_state=no_M2_controller", observer._trace)
        self.assertIn("build=M2-navdiag-1", observer._trace)
        self.assertIn("human_state=Idle", observer._trace)
        self.assertIn("animation=idle", observer._trace)
        self.assertEqual(cadet.calls, [])

    def test_large_watch_rotates_before_persistent_data_save_limit(self):
        src = (Path(__file__).resolve().parents[1] / "addons/AICadetsM2Watcher.cl").read_text()
        data = {"AICadetsM2Report-existing": "R" * 331000}
        saved = {}
        time = NS(GameTime=0.0)

        def save_to_file(name, encrypted):
            payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(payload) > 1_000_000:
                raise RuntimeError("PersistentData.SaveToFile exceeded 1 mb limit")
            saved[name] = dict(data)
            return True

        persistent = NS(
            FileExists=lambda name: name in saved,
            SaveToFile=save_to_file,
            GetProperty=lambda key, default: data.get(key, default),
            SetProperty=lambda key, value: data.__setitem__(key, value),
        )
        observer = load_controller({
            "Network": NS(IsMasterClient=True), "Time": time,
            "Game": NS(AIHumans=[], Print=lambda message: None),
            "PersistentData": persistent,
            "Convert": NS(ToString=str),
            "String": NS(Length=len, SubstringWithLength=lambda value,start,length: value[start:start+length]),
            "Range": range, "Vector3": Vector,
        }, src, class_name="AICadetsM2Watcher")

        observer.OnGameStart()
        for index in range(40):
            time.GameTime = index * 0.2
            observer.Record("synthetic_sample " + ("x" * 4000))
        observer.Flush()

        self.assertGreaterEqual(len(saved), 8)
        names = sorted(saved, key=lambda name: int(name.removeprefix("AICadetsM2Watch")))
        for name in names:
            snapshot = saved[name]
            encoded = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.assertLessEqual(len(encoded), 1_000_000)
            trace = snapshot["AICadetsM2WatchTrace"]
            self.assertLessEqual(len(trace), 16000)
            self.assertIn("AICadetsM2Watcher v4", trace)
        self.assertIn("previous=AICadetsM2Watch", saved[names[-1]]["AICadetsM2WatchTrace"])
        self.assertEqual(observer._records, 41)
        self.assertEqual(len({saved[name]["AICadetsM2WatchTrace"] for name in names}), len(names))
