# M1 acceptance report (current)

## Scope

This report separates:

- **Verified**: directly observed evidence
- **Inferred**: interpretation from indirect signals
- **Untested**: still pending gameplay verification

## Verified

1. Recovered baseline files are preserved in-repo with expected blobs:
   - `AICadetsTraversal.cl` = `4c1d23c628d18f98500d2c3f20f5d954c1ea17fd`
   - `AICadetsWatcher.cl` = `5b3e1720b6e3d66b4fc35d0c9957306b67203b57`
2. Reliability candidate add-on exists separately as `AICadetsTraversalReliable.cl`.
3. Controller emits bounded machine-readable event logs (`[AI Cadets M1R] ...`).
4. Automated checks and mocked-flow tests pass in CI/local static execution (see validation output in PR).

## Inferred (from latest successful watcher evidence)

From the latest reported successful run summary:

- Scout discovered at ~2.66s.
- First hook attach/release around 3.86s / 4.50s.
- Second hook attach/release around 4.72s / 5.02s.
- ~20.11 velocity change near map surface normal `(1, 0, 0)` at 5.02s likely indicates wall-adjacent event.
- ~34.62 velocity change near upward normal `(0, 1, 0)` at 7.22s likely indicates landing/floor impact.
- Scout stationary by ~8.24s.
- Horizontal displacement ~86.37; gas consumption ~0.676.
- Watcher timeout reached around 27.66s.

These are evidence of maneuver execution and post-release motion, not proof of safe navigation.

## Untested / pending

1. Full 10-attempt x 3-surface matrix for reliability candidate.
2. Realism-mode comparison across the same matrix.
3. Controlled obstacle/fall-recovery pass/fail rates.
4. Consenting second-client synchronization after solo acceptance.
5. Confirmation that reliability candidate should replace baseline for default M1 execution.

## Acceptance gate

M1 is accepted only after:

1. manual matrix in `docs/M1_TESTING.md` is completed,
2. failure classes and safe termination are validated in game,
3. no regression in Scout spawn or watcher trace generation is observed,
4. evidence is attached per run with clear verified/inferred separation.
