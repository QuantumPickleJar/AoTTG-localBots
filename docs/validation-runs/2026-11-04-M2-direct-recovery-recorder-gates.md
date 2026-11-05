# Validation Card — M2 Direct recovery and Flight Recorder gates

SESSION: `M2-DIRECT-RECOVERY-20261104`
GOAL: Validate the focused single-cadet Direct grounded pursuit and bounded opposite-side recovery change, verify Hold interruption and the Engine comparison, and evaluate Flight Recorder performance, timing, and watcher persistence. This card does not authorize multi-cadet, rescue, personality, or M3 gameplay.
SOURCE BRANCH / M2 GAMEPLAY COMMIT: `feat/m2-exploration-and-orders` / `7c19f75217af57a6ff895c0452266363ea07b5dc`. Docs-only commits followed; the pre-task feature head was `0f10ef1c7e73dfb3c02ec69499e73851a1954787`, and the original seven commits beyond PR #6 head `027ac43` are preserved.
REPORTED M2 BUILD: `M2-locomotion-1-f8combo-4-opposite-retry-gate`
RECORDER BUILD: installed `0.1.11`, source commit `db2a57a6bc62211844b988e24f373dff246763a4`; the installed run completed structurally but failed the performance gate. A 0.1.12 unsorted-discovery candidate was built afterward and is not installed or runtime-tested.
RECORDER CANDIDATE: `0.1.12`, source commit `3e45f3f464119b00b9161f072b464b2a9a7aa669`; 50 package-manifest files verified with no hash failures; ZIP SHA-256 `9111895A1EC15559FF8D1C8D83A7C1CCC21E3842B0C4E3AD1AADA7BAC0BBCA7F`. Candidate DLL SHA-256: plugin `4EAD432B6913BA3D3931A720F4D1946C5A1F71BED76172805D2214835A1DBC7F`, transport `A9226AE194AD2426871FF5D3DDC360C3BFDF9F7E5B64112FE118E31AF5539DD7`. Not installed or runtime-tested.
TEST PROFILE: single owned cadet; private master-host; City 1 / Training / Waves; one ordinary Titan; comparable start geometry.

## Preflight record

- AoTTG2 product build: **not observed; the game window did not expose a screenshot or menu state through desktop control**.
- Unity build: `2023.1.22f1`, observed in the fresh BepInEx startup log.
- Lobby privacy / host authority / connected clients: **not observed; no lobby was entered**.
- Saved settings snapshot: `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261104\InGame.before.json` (saved preset only; not evidence of active settings).
- Effective runtime ground driver as shown in the F8 panel: **not observed**.
- Active add-ons, observed in the lobby UI (not inferred from a saved preset): enable exactly:
  - `AICadetsWaveCadet`
  - `AICadetsCommandPanel`
  - `AICadetsM2Watcher`
- Confirm disabled: `AICadetsProbe`, `AICadetsTraversal`, `AICadetsTraversalReliable`, `AICadetsWatcher`, and every other active test add-on.
- No manual steering or Recovery during locomotion runs. Preserve normal master-client ownership; do not test migration by assumption.
- Recorder must be local opt-in using the existing named-pipe receiver. Do not include other players' telemetry.
- Deployed add-on SHA-256: WaveCadet `55F0D4CF0FDA6C4789CB7A59B16D9A29C19BF9F2FFF1B663DC504CB984007EF4`; CommandPanel `8E6EB2B708F6A67BF7C9D5D7E0BD23B9DCBA1418910239CBDAAE6AE96EC1E17C`; M2Watcher `B6BD148511EA59203F6A3ACBFE0C8886E73C32C6CF4E71D08D9DBE15CCC24489`.
- Recorder package ZIP SHA-256: `96BDE8B78E0AE84A5F0A36A8180F8552FAA37D2E0AE12505E0AA5E82E1E32521`. All 49 manifest-listed files and hashes match; the ZIP contains those files plus `package-manifest.json`.
- Installed recorder DLL SHA-256: plugin `0AAB6C3F0FF99111652797DD34EA968FB4B47B2591A15523F20C09FECDD5F061`; transport `91F47BEACC12351C4E2CD9B7370C54F6B9F67802C30E8076C14A0AAD9BA0DF5B`.
- After the completed run, the game was confirmed closed and recorder config was set to `Enabled = false`; config SHA-256 `16F327AB36C520DD9257AC5D7E7BE2A87029DFAC1A911B25A87739225F89905B`. The pre-run config copy is in `rollback\org.aicadets.aottg2.flight-recorder.cfg` and records the 512-entry / 4 MiB producer queue caps used for analysis.
- Completed recorder ZIP: `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261104\run-1ad84008622a4d4d9e06cae2a25ffac6.zip`, SHA-256 `11A6522FD6BEC854CC12A71044DA60C1BB1A6903FCD50A3DB6986D02185A94D7`. Analysis report: `C:\Users\vmorr\Documents\Aottg2\Recorders\analysis\run-1ad84008622a4d4d9e06cae2a25ffac6-review\report.md`; the ZIP itself was re-analyzed with verified integrity.
- Completed console log: `BepInEx.completed-run.log`, SHA-256 `6D34E9DCEB205D70B891C858D954E2A07D69CA70C1B61FDA976EACD982EE56DD`; receiver stdout/stderr are under `logs`. No gameplay video or watcher files exist because no lobby was entered.
- Pre-run add-on and recorder backups: `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261104\rollback`.
- Save video, watcher files, recorder ZIP, receiver output, console log, settings snapshot, deployed hashes, and this card when a lobby run can be observed. The recorder-only run artifacts are preserved now; no game video or watcher files exist because no lobby was entered.

## Deployment and capture attempt

- Supplied 0.1.10 recorder evidence remains a structural pass but performance/timing fail: 20 hash-verified chunks, 20,878 frames, 901 events, zero declared drops/gaps, about 417.54 seconds; 59/81 post-15-second p95 windows exceed 1.0 ms, worst p95 5.7656 ms and maximum sample 65.7773 ms. Source ZIP: `C:\Users\vmorr\AppData\Local\Temp\codex-file-preview-oGAMtY\run-a19d79cbcb9a4ecbbec2e5dd9a07def2.zip`; report: `C:\Users\vmorr\Documents\Aottg2\Recorders\analysis\run-a19d79cbcb9a4ecbbec2e5dd9a07def2-review\report.md`.
- Supplied M2 controller trace identifies the failed single-cadet Direct recovery: 32 blocked ground routes, 11 exhausted recoveries, a changed retry goal followed by 0.024 units of movement, no renewed same-target progress, zero attack attempts, and zero Titan deaths. This trace is the failure basis; it is not a result for the focused fix.

- A clean game restart loaded `AoTTG2 Flight Recorder 0.1.11`; BepInEx logged run `1ad84008622a4d4d9e06cae2a25ffac6` and `Chainloader startup complete`. The local receiver connected, received hello, and received the producer stop record. `writer_state.json` finalized with `capture_complete=true`, `is_final=true`, 39,509 accepted frames, and one sealed chunk.
- Offline analysis verified the chunk SHA-256 and complete 39,509-frame coverage; no frame-step gaps, declared frame/sample drops, parse errors, or incomplete reasons were found. The capture includes 158 events and zero tracked entities.
- Performance: **fail** — 156 health windows after the first 15 monotonic seconds; 2 exceeded 1.0 ms p95. Worst p95 was 2.8658 ms; worst individual reported sample was 91.2873 ms. Producer queue health showed maximum sampled depth 14 and high-water bytes 5,721 against the run's local config caps of 512 entries / 4 MiB. Receiver-writer high-water was depth 1 / 2,317 bytes against recorded limits of 256 entries / 64 MiB. No drops or fatal errors were reported. Since there were no tracked actors, M2 workload performance remains unmeasured.
- Timing: **inconclusive** — frame ordinals were continuous; fixed delta was 0.019999992 s; frame/game-time anomalies were zero. Producer health wall time was monotonic and correlated with game time (Pearson r=0.9999999997; slope 1.00000058 game seconds per wall second). There were no collision calibration candidates or M2 watcher/controller events, so `sample_phase_verified=false` remains.
- UI observation is blocked: the game window exposes only an empty pane to accessibility and its screenshot capture times out. No active add-on list, lobby privacy, map/mode, effective F8 driver, movement, watcher output, or video was observed.
- Candidate 0.1.12 replaces sorted discovery with `FindObjectsByType(..., FindObjectsSortMode.None)`, preserving inactive-object coverage and explicit entity-ID output ordering. It built against the installed interop but has not been installed or measured. This does not clear the performance gate.

## Fresh-lobby run matrix

Create a fresh private master-host lobby for every row. Restart the game between variants when required by the installed file changes. Use only the add-on list above.

| Run ID | Variant | Required observation | Outcome |
|---|---|---|---|
| `M2-DIR-CLEAR-01` | Engage + Direct on clear ground | Measured physical displacement, sustained positive target-relative progress, and no repeated command thrashing | Blocked before lobby setup |
| `M2-DIR-CORNER-01` | Engage + Direct at the W3-style blocked corner | `ground_route_blocked`; first `reposition_end moved<2`; exactly one opposite-side retry; distinct goal; same Titan; second displacement >= 2; renewed same-target progress. If second displacement is < 2, confirm safe observation/temporary ban and no third retry; this is a failure of recovery acceptance. | Blocked before lobby setup |
| `M2-DIR-HOLD-01` | Hold during measured Direct ground movement | `Idle` cancellation and cessation of ground movement; then separately verify Engage and Explore still work | Blocked before lobby setup |
| `M2-ENGINE-COMP-01` | Engage + Engine in comparable fresh conditions | Compare physical displacement, target gain, path length, reversals, and recovery. `MoveTo` or `ai_state=MoveTo` alone is API/state evidence, not a pass. | Blocked before lobby setup |
| `FR-PHASE-CAL-01` | Controlled calibration with an independently observable, ordinary physics transition | Record fixed-step ordinal, `Time.fixedTimeAsDouble`, monotonic wall time, recorder actor samples, and same-step M2 watcher/controller or collision callback event. Use a naturally occurring collision/ground-contact transition; no teleport, direct transform/velocity write, fake damage, or synthetic physics. | Not performed; phase remains unverified |
| `M2-WATCH-ROTATE-01` | Long private run with watcher rotation enabled | Create multiple segments; no `SaveToFile exceeded 1 mb limit`; every segment below limit; valid previous-file links and numbering; preserve unrelated `PersistentData`; save console log | Blocked before lobby setup |

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

- Static/API: **pass** — `python scripts/check_probe.py`, `python scripts/check_traversal.py`, `python scripts/check_traversal_reliable.py`, `python scripts/check_wave_m2.py`, `python -m unittest discover -s tests -v` (141 tests), `python tools/recovery_preflight.py --addons addons --persistent <empty-test-directory>`, and whitespace checks. These are source/mock checks, not game execution.
- Direct clear-ground / recovery / Hold / Engine: **not run; UI access blocked before lobby setup**.
- Recorder loading and shutdown: **pass** for 0.1.11; clean restart, hello, producer stop, receiver shutdown, and final capture state were observed.
- Recorder structure: **pass**; one SHA-256-verified chunk, 39,509 frames, no gaps or declared drops, `capture_complete=true`.
- Recorder performance: **fail**; 2 of 156 post-start p95 windows exceed 1.0 ms, and the worst sample is 91.2873 ms (>60 ms). No actors were tracked, so this is not an M2 workload measurement.
- Recorder phase calibration: **inconclusive / not performed**; no independently observable physics transition or M2 events, and `sample_phase_verified=false`.
- Timing continuity/correlation: **partial pass** for ordinal/time continuity and monotonic wall correlation only; it does not establish sample phase.
- Watcher persistence rotation: **not run**.
- Package integrity: **pass** for installed 0.1.11; its DLL hashes match the verified package manifest. Candidate 0.1.12 was only built; its runtime and installed-package gates are open.
- Physical movement, combat, and M2 live recovery: **no live evidence**. The user-supplied prior trace is failure evidence, not a result for this build.
- Active runtime add-ons, actual in-game product build, lobby state, effective driver, and video: **not observed**.

## Rollback

- Source rollback for gameplay is the unmodified pre-task `0f10ef1c7e73dfb3c02ec69499e73851a1954787` commit plus the prior PR #6 head `027ac43`; preserve all existing commits and rollback files.
- Installed WaveCadet baseline SHA-256 before this task: `0CEE1C59489E23585F9653078AC5B5EDB3348D2A46BA88E0FC0E5872F413D2AC`; the byte-for-byte backup is `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261104\rollback\AICadetsWaveCadet.cl`, and the deployed SHA-256 is `55F0D4CF0FDA6C4789CB7A59B16D9A29C19BF9F2FFF1B663DC504CB984007EF4`.
- Installed CommandPanel baseline SHA-256: `8E6EB2B708F6A67BF7C9D5D7E0BD23B9DCBA1418910239CBDAE6AE96EC1E17C`.
- Installed M2Watcher baseline SHA-256: `B6BD148511EA59203F6A3ACBFE0C8886E73C32C6CF4E71D08D9DBE15CCC24489`.
- Task backups are under `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261104\rollback`; restore only these three `.cl` files and the recorder DLL/config files if rolling back this deployment.
- Restore only the add-on files changed for the test from the recorded backups, restore the previous recorder DLL and config if replaced, and restart AoTTG2. Do not modify M1 files, mission scripts, unrelated persistent data, or existing rollback files.
