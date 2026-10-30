"""Offline API-name/arity and structural checks; NOT CL compilation/type checking."""
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
BASELINE_SHA256 = "2f44ba8b1be09192599d98d03b2f467e1fe8af6b2d2340aef09e844fdd146110"


def validate(source):
    assert source.endswith("\n"), "Missing final newline"
    for number, line in enumerate(source.splitlines(), 1):
        assert "\t" not in line and line == line.rstrip(), f"Whitespace at {number}"
        assert (len(line) - len(line.lstrip())) % 4 == 0, f"Indent at {number}"
    tree = ast.parse(translate(source))
    cls = tree.body[0]
    assert cls.name == "AICadetsTraversal"
    methods = {n.name: len(n.args.args) - 1 for n in cls.body if isinstance(n, ast.FunctionDef)}
    fields = {n.targets[0].id for n in cls.body if isinstance(n, ast.Assign)}
    assert methods["OnGameStart"] == methods["OnTick"] == 0
    # Explicit receiver map for this small script, not general type inference.
    receivers = {name: name for name in CONTRACT["types"]}
    receivers.update({"self._scout": "Human", "host": "Human", "human": "Human",
                      "hit": "LineCastHitResult", "editorHit": "LineCastHitResult",
                      "velocity": "Vector3", "horizontal": "Vector3", "delta": "Vector3",
                      "self._direction": "Vector3", "Network.MyPlayer": "Player",
                      "host.Forward": "Vector3"})

    def api_type(node):
        return receivers.get(ast.unparse(node))

    def members(kind, category):
        result = dict() if category == "methods" else set()
        for typ in (["Object", "Character", "Human"] if kind == "Human" else [kind]):
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
                assert node.func.id == "Vector3" and count == 3, "Expected explicit Vector3(x,y,z)"
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
            if target.startswith("self._scout."):
                assert target == "self._scout.Name", "No physics/resource/property cheats"
    # Reject unbounded language loops; only the one finite spawn-time scan is allowed.
    loops = [n for n in ast.walk(tree) if isinstance(n, ast.For)]
    assert len(loops) == 1 and ast.unparse(loops[0].iter) == "Game.AIHumans"
    assert source.count("Game.SpawnHumanAt(") == 1
    assert source.count("self.ConsiderAnchor(") == 5
    assert 'Game.SpawnHumanAt(1, "Levi", LoadoutEnum.HumanBlades,' in source
    assert "class Main" not in source
    assert not re.search(r"\b(SendMessage|Upload|Refill|AddForce|MoveTo)\b", source)


def main():
    baseline = (ROOT / "addons/AICadetsProbe.cl").read_bytes()
    assert hashlib.sha256(baseline).hexdigest() == BASELINE_SHA256, "Known-good v0.1.1 probe changed"
    validate((ROOT / "addons/AICadetsTraversal.cl").read_text())
    print("Pinned API names/arity, structure, bounded candidate count and baseline hash passed.")
    print("Not a CL compiler, type checker, physics simulation or in-game compatibility test.")


if __name__ == "__main__":
    main()
