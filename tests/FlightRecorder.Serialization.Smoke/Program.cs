using System.Diagnostics;
using System.Buffers;
using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using System.Text.Json.Serialization;

if (args.Length != 2)
    throw new ArgumentException("Usage: FlightRecorder.Serialization.Smoke <plugin-dll> <game-root>");

var pluginPath = Path.GetFullPath(args[0]);
var gameRoot = Path.GetFullPath(args[1]);
var pluginOutput = Path.GetDirectoryName(pluginPath)!;
var searchPaths = new[]
{
    pluginOutput,
    Path.Combine(gameRoot, "BepInEx", "core"),
    Path.Combine(gameRoot, "BepInEx", "interop"),
};
AssemblyLoadContext.Default.Resolving += (_, name) =>
{
    foreach (var directory in searchPaths)
    {
        var candidate = Path.Combine(directory, name.Name + ".dll");
        if (File.Exists(candidate)) return AssemblyLoadContext.Default.LoadFromAssemblyPath(candidate);
    }
    return null;
};

var assembly = AssemblyLoadContext.Default.LoadFromAssemblyPath(pluginPath);
const string ns = "Aicadets.FlightRecorder.UnityIl2Cpp.";
var frameType = RequiredType(assembly, ns + "FramePayload");
var sampleType = RequiredType(assembly, ns + "EntitySamplePayload");
var extraType = RequiredType(assembly, ns + "EntityExtraPayload");
var converterType = RequiredType(assembly, ns + "FramePayloadJsonConverter");
var frame = Activator.CreateInstance(frameType, nonPublic: true)!;
Set(frame, "Step", 250L);
Set(frame, "T", 5.0d);
Set(frame, "Phase", "fixed_update_pre_physics");
Set(frame, "FixedDeltaTime", 0.02f);

var samples = Activator.CreateInstance(typeof(List<>).MakeGenericType(sampleType))!;
var addSample = samples.GetType().GetMethod("Add")!;
for (var i = 0; i < 21; i++)
{
    var kind = i == 0 ? "human" : i == 1 ? "titan" : "odm_hook";
    var sample = Activator.CreateInstance(sampleType, nonPublic: true)!;
    Set(sample, "Id", $"{kind}:instance-{1000 + i}:1");
    Set(sample, "Kind", kind);
    FillArray(sample, "Pos", new[] { i * 1.25f, 10.06f, -i * 2.5f });
    FillArray(sample, "Rot", new[] { 0.0f, 0.1f, 0.0f, 0.995f });
    Set(sample, "Vel", new[] { 1.0f, 2.0f, 3.0f });
    Set(sample, "AngVel", new[] { 0.1f, 0.2f, 0.3f });
    Set(sample, "State", i == 0 ? "Land" : i == 1 ? "Walk" : "Disabled");

    var extra = Activator.CreateInstance(extraType, nonPublic: true)!;
    Set(extra, "EntityClass", i == 0 ? "Characters.Human" : i == 1 ? "Characters.Titan" : "Characters.Hook");
    Set(extra, "SourceInstanceId", 1000 + i);
    Set(extra, "Scene", "City");
    Set(extra, "OwnerId", i > 1 ? "human:instance-1000:1" : null);
    Set(extra, "PoseSource", "UnityEngine.Transform");
    Set(extra, "WallMonotonicElapsedSeconds", 5.0d);
    Set(extra, "MotionMode", "root_rigidbody_dynamic");
    Set(extra, "RigidbodySource", "Component.GetComponent<Rigidbody> on root object");
    Set(extra, "VelocitySource", "UnityEngine.Rigidbody.velocity");
    Set(extra, "AngularVelocitySource", "UnityEngine.Rigidbody.angularVelocity");
    Set(extra, "AiControlled", i != 1);
    Set(extra, "Team", "Human");
    Set(extra, "CurrentHealth", 100.0f);
    Set(extra, "DeadFlag", false);
    Set(extra, "GroundedGameField", i == 0);
    Set(extra, "CurrentSpeedGameField", 6.25f);
    Set(extra, "AnimationGameMethod", "Armature|idle");
    Set(extra, "AnimationSourceStep", 250L);
    if (i == 0)
    {
        Set(extra, "CurrentGasGameProperty", 110.0f);
        Set(extra, "MaxGasGameProperty", 120.0f);
    }
    if (i == 2)
    {
        Set(extra, "HookStateSource", "Characters.Hook.State");
        Invoke(extra, "SetHookPoint", 12.5f, 22.0f, -4.0f);
        Invoke(extra, "SetAnchorPosition", 10.0f, 20.0f, -5.0f);
        Set(extra, "HookCharacterId", "titan:instance-1001:1");
    }
    if (i == 20)
    {
        Set(extra, "ProjectileTeamGameProperty", 1);
        Invoke(extra, "SetProjectileVelocity", 30.0f, -5.0f, 4.0f);
        Set(extra, "ProjectileVelocityProvenance", "Projectiles.BaseProjectile._velocity");
    }
    Set(sample, "Extra", extra);
    addSample.Invoke(samples, new object?[] { sample });
}
Set(frame, "Samples", samples);

var baselineOptions = new JsonSerializerOptions
{
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    NumberHandling = JsonNumberHandling.Strict,
};
var manualOptions = new JsonSerializerOptions(baselineOptions);
manualOptions.Converters.Add((JsonConverter)Activator.CreateInstance(converterType, nonPublic: true)!);
var outputBuffer = new ArrayBufferWriter<byte>(32 * 1024);
var baseline = Serialize(frame, frameType, baselineOptions, outputBuffer);
var manual = Serialize(frame, frameType, manualOptions, outputBuffer);
if (!string.Equals(baseline, manual, StringComparison.Ordinal))
    throw new InvalidOperationException("Manual frame JSON differs from the default v1 DTO serialization.");

const int iterations = 5000;
for (var i = 0; i < 300; i++)
{
    Write(frame, frameType, baselineOptions, outputBuffer);
    Write(frame, frameType, manualOptions, outputBuffer);
}
var baselineMs = Measure(frame, frameType, baselineOptions, outputBuffer, iterations);
var manualMs = Measure(frame, frameType, manualOptions, outputBuffer, iterations);
Console.WriteLine($"schema_equivalent=true samples=21 bytes={System.Text.Encoding.UTF8.GetByteCount(manual)} iterations={iterations}");
Console.WriteLine($"default_serializer_ms={baselineMs:F2} manual_converter_ms={manualMs:F2} speedup={baselineMs / manualMs:F2}x");
Console.WriteLine("This microbenchmark is offline serializer evidence only; it is not an installed Unity performance result.");

static double Measure(object value, Type type, JsonSerializerOptions options,
    ArrayBufferWriter<byte> outputBuffer, int iterations)
{
    var start = Stopwatch.GetTimestamp();
    for (var i = 0; i < iterations; i++)
        Write(value, type, options, outputBuffer);
    return (Stopwatch.GetTimestamp() - start) * 1000d / Stopwatch.Frequency;
}

static string Serialize(object value, Type type, JsonSerializerOptions options,
    ArrayBufferWriter<byte> outputBuffer)
{
    Write(value, type, options, outputBuffer);
    return System.Text.Encoding.UTF8.GetString(outputBuffer.WrittenSpan);
}

static void Write(object value, Type type, JsonSerializerOptions options,
    ArrayBufferWriter<byte> outputBuffer)
{
    outputBuffer.Clear();
    using (var writer = new Utf8JsonWriter(outputBuffer))
        JsonSerializer.Serialize(writer, value, type, options);
}

static Type RequiredType(Assembly assembly, string name) =>
    assembly.GetType(name, throwOnError: true)!;

static void Set(object target, string propertyName, object? value)
{
    var property = target.GetType().GetProperty(propertyName,
        BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
        ?? throw new MissingMemberException(target.GetType().FullName, propertyName);
    property.SetValue(target, value);
}

static void FillArray(object target, string propertyName, float[] values)
{
    var property = target.GetType().GetProperty(propertyName)!;
    var destination = (float[])property.GetValue(target)!;
    Array.Copy(values, destination, Math.Min(values.Length, destination.Length));
}

static void Invoke(object target, string methodName, params object[] args)
{
    var method = target.GetType().GetMethod(methodName,
        BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
        ?? throw new MissingMethodException(target.GetType().FullName, methodName);
    method.Invoke(target, args);
}
