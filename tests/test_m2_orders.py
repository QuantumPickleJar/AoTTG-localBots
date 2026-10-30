"""Source-driven mock checks of the optional M2 command-panel addon.

These tests execute the translated addon methods, not Unity UI or the AoTTG2
Custom Logic interpreter. In-game widget binding still requires a live test.
"""
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

    def Absolute(self, *args):
        return self

    def Right(self, *args):
        return self

    def Top(self, *args):
        return self

    def Width(self, *args):
        return self

    def Padding(self, *args):
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
        def make_root():
            root = Element()
            roots.append(root)
            return root
        ui = NS(
            VisualElement=lambda: Element(),
            Label=lambda value: Element(value),
            Button=lambda value, callback: NS(Text=value, callback=callback),
            GetRootVisualElement=make_root,
        )
        controller = load_controller(
            {
                "UI": ui,
                "Network": NS(IsMasterClient=master),
                "PersistentData": NS(
                    GetProperty=lambda key, default: persistent.get(key, default),
                    SetProperty=lambda key, value: persistent.__setitem__(key, value),
                ),
                "Game": NS(Print=logs.append),
                "Convert": NS(ToString=str),
            },
            SOURCE,
            class_name="AICadetsCommandPanel",
        )
        return controller, persistent, roots, logs

    def test_master_receives_panel_and_actions(self):
        panel, data, roots, logs = self.make_controller()
        panel.OnGameStart()
        self.assertEqual(len(roots), 1)
        self.assertEqual(len(roots[0].children), 1)
        buttons = [e for e in panel._panel.children if hasattr(e, "callback")]
        self.assertEqual(len(buttons), 8)
        panel.SelectTwo()
        panel.Explore()
        self.assertEqual(data["AICadetsCmdScope"], "AICadetsM2-2")
        self.assertEqual(data["AICadetsCmdMode"], "Explore")
        self.assertEqual(data["AICadetsCmdSequence"], 1)
        panel.SelectAll()
        panel.Hold()
        self.assertEqual(data["AICadetsCmdScope"], "all")
        self.assertEqual(data["AICadetsCmdMode"], "Hold")
        self.assertEqual(data["AICadetsCmdSequence"], 2)
        panel.Engage()
        self.assertEqual(data["AICadetsCmdSequence"], 3)
        self.assertEqual(data["AICadetsCmdMode"], "Engage")
        panel.OnGameEnd()
        self.assertTrue(panel._panel is None)

    def test_nonmaster_has_no_panel_and_no_commands(self):
        panel, data, roots, logs = self.make_controller(master=False)
        panel.OnGameStart()
        self.assertEqual(roots, [])
        panel.Hold()
        self.assertEqual(data, {})

if __name__ == "__main__":
    unittest.main()
