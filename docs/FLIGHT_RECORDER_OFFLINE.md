# Flight trace reader, writer core and offline evidence contract

**Scope:** Python standard-library reader, runtime-independent writer core and synthetic fixtures. The writer accepts copied primitive snapshots; it has no Unity imports and is not a Unity plug-in or game-side recorder. Passing offline checks does not show that a trace came from AoTTG2 or that its samples are complete.

## Run the analyzer

```bash
python3 tools/analyze_flight.py examples/flight_recorder/example_run --out flight_report
python3 tools/replay_decisions.py examples/flight_recorder/example_replay --out replay_report
```

The flight analyzer writes `coverage.json`, `anomalies.json`, `timeline.csv`, `tracks.csv`, `focus.csv`, and `report.md`. The decision adapter writes recorded inputs, contract problems, optional policy comparisons and a summary. Neither tool invents missing observations or simulates game physics.

## Trace format accepted by the reader

Runs declare `schema_version: "aicadets.flight.v1"` in `metadata.json` and contain ordered JSONL chunks. A `frame` record carries `step`, game-time `t`, `phase`, optional `fixed_delta_time`, and a `samples` array. A sample should carry a stable per-spawn `id`, `kind`, position, velocity when available, and explicit state. Events are separate records; command intent, observed outcomes and evidence provenance should not be merged into a single “success” flag.

The optional `chunk_manifest.json` uses `manifest_schema: "aicadets.flight.chunk-index.v1"`. Each entry identifies a chunk by relative `file`, exact stored-byte `bytes`, SHA-256, `frame_count`, and optional first/last step. Hash and size checks run before parsing. Corrupt or missing chunks are reported and rejected while independent valid chunks can still be analyzed. Unindexed chunks are reported. Without this manifest, integrity is `not_provided`; it is not described as verified.

## Runtime-independent writer core

`tools/flight_writer.py` exposes immutable `FrameSnapshot`, `EntitySample`, `RecorderEvent` and `EntityLifecycleRecord` values plus `FlightRecorderWriter`. It copies nested JSON-compatible fields into frozen values before producer handoff, rejects non-finite numbers and duplicate IDs in a frame, and writes the reader's frame/event/entity/gap records. `StableEntityRegistry` creates per-spawn generation IDs; a reused source handle gets a new ID after despawn.

The writer uses one bounded count-and-memory-accounted queue and a background chunk worker. Configurable item/byte capacity is reserved for event and lifecycle control records, preserving FIFO order while protecting control submission from frame saturation. Frame queue submission never waits for the disk worker: saturation creates an explicit gap; if the bounded gap ledger itself cannot accept an account within the configured timeout, `RecorderOverloadError` is raised and that frame was not accepted. Events and lifecycle records wait only for the configured timeout, then raise visibly so the caller can retain/retry them. Storage limits stop ordinary writes, count affected frames/samples and rejected controls, and use reserved room for final loss-accounting gaps and control files. Each finalized chunk is flushed, atomically renamed and SHA-256 indexed; `writer_state.json` records checkpointed submitted progress, durable progress and whether the final state was committed. `recover_run()` verifies indexed chunks, reindexes complete chunks whose manifest update was interrupted, salvages complete JSONL records from partial chunks, and emits exact missing-step gaps only when the known bounds support that statement. A checkpoint is not treated as the final crash step; without a final state or externally known expected last step, recovery marks the tail unknown. Truncated tails with unknowable steps remain identified as unknown.

Gap `unit` values distinguish `frames` from `entity_samples`; the analyzer reports the two quantities separately. Legacy untyped gap counts remain in `reported_dropped_samples` for compatibility. A rejected/timeout control event is surfaced to the caller and reflected in `capture_complete=false` if the writer itself observed it. The adapter must not ignore submission errors.

This Python core remains runtime-independent. The separate adapter follow-on supplies a BepInEx IL2CPP component, bounded .NET producer, and Windows named-pipe receiver that writes through this core. Offline tests do not verify Unity callbacks or gameplay coverage; see [the installed-build audit](FLIGHT_RECORDER_ADAPTER_PLAN.md).

## Existing M2 source trace bridge

`addons/AICadetsWaveCadet.cl` currently writes `LogEvent` key/value lines. `tools/m2_trace_adapter.py` can preserve those lines as `m2_source_observation` events in a clearly incomplete `custom_logic_m2_log_events_only` run:

```bash
python3 tools/m2_trace_adapter.py m2_log.txt --out m2_observations
python3 tools/replay_decisions.py m2_observations --out m2_replay_report
```

The adapter preserves the raw line and exact source fields. It does not turn event sequence IDs into decision IDs, cadet names into stable spawn IDs, legacy `behavior_profile` settings into an M3 profile, or timestamps into physics steps. The replay reader reports these events as observation-only and lists the contract fields they lack. The output is useful for inspecting what the controller actually logged; it cannot reconstruct or replay a complete M2 decision.

The source-based M2 tests in `tests/test_wave_m2.py` execute functions from `AICadetsWaveCadet.cl` through `tests/cl_harness.py` with mocked game APIs. They verify source-level decisions and observed log fields, but do not run the AoTTG2 parser, installed runtime, or Unity physics. The Python `reference_policy` is a separate illustrative policy. Its replay agreement is labeled `python_reference_policy_demo` and is **not** M2 production-policy parity. A native M2 decision replay would require the controller to have emitted the full decision input contract and a same-step entity frame; that evidence does not currently exist, and this offline bridge does not modify the M2 controller.

## Evidence and attribution rules

- A global step marker and a sample are separate. Missing steps, time mismatches, nonmonotonic values, declared gaps, bad chunks, and per-entity sampling gaps remain visible.
- A velocity discontinuity is an indication, not proof of a collision. Only an explicit collision/contact event with `evidence: "observed"` enters the contact window.
- Attack-to-damage/death and hook-launch-to-attachment are linked only when the outcome is marked `observed`, the actor/entity matches, and both events carry the same nonempty `correlation_id`. Inferred, missing-ID, or mismatched events cannot close the action window.
- A command-to-motion window compares samples for the same entity after an observed command. Without a correlated observed outcome record, it describes temporal motion evidence only; it cannot establish causation or command acceptance.
- Missing damage is not proof of a miss or kill. Hook launch is not attachment. A rescue attempt, grab-state change, survivor and causal rescue are separate outcomes.
- `capture_tier`, game build, phase and coverage metadata are reported as provided. They are not upgraded by the analyzer. A synthetic or low-rate Custom Logic trace cannot certify per-physics-step capture.

## Decision replay boundary

`decision_input`, `decision_result`, and `action_outcome` records use a stable entity ID plus `decision_id` to pair planner inputs and results. Inputs must include the versioned profile groups, profile hash, policy version, state version, candidates and actual gate results. The adapter reports absent frames or unmatched events. A reference policy may compare recorded decisions against the same serialized inputs; agreement tests policy determinism, not correctness of the physics or the original choice.

## Local checks

The offline suite also exercises writer bounds, snapshot immutability, stable per-spawn IDs, source gaps, queue saturation, storage caps, incomplete decision inputs, corruption and interrupted-write recovery. The synthetic benchmark covers paced 50/100 Hz sessions with 30/50/100 entities; its rates, memory and bytes are not Unity overhead measurements. See [REC-I status](REC_I_VALIDATION_BLOCKER.md) for the separate installed-game blocker. Until REC-I has a real calibrated pass, routine gameplay evidence remains video-first per the validation harness.
