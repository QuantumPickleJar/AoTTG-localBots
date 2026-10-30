"""Static smoke-check only: validates obvious AoTTG2 Custom Logic API usage.

Not a Custom Logic compiler and not an in-game integration test.
"""
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "addons" / "AICadetsProbe.cl"
s = FILE.read_text(encoding="utf-8")
assert "addon AICadetsProbe" in s and "class Main" not in s
required = [
    "function OnGameStart()", "function OnSecond()", "function OnTick()",
    "Network.IsMasterClient", "Game.SpawnHumanAt(",
    "LoadoutEnum.HumanBlades", "Physics.LineCast(",
    "LaunchHookLeft(", "IsHookedLeft", "UseGas(true)",
    "UseGas(false)", "ReleaseHookLeft()", "SetDisplayName(",
]
for token in required:
    assert token in s, f"Missing expected API use: {token}"
assert s.count("Game.SpawnHumanAt(") == 1, "MVP should spawn only one bot per round"
# Game's SpawnAIHumanAt resolves an exact costume preset name. Empty names
# can produce null and a NullReferenceException inside the game wrapper.
assert 'Game.SpawnHumanAt(0, "",' not in s, "Invalid unnamed custom costume preset"
assert 'Game.SpawnHumanAt(1, "Levi", LoadoutEnum.HumanBlades,' in s, ("Expected a known named Costume1 preset for probe v0.1.1")
assert s.count("{") == s.count("}"), "Unbalanced braces (naive check)"
assert s.count("(") == s.count(")"), "Unbalanced parentheses (naive check)"
assert "SendMessage" not in s and "Upload" not in s, "MVP must not transmit telemetry"
print("Static smoke checks passed; in-game parsing and behavior still unverified.")
