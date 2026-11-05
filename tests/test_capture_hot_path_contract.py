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
        frame = self.source.split("internal FramePayload CaptureFrame(", 1)[1].split("private string? FindId", 1)[0]
        self.assertIn("_captureScopeStep = step;", frame)
        self.assertNotIn("_captureScopeByCharacter.Clear();", frame)
        self.assertIn("cached.Step == _captureScopeStep", self.source)
        self.assertIn("IsAllowedForCurrentSample(BaseCharacter character)", self.source)
        self.assertIn("var allowed = _plugin.IsAllowed(character);", self.source)

    def test_frame_buffer_hint_tracks_observed_v1_sample_size(self):
        self.assertIn("Math.Clamp(1024 + frame.Samples.Count * 640, 4096, 256 * 1024)", self.source)

    def test_capture_work_includes_periodic_health_publication(self):
        fixed_update = self.source.split("public void FixedUpdate()", 1)[1].split("public void OnApplicationQuit", 1)[0]
        self.assertIn("transportWorkMs += (Stopwatch.GetTimestamp() - stageStarted)", fixed_update)
        self.assertLess(fixed_update.index("plugin.PublishHealth("), fixed_update.index("plugin.RecordCaptureWork("))

    def test_enum_state_names_are_cached_until_the_underlying_value_changes(self):
        self.assertIn("LastSampledStateCode", self.source)
        self.assertIn("currentHookState.GetHashCode()", self.source)
        self.assertIn("entity.LastSampledStateCode != hookStateCode", self.source)

    def test_disabled_hooks_keep_state_sampling_without_anchor_queries(self):
        hook = self.source.split("else if (component is Hook hook)", 1)[1].split(
            "else if (component is BaseProjectile projectile)", 1)[0]
        self.assertIn("var currentHookState = hook.State;", hook)
        self.assertIn("sample.State = entity.LastSampledState;", hook)
        self.assertIn('extra.HookStateSource = "Characters.Hook.State";', hook)
        disabled_guard = hook.index('if (sample.State != "Disabled")')
        self.assertLess(disabled_guard, hook.index("hook.GetHookPosition()"))
        self.assertLess(disabled_guard, hook.index("hook.Anchor"))
        self.assertLess(disabled_guard, hook.index("hook.HookCharacter"))

    def test_periodic_discovery_excludes_inactive_scene_objects(self):
        self.assertEqual(self.source.count("FindObjectsInactive.Exclude, FindObjectsSortMode.None"), 2)
        self.assertNotIn("FindObjectsInactive.Include, FindObjectsSortMode.None", self.source)


if __name__ == "__main__":
    unittest.main()
