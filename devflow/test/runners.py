from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def detect_test_stack(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root).expanduser().resolve()
    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or (root / "tests").exists():
        return _detect_python_stack(root)
    if (root / "package.json").exists():
        return _detect_javascript_stack(root)
    if _has_plain_javascript_or_html(root):
        return _detect_plain_html_js_stack(root)
    if (root / "pom.xml").exists() or (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        return _detect_java_stack(root)
    return {
        "language": "unknown",
        "framework": "unknown",
        "commands": [],
        "generators": _optional_generators(["coverup", "pynguin", "evosuite"]),
    }


def _detect_python_stack(root: Path) -> dict[str, Any]:
    has_pytest = (root / "pytest.ini").exists()
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            text = pyproject.read_text(encoding="utf-8")
        except OSError:
            text = ""
        has_pytest = has_pytest or "pytest" in text or "[tool.pytest" in text
    framework = "pytest" if has_pytest else "unittest"
    command = "uv run pytest" if has_pytest else "uv run python -m unittest discover -s tests"
    return {
        "language": "python",
        "framework": framework,
        "commands": [{"name": framework, "command": command}],
        "generators": _optional_generators(["coverup", "pynguin"]),
    }


def _detect_javascript_stack(root: Path) -> dict[str, Any]:
    package_path = root / "package.json"
    framework = "npm"
    try:
        payload = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    dependencies = {}
    for key in ("dependencies", "devDependencies"):
        if isinstance(payload.get(key), dict):
            dependencies.update(payload[key])
    test_script = ""
    scripts = payload.get("scripts") if isinstance(payload.get("scripts"), dict) else {}
    if scripts:
        test_script = str(scripts.get("test") or "")
    if "vitest" in dependencies or "vitest" in test_script:
        framework = "vitest"
    elif "jest" in dependencies or "jest" in test_script:
        framework = "jest"
    return {
        "language": "javascript",
        "framework": framework,
        "commands": [{"name": framework, "command": "npm.cmd test"}] if test_script else [],
        "generators": [],
    }


def _detect_plain_html_js_stack(root: Path) -> dict[str, Any]:
    commands = []
    if shutil.which("node") is not None:
        commands.append({"name": "node-assert", "command": "node test/game.test.js"})
    return {
        "language": "javascript",
        "framework": "html-js",
        "commands": commands,
        "generators": [],
    }


def _has_plain_javascript_or_html(root: Path) -> bool:
    for pattern in ("*.html", "*.js", "*.mjs", "*.cjs"):
        if any(path.is_file() for path in root.glob(pattern)):
            return True
    return False


def _detect_java_stack(root: Path) -> dict[str, Any]:
    if (root / "pom.xml").exists():
        return {
            "language": "java",
            "framework": "maven",
            "commands": [{"name": "maven", "command": "mvn test"}],
            "generators": _optional_generators(["evosuite"]),
        }
    return {
        "language": "java",
        "framework": "gradle",
        "commands": [{"name": "gradle", "command": "gradle test"}],
        "generators": _optional_generators(["evosuite"]),
    }


def _optional_generators(names: list[str]) -> list[dict[str, Any]]:
    return [{"name": name, "available": shutil.which(name) is not None} for name in names]
