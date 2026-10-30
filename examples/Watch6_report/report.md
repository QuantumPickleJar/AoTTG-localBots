# AI Cadets M1 flight diagnostic — AICadetsM1Watch6(1).txt

## Summary

- Source: AICadetsWatcher v3; 44 watcher events, 0 controller events.
- 3D displacement: 107.58 world units; horizontal: 102.95 units.
- Sampled path length (lower bound): 120.07 units; peak sampled speed: 56.24 units/s.
- Gas consumed (observed): 0.90 units.
- Hook transitions: 4; candidate selections logged: 0; candidate rejections logged: 0.
- Controller finish reasons: NOT OBSERVED; watcher stopped: watch_timeout.

## Hook events

- t=1.32: attached
- t=1.96: released
- t=2.34: attached
- t=2.98: released

## Physics impulses (inferred; not collision callbacks)

- t=3.12 possible_impact dt=0.01999998 pre_pos=(27.33, 60.93, -484.72) pos=(27.63, 61.03, -483.90) pre_vel=(19.29, 6.82, 52.02) post_vel=(0.00, 4.77, 38.68) delta_v=23.54361 layer=MapObjects hit=(28.13, 62.21, -482.55) normal=(-1.00, 0.00, 0.00) distance=2.330009
- t=4.00 landing_velocity_change dt=0.01999998 pre_pos=(27.63, 57.57, -450.64) pos=(27.63, 57.61, -449.89) pre_vel=(0.00, -12.43, 38.68) post_vel=(-0.03, 0.00, 28.29) delta_v=16.19667 map_hit=none

## Forward risk-ray hits (proximity, not collision)

- None observed or unavailable in the older watcher.

## Development findings

- A likely surface-contact impulse occurred within 0.6 s after final hook release. Check whether the controller was in Observe (collision guard is bypassed there in PR #3); the risk ray may detect a surface but does not prove contact.
- Missing controller decision trace: anchor candidates, safety decisions, state changes, and command intent cannot be established from this run.
- Both hook attachment/release cycles were observed. This is maneuver evidence, not proof of waypoint arrival, safe landing, or repeatable success.
- Watch window expired by design. Do not infer controller success/failure from watcher timeout.
- At least one sudden deceleration had no confirming map-layer ray hit; it may be a landing, missed surface, or other physics impulse.

## Evidence limits

AoTTG Custom Logic runtime is not simulated by this analyzer. Sampled positions and map-layer linecasts are evidence, not exact physical collision callbacks. Controller decision events exist only when the instrumented controller is enabled. Comparisons between runs require matching map, starting pose and settings.
