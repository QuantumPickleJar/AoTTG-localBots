using System.IO.Pipes;
using System.Text.Json;
using Aicadets.FlightRecorder.Transport;

if (args.Length == 3 && args[0] == "--send-to-python")
{
    await SendToPythonReceiverAsync(args[1], args[2]);
    return;
}

if (args.Length == 4 && args[0] == "--send-two-sessions-to-python")
{
    await SendTwoSessionsToPythonReceiverAsync(args[1], args[2], args[3]);
    return;
}

var pipeName = $"aicadets-test-{Guid.NewGuid():N}";
var runId = Guid.NewGuid().ToString("N");
var read = ReadThreeLinesAsync(pipeName, runId);
await using var client = new PipePublisher(pipeName, runId,
    "{\"writer_schema\":\"aicadets.flight.v1\",\"producer\":\"transport-smoke\"}");
if (!client.TryPublishControl("event", "{\"event\":\"smoke\",\"t\":1.0,\"evidence\":\"observed\"}"))
    throw new InvalidOperationException("event was rejected by an empty bounded queue");
if (!client.TryPublishControl("stop", "{\"graceful\":true,\"reason\":\"smoke\",\"dropped_frames\":0,\"dropped_control_messages\":0}"))
    throw new InvalidOperationException("stop was rejected by an empty bounded queue");
if (!await client.StopAndDrainAsync(TimeSpan.FromSeconds(5)))
    throw new InvalidOperationException($"pipe did not drain: queue={client.QueueDepth}, bytes={client.QueueBytes}, " +
        $"connections={client.ConnectionAttempts}, failure={client.Failure}, error={client.LastConnectionError}");

var lines = await read.WaitAsync(TimeSpan.FromSeconds(5));
var expectedKinds = new[] { "hello", "event", "stop" };
for (var index = 0; index < lines.Count; index++)
{
    using var message = JsonDocument.Parse(lines[index]);
    var root = message.RootElement;
    if (root.GetProperty("protocol").GetString() != PipePublisher.Protocol ||
        root.GetProperty("run_id").GetString() != runId ||
        root.GetProperty("sequence").GetInt64() != index + 1 ||
        root.GetProperty("kind").GetString() != expectedKinds[index])
        throw new InvalidOperationException($"protocol mismatch in message {index + 1}");
}
Console.WriteLine("transport pipe smoke passed: ordered hello/event/stop envelopes");
await RunBackpressureSmokeAsync();
await RunCriticalReserveAccountingSmokeAsync();
await RunCriticalByteReserveAccountingSmokeAsync();
await RunInvalidPayloadAccountingSmokeAsync();
await RunSerializationFailureAccountingSmokeAsync();

static async Task SendToPythonReceiverAsync(string pipeName, string runId)
{
    var hello = "{\"writer_schema\":\"aicadets.flight.v1\",\"producer\":\"transport-smoke\"," +
        "\"producer_version\":\"0.1.0\",\"runtime_observation_phase\":\"fixture\"," +
        "\"declared_coverage\":{\"fixture\":\"synthetic\"}}";
    await using var publisher = new PipePublisher(pipeName, runId, hello);
    if (!publisher.TryPublishControl("lifecycle", "{\"action\":\"spawn\",\"id\":\"human:test:1\"," +
            "\"kind\":\"human\",\"t\":0.02,\"step\":0,\"evidence\":\"observed\"}"))
        throw new InvalidOperationException("lifecycle message was not queued");
    var framePayload = new
    {
        step = 0, t = 0.02, phase = "fixture", fixed_delta_time = 0.02,
        samples = new[] { new { id = "human:test:1", kind = "human", pos = new[] { 0, 0, 0 }, vel = new[] { 1, 0, 0 } } },
    };
    if (!publisher.TryPublishFrame(framePayload, 0, 0.02))
        throw new InvalidOperationException("frame message was not queued");
    if (!publisher.TryPublishControl("event", "{\"event\":\"fixture_command\",\"t\":0.02," +
            "\"id\":\"human:test:1\",\"evidence\":\"observed\",\"fields\":{\"command\":\"fixture\"}}"))
        throw new InvalidOperationException("event message was not queued");
    if (!publisher.TryPublishControl("stop", "{\"graceful\":true,\"reason\":\"fixture_stop\"," +
            "\"dropped_frames\":0,\"dropped_control_messages\":0}"))
        throw new InvalidOperationException("stop message was not queued");
    if (!await publisher.StopAndDrainAsync(TimeSpan.FromSeconds(15)))
        throw new InvalidOperationException($"Python pipe delivery failed: {publisher.Failure ?? publisher.LastConnectionError}");
}

static async Task SendTwoSessionsToPythonReceiverAsync(string pipeName, string firstRunId, string secondRunId)
{
    var hello = "{\"writer_schema\":\"aicadets.flight.v1\",\"producer\":\"transport-smoke\"," +
        "\"producer_version\":\"0.1.0\",\"runtime_observation_phase\":\"fixture\"," +
        "\"declared_coverage\":{\"fixture\":\"synthetic\"}}";
    await using (var first = new PipePublisher(pipeName, firstRunId, hello))
    {
        if (!first.TryPublishFrame(FramePayload(0), 0))
            throw new InvalidOperationException("first-session frame was not queued");
        if (!await first.StopAndDrainAsync(TimeSpan.FromSeconds(15)))
            throw new InvalidOperationException($"first session did not disconnect cleanly: {first.Failure ?? first.LastConnectionError}");
    }

    await using var second = new PipePublisher(pipeName, secondRunId, hello);
    var typedFrame = new
    {
        step = 0, t = 0.02, phase = "fixture", fixed_delta_time = 0.02,
        samples = new[] { new { id = "human:session-2:1", kind = "human", pos = new[] { 0, 0, 0 } } },
    };
    if (!second.TryPublishFrame(typedFrame, 0, 0.02))
        throw new InvalidOperationException("second-session frame was not queued");
    if (!second.TryPublishControl("stop", "{\"graceful\":true,\"reason\":\"fixture_stop\"," +
            "\"dropped_frames\":0,\"dropped_control_messages\":0}"))
        throw new InvalidOperationException("second-session stop was not queued");
    if (!await second.StopAndDrainAsync(TimeSpan.FromSeconds(15)))
        throw new InvalidOperationException($"second session did not complete: {second.Failure ?? second.LastConnectionError}");
}

static async Task<List<string>> ReadThreeLinesAsync(string pipeName, string runId)
{
    var lines = new List<string>(3);
    while (lines.Count < 3)
    {
        await using var server = new NamedPipeServerStream(pipeName, PipeDirection.InOut, 1,
            PipeTransmissionMode.Byte, PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
        await server.WaitForConnectionAsync().WaitAsync(TimeSpan.FromSeconds(10));
        using var reader = new StreamReader(server, leaveOpen: true);
        while (lines.Count < 3)
        {
            var line = await reader.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(10));
            if (line is null) break;
            lines.Add(line);
            using var message = JsonDocument.Parse(line);
            var ack = JsonSerializer.SerializeToUtf8Bytes(new
            {
                protocol = PipePublisher.Protocol,
                run_id = runId,
                ack_sequence = message.RootElement.GetProperty("sequence").GetInt64(),
                accepted = true,
            });
            await server.WriteAsync(ack);
            await server.WriteAsync(new byte[] { (byte)'\n' });
            await server.FlushAsync();
        }
    }
    return lines;
}

static async Task RunBackpressureSmokeAsync()
{
    var pipeName = $"aicadets-pressure-{Guid.NewGuid():N}";
    var runId = Guid.NewGuid().ToString("N");
    await using var client = new PipePublisher(pipeName, runId,
        "{\"writer_schema\":\"aicadets.flight.v1\",\"producer\":\"pressure-smoke\"}",
        queueCapacity: 5, maxQueueBytes: 8192, controlReserveSlots: 2, controlReserveBytes: 2048,
        criticalReserveSlots: 1, criticalReserveBytes: 1024);
    await Task.Delay(50); // Keep the local pipe absent while the bounded queue fills.

    if (!client.TryPublishFrame(FramePayload(0), 0) || !client.TryPublishFrame(FramePayload(1), 1))
        throw new InvalidOperationException("initial frames did not fit the bounded queue");
    if (client.TryPublishFrame(FramePayload(2), 2) || client.TryPublishFrame(FramePayload(3), 3))
        throw new InvalidOperationException("full frame queue did not report dropped samples");
    if (client.DroppedFrames != 2)
        throw new InvalidOperationException($"expected two accounted drops, got {client.DroppedFrames}");

    var received = ReadUntilStopAsync(pipeName, runId);
    var deadline = DateTime.UtcNow.AddSeconds(10);
    while (client.QueueDepth > 1 && DateTime.UtcNow < deadline) await Task.Delay(10);
    if (client.QueueDepth > 1) throw new TimeoutException("receiver did not drain the bounded queue");
    if (!client.TryPublishFrame(FramePayload(4), 4))
        throw new InvalidOperationException("frame after queue recovery was not accepted");
    if (!client.TryPublishControl("stop", JsonSerializer.Serialize(new
        {
            graceful = true, reason = "backpressure_smoke", dropped_frames = client.DroppedFrames,
            dropped_control_messages = client.DroppedControlMessages,
        })))
        throw new InvalidOperationException("stop envelope was not accepted after backpressure");
    if (!await client.StopAndDrainAsync(TimeSpan.FromSeconds(10)))
        throw new InvalidOperationException($"backpressure queue failed to drain: {client.Failure}");

    var messages = await received.WaitAsync(TimeSpan.FromSeconds(10));
    var gaps = messages.Select(line => JsonDocument.Parse(line)).ToList();
    try
    {
        var gapMessages = gaps.Where(message => message.RootElement.GetProperty("kind").GetString() == "gap").ToList();
        if (gapMessages.Count != 2 || gapMessages.Any(message =>
                message.RootElement.GetProperty("payload").GetProperty("dropped_frames").GetInt64() != 1))
            throw new InvalidOperationException("frame drops were not emitted as two exact gap envelopes");
    }
    finally
    {
        foreach (var message in gaps) message.Dispose();
    }
    Console.WriteLine("transport backpressure smoke passed: bounded queue emitted explicit frame gaps");
}

static async Task RunCriticalReserveAccountingSmokeAsync()
{
    var pipeName = $"aicadets-critical-reserve-{Guid.NewGuid():N}";
    var runId = Guid.NewGuid().ToString("N");
    await using var client = new PipePublisher(pipeName, runId,
        "{\"writer_schema\":\"aicadets.flight.v1\",\"producer\":\"critical-reserve-smoke\"}",
        queueCapacity: 5, maxQueueBytes: 8192, controlReserveSlots: 2, controlReserveBytes: 2048,
        criticalReserveSlots: 2, criticalReserveBytes: 1024);
    await Task.Delay(50); // Keep the receiver absent while ordinary controls fill their limit.
    if (!client.TryPublishControl("event", "{\"event\":\"queued-1\",\"t\":1.0}") ||
        !client.TryPublishControl("event", "{\"event\":\"queued-2\",\"t\":1.1}"))
        throw new InvalidOperationException("ordinary controls did not fit before the critical reserve");
    if (client.TryPublishFrame(FramePayload(0), 0))
        throw new InvalidOperationException("frame unexpectedly fit after the data queue reached its frame limit");
    if (client.TryPublishControl("event", "{\"event\":\"triggers-gap\",\"t\":1.2}"))
        throw new InvalidOperationException("ordinary control unexpectedly consumed the reserved gap/stop capacity");
    if (client.Failure != "control_queue_full" || client.DroppedFrames != 1 || client.DroppedControlMessages != 1)
        throw new InvalidOperationException("control overflow did not preserve the frame gap and report the dropped event");
    if (!client.TryPublishControl("stop", "{\"graceful\":false,\"reason\":\"critical_reserve_smoke\"," +
            "\"dropped_frames\":1,\"dropped_control_messages\":1}"))
        throw new InvalidOperationException("stop record could not use critical capacity after a control overflow");

    var received = ReadUntilStopAsync(pipeName, runId);
    var drain = await client.StopAndDrainAsync(TimeSpan.FromSeconds(10));
    if (drain || client.QueueDepth != 0)
        throw new InvalidOperationException("failed capture was reported complete or left queued messages undrained");
    var messages = await received.WaitAsync(TimeSpan.FromSeconds(10));
    var parsed = messages.Select(line => JsonDocument.Parse(line)).ToList();
    try
    {
        var expectedKinds = new[] { "hello", "event", "event", "gap", "stop" };
        if (parsed.Count != expectedKinds.Length || parsed.Where((message, index) =>
                message.RootElement.GetProperty("kind").GetString() != expectedKinds[index]).Any())
            throw new InvalidOperationException("receiver did not get the queued controls, frame gap, and final stop in order");
        var gap = parsed.Single(message => message.RootElement.GetProperty("kind").GetString() == "gap");
        if (gap.RootElement.GetProperty("payload").GetProperty("dropped_frames").GetInt64() != 1)
            throw new InvalidOperationException("reserved gap did not account for the dropped frame");
        var stop = parsed.Single(message => message.RootElement.GetProperty("kind").GetString() == "stop");
        if (stop.RootElement.GetProperty("payload").GetProperty("graceful").GetBoolean() ||
            stop.RootElement.GetProperty("payload").GetProperty("dropped_control_messages").GetInt64() != 1)
            throw new InvalidOperationException("final stop did not retain the incomplete status and dropped-control count");
    }
    finally
    {
        foreach (var message in parsed) message.Dispose();
    }
    Console.WriteLine("transport critical-reserve smoke passed: full control queue still records frame gap and incomplete stop");
}

static async Task RunCriticalByteReserveAccountingSmokeAsync()
{
    var pipeName = $"aicadets-critical-bytes-{Guid.NewGuid():N}";
    var runId = Guid.NewGuid().ToString("N");
    await using var client = new PipePublisher(pipeName, runId,
        "{\"writer_schema\":\"aicadets.flight.v1\",\"producer\":\"critical-byte-reserve-smoke\"}",
        queueCapacity: 16, maxQueueBytes: 8192, controlReserveSlots: 4, controlReserveBytes: 4096,
        criticalReserveSlots: 2, criticalReserveBytes: 2048);
    await Task.Delay(50); // Keep the receiver absent so the byte limits are deterministic.
    var bulkPayload = JsonSerializer.Serialize(new
    {
        @event = "bulk_fixture",
        t = 1.0,
        blob = new string('x', 5750),
    });
    if (!client.TryPublishControl("event", bulkPayload))
        throw new InvalidOperationException("bulk control did not fit below the ordinary-control byte limit");
    if (client.TryPublishFrame(FramePayload(0), 0))
        throw new InvalidOperationException("frame unexpectedly fit after ordinary controls consumed the data-byte budget");
    if (client.TryPublishControl("event", "{\"event\":\"triggers-byte-gap\",\"t\":1.1}"))
        throw new InvalidOperationException("ordinary control unexpectedly consumed the reserved gap/stop bytes");
    if (client.Failure != "control_queue_full" || client.DroppedFrames != 1 || client.DroppedControlMessages != 1)
        throw new InvalidOperationException("byte overflow did not preserve the frame gap and report the dropped event");
    if (!client.TryPublishControl("stop", "{\"graceful\":false,\"reason\":\"critical_byte_reserve_smoke\"," +
            "\"dropped_frames\":1,\"dropped_control_messages\":1}"))
        throw new InvalidOperationException("stop record could not use critical bytes after a control overflow");

    var received = ReadUntilStopAsync(pipeName, runId);
    var drain = await client.StopAndDrainAsync(TimeSpan.FromSeconds(10));
    if (drain || client.QueueDepth != 0)
        throw new InvalidOperationException("byte-limited failed capture was reported complete or left queued messages undrained");
    var messages = await received.WaitAsync(TimeSpan.FromSeconds(10));
    var parsed = messages.Select(line => JsonDocument.Parse(line)).ToList();
    try
    {
        var kinds = parsed.Select(message => message.RootElement.GetProperty("kind").GetString()).ToArray();
        if (!kinds.SequenceEqual(new[] { "hello", "event", "gap", "stop" }))
            throw new InvalidOperationException("byte-limited receiver did not get the frame gap and final stop in order");
        if (parsed[2].RootElement.GetProperty("payload").GetProperty("dropped_frames").GetInt64() != 1 ||
            parsed[3].RootElement.GetProperty("payload").GetProperty("dropped_control_messages").GetInt64() != 1)
            throw new InvalidOperationException("byte-reserved gap/stop did not preserve drop accounting");
    }
    finally
    {
        foreach (var message in parsed) message.Dispose();
    }
    Console.WriteLine("transport critical-byte smoke passed: full control bytes still record frame gap and incomplete stop");
}

static async Task RunInvalidPayloadAccountingSmokeAsync()
{
    var pipeName = $"aicadets-invalid-payload-{Guid.NewGuid():N}";
    var runId = Guid.NewGuid().ToString("N");
    await using var client = new PipePublisher(pipeName, runId,
        "{\"writer_schema\":\"aicadets.flight.v1\",\"producer\":\"invalid-payload-smoke\"}",
        queueCapacity: 5, maxQueueBytes: 8192, controlReserveSlots: 2, controlReserveBytes: 2048,
        criticalReserveSlots: 1, criticalReserveBytes: 1024);
    await Task.Delay(50);
    if (!client.TryPublishFrame(FramePayload(0), 0) || !client.TryPublishFrame(FramePayload(1), 1))
        throw new InvalidOperationException("initial frames did not fit before invalid-payload accounting check");
    if (client.TryPublishFrame(FramePayload(2), 2) || client.DroppedFrames != 1)
        throw new InvalidOperationException("queue pressure did not account exactly one real frame drop");
    if (client.TryPublishFrame("not-json", 3) || client.DroppedFrames != 1 ||
        client.Failure != "invalid_payload_json")
        throw new InvalidOperationException("invalid JSON was misreported as an additional dropped frame");

    var received = ReadUntilStopAsync(pipeName, runId);
    if (!client.TryPublishControl("stop", JsonSerializer.Serialize(new
        {
            graceful = false, reason = "invalid_payload_smoke", dropped_frames = client.DroppedFrames,
            dropped_control_messages = client.DroppedControlMessages,
        })))
        throw new InvalidOperationException("stop envelope was rejected after invalid-payload failure");
    if (await client.StopAndDrainAsync(TimeSpan.FromSeconds(10)) || client.QueueDepth != 0)
        throw new InvalidOperationException("invalid-payload capture was reported complete or left queued messages undrained");

    var messages = await received.WaitAsync(TimeSpan.FromSeconds(10));
    var kinds = messages.Select(line => JsonDocument.Parse(line)).ToList();
    try
    {
        var messageKinds = kinds.Select(message => message.RootElement.GetProperty("kind").GetString()).ToArray();
        if (!messageKinds.SequenceEqual(new[] { "hello", "frame", "frame", "gap", "stop" }))
            throw new InvalidOperationException("invalid-payload failure did not preserve the single genuine frame gap");
        var gap = kinds[^2].RootElement.GetProperty("payload");
        if (gap.GetProperty("dropped_frames").GetInt64() != 1)
            throw new InvalidOperationException("invalid JSON inflated the genuine dropped-frame gap");
        var stop = kinds[^1].RootElement.GetProperty("payload");
        if (stop.GetProperty("dropped_frames").GetInt64() != 1 || stop.GetProperty("graceful").GetBoolean())
            throw new InvalidOperationException("stop did not preserve the single genuine frame drop and failed status");
    }
    finally
    {
        foreach (var message in kinds) message.Dispose();
    }
    Console.WriteLine("transport invalid-payload smoke passed: fatal serialization did not inflate frame-drop accounting");
}

static async Task RunSerializationFailureAccountingSmokeAsync()
{
    var pipeName = $"aicadets-serialization-failure-{Guid.NewGuid():N}";
    var runId = Guid.NewGuid().ToString("N");
    await using var client = new PipePublisher(pipeName, runId,
        "{\"writer_schema\":\"aicadets.flight.v1\",\"producer\":\"serialization-failure-smoke\"}");
    var accepted = client.TryPublishFrame(new { value = double.NaN }, 0, 0.02);
    var failure = client.Failure;
    if (accepted || client.DroppedFrames != 0 || failure is null ||
        !failure.StartsWith("frame_serialization_failed:", StringComparison.Ordinal))
        throw new InvalidOperationException("fatal typed-frame serialization was counted as a frame drop");

    var received = ReadUntilStopAsync(pipeName, runId);
    if (!client.TryPublishControl("stop", "{\"graceful\":false,\"reason\":\"serialization_failure_smoke\",\"dropped_frames\":0}"))
        throw new InvalidOperationException("stop envelope was rejected after typed-frame serialization failure");
    if (await client.StopAndDrainAsync(TimeSpan.FromSeconds(10)) || client.QueueDepth != 0)
        throw new InvalidOperationException("typed serialization failure was reported complete or left queued messages undrained");

    var messages = await received.WaitAsync(TimeSpan.FromSeconds(10));
    var kinds = messages.Select(line => JsonDocument.Parse(line)).ToList();
    try
    {
        if (!kinds.Select(message => message.RootElement.GetProperty("kind").GetString())
                .SequenceEqual(new[] { "hello", "stop" }))
            throw new InvalidOperationException("typed serialization failure fabricated a frame or gap envelope");
    }
    finally
    {
        foreach (var message in kinds) message.Dispose();
    }
    Console.WriteLine("transport serialization-failure smoke passed: fatal typed-frame failure was not counted as a drop");
}

static string FramePayload(long step) => JsonSerializer.Serialize(new
{
    step, t = (step + 1) * 0.02, phase = "fixture", fixed_delta_time = 0.02,
    samples = new[] { new { id = "human:pressure:1", kind = "human", pos = new[] { (double)step, 0.0, 0.0 } } },
});

static async Task<List<string>> ReadUntilStopAsync(string pipeName, string runId)
{
    await using var server = new NamedPipeServerStream(pipeName, PipeDirection.InOut, 1,
        PipeTransmissionMode.Byte, PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
    await server.WaitForConnectionAsync().WaitAsync(TimeSpan.FromSeconds(10));
    using var reader = new StreamReader(server, leaveOpen: true);
    var lines = new List<string>();
    while (true)
    {
        var line = await reader.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(10));
        if (line is null) throw new EndOfStreamException("pipe ended before stop envelope");
        lines.Add(line);
        using var message = JsonDocument.Parse(line);
        var root = message.RootElement;
        var ack = JsonSerializer.SerializeToUtf8Bytes(new
        {
            protocol = PipePublisher.Protocol,
            run_id = runId,
            ack_sequence = root.GetProperty("sequence").GetInt64(),
            accepted = true,
        });
        await server.WriteAsync(ack);
        await server.WriteAsync(new byte[] { (byte)'\n' });
        await server.FlushAsync();
        if (root.GetProperty("kind").GetString() == "stop") return lines;
    }
}
