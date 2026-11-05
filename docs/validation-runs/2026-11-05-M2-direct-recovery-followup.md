# Validation Card — M2 Direct movement and recovery follow-up

SESSION: `M2-DIRECT-RECOVERY-20261105-016`  
STATUS: Card created before the next gameplay run. No post-patch live result is claimed.  
SCOPE: Single-cadet M2 `Engage + Direct`, grounded pursuit, bounded opposite-side recovery, Hold interruption, Engine comparison, recorder performance/timing, and watcher rotation. No multi-cadet, rescue, personality, or M3 gameplay.  
NON-GOALS: No mission-script or M1 changes, no attack/damage semantics changes, no synthetic movement/physics, no recorder or watcher implementation mixed into the gameplay change.

## Build and session facts to capture

| Fact | Required evidence | Result |
|---|---|---|
| AoTTG2 product build and Unity version | Installed build file plus startup logs | Pending |
| Lobby and host | Fresh private master-host lobby for every gameplay variant | Pending user confirmation |
| Human participants | User is the only human-controlled player | Pending user confirmation |
| Map/mode/wave | City 1 / Training / Waves / Wave 1 Titan count 1 | Pending active lobby check |
| Actors | One owned cadet and one ordinary Titan | Pending active lobby check |
| Custom Logic add-ons | Exactly `AICadetsWaveCadet`, `AICadetsCommandPanel`, `AICadetsM2Watcher` enabled; Probe, Traversal, TraversalReliable, Watcher, and all other test add-ons disabled | Pending active add-on check |
| Active settings | Snapshot from the running setup; do not infer from the saved preset | Pending |
| Effective driver | Watcher/controller event confirms Direct or Engine after the command | Pending |
| Deployed files | SHA-256 for all three enabled add-ons plus recorder/plugin/transport/package manifests | Pending |
| Recorder | Version, run ID, receiver handshake, final ZIP, analyzer report, clean stop | Pending |
| Watcher | Run ID, segment manifest, saved game/Custom Logic console logs | Pending |
| Artifacts | Video if available, settings snapshot, deployed hashes, Validation Card | Pending |

Raw watcher, recorder, video, and game logs remain local. Do not place player display names or raw private telemetry in PR descriptions.

## Preconditions

- Start from a closed game. Verify the currently installed WaveCadet rollback file and hash before deployment; retain every existing rollback artifact. Record the candidate commit and installed hashes after deployment.
- Start the local recorder receiver before launching the game. Keep recording disabled until the receiver is listening and the opt-in configuration is verified. Use a fresh clean restart and confirm the installed plugin version and hello handshake at the menu.
- Use a fresh private master-host lobby for each gameplay variant. Confirm the user is the only human-controlled player, the map/mode/wave, actor count, and exact active Custom Logic add-ons in the running lobby.
- If the cadet does not spawn, invalidate the attempt, restart the round, and record the replacement run ID. Do not issue an order before the cadet exists.
- For the blocked-route variant, reproduce the W3-style corner as closely as possible. No manual steering or Recovery is permitted during the observation interval.
- A lone human-controlled player can still have a non-cadet killer/display name in logs; do not interpret a name string as another human participant.
- Do not use teleports, direct transform writes, velocity writes, fake damage, fake kills, or synthetic physics.

## Gameplay run matrix

Every row is a separate fresh private master-host variant. Record a unique watcher run ID and recorder run ID for each.

| Run ID | Variant | Pass evidence | Result |
|---|---|---|---|
| Pending | Clear-ground `Engage + Direct` | One F8 command; measured physical displacement; positive same-target distance progress over a sustained interval; no repeated command thrashing | Pending |
| Pending | W3-style blocked corner `Engage + Direct` | `ground_route_blocked`; attempt 1 `reposition_end` with `movement_result=moved<2`; exactly one `reposition_retry`; a genuinely different opposite-side goal; same Titan retained; attempt 2 start/end displacement measured from its own start; at least 2 units moved and renewed same-target progress. If attempt 2 remains under 2, bounded safe Observe and no third retry are a safe-failure result, not a recovery pass. | Pending |
| Pending | Hold interruption during measured Direct ground movement | Hold issues `Idle`; owned movement ceases; no stale retry resumes. In separate fresh variants, confirm Engage and Explore work after Hold. | Pending |
| Pending | Engine comparison under comparable geometry | Compare physical displacement, same-target distance gain, path length, reversals, and recovery. `MoveTo` and `ai_state=MoveTo` alone are API/state evidence, not movement success. | Pending |
| Pending | Combat reachability | If locomotion reaches an attack window, record attempt and observed animation/state. Animation, proximity, or `confirmed_damage=false` is not a hit. Require independently attributed damage/death evidence before claiming damage or a Titan kill. | Pending |
| Pending | Watcher persistence | Multiple numbered segments below 1 MB; valid predecessor links and numbering; no `SaveToFile exceeded 1 mb limit`; preserve unrelated `PersistentData` properties; save the game and Custom Logic console logs. | Pending |

## Recorder performance and timing gates

- Installed plugin is observed loading after a clean restart; capture ends with `capture_complete=true`; all chunk hashes validate; no missing frame steps, frame drops, entity-sample drops, fatal errors, or unclean producer/receiver stop.
- After the first 15 seconds, every producer-health window has `capture_work_ms_p95 <= 1.0`; no individual capture-work sample exceeds 60 ms. Queue depth and queue bytes remain within the declared producer and writer limits without drops or fatal errors. Do not weaken thresholds or omit expensive samples.
- Keep the `aicadets.flight.v1` schema, local named-pipe transport, recovery behavior, and package manifest integrity.
- Calibrate sample phase with a reproducible natural event: correlate an independently observable physics transition or known fixed-step event to the same-step and following-step recorder samples and available watcher/controller event timestamps. Verify fixed-step ordinal continuity, game-time continuity, wall-clock correlation, and the event/sample relationship. Keep `sample_phase_verified=false` if inconclusive.
- Do not claim complete actor coverage, collision or attack causality, damage, or kills from the Flight Recorder alone.

## Prior live baseline

Run 06, watcher run `m2-0`, used recorder 0.1.15 run `54ba9419295a4ec8b05d5769b1bc9990`. The user confirmed a private master-host session with only them as the human-controlled player, City 1 / Training / Waves, Wave 1 Titan count 1, one owned cadet, one ordinary Titan, and exactly the three required M2 add-ons. The W3-style blocked-corner cadet existed and moved before the order; one F8 `Engage + Direct` order was issued and acknowledged as sequence 1. This is recorded to distinguish pre-order movement from post-order evidence.

The run failed the blocked-recovery gate: 12 blocked routes, 9 recovery starts/ends, 0 retry commands, and 6 exhausted recoveries. At controller game time 252.5571, attempt 1 ended with measured displacement `0.1135934` and `termination_reason=odm_transition`; the state path skipped the under-2 retry branch. The next candidate must exercise the corrected deferred retry and same-target progress path. The watcher also recorded 4 attack attempts, but no target damage callback or Titan death; no hit or kill is claimed.

Recorder run 06 finalized structurally: `capture_complete=true`, 24,247 frames, 10/10 hash-verified chunks, no missing frame steps, zero declared drops, no malformed/incomplete/fatal records, and clean stop. The sealed ZIP SHA-256 is `F24188704D6AFE4937C964EB410C3D90BEE076C5950292A820427EFAF120C5C3`. Performance failed the maximum-sample gate: 0/95 post-15-second p95 windows exceeded 1.0 ms and worst p95 was 0.9527 ms, but the maximum capture-work sample was 81.3031 ms (limit 60 ms). Re-analysis with the exact active config (512 entries / 4 MiB; config SHA-256 `7F6B4503E22F7A424BEC6195E0906DD21150C411E56A35CD9DEFFEDAD945D682`) confirms producer high-water 5 entries / 64,995 bytes within limits, and writer high-water 2 entries / 43,824 bytes within 256 / 64 MiB; zero drops. The configured report is `analysis-configured-queue-limits/report.md` in the run 06 folder. Timing remained `fixed_update_pre_physics`, `sample_phase_verified=false`; calibration was not performed. Watcher rotation produced 50 linked segments, all below 1 MB, but separate console capture and unrelated-property preservation remain unverified.

## Artifact and rollback checklist

- Save the completed card, one video per variant if available, watcher files plus per-file hashes, recorder ZIP and analysis, BepInEx/Unity/Custom Logic/receiver logs, active settings snapshot, deployed hashes, package manifest, and rollback hashes.
- Keep the pre-run WaveCadet rollback, all prior gameplay backups, installed recorder rollback bundles (0.1.13, 0.1.14, and 0.1.15), and watcher backups. Restore only the exact intended installed file and verify its hash; do not replace loader files or generated interop.
- Record static/API, installed recorder, performance, timing, watcher persistence, physical movement/recovery, combat, and package-integrity outcomes separately as pass, fail, partial, or inconclusive.
