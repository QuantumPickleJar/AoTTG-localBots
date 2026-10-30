"""Static checks for M2 Wave cadet addon."""
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from cl_harness import translate  # noqa: E402

CONTRACT = json.loads((ROOT / "tests/api_contract.json").read_text())


def validate(source):
    assert source.endswith("\n"), "Missing final newline"
    for number, line in enumerate(source.splitlines(), 1):
        assert "\t" not in line and line == line.rstrip(), f"Whitespace at {number}"
        assert (len(line) - len(line.lstrip())) % 4 == 0, f"Indent at {number}"
    tree = ast.parse(translate(source))
    cls = tree.body[0]
    assert cls.name == "AICadetsWaveCadet"
    methods = {n.name: len(n.args.args) - 1 for n in cls.body if isinstance(n, ast.FunctionDef)}
    fields = {n.targets[0].id for n in cls.body if isinstance(n, ast.Assign)}
    assert methods["OnGameStart"] == methods["OnTick"] == 0
    receivers = {name: name for name in CONTRACT["types"]}
    receivers.update(
        {
            "self._cadet": "Human",
            "self._cadet.Forward": "Vector3",
            "self._cadet.Velocity": "Vector3",
            "host": "Human",
            "human": "Human",
            "titan": "Titan",
            "t": "Titan",
            "victim": "Character",
            "killer": "Character",
            "self._target": "Titan",
            "self._target.Forward": "Vector3",
            "hit": "LineCastHitResult",
            "editorHit": "LineCastHitResult",
            "velocity": "Vector3",
            "horizontalVelocity": "Vector3",
            "toNape": "Vector3",
            "toGoal": "Vector3",
            "baseDirection": "Vector3",
            "baseDir": "Vector3",
            "direction": "Vector3",
            "flatTarget": "Vector3",
            "toTarget": "Vector3",
            "behindDir": "Vector3",
            "delta": "Vector3",
            "difference": "Vector3",
            "away": "Vector3",
            "horizontal": "Vector3",
            "horizontalAway": "Vector3",
            "retreatPoint": "Vector3",
            "recoverGoal": "Vector3",
            "self._direction": "Vector3",
            "Network.MyPlayer": "Player",
            "host.Forward": "Vector3",
            "Game.Titans": "List",
            "Game.Humans": "List",
            "Game.PlayerHumans": "List",
            "Game.AIHumans": "List",
        }
    )

    def api_type(node):
        return receivers.get(ast.unparse(node))

    def members(kind, category):
        result = dict() if category == "methods" else set()
        parents = [kind]
        if kind == "Human":
            parents = ["Object", "Character", "Human"]
        elif kind == "Titan":
            parents = ["Object", "Character", "Titan"]
        elif kind == "Character":
            parents = ["Object", "Character"]
        for typ in parents:
            if typ in CONTRACT["types"]:
                result.update(CONTRACT["types"][typ][category])
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            receiver = ast.unparse(node.value)
            if receiver == "self":
                assert node.attr in fields | methods.keys(), f"Unknown self member {node.attr}"
            elif api_type(node.value):
                typ = api_type(node.value)
                assert node.attr in members(typ, "methods") or node.attr in members(typ, "properties"), f"Unknown API {typ}.{node.attr}"
            else:
                raise AssertionError(f"Unmapped receiver: {receiver}; review API contract")
        if isinstance(node, ast.Call):
            count = len(node.args)
            if isinstance(node.func, ast.Name):
                if node.func.id == "Vector3":
                    assert count == 3, "Expected Vector3(x,y,z)"
                else:
                    assert node.func.id in {"Range"}, f"Unknown global call: {node.func.id}"
            elif ast.unparse(node.func.value) == "self":
                assert count == methods[node.func.attr], f"Wrong helper arity {node.func.attr}"
            else:
                typ = api_type(node.func.value)
                assert typ, f"Unknown call {ast.unparse(node.func)}"
                assert node.func.attr in members(typ, "methods"), f"Unknown method {typ}.{node.func.attr}"
                spec = members(typ, "methods")[node.func.attr]
                assert spec["min_args"] <= count <= spec["max_args"], spec["signature"]
        if isinstance(node, ast.Assign):
            target = ast.unparse(node.targets[0])
            if target.startswith("self._cadet."):
                assert target in {"self._cadet.Name"}, "No direct movement/resource cheats via property writes"
    assert "class Main" not in source
    assert source.count("Game.SpawnHumanAt(") == 1
    assert not re.search(r"\b(Upload|SendMessage|SetPreload|RestartWithPreloadSettings)\b", source)


def main():
    addon = ROOT / "addons"
    validate((addon / "AICadetsWaveCadet.cl").read_text())
    # Preserve known M0 probe bytes.
    probe_data = (addon / "AICadetsProbe.cl").read_bytes()
    probe_sha = hashlib.sha1(b"blob " + str(len(probe_data)).encode() + b"\0" + probe_data).hexdigest()
    assert probe_sha == "219fc9ab810998204c353833de868231a8736134"
    print("M2 wave static checks passed.")
    print("This check is static and does not validate in-game mission integration.")


if __name__ == "__main__":
    main()
