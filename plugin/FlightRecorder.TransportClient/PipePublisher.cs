using System.Buffers;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;

namespace Aicadets.FlightRecorder.Transport;

/// <summary>
/// Bounded, reconnecting named-pipe producer. Callers pass only immutable JSON
/// primitive snapshots; this class never retains Unity/game object references.
/// </summary>
public sealed class PipePublisher : IAsyncDisposable
{
    public const string Protocol = "aicadets.flight.transport.v1";
    public const int MaxEnvelopeBytes = 1024 * 1024;

    private readonly string _pipeName;
    private readonly string _runId;
    private readonly int _queueCapacity;
    private readonly int _maxQueueBytes;
    private readonly int _controlReserveSlots;
    private readonly int _controlReserveBytes;
    private readonly int _criticalReserveSlots;
    private readonly int _criticalReserveBytes;
    private readonly object _gate = new();
    private readonly Queue<ReadOnlyMemory<byte>> _queue = new();
    private readonly SemaphoreSlim _available = new(0);
    private readonly CancellationTokenSource _cancel = new();
    private readonly Task _worker;
    private readonly TaskCompletionSource _drained = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private int _queuedBytes;
    private int _maxQueueDepth;
    private int _queueHighWaterBytes;
    private long _nextSequence = 1;
    private long _droppedFrames;
    private long _totalDroppedFrames;
    private long _firstDroppedSequence;
    private long _lastDroppedSequence;
    private long _firstDroppedStep;
    private long _lastDroppedStep;
    private long _droppedControlMessages;
    private bool _accepting = true;
    private bool _completed;
    private string? _failure;
    private string? _lastFrameDropReason;
    private int _connectionAttempts;
    private string? _lastConnectionError;

    public PipePublisher(string pipeName, string runId, string helloPayloadJson,
        int queueCapacity = 512, int maxQueueBytes = 4 * 1024 * 1024,
        int controlReserveSlots = 32, int controlReserveBytes = 256 * 1024,
        int criticalReserveSlots = 2, int criticalReserveBytes = 16 * 1024)
    {
        if (string.IsNullOrWhiteSpace(pipeName) || pipeName.Length > 80 ||
            pipeName.Any(ch => !IsAsciiLetterOrDigit(ch) && ch is not ('_' or '-' or '.')))
            throw new ArgumentException("Invalid local named pipe name", nameof(pipeName));
        if (!Guid.TryParseExact(runId, "N", out _))
            throw new ArgumentException("runId must be a UUID in N format", nameof(runId));
        if (queueCapacity < 2 || maxQueueBytes < 4096 || controlReserveSlots < 1 ||
            controlReserveSlots >= queueCapacity || controlReserveBytes < 1024 ||
            controlReserveBytes >= maxQueueBytes || criticalReserveSlots < 1 ||
            criticalReserveSlots > controlReserveSlots || criticalReserveSlots >= queueCapacity ||
            criticalReserveBytes < 1024 || criticalReserveBytes > controlReserveBytes ||
            criticalReserveBytes >= maxQueueBytes)
            throw new ArgumentOutOfRangeException(nameof(queueCapacity), "Queue and control reserves are invalid");

        _pipeName = pipeName;
        _runId = runId.ToLowerInvariant();
        _queueCapacity = queueCapacity;
        _maxQueueBytes = maxQueueBytes;
        _controlReserveSlots = controlReserveSlots;
        _controlReserveBytes = controlReserveBytes;
        _criticalReserveSlots = criticalReserveSlots;
        _criticalReserveBytes = criticalReserveBytes;
        if (!TryEnqueueLocked("hello", helloPayloadJson, isControl: true, sequence: _nextSequence++))
            throw new ArgumentException("hello envelope exceeds the configured transport limits", nameof(helloPayloadJson));
        _worker = Task.Run(PumpAsync);
    }

    public long DroppedFrames { get { lock (_gate) return _totalDroppedFrames; } }
    public long DroppedControlMessages { get { lock (_gate) return _droppedControlMessages; } }
    public string? Failure { get { lock (_gate) return _failure; } }
    public int QueueDepth { get { lock (_gate) return _queue.Count; } }
    public int QueueBytes { get { lock (_gate) return _queuedBytes; } }
    public int MaxQueueDepth { get { lock (_gate) return _maxQueueDepth; } }
    public int MaxQueueBytes { get { lock (_gate) return _queueHighWaterBytes; } }
    public long PendingDroppedFrames { get { lock (_gate) return _droppedFrames; } }
    public string? LastFrameDropReason { get { lock (_gate) return _lastFrameDropReason; } }
    public int ConnectionAttempts => Volatile.Read(ref _connectionAttempts);
    public string? LastConnectionError => Volatile.Read(ref _lastConnectionError);

    /// <summary>Enqueue one frame or account it as dropped without blocking the caller.</summary>
    public bool TryPublishFrame(string payloadJson, long step)
    {
        if (step < 0) throw new ArgumentOutOfRangeException(nameof(step));
        lock (_gate)
        {
            if (!_accepting || _failure is not null) return false;
            if (!FlushPendingFrameGapLocked(payloadJson)) return DropFrameLocked(step, "gap_marker_queue_full");
            var sequence = _nextSequence++;
            if (TryEnqueueLocked("frame", payloadJson, isControl: false, sequence)) return true;
            return DropFrameAtSequenceLocked(sequence, step, "frame_queue_full");
        }
    }

    /// <summary>
    /// Serialize a trusted frame DTO directly inside its protocol envelope.
    /// This avoids a UTF-16 JSON string followed by parse-and-reserialize work
    /// on Unity's FixedUpdate thread. The DTO must contain only copied primitive
    /// data and must not reference Unity/game objects.
    /// </summary>
    public bool TryPublishFrame<T>(T payload, long step, double reportedAt,
        JsonSerializerOptions? serializerOptions = null, int initialCapacityHint = 4096)
    {
        if (step < 0) throw new ArgumentOutOfRangeException(nameof(step));
        if (!double.IsFinite(reportedAt)) throw new ArgumentOutOfRangeException(nameof(reportedAt));
        if (payload is null) throw new ArgumentNullException(nameof(payload));
        if (initialCapacityHint < 256 || initialCapacityHint > MaxEnvelopeBytes)
            throw new ArgumentOutOfRangeException(nameof(initialCapacityHint));
        lock (_gate)
        {
            if (!_accepting || _failure is not null) return false;
            if (!FlushPendingFrameGapLocked(reportedAt, step)) return DropFrameLocked(step, "gap_marker_queue_full");
            var sequence = _nextSequence++;
            if (TryEnqueueObjectLocked("frame", payload, isControl: false, sequence,
                    serializerOptions, initialCapacityHint)) return true;
            return DropFrameAtSequenceLocked(sequence, step, "frame_queue_full");
        }
    }

    /// <summary>Enqueue a control message, retaining reserved queue capacity for it.</summary>
    public bool TryPublishControl(string kind, string payloadJson)
    {
        if (kind is not ("event" or "lifecycle" or "health" or "stop"))
            throw new ArgumentException("Unsupported control message kind", nameof(kind));
        lock (_gate)
        {
            // A failed capture may still send one final stop record. The receiver
            // uses it to persist the producer failure and incomplete status.
            if (!_accepting || (_failure is not null && kind != "stop")) return false;
            if (!FlushPendingFrameGapLocked(payloadJson))
            {
                _droppedControlMessages++;
                _failure ??= "control_reserve_exhausted_before_frame_gap";
                return false;
            }
            var sequence = _nextSequence++;
            if (TryEnqueueLocked(kind, payloadJson, isControl: true, sequence, isCritical: kind == "stop"))
                return true;
            _droppedControlMessages++;
            _failure ??= "control_queue_full";
            return false;
        }
    }

    /// <summary>Stop accepting messages and wait for the bounded queue to drain.</summary>
    public async Task<bool> StopAndDrainAsync(TimeSpan timeout, CancellationToken cancellationToken = default)
    {
        if (timeout <= TimeSpan.Zero) throw new ArgumentOutOfRangeException(nameof(timeout));
        lock (_gate)
        {
            if (_accepting && _failure is null && !FlushPendingFrameGapLocked("{}"))
                _failure ??= "pending_frame_gap_not_queued_before_stop";
            _accepting = false;
            _completed = true;
            if (_queue.Count == 0) _drained.TrySetResult();
            else _available.Release();
        }
        try
        {
            await _drained.Task.WaitAsync(timeout, cancellationToken).ConfigureAwait(false);
            await _worker.WaitAsync(timeout, cancellationToken).ConfigureAwait(false);
            return Failure is null;
        }
        catch (TimeoutException)
        {
            lock (_gate) _failure ??= "pipe_queue_did_not_drain_before_timeout";
            return false;
        }
    }

    public async ValueTask DisposeAsync()
    {
        await StopAndDrainAsync(TimeSpan.FromSeconds(5)).ConfigureAwait(false);
        _cancel.Cancel();
        _available.Release();
        try { await _worker.ConfigureAwait(false); }
        catch (OperationCanceledException) { }
        _available.Dispose();
        _cancel.Dispose();
    }

    private bool DropFrameLocked(long step, string reason)
    {
        var sequence = _nextSequence++;
        return DropFrameAtSequenceLocked(sequence, step, reason);
    }

    private bool DropFrameAtSequenceLocked(long sequence, long step, string reason)
    {
        _droppedFrames++;
        _totalDroppedFrames++;
        if (_droppedFrames == 1)
        {
            _firstDroppedSequence = sequence;
            _firstDroppedStep = step;
        }
        _lastDroppedSequence = sequence;
        if (_droppedFrames > 1 && step < _lastDroppedStep)
            _failure ??= "non_monotonic_dropped_frame_step";
        _lastDroppedStep = step;
        _lastFrameDropReason = reason;
        return false;
    }

    private bool FlushPendingFrameGapLocked(string reportingPayloadJson)
    {
        if (_droppedFrames == 0) return true;
        double? reportedAt = null;
        long? reportedStep = null;
        try
        {
            using var doc = JsonDocument.Parse(reportingPayloadJson);
            if (doc.RootElement.TryGetProperty("t", out var t) && t.ValueKind == JsonValueKind.Number && t.TryGetDouble(out var tValue))
                reportedAt = tValue;
            if (doc.RootElement.TryGetProperty("step", out var step) && step.ValueKind == JsonValueKind.Number && step.TryGetInt64(out var stepValue))
                reportedStep = stepValue;
            if (doc.RootElement.TryGetProperty("reported_at_t", out var reportedT) && reportedT.ValueKind == JsonValueKind.Number && reportedT.TryGetDouble(out tValue))
                reportedAt = tValue;
            if (doc.RootElement.TryGetProperty("reported_at_step", out var reportedS) && reportedS.ValueKind == JsonValueKind.Number && reportedS.TryGetInt64(out stepValue))
                reportedStep = stepValue;
        }
        catch (JsonException)
        {
            _failure ??= "invalid_payload_json";
            return false;
        }

        return FlushPendingFrameGapLocked(reportedAt, reportedStep);
    }

    private bool FlushPendingFrameGapLocked(double? reportedAt, long? reportedStep)
    {
        if (_droppedFrames == 0) return true;

        var payload = new Dictionary<string, object?>
        {
            ["first_sequence"] = _firstDroppedSequence,
            ["last_sequence"] = _lastDroppedSequence,
            ["dropped_frames"] = _droppedFrames,
            ["first_step"] = _firstDroppedStep,
            ["last_step"] = _lastDroppedStep,
            ["dropped_entity_samples"] = null,
        };
        if (reportedAt is not null) payload["reported_at_t"] = reportedAt.Value;
        if (reportedStep is not null) payload["reported_at_step"] = reportedStep.Value;
        var json = JsonSerializer.Serialize(payload);
        var gapSequence = _nextSequence;
        if (!TryEnqueueLocked("gap", json, isControl: true, gapSequence, isCritical: true)) return false;
        _nextSequence++;
        _droppedFrames = 0;
        _firstDroppedSequence = _lastDroppedSequence = 0;
        _firstDroppedStep = _lastDroppedStep = 0;
        return true;
    }

    private bool TryEnqueueLocked(string kind, string payloadJson, bool isControl, long sequence,
        bool isCritical = false)
    {
        var encoded = new ArrayBufferWriter<byte>(256);
        try
        {
            using var payload = JsonDocument.Parse(payloadJson, new JsonDocumentOptions { MaxDepth = 32 });
            if (payload.RootElement.ValueKind != JsonValueKind.Object) return false;
            ValidateNoDuplicateMembers(payload.RootElement);
            using (var writer = new Utf8JsonWriter(encoded))
            {
                writer.WriteStartObject();
                writer.WriteString("protocol", Protocol);
                writer.WriteString("run_id", _runId);
                writer.WriteNumber("sequence", sequence);
                writer.WriteString("kind", kind);
                writer.WritePropertyName("payload");
                payload.RootElement.WriteTo(writer);
                writer.WriteEndObject();
            }
            AppendNewline(encoded);
        }
        catch (JsonException)
        {
            _failure ??= "invalid_payload_json";
            return false;
        }
        return TryQueueLineLocked(encoded.WrittenMemory, isControl, isCritical);
    }

    private bool TryEnqueueObjectLocked<T>(string kind, T payload, bool isControl, long sequence,
        JsonSerializerOptions? serializerOptions, int initialCapacityHint)
    {
        var encoded = new ArrayBufferWriter<byte>(initialCapacityHint);
        try
        {
            using (var writer = new Utf8JsonWriter(encoded))
            {
                writer.WriteStartObject();
                writer.WriteString("protocol", Protocol);
                writer.WriteString("run_id", _runId);
                writer.WriteNumber("sequence", sequence);
                writer.WriteString("kind", kind);
                writer.WritePropertyName("payload");
                JsonSerializer.Serialize(writer, payload, serializerOptions);
                writer.WriteEndObject();
            }
            AppendNewline(encoded);
        }
        catch (Exception ex) when (ex is JsonException or NotSupportedException or InvalidOperationException)
        {
            _failure ??= $"frame_serialization_failed: {ex.GetType().Name}";
            return false;
        }
        return TryQueueLineLocked(encoded.WrittenMemory, isControl, isCritical: false);
    }

    private static void AppendNewline(ArrayBufferWriter<byte> encoded)
    {
        encoded.GetSpan(1)[0] = (byte)'\n';
        encoded.Advance(1);
    }

    private bool TryQueueLineLocked(ReadOnlyMemory<byte> line, bool isControl, bool isCritical)
    {
        if (line.Length > MaxEnvelopeBytes) return false;
        var itemLimit = isCritical ? _queueCapacity :
            isControl ? _queueCapacity - _criticalReserveSlots : _queueCapacity - _controlReserveSlots;
        var byteLimit = isCritical ? _maxQueueBytes :
            isControl ? _maxQueueBytes - _criticalReserveBytes : _maxQueueBytes - _controlReserveBytes;
        if (_queue.Count >= itemLimit || _queuedBytes + line.Length > byteLimit) return false;
        _queue.Enqueue(line);
        _queuedBytes += line.Length;
        _maxQueueDepth = Math.Max(_maxQueueDepth, _queue.Count);
        _queueHighWaterBytes = Math.Max(_queueHighWaterBytes, _queuedBytes);
        _available.Release();
        return true;
    }

    private static void ValidateNoDuplicateMembers(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var property in element.EnumerateObject())
            {
                if (!names.Add(property.Name)) throw new JsonException($"Duplicate JSON member: {property.Name}");
                ValidateNoDuplicateMembers(property.Value);
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in element.EnumerateArray()) ValidateNoDuplicateMembers(item);
        }
    }

    private async Task PumpAsync()
    {
        var delay = TimeSpan.FromMilliseconds(100);
        NamedPipeClientStream? pipe = null;
        try
        {
            while (!_cancel.IsCancellationRequested)
            {
                ReadOnlyMemory<byte> head = default;
                bool hasHead;
                bool completed;
                lock (_gate)
                {
                    hasHead = _queue.Count != 0;
                    if (hasHead) head = _queue.Peek();
                    completed = _completed;
                }
                if (!hasHead && completed)
                {
                    _drained.TrySetResult();
                    return;
                }
                if (!hasHead)
                {
                    await _available.WaitAsync(_cancel.Token).ConfigureAwait(false);
                    continue;
                }

                try
                {
                    if (pipe is null)
                    {
                        Interlocked.Increment(ref _connectionAttempts);
                        pipe = new NamedPipeClientStream(".", _pipeName, PipeDirection.InOut,
                            PipeOptions.Asynchronous);
                        await pipe.ConnectAsync(1000, _cancel.Token).ConfigureAwait(false);
                        delay = TimeSpan.FromMilliseconds(100);
                        Volatile.Write(ref _lastConnectionError, null);
                    }
                    using var acknowledgementReader = new StreamReader(pipe, new UTF8Encoding(false, true),
                        detectEncodingFromByteOrderMarks: false, bufferSize: 1024, leaveOpen: true);
                    using var sent = JsonDocument.Parse(head);
                    var expectedSequence = sent.RootElement.GetProperty("sequence").GetInt64();
                    await pipe.WriteAsync(head, _cancel.Token).ConfigureAwait(false);
                    await pipe.FlushAsync(_cancel.Token).ConfigureAwait(false);
                    var acknowledgementLine = await acknowledgementReader.ReadLineAsync()
                        .WaitAsync(TimeSpan.FromSeconds(2), _cancel.Token).ConfigureAwait(false);
                    if (acknowledgementLine is null)
                        throw new IOException("receiver closed the pipe before acknowledging the message");
                    try
                    {
                        using var acknowledgement = JsonDocument.Parse(acknowledgementLine);
                        var ack = acknowledgement.RootElement;
                        if (ack.GetProperty("protocol").GetString() != Protocol ||
                            ack.GetProperty("run_id").GetString() != _runId ||
                            ack.GetProperty("ack_sequence").GetInt64() != expectedSequence)
                            throw new ReceiverRejectedException("receiver acknowledgement does not match the sent message");
                        if (!ack.GetProperty("accepted").GetBoolean())
                            throw new ReceiverRejectedException(ack.TryGetProperty("error", out var error)
                                ? error.GetString() ?? "receiver rejected message"
                                : "receiver rejected message");
                    }
                    catch (ReceiverRejectedException) { throw; }
                    catch (Exception ex) when (ex is JsonException or KeyNotFoundException or InvalidOperationException)
                    {
                        throw new ReceiverRejectedException($"invalid receiver acknowledgement: {ex.Message}");
                    }
                    lock (_gate)
                    {
                        if (_queue.Count > 0 && _queue.Peek().Equals(head))
                        {
                            _queue.Dequeue();
                            _queuedBytes -= head.Length;
                        }
                        if (_queue.Count == 0 && _completed) _drained.TrySetResult();
                    }
                }
                catch (OperationCanceledException) when (_cancel.IsCancellationRequested)
                {
                    return;
                }
                catch (ReceiverRejectedException ex)
                {
                    lock (_gate)
                    {
                        _failure ??= $"receiver_rejected_message: {ex.Message}";
                        _accepting = false;
                        _completed = true;
                        _drained.TrySetResult();
                    }
                    return;
                }
                catch (Exception ex) when (ex is IOException or TimeoutException or ObjectDisposedException)
                {
                    Volatile.Write(ref _lastConnectionError, $"{ex.GetType().Name}: {ex.Message}");
                    if (pipe is not null)
                    {
                        await pipe.DisposeAsync().ConfigureAwait(false);
                        pipe = null;
                    }
                    await Task.Delay(delay, _cancel.Token).ConfigureAwait(false);
                    delay = TimeSpan.FromMilliseconds(Math.Min(delay.TotalMilliseconds * 2, 5000));
                }
            }
        }
        catch (OperationCanceledException) when (_cancel.IsCancellationRequested) { }
        finally
        {
            if (pipe is not null) await pipe.DisposeAsync().ConfigureAwait(false);
            lock (_gate)
                if (_queue.Count == 0) _drained.TrySetResult();
        }
    }

    private static bool IsAsciiLetterOrDigit(char value) =>
        value is >= 'A' and <= 'Z' or >= 'a' and <= 'z' or >= '0' and <= '9';

    private sealed class ReceiverRejectedException : IOException
    {
        public ReceiverRejectedException(string message) : base(message) { }
    }
}
