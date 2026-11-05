# Validation result — W3 / W4 / W5 wall encounter follow-up

- Session ID: M2-L0-20261102-W3-W5
- Profile: M2-L0
- Date: 2026-11-02
- AoTTG2 build / map / mode / host: Controller build tag `M2-locomotion-1-f8combo-2-holdrecovery`; clips show City 1 / Waves. The product build, lobby privacy, and complete live add-on list are not captured in the supplied artifacts.
- Commit / build tag: `a5e1b20842654f3bee77f0be92176f609e54bbdb` / `M2-locomotion-1-f8combo-2-holdrecovery`.
- Installed files and enabled add-ons: M2 watcher and WaveCadet telemetry confirm this build ran. The exact enabled/disabled lobby list is not present.
- Explicitly disabled add-ons: Not established by these artifacts.
- Relevant saved settings: Current lobby settings are not logged. The user identifies Watch3 as Direct, Watch4 as Engine, and Watch5 as Hold/Recovery.
- Test actions and observed physical outcomes:
  - **Watch3 / Direct:** 11 `ground_route_blocked` and two `recover_exhausted` events. At t=98.396 the reposition moved 0.081 units; at t=115.753 a map hit was 5.256 units ahead and the chosen reposition moved 0.003 units; at t=132.952 a map hit was 1.052 units ahead and its reposition moved 0.387 units. The supplied video visually shows the cadet remaining by the alley/building edge, though it does not share a frame-accurate clock with the watcher.
  - **Watch4 / Engine:** six measured pursuit intervals. The first three toward Titan 1008 had target gains +57.646, +73.944, and +68.180 units. After switching to Titan 1009, three intervals had gains -6.064, -48.970, and -13.437. No direct wall-probe blockage or circling was recorded. One attack attempt occurred at 3.980 units with state `Attack` / `Armature|attack1`, followed by `confirmed_damage=false`; one later recovery exhausted with `collision_risk`.
  - **Watch5 / Hold/Recovery:** Hold was applied during active `RecoverGround` / `MoveTo`. Watcher telemetry showed velocity fall from (-13.95, 0, 1.13) to zero and position remain `(78.04, 10.06, -135.24)` through the Hold interval. Recovery retained Titan 1005, moved 14.884 units, and returned to `ApproachGround`; a later attempt exhausted on `collision_risk`.
- Watcher log / video filenames: `AICadetsM2Watch3.txt`, `AICadetsM2Watch4.txt`, `AICadetsM2Watch5.txt`; `engage-direct-titan-encounter-2026.11.02 - 13.42.02.73.mp4`, `engage-engine-titan-encounter-2026.11.02 - 13.43.55.74.mp4`, `hold-to-recovery-engine-2026.11.02 - 13.45.46.75.mp4`.
- Code-reported commands vs observed motion: `MoveTo` state alone was not counted as movement. Watch3 reposition displacement and W4 pursuit samples provide movement evidence; Watch5 stationary position/velocity samples confirm Hold stop and Recovery movement.
- Outcome: **PARTIAL**.
- Verified / observed / inferred: Direct's wall detection and failed physical escape are verified by the controller trace; W3 video visually corroborates the scene but is not time-synchronized. Hold physically stops active recovery navigation. Engine's initial pursuit gains are measured. The Direct/Engine runs are not a controlled A/B: their target histories and route geometry differ. The attack animation did not produce confirmed damage.
- Remaining issue and next action: A clear-ray ground escape can be unreachable or fail to move. The current code immediately observes/bans the Titan after under-2-unit reposition displacement, even when one recovery attempt remains. Test a bounded alternate-side retry under M2-L0. Do not proceed to M2-C1 attack acceptance yet.
- Rollback status: No source change was made for these W3–W5 runs; build remains `a5e1b20`.
