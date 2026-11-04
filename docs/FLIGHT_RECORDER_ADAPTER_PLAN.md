# Flight Recorder adapter and installed-build audit

**State:** The read-only Unity IL2CPP adapter, local named-pipe producer, and Python writer bridge are implemented in PR #16, now based on `main` after PR #15 merged. Version 0.1.9 adds bounded retries for transient Windows permission failures during atomic writer-state replacement and prevents receiver cleanup from masking a fatal writer error. It retains offline Titan-death attribution, direct frame serialization, protected queue capacity, and receipt-verified installer upgrades. M2 gameplay is unchanged. The adapter is opt-in and not yet accepted as an M2 sensor; 0.1.9 still needs private runtime and performance validation.

## Installed build findings

| Question | Finding | Confidence |
|---|---|---|
| Runtime backend | GameAssembly.dll, global-metadata.dat, and UnityPlayer.dll are present; Mono managed game assemblies are absent. BepInEx generated IL2CPP interop from this exact installation. | High: local preflight and loader log. |
| Architecture and Unity version | x64; Unity 2023.1.22f1. | High: PE inspection and BepInEx runtime log. |
| IL2CPP metadata | Metadata version 29.1 was read during interop generation. | High for this installed copy. |
| Loader | BepInEx 6.0.0-be.791 started successfully and generated interop. The recorder initialized in a main-menu smoke and produced the supplied partial gameplay trace. | High for startup and observed partial capture; full coverage/performance remains unverified. |
| Generated game surface | Interop exposes Characters.Human, BaseCharacter, BaseTitan, Hook/HookUseable, CharacterSpawner, and Projectiles.BaseProjectile plus sampled properties. The plugin compiles against these assemblies. | High for metadata and compilation; gameplay field values are not yet verified. |
| Sampling phase | Injected MonoBehaviour.FixedUpdate ran in the main-menu smoke. Unity documents FixedUpdate as preceding physics; relative order among AoTTG2 scripts is unknown. | High for callback startup and generic Unity phase; gameplay ordering uncalibrated. |
| Collision callback | Human.OnCollisionEnter(Collision) is present in generated interop and Harmony-patched; 209 callbacks were observed in the supplied gameplay capture. | High for callback execution in that run; coverage and causal damage meaning remain unverified. |

The H3VR BepInEx 5 Mono profile was not copied. AoTTG2 uses a separate BepInEx IL2CPP build. No game binary was modified or included in the package. Generated interop stays local and is not committed.

## Selected implementation

Use BepInEx IL2CPP with an injected MonoBehaviour sampled from FixedUpdate. This route is supported by the successful BepInEx 6.0.0-be.791 start and interop generation on this exact IL2CPP build. Capture refuses any runtime other than x64 Unity 2023.1.22f1.

The adapter copies Unity/game values to primitive JSON-compatible data on Unity's callback thread. Version 0.1.9 serializes the frame DTO once into a bounded UTF-8 envelope; a bounded .NET producer sends it over a local Windows named pipe, and the existing Python receiver calls tools/flight_writer.py. The pipe worker never calls Unity APIs. Ordinary frame and control traffic cannot consume the final two queue slots or 16 KiB reserved for frame-gap accounting and a stop record. The Python writer retries Windows `PermissionError` during atomic state-file replacement with bounded backoff; a permanent failure still marks the run incomplete, and receiver cleanup preserves the primary failure without a second exception. The installer replaces a prior receipt-verified installation only after checking its hashes and contents, and refuses to alter an unmanaged or changed folder. Messages use aicadets.flight.v1 and its existing hashed chunk manifest. No transforms, physics properties, inputs, game state, or controller decisions are written or changed by the plugin. The optimization requires a new installed-game performance measurement.

## Current capture coverage

- Photon-owned Humans; AI Humans/Titans only on the local Photon master. Non-local player-controlled characters and AI on non-master clients are excluded.
- Human-linked Hook components from left/right HookUseable.Hooks. Hook state, transform, hook point, and anchor are sampled. State changes between samples are observations, not direct hook callbacks.
- Projectiles sampled only when their owner passes the same local ownership filter. Their game velocity field is kept separate from Rigidbody velocity.
- Position/rotation from Transform. Linear/angular velocity only from a non-kinematic root Rigidbody. Kinematic, child-body, or transform-only objects are not mislabeled as dynamic Rigidbody samples.
- Human/Titan state, AI flag, team, health, dead/grounded flags, current speed and animation; Human gas; Titan/Hook state; projectile game velocity.
- Human.OnCollisionEnter Harmony postfix events include callback provenance, relative velocity, impulse, contact count, and collider identity. Character collisions require both actors to pass the ownership filter. No gameplay invocation has been observed yet.
- Active scene name/handle changes detected by comparing SceneManager.GetActiveScene at FixedUpdate boundaries. Timestamp is detection time; very short transitions may be missed.
- First-seen lifecycle is inferred from the 0.5-second census. Despawn is recorded when Unity's object-null state is observed. IDs combine per-kind Unity instance ID and reuse generation, stable only within one run.
- Capture-work last, p95, and maximum milliseconds over the latest 256 callbacks are emitted about every five simulation seconds. The measurement covers discovery/sampling/serialization/queue submission, not whole-game frame time.

The registry is refreshed by a whole-scene census every configured 0.5 seconds, then sampled each FixedUpdate. Short-lived objects between censuses may be missed. Exceeding the entity cap stops capture as incomplete instead of silently skipping entities.

## Explicitly unavailable or unverified

Moving environment geometry; Titan collision callbacks; direct attack/damage/death/rescue events; structured M2 commands/personality decisions; complete actor coverage; relative script order; and 0.1.9 mission performance/REC-I calibration. Health and dead fields are sampled and are not promoted to event callbacks. Existing M2 key/value logs are not fabricated into complete decisions. Private/local-host testing is required.

## Build and transport

The plugin builds against interop generated from x64 Unity 2023.1.22f1 with BepInEx 6.0.0-be.791. The package contains plugin/transport DLLs, receiver/writer/analyzer, a portable Python 3.14.10 x64 runtime and license, launcher/install/rollback scripts, example config, and manifest; no game, loader, or proprietary interop binaries. Recording defaults disabled.

The producer queue is bounded by count and bytes, sequences messages with acknowledgments, retries pipe disconnections, and accounts for dropped frames/control messages. Ordinary controls cannot use the critical reserve; an overflow still stops the capture incomplete, but the adapter gets reserved space to report the frame gap and final stop. The receiver uses a current-user-only named pipe and writes via the existing Python writer. Offline protocol tests cover adapter-shaped frames, events, lifecycle, health metadata, and both slot- and byte-reserve exhaustion; they do not emulate Unity.

Package install/rollback details are in [FLIGHT_RECORDER_IL2CPP_PACKAGE_README.md](FLIGHT_RECORDER_IL2CPP_PACKAGE_README.md). The private gameplay validation card is in [REC_I_VALIDATION_BLOCKER.md](REC_I_VALIDATION_BLOCKER.md).

## Validation levels

| Level | Result | Establishes |
|---|---|---|
| 1 — Offline | All 117 Python tests pass; transport builds for .NET 6 and .NET 8; ordered-pipe/backpressure and Windows pipe-to-writer recovery smokes pass; the Unity plug-in builds against this installed game's interop with zero warnings/errors. The 0.1.9 package build is pending. | Synthetic writer/transport behavior and installed-interop compilation only; no gameplay or performance claim. |
| 2 — Installed-runtime smoke | 0.1.8 initialized and connected to the receiver. The latest local run persisted 8,197 frames and 282 events in six verified chunks, then ended `writer_error` when Windows denied replacement of `writer_state.json`; one enqueued frame was not durable. This is partial runtime/transport evidence, not a clean-stop pass. | 0.1.9 has not been installed or smoke-tested. The retry and cleanup changes are only offline-verified so far. |
| 3 — REC-I gameplay calibration | The earlier 0.1.5 health window reached 1.8008 ms p95 at a 20 ms fixed step, above the 1.0 ms limit. The latest run does not establish 0.1.9 performance or calibration. | Requires a new private session, p95/max measurement, zero transport losses, verified chunks, motion cross-check, and phase/coverage review. Preserve startup and steady-state health windows separately. |

## References

- [BepInEx IL2CPP installation guide](https://docs.bepinex.dev/master/articles/user_guide/installation/unity_il2cpp.html)
- [BepInEx plugin template](https://docs.bepinex.dev/master/articles/dev_guide/plugin_tutorial/2_plugin_start.html)
- [Il2CppInterop class injection](https://github.com/BepInEx/Il2CppInterop/blob/master/Documentation/Class-Injection.md)
- [Unity MonoBehaviour.FixedUpdate](https://docs.unity3d.com/ja/current/ScriptReference/MonoBehaviour.FixedUpdate.html)
- [AoTTG2 Custom Logic API documentation](https://github.com/AoTTG-2/CustomLogicDocumentation)
- [AoTTG2 example content](https://github.com/AoTTG-2/AoTTG2-Example-Content)

AoTTG2 Custom Logic remains its own language. No .cl source or mission logic is changed by this PR.
