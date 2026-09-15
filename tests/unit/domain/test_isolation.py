"""Architectural isolation test verifying zero framework imports in app/domain/."""

import ast
import os
from pathlib import Path

PROHIBITED_MODULES = {
    "fastapi",
    "starlette",
    "sqlalchemy",
    "alembic",
    "httpx",
    "requests",
    "pydantic",
    "pydantic_settings",
    "pydantic_core",
    "openai",
    "anthropic",
    "google",
    "n8n",
}


def get_imports_from_file(filepath: Path) -> set[str]:
    """Parse python source using AST and extract all top-level imported module names."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        tree = ast.parse(f.read(), filename=str(filepath))

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    return imported


def test_domain_layer_isolation():
    """Verify that no file inside app/domain/ imports prohibited infrastructure/framework packages."""
    domain_dir = Path(__file__).resolve().parents[3] / "app" / "domain"
    assert domain_dir.exists(), f"Domain directory {domain_dir} does not exist"

    violations = []
    py_files = list(domain_dir.rglob("*.py"))
    assert len(py_files) > 0, "No python files found in domain layer"

    for py_file in py_files:
        imports = get_imports_from_file(py_file)
        forbidden = imports.intersection(PROHIBITED_MODULES)
        if forbidden:
            violations.append(f"{py_file.name} imports prohibited packages: {forbidden}")

    assert not violations, "Domain architectural boundary violated:\n" + "\n".join(violations)