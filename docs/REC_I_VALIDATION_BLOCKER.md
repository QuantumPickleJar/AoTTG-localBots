# REC-I status: game-side capture adapter not built

**Status: BLOCKED before installed-runtime testing.** The bounded Windows
transport and Python writer bridge are implemented and pass synthetic
end-to-end checks. There is no Unity capture component, no installed-build
interop set, and no installable recorder package. No game load or REC-I
gameplay result is claimed.

## Evidence available

The exact local AoTTG2 installation was inspected read-only. It reports an
x64 IL2CPP layout (`GameAssembly.dll`, `global-metadata.dat`, and
`UnityPlayer.dll`; no Mono assemblies). File sizes and SHA-256 values match
the owner's supplied preflight. The `globalgamemanagers` header contains the
candidate Unity version `2023.1.22f1`; verify it against a loader log before
choosing an IL2CPP loader. The report stays in the local temp directory; no
game binaries, hashes, or installation path are committed. No BepInEx or
MelonLoader files are installed in AoTTG2, and generated interop assemblies
are still unavailable. Do not treat another public release as a match.

The H3VR Thunderstore profile contains BepInEx 5.4.17.0 and its log reports
Unity 5.6.7 with Mono CLR 2.0 and managed `Assembly-CSharp.dll`. This is not
the IL2CPP loader package for AoTTG2; do not copy its files into the AoTTG2
folder.

The read-only [installed-build probe](../scripts/inspect_unity_install.py)
reports common layout indicators, hashes, PE architecture, possible Unity
version text from the `globalgamemanagers` header, and pre-existing loader
directories. Architecture and version are hints; the probe cannot establish
loader permission or compatibility.

## Work ready offline

- `tools/flight_writer.py` writes bounded `aicadets.flight.v1` frames, events,
  lifecycle records, and hashed chunks; recovery and analysis remain available.
- `plugin/FlightRecorder.TransportClient` builds for .NET 6 and .NET 8 and
  sends bounded, sequenced messages with acknowledgments over a local pipe.
- `tools/flight_transport.py` receives the Windows named pipe, enforces
  current-user pipe access and local-only clients, and forwards primitive
  records to the existing Python writer.
- Python tests exercise protocol parsing, retries/duplicates, sequence and
  frame-step loss, lifecycle/event mapping, incomplete metadata, and analyzer
  integrity. The Windows smoke script sends fixture data through the actual
  named pipe and verifies its hashed writer output.

These are Level 1 checks with synthetic records. They do not verify a Unity
callback, game actor class, `Rigidbody` semantics, collision provenance,
runtime overhead, or AoTTG2 compatibility. No M2 or Custom Logic gameplay file
is changed by this branch.

## Exact prerequisites for the next adapter build

1. Confirmation that native IL2CPP plugin loading is permitted for this
   installation.
2. One specific BepInEx IL2CPP release checked against the x64 build and
   candidate Unity 2023.1.22f1 version, plus a reviewed file-level
   backup/rollback before installation.
3. After the approved loader's first run, its generated interop assemblies
   and startup log, needed to map actual Humans, Titans, hooks, projectiles,
   and event callback types.
4. A compiled Unity component using the selected pre-physics `FixedUpdate`
   phase, explicit actor coverage, stable per-spawn IDs, and a read-only
   provider connected to the tested transport.

Do not request a gameplay capture until that component is compiled, the
installed-runtime smoke passes, and the deployment/rollback files have been
reviewed.

## REC-I validation card (blocked; not runnable)

```text
SESSION ID: REC-I
STATUS: BLOCKED — no game-side adapter or deployable package exists yet.
SOURCE BRANCH: codex/flight-recorder-il2cpp-adapter, based on PR #15; use the final PR head after CI passes.
FILES TO COPY / LOADER PATH: None. The .NET transport library and Python receiver are not a game plugin.
LAUNCHER ORDER: Not applicable until an adapter and approved loader package exist.
ENABLED: No gameplay test. For the later calibration, enable only the approved passive recorder alongside the agreed M2 test add-ons.
DISABLED: All unrelated experimental probes and all other players' telemetry collection.
MODE / MAP / HOST: Later private master-host, City 1 / Training / Waves; no session before Level 2.
FIRST 30–60 SECONDS: Not requested yet. When unblocked, first confirm plugin load, receiver handshake, fixed-step counter advance, stable actor IDs, clean shutdown, and no control/physics mutation.
EXPECTED COVERAGE: Only classes that the compiled adapter explicitly declares and the installed-runtime audit confirms. Collision, decisions, gas, hooks, and moving geometry stay unavailable until their source callbacks/fields are verified.
TRACE CHECKS: Run tools/analyze_flight.py against the local run; verify chunk hashes, exact frame-step gaps, IDs across lifecycle, phase label, per-field provenance, queue/drop counters, and capture_complete.
ACCEPTANCE: No unaccounted loss; valid hashes; phase and class coverage match direct video/runtime checks; measured CPU/frame-time/storage stay within pre-agreed limits; safe shutdown and rollback.
FAILURE / ROLLBACK: Stop the run, preserve local logs and the incomplete trace, disable/remove only manifest-listed recorder files, and restore the reviewed backup. Do not change M2 gameplay code.
ARCHIVE TO RETURN: After the adapter exists, return the recorder's local run folder (chunks, chunk_manifest.json, metadata.json, state.json), receiver and loader logs, the short motion cross-check video, and performance/drop summary. Do not include game binaries or other players' data.
```

Keep the current video-first M2 validation path unchanged until REC-I can be
run with a compiled, passive adapter.
