# Validation Card — M2 Direct recovery and Flight Recorder gates

SESSION: `M2-DIRECT-RECOVERY-20261104`
GOAL: Validate the focused single-cadet Direct grounded pursuit and bounded opposite-side recovery change, verify Hold interruption and the Engine comparison, and evaluate Flight Recorder performance, timing, and watcher persistence. This card does not authorize multi-cadet, rescue, personality, or M3 gameplay.
SOURCE BRANCH / M2 GAMEPLAY COMMIT: `feat/m2-exploration-and-orders` / `7c19f75217af57a6ff895c0452266363ea07b5dc`. Docs-only commits followed; the pre-task feature head was `0f10ef1c7e73dfb3c02ec69499e73851a1954787`, and the original seven commits beyond PR #6 head `027ac43` are preserved.
FOLLOW-UP M2 GAMEPLAY COMMIT: `a5c0b81` adds shorter safe variants on the opposite-side recovery route and distinguishes a blocked route from an issued retry. Build tag: `M2-locomotion-1-f8combo-5-shorter-opposite-retry`.
REPORTED M2 BUILD: `M2-locomotion-1-f8combo-4-opposite-retry-gate`
RECORDER BUILD: `0.1.11` was the earlier recorder-only install and failed performance; `0.1.12` was later installed for the user-operated actor-loaded retest below and also failed performance. Recorder 0.1.13 is a diagnostic/performance candidate with package and installed-runtime gates still open.
RECORDER 0.1.12: source commit `3e45f3f464119b00b9161f072b464b2a9a7aa669`; 50 package-manifest files verified with no hash failures; ZIP SHA-256 `9111895A1EC15559FF8D1C8D83A7C1CCC21E3842B0C4E3AD1AADA7BAC0BBCA7F`. Plugin SHA-256 `4EAD432B6913BA3D3931A720F4D1946C5A1F71BED76172805D2214835A1DBC7F`; transport SHA-256 `A9226AE194AD2426871FF5D3DDC360C3BFDF9F7E5B64112FE118E31AF5539DD7`. It was installed and tested in the live retest below; structural gates passed, actor-loaded performance failed.
TEST PROFILE: single owned cadet; private master-host; City 1 / Training / Waves; one ordinary Titan; comparable start geometry.

## Preflight record

- AoTTG2 product build: **not observed; the game window did not expose a screenshot or menu state through desktop control**.
- Unity build: `2023.1.22f1`, observed in the fresh BepInEx startup log.
- Lobby privacy / host authority / connected clients: **not observed during the earlier 0.1.11 recorder-only attempt; no lobby was entered for that attempt**. The user later confirmed the `m2-0` retest was private with only them present; master-host status was not independently confirmed.
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
- Completed console log for the earlier 0.1.11 recorder-only attempt: `BepInEx.completed-run.log`, SHA-256 `6D34E9DCEB205D70B891C858D954E2A07D69CA70C1B61FDA976EACD982EE56DD`; receiver stdout/stderr are under `logs`. That attempt had no gameplay video or watcher files because no lobby was entered.
- Pre-run add-on and recorder backups: `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261104\rollback`.
- Save video, watcher files, recorder ZIP, receiver output, console log, settings snapshot, deployed hashes, and this card for each lobby run. The subsequent user-operated `m2-0` artifacts are listed below; no video or in-game Custom Logic console log was captured.

## Deployment and capture attempt

- Supplied 0.1.10 recorder evidence remains a structural pass but performance/timing fail: 20 hash-verified chunks, 20,878 frames, 901 events, zero declared drops/gaps, about 417.54 seconds; 59/81 post-15-second p95 windows exceed 1.0 ms, worst p95 5.7656 ms and maximum sample 65.7773 ms. Source ZIP: `C:\Users\vmorr\AppData\Local\Temp\codex-file-preview-oGAMtY\run-a19d79cbcb9a4ecbbec2e5dd9a07def2.zip`; report: `C:\Users\vmorr\Documents\Aottg2\Recorders\analysis\run-a19d79cbcb9a4ecbbec2e5dd9a07def2-review\report.md`.
- Supplied M2 controller trace identifies the failed single-cadet Direct recovery: 32 blocked ground routes, 11 exhausted recoveries, a changed retry goal followed by 0.024 units of movement, no renewed same-target progress, zero attack attempts, and zero Titan deaths. This trace is the failure basis; it is not a result for the focused fix.

- A clean game restart loaded `AoTTG2 Flight Recorder 0.1.11`; BepInEx logged run `1ad84008622a4d4d9e06cae2a25ffac6` and `Chainloader startup complete`. The local receiver connected, received hello, and received the producer stop record. `writer_state.json` finalized with `capture_complete=true`, `is_final=true`, 39,509 accepted frames, and one sealed chunk.
- Offline analysis verified the chunk SHA-256 and complete 39,509-frame coverage; no frame-step gaps, declared frame/sample drops, parse errors, or incomplete reasons were found. The capture includes 158 events and zero tracked entities.
- Performance: **fail** — 156 health windows after the first 15 monotonic seconds; 2 exceeded 1.0 ms p95. Worst p95 was 2.8658 ms; worst individual reported sample was 91.2873 ms. Producer queue health showed maximum sampled depth 14 and high-water bytes 5,721 against the run's local config caps of 512 entries / 4 MiB. Receiver-writer high-water was depth 1 / 2,317 bytes against recorded limits of 256 entries / 64 MiB. No drops or fatal errors were reported. Since there were no tracked actors, M2 workload performance remains unmeasured.
- Timing: **inconclusive** — frame ordinals were continuous; fixed delta was 0.019999992 s; frame/game-time anomalies were zero. Producer health wall time was monotonic and correlated with game time (Pearson r=0.9999999997; slope 1.00000058 game seconds per wall second). There were no collision calibration candidates or M2 watcher/controller events, so `sample_phase_verified=false` remains.
- UI observation is blocked: the game window exposes only an empty pane to accessibility and its screenshot capture times out. No active add-on list, lobby privacy, map/mode, effective F8 driver, movement, watcher output, or video was observed.
- Installed recorder 0.1.12 replaced sorted discovery with `FindObjectsByType(..., FindObjectsSortMode.None)`, preserving inactive-object coverage and explicit entity-ID output ordering. Its actor-loaded retest failed the unchanged performance gate as recorded below.

### User-operated 0.1.12 actor-loaded retest

- User confirmed the `m2-0` lobby was private with only them present. The local `GUEST`-prefixed killer label is the user's own display name; no other human participant was present. Raw identifiers remain in local artifacts and are not copied into this card.
- User reports that a spawn close to a building can prevent the cadet from spawning; they restart the round to obtain a different spawn. It is unknown whether that caveat affected `m2-0`; do not treat this run as a clean spawn-geometry-controlled variant.
- Product build `1.2.3`, Unity `2023.1.22f1`; exact active add-on list, City 1 / Training / Waves state, effective F8 driver, and master-host role were not independently observed.
- Recorder `0.1.12` loaded after a clean restart and stopped cleanly. Run `eefc8131fe93455d89bca3d5261af70c`: `capture_complete=true`; 17,123 frames, 16 verified chunks, 1.0 frame coverage, zero frame gaps, zero declared frame/entity/control drops, 1,072 events, and no parse errors. ZIP SHA-256 `881BBE1DC39404F913EE7EB0C8F6C38F26C816487AB2381CA3EA7DFFA5F95150`.
- Recorder performance **fail**: 14/67 post-15-second health windows exceeded 1.0 ms p95; worst p95 `2.8867` ms; maximum sample `59.6039` ms (under the 60 ms cap). Producer queue high-water was depth 3 / 326,767 bytes versus 512 / 4 MiB; writer queue high-water was depth 6 / 128,323 bytes versus 256 / 64 MiB. No drops or fatal errors.
- Timing continuity **pass**, phase calibration **inconclusive**: no frame gaps, nonmonotonic frame time, or fixed-step mismatches; fixed delta `0.019999992`; monotonic wall clock, correlation `0.9999706711`, slope `1.0086115`. Collision candidates were present, but the run was not a controlled calibration; `sample_phase_verified=false` remains. Recorder and watcher/controller events were not joined into one trace.
- Direct order/movement **partial**: one `EngageDirect` order used horizontal `Human.Move(direction)` commands and ground-height goals. One measured interval showed 24.273 units of displacement, 26.926 path length, and 25.448 target gain. The controlled clear-ground geometry and sustained interval criteria were not established.
- Recovery **fail for acceptance; bounded safe outcome observed**: at t=221.6505, target `1009`, attempt 1 moved 1.527 units. The one retry retained the Titan but reported `goal=none` / `opposite_side_blocked`; no second movement or alternate goal was issued or measured. It entered `Observe` with no third retry. This did not meet the retry pass criteria. Five attacks were recorded with `confirmed_damage=false`; no cadet damage or kill is claimed.
- Hold interruption, post-Hold Engage/Explore, and the Engine comparison were not run.
- Watcher rotation **partial**: 36 linked segments (`Watch48`–`Watch83`, segments 0–35) had consecutive previous-file links; all stayed below 1 MB (maximum 352,350 bytes). All 21 unrelated PersistentData keys remained present. The BepInEx log did not contain Custom Logic console output, so absence of the 1 MB warning is unverified. Files and SHA inventory are in `recorder-0.1.12-live-retest\watcher-files`.
- Artifacts: recorder ZIP and reports under `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261104\recorder-0.1.12-live-retest`; ZIP analysis at `C:\Users\vmorr\Documents\Aottg2\Recorders\analysis\run-eefc8131fe93455d89bca3d5261af70c-zip-review\report.md`; completed BepInEx log SHA-256 `AA585D035A56177A6175D24F9A7CF2A06DFE273A6F8F9C92C2B826A8BC9C60CB`. Recorder config was restored to `Enabled=false` after game exit.

## Fresh-lobby run matrix

Create a fresh private master-host lobby for every row. Restart the game between variants when required by the installed file changes. Use only the add-on list above.

| Run ID | Variant | Required observation | Outcome |
|---|---|---|---|
| `M2-DIR-CLEAR-01` | Engage + Direct on clear ground | Measured physical displacement, sustained positive target-relative progress, and no repeated command thrashing | Partial movement in `m2-0`; controlled clear-ground interval not established |
| `M2-DIR-CORNER-01` | Engage + Direct at the W3-style blocked corner | `ground_route_blocked`; first `reposition_end moved<2`; exactly one opposite-side retry; distinct goal; same Titan; second displacement >= 2; renewed same-target progress. If second displacement is < 2, confirm safe observation/temporary ban and no third retry; this is a failure of recovery acceptance. | Fail for recovery acceptance; retry had no goal or measured displacement; bounded Observe/no third retry |
| `M2-DIR-HOLD-01` | Hold during measured Direct ground movement | `Idle` cancellation and cessation of ground movement; then separately verify Engage and Explore still work | Not run |
| `M2-ENGINE-COMP-01` | Engage + Engine in comparable fresh conditions | Compare physical displacement, target gain, path length, reversals, and recovery. `MoveTo` or `ai_state=MoveTo` alone is API/state evidence, not a pass. | Not run |
| `FR-PHASE-CAL-01` | Controlled calibration with an independently observable, ordinary physics transition | Record fixed-step ordinal, `Time.fixedTimeAsDouble`, monotonic wall time, recorder actor samples, and same-step M2 watcher/controller or collision callback event. Use a naturally occurring collision/ground-contact transition; no teleport, direct transform/velocity write, fake damage, or synthetic physics. | Not performed; continuity only; phase remains unverified |
| `M2-WATCH-ROTATE-01` | Long private run with watcher rotation enabled | Create multiple segments; no `SaveToFile exceeded 1 mb limit`; every segment below limit; valid previous-file links and numbering; preserve unrelated `PersistentData`; save console log | Partial: 36 linked segments under 1 MB; no console log to verify warning absence |

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

- Static/API: **pass** — `python scripts/check_probe.py`, `python scripts/check_traversal.py`, `python scripts/check_traversal_reliable.py`, `python scripts/check_wave_m2.py`, `python -m unittest discover -s tests -v` (143 tests at follow-up head), `python tools/recovery_preflight.py --addons addons --persistent <empty-test-directory>`, and whitespace checks. These are source/mock checks, not game execution.
- M2 source/API/statics: **pass**; the user-operated run confirms physical Direct movement but not accepted clear-ground or recovery behavior. Retry acceptance **fail** as described above.
- Recorder 0.1.11 and 0.1.12 loading/shutdown/package: **pass**; 0.1.12 structural capture gate **pass**.
- Recorder 0.1.12 actor-loaded performance: **fail**; 14/67 post-start windows exceed 1.0 ms p95. Timing continuity **pass**, calibration **inconclusive**.
- Watcher rotation: **partial**; linked files are below the limit and PersistentData keys are preserved, but the in-game console warning check is unverified.
- Hold, post-Hold Engage/Explore, Engine comparison, controlled physics calibration, and video: **not run / not captured**.
- User confirmed the `m2-0` session was private and had only them present; exact active add-ons, map/mode, effective driver, and master-host status remain unobserved.
- Recorder 0.1.13 diagnostic/performance candidate: **static/build/package/install pass**; fresh actor-loaded performance and timing-calibration runs remain open.

## Next user-operated validation card

The separate follow-up card `2026-11-04-M2-opposite-retry-and-recorder-013.md` was created before the next gameplay run. WaveCadet build tag `M2-locomotion-1-f8combo-5-shorter-opposite-retry` (commit `a5c0b81f9bbf13b4ce1be05c02c4a6c9f50cf0dc`) is deployed with SHA-256 `866C3BC8B3C9DDA0465633EB85B5B4E7D8C188B79CDD14FA53FA3FFB185C2CA9`. Recorder 0.1.13 package source `e0e216dd518cad9569447cd18e7bccc206d94aac` passed its 50-file manifest and 51-file ZIP checks; ZIP SHA-256 `8C7371859C2EE41F6AECEA34915A8A17B9F603B173A9AE00A2B32675F48021F6`. Installed plugin SHA-256 `E5E331BDFCEF4BDE89CF4A29EA2227998C7A8E503F969B0279A0D74A2B97B314`; transport SHA-256 `DF25B8322B8CCEE6BE6444A8053125C33D49A90DE58128A319511CB14634EF9A`; capture is disabled. The primary gate is the same-target, one opposite-side retry at the W3-style corner; if no safe opposite goal is found, record `reposition_retry_blocked` and verify bounded observation/no third command. Also capture an actor-loaded recorder run. Other required variants remain listed on that card; do not infer unrun results.

## Rollback

- Source rollback for gameplay is the unmodified pre-task `0f10ef1c7e73dfb3c02ec69499e73851a1954787` commit plus the prior PR #6 head `027ac43`; preserve all existing commits and rollback files.
- Installed WaveCadet baseline SHA-256 before this task: `0CEE1C59489E23585F9653078AC5B5EDB3348D2A46BA88E0FC0E5872F413D2AC`; the byte-for-byte backup is `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261104\rollback\AICadetsWaveCadet.cl`, and the deployed SHA-256 is `55F0D4CF0FDA6C4789CB7A59B16D9A29C19BF9F2FFF1B663DC504CB984007EF4`.
- Installed CommandPanel baseline SHA-256: `8E6EB2B708F6A67BF7C9D5D7E0BD23B9DCBA1418910239CBDAE6AE96EC1E17C`.
- Installed M2Watcher baseline SHA-256: `B6BD148511EA59203F6A3ACBFE0C8886E73C32C6CF4E71D08D9DBE15CCC24489`.
- Task backups are under `C:\Users\vmorr\Documents\Aottg2\Recorders\validation\M2-DIRECT-RECOVERY-20261104\rollback`; restore only these three `.cl` files and the recorder DLL/config files if rolling back this deployment.
- Restore only the add-on files changed for the test from the recorded backups, restore the previous recorder DLL and config if replaced, and restart AoTTG2. Do not modify M1 files, mission scripts, unrelated persistent data, or existing rollback files.
