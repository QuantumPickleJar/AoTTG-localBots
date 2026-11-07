# M2 pursuit policy and behavior profiles

This is a tunable policy foundation, not a completed personality system. Profiles change bounded choices; they never change physics, gas, damage, target validity, host authority, Hold, or explicit Explore's noncombat intent. Defaults preserve the existing exploration maneuvers. One cadet still spawns.

## Settings

| Setting | Range/default | Effect |
| --- | --- | --- |
| ProfileName | text / Steady scout | Diagnostic name only |
| Persistence | 1–5 / 3 | One to three ground/air recovery attempts, limited by MaxRecoveriesPerTarget; fractional budgets round up through the attempt counter |
| AerialPreference | 1–5 / 3 | After an initial one-second ground segment, probe every 12–4 seconds for a usable forward/lateral map anchor |
| RepositionSkill | 1–5 / 3 | Lateral reposition offset of 11–23 units; reverse the side if the first corridor is blocked |

These are continuous tuning values in the interval 1–5. The descriptive profile name does not secretly change settings. Example combinations to test, not calibrated personalities:

| Profile | Persistence | AerialPreference | RepositionSkill |
| --- | --- | --- | --- |
| Steady scout | 3 | 3 | 3 |
| Tenacious aerialist | 5 | 5 | 4 |
| Cautious runner | 2 | 1 | 3 |
| Clumsy novice | 2 | 2 | 1 |

The novice label means a simpler, shorter reposition in this prototype. It does not deliberately miss attacks, collide, waste gas, or fabricate mistakes. More personality dimensions should map to observable decisions and be evaluated independently.

## Tactical turning points

- A distant living Titan remains the pursuit goal. Ground navigation now periodically checks the same anchor geometry used by ODM. A failed geometric probe does not issue Idle, jump or hook commands. A successful probe starts the existing bounded physical traversal; it is not proof of attachment.
- Ground progress logs both displacement and projected movement toward the target's bearing at the start of the observation window. Sideways motion or a closed loop no longer counts as progress merely because the cadet moved. The target's current distance is logged separately, since a moving Titan can change it independently of the cadet.
- Two poor progress windows initiate recovery. A grounded cadet keeps the target and tries a lateral waypoint for up to six seconds, then replans against the same Titan. If recovery is exhausted, temporarily ban the target for 15 seconds and return to acquisition/search. Other targets can be selected during this interval.
- Target selection uses distance plus small bounded momentum alignment and obstruction adjustments. These apply only during acquisition. They are not an interrupt that continuously switches a valid target. A Titan moving across terrain still requires live validation.
- Existing attack, collision, gas, traversal and ownership limits remain authoritative. No successful kill or refill is inferred from motion or state transitions.

## Evidence and limitations

Watch3 contains only watch_started, with no cadet observations. Watch4 used the older 90-second collector and exhausted its 500-record limit at game time 69.40. Its published state remains Engage / ApproachGround after startup; it contains no controller decision trace or target geometry. The two supplied video files are approximately 13.83 and 11.99 seconds long. Sampled frames show ground movement near street geometry and a Titan, but do not establish the controller's selected Titan or the engine-level cause of spiralling. The source establishes that distant ApproachGround previously never looked for ODM anchors, and its progress test ignored movement direction. Those policy defects are addressed here; the engine's steering behavior is not proven fixed.

## Validation

Use City 1 / Training / Waves, one owned cadet, updated WaveCadet + CommandPanel + M2Watcher. Start with the default profile and leave Engage active for two to three minutes. Preserve the watcher file and video; expect behavior_profile, travel_probe, pursuit_progress, reposition_start/end and normal hook/attack events in the per-cadet decision trace. Compare matched starting situations with aerial preference 1 versus 5, then persistence 1 versus 5. Verify Hold during recovery, explicit Explore with Titans present, and low-gas interruption separately. Do not infer better play from more hooks or a different state.

Automated tests execute translated controller source with mocked observations. They cannot certify game parsing, steering, nape access, attacks, or organic-feeling behavior. Roll back the controller and watcher to a7e5fd9 to isolate these policy changes. M0/M1 sources and the command panel are unchanged.

API contracts remain Human.MoveTo(position: Vector3, range: float), Human.MoveToTarget(target: Object, range: float), and the existing LaunchHookLeft/AimAt/UseGas actions: https://github.com/AoTTG-2/CustomLogicDocumentation/blob/main/reference/Entities/Human.md . No new game API is introduced.
