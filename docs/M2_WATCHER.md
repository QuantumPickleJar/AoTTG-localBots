# Optional read-only M2 flight observer

This is a separate, opt-in observer derived from the **in-game proven M1 v3 watcher**. It does not alter M2 movement or combat. It is not needed to start M2. First test `AICadetsWaveCadet.cl` alone from `fix/m2-global-target-acquisition`, without the M1 addons or watcher.

Once M2 actually acquires a Titan and issues hook commands, enable this second add-on in a fresh, private host lobby:

- `AICadetsWaveCadet`
- `AICadetsM2Watcher`

Disable M1 Probe/Traversal/Reliable and the original `AICadetsWatcher` during isolated M2 testing.

The new watcher observes an **owned** `AICadetsM2-1` through `AICadetsM2-4` (the first discovered) and writes `Documents/AoTTG2/PersistentData/AICadetsM2WatchN`, from N=0..99. The saved JSON property is `AICadetsM2WatchTrace`, separate from v3 M1's trace. On host startup it writes `watch_started`, then `scout_found` upon finding the M2 cadet. It watches up to 25 seconds after discovery, sampling flight at 5 Hz plus fixed-tick hook/ground changes and possible impact clues. A second separate game/lobby is recommended per recording.

The M2 controller's own `[AI Cadets M2]` chat gives **target acquisition, state decisions and attack events**; this watcher only observes physical bot motion. Match game time/run setup with screenshots or video. v3's near-surface `possible_impact` events are not proof of physical collision callbacks.

**Safety and limitations:**
- No player telemetry; no bot commands.
- Saves local PersistentData only. This service shares its PersistentData collection with other scripts and its files could contain unrelated keys. Inspect and remove unrelated keys *before* sharing. It does not call `Clear()`.
- Does not work for more than one M2 cadet per watcher instance. It will pick the first owned matching M2 bot. Multi-bot instrumentation should be a separate enhancement.
- Unverified in the game interpreter as an M2-specific add-on, although the underlying v3 M1 pattern has worked in-game.
- If M2 fails to spawn with this observer enabled, disable **only this new watcher** and retest M2 alone. Do not alter M2 code to compensate for observer problems.
