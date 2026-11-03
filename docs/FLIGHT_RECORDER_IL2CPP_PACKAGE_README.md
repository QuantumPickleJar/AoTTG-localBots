# AoTTG2 IL2CPP Flight Recorder package

**Build:** 0.1.5, compiled against interop generated from the installed AoTTG2 build

**Runtime:** x64, Unity 2023.1.22f1, IL2CPP metadata 29.1, BepInEx 6.0.0-be.791, .NET 6
**Capture default:** disabled

This opt-in package contains the game-side BepInEx IL2CPP plugin, bounded named-pipe producer, Python receiver/writer/analyzer, and a portable Python 3.14.10 x64 embeddable runtime with its license. It does not contain AoTTG2 binaries, loader binaries, or generated/proprietary game interop. An earlier 0.1.5 build from the same adapter source passed a main-menu smoke: 1,982 ordered frames, one verified hashed chunk, 8 events, zero drops or analyzer anomalies, graceful stop, and zero entities. At about 20 ms fixedDeltaTime, the first five-second health window reported capture-work p95 0.7254 ms and maximum 103.9691 ms; later windows reported p95 0.1726–0.5526 ms and maxima 6.9426–12.7446 ms. The deterministic 0.1.5 package then started and wrote 5,717 ordered menu frames and 23 events to one SHA-256-verified chunk with no entities, drops, or analyzer anomalies. That retry ended with `capture_complete=false` and `receiver_interrupted` after the game and BepInEx console were closed together; it does not count as a clean-shutdown pass. Neither menu run establishes gameplay entity coverage, collision callback firing, or mission performance. A later gameplay-length capture provides preliminary evidence, but REC-I calibration is not accepted; see below.

## Latest gameplay capture

The supplied 19m09s trace is a successful writer/transport run: 56,970 frame markers across 35 SHA-256-verified chunks, 779 events, 54 lifecycle records, and 27 entity IDs (6 Titans, 3 Humans, 18 Hooks). `capture_complete=true`; there are no declared drops, missing frame markers, or incomplete reasons. The sample phase remains unverified and the analyzer reports 277 `unexplained_velocity_change` anomalies.

One Titan changed from health 1/dead false to health 0/dead true with a `Dead` state and `die.front` animation, then was observed destroyed. An AI-controlled Human had 13 observed collision callbacks with that Titan in the preceding 3.56 seconds and was in an attack state around the death sample. This strongly suggests that the cadet got the kill, but no damage-source/correlated death event was captured, so direct attribution remains unconfirmed.
This is a local BepInEx plug-in loaded by the game client at startup. It is not an AoTTG Custom Logic `.cl` add-on selected from a lobby. Keep the game folder writable: BepInEx writes its own configuration, logs, and generated interop. The recorder installer only writes its two DLLs and receipt into its dedicated plug-in folder; the game binaries were not changed.

## Captured scope

- Characters are sampled only when Photon reports local ownership, or when the character is AI-controlled and this client is Photon master. Remote player-controlled characters and AI on non-master clients are excluded.
- Owner-linked Hooks discovered from the Human left/right HookUseable.Hooks lists. Hook transform, state, hook point and anchor are sampled. Changes between Hook.State samples are emitted with sampled-field-transition evidence, not as direct hook callbacks.
- Projectiles whose owners pass the same local ownership filter.
- Transform position/rotation. Linear and angular velocity come only from a non-kinematic root Rigidbody. Game-reported projectile velocity remains separate from Rigidbody velocity. Kinematic and transform-only objects are labeled explicitly.
- Human/Titan state, AI/team, health, dead/grounded flags, current speed and animation; Human gas; Hook state; and projectile velocity field.
- Human.OnCollisionEnter Harmony postfix event records with relative velocity, impulse, contact count and collider provenance. The callback fired in the supplied run (209 records), demonstrating execution in that run but not full collision coverage. Player-versus-player collisions are omitted.
- Active scene name/handle changes detected by polling at FixedUpdate boundaries. The recorded time is detection time; very short transitions can be missed.
- Capture-work last/p95/max milliseconds over a rolling 256-callback window, sent in health events every five simulation seconds. This covers adapter discovery, sampling, JSON serialization and queue submission, not all game frame work.

First-seen lifecycle is inferred from the 0.5-second discovery census. Destruction is recorded when Unity's object-null state is observed. Transient entities between censuses may be missed. IDs are stable within the run and use per-kind instance-ID generations; they are not cross-run identities.

The injected FixedUpdate callback is pre-physics; order relative to AoTTG2 scripts is unknown. Step is the adapter callback ordinal. Time uses Unity fixed simulation time, with monotonic wall elapsed separately preserved. No transforms, physics properties, inputs, or gameplay state are written.

Unavailable/unverified: moving world geometry, Titan-side collision callbacks, direct damage/death/rescue attribution events, structured controller decisions, complete actor/collision coverage, callback phase, and REC-I performance acceptance. Human collision callbacks have been observed and one Titan death state was sampled, but neither provides a damage-source event. See docs/REC_I_VALIDATION_BLOCKER.md for the current calibration status.

## Install

1. Close AoTTG2. Confirm BepInEx 6.0.0-be.791 has generated BepInEx/interop for this exact installation. Follow the [BepInEx IL2CPP installation guide](https://docs.bepinex.dev/master/articles/user_guide/installation/unity_il2cpp.html) for a compatible local install; do not copy the H3VR Mono profile.
2. Extract the package to a local directory.
3. Run the guarded installer in PowerShell:

       .\scripts\install_flight_recorder.ps1 -GameRoot "C:\Path\To\AoTTG2" -PackageRoot "C:\Path\To\AoTTG2-FlightRecorder-0.1.5"

4. Keep BepInEx/config/org.aicadets.aottg2.flight-recorder.cfg at Enabled = false for the startup check. Launch to the main menu and verify the plugin load and capture-disabled lines in BepInEx/LogOutput.log. Then close the game.
5. Copy configs/flight-recorder-transport.example.json to a new local config, set recording_enabled to true and choose a new empty output directory. Start the bundled receiver first:

       .\scripts\start_flight_recorder_receiver.ps1 -PackageRoot "C:\Local\Path\AoTTG2-FlightRecorder-0.1.5" -ConfigPath "C:\Local\Path\flight-recorder-transport.json"

6. Set the plugin config Enabled = true only for a private/solo test, with the receiver running. Launch the game and verify the run/pipe handshake before entering the test session. Use the REC-I card for add-on and scene setup.
7. After the game closes, set Enabled = false and analyze the run:

       .\runtime\python.exe .\tools\analyze_flight.py "C:\Local\Path\recordings\run-<run-id>" --out "C:\Local\Path\analysis"

The launcher runs the packaged embeddable Python runtime without changing PATH or installing a system-wide Python. It starts the receiver in a hidden window and writes local stdout/stderr logs next to the receiver config. The Windows receiver uses a current-user DACL and rejects remote named-pipe clients. No external network or cloud telemetry is used by the recorder.

If a game process disconnects before sending its stop message, the receiver finalizes that run as incomplete. A later client connection with a new run ID is written to a separate run directory; the interrupted run is not continued or overwritten. A valid stop ends the receiver, so start it again before a later capture.

## Rollback

Close the game and run the packaged remove_flight_recorder.ps1 with the same GameRoot. It validates the install receipt and file hashes, refuses modified/unlisted files, then removes only the two recorder DLLs and their receipt. It leaves BepInEx, loader files, generated interop, and user configuration untouched. Review and remove the recorder config separately if desired. Loader removal is a separate action.

## Validation boundary

A successful build establishes compilation against the installed interop. The supplied gameplay-length run completed with 56,970 frames, 779 events, 35 verified chunks, zero drops, and a complete stop. It showed Human, Hook, and Titan samples and 209 observed Human.OnCollisionEnter callbacks. One Titan was sampled into its dead state and later observed destroyed; an AI Human had repeated collisions and an attack animation shortly before, which suggests but does not prove kill attribution because no damage-source event exists. The run is not a REC-I pass: phase remains unverified, the analyzer reported 277 `unexplained_velocity_change` anomalies, and later-window capture-work p95 reached 1.8008 ms (above the 1.0 ms criterion), while the 53.6163 ms max remained under 60 ms. The scene label stayed `Startup`, so the map/mode is not established. A short video cross-check and anomaly/phase review remain before accepting calibration.
