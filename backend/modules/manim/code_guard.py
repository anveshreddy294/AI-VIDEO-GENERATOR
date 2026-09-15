"""Conservative preflight for generated scene code. Not an OS sandbox."""
import ast

FORBIDDEN = {"eval", "exec", "compile", "open", "input", "__import__", "getattr", "setattr",
             "delattr", "globals", "locals", "vars", "breakpoint", "help", "exit", "quit"}


def validate_scene_code(code, strict=False):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name not in ("manim", "numpy") for alias in node.names):
            raise ValueError("Generated scene uses a forbidden import")
        if isinstance(node, ast.ImportFrom) and node.module not in ("manim", "numpy", "modules.manim.templates.chalkboard_scene"):
            raise ValueError("Generated scene uses a forbidden import")
        if isinstance(node, ast.Name) and (node.id in FORBIDDEN or node.id.startswith("__")):
            raise ValueError("Generated scene uses a forbidden builtin")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Generated scene uses forbidden introspection")
    if strict and not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                          and n.func.attr in ("play", "add") for n in ast.walk(tree)):
        raise ValueError("Strict rendering rejects blank scenes")
    return tree
