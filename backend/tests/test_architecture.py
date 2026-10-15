"""以实际依赖约束保护模块职责，不依赖额外架构测试框架。"""

import ast
from pathlib import Path


def test_architecture_boundaries():
    source = Path(__file__).resolve().parents[1] / "src" / "apps"
    violations = []
    for path in source.rglob("*.py"):
        owner = path.relative_to(source).parts[0]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            imports = []
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    package = ["apps", *path.relative_to(source).parts[:-1]]
                    base = package[: len(package) - node.level + 1]
                    module = ".".join(base + (node.module.split(".") if node.module else []))
                else:
                    module = node.module or ""
                imports.append(module)
                imports.extend(f"{module}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            for target in imports:
                forbidden = (
                    owner == "domain"
                    and (
                        target.startswith(
                            (
                                "fastapi",
                                "starlette",
                                "sqlite3",
                                "langchain",
                                "apps.db",
                                "apps.services",
                                "apps.runtime",
                                "apps.bootstrap",
                            )
                        )
                    )
                    or owner == "agents"
                    and target.startswith("apps.services")
                    or owner in {"db", "llm", "core"}
                    and target.startswith("apps.services")
                    or owner not in {"main.py", "bootstrap"}
                    and target.startswith("apps.bootstrap")
                    or owner == "api"
                    and target.startswith("apps.db")
                    or owner == "services"
                    and target.startswith(("fastapi", "starlette", "apps.api"))
                )
                if forbidden:
                    violations.append(f"{path.relative_to(source)}:{node.lineno} imports {target}")
    assert not violations, "\n".join(violations)


def test_no_legacy_service_or_lifecycle_modules_remain():
    source = Path(__file__).resolve().parents[1] / "src" / "apps"
    assert not (source / "core" / "lifecycle.py").exists()
    assert not list((source / "services").glob("*_service.py"))
    assert (source / "bootstrap" / "lifecycle.py").is_file()
    assert (source / "api" / "compat").is_dir()
