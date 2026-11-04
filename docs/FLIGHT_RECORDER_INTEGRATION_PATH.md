# Flight Recorder integration and PR disposition

PR #15 merged into `main` at merge commit `f0f3b2448c2042db8490cf5c640617a256667ae4`. PR #16 was retargeted to `main`; its merge base is the already merged offline foundation, so its review diff contains the IL2CPP adapter follow-on rather than a duplicate writer stack. M2 gameplay remains separate and unchanged.

## PR disposition

| PR | Current GitHub state | Action |
|---|---|---|
| #6 | Open, draft; `feat/m2-exploration-and-orders` | Leave untouched. Use recorder evidence for M2 diagnosis only after calibration; do not merge with #16. |
| #10 | Closed, not merged | Superseded by the offline analyzer and audit integrated through #15. Leave closed. |
| #11 | Open, draft; independent PRIM-I branch | Keep draft and separate. It is not a recorder prerequisite; defer its gameplay check until REC-I is calibrated. |
| #12 | Open, draft; stacked on #11 | Superseded by the offline policy/replay content integrated through #15. Close as superseded; do not retarget or merge its stacked branch. |
| #13 | Open, draft; stacked combined branch | Superseded by the offline replay/conformance content integrated through #15. Close as superseded; do not retarget or merge its stacked branch. |
| #14 | Open, draft; stacked on #10–#13 | Its Python writer is integrated through #15. Close as superseded; do not merge its M2-bearing ancestry or retarget it. |
| #15 | Merged | Offline writer, analyzer, replay adapter, recovery, tests, and documentation are now on `main`. |
| #16 | Open, ready for review, base `main` | Keep separate from M2. Update review text and CI for the adapter/attribution/performance, critical-queue-reserve, verified installer-upgrade, and 0.1.9 writer-recovery changes. Do not merge until a 0.1.9 private capture measures the performance gate and the remaining review gates are resolved. |

The recommended cleanup is to close #12–#14 as superseded by #15, while leaving #6 and #11 draft. No branch retargeting is needed for those stacked drafts. PR #16 is the only recorder adapter integration candidate.

## Scope boundary

PR #15 supplies the runtime-independent Python writer and offline toolchain. PR #16 adds the BepInEx IL2CPP adapter and local named-pipe transport, and now adds conservative kill-attribution analysis output plus the direct frame-envelope serialization path. It does not modify M2 controller, watcher, or mission logic and does not make native recorder readiness or REC-I calibration claims.

## Validation gates before merging #16

1. The PR head must pass static-smoke, Windows named-pipe transport checks, Python regression tests, and installed-interop plugin build.
2. A guarded 0.1.9 package must include its source commit and manifest hashes, exclude proprietary game binaries/interop, and remain reversible. Automatic upgrade must remove only a receipt-verified, unchanged prior recorder installation.
3. A fresh private installed-game capture must meet the steady-state capture-work p95/max limits with zero unaccounted drops, valid chunks, and no visible control/stutter issue. Any transport/control overflow remains a failed capture even if its gap and incomplete stop are preserved. The prior 0.1.5 p95 breach is historical and cannot be cleared by offline tests.
4. Keep the callback phase and coverage limits explicit; review the 174 remaining velocity-change findings and use the short video only to calibrate motion/phase. Contact-based kill attribution stays inferred absent a direct damage/death event.

After these checks pass, the owner can review the updated #16 diff and CI and merge #16 into `main`. Do not merge #6 or start the next gameplay milestone in the same integration. Use the first calibrated recording to select one narrowly scoped M2 stabilization behavior, prepare its own validation card, and keep it on the M2 branch for separate review.
