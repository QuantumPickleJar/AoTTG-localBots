"""Tiny source-driven control-flow harness, NOT an AoTTG2 interpreter.

Only translates this project's braces, functions, if/elif/else, collection for,
assignments and calls to Python. Engine APIs/physics are mocked by tests.
Rejects unsupported statements. Does not establish CL parser/type semantics,
copy semantics, engine timing, ownership transfer or actual movement.
"""
import ast
import re
from dataclasses import dataclass
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "addons/AICadetsTraversal.cl"


def expression(text):
    # Only rewrite outside quoted strings (including # or ! inside strings).
    parts = re.split(r'("(?:\\.|[^"\\])*")', text)
    for i in range(0, len(parts), 2):
        part = parts[i].replace("&&", " and ").replace("||", " or ")
        part = re.sub(r"!(?!=)", "not ", part)
        for cl, py in (("true", "True"), ("false", "False"), ("null", "None")):
            part = re.sub(rf"\b{cl}\b", py, part)
        parts[i] = part
    return "".join(parts)


def translate(source):
    output = []
    depth = 0
    pending = False
    for number, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "{":
            assert pending, f"Unexpected opening brace: {number}"
            depth += 1
            pending = False
            continue
        assert not pending, f"Expected brace: {number}"
        if line == "}":
            depth -= 1
            assert depth >= 0
            continue
        if line.startswith("addon "):
            translated = "class " + line[6:] + ":"
            pending = True
        elif line.startswith("function "):
            match = re.fullmatch(r"function (\w+)\((.*)\)", line)
            assert match, f"Unsupported function: {number}"
            name, args = match.groups()
            translated = f"def {name}(self{', ' if args else ''}{args}):"
            pending = True
        elif line == "else":
            translated = "else:"
            pending = True
        elif re.match(r"(if|elif|for) \(", line):
            kind, rest = line.split(" (", 1)
            assert rest.endswith(")")
            translated = kind + " " + expression(rest[:-1]) + ":"
            pending = True
        else:
            assert line.endswith(";"), f"Unsupported statement: {number}: {line}"
            translated = expression(line[:-1])
        output.append("    " * depth + translated)
    assert depth == 0 and not pending, "Unbalanced structure"
    result = "\n".join(output) + "\n"
    tree = ast.parse(result)
    allowed = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.arguments, ast.arg,
               ast.Assign, ast.Expr, ast.If, ast.For, ast.Return, ast.Call,
               ast.Attribute, ast.Name, ast.Constant, ast.Load, ast.Store,
               ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Add, ast.Sub,
               ast.Mult, ast.Div, ast.USub, ast.Not, ast.And, ast.Or, ast.Eq,
               ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
    for node in ast.walk(tree):
        assert isinstance(node, allowed), f"Unsupported syntax: {type(node).__name__}"
    return result


def load_controller(environment, source=None):
    namespace = dict(environment)
    exec(compile(translate(source or SOURCE.read_text()), str(SOURCE), "exec"), namespace)
    return namespace["AICadetsTraversal"]()


@dataclass(frozen=True)
class Vector:
    X: float
    Y: float
    Z: float

    def __add__(self, other):
        return Vector(self.X + other.X, self.Y + other.Y, self.Z + other.Z)

    def __sub__(self, other):
        return Vector(self.X - other.X, self.Y - other.Y, self.Z - other.Z)

    def __mul__(self, scalar):
        return Vector(self.X * scalar, self.Y * scalar, self.Z * scalar)

    @property
    def Magnitude(self):
        return sqrt(self.X ** 2 + self.Y ** 2 + self.Z ** 2)

    @property
    def Normalized(self):
        length = self.Magnitude
        return self * (1.0 / length) if length else Vector(0, 0, 0)

    @staticmethod
    def Distance(a, b):
        return (a - b).Magnitude

    @staticmethod
    def Dot(a, b):
        return a.X * b.X + a.Y * b.Y + a.Z * b.Z

    @staticmethod
    def Normalize(value):
        return value.Normalized
