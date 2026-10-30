"""Static checks for the reliability-candidate traversal controller."""
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
BASELINES = {
    "AICadetsTraversal.cl": "4c1d23c628d18f98500d2c3f20f5d954c1ea17fd",
    "AICadetsWatcher.cl": "5b3e1720b6e3d66b4fc35d0c9957306b67203b57",
    "AICadetsProbe.cl": "219fc9ab810998204c353833de868231a8736134",  # Git blob SHA verified against main
}


def git_blob_sha(path):
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def normalized_blob_sha(path):
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def validate(source):
    assert source.endswith("\n"), "Missing final newline"
    for number, line in enumerate(source.splitlines(), 1):
        assert "\t" not in line and line == line.rstrip(), f"Whitespace at {number}"
        assert (len(line) - len(line.lstrip())) % 4 == 0, f"Indent at {number}"
    tree = ast.parse(translate(source))
    cls = tree.body[0]
    assert cls.name == "AICadetsTraversalReliable"
    methods = {n.name: len(n.args.args) - 1 for n in cls.body if isinstance(n, ast.FunctionDef)}
    fields = {n.targets[0].id for n in cls.body if isinstance(n, ast.Assign)}
    assert methods["OnGameStart"] == methods["OnTick"] == 0
    receivers = {name: name for name in CONTRACT["types"]}
    receivers.update(
        {
            "self._scout": "Human",
            "host": "Human",
            "human": "Human",
            "hit": "LineCastHitResult",
            "editorHit": "LineCastHitResult",
            "velocity": "Vector3",
            "horizontal": "Vector3",
            "delta": "Vector3",
            "difference": "Vector3",
            "self._direction": "Vector3",
            "Network.MyPlayer": "Player",
            "host.Forward": "Vector3",
        }
    )

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
                assert (
                    node.attr in members(typ, "methods") or node.attr in members(typ, "properties")
                ), f"Unknown API {typ}.{node.attr}"
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
    loops = [n for n in ast.walk(tree) if isinstance(n, ast.For)]
    assert len(loops) == 1 and ast.unparse(loops[0].iter) == "Game.AIHumans"
    assert source.count("self.ConsiderAnchor(") == 10
    assert source.count("Game.SpawnHumanAt(") == 1
    assert 'Game.SpawnHumanAt(1, "Levi", LoadoutEnum.HumanBlades,' in source
    assert "class Main" not in source
    assert not re.search(r"\b(SendMessage|Upload|Refill|AddForce|MoveTo)\b", source)


def main():
    addon = ROOT / "addons"
    assert normalized_blob_sha(addon / "AICadetsTraversal.cl") == BASELINES["AICadetsTraversal.cl"], "Recovered baseline traversal changed"
    assert normalized_blob_sha(addon / "AICadetsWatcher.cl") == BASELINES["AICadetsWatcher.cl"], "Recovered baseline watcher changed"
    assert git_blob_sha(addon / "AICadetsProbe.cl") == BASELINES["AICadetsProbe.cl"], "Known-good v0.1.1 probe changed"
    validate((addon / "AICadetsTraversalReliable.cl").read_text())
    print("Reliable traversal static checks passed; baseline add-ons remain source-identical.")
    print("This check is static and cannot validate live AoTTG2 parser/physics behavior.")


if __name__ == "__main__":
    main()
