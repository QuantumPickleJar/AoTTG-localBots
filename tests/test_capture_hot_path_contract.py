"""Guard the recorder's fixed-step sampling cost without changing its schema."""
import unittest
from pathlib import Path
import re


PLUGIN = (Path(__file__).resolve().parents[1] /
          "plugin" / "FlightRecorder.UnityIl2Cpp" / "Plugin.cs")
REPO = PLUGIN.parents[2]


class CaptureHotPathContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PLUGIN.read_text()
        cls.package_script = (REPO / "scripts" / "package_flight_recorder.ps1").read_text()
        cls.install_script = (REPO / "scripts" / "install_flight_recorder.ps1").read_text()

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

    def test_entity_transform_and_scene_metadata_are_cached_in_the_sample_loop(self):
        frame = self.source.split("internal FramePayload CaptureFrame(", 1)[1].split("private string? FindId", 1)[0]
        self.assertIn("var transform = entity.Transform;", frame)
        self.assertIn("entity.Transform = transform;", frame)
        self.assertIn("if (entity.SceneHandle != scene.handle)", frame)
        self.assertIn("entity.SceneName = scene.name;", frame)
        self.assertIn("extra.Scene = entity.SceneName;", frame)

    def test_hook_scope_uses_the_cached_owner_id(self):
        owner_filter = self.source.split("private bool IsAllowedForCurrentSample(TrackedEntity entry)", 1)[1].split(
            "private bool IsAllowedForCurrentSample(BaseCharacter character)", 1)[0]
        self.assertIn("entry.OwnerHumanSourceId ?? entry.OwnerSourceId", owner_filter)
        self.assertIn("_captureScopeByCharacter.TryGetValue(sourceId", owner_filter)
        self.assertIn("entry.OwnerCharacter is BaseCharacter owner", owner_filter)

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

    def test_package_and_guarded_installer_target_the_current_plugin_version(self):
        self.assertIn('PluginVersion = "0.1.19"', self.source)
        self.assertIn("$pluginVersion = $versionMatch.Groups[1].Value", self.package_script)
        self.assertIn("plugin_version = $pluginVersion", self.package_script)
        self.assertIn('$packageManifest.plugin_version -ne "0.1.19"', self.install_script)
        self.assertIn('plugin_version = "0.1.19"', self.install_script)

    def test_manual_frame_converter_covers_every_v1_frame_property(self):
        converter = self.source.split("internal sealed class FramePayloadJsonConverter", 1)[1].split(
            "internal struct CaptureStageMeasurement", 1)[0]
        self.assertIn("Converters = { new FramePayloadJsonConverter() }", self.source)
        for class_name, next_class in (
            ("FramePayload", "EntitySamplePayload"),
            ("EntitySamplePayload", "EntityExtraPayload"),
            ("EntityExtraPayload", "LifecyclePayload"),
        ):
            declaration = self.source.split(f"internal sealed class {class_name}", 1)[1].split(
                f"internal sealed class {next_class}", 1)[0]
            names = re.findall(r'JsonPropertyName\("([^"]+)"\)', declaration)
            for name in names:
                self.assertIn(f'"{name}"', converter, f"frame converter omits {class_name}.{name}")

    def test_slow_capture_diagnostic_is_sparse_and_records_operation_identity(self):
        capture = self.source.split("internal FramePayload CaptureFrame(", 1)[1].split(
            "private string? FindId", 1)[0]
        self.assertIn('Event = "capture_slow_operation"', capture)
        self.assertIn('slowestOperation.SlowestElapsedMs >= 5d', capture)
        self.assertIn('TryReserveSlowOperationReport(t)', capture)
        self.assertIn('["operation_group"]', capture)
        self.assertIn('["entity_id"]', capture)


if __name__ == "__main__":
    unittest.main()
