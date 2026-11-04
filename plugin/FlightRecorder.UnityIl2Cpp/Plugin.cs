using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Serialization;
using Aicadets.FlightRecorder.Transport;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Unity.IL2CPP;
using Characters;
using HarmonyLib;
using Photon.Pun;
using Projectiles;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace Aicadets.FlightRecorder.UnityIl2Cpp;

[BepInPlugin(PluginGuid, PluginName, PluginVersion)]
public sealed class FlightRecorderPlugin : BasePlugin
{
    public const string PluginGuid = "org.aicadets.aottg2.flight-recorder";
    public const string PluginName = "AoTTG2 Flight Recorder";
    public const string PluginVersion = "0.1.7";
    private const string RequiredUnityVersion = "2023.1.22f1";
    private const string CapturePhase = "fixed_update_pre_physics_order_unspecified";
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        NumberHandling = JsonNumberHandling.Strict,
    };

    private static FlightRecorderPlugin? _instance;
    private ConfigEntry<bool>? _enableCapture;
    private ConfigEntry<string>? _pipeName;
    private ConfigEntry<double>? _discoveryInterval;
    private ConfigEntry<int>? _maxEntities;
    private ConfigEntry<int>? _queueCapacity;
    private ConfigEntry<int>? _queueBytes;
    private PipePublisher? _publisher;
    private Harmony? _harmony;
    private long _clockOrigin;
    private long _fixedStep;
    private double _nextHealthAt = 5d;
    private readonly double[] _captureWorkWindowMs = new double[256];
    private int _captureWorkCount;
    private int _captureWorkWriteIndex;
    private double _captureWorkLastMs;
    private int _shutdownStarted;
    private bool _captureFailed;

    internal static FlightRecorderPlugin? Instance => _instance;
    internal PipePublisher? Publisher => _publisher;
    internal long FixedStep => _fixedStep;
    internal bool IsCapturing => _publisher is not null && !_captureFailed && Volatile.Read(ref _shutdownStarted) == 0;
    internal int MaxEntities => Math.Clamp(_maxEntities?.Value ?? 512, 1, 4096);
    internal double DiscoveryInterval => _discoveryInterval?.Value ?? 0.5;
    internal static JsonSerializerOptions SerializerOptions => JsonOptions;
    internal void IncrementFixedStep()
    {
        checked { _fixedStep++; }
    }

    public override void Load()
    {
        _instance = this;
        _enableCapture = Config.Bind("Capture", "Enabled", false,
            "Opt in to local recording. Leave false unless the Python receiver is running and this is a private test session.");
        _pipeName = Config.Bind("Transport", "PipeName", "aicadets-flight-recorder-v1",
            "Local Windows named pipe used by the Python Flight Recorder receiver.");
        _discoveryInterval = Config.Bind("Capture", "DiscoveryIntervalSeconds", 0.5d,
            "Interval for actor discovery. Actors are sampled each Unity FixedUpdate after discovery.");
        _maxEntities = Config.Bind("Capture", "MaxTrackedEntities", 512,
            "Hard cap; exceeding it stops capture as incomplete instead of silently omitting entities.");
        _queueCapacity = Config.Bind("Transport", "QueueCapacity", 512,
            "Bounded producer queue entries.");
        _queueBytes = Config.Bind("Transport", "QueueBytes", 4 * 1024 * 1024,
            "Bounded producer queue byte limit.");

        if (!_enableCapture.Value)
        {
            Log.LogInfo("Loaded with capture disabled; no Unity sampler or transport was started.");
            return;
        }

        if (!string.Equals(Application.unityVersion, RequiredUnityVersion, StringComparison.Ordinal))
        {
            Log.LogError($"Capture refused: Unity {Application.unityVersion} does not match audited {RequiredUnityVersion}.");
            return;
        }
        if (RuntimeInformation.ProcessArchitecture != Architecture.X64)
        {
            Log.LogError("Capture refused: this build was compiled for the audited x64 installation.");
            return;
        }

        try
        {
            _clockOrigin = Stopwatch.GetTimestamp();
            var runId = Guid.NewGuid().ToString("N");
            var hello = JsonSerializer.Serialize(new HelloPayload
            {
                WriterSchema = "aicadets.flight.v1",
                Producer = PluginName,
                ProducerVersion = PluginVersion,
                CaptureTier = "partial_il2cpp_periodic_discovery_v1",
                InstalledBuildFingerprint = new { unity_version = Application.unityVersion, architecture = "x64" },
                RuntimeObservationPhase = CapturePhase,
                TimestampClock = "UnityEngine.Time.fixedTimeAsDouble; fixed simulation clock; wall monotonic elapsed is carried separately",
                StepSource = "adapter FixedUpdate callback ordinal",
                DiscoveryIntervalSeconds = Math.Clamp(DiscoveryInterval, 0.2d, 5d),
                DeclaredCoverage = new
                {
                    entity_classes = new[] { "human_local_or_master_ai", "titan_local_or_master_ai", "odm_hook_from_captured_human_hook_lists", "projectile_with_local_or_master_ai_owner" },
                    transforms = new[] { "position", "rotation" },
                    rigidbody = "root Rigidbody only; velocity fields emitted only when present and non-kinematic",
                    game_fields = new[] { "AI", "team", "health", "dead", "grounded", "current_speed", "current_animation", "human_state", "human_current_gas", "titan_state", "hook_state", "hook_anchor", "projectile_velocity_field" },
                    collisions = "Human.OnCollisionEnter Harmony postfix; only locally owned actors or AI on the local Photon master, and non-character world colliders",
                    entity_lifecycle = new { first_seen = "inferred_first_seen_by_periodic_census", destroyed = "observed_unity_object_destroyed", transient_between_censuses = "may_be_missed" },
                    scene_changes = "active scene name and handle compared at each FixedUpdate callback; transition timestamp is sampling time",
                    hook_state_transitions = "sampled Hook.State differences between adjacent adapter callbacks; not a direct hook callback",
                    excluded = new[] { "non-local player-controlled Humans", "AI on non-master clients", "unknown-owner Hooks and projectiles", "moving environment geometry", "structured controller decisions", "unverified collision callback execution" },
                    privacy_filter = "Human/projectile samples require local Photon ownership or AI on the local Photon master; player-vs-player collisions are omitted"
                }
            }, JsonOptions);

            var pipe = string.IsNullOrWhiteSpace(_pipeName.Value) ? "aicadets-flight-recorder-v1" : _pipeName.Value.Trim();
            _publisher = new PipePublisher(pipe, runId, hello,
                queueCapacity: Math.Clamp(_queueCapacity.Value, 64, 4096),
                maxQueueBytes: Math.Clamp(_queueBytes.Value, 512 * 1024, 64 * 1024 * 1024));
            _harmony = new Harmony(PluginGuid);
            _harmony.PatchAll(typeof(FlightRecorderPlugin).Assembly);
            AppDomain.CurrentDomain.ProcessExit += OnProcessExit;
            AddComponent<FlightRecorderDriver>();
            Log.LogInfo($"Opt-in partial capture started; run={runId}, Unity={Application.unityVersion}, pipe={pipe}.");
        }
        catch (Exception exception)
        {
            FailCapture("plugin_startup_exception", exception);
        }
    }

    public override bool Unload()
    {
        AppDomain.CurrentDomain.ProcessExit -= OnProcessExit;
        Shutdown("plugin_unload", waitForDrain: false);
        try { _harmony?.UnpatchSelf(); }
        catch (Exception exception) { Log.LogWarning($"Could not remove Harmony patches during unload: {exception.GetType().Name}"); }
        return true;
    }

    internal double NowSeconds() => Time.fixedTimeAsDouble;

    internal double MonotonicElapsedSeconds() =>
        (Stopwatch.GetTimestamp() - _clockOrigin) / (double)Stopwatch.Frequency;

    internal void RecordCaptureWork(double elapsedMs)
    {
        _captureWorkLastMs = elapsedMs;
        _captureWorkWindowMs[_captureWorkWriteIndex] = elapsedMs;
        _captureWorkWriteIndex = (_captureWorkWriteIndex + 1) % _captureWorkWindowMs.Length;
        _captureWorkCount = Math.Min(_captureWorkCount + 1, _captureWorkWindowMs.Length);
    }

    private (double Last, double P95, double Maximum, int Count) CaptureWorkStatistics()
    {
        if (_captureWorkCount == 0) return (0d, 0d, 0d, 0);
        var ordered = new double[_captureWorkCount];
        var start = _captureWorkCount == _captureWorkWindowMs.Length ? _captureWorkWriteIndex : 0;
        for (var i = 0; i < _captureWorkCount; i++)
            ordered[i] = _captureWorkWindowMs[(start + i) % _captureWorkWindowMs.Length];
        Array.Sort(ordered);
        var p95Index = Math.Max(0, (int)Math.Ceiling(ordered.Length * 0.95d) - 1);
        return (_captureWorkLastMs, ordered[p95Index], ordered[^1], ordered.Length);
    }

    internal bool IsAllowed(BaseCharacter actor)
    {
        if (actor == null) return false;
        return actor.IsMine() || (actor.AI && PhotonNetwork.IsMasterClient);
    }

    internal string? FindEntityId(int instanceId, string? kind = null) =>
        CaptureRegistry.TryFindEntityId(instanceId, kind);

    internal void ReportCollision(Human actor, Collision collision)
    {
        if (!IsCapturing || actor == null || collision == null) return;
        try
        {
            if (!IsAllowed(actor)) return;
            var otherCollider = collision.collider;
            if (otherCollider == null) return;
            var otherCharacter = otherCollider.GetComponentInParent<BaseCharacter>(true);
            if (otherCharacter != null && !IsAllowed(otherCharacter)) return;

            var actorId = FindEntityId(actor.GetInstanceID(), "human");
            var otherId = otherCharacter == null ? null : FindEntityId(otherCharacter.GetInstanceID());
            var relative = collision.relativeVelocity;
            var impulse = collision.impulse;
            var eventPayload = new EventPayload
            {
                Event = "collision",
                T = NowSeconds(),
                Step = _fixedStep,
                Actor = actorId,
                Evidence = "observed",
                Fields = new Dictionary<string, object?>
                {
                    ["callback_type"] = "UnityEngine.Collision",
                    ["callback_source"] = "Characters.Human.OnCollisionEnter(UnityEngine.Collision); Harmony postfix",
                    ["actor_source_instance_id"] = actor.GetInstanceID(),
                    ["relative_velocity"] = new[] { relative.x, relative.y, relative.z },
                    ["impulse"] = new[] { impulse.x, impulse.y, impulse.z },
                    ["contact_count"] = collision.contactCount,
                    ["other_collider_instance_id"] = otherCollider.GetInstanceID(),
                    ["other_collider_layer"] = otherCollider.gameObject.layer,
                    ["other_character_id"] = otherId,
                    ["other_character_class"] = otherCharacter == null ? null : otherCharacter.GetType().FullName,
                }
            };
            if (_publisher?.TryPublishControl("event", JsonSerializer.Serialize(eventPayload, JsonOptions)) != true)
            {
                if (_publisher?.Failure is { } failure)
                    FailCapture("collision_event_transport_failure", new IOException(failure));
            }
        }
        catch (Exception exception)
        {
            FailCapture("collision_callback_capture_exception", exception);
        }
    }

    internal void FailCapture(string reason, Exception exception)
    {
        if (Interlocked.Exchange(ref _shutdownStarted, 1) != 0) return;
        _captureFailed = true;
        var publisher = _publisher;
        Log.LogError($"Capture stopped and will be marked incomplete: {reason}: {exception.GetType().Name}: {exception.Message}; " +
            $"dropped_frames={publisher?.DroppedFrames ?? 0}, dropped_control_messages={publisher?.DroppedControlMessages ?? 0}, " +
            $"queue_depth={publisher?.QueueDepth ?? 0}, queue_bytes={publisher?.QueueBytes ?? 0}, " +
            $"queue_high_water_depth={publisher?.MaxQueueDepth ?? 0}, queue_high_water_bytes={publisher?.MaxQueueBytes ?? 0}");
        var payload = JsonSerializer.Serialize(new StopPayload
        {
            Graceful = false,
            Reason = reason,
            DroppedFrames = publisher?.DroppedFrames ?? 0,
            DroppedControlMessages = publisher?.DroppedControlMessages ?? 0,
            TransportFailure = publisher?.Failure,
            QueueDepth = publisher?.QueueDepth ?? 0,
            QueueBytes = publisher?.QueueBytes ?? 0,
            QueueHighWaterDepth = publisher?.MaxQueueDepth ?? 0,
            QueueHighWaterBytes = publisher?.MaxQueueBytes ?? 0,
        }, JsonOptions);
        publisher?.TryPublishControl("stop", payload);
        if (publisher is not null)
            _ = Task.Run(async () => await publisher.DisposeAsync().ConfigureAwait(false));
    }

    internal void Shutdown(string reason, bool waitForDrain)
    {
        if (Interlocked.Exchange(ref _shutdownStarted, 1) != 0) return;
        if (_publisher is not { } publisher) return;
        Log.LogInfo($"Draining recorder transport during {reason}.");
        var payload = JsonSerializer.Serialize(new StopPayload
        {
            Graceful = !_captureFailed,
            Reason = reason,
            DroppedFrames = publisher.DroppedFrames,
            DroppedControlMessages = publisher.DroppedControlMessages,
            TransportFailure = publisher.Failure,
            QueueDepth = publisher.QueueDepth,
            QueueBytes = publisher.QueueBytes,
            QueueHighWaterDepth = publisher.MaxQueueDepth,
            QueueHighWaterBytes = publisher.MaxQueueBytes,
        }, JsonOptions);
        if (!publisher.TryPublishControl("stop", payload))
        {
            _captureFailed = true;
            Log.LogError("Stop record could not be queued; receiver will treat the closed pipe as incomplete.");
        }

        if (waitForDrain)
        {
            try
            {
                var drained = publisher.StopAndDrainAsync(TimeSpan.FromSeconds(2.5)).GetAwaiter().GetResult();
                if (!drained) Log.LogWarning("Transport did not drain before shutdown deadline; recording is incomplete.");
            }
            catch (Exception exception)
            {
                Log.LogWarning($"Transport shutdown failed: {exception.GetType().Name}");
            }
        }
        else
        {
            _ = Task.Run(async () => await publisher.StopAndDrainAsync(TimeSpan.FromSeconds(2.5)).ConfigureAwait(false));
        }
    }

    internal void OnUnityApplicationQuit() => Shutdown("unity_application_quit", waitForDrain: true);

    private void OnProcessExit(object? sender, EventArgs args) => Shutdown("process_exit", waitForDrain: true);

    internal void CheckTransportHealth()
    {
        if (_publisher?.Failure is { } failure)
            FailCapture("transport_accounting_failure", new IOException(failure));
    }

    internal void PublishHealth(double t, double monotonicElapsed)
    {
        var publisher = _publisher;
        if (publisher is null || publisher.ConnectionAttempts == 0 || publisher.LastConnectionError is not null || t < _nextHealthAt)
            return;
        _nextHealthAt = t + 5d;
        var captureWork = CaptureWorkStatistics();
        var payload = JsonSerializer.Serialize(new HealthPayload
        {
            T = t,
            Step = _fixedStep,
            Evidence = "observed",
            HealthSource = "local PipePublisher counters",
            WallMonotonicElapsedSeconds = monotonicElapsed,
            QueueDepth = publisher.QueueDepth,
            QueueBytes = publisher.QueueBytes,
            QueueHighWaterBytes = publisher.MaxQueueBytes,
            DroppedFrames = publisher.DroppedFrames,
            DroppedControlMessages = publisher.DroppedControlMessages,
            ConnectionAttempts = publisher.ConnectionAttempts,
            CaptureWorkMsLast = captureWork.Last,
            CaptureWorkMsP95 = captureWork.P95,
            CaptureWorkMsMaximum = captureWork.Maximum,
            CaptureWorkSampleCount = captureWork.Count,
        }, JsonOptions);
        if (!publisher.TryPublishControl("health", payload)) CheckTransportHealth();
    }
}

public sealed class FlightRecorderDriver : MonoBehaviour
{
    private CaptureRegistry? _registry;

    public FlightRecorderDriver(IntPtr pointer) : base(pointer) { }

    public void Awake()
    {
        var plugin = FlightRecorderPlugin.Instance;
        if (plugin is null || !plugin.IsCapturing) return;
        _registry = new CaptureRegistry(plugin);
    }

    public void FixedUpdate()
    {
        var plugin = FlightRecorderPlugin.Instance;
        if (plugin is null || !plugin.IsCapturing || _registry is null) return;
        var captureStarted = Stopwatch.GetTimestamp();
        try
        {
            plugin.CheckTransportHealth();
            if (!plugin.IsCapturing) return;
            plugin.IncrementFixedStep();
            _registry.ObserveSceneChange(plugin.FixedStep, plugin.NowSeconds());
            if (!plugin.IsCapturing) return;
            _registry.DiscoverIfDue();
            if (!plugin.IsCapturing) return;
            var frame = _registry.CaptureFrame(plugin.FixedStep, plugin.NowSeconds(), Time.fixedDeltaTime,
                plugin.MonotonicElapsedSeconds());
            var frameCapacityHint = Math.Clamp(2048 + frame.Samples.Length * 1024, 4096, 256 * 1024);
            if (plugin.Publisher?.TryPublishFrame(frame, plugin.FixedStep, frame.T,
                    FlightRecorderPlugin.SerializerOptions, frameCapacityHint) != true)
                plugin.CheckTransportHealth();
            foreach (var observation in _registry.DrainObservationEvents())
            {
                if (plugin.Publisher?.TryPublishControl("event", JsonSerializer.Serialize(observation, FlightRecorderPlugin.SerializerOptions)) != true)
                    plugin.CheckTransportHealth();
            }
            plugin.RecordCaptureWork((Stopwatch.GetTimestamp() - captureStarted) * 1000d / Stopwatch.Frequency);
            plugin.PublishHealth(plugin.NowSeconds(), plugin.MonotonicElapsedSeconds());
        }
        catch (Exception exception)
        {
            plugin.FailCapture("fixed_update_capture_exception", exception);
        }
    }

    public void OnApplicationQuit() => FlightRecorderPlugin.Instance?.OnUnityApplicationQuit();
}

[HarmonyPatch(typeof(Human), nameof(Human.OnCollisionEnter))]
internal static class HumanCollisionPatch
{
    [HarmonyPostfix]
    private static void Postfix(Human __instance, Collision collision) =>
        FlightRecorderPlugin.Instance?.ReportCollision(__instance, collision);
}

internal sealed class CaptureRegistry
{
    private readonly FlightRecorderPlugin _plugin;
    private readonly Dictionary<(string Kind, int SourceId), TrackedEntity> _entities = new();
    private readonly Dictionary<(string Kind, int SourceId), int> _generations = new();
    private readonly Dictionary<int, string> _idsByInstance = new();
    private readonly List<TrackedEntity> _ordered = new();
    private readonly List<EventPayload> _observationEvents = new();
    private double _nextDiscoveryAt;
    private int _activeSceneHandle;
    private string _activeSceneName = "";

    internal CaptureRegistry(FlightRecorderPlugin plugin)
    {
        _plugin = plugin;
        var scene = SceneManager.GetActiveScene();
        _activeSceneHandle = scene.handle;
        _activeSceneName = scene.name;
        _active = this;
    }

    internal void ObserveSceneChange(long step, double t)
    {
        var scene = SceneManager.GetActiveScene();
        if (scene.handle == _activeSceneHandle && string.Equals(scene.name, _activeSceneName, StringComparison.Ordinal)) return;
        _observationEvents.Add(new EventPayload
        {
            Event = "active_scene_sampled_change",
            T = t,
            Step = step,
            Evidence = "sampled_active_scene_change_between_fixed_update_callbacks",
            Fields = new Dictionary<string, object?>
            {
                ["previous_scene_name"] = _activeSceneName,
                ["previous_scene_handle"] = _activeSceneHandle,
                ["active_scene_name"] = scene.name,
                ["active_scene_handle"] = scene.handle,
                ["observation_mode"] = "active_scene_poll_at_adapter_fixed_update",
            }
        });
        _activeSceneHandle = scene.handle;
        _activeSceneName = scene.name;
    }

    internal EventPayload[] DrainObservationEvents()
    {
        if (_observationEvents.Count == 0) return Array.Empty<EventPayload>();
        var result = _observationEvents.ToArray();
        _observationEvents.Clear();
        return result;
    }

    internal static string? TryFindEntityId(int instanceId, string? kind)
    {
        var registry = FlightRecorderDriverRegistry;
        if (registry is null) return null;
        if (kind is not null && registry._entities.TryGetValue((kind, instanceId), out var typed)) return typed.Id;
        return registry._idsByInstance.TryGetValue(instanceId, out var entityId) ? entityId : null;
    }

    private static CaptureRegistry? FlightRecorderDriverRegistry => _active;
    private static CaptureRegistry? _active;

    internal void DiscoverIfDue()
    {
        var now = _plugin.NowSeconds();
        if (now < _nextDiscoveryAt) return;
        _nextDiscoveryAt = now + Math.Clamp(_plugin.DiscoveryInterval, 0.2d, 5d);

        var observed = new HashSet<(string Kind, int SourceId)>();
        foreach (var human in Object.FindObjectsOfType<Human>(true))
        {
            if (!_plugin.IsCapturing) return;
            if (human == null || !_plugin.IsAllowed(human) || !human.FinishSetup) continue;
            Track(human, "human", observed);
            if (!_plugin.IsCapturing) return;
            TrackHooks(human, observed);
        }
        foreach (var titan in Object.FindObjectsOfType<BaseTitan>(true))
        {
            if (!_plugin.IsCapturing) return;
            if (titan == null || !_plugin.IsAllowed(titan)) continue;
            Track(titan, "titan", observed);
        }
        foreach (var projectile in Object.FindObjectsOfType<BaseProjectile>(true))
        {
            if (!_plugin.IsCapturing) return;
            if (projectile == null) continue;
            var owner = projectile._owner;
            if (owner == null || !_plugin.IsAllowed(owner)) continue;
            Track(projectile, "projectile", observed, owner.GetInstanceID());
        }

        foreach (var entry in _entities.Values.ToArray())
        {
            if (entry.Component == null)
            {
                PublishLifecycle("despawn", entry, "observed_unity_object_destroyed", now);
                _entities.Remove((entry.Kind, entry.SourceId));
                _idsByInstance.Remove(entry.SourceId);
            }
            else if (!StillWithinCaptureScope(entry))
            {
                PublishLifecycle("despawn", entry, "capture_scope_ended_ownership_filter", now);
                _entities.Remove((entry.Kind, entry.SourceId));
                _idsByInstance.Remove(entry.SourceId);
            }
        }
        _ordered.Clear();
        _ordered.AddRange(_entities.Values);
        _ordered.Sort(static (left, right) => string.CompareOrdinal(left.Id, right.Id));
        _active = this;

        if (_entities.Count > _plugin.MaxEntities)
            _plugin.FailCapture("tracked_entity_limit_exceeded", new InvalidOperationException($"tracked={_entities.Count}, limit={_plugin.MaxEntities}"));
    }

    private void TrackHooks(Human owner, HashSet<(string Kind, int SourceId)> observed)
    {
        TrackHookList(owner.HookLeft, owner, observed);
        TrackHookList(owner.HookRight, owner, observed);
    }

    private void TrackHookList(HookUseable? useable, Human owner, HashSet<(string Kind, int SourceId)> observed)
    {
        if (useable == null || useable.Hooks == null) return;
        var hooks = useable.Hooks;
        for (var i = 0; i < hooks.Count; i++)
        {
            if (!_plugin.IsCapturing) return;
            var hook = hooks[i];
            if (hook == null) continue;
            Track(hook, "odm_hook", observed, owner.GetInstanceID(), owner.GetInstanceID());
        }
    }

    private void Track(Component component, string kind, HashSet<(string Kind, int SourceId)> observed,
        int? ownerSourceId = null, int? ownerHumanSourceId = null)
    {
        var sourceId = component.GetInstanceID();
        var key = (kind, sourceId);
        observed.Add(key);
        if (_entities.TryGetValue(key, out var priorEntry) && priorEntry.Component == null)
        {
            PublishLifecycle("despawn", priorEntry, "observed_unity_object_destroyed_before_instance_id_reuse", _plugin.NowSeconds());
            _entities.Remove(key);
            _idsByInstance.Remove(sourceId);
        }
        if (!_entities.TryGetValue(key, out var entry))
        {
            if (_entities.Count >= _plugin.MaxEntities)
            {
                _plugin.FailCapture("tracked_entity_limit_exceeded",
                    new InvalidOperationException($"tracked={_entities.Count + 1}, limit={_plugin.MaxEntities}"));
                return;
            }
            var generationKey = key;
            var generation = _generations.TryGetValue(generationKey, out var prior) ? prior + 1 : 1;
            _generations[generationKey] = generation;
            entry = new TrackedEntity
            {
                Component = component,
                Kind = kind,
                SourceId = sourceId,
                Generation = generation,
                Id = $"{kind}:instance-{sourceId}:{generation}",
                ClassName = component.GetType().FullName ?? component.GetType().Name,
                OwnerSourceId = ownerSourceId,
                OwnerHumanSourceId = ownerHumanSourceId,
                OwnerCharacter = component is BaseProjectile projectile ? projectile._owner : null,
            };
            try { entry.RootRigidbody = component.GetComponent<Rigidbody>(); }
            catch (Exception exception) { _plugin.FailCapture("rigidbody_lookup_failed", exception); return; }
            _entities.Add(key, entry);
            _idsByInstance[sourceId] = entry.Id;
            PublishLifecycle("spawn", entry, "inferred_first_seen_by_periodic_census", _plugin.NowSeconds());
        }
        else
        {
            entry.Component = component;
            entry.OwnerSourceId = ownerSourceId ?? entry.OwnerSourceId;
            entry.OwnerHumanSourceId = ownerHumanSourceId ?? entry.OwnerHumanSourceId;
            if (component is BaseProjectile projectile) entry.OwnerCharacter = projectile._owner;
            if (entry.RootRigidbody == null)
            {
                try { entry.RootRigidbody = component.GetComponent<Rigidbody>(); }
                catch (Exception exception) { _plugin.FailCapture("rigidbody_lookup_failed", exception); }
            }
        }
        if (component is Hook && ownerHumanSourceId is { } hookOwnerId &&
            _entities.TryGetValue(("human", hookOwnerId), out var hookOwner))
            entry.OwnerCharacter = hookOwner.Component as BaseCharacter;
    }

    private void PublishLifecycle(string action, TrackedEntity entry, string evidence, double t)
    {
        var payload = JsonSerializer.Serialize(new LifecyclePayload
        {
            Action = action,
            Id = entry.Id,
            Kind = entry.Kind,
            T = t,
            Step = _plugin.FixedStep,
            Evidence = evidence,
        }, FlightRecorderPlugin.SerializerOptions);
        if (_plugin.Publisher?.TryPublishControl("lifecycle", payload) != true)
            _plugin.CheckTransportHealth();
    }

    internal FramePayload CaptureFrame(long step, double t, float fixedDeltaTime, double monotonicElapsed)
    {
        var samples = new List<EntitySamplePayload>(_ordered.Count);
        foreach (var entity in _ordered)
        {
            var component = entity.Component;
            if (component == null) continue;
            if (!StillWithinCaptureScope(entity)) continue;
            if (component is Human pendingHuman && !pendingHuman.FinishSetup) continue;
            var transform = component.transform;
            var position = transform.position;
            var rotation = transform.rotation;
            var sample = new EntitySamplePayload
            {
                Id = entity.Id,
                Kind = entity.Kind,
                Pos = new[] { position.x, position.y, position.z },
                Rot = new[] { rotation.x, rotation.y, rotation.z, rotation.w },
                Extra = new Dictionary<string, object?>
                {
                    ["entity_class"] = entity.ClassName,
                    ["source_instance_id"] = entity.SourceId,
                    ["scene"] = component.gameObject.scene.name,
                    ["owner_id"] = entity.OwnerSourceId is { } ownerId ? FindId(ownerId) : null,
                    ["pose_source"] = "UnityEngine.Transform",
                    ["wall_monotonic_elapsed_seconds"] = monotonicElapsed,
                }
            };

            var body = entity.RootRigidbody;
            if (body != null)
            {
                var kinematic = body.isKinematic;
                sample.Extra["motion_mode"] = kinematic ? "root_rigidbody_kinematic" : "root_rigidbody_dynamic";
                sample.Extra["rigidbody_source"] = "Component.GetComponent<Rigidbody> on root object";
                if (!kinematic)
                {
                    var velocity = body.velocity;
                    var angularVelocity = body.angularVelocity;
                    sample.Vel = new[] { velocity.x, velocity.y, velocity.z };
                    sample.AngVel = new[] { angularVelocity.x, angularVelocity.y, angularVelocity.z };
                    sample.Extra["velocity_source"] = "UnityEngine.Rigidbody.velocity";
                    sample.Extra["angular_velocity_source"] = "UnityEngine.Rigidbody.angularVelocity";
                }
            }
            else
            {
                sample.Extra["motion_mode"] = "root_transform_no_rigidbody";
                sample.Extra["velocity_unavailable_reason"] = "no root Rigidbody component found";
            }

            if (component is BaseCharacter character)
            {
                sample.Extra["ai_controlled"] = character.AI;
                sample.Extra["team"] = character.Team;
                sample.Extra["current_health"] = character.CurrentHealth;
                sample.Extra["dead_flag"] = character.Dead;
                sample.Extra["grounded_game_field"] = character.Grounded;
                sample.Extra["current_speed_game_field"] = character.CurrentSpeed;
                sample.Extra["animation_game_method"] = character.GetCurrentAnimation();
                if (character is Human human)
                {
                    sample.State = human.State.ToString();
                    if (human.Stats != null)
                    {
                        sample.Extra["current_gas_game_property"] = human.Stats.CurrentGas;
                        sample.Extra["max_gas_game_property"] = human.Stats.MaxGas;
                    }
                }
                else if (character is BaseTitan titan)
                {
                    sample.State = titan.State.ToString();
                }
            }
            else if (component is Hook hook)
            {
                var hookState = hook.State.ToString();
                sample.State = hookState;
                if (entity.LastSampledState is { } previousState && !string.Equals(previousState, hookState, StringComparison.Ordinal))
                {
                    _observationEvents.Add(new EventPayload
                    {
                        Event = "hook_state_sampled_change",
                        T = t,
                        Step = step,
                        Actor = entity.Id,
                        Evidence = "sampled_Hook.State_difference_between_adjacent_FixedUpdate_callbacks",
                        Fields = new Dictionary<string, object?>
                        {
                            ["previous_state"] = previousState,
                            ["current_state"] = hookState,
                            ["observation_mode"] = "sampled_game_field_transition; not a direct hook callback",
                        }
                    });
                }
                entity.LastSampledState = hookState;
                var hookPoint = hook.GetHookPosition();
                sample.Extra["hook_point_game_method"] = new[] { hookPoint.x, hookPoint.y, hookPoint.z };
                sample.Extra["hook_state_source"] = "Characters.Hook.State";
                var anchor = hook.Anchor;
                if (anchor != null)
                {
                    var anchorPosition = anchor.position;
                    sample.Extra["anchor_transform_position"] = new[] { anchorPosition.x, anchorPosition.y, anchorPosition.z };
                }
                var target = hook.HookCharacter;
                if (target != null && _plugin.IsAllowed(target))
                    sample.Extra["hook_character_id"] = FindId(target.GetInstanceID());
            }
            else if (component is BaseProjectile projectile)
            {
                sample.Extra["projectile_team_game_property"] = projectile._team;
                var gameVelocity = projectile._velocity;
                sample.Extra["projectile_velocity_game_property"] = new[] { gameVelocity.x, gameVelocity.y, gameVelocity.z };
                sample.Extra["projectile_velocity_provenance"] = "Projectiles.BaseProjectile._velocity; not substituted for Rigidbody.velocity";
            }
            samples.Add(sample);
        }
        return new FramePayload
        {
            Step = step,
            T = t,
            Phase = "fixed_update_pre_physics_order_unspecified",
            FixedDeltaTime = fixedDeltaTime,
            Samples = samples.ToArray(),
        };
    }

    private string? FindId(int sourceId) => _idsByInstance.TryGetValue(sourceId, out var id) ? id : null;

    private bool StillWithinCaptureScope(TrackedEntity entry)
    {
        if (entry.Component is BaseCharacter character) return _plugin.IsAllowed(character);
        if (entry.Component is Hook) return entry.OwnerCharacter != null && _plugin.IsAllowed(entry.OwnerCharacter);
        if (entry.Component is BaseProjectile projectile)
        {
            var owner = projectile._owner;
            return owner != null && _plugin.IsAllowed(owner);
        }
        return false;
    }
}

internal sealed class TrackedEntity
{
    internal Component Component { get; set; } = null!;
    internal string Kind { get; init; } = "";
    internal int SourceId { get; init; }
    internal int Generation { get; init; }
    internal string Id { get; init; } = "";
    internal string ClassName { get; init; } = "";
    internal int? OwnerSourceId { get; set; }
    internal int? OwnerHumanSourceId { get; set; }
    internal BaseCharacter? OwnerCharacter { get; set; }
    internal Rigidbody? RootRigidbody { get; set; }
    internal string? LastSampledState { get; set; }
}

internal sealed class HelloPayload
{
    [JsonPropertyName("writer_schema")] public string WriterSchema { get; init; } = "";
    [JsonPropertyName("producer")] public string Producer { get; init; } = "";
    [JsonPropertyName("producer_version")] public string ProducerVersion { get; init; } = "";
    [JsonPropertyName("capture_tier")] public string CaptureTier { get; init; } = "";
    [JsonPropertyName("installed_build_fingerprint")] public object? InstalledBuildFingerprint { get; init; }
    [JsonPropertyName("runtime_observation_phase")] public string RuntimeObservationPhase { get; init; } = "";
    [JsonPropertyName("timestamp_clock")] public string TimestampClock { get; init; } = "";
    [JsonPropertyName("step_source")] public string StepSource { get; init; } = "";
    [JsonPropertyName("discovery_interval_seconds")] public double DiscoveryIntervalSeconds { get; init; }
    [JsonPropertyName("declared_coverage")] public object? DeclaredCoverage { get; init; }
}

internal sealed class FramePayload
{
    [JsonPropertyName("step")] public long Step { get; init; }
    [JsonPropertyName("t")] public double T { get; init; }
    [JsonPropertyName("phase")] public string Phase { get; init; } = "";
    [JsonPropertyName("fixed_delta_time")] public float FixedDeltaTime { get; init; }
    [JsonPropertyName("samples")] public EntitySamplePayload[] Samples { get; init; } = Array.Empty<EntitySamplePayload>();
}

internal sealed class EntitySamplePayload
{
    [JsonPropertyName("id")] public string Id { get; init; } = "";
    [JsonPropertyName("kind")] public string Kind { get; init; } = "";
    [JsonPropertyName("pos")] public float[] Pos { get; init; } = Array.Empty<float>();
    [JsonPropertyName("vel")] public float[]? Vel { get; set; }
    [JsonPropertyName("rot")] public float[]? Rot { get; init; }
    [JsonPropertyName("ang_vel")] public float[]? AngVel { get; set; }
    [JsonPropertyName("state")] public string? State { get; set; }
    [JsonPropertyName("extra")] public Dictionary<string, object?> Extra { get; init; } = new();
}

internal sealed class LifecyclePayload
{
    [JsonPropertyName("action")] public string Action { get; init; } = "";
    [JsonPropertyName("id")] public string Id { get; init; } = "";
    [JsonPropertyName("kind")] public string Kind { get; init; } = "";
    [JsonPropertyName("t")] public double T { get; init; }
    [JsonPropertyName("step")] public long Step { get; init; }
    [JsonPropertyName("evidence")] public string Evidence { get; init; } = "";
}

internal sealed class EventPayload
{
    [JsonPropertyName("event")] public string Event { get; init; } = "";
    [JsonPropertyName("t")] public double T { get; init; }
    [JsonPropertyName("step")] public long Step { get; init; }
    [JsonPropertyName("actor")] public string? Actor { get; init; }
    [JsonPropertyName("evidence")] public string Evidence { get; init; } = "";
    [JsonPropertyName("fields")] public Dictionary<string, object?> Fields { get; init; } = new();
}

internal sealed class StopPayload
{
    [JsonPropertyName("graceful")] public bool Graceful { get; init; }
    [JsonPropertyName("reason")] public string Reason { get; init; } = "";
    [JsonPropertyName("dropped_frames")] public long DroppedFrames { get; init; }
    [JsonPropertyName("dropped_control_messages")] public long DroppedControlMessages { get; init; }
    [JsonPropertyName("transport_failure")] public string? TransportFailure { get; init; }
    [JsonPropertyName("queue_depth")] public int QueueDepth { get; init; }
    [JsonPropertyName("queue_bytes")] public int QueueBytes { get; init; }
    [JsonPropertyName("queue_high_water_depth")] public int QueueHighWaterDepth { get; init; }
    [JsonPropertyName("queue_high_water_bytes")] public int QueueHighWaterBytes { get; init; }
}

internal sealed class HealthPayload
{
    [JsonPropertyName("t")] public double T { get; init; }
    [JsonPropertyName("step")] public long Step { get; init; }
    [JsonPropertyName("evidence")] public string Evidence { get; init; } = "";
    [JsonPropertyName("health_source")] public string HealthSource { get; init; } = "";
    [JsonPropertyName("wall_monotonic_elapsed_seconds")] public double WallMonotonicElapsedSeconds { get; init; }
    [JsonPropertyName("queue_depth")] public int QueueDepth { get; init; }
    [JsonPropertyName("queue_bytes")] public int QueueBytes { get; init; }
    [JsonPropertyName("queue_high_water_bytes")] public int QueueHighWaterBytes { get; init; }
    [JsonPropertyName("dropped_frames")] public long DroppedFrames { get; init; }
    [JsonPropertyName("dropped_control_messages")] public long DroppedControlMessages { get; init; }
    [JsonPropertyName("connection_attempts")] public int ConnectionAttempts { get; init; }
    [JsonPropertyName("capture_work_ms_last")] public double CaptureWorkMsLast { get; init; }
    [JsonPropertyName("capture_work_ms_p95")] public double CaptureWorkMsP95 { get; init; }
    [JsonPropertyName("capture_work_ms_maximum")] public double CaptureWorkMsMaximum { get; init; }
    [JsonPropertyName("capture_work_sample_count")] public int CaptureWorkSampleCount { get; init; }
}
