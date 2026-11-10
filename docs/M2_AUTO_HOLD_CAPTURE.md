# M2 one-click Hold capture

**Status:** Candidate test tooling. Static checks pass locally; AoTTG2 Custom Logic parsing and live behavior still need a game run.

This flow captures one host-owned cadet's `EngageDirect -> Hold -> EngageDirect` sequence. The host creates the private lobby and selects the capture button once. After that, the CommandPanel waits for the live controller and passive watcher, sends the orders, and records acknowledgements and sampled movement. It does not change the WaveCadet controller or move the character directly.

## Validation card

- **Profile:** M2-L0, one-cadet Direct test.
- **Source:** `feat/m2-exploration-and-orders` plus the auto-capture candidate commit. Record the exact commit and F8 build tag before testing.
- **Files to deploy:** `addons/AICadetsCommandPanel.cl`, `addons/AICadetsM2Watcher.cl`. Keep the WaveCadet file at the exact source hash used for the run.
- **Enable:** `AICadetsWaveCadet`, `AICadetsCommandPanel`, `AICadetsM2Watcher`.
- **Disable:** `AICadetsProbe`, `AICadetsTraversal`, `AICadetsTraversalReliable`, `AICadetsWatcher`, and every other active test add-on.
- **Lobby:** Private master-host City 1 / Training / Waves; Wave 1 with one ordinary Titan; one human-controlled player; one owned `AICadetsM2-1`. Verify the actual add-on list and Direct driver in the running lobby. Do not infer them from saved settings.
- **Recorder:** Leave Flight Recorder capture disabled for this test. The M2 watcher is the required evidence source.
- **Before deployment:** Save the installed panel and watcher files, their SHA-256 hashes, and the current watcher-file inventory. Confirm the watcher has a free output slot. Keep all existing watcher files in a hash-verified backup.

## Run steps

1. Start a fresh private lobby with the settings above. Confirm the local player is the master host and the only human-controlled participant.
2. Wait for one live owned M2-1, a fresh controller status, an active watcher file, and the watcher-ready cadet flag.
3. Open the F8 CommandPanel and select **RUN AUTO HOLD CAPTURE (M2-1)** once. Do not steer the cadet or issue Recovery while the sequence runs.
4. Let the sequence finish or time out. Close the game normally and preserve the watcher output and game logs. Review the matching run ID, build tag, event trace, and `path_counted` samples.
5. Restore the exact pre-run installed panel and watcher files and verify their hashes. Preserve the WaveCadet file and all M1 add-ons.

## Expected events and outcomes

- The runner sends `EngageDirect` only after the watcher has found the owned M2-1, created its output file, and published a fresh movement sample. It waits for the matching order acknowledgement.
- Before sending Hold, the runner requires `ApproachGround` against a nonzero Titan target for at least two seconds and at least 2.0 units of watcher-measured path from that target's baseline.
- After a fresh Hold acknowledgement, it observes for five seconds. A path increase of at most 2.0 units is recorded as `within_2_units`; a larger increase is recorded as `over_2_units` and fails the Hold movement gate.
- The runner then sends `EngageDirect` again. It records completion only after the same target is in `ApproachGround` and the watcher measures at least 2.0 additional units of path.
- The watcher measures distance between periodic position samples. A single step greater than 100 units is excluded from the cumulative path and logged with `path_counted=False`; inspect these samples before scoring the run. Displacement is evidence of observed motion, not proof that Hold or Engage caused it.
- A missing watcher, stale heartbeat/sample, lost master authority, order without a matching acknowledgement, path reset, missing ground movement, or timeout makes the run fail or inconclusive. A completed order sequence alone is not a movement pass.
- This flow does not validate recovery retry, target gain, combat damage, Titan kills, multiplayer authority migration, or recorder timing/performance.

## Manual result record

```text
Session ID:
AoTTG2 build / Unity build:
Source commit / F8 build tag:
Private master-host / only human confirmed:
Map / mode / Wave 1 Titan count:
Enabled / disabled add-ons and installed hashes:
Watcher filename / run ID / saved trace hash:
EngageDirect order and matching acknowledgement:
Same-target ApproachGround observed:
Pre-Hold path delta:
Hold acknowledgement / five-second path delta:
Resume order and matching acknowledgement:
Post-resume same-target path delta:
Outcome: PASS / FAIL / PARTIAL / INCONCLUSIVE
Observed vs inferred:
Rollback hashes verified:
Raw watcher and game logs remain local:
```

## Rollback

Restore `addons/AICadetsCommandPanel.cl` and `addons/AICadetsM2Watcher.cl` from the source revision immediately before this candidate (currently `5bec459`) and restore the installed files from the hash-verified pre-run backups. Do not change `addons/AICadetsWaveCadet.cl`, M1 files, mission scripts, or unrelated `PersistentData` files.

## API references

The runner uses the documented `OnGameStart()` and `OnTick()` callbacks from the [official callback reference](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/callbacks/main.md). It uses `PersistentData.FileExists(fileName: string) -> bool`, `PersistentData.SetProperty(property: string, value: float|int|string|bool|null)`, and `Vector3.Distance(a: Vector3, b: Vector3) -> float` as documented in the [PersistentData API](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Game/PersistentData.md) and [Vector3 API](https://github.com/AoTTG-2/CustomLogicDocumentation/blob/38796d52a99c2dd76ec08a111395628a9151d07e/reference/Collections/Vector3.md).
