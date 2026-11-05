"""Guard the recorder's fixed-step sampling cost without changing its schema."""
import unittest
from pathlib import Path


PLUGIN = (Path(__file__).resolve().parents[1] /
          "plugin" / "FlightRecorder.UnityIl2Cpp" / "Plugin.cs")


class CaptureHotPathContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PLUGIN.read_text()

    def test_animation_sampling_cadence_is_explicit_in_the_v1_payload(self):
        self.assertIn("AnimationSampleIntervalFixedSteps = 5", self.source)
        self.assertIn("animation_source_step", self.source)
        self.assertIn("game_field_sampling", self.source)
        self.assertIn("step - entity.AnimationSampleStep >= FlightRecorderPlugin.AnimationSampleIntervalFixedSteps", self.source)

    def test_scope_cache_is_per_fixed_step(self):
        self.assertIn("_captureScopeByCharacter.Clear();", self.source)
        self.assertIn("IsAllowedForCurrentSample(BaseCharacter character)", self.source)
        self.assertIn("allowed = _plugin.IsAllowed(character);", self.source)

    def test_enum_state_names_are_cached_until_the_underlying_value_changes(self):
        self.assertIn("LastSampledStateCode", self.source)
        self.assertIn("currentHookState.GetHashCode()", self.source)
        self.assertIn("entity.LastSampledStateCode != hookStateCode", self.source)


if __name__ == "__main__":
    unittest.main()
