# REC-I status: blocked on installed-game audit

**Status: BLOCKED — no current installed AoTTG2 files or game process are available in this workspace.** No Unity adapter or native recorder has been built, copied, or loaded, and no REC-I pass is claimed. Prompts 1 and 2 remain completed and analyzed; post-Prompt-2 M2 stabilization continues separately.

## What is missing

The installation needed to establish the actual Unity version, Mono/IL2CPP backend, permitted mod-loading path, plugin compatibility, and accessible physics callbacks was not available for inspection. The October 31 Custom Logic documentation is evidence about its published API surface, not the currently installed executable. Without that audit, a native plugin or a purported post-physics callback would be guesswork.

The official [AoTTG2 Team itch.io release page](https://aottg2-team.itch.io/aottg2) was reachable for listing inspection. As listed on November 3, 2026, it shows the November 1 release, including a Windows launcher ZIP (50 MB, Version 8) and a Windows Standalone64 ZIP (1 GB, Version 7). Selecting the Standalone64 download in the cloud browser displayed the site's “Thanks for downloading” acknowledgement, but no browser download event or archive path appeared within 30 seconds. The archive could not be inspected in this cloud environment; this does not establish that it is unavailable elsewhere. The listing is not evidence that the release matches the user's installed copy.

`scripts/inspect_unity_install.py` is a read-only layout hint. It can report whether common Mono or IL2CPP files exist and hash selected filenames, but it **cannot** identify the exact Unity version, establish loader compatibility, or validate callbacks. It does not read or upload binary contents. Its result is a preflight input, not a feasibility verdict:

```powershell
py -3 scripts/inspect_unity_install.py "D:\Games\AoTTG2" --out build_preflight.json
```

Run it against the current launcher installation root only if that path is available. Keep the JSON local; it contains installation filenames and hashes.

## Work that is ready offline

- `tools/analyze_flight.py` accepts the `aicadets.flight.v1` trace format and optional hashed chunk manifest; it reports declared dropped frames and entity samples separately.
- `tools/flight_writer.py` now provides a Unity-independent bounded writer core, immutable snapshots, structured events, chunk hashing, explicit gap accounting, configurable storage limits, checkpoint state and conservative recovery. Synthetic tests/benchmarks do not establish a supported Unity connection.
- Synthetic fixtures and tests exercise multi-entity tracking, fixed-step coverage, gaps, integrity failure recovery, event correlation and evidence grades.
- `tools/replay_decisions.py` extracts serialized planner decisions for deterministic offline policy comparisons. It does not replay Unity physics. Its `python_reference_policy_demo` agreement is separate from M2 controller behavior.
- `tools/m2_trace_adapter.py` preserves the existing M2 `LogEvent` observations and reports missing decision-replay fields. It does not fabricate M3 profiles, candidate gates, decision IDs, stable spawn IDs, physics steps, or frames.
- `tests/test_wave_m2.py` executes the actual M2 Custom Logic source through the project's constrained translation harness and mocked APIs. Those source-driven checks are not installed-game parser or physics validation.
- `addons/AICadetsPrimitiveObserver.cl` is an opt-in, low-rate Custom Logic fallback for an isolated probe. It is not a physics-step recorder, has no verified post-physics phase, and cannot establish full entity/collision coverage.

There is still no game-side Unity adapter, callback, inter-process transport, coverage registry tied to game objects, or deployable recorder package. The Python writer queue and storage cap are implemented only within the runtime-independent core. The offline reader cannot certify data that no verified recorder produced.

## REC-I gate

**Do not deploy or label the Python core as an installed-game recorder.** The game-side test remains blocked until the installed files are available for a feasibility audit, an allowed compatible loader is verified, a passive adapter and transport are reviewed, and exact deployment files and rollback are known.

When those prerequisites are met, REC-I needs a fresh private City 1 / Training / Waves session with the M2 trio and only a compatible passive recorder. Calibrate a short capture against video; compare global physics-step IDs, timestamps/phase, representative dynamic entity classes, collision evidence, drops, queue pressure, disk output, and overhead. Pass only with verified phase and complete coverage for the claimed classes, accounted-for drops, intact chunks, and safe measured overhead. Until that pass, preserve the existing video-first instructions in `docs/GAMEPLAY_VALIDATION_HARNESS.md`.

**Current result:** `BLOCKED` — no installed-game audit, deployment files, or runtime evidence. This is an explicit blocker, not an inconclusive game test.

## REC-I Validation Card (blocked; not runnable)

```text
SESSION ID: REC-I
STATUS: BLOCKED — do not start this session from the current artifacts.
SOURCE: offline reader and runtime-independent writer core only; no game-side adapter or recorder commit exists.
FILES TO COPY / LOADER PATH: None. No native recorder package or compatible loader has been identified.
ENABLE: No session. When unblocked, M2 WaveCadet + CommandPanel + a compatible observer/recorder only.
DISABLE: M0 Probe, M1 Traversal/Reliable/Watcher, and any independent active probe. Keep the M2Watcher only if compatibility is established.
MAP / MODE / HOST: Private master-host, City 1 / Training / Waves, after the installed-game audit.
PRECONDITION: Verify the current installation, Unity version/backend, allowed loader and a reviewed passive implementation.
ACTIONS: None until that precondition is met. Do not use the Custom Logic fallback as a substitute for REC-I.
ARCHIVE / PATH: No recorder output path exists yet. After implementation, use a local, capped run directory and archive intact chunks plus metadata/manifest.
EXPECTED EVIDENCE: Verified post-physics phase; complete global step IDs and monotonic timestamps; declared entity-class coverage; observed collision provenance; explicit gap/drop ranges; queue, disk and overhead metrics.
PASS: All claimed physics steps are present or every loss is accounted for; no silent drops; hashes and recovery validate; measured overhead and storage remain within reviewed limits.
FAIL / PARTIAL / INCONCLUSIVE: Any step loss, unaccounted coverage, invalid phase, unreadable chunks, unsafe overhead, or unavailable class is reported explicitly.
ROLLBACK: No files are currently installed. If a future build is tested, disable/remove only its exact recorder files and restore the pre-test Addons folder copy.
```
