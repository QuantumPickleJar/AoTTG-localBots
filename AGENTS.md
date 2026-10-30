# Instructions for coding agents and ChatGPT Work

Goal: preserve and extend AoTTG2 single-player and approved cooperative play through local, physically grounded AI Scout characters.

- Treat `addons/AICadetsProbe.cl` as AoTTG2 **Custom Logic**, NOT ordinary compilable C#.
- Source of truth: official `AoTTG-2/CustomLogicDocumentation` API and `AoTTG-2/AoTTG2-Example-Content` examples. Quote exact signatures in PR descriptions and cite source URLs. The engine and API may change.
- Keep each PR scoped to one testable behavior, include expected game-observed behavior, and a rollback path.
- Never claim in-game execution verified using only Python static tests.
- Do not silently collect other players' telemetry. No tracking or cloud service as a default dependency.
- Preserve mission scripts by using the `addon` interface where possible. Do not replace mission logic without explicit design review.
- Open PRs instead of merging directly; attach CI results and the manual game test checklist.
- Keep game authority on the master client for AI mutations; never assume master-client migration works without testing.
- No AI-training infrastructure dependency.
