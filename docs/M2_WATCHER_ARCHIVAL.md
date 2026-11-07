# M2 watcher archival and slot recycling

This is a local-only filesystem utility for the M2 Custom Logic watcher. The official Custom Logic API places saved data under Documents/Aottg2/PersistentData; PersistentData.SaveToFile(fileName, encrypted) saves the current persistent-data store to a named file. The archive therefore preserves each selected file as opaque bytes instead of parsing or rewriting its properties.

The utility handles only direct children named AICadetsM2Watch followed by digits, with no extension, .txt, or .json. It does not call PersistentData.Clear, touch other filenames, upload data, or modify gameplay add-ons.

## Recommended iterative workflow

1. Close AoTTG2.
2. Start start_m2_watcher_archival.bat before launching the game. The monitor first archives and verifies existing watcher files, removes only those verified watcher files to free the 0–99 output slots, and then waits for AoTTG2.
3. Launch the private M2 lobby with the M2 WaveCadet, CommandPanel/F8, and M2Watcher add-ons.
4. After AoTTG2 exits, the monitor captures final watcher files, writes the SHA-256 manifest, verifies the archive, and only then removes the archived watcher files. The monitor remains available for the next iteration. Press Ctrl+C in its window to stop.

Start the monitor before the game. If AoTTG2 is already open, the script attaches to the current session; it cannot prepare slots before that run.

The launcher uses AoTTG2.exe as the process name. If this installation uses another executable name, run the script directly and set --process-name to the executable's exact process name.

## Commands

Read-only inventory:

    py -3 tools/archive_m2_watcher.py preflight

One-time archive, keeping original files:

    py -3 tools/archive_m2_watcher.py archive

Archive and recycle exact watcher files after AoTTG2 is closed:

    py -3 tools/archive_m2_watcher.py archive --prune-verified

Monitor one session and stop afterward:

    py -3 tools/archive_m2_watcher.py monitor --once --prune-verified

The continuous monitor used by the Windows launcher:

    py -3 tools/archive_m2_watcher.py monitor --prune-verified

Default source directory:

    %USERPROFILE%\Documents\Aottg2\PersistentData

Default archive root:

    %USERPROFILE%\Documents\Aottg2\Recorders\M2WatcherArchive

Pass --source-dir or --archive-root to use other paths. Each capture session receives a unique directory containing compressed byte snapshots and manifest.json. The manifest records original-byte and compressed-byte SHA-256 hashes, observed revisions, vanished source files, and any pruning results.

## Safety and recovery

Pruning is opt-in. The --prune-verified option makes the tool remove only exact M2 watcher filenames, and only after each archived copy decompresses to the original byte length and SHA-256. It also requires AoTTG2 to be closed and stops if a source changes, cannot be read stably, has an ambiguous watcher-like name, or lacks a verified archive snapshot. Unrelated files are never candidates. A failed or interrupted prune leaves a manifest showing its state; successfully archived originals remain recoverable.

Restore the latest captured version of each filename:

    py -3 tools/archive_m2_watcher.py restore --archive-dir "%USERPROFILE%\Documents\Aottg2\Recorders\M2WatcherArchive\<archive-id>"

Restore refuses to overwrite a different file. Add --force-overwrite only when intentionally replacing a conflicting watcher file. Close AoTTG2 before restoring.

The archive is a full copy of each selected SaveToFile snapshot, so it may contain persistent properties beyond the watcher trace. Keep the archive local and protected. The program never opens or edits unrelated PersistentData files. It does not delete or rotate old archives automatically.
