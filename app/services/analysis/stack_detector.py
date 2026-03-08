from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StackInfo:
    project_type: str = "unknown"
    primary_language: str | None = None
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    has_docker: bool = False
    has_ci: bool = False
    ci_provider: str | None = None
    has_kubernetes: bool = False
    has_terraform: bool = False
    has_helm: bool = False
    infra_tools: list[str] = field(default_factory=list)
    linters: list[str] = field(default_factory=list)
    formatters: list[str] = field(default_factory=list)


def _file_exists(root: Path, *paths: str) -> bool:
    return any((root / p).exists() for p in paths)


def _read_json(root: Path, filename: str) -> dict:
    try:
        import json
        return json.loads((root / filename).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_text(root: Path, filename: str) -> str:
    try:
        return (root / filename).read_text(encoding="utf-8")
    except Exception:
        return ""


def detect_stack(repo_root: Path, languages: dict[str, object]) -> StackInfo:
    info = StackInfo()

    # Primary language from language distribution
    if languages:
        primary = max(languages.values(), key=lambda s: s.loc, default=None)  # type: ignore[attr-defined]
        if primary:
            info.primary_language = primary.name

    _detect_project_type(repo_root, languages, info)
    _detect_package_managers(repo_root, info)
    _detect_frameworks(repo_root, info)
    _detect_docker(repo_root, info)
    _detect_ci(repo_root, info)
    _detect_infra(repo_root, info)
    _detect_linters(repo_root, info)

    return info


def _detect_project_type(repo_root: Path, languages: dict, info: StackInfo) -> None:
    has_frontend = any(
        n in languages for n in ("JavaScript", "TypeScript", "Vue", "Svelte", "HTML")
    )
    has_backend = any(
        n in languages for n in ("Python", "Java", "Go", "Kotlin", "Scala", "Ruby", "PHP", "C#", "Rust")
    )
    has_infra = any(n in languages for n in ("Terraform", "HCL", "YAML"))
    is_mono = _looks_like_monorepo(repo_root)
    has_bin = _file_exists(repo_root, "setup.py", "setup.cfg", "pyproject.toml") and \
        "[tool.poetry.scripts]" in _read_text(repo_root, "pyproject.toml")
    has_cli = _file_exists(repo_root, "cli.py", "main.py", "cmd/main.go") or \
        _file_exists(repo_root, "src/cli.py", "src/main.py")

    if is_mono:
        info.project_type = "monorepo"
    elif has_infra and not has_backend and not has_frontend:
        info.project_type = "infra_config"
    elif has_frontend and not has_backend:
        info.project_type = "frontend_application"
    elif has_backend and not has_frontend:
        if has_cli:
            info.project_type = "cli_tool"
        elif _file_exists(repo_root, "setup.py", "setup.cfg") or \
                _is_library(repo_root):
            info.project_type = "library"
        else:
            info.project_type = "backend_service"
    elif has_backend and has_frontend:
        info.project_type = "monolith"
    else:
        info.project_type = "unknown"


def _looks_like_monorepo(root: Path) -> bool:
    indicators = ["packages", "apps", "services", "libs"]
    found = sum(1 for d in indicators if (root / d).is_dir())
    return found >= 2


def _is_library(root: Path) -> bool:
    pkg = _read_json(root, "package.json")
    if pkg.get("main") or pkg.get("exports"):
        return True
    pyproject = _read_text(root, "pyproject.toml")
    if "[tool.poetry]" in pyproject and "packages" in pyproject:
        return True
    return _file_exists(root, "setup.py", "setup.cfg", "*.gemspec")


def _detect_package_managers(root: Path, info: StackInfo) -> None:
    checks = [
        ("package-lock.json", "npm"),
        ("yarn.lock", "yarn"),
        ("pnpm-lock.yaml", "pnpm"),
        ("requirements.txt", "pip"),
        ("Pipfile", "pipenv"),
        ("pyproject.toml", "pip/poetry"),
        ("poetry.lock", "poetry"),
        ("go.mod", "go modules"),
        ("Cargo.toml", "cargo"),
        ("pom.xml", "maven"),
        ("build.gradle", "gradle"),
        ("build.gradle.kts", "gradle"),
        ("Gemfile", "bundler"),
        ("composer.json", "composer"),
    ]
    for filename, pm in checks:
        if _file_exists(root, filename):
            info.package_managers.append(pm)


def _detect_frameworks(root: Path, info: StackInfo) -> None:
    pkg = _read_json(root, "package.json")
    all_deps: dict = {}
    all_deps.update(pkg.get("dependencies", {}))
    all_deps.update(pkg.get("devDependencies", {}))

    js_frameworks = {
        "react": "React",
        "next": "Next.js",
        "vue": "Vue",
        "nuxt": "Nuxt.js",
        "angular": "Angular",
        "@angular/core": "Angular",
        "svelte": "Svelte",
        "express": "Express",
        "fastify": "Fastify",
        "nestjs": "NestJS",
        "@nestjs/core": "NestJS",
        "koa": "Koa",
    }
    for dep, name in js_frameworks.items():
        if dep in all_deps and name not in info.frameworks:
            info.frameworks.append(name)

    # Python frameworks
    requirements = _read_text(root, "requirements.txt")
    pyproject = _read_text(root, "pyproject.toml")
    combined = requirements + pyproject

    py_frameworks = {
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "tornado": "Tornado",
        "aiohttp": "aiohttp",
        "starlette": "Starlette",
        "sqlalchemy": "SQLAlchemy",
        "celery": "Celery",
    }
    for key, name in py_frameworks.items():
        if key in combined.lower() and name not in info.frameworks:
            info.frameworks.append(name)

    # Go frameworks
    go_mod = _read_text(root, "go.mod")
    go_frameworks = {
        "gin-gonic/gin": "Gin",
        "labstack/echo": "Echo",
        "gofiber/fiber": "Fiber",
        "gorilla/mux": "Gorilla Mux",
    }
    for key, name in go_frameworks.items():
        if key in go_mod and name not in info.frameworks:
            info.frameworks.append(name)

    # Java/Kotlin frameworks
    pom = _read_text(root, "pom.xml")
    gradle = _read_text(root, "build.gradle") + _read_text(root, "build.gradle.kts")
    jvm_combined = pom + gradle
    jvm_frameworks = {
        "spring-boot": "Spring Boot",
        "spring-web": "Spring MVC",
        "micronaut": "Micronaut",
        "quarkus": "Quarkus",
        "ktor": "Ktor",
    }
    for key, name in jvm_frameworks.items():
        if key in jvm_combined.lower() and name not in info.frameworks:
            info.frameworks.append(name)


def _detect_docker(root: Path, info: StackInfo) -> None:
    info.has_docker = _file_exists(
        root, "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "Dockerfile.dev", "Dockerfile.prod"
    )


def _detect_ci(root: Path, info: StackInfo) -> None:
    if _file_exists(root, "bitbucket-pipelines.yml"):
        info.has_ci = True
        info.ci_provider = "bitbucket"
    elif _file_exists(root, ".gitlab-ci.yml"):
        info.has_ci = True
        info.ci_provider = "gitlab"
    elif _file_exists(root, ".github/workflows"):
        info.has_ci = True
        info.ci_provider = "github_actions"
    elif _file_exists(root, "Jenkinsfile"):
        info.has_ci = True
        info.ci_provider = "jenkins"


def _detect_linters(root: Path, info: StackInfo) -> None:
    pyproject = _read_text(root, "pyproject.toml")
    setup_cfg = _read_text(root, "setup.cfg")

    linter_checks = [
        (["eslint.config.js", "eslint.config.mjs", ".eslintrc", ".eslintrc.js",
          ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml"], "ESLint"),
        ([".flake8"], "Flake8"),
        ([".pylintrc"], "Pylint"),
        (["mypy.ini"], "MyPy"),
        ([".rubocop.yml", ".rubocop.yaml"], "RuboCop"),
        (["golangci.yml", ".golangci.yml", "golangci.yaml", ".golangci.yaml"], "golangci-lint"),
    ]
    for paths, name in linter_checks:
        if _file_exists(root, *paths):
            info.linters.append(name)

    if "[tool.ruff]" in pyproject or "ruff" in pyproject:
        info.linters.append("Ruff")
    if "[flake8]" in setup_cfg:
        if "Flake8" not in info.linters:
            info.linters.append("Flake8")
    if "[mypy]" in pyproject:
        if "MyPy" not in info.linters:
            info.linters.append("MyPy")

    formatter_checks = [
        ([".prettierrc", ".prettierrc.js", ".prettierrc.json",
          ".prettierrc.yml", ".prettierrc.yaml", "prettier.config.js"], "Prettier"),
        (["gofmt"], "gofmt"),
    ]
    for paths, name in formatter_checks:
        if _file_exists(root, *paths):
            info.formatters.append(name)

    if "[tool.black]" in pyproject:
        info.formatters.append("Black")
    if "[tool.isort]" in pyproject:
        info.formatters.append("isort")


def _detect_infra(root: Path, info: StackInfo) -> None:
    if _file_exists(root, "terraform") or list(root.rglob("*.tf")):
        info.has_terraform = True
        info.infra_tools.append("terraform")
    if _file_exists(root, "k8s", "kubernetes") or list(root.rglob("*.yaml")):
        # Check for k8s manifest signatures
        for f in root.rglob("*.yaml"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                if "apiVersion:" in content and "kind:" in content:
                    info.has_kubernetes = True
                    if "kubernetes" not in info.infra_tools:
                        info.infra_tools.append("kubernetes")
                    break
            except Exception:
                pass
    if _file_exists(root, "helm", "charts") or list(root.rglob("Chart.yaml")):
        info.has_helm = True
        info.infra_tools.append("helm")
