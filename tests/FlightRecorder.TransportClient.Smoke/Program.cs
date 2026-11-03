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
await RunFinalGapAccountingSmokeAsync();

static async Task SendToPythonReceiverAsync(string pipeName, string runId)
{
    var hello = "{\"writer_schema\":\"aicadets.flight.v1\",\"producer\":\"transport-smoke\"," +
        "\"producer_version\":\"0.1.0\",\"runtime_observation_phase\":\"fixture\"," +
        "\"declared_coverage\":{\"fixture\":\"synthetic\"}}";
    await using var publisher = new PipePublisher(pipeName, runId, hello);
    if (!publisher.TryPublishControl("lifecycle", "{\"action\":\"spawn\",\"id\":\"human:test:1\"," +
            "\"kind\":\"human\",\"t\":0.02,\"step\":0,\"evidence\":\"observed\"}"))
        throw new InvalidOperationException("lifecycle message was not queued");
    if (!publisher.TryPublishFrame("{\"step\":0,\"t\":0.02,\"phase\":\"fixture\"," +
            "\"fixed_delta_time\":0.02,\"samples\":[{\"id\":\"human:test:1\",\"kind\":\"human\"," +
            "\"pos\":[0,0,0],\"vel\":[1,0,0]}]}", 0))
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
    if (!second.TryPublishFrame(FramePayload(0), 0))
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
        queueCapacity: 4, maxQueueBytes: 8192, controlReserveSlots: 1, controlReserveBytes: 1024);
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

static async Task RunFinalGapAccountingSmokeAsync()
{
    var pipeName = $"aicadets-final-gap-{Guid.NewGuid():N}";
    var runId = Guid.NewGuid().ToString("N");
    await using var client = new PipePublisher(pipeName, runId,
        "{\"writer_schema\":\"aicadets.flight.v1\",\"producer\":\"final-gap-smoke\"}",
        queueCapacity: 2, maxQueueBytes: 8192, controlReserveSlots: 1, controlReserveBytes: 1024);
    await Task.Delay(50); // Keep the local pipe absent while the control reserve fills.
    if (!client.TryPublishControl("event", "{\"event\":\"queued\",\"t\":1.0}"))
        throw new InvalidOperationException("control record did not fit the bounded queue");
    if (client.TryPublishFrame("{\"step\":0,\"t\":1.0,\"phase\":\"fixture\",\"samples\":[]}", 0))
        throw new InvalidOperationException("frame unexpectedly fit after the queue reached capacity");

    var drain = client.StopAndDrainAsync(TimeSpan.FromSeconds(5));
    if (client.Failure != "pending_frame_gap_not_queued_before_stop")
        throw new InvalidOperationException("shutdown failed to report an unqueued final frame-gap marker");
    var received = ReadTwoMessagesAsync(pipeName, runId);
    var messages = await received.WaitAsync(TimeSpan.FromSeconds(10));
    var drainSucceeded = await drain;
    if (drainSucceeded || client.QueueDepth != 0)
        throw new InvalidOperationException("shutdown reported success or left queued messages after an unaccounted loss");
    if (messages.Any(line => JsonDocument.Parse(line).RootElement.GetProperty("kind").GetString() == "gap"))
        throw new InvalidOperationException("a gap marker was reported despite not fitting in the bounded queue");
    Console.WriteLine("transport shutdown accounting smoke passed: unqueued final loss marks producer failure");
}

static async Task<List<string>> ReadTwoMessagesAsync(string pipeName, string runId)
{
    await using var server = new NamedPipeServerStream(pipeName, PipeDirection.InOut, 1,
        PipeTransmissionMode.Byte, PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
    await server.WaitForConnectionAsync().WaitAsync(TimeSpan.FromSeconds(10));
    using var reader = new StreamReader(server, leaveOpen: true);
    var lines = new List<string>(2);
    while (lines.Count < 2)
    {
        var line = await reader.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(10));
        if (line is null) throw new EndOfStreamException("pipe ended before the queued records were acknowledged");
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
    return lines;
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
