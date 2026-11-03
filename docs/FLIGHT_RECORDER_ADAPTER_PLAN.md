# Flight Recorder adapter and installed-build audit plan

## Known starting point

The installed-build preflight is strongly IL2CPP-indicated:

- `GameAssembly.dll`, `global-metadata.dat`, and `UnityPlayer.dll` are present;
- Mono managed assemblies and `mono_mscorlib` were not detected; and
- the preflight reported the `Aottg2_Data` layout.

This narrows the integration search, but it does not identify the Unity
version, a supported loader, an injection ABI, or a usable physics callback.
The Python writer is complete offline infrastructure only.

## Adapter implementation stages

### 1. Freeze an installed-build audit record

Run the read-only probe from this branch against the exact directory containing
`Aottg2.exe` and `Aottg2_Data`:

```powershell
py -3 scripts/inspect_unity_install.py "C:\Actual\Path\To\AoTTG2" --out build_preflight.json
```

Keep `build_preflight.json` local. Do not commit proprietary binaries,
installation paths, or metadata that identifies another player's machine.
Record separately, if available, the executable and DLL file versions, Unity
player version, game build/version string, installed mod-loader name/version,
and whether the loader supports IL2CPP on this build. Hashes are useful for
matching a later audit, but a hash alone does not establish compatibility.

Required audit outputs before adapter coding:

1. exact game-root path confirmed by the user;
2. preflight JSON and its timestamp;
3. `Aottg2.exe`, `GameAssembly.dll`, `global-metadata.dat`, and
   `UnityPlayer.dll` presence/version/hash inventory;
4. Unity version and scripting-backend evidence from the installed files;
5. permitted local loader/injection mechanism, if one exists; and
6. a documented rollback/backup location for any later adapter experiment.

The probe is read-only. Any loader installation or game-file modification is a
separate, explicitly approved step and must not be folded into the offline
writer PR.

### 2. Select one supported runtime seam

Use the official Custom Logic documentation and examples as the source of
truth for any Custom Logic-facing API claim:

- [CustomLogicDocumentation](https://github.com/AoTTG-2/CustomLogicDocumentation)
- [AoTTG2-Example-Content](https://github.com/AoTTG-2/AoTTG2-Example-Content)

The adapter decision must answer whether the installed build permits:

- a game-side callback at or near the physics step;
- enumeration of the local human cadets, Titans, and relevant objects;
- read-only position, velocity, rotation, state, gas, hook, and animation
  observations;
- stable per-spawn/entity identifiers and event correlation; and
- bounded local file or IPC access from the game process.

If no supported seam is found, stop at the audit and keep the recorder
offline-only. Do not substitute a video parser, teleportation, fake physics,
or a Custom Logic `PersistentData` poller as physics-step evidence.

### 3. Build the smallest game-side adapter

The first adapter should be observation-only and master-client scoped. It
should copy primitive values into a transport-neutral snapshot, then hand the
copy to a local transport. It must not mutate M2 control, mission scripts,
movement, combat, ownership, gas, or health.

The snapshot envelope should carry:

- run ID, build tag, monotonic frame/step, and game time;
- fixed-step or callback-phase evidence;
- stable spawn/entity ID, actor kind, position, velocity, rotation, and
  observed state;
- explicit actor coverage counts and missing-field/loss notices; and
- correlation IDs for observed events, never guessed decision inputs.

The existing Python API is the sink contract:
`FlightWriter.submit_frame(FrameSnapshot)` and
`FlightWriter.submit_event(RecorderEvent)`. The Unity-side adapter must not
import Python or assume that these classes can run inside IL2CPP.

### 4. Add a local-only transport bridge

Prefer a bounded local transport supported by the selected runtime seam. On
Windows, evaluate a named pipe first; use a loopback TCP fallback only if the
loader/runtime cannot expose a pipe. Bind only to the local machine, use a
per-run nonce, bound message sizes, and preserve explicit transport gaps.
There is no cloud endpoint, telemetry service, or other-player collection in
this design.

The bridge should be a separate process/module boundary:

`AoTTG2 adapter -> local transport -> Python FlightWriter -> local run files`

The writer remains responsible for queue limits, hashed chunks, recovery, and
loss accounting. The adapter remains responsible for runtime observations and
their provenance. Neither side may silently fill a missing physics frame.

### 5. Validate in gates

Use a private master-host session only after the adapter loads without changing
M2 behavior:

1. handshake and clean shutdown with zero actor mutation;
2. one known human plus one known Titan, checking IDs and coverage;
3. callback-phase calibration against a short video and game clock;
4. deliberate transport interruption, queue pressure, and recovery checks;
5. event provenance and missing-frame accounting; and
6. measured overhead and a short REC-I capture.

Only after these gates pass may the project describe the installed-game
recorder as functioning. Until then, call it an offline writer plus an
unbuilt/unvalidated adapter plan.

## Rollback

The clean integration PR is documentation, Python tooling, tests, examples,
and the local preflight only. Roll it back by reverting that PR or deleting
the separate audit checkout; it does not touch the installed game or the M2
add-ons. Any later runtime adapter must ship with a file backup, a disable
switch, and a documented restore procedure before private validation.
