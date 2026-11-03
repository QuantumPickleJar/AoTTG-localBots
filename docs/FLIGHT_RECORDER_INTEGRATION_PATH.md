# Flight Recorder integration path

This document records the non-destructive extraction of the offline Flight
Recorder work from the stacked draft PRs. It is intentionally separate from
the unvalidated M2 gameplay branch and does not claim that AoTTG2 can load a
recorder.

## Follow-on adapter branch

`codex/flight-recorder-il2cpp-adapter` starts from PR #15's integration branch.
It adds a bounded .NET named-pipe producer, a Windows Python receiver wired to
the existing writer, writer-side incomplete-capture accounting, and offline
transport tests. The Windows smoke test uses synthetic fixtures. This
follow-on still contains no Unity observation component and does not establish
an installed-game recorder. PR #15 is not merged by this work; PR #6 and the
M2 branch remain untouched.

## PR #15 base branch decision

The clean integration branch is based on `main` at `39857d9`, not on
`feat/m2-exploration-and-orders`. It contains the offline dependency closure
needed by the existing writer and its tests:

- PR #10: the versioned reader/analyzer, synthetic traces, and read-only
  installed-build preflight;
- the reusable offline policy/replay support from PRs #12 and #13, including
  the observation-only M2 trace adapter; and
- PR #14: the bounded Python writer, recovery path, benchmark, tests, and
  writer specification.

The extraction includes no `addons/*.cl`, no M2 controller changes, no M2
gameplay test edits, no PRIM-I probe, and no workflow change. The existing
Python writer remains runtime-independent: it is not a Unity plugin, IL2CPP
module, or native recorder.

## Draft PR disposition

| PR | Disposition | Reason |
|---|---|---|
| #6 | Remain draft, untouched | M2 gameplay and Custom Logic changes still require live physical validation. It is not a recorder prerequisite. |
| #10 | Supersede with this clean integration PR after review | Its offline recorder files are retained here; its original branch also inherits the M2 feature branch. |
| #11 | Remain draft, untouched | PRIM-I is an independent opt-in gameplay probe. It is not needed by the Python writer or installed-build audit. |
| #12 | Supersede with this clean integration PR after review | Its policy module/tests are required by the existing replay test closure, but its stacked branch is not used. |
| #13 | Supersede with this clean integration PR after review | Its replay conformance and observation-only adapter are included; M2-specific test edits are excluded. |
| #14 | Supersede with this clean integration PR after review | Its writer and prerequisites are included without the M2 ancestry. |

Until this clean PR is accepted, leave #6 and #10–#14 open and draft. Do not
merge #14 first: its head is based on PR #13, whose ancestry includes the
69-commit M2 feature branch. Do not retarget the existing stacked PRs directly
to `main`; that would expose the inherited M2 gameplay diff in their PRs.

After the clean PR is accepted, close #10, #12, #13, and #14 as superseded;
leave #6 and #11 open for their own validation tracks. No PR in this path
should be marked ready for review until the offline CI is green and the scope
has been checked for add-on or M2-controller files.

## Verification boundary

The offline result is limited to Python tests, compile checks, synthetic trace
analysis/replay, writer stress/fault tests, and a read-only installation
inventory. It does not establish any of the following:

- an IL2CPP injection or mod-loader path;
- a Unity callback/physics-step hook;
- complete actor or collision coverage;
- a local transport working from inside AoTTG2; or
- native recorder readiness or gameplay evidence.

Those are adapter and private-game validation gates described in
`FLIGHT_RECORDER_ADAPTER_PLAN.md`.
