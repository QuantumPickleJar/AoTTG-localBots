# Single-pass M1 improvement prompt — AoTTG-localBots

Act as a careful AoTTG2 Custom Logic developer. Modify ONLY one bounded M1 behavior based on the evidence below; return a minimal patch and test checklist. Do NOT start M2 combat or M3 boss behavior before M1 traversal is reliable. Preserve the v0.1.1 probe, master-only AI mutation, no teleports/velocity writes/refills, no nonconsensual telemetry, and the addon interface. Do not claim an in-game test from a static check. Official APIs must be confirmed rather than invented.

Evidence file: AICadetsM1Watch6(1).txt (AICadetsWatcher v3). Watcher events=44; controller events=0; hook transitions=4; candidate rejects=0; controller outcome=UNKNOWN (no controller trace).
Measured: horizontal displacement=102.95; 3D displacement=107.58; gas use=0.90; peak sampled speed=56.24; watcher stop=watch_timeout.

Specific anomalies / uncertainties:
- A likely surface-contact impulse occurred within 0.6 s after final hook release. Check whether the controller was in Observe (collision guard is bypassed there in PR #3); the risk ray may detect a surface but does not prove contact.
- Missing controller decision trace: anchor candidates, safety decisions, state changes, and command intent cannot be established from this run.
- Both hook attachment/release cycles were observed. This is maneuver evidence, not proof of waypoint arrival, safe landing, or repeatable success.
- Watch window expired by design. Do not infer controller success/failure from watcher timeout.
- At least one sudden deceleration had no confirming map-layer ray hit; it may be a landing, missed surface, or other physics impulse.

Collision-related evidence (timestamped):
- t=3.12: possible_impact dt=0.01999998 pre_pos=(27.33, 60.93, -484.72) pos=(27.63, 61.03, -483.90) pre_vel=(19.29, 6.82, 52.02) post_vel=(0.00, 4.77, 38.68) delta_v=23.54361 layer=MapObjects hit=(28.13, 62.21, -482.55) normal=(-1.00, 0.00, 0.00) distance=2.330009
- t=4.00: landing_velocity_change dt=0.01999998 pre_pos=(27.63, 57.57, -450.64) pos=(27.63, 57.61, -449.89) pre_vel=(0.00, -12.43, 38.68) post_vel=(-0.03, 0.00, 28.29) delta_v=16.19667 map_hit=none

Task: (1) separate facts from hypotheses; (2) identify ONE highest-value controller or observer defect to address, with a guardrail against regressions; (3) modify the smallest code surface; (4) provide static tests and a three-run manual in-game test matrix (clear route, obstructed route, ground/landing), including expected telemetry and rollback; (5) state what evidence would establish M1 completion. No broad architecture rewrite, no speculative new API, no merge before gameplay validation.
