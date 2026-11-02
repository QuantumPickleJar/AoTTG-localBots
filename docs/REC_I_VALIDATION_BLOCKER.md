# REC-I status: blocked on installed-game audit

**Status: BLOCKED — no current AoTTG2 installation or game process is available in this workspace.** No native recorder has been built, copied, or loaded, and no REC-I pass is claimed.

## What is missing

The installation needed to establish the actual Unity version, Mono/IL2CPP backend, permitted mod-loading path, plugin compatibility, and accessible physics callbacks was not available for inspection. The October 31 Custom Logic documentation is evidence about its published API surface, not the currently installed executable. Without that audit, a native plugin or a purported post-physics callback would be guesswork.

`scripts/inspect_unity_install.py` is a read-only layout hint. It can report whether common Mono or IL2CPP files exist and hash selected filenames, but it **cannot** identify the exact Unity version, establish loader compatibility, or validate callbacks. It does not read or upload binary contents. Its result is a preflight input, not a feasibility verdict:

```powershell
py -3 scripts/inspect_unity_install.py "D:\Games\AoTTG2" --out build_preflight.json
```

Run it against the current launcher installation root only if that path is available. Keep the JSON local; it contains installation filenames and hashes.

## Work that is ready offline

- `tools/analyze_flight.py` accepts the reference `aicadets.flight.v1` trace format and optional hashed chunk manifest.
- Synthetic fixtures and tests exercise multi-entity tracking, fixed-step coverage, gaps, integrity failure recovery, event correlation and evidence grades.
- `tools/replay_decisions.py` extracts serialized planner decisions for deterministic offline policy comparisons. It does not replay Unity physics.
- `addons/AICadetsPrimitiveObserver.cl` is an opt-in, low-rate Custom Logic fallback for an isolated probe. It is not a physics-step recorder, has no verified post-physics phase, and cannot establish full entity/collision coverage.

There is no game-side writer, bounded native queue, coverage registry, capture cap implementation, or deployable recorder package in this change. The offline reader cannot certify data that no verified recorder produced.

## REC-I gate

**Do not deploy or label any current artifact a recorder.** The game-side test remains blocked until a current installation is available for the feasibility audit, an allowed compatible loader is verified, a passive capture implementation is reviewed, and its exact files and rollback are known.

When those prerequisites are met, REC-I needs a fresh private City 1 / Training / Waves session with the M2 trio and only a compatible passive recorder. Calibrate a short capture against video; compare global physics-step IDs, timestamps/phase, representative dynamic entity classes, collision evidence, drops, queue pressure, disk output, and overhead. Pass only with verified phase and complete coverage for the claimed classes, accounted-for drops, intact chunks, and safe measured overhead. Until that pass, preserve the existing video-first instructions in `docs/GAMEPLAY_VALIDATION_HARNESS.md`.

**Current result:** `BLOCKED` — no installed-game audit, deployment files, or runtime evidence. This is an explicit blocker, not an inconclusive game test.

## REC-I Validation Card (blocked; not runnable)

```text
SESSION ID: REC-I
STATUS: BLOCKED — do not start this session from the current artifacts.
SOURCE: recorder PR head commit (offline analyzer only; no game-side recorder commit exists).
FILES TO COPY / LOADER PATH: None. No native recorder package or compatible loader has been identified.
ENABLE: No session. When unblocked, M2 WaveCadet + CommandPanel + a compatible observer/recorder only.
DISABLE: M0 Probe, M1 Traversal/Reliable/Watcher, and any independent active probe. Keep the M2Watcher only if compatibility is established.
MAP / MODE / HOST: Private master-host, City 1 / Training / Waves, after the installed-game audit.
PRECONDITION: Verify the current installation, Unity version/backend, allowed loader and a reviewed passive implementation.
ACTIONS: None until that precondition is met. Do not use the Custom Logic fallback as a substitute for REC-I.
ARCHIVE / PATH: No recorder output path exists yet. After implementation, use a local, capped run directory and archive intact chunks plus metadata/manifest.
EXPECTED EVIDENCE: Verified post-physics phase; complete global step IDs and monotonic timestamps; declared entity-class coverage; observed collision provenance; explicit gap/drop ranges; queue, disk and overhead metrics.
PASS: No missing physics steps or silent drops for claimed coverage; hashes and recovery validate; measured overhead and storage remain within reviewed limits.
FAIL / PARTIAL / INCONCLUSIVE: Any step loss, unaccounted coverage, invalid phase, unreadable chunks, unsafe overhead, or unavailable class is reported explicitly.
ROLLBACK: No files are currently installed. If a future build is tested, disable/remove only its exact recorder files and restore the pre-test Addons folder copy.
```
