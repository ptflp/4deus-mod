import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "fourdeus_backend"


def module_name(path: Path) -> str:
    relative = path.relative_to(PROJECT_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def internal_import_graph() -> dict[str, set[str]]:
    modules = {
        module_name(path): path
        for path in BACKEND_ROOT.rglob("*.py")
    }
    graph = {name: set() for name in modules}
    for name, path in modules.items():
        package = (
            name
            if path.name == "__init__.py"
            else name.rpartition(".")[0]
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level == 0:
                continue
            relative = "." * node.level + (node.module or "")
            target = importlib.util.resolve_name(relative, package)
            candidates = (
                target,
                *(
                    f"{target}.{alias.name}"
                    for alias in node.names
                ),
            )
            graph[name].update(
                candidate
                for candidate in candidates
                if candidate in modules
            )
    return graph


class BackendArchitectureTests(unittest.TestCase):
    def test_decky_entrypoint_bootstraps_an_isolated_import(self):
        script = textwrap.dedent(
            f"""
            import logging
            import runpy
            import sys
            import types

            decky_plugin = types.ModuleType("decky_plugin")
            decky_plugin.logger = logging.getLogger("entrypoint-test")
            decky_plugin.DECKY_USER_HOME = {str(PROJECT_ROOT)!r}
            decky_plugin.DECKY_PLUGIN_DIR = {str(PROJECT_ROOT)!r}
            sys.modules["decky_plugin"] = decky_plugin

            namespace = runpy.run_path({str(PROJECT_ROOT / "main.py")!r})
            assert namespace["Plugin"].__module__ == "fourdeus_backend.plugin"
            """
        )
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", script],
            cwd="/tmp",
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_entrypoints_remain_thin(self):
        limits = {
            "main.py": 10,
            "nested_desktop_mouse.py": 15,
            "trackpad_metrics.py": 15,
        }
        for relative_path, limit in limits.items():
            with self.subTest(path=relative_path):
                lines = (
                    PROJECT_ROOT / relative_path
                ).read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(len(lines), limit)

    def test_backend_modules_remain_bounded(self):
        for path in BACKEND_ROOT.rglob("*.py"):
            with self.subTest(path=path.relative_to(PROJECT_ROOT)):
                lines = path.read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(len(lines), 800)

    def test_internal_import_graph_has_no_cycles(self):
        graph = internal_import_graph()
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(module: str, stack: tuple[str, ...]):
            if module in visiting:
                start = stack.index(module)
                cycle = (*stack[start:], module)
                self.fail("Import cycle: " + " -> ".join(cycle))
            if module in visited:
                return
            visiting.add(module)
            for dependency in graph[module]:
                visit(dependency, (*stack, module))
            visiting.remove(module)
            visited.add(module)

        for module in graph:
            visit(module, ())


if __name__ == "__main__":
    unittest.main()
