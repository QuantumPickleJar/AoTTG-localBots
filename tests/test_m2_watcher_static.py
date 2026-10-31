"""Safety checks for the optional passive M2 observer."""
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from cl_harness import load_controller, Vector
from test_wave_m2 import Cadet

class M2WatcherTests(unittest.TestCase):
    def test_passive_bounded_m2_observer(self):
        src = (Path(__file__).resolve().parents[1] / "addons/AICadetsM2Watcher.cl").read_text()
        for token in ("AICadetsM2WatchTrace", "AICadetsM2RunId-", "GetAIState()", "_records >= 2000", "AICadetsM2TargetInfo-", "AICadetsM2Navigation-"):
            self.assertIn(token, src)
        for token in ("PersistentData.Clear(", "SpawnHumanAt(", "LaunchHookLeft(", "UseGas(", "Attack(", ".MoveTo("):
            self.assertNotIn(token, src)

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
            "Convert": NS(ToString=str), "Range": range, "Vector3": Vector,
        }, src, class_name="AICadetsM2Watcher")
        observer.OnGameStart()
        observer.OnTick()
        time.GameTime = 0.02
        observer.OnTick()
        self.assertIn("owned_cadet name=AICadetsM1 view_id=888 alive=True controller_state=no_M2_controller", observer._trace)
        self.assertIn("build=M2-navdiag-1", observer._trace)
        self.assertEqual(cadet.calls, [])
