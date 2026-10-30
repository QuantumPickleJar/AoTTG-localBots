# Player demonstration and telemetry policy — design draft

No player telemetry is collected by the MVP add-on. Any future data recording must be expressly **opt-in**, off by default, and transparent about what is stored and how to delete it.

Suggested fields for **self-recording only**: local-relative timestamp, world-relative position/velocity, anchor attempt and attachment outcomes, gas activation, hook release, generalized map/mission label, collision and checkpoint events. Use a pseudonymous session identifier generated locally. Do not collect usernames, chat, passwords, account IDs, IP addresses, exact device identifiers, or unrelated gameplay.

**Multiplayer:** The host's technical ability to observe another player's game state does not equal permission to record it. Require each human participant's affirmative permission before logging their data. Minimize any nonconsensual incidental information and do not upload it.

**Collection & upload:** Offline export first; explicit file review, then a separate affirmative upload step. All uploads can be skipped. Publish schema, version, license/consent terms, retention and deletion process. Do not infer permission to train on video recordings found online; prefer factual physics observations and links, or request license/permission before redistributing derived datasets.

**Technical caveat:** The documented Custom Logic API does not establish arbitrary local filesystem write access. A future telemetry exporter might need a permitted companion app or explicit manual console export. No hidden network reporting.
