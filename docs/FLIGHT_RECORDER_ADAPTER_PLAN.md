# Flight Recorder adapter and installed-build audit

**State:** the local transport and Python writer bridge are implemented and
tested with synthetic records. The Unity-side capture adapter is not built.
PR #15's offline writer work is the parent; M2 gameplay remains on its own
branch and is not changed here.

## Runtime findings

| Question | Finding | Confidence |
|---|---|---|
| Mono or IL2CPP | The supplied preflight reports `GameAssembly.dll`, `global-metadata.dat`, and `UnityPlayer.dll`, with no Mono assemblies. | High for the supplied installation record; not re-read from game files here. |
| Unity version and executable architecture | Not established. The game executable and `Aottg2_Data/globalgamemanagers` were not available in the inspected workspace. The read-only probe now reports PE architecture and a Unity version-string hint when present. | Unknown for this installed copy. |
| Loader compatibility or permission | No loader is installed or validated for this build. BepInEx and MelonLoader both document generic IL2CPP support, but neither establishes AoTTG2 compatibility or permission. | Unknown. |
| Physics observation point | Unity's `MonoBehaviour.FixedUpdate()` runs on the fixed interval and the physics calculations follow the callback. This is a documented **pre-physics** seam, not post-physics state. The actual callback ordering and runtime invocation still need calibration on this game build. | Generic Unity behavior: high; AoTTG2 runtime calibration: absent. |
| Game classes, hooks, projectiles, collisions, resources | No AoTTG2 IL2CPP interop assemblies or live process were available. No class mapping or event/collision callback is claimed. | Unknown. |

The owner-provided preflight includes hashes and sizes for game binaries; they
were not independently verified because those files were absent here. Keep
the local preflight JSON private and do not commit proprietary files or the
owner's installation path.

## Selected implementation route

If the installed build and its use policy allow a local plugin, the first
native prototype will use **BepInEx IL2CPP** with an injected Unity
`MonoBehaviour` sampling in `FixedUpdate`. This is the selected development
route because the official BepInEx guide provides an IL2CPP plugin template
whose entry point is `public override void Load()`, and the official
Il2CppInterop class-injection guide documents
`ClassInjector.RegisterTypeInIl2Cpp<T>()` followed by
`gameObject.AddComponent<T>()`. The BepInEx IL2CPP install guide says this
path currently uses bleeding-edge builds. These sources support a prototype
route; they do not establish a compatible version, permission, or successful
load in AoTTG2.

MelonLoader also documents IL2CPP support and a .NET 6 runtime requirement.
It is not selected for this branch: its generic documentation offers no
AoTTG2-specific compatibility evidence, and it uses a proxy DLL installation
at the game root. No loader has been downloaded, installed, or run against the
game. The candidate must be re-evaluated after obtaining the installed
executable and Unity version.

References:

- [BepInEx IL2CPP installation](https://docs.bepinex.dev/master/articles/user_guide/installation/unity_il2cpp.html)
- [BepInEx plugin template and `public override void Load()`](https://docs.bepinex.dev/master/articles/dev_guide/plugin_tutorial/2_plugin_start.html)
- [Il2CppInterop class injection and `ClassInjector.RegisterTypeInIl2Cpp<T>()`](https://github.com/BepInEx/Il2CppInterop/blob/master/Documentation/Class-Injection.md)
- [Unity `MonoBehaviour.FixedUpdate()`](https://docs.unity3d.com/ja/current/ScriptReference/MonoBehaviour.FixedUpdate.html)
- [MelonLoader IL2CPP requirements and install/uninstall instructions](https://github.com/LavaGang/MelonLoader)
- [AoTTG2 Custom Logic API documentation](https://github.com/AoTTG-2/CustomLogicDocumentation)
- [AoTTG2 example content](https://github.com/AoTTG-2/AoTTG2-Example-Content)

The Unity callback is declared in the adapter as `void FixedUpdate()`; Unity
documents it as part of the fixed physics loop, with physics calculations
following that callback. See the linked Unity API reference above.

AoTTG2 Custom Logic remains its own scripting language. Its published API and
examples are the source of truth for `.cl` code, but they do not create a
native C# or named-pipe API. No mission logic or Custom Logic add-on is changed
in this adapter branch.

## Planned game-side capture boundary

The first Unity implementation will use a persistent injected component and
copy only primitive values inside the Unity callback. It will use an
adapter-owned monotonic step counter, a monotonic timestamp, the measured
`Time.fixedDeltaTime`, and phase `fixed_update_pre_physics`. It will not call
Unity APIs from the transport thread. Any change to the callback or state
sampling phase must be captured as provenance, not silently normalized.

Once the exact generated interop assemblies are available:

1. Map the actual Human, Titan, ODM hook, projectile, and relevant world types
   from the installed `GameAssembly.dll` and metadata. Do not infer C# classes
   from Custom Logic names.
2. Identify a spawn/despawn registry or an observed lifecycle source. Assign
   IDs from a source handle plus spawn generation. If an entity is only first
   discovered by a census, label that evidence as discovery, not observed spawn.
3. For each actor, record transform pose; capture velocity only when a real
   Rigidbody or game-owned velocity field is available. Include whether the
   Rigidbody is kinematic. Transform-only motion must not be presented as
   Rigidbody simulation.
4. Inspect the relevant gas, hook, animation, and state fields in interop. Omit
   inaccessible values and preserve field provenance.
5. Identify actual collision/attack/damage/death/rescue callbacks. A velocity
   change is not a collision. Controller key/value logs are not complete
   structured decisions; never synthesize replay inputs from them.
6. Avoid per-step whole-scene scans. Prefer verified actor registration;
   use any low-rate census only for discovery, with its cadence and coverage
   marked explicitly.

No capture-provider source is included yet because the class names and
assemblies that it must compile against are missing. The transport library is
not an empty game plugin and must not be deployed into AoTTG2 by itself.

## Implemented transport and writer connection

`plugin/FlightRecorder.TransportClient` is a bounded .NET 6/.NET 8 named-pipe
producer. It accepts only immutable JSON primitive payloads, uses a persistent
local pipe connection with per-message acknowledgments, retries after
disconnect, reserves queue capacity for control messages, and emits explicit
frame-loss envelopes. The Windows Python receiver uses a current-user DACL,
rejects remote pipe clients, validates ordering and size, and calls the
existing `FlightRecorderWriter` API. Full details and the opt-in config are in
[FLIGHT_RECORDER_TRANSPORT.md](FLIGHT_RECORDER_TRANSPORT.md).

Transport or source loss calls `FlightRecorderWriter.mark_incomplete(...)`.
The writer keeps the normal `aicadets.flight.v1` frame/event format and adds a
bounded `incomplete_reasons` summary to final metadata. It never labels a
missing step as a sampled frame. The test-only C# producer and Windows smoke
test emit synthetic fixture data only.

## Installed-build audit prerequisites

The audit can resume when the exact installed game root is available. First
run the read-only probe:

```powershell
py -3 scripts/inspect_unity_install.py "C:\Path\To\AoTTG2" --out "$env:TEMP\aottg2_build_preflight.json"
```

Keep the output local. It hashes the top-level executable/DLLs and relevant
metadata, reports PE architecture and searches only the first 4096 bytes of
`globalgamemanagers` for a Unity version string. The architecture and version
are hints, not ABI or compatibility proof. Also record, locally:

- the exact `Aottg2.exe` file/product version and architecture;
- Unity version from `globalgamemanagers` and from any loader startup log;
- `GameAssembly.dll`, `global-metadata.dat`, `UnityPlayer.dll`, and
  `globalgamemanagers` hashes;
- any pre-existing BepInEx/MelonLoader files and versions;
- whether local plugin loading is permitted for this installation; and
- a reviewed backup and exact rollback list before any loader files are added.

If BepInEx is allowed and the audited architecture/version is compatible, a
controlled first loader run would generate `BepInEx/interop` assemblies and a
loader log. These files are the required compile inputs for the game type
mapping. Do not install a loader or start the game merely to generate them
without a backed-up, reviewed game-root package and rollback. Do not install
multiple loaders to probe compatibility.

## Validation boundary

| Level | Current state | What it establishes |
|---|---|---|
| Offline | Passed locally; CI is added in this branch. | .NET transport build, protocol tests, Windows named pipe to Python writer, hashed chunk analysis. Uses synthetic data. |
| Installed-runtime smoke | Not run. | Requires exact game root, permitted compatible loader, and a compiled Unity capture component. |
| REC-I gameplay calibration | Not runnable. | Requires the owner's private game session after Level 2 passes. |

The current branch does not establish game load, physics phase, entity
coverage, collisions, or runtime overhead. It does not claim a native recorder
is ready.

## Rollback

This branch only adds source, tests, docs, and local receiver tooling. It has
not changed the game installation or M2 gameplay files. Future deployment must
include a pre-install copy and a precise manifest of only the files added; its
rollback removes those recorder/loader files and restores any backed-up file
that the chosen loader replaces.
