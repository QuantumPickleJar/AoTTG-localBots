# M1 gameplay testing and acceptance

## Current status

- `AICadetsTraversal.cl` + `AICadetsWatcher.cl` are the recovered baseline pair.
- `AICadetsTraversalReliable.cl` is the reliability candidate.
- M1 is **not complete** until human gameplay acceptance is done.

## Installation paths

Copy to `Documents/AoTTG2/Addons/`:

- Baseline traversal: `addons/AICadetsTraversal.cl`
- Reliability candidate: `addons/AICadetsTraversalReliable.cl`
- Independent watcher: `addons/AICadetsWatcher.cl`
- M0 rollback probe: `addons/AICadetsProbe.cl`

Enable only one traversal add-on at a time:

- Baseline run: `AICadetsTraversal` (+ optional watcher)
- Candidate run: `AICadetsTraversalReliable` (+ optional watcher)

## Preflight before each session

Run:

```sh
python tools/recovery_preflight.py
```

This confirms recovered baseline file hashes and warns if watcher slots are exhausted.

## Required gameplay matrix (human verification)

Minimum: **10 attempts across at least 3 surface profiles** (for example city facade, staggered rooftops/walls, forest trunks).

For each profile, include both:

1. Baseline (`AICadetsTraversal`)
2. Candidate (`AICadetsTraversalReliable`)

For each attempt record:

- map/mode/realism
- add-ons enabled
- result line
- attempts/attachments/recoveries (candidate)
- displacement, gas_used
- observed impacts/stalls
- watcher file ID if enabled

## Mandatory behavior checks

1. **Two-anchor continuity**
   - visible first and second attachment/release under normal route geometry.
2. **Safe termination**
   - after success/failure, gas and hooks remain off.
3. **Obstructed/missing anchor**
   - no unbounded retries; explicit reason.
4. **Fall/impact recovery**
   - candidate attempts bounded recovery only when possible; otherwise safe termination with reason.
5. **Duplicate and restart safety**
   - round restart/lobby recreation does not spawn duplicate test bots.
6. **Realism-mode comparison**
   - run a subset of attempts with realism on and record differences.
7. **Consenting second-client check (after solo pass)**
   - validate shared visibility and synchronization in private lobby only.

## Expected log patterns

### Baseline

`[AI Cadets M1] ... result=<reason>`

### Candidate

Event lines:

`[AI Cadets M1R] t=<...> state=<...> leg=<...> event=<...> ...`

Terminal line:

`[AI Cadets M1R] result_class=<success|recoverable_interruption|safe_termination|failure> result_reason=<...> ...`

## Controller + watcher correlation

1. Save copied controller chat lines to a text file, for example `controller-run-07.log`.
2. Keep the watcher JSON file (for example `AICadetsM1Watch7.txt`).
3. Run:

```sh
python tools/analyze_m1_run.py --controller-log controller-run-07.log --watch-file AICadetsM1Watch7.txt --output run-07-timeline.md
```

This produces a merged timeline table with `verified`, `observed`, and `inferred` rows.
`possible_impact` and `hook_transition_near_surface` remain **inferred clues**, not collision proof.

## Rollback instructions

If candidate behavior regresses:

1. Disable `AICadetsTraversalReliable`.
2. Re-enable `AICadetsTraversal` (and optional `AICadetsWatcher`).
3. Recreate lobby.

If all M1 add-ons must be disabled:

1. Disable traversal and watcher add-ons.
2. Use unchanged `AICadetsProbe` for M0 regression only.

No binary patching, mission replacement, or automatic telemetry upload is performed.
