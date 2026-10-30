"""Ensure the inexpensive validator catches representative API regressions."""
import sys
import unittest

from cl_harness import ROOT, SOURCE

sys.path.insert(0, str(ROOT / "scripts"))
from check_traversal import validate


class StaticChecksTests(unittest.TestCase):
    def test_current_script(self):
        validate(SOURCE.read_text())

    def test_api_and_structure_mutations_are_rejected(self):
        source = SOURCE.read_text()
        for old, new in (("UseGas(true)", "UseGas(true, false)"),
                         ("LaunchHookLeft(self._anchor)", "LaunchLeftHook(self._anchor)"),
                         (".LeftHookReady", ".IsLeftHookReady"),
                         ("self.Enter(\"Coast\")", "self.Enter()"),
                         ("LoadoutEnum.HumanBlades", "LoadoutEnum.Blades"),
                         ("return false;", "return false")):
            with self.subTest(new=new):
                self.assertIn(old, source)
                with self.assertRaises((AssertionError, SyntaxError)):
                    validate(source.replace(old, new))


if __name__ == "__main__":
    unittest.main()
