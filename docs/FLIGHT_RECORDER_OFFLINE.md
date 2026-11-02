# Flight trace reader and offline evidence contract

**Scope:** offline analyzer and synthetic fixtures only. This is a reader for a reference format, not a game-side recorder. A passing parser test does not show that a trace came from AoTTG2 or that its samples are complete.

## Run the analyzer

```bash
python3 tools/analyze_flight.py examples/flight_recorder/example_run --out flight_report
python3 tools/replay_decisions.py examples/flight_recorder/example_replay --out replay_report
```

The flight analyzer writes `coverage.json`, `anomalies.json`, `timeline.csv`, `tracks.csv`, `focus.csv`, and `report.md`. The decision adapter writes recorded inputs, contract problems, optional policy comparisons and a summary. Neither tool invents missing observations or simulates game physics.

## Trace format accepted by the reader

Runs declare `schema_version: "aicadets.flight.v1"` in `metadata.json` and contain ordered JSONL chunks. A `frame` record carries `step`, game-time `t`, `phase`, optional `fixed_delta_time`, and a `samples` array. A sample should carry a stable per-spawn `id`, `kind`, position, velocity when available, and explicit state. Events are separate records; command intent, observed outcomes and evidence provenance should not be merged into a single “success” flag.

The optional `chunk_manifest.json` uses `manifest_schema: "aicadets.flight.chunk-index.v1"`. Each entry identifies a chunk by relative `file`, exact stored-byte `bytes`, SHA-256, `frame_count`, and optional first/last step. Hash and size checks run before parsing. Corrupt or missing chunks are reported and rejected while independent valid chunks can still be analyzed. Unindexed chunks are reported. Without this manifest, integrity is `not_provided`; it is not described as verified.

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

The fixture suite validates parsing, bounded reports, manifest integrity, frame coverage, event correlation and decision replay on synthetic data. It also checks that source-harness M2 observations remain unreplayable when required state is absent. See [REC-I status](REC_I_VALIDATION_BLOCKER.md) for the separate installed-game blocker. Until REC-I has a real calibrated pass, routine gameplay evidence remains video-first per the validation harness.
