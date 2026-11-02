"""The primitive probe is source-checked, not executed as game code."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_primitive_probe import validate  # noqa: E402


class PrimitiveProbeTests(unittest.TestCase):
    def test_probe_and_observer_meet_static_contract(self):
        validate()

    def test_rejects_position_or_velocity_cheats(self):
        probe = (ROOT / "addons/AICadetsPrimitiveProbe.cl").read_text()
        with self.assertRaises(AssertionError):
            validate(probe.replace("self._scout.Dodge();", "self._scout.Position = Vector3(0.0, 0.0, 0.0);"))

    def test_rejects_enabled_by_default_or_unbounded_observer(self):
        probe = (ROOT / "addons/AICadetsPrimitiveProbe.cl").read_text()
        observer = (ROOT / "addons/AICadetsPrimitiveObserver.cl").read_text()
        with self.assertRaises((AssertionError, SyntaxError)):
            validate(probe.replace("RunTest = false;", "RunTest = true;"), observer)
        with self.assertRaises(AssertionError):
            validate(probe, observer.replace("self._records >= 600", "self._records >= 6000"))


if __name__ == "__main__":
    unittest.main()
