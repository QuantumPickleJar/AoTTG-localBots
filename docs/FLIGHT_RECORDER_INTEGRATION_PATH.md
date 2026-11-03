# Flight Recorder integration and PR path

PR #15 contains the runtime-independent Python Flight Recorder writer and its prerequisites on a clean branch based on main. It excludes the unvalidated M2 gameplay branch. PR #16 is the separate Unity IL2CPP adapter implementation, based on the PR #15 branch. Neither PR has been merged by this work.

## PR disposition

| PR | Current action | Follow-on |
|---|---|---|
| #6 | Leave draft and untouched. | M2 gameplay remains a separate live-validation track. |
| #10 | Leave draft; do not retarget its stacked branch. | After #15 is accepted, close as superseded by #15. |
| #11 | Leave draft and untouched. | Independent PRIM-I probe; not a recorder prerequisite. |
| #12 | Leave draft; do not retarget its stacked branch. | After #15 is accepted, close as superseded by #15. |
| #13 | Leave draft; do not retarget its stacked branch. | After #15 is accepted, close as superseded by #15. |
| #14 | Leave draft; do not retarget its stacked branch. | Its writer is consolidated into #15; after #15 is accepted, close as superseded by #15. |
| #15 | Keep open as the offline foundation and current base branch for #16. | Review/integrate separately. Do not merge automatically as part of #16. |
| #16 | Keep draft and based on the PR #15 branch. It contains only the adapter/transport/runtime audit follow-on. | After #15 is accepted into main, retarget #16 to main so its diff contains only the adapter follow-on, then recheck CI and scope. |

Do not merge PR #6 or change its branch. Do not retarget #10, #12, or #13 to main: their ancestry contains the M2 feature history. Do not merge PR #14 first; its ancestry is stacked through earlier branches. PR #15 is the clean consolidated offline base. PR #16 depends on it and does not duplicate its writer implementation.

## Scope boundaries

PR #15 provides the offline reader/analyzer, replay support, writer, recovery, benchmark, and tests. It contains no M2 gameplay source changes.

PR #16 adds the BepInEx IL2CPP adapter compiled against the installed build's generated interop, producer-health/coverage metadata, sampled scene/hook observations, Windows packaging and rollback scripts, and adapter-shaped protocol tests. It consumes the existing Python writer through the local named-pipe receiver; it does not create a competing file format. It changes no M2 controller or watcher files.

## Validation boundary

The installed-runtime main-menu smoke proves loader/plugin startup and local writer transport only. It did not enter a lobby or mission and saw no game entities. REC-I is the first private gameplay calibration; it must establish actor coverage, hook samples, collision callback behavior if fired, motion cross-check, drops, and measured capture cost before the recorder is used to diagnose M2.

PR #16 remains draft and review-only. Keep both PRs unmerged until their owners review the exact diff and checks.
