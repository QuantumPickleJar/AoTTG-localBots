"""Source checks for the isolated M3 probe; this is not the AoTTG2 interpreter."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from cl_harness import translate  # noqa: E402

PROBE = ROOT / "addons/AICadetsPrimitiveProbe.cl"
OBSERVER = ROOT / "addons/AICadetsPrimitiveObserver.cl"


def validate(probe=None, observer=None):
    probe = PROBE.read_text(encoding="utf-8") if probe is None else probe
    observer = OBSERVER.read_text(encoding="utf-8") if observer is None else observer
    for source, name in ((probe, "AICadetsPrimitiveProbe"),
                         (observer, "AICadetsPrimitiveObserver")):
        tree = __import__("ast").parse(translate(source))
        assert tree.body and tree.body[0].name == name
        for forbidden in (".Position =", ".Velocity =", ".CurrentGas =", ".Health =",
                          ".CurrentSpecial =", "ActivateSpecial(", "Teleport(", "SendMessage(", "Upload("):
            assert forbidden not in source, f"Forbidden mutation or transmission in {name}: {forbidden}"
    assert "RunTest = false;" in probe
    assert "RunObserver = false;" in observer
    assert probe.count("Game.SpawnHumanAt(") == 1, "Primitive probe must spawn at most one test actor"
    assert "self._scout.Dodge();" in probe
    assert "self._scout.Jump();" in probe
    assert probe.count("self._scout.Dash(") >= 5, "Expected four directional dashes and airborne dash"
    assert "self._scout.UseGas(false);" in probe, "Gas input needs cleanup"
    assert "self._scout.ReleaseHookLeft();" in probe, "Hook input needs cleanup"
    assert "self._moveDuration > 1.0" in probe and "self._moveDuration = 1.0;" in probe
    assert "self._observeDuration > 3.0" in probe and "self._observeDuration = 3.0;" in probe
    assert "Time.GameTime + 0.1" in observer, "Fallback observer must have an explicit bounded sample interval"
    assert re.search(r"if \(self\._records >= 600\)\s*$", observer, re.MULTILINE), "Fallback observer must have a record cap of 600"
    assert "AICadetsPrimitiveViewID" in observer and "human.IsMine" in observer
    assert "CurrentAnimation" in observer and "Velocity" in observer and "CurrentGas" in observer


def main():
    validate()
    print("M3 primitive probe source checks passed.")
    print("This does not validate Custom Logic parsing, physics, callbacks, ownership, or in-game behavior.")


if __name__ == "__main__":
    main()
