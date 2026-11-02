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

The fixture suite validates parsing, bounded reports, manifest integrity, frame coverage, event correlation and decision replay on synthetic data. See [REC-I status](REC_I_VALIDATION_BLOCKER.md) for the separate installed-game blocker. Until REC-I has a real calibrated pass, routine gameplay evidence remains video-first per the validation harness.
