# Flight Recorder writer synthetic benchmark

**Result:** all six paced synthetic cases completed with an intact hashed manifest and zero queue/storage frame drops. This is an offline Python/Linux measurement, not Unity overhead, real game cadence, or a deployment guarantee.

## Method

Run with:

```bash
python3 scripts/benchmark_flight_writer.py --out /tmp/aicadets-flight-writer-benchmark --duration 3
```

Each scenario produced 150 or 300 frames at a paced 50 or 100 Hz, with 30, 50 or 100 immutable entity samples per frame. It measured elapsed producer/drain rate, writer-thread busy frames per second (excluding time waiting for paced input), entity-samples per second, output directory bytes, Python `tracemalloc` peak, process peak RSS, p95 producer enqueue time and maximum queue usage. A separate interrupted-write fixture per scenario salvaged 49 or 99 complete frames plus one truncated final frame, recorded one explicit missing-step gap, and was rechecked with the existing analyzer and manifest verifier.

Environment: Python 3.12.14, Linux x86_64 cloud worker. Memory is process-wide in this isolated child process; `tracemalloc` peak excludes interpreter/runtime native allocations. RSS is the process high-water mark. All six runs reported `capture_complete=true` and zero queue/storage drops.

## Measured results

| Target Hz | Entities | Producer updates/s | Writer busy frames/s | Entity samples/s | Recording bytes | Python peak MiB | RSS peak MiB | Enqueue p95 ms | Recovery frames/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 50 | 30 | 50.2 | 759 | 1,505 | 551,550 | 1.17 | 15.8 | 1.40 | 4,862 |
| 50 | 50 | 50.1 | 646 | 2,507 | 909,909 | 1.19 | 16.0 | 1.45 | 3,481 |
| 50 | 100 | 50.0 | 320 | 5,003 | 1,811,966 | 1.24 | 16.8 | 3.21 | 2,041 |
| 100 | 30 | 100.0 | 904 | 2,999 | 1,108,069 | 1.17 | 16.0 | 0.91 | 7,197 |
| 100 | 50 | 99.9 | 646 | 4,993 | 1,829,429 | 1.19 | 16.3 | 1.64 | 3,551 |
| 100 | 100 | 99.2 | 195 | 9,918 | 3,645,134 | 1.67 | 18.5 | 3.07 | 2,347 |

The largest tested scenario wrote 30,000 entity samples in three seconds, used 3,645,134 bytes in its run directory, reached a 1.67 MiB traced allocation peak and 18.5 MiB process RSS peak, and had a 3.07 ms p95 enqueue time. The queue peaked at 11 frames; there were no queue or storage drops and `capture_complete=true`. Its independent recovery fixture salvaged 99 complete frames at about 2,347 frames/s, left a one-step gap for the torn final line, and passed manifest integrity validation. The fixture supplied its known final step; an actual interrupted run without an external final-step observation retains `unknown_tail_loss=true`.

## Interpretation and limits

- The queue stayed shallow in these paced workloads (maximum depth 11) and no frames dropped. Fault-injection tests separately force saturation and confirm explicit gaps/errors.
- “Writer busy frames/s” is serialized work in the Python worker; “producer updates/s” is the paced input cadence. Neither is game FPS.
- The benchmark uses deterministic synthetic poses and omits Unity enumeration, engine object copying, plugin callbacks, IPC serialization, Windows storage behavior, rendering, gameplay events and actual game CPU contention.
- Results do not establish the user's installed AoTTG2 version, plugin compatibility, recorder phase, entity coverage, or safe runtime overhead.

The reproducible raw output is `metrics.json` in the `--out` directory. The committed script prints each scenario as it completes and writes the complete JSON summary last.
