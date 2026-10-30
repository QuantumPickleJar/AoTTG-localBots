"""Mocked M2 F8 order-menu behavior; NOT an AoTTG2 UI-runtime integration test."""
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from cl_harness import load_controller

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "addons" / "AICadetsCommandPanel.cl").read_text()


class Element:
    def __init__(self, text=""):
        self.Text = text
        self.children = []
        self.removed = False
        self.active = True

    def Absolute(self, *args):
        return self

    def Left(self, *args):
        return self

    def Top(self, *args):
        return self

    def Width(self, *args):
        return self

    def Height(self, *args):
        return self

    def Padding(self, *args):
        return self

    def Active(self, value=True):
        self.active = value
        return self

    def Add(self, element):
        self.children.append(element)
        return self

    def RemoveFromHierarchy(self):
        self.removed = True


class OrdersTest(unittest.TestCase):
    def make_controller(self, master=True):
        persistent = {}
        roots = []
        logs = []
        keypresses = set()
        camera = []
        inputs = []
        humans = []
        time = NS(GameTime=2.0)

        def make_root():
            root = Element()
            roots.append(root)
            return root

        ui = NS(
            VisualElement=lambda: Element(),
            ScrollView=lambda: Element(),
            Label=lambda value: Element(value),
            Button=lambda value, callback: NS(Text=value, callback=callback),
            GetRootVisualElement=make_root,
        )
        controller = load_controller(
            {
                "UI": ui,
                "Input": NS(
                    GetKeyDown=lambda key: key in keypresses,
                    SetHumanKeysEnabled=lambda enabled: inputs.append(enabled),
                ),
                "Camera": NS(
                    SetCameraLocked=lambda locked: camera.append(("lock", locked)),
                    SetCursorVisible=lambda visible: camera.append(("cursor", visible)),
                ),
                "Time": time,
                "Network": NS(
                    IsMasterClient=master,
                    MyPlayer=NS(Character=NS(
                        Type="Human", IsAlive=True,
                        Position=NS(X=10.0, Y=5.0, Z=-12.0))),
                ),
                "PersistentData": NS(
                    GetProperty=lambda key, default: persistent.get(key, default),
                    SetProperty=lambda key, value: persistent.__setitem__(key, value),
                ),
                "Game": NS(Print=logs.append, AIHumans=humans),
                "Convert": NS(ToString=str),
            },
            SOURCE,
            class_name="AICadetsCommandPanel",
        )
        return controller, persistent, roots, logs, keypresses, camera, inputs, humans, time

    def test_menu_hidden_by_default_f8_controls_cursor_without_pause(self):
        panel, data, roots, logs, keys, camera, inputs, humans, time = self.make_controller()
        panel.OnGameStart()
        self.assertEqual(len(roots), 1)
        self.assertFalse(panel._panel.active)
        self.assertEqual(camera, [("lock", False), ("cursor", False)])
        keys.add("CustomKey/F8")
        panel.OnFrame()
        self.assertTrue(panel._open)
        self.assertTrue(panel._panel.active)
        self.assertIn(("cursor", True), camera)
        self.assertNotIn(("lock", True), camera)
        self.assertEqual(len(inputs), 1)
        keys.clear()
        panel.OnFrame()
        self.assertTrue(panel._open)
        keys.add("CustomKey/F8")
        panel.OnFrame()
        self.assertFalse(panel._open)
        self.assertFalse(panel._panel.active)
        self.assertEqual(camera[-1], ("cursor", False))
        self.assertEqual(inputs[-1], True)
        self.assertIn(("lock", False), camera)

    def test_f9_recovery_with_desynchronized_menu_state(self):
        panel, data, roots, logs, keys, camera, inputs, humans, time = self.make_controller()
        panel.OnGameStart()
        panel.OpenMenu()
        panel._open = False
        keys.add("CustomKey/F9")
        panel.OnFrame()
        self.assertFalse(panel._panel.active)
        self.assertEqual(camera[-1], ("cursor", False))
        self.assertEqual(inputs[-1], True)

    def test_menu_timeout_restores_normal_play(self):
        panel, data, roots, logs, keys, camera, inputs, humans, time = self.make_controller()
        panel.OnGameStart()
        panel.OpenMenu()
        time.GameTime += panel.MenuMaxSeconds + 1.0
        panel.OnTick()
        self.assertFalse(panel._open)
        self.assertFalse(panel._panel.active)
        self.assertEqual(camera[-1], ("cursor", False))
        self.assertEqual(inputs[-1], True)

    def test_commands_are_pending_until_matching_m2_controller_acks(self):
        panel, data, roots, logs, keys, camera, inputs, humans, time = self.make_controller()
        panel.OnGameStart()
        panel.OpenMenu()
        buttons = [e for e in panel._actions.children if hasattr(e, "callback")]
        self.assertEqual(len(buttons), 11)
        panel.SelectTwo()
        panel.Explore()
        self.assertEqual(data["AICadetsCmdScope"], "AICadetsM2-2")
        self.assertEqual(data["AICadetsCmdMode"], "Explore")
        self.assertEqual(data["AICadetsCmdSequence"], 1)
        self.assertIn("PENDING #1", panel._responseLabel.Text)
        humans.append(NS(Name="AICadetsM2-2", IsAlive=True, IsMine=True))
        time.GameTime = 5.0
        data["AICadetsM2Heartbeat-AICadetsM2-2"] = 5.0
        data["AICadetsM2State-AICadetsM2-2"] = "Explore"
        data["AICadetsM2AckSeq-AICadetsM2-2"] = 1
        panel.RefreshStatus()
        self.assertIn("APPLIED #1", panel._responseLabel.Text)
        self.assertIn("AICadetsM2-2 [Explore]", panel._rosterLabel.Text)
        panel.SelectAll()
        panel.Resupply()
        self.assertEqual(data["AICadetsCmdSequence"], 2)
        self.assertEqual(data["AICadetsCmdMode"], "Resupply")
        self.assertIn("PENDING #2", panel._responseLabel.Text)
        panel.Hold()
        self.assertEqual(data["AICadetsCmdSequence"], 3)
        panel.Engage()
        self.assertEqual(data["AICadetsCmdSequence"], 4)

    def test_m1_only_does_not_appear_controllable(self):
        panel, data, roots, logs, keys, camera, inputs, humans, time = self.make_controller()
        humans.append(NS(Name="AICadetsM1", IsAlive=True, IsMine=True))
        panel.OnGameStart()
        panel.OpenMenu()
        panel.Hold()
        self.assertIn("No owned M2 cadets", panel._rosterLabel.Text)
        self.assertIn("M1 demo bots: 1", panel._rosterLabel.Text)
        self.assertIn("NOT APPLIED #1: no owned M2 cadet", panel._responseLabel.Text)

    def test_terminated_m2_shows_reason_not_pending_forever(self):
        panel, data, roots, logs, keys, camera, inputs, humans, time = self.make_controller()
        panel.OnGameStart()
        panel.OpenMenu()
        humans.append(NS(Name="AICadetsM2-1", IsAlive=True, IsMine=True))
        data["AICadetsM2State-AICadetsM2-1"] = "Done"
        data["AICadetsM2Heartbeat-AICadetsM2-1"] = 2.0
        data["AICadetsM2TerminalReason-AICadetsM2-1"] = "repeated_start"
        panel.Hold()
        self.assertIn("TERMINATED: repeated_start", panel._rosterLabel.Text)
        self.assertIn("NOT APPLIED #1: controller terminated", panel._responseLabel.Text)
        # Do not misclassify a Done cadet as merely missing a heartbeat.
        time.GameTime = 20.0
        panel.RefreshStatus()
        self.assertIn("TERMINATED: repeated_start", panel._rosterLabel.Text)

    def test_absent_cadet_shows_last_terminal_reason_as_history(self):
        panel, data, roots, logs, keys, camera, inputs, humans, time = self.make_controller()
        data["AICadetsM2State-AICadetsM2-1"] = "Done"
        data["AICadetsM2TerminalReason-AICadetsM2-1"] = "invalid_state"
        panel.OnGameStart()
        panel.OpenMenu()
        self.assertIn("Previous M2-1 ended: invalid_state", panel._rosterLabel.Text)

    def test_mark_supply_is_waypoint_not_fake_refill(self):
        panel, data, roots, logs, keys, camera, inputs, humans, time = self.make_controller()
        panel.OnGameStart()
        panel.MarkSupply()
        self.assertEqual(data["AICadetsSupplyRevision"], 1)
        self.assertEqual(data["AICadetsSupplyX"], 10.0)
        self.assertEqual(data["AICadetsSupplyY"], 5.0)
        self.assertEqual(data["AICadetsSupplyZ"], -12.0)
        self.assertNotIn("CurrentGas", data)

    def test_close_and_game_end_restore_controls(self):
        panel, data, roots, logs, keys, camera, inputs, humans, time = self.make_controller()
        panel.OnGameStart()
        panel.OpenMenu()
        panel.OnGameEnd()
        self.assertIsNone(panel._panel)
        self.assertFalse(panel._open)
        self.assertTrue(roots[0].children[0].removed)
        self.assertEqual(camera[-1], ("cursor", False))
        self.assertEqual(inputs[-1], True)
        self.assertIn(("lock", False), camera)

    def test_nonmaster_cannot_create_menu_or_issue_orders(self):
        panel, data, roots, logs, keys, camera, inputs, humans, time = self.make_controller(master=False)
        panel.OnGameStart()
        self.assertEqual(roots, [])
        panel.OnFrame()
        panel.Hold()
        self.assertEqual(data, {})


if __name__ == "__main__":
    unittest.main()
