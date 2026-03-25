"""Scaffold a new autodev project with default files.

``autodev init`` creates the minimal set of files needed to start
using autodev in a project directory, plus lightweight native
agent-convention files for Claude Code, Codex, Gemini CLI, and OpenCode.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from autodev.init_templates import (
    CORE_RULES,
    TOOL_GUIDE_TEMPLATE,
    TOOL_SPECS,
    build_base_templates,
    build_tool_support_templates,
)
from autodev.skill_catalog import DEFAULT_PROJECT_SKILLS, bundled_skills_root

def normalize_init_tool(tool: str) -> str:
    """Validate and normalize one explicitly requested wrapper tool."""
    normalized = tool.strip().lower()
    if not normalized:
        return "codex"
    if "," in normalized:
        raise ValueError(
            "Unsupported init tool list. Pass exactly one tool: "
            + ", ".join(sorted(TOOL_SPECS))
        )
    if normalized in {"all", "detected"}:
        raise ValueError(
            "Unsupported init tool selector. Pass exactly one tool: "
            + ", ".join(sorted(TOOL_SPECS))
        )
    if normalized not in TOOL_SPECS:
        valid = ", ".join(sorted(TOOL_SPECS))
        raise ValueError(f"Unsupported init tool: {normalized}. Expected one of: {valid}")
    return normalized


def parse_init_tools_spec(spec: str) -> str:
    """Parse the CLI ``--use`` value.

    `autodev init` now scaffolds exactly one tool wrapper per invocation.
    When omitted, it defaults to `codex`.
    """
    return normalize_init_tool(spec)


def infer_init_default_backend(tool: str) -> str:
    """Choose the backend written to ``autodev.toml`` during init."""
    return normalize_init_tool(tool)


def _build_tool_wrappers(project_name: str, tool: str) -> dict[str, str]:
    """Return thin tool-specific wrappers for the selected CLI."""
    files: dict[str, str] = {}

    spec = TOOL_SPECS[tool]
    tool_root = spec.root
    tool_guide_path = f"{tool_root}/{spec.guide_name}"
    tool_rules_path = f"{tool_root}/rules/core.md"

    files[tool_guide_path] = TOOL_GUIDE_TEMPLATE.format(
        project_name=project_name,
        tool_label=spec.label,
        tool_rules_path=tool_rules_path,
    )
    files[tool_rules_path] = CORE_RULES

    for relative_path, template in spec.command_files.items():
        files[f"{tool_root}/{relative_path}"] = template

    return files


def _link_tool_skills(directory: Path, tool: str, created: list[str]) -> None:
    """Expose the canonical ``.skills`` directory inside the tool root."""
    skills_root = directory / ".skills"
    tool_skills = directory / TOOL_SPECS[tool].root / "skills"

    if tool_skills.exists():
        return

    tool_skills.parent.mkdir(parents=True, exist_ok=True)
    try:
        tool_skills.symlink_to(Path("..") / ".skills", target_is_directory=True)
        created.append(f"{TOOL_SPECS[tool].root}/skills")
        return
    except OSError:
        pass

    shutil.copytree(skills_root, tool_skills)
    created.append(f"{TOOL_SPECS[tool].root}/skills")


def _copy_tree(source, destination: Path) -> None:
    """Recursively copy a traversable package directory to the filesystem."""
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            _copy_tree(child, destination / child.name)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())


def _copy_default_project_skills(directory: Path, created: list[str]) -> None:
    """Copy curated bundled skills into the project-local ``.skills`` root."""
    skills_root = bundled_skills_root()
    project_skills_root = directory / ".skills"

    for skill_name in DEFAULT_PROJECT_SKILLS:
        source = skills_root.joinpath(skill_name)
        target = project_skills_root / skill_name
        if target.exists():
            continue
        _copy_tree(source, target)
        created.append(f".skills/{skill_name}/")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_project(
    directory: Path,
    project_name: str = "",
    *,
    available_tool: str = "codex",
    default_backend: str | None = None,
) -> list[str]:
    """Create default autodev files in *directory*.

    Returns a list of created file paths (relative to *directory*).
    Existing files are **never** overwritten.

    Parameters
    ----------
    directory:
        The target project directory.
    project_name:
        Human-readable project name.  Defaults to the directory name.
    available_tool:
        Which single tool-specific wrapper set to scaffold.
        Defaults to ``codex``.
    default_backend:
        Optional override for the backend written to ``autodev.toml``.
        Defaults to the selected tool.
    """
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)

    if not project_name:
        project_name = directory.name

    created: list[str] = []
    tool = normalize_init_tool(available_tool)
    if default_backend is None:
        default_backend = tool

    templates: dict[str, str] = {
        **build_base_templates(default_backend=default_backend),
    }
    templates.update(build_tool_support_templates(tool))
    templates.update(_build_tool_wrappers(project_name, tool))

    files: dict[str, str] = {
        name: tpl.replace("{project_name}", project_name)
        for name, tpl in templates.items()
    }

    for name, content in files.items():
        path = directory / name
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(name)

    _copy_default_project_skills(directory, created)
    _link_tool_skills(directory, tool, created)

    log_dir = directory / "logs" / "attempts"
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
        created.append("logs/")

    return created
