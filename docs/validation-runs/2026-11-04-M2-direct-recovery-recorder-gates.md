# Validation Card — M2 Direct recovery and Flight Recorder gates

SESSION: `M2-DIRECT-RECOVERY-20261104`
GOAL: Validate the focused single-cadet Direct grounded pursuit and bounded opposite-side recovery change, verify Hold interruption and the Engine comparison, and evaluate Flight Recorder performance, timing, and watcher persistence. This card does not authorize multi-cadet, rescue, personality, or M3 gameplay.
SOURCE BRANCH / BASE HEAD: `feat/m2-exploration-and-orders` / `0f10ef1c7e73dfb3c02ec69499e73851a1954787` (seven local commits ahead of PR #6 head `027ac43`; local changes pending).
REPORTED M2 BUILD: `M2-locomotion-1-f8combo-4-opposite-retry-gate`
RECORDER BUILD: pending; the previously supplied run used plugin `0.1.10` and did not pass performance or timing gates.
TEST PROFILE: single owned cadet; private master-host; City 1 / Training / Waves; one ordinary Titan; comparable start geometry.

## Preflight record

- AoTTG2 product build: **pending; record the in-game build shown by the client**.
- Unity build: **pending runtime confirmation**; prior recorder run reported `2023.1.22f1`.
- Lobby privacy / host authority / connected clients: **pending live observation**.
- Saved preset and values: **pending snapshot**.
- Effective runtime ground driver as shown in the F8 panel: **pending per run**.
- Active add-ons, observed in the lobby UI (not inferred from a saved preset): enable exactly:
  - `AICadetsWaveCadet`
  - `AICadetsCommandPanel`
  - `AICadetsM2Watcher`
- Confirm disabled: `AICadetsProbe`, `AICadetsTraversal`, `AICadetsTraversalReliable`, `AICadetsWatcher`, and every other active test add-on.
- No manual steering or Recovery during locomotion runs. Preserve normal master-client ownership; do not test migration by assumption.
- Recorder must be local opt-in using the existing named-pipe receiver. Do not include other players' telemetry.
- Source/deployed file hashes and recorder package-manifest integrity: **pending deployment record**.
- Save the video, watcher files, recorder ZIP, receiver output, console log, settings snapshot, deployed hashes, and this completed card for each run.

## Fresh-lobby run matrix

Create a fresh private master-host lobby for every row. Restart the game between variants when required by the installed file changes. Use only the add-on list above.

| Run ID | Variant | Required observation | Outcome |
|---|---|---|---|
| `M2-DIR-CLEAR-01` | Engage + Direct on clear ground | Measured physical displacement, sustained positive target-relative progress, and no repeated command thrashing | Pending |
| `M2-DIR-CORNER-01` | Engage + Direct at the W3-style blocked corner | `ground_route_blocked`; first `reposition_end moved<2`; exactly one opposite-side retry; distinct goal; same Titan; second displacement >= 2; renewed same-target progress. If second displacement is < 2, confirm safe observation/temporary ban and no third retry; this is a failure of recovery acceptance. | Pending |
| `M2-DIR-HOLD-01` | Hold during measured Direct ground movement | `Idle` cancellation and cessation of ground movement; then separately verify Engage and Explore still work | Pending |
| `M2-ENGINE-COMP-01` | Engage + Engine in comparable fresh conditions | Compare physical displacement, target gain, path length, reversals, and recovery. `MoveTo` or `ai_state=MoveTo` alone is API/state evidence, not a pass. | Pending |
| `FR-PHASE-CAL-01` | Controlled calibration with an independently observable, ordinary physics transition | Record fixed-step ordinal, `Time.fixedTimeAsDouble`, monotonic wall time, recorder actor samples, and same-step M2 watcher/controller or collision callback event. Use a naturally occurring collision/ground-contact transition; no teleport, direct transform/velocity write, fake damage, or synthetic physics. | Pending |
| `M2-WATCH-ROTATE-01` | Long private run with watcher rotation enabled | Create multiple segments; no `SaveToFile exceeded 1 mb limit`; every segment below limit; valid previous-file links and numbering; preserve unrelated `PersistentData`; save console log | Pending |

## Recorder acceptance gate

Record recorder package version, installed DLL SHA-256, manifest validation, clean-restart plugin load line, receiver start/stop state, and run ID. For the calibration and applicable movement runs, record:

- `capture_complete=true`; every chunk hash valid; no frame-step gaps; zero dropped frames and zero dropped entity samples.
- Producer stop and receiver shutdown are clean; queue depth/bytes remain bounded without a drop or fatal error.
- After the first 15 seconds, every producer-health window has `capture_work_ms_p95 <= 1.0`; no individual capture-work sample exceeds 60 ms.
- Fixed-step ordinal and game-time continuity; wall-clock correlation; relationship between recorder samples and M2 watcher/controller events.
- Timing phase is documented and reproducibly observed. A complete ZIP by itself does not verify pre/post-physics phase.
- Do not claim full actor coverage, collision causality, attack causality, damage, or kills from the recorder alone.

## Combat evidence boundary

If locomotion reaches an attack window, record attack attempts and observed animation/state. Animation, proximity, and `confirmed_damage=false` do not prove a hit. Claim a Titan kill only with independently attributed damage/death evidence. This card does not change attack damage, Titan health, or attribution behavior.

## Results and evidence

- Direct clear-ground: **pending**.
- Direct W3-style recovery: **pending**.
- Hold / Engage / Explore: **pending**.
- Engine regression comparison: **pending**.
- Recorder runtime loading / stop / chunk integrity / continuity: **pending**.
- Recorder performance: **pending**.
- Recorder phase calibration: **pending**.
- Watcher persistence rotation: **pending**.
- Artifact names, deployed hashes, settings snapshot, product build, effective driver, and run IDs: **pending**.
- Separate conclusions for static/API checks, runtime recorder, watcher persistence, physical movement, combat, and package integrity: **pending**.

## Rollback

- Source rollback for gameplay is the unmodified pre-task `0f10ef1c7e73dfb3c02ec69499e73851a1954787` commit plus the prior PR #6 head `027ac43`; preserve all existing commits and rollback files.
- Installed WaveCadet baseline SHA-256 before this task: `0CEE1C59489E23585F9653078AC5B5EDB3348D2A46BA88E0FC0E5872F413D2AC`. A timestamped byte-for-byte backup path and post-deploy hash must be recorded before launching the game.
- Installed CommandPanel baseline SHA-256: `8E6EB2B708F6A67BF7C9D5D7E0BD23B9DCBA1418910239CBDAE6AE96EC1E17C`.
- Installed M2Watcher baseline SHA-256: `B6BD148511EA59203F6A3ACBFE0C8886E73C32C6CF4E71D08D9DBE15CCC24489`.
- Restore only the add-on files changed for the test from the recorded backups, restore the previous recorder DLL and config if replaced, and restart AoTTG2. Do not modify M1 files, mission scripts, unrelated persistent data, or existing rollback files.
