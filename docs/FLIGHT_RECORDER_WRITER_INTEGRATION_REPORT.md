# Flight Recorder writer integration report

**Status:** offline writer core and fault tests are ready for draft review. This work is based on `codex/2026-11-02-integration-replay-conformance` (PR #13 combined baseline). It does not modify the live M2 controller, merge PR #6, activate experimental maneuvers, or validate Unity physics.

## Issue and PR review

| Item | Integration finding | Writer boundary |
|---|---|---|
| Issue #9 | Requires local opt-in, passive, bounded, per-physics-step capture; stable per-spawn identities; loss accounting; independently recoverable chunks; and separate offline/game validation. | The Python core implements bounded storage and recovery but has no game callback, transport, loader or claim of physics-step coverage. |
| PR #10 | Defines the `aicadets.flight.v1` reader and SHA-256 chunk-index contract. Its replay reader requires a complete decision input and a same-step frame. | The writer emits reader-compatible JSONL records and manifest entries. It omits unknown values rather than filling gaps. |
| PR #11 | The opt-in Custom Logic primitive probe/observer is isolated and low-rate; it is not global physics-step instrumentation. | It remains independent from this writer and cannot stand in for the future engine adapter. |
| PR #12 | Adds the typed M3 profile/rescue contract; execution remains gated and Carry is not enabled. | The writer accepts structured events but neither validates nor executes M3 policy. |
| PR #13 | Preserves source-based M2 observations and harness coverage. Existing `LogEvent` rows lack enough state to satisfy the replay-input contract. | `m2_source_observation` remains explicitly unreplayable. Python reference-policy agreement is not M2 production-policy parity. |

The combined offline pass reported 197 tests passing before this writer scope. No cross-PR schema or controller conflict was found at the integration boundary. The key unresolved data gap is the M2 decision input contract; reconstructing it requires controller instrumentation and is outside this writer change.

## Writer and verification

The core in `tools/flight_writer.py` uses only the Python standard library. Producers hand off frozen primitive snapshots; a bounded background writer emits ordered JSONL chunks with size, SHA-256 and frame-range manifest entries. Per-spawn IDs and lifecycle events are explicit. A reserved queue budget protects event/lifecycle submissions from frame saturation. Queue overflow and storage exhaustion create counted gaps; if bounded accounting or control submission cannot proceed, the API raises instead of pretending the record was accepted. Recovery verifies independent chunks, reindexes complete renamed chunks, salvages complete JSONL lines and marks an unknowable crash tail as unknown.

The expanded suite now has **212 passing tests**, including 15 writer tests for immutable handoff, stable IDs/despawn, source-step gaps, queue saturation and accounting exhaustion, bounded storage and loss-ledger compaction, incomplete decisions, corrupted chunks, interrupted writes and recovery. Paced synthetic throughput, memory, file-size and recovery results are in [the benchmark report](FLIGHT_RECORDER_WRITER_BENCHMARK.md). These are Python/Linux measurements, not Unity or Windows performance evidence.

## Windows release investigation

The [official release listing](https://aottg2-team.itch.io/aottg2) currently identifies AoTTG2 version 11.01.2026 and a 1 GB Windows Standalone64 Version 7 upload dated November 1, 2026. In the cloud browser, selecting that download produced the site's “Thanks for downloading” acknowledgement but no browser download event or archive path within 30 seconds. The archive could not be inspected here. This does not establish the user's installed version or prove the archive is unavailable outside this cloud environment.

## Remaining work by environment

| Requires installed game files | Requires actual gameplay |
|---|---|
| Run `py -3 scripts/inspect_unity_install.py "D:\Games\AoTTG2" --out build_preflight.json` against the user's current install. Identify the installed Unity build/backend and permitted loading path; review actual game files and choose the adapter ABI/transport and rollback. | After a compatible passive adapter exists, verify callback phase against video, entity-class coverage and ID lifecycle, event provenance, drops, disk behavior and game CPU/frame-time/memory overhead in a private session. This is the REC-I calibration gate. |

The immediate local action is the read-only install preflight above; replace the sample path with the user's actual installation root. Then use those results to decide whether a Unity adapter is feasible. Gameplay calibration follows only after that audit and adapter review. See [the deployment connection spec](FLIGHT_RECORDER_WRITER_SPEC.md).
