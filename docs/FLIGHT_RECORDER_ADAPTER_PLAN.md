# Flight Recorder adapter and installed-build audit

**State:** the local transport and Python writer bridge are implemented and
tested with synthetic records. The Unity-side capture adapter is not built.
PR #15's offline writer work is the parent; M2 gameplay remains on its own
branch and is not changed here.

## Runtime findings

| Question | Finding | Confidence |
|---|---|---|
| Mono or IL2CPP | Read-only inspection of the exact supplied installation found `GameAssembly.dll`, `global-metadata.dat`, and `UnityPlayer.dll`, with no Mono managed assemblies. File sizes and SHA-256 values matched the supplied preflight. | High for this installed copy. |
| Unity version and executable architecture | PE header reports x64. The first 4096 bytes of `globalgamemanagers` contain candidate version string `2023.1.22f1`. | High for x64; medium for the Unity version because this is a string hint, not runtime confirmation. |
| Loader compatibility or permission | No loader directory is present in AoTTG2. The H3VR Thunderstore profile has BepInEx 5.4.17.0, Unity 5.6.7, Mono CLR 2.0, and `Assembly-CSharp.dll`; that is a Mono-era setup, not a file set to copy into this IL2CPP installation. No AoTTG2 loader permission or compatible IL2CPP package is established. | High for the inspected H3VR profile and AoTTG2 filesystem; AoTTG2 loader compatibility and permission unknown. |
| Physics observation point | Unity's `MonoBehaviour.FixedUpdate()` runs on the fixed interval and the physics calculations follow the callback. This is a documented **pre-physics** seam, not post-physics state. The actual callback ordering and runtime invocation still need calibration on this game build. | Generic Unity behavior: high; AoTTG2 runtime calibration: absent. |
| Game classes, hooks, projectiles, collisions, resources | No AoTTG2 IL2CPP interop assemblies or live process were available. No class mapping or event/collision callback is claimed. | Unknown. |

The read-only probe was run against the exact local AoTTG2 installation. Its
sizes and hashes matched the owner's supplied preflight. The JSON report is
kept in the local temporary directory; do not commit proprietary hashes or
the owner's installation path.

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
load in AoTTG2. The detected Unity version is a candidate string from the
installed files; verify it against a loader log before selecting a package.

MelonLoader also documents IL2CPP support and a .NET 6 runtime requirement.
It is not selected for this branch: its generic documentation offers no
AoTTG2-specific compatibility evidence, and it uses a proxy DLL installation
at the game root. No loader has been downloaded, installed, or run against the
game. The H3VR BepInEx 5.4.17 Mono profile must not be copied into AoTTG2.
Before installing anything, verify a specific BepInEx IL2CPP release against
the installed x64 Unity 2023.1.22f1 candidate and obtain explicit approval for
native loader use. No loader has been installed in AoTTG2.

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

## Installed-build audit and next prerequisites

The exact installed root has now been inspected read-only. To reproduce the
probe on this machine:

```powershell
py -3 scripts/inspect_unity_install.py "C:\Path\To\AoTTG2" --out "$env:TEMP\aottg2_build_preflight.json"
```

Keep the output local. It hashes the top-level executable/DLLs and relevant
metadata, reports PE architecture and searches only the first 4096 bytes of
`globalgamemanagers` for a Unity version string. The architecture and version
are hints, not ABI or compatibility proof. No game files were changed. The
remaining pre-install audit needs:

- confirmation that native IL2CPP plugin loading is permitted for this copy;
- one specific BepInEx IL2CPP release documented for the detected architecture
  and Unity version; and
- a reviewed backup and exact rollback list before any loader files are added.

If those conditions are met, a controlled first loader run can generate
`BepInEx/interop` assemblies and a loader log. These are still required to map
game types and compile the capture component. Do not copy the H3VR profile,
install multiple loaders, or start the game to probe compatibility. First
prepare and review the exact loader package, backup, and rollback list.

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
