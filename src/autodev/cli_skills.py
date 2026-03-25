"""CLI helpers for skill discovery and recommendation."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from autodev.cli_common import find_config, load_runtime_config
from autodev.init_project import parse_init_tools_spec
from autodev.init_templates import TOOL_SPECS
from autodev.skill_catalog import (
    DEFAULT_PROJECT_SKILLS,
    iter_skills_from_root,
    list_bundled_skills,
    recommend_skills,
)


@dataclass(frozen=True)
class DoctorCheck:
    level: str
    label: str
    detail: str


def _project_skills_root() -> Path | None:
    """Return the nearest project-local ``.skills`` directory if one exists."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".skills"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _available_skills() -> tuple[str, list]:
    project_root = _project_skills_root()
    if project_root is not None:
        return str(project_root), iter_skills_from_root(project_root)
    return "bundled skills", list_bundled_skills()


def _same_target(path: Path, expected: Path) -> bool:
    try:
        return path.resolve() == expected.resolve()
    except OSError:
        return False


def _record(checks: list[DoctorCheck], level: str, label: str, detail: str) -> None:
    checks.append(DoctorCheck(level=level, label=label, detail=detail))


def _check_required_skill_dirs(checks: list[DoctorCheck], skills_root: Path) -> None:
    if not skills_root.exists():
        _record(
            checks,
            "error",
            "project skills root",
            f"missing {skills_root}; run `autodev init . --use codex` or your chosen tool again",
        )
        return

    _record(checks, "ok", "project skills root", str(skills_root))
    for skill_name in DEFAULT_PROJECT_SKILLS:
        skill_file = skills_root / skill_name / "SKILL.md"
        if skill_file.exists():
            _record(checks, "ok", f"shared skill {skill_name}", str(skill_file))
        else:
            _record(
                checks,
                "error",
                f"shared skill {skill_name}",
                f"missing {skill_file}; rerun `autodev init . --use codex` or restore the skill directory",
            )


def _check_tool_scaffold(checks: list[DoctorCheck], project_root: Path, tool: str) -> None:
    spec = TOOL_SPECS[tool]
    tool_root = project_root / spec.root
    guide_path = tool_root / spec.guide_name
    rules_path = tool_root / "rules" / "core.md"
    skills_root = project_root / ".skills"
    tool_skills = tool_root / "skills"

    if tool_root.exists():
        _record(checks, "ok", f"{tool} scaffold root", str(tool_root))
    else:
        _record(
            checks,
            "error",
            f"{tool} scaffold root",
            f"missing {tool_root}; run `autodev init . --use {tool}`",
        )
        return

    if guide_path.exists():
        _record(checks, "ok", f"{tool} guide", str(guide_path))
    else:
        _record(checks, "error", f"{tool} guide", f"missing {guide_path}")

    if rules_path.exists():
        _record(checks, "ok", f"{tool} core rules", str(rules_path))
    else:
        _record(checks, "error", f"{tool} core rules", f"missing {rules_path}")

    if tool_skills.is_symlink() and _same_target(tool_skills, skills_root):
        _record(checks, "ok", f"{tool} skills link", f"{tool_skills} -> {skills_root}")
    elif tool_skills.exists():
        _record(
            checks,
            "warn",
            f"{tool} skills link",
            f"{tool_skills} exists but is not a symlink to {skills_root}; fallback copy is usable but less tidy",
        )
    else:
        _record(checks, "error", f"{tool} skills link", f"missing {tool_skills}")

    if tool == "claude":
        for manifest in ("plugin.json", "marketplace.json"):
            path = project_root / ".claude-plugin" / manifest
            if path.exists():
                _record(checks, "ok", f"claude plugin {manifest}", str(path))
            else:
                _record(
                    checks,
                    "error",
                    f"claude plugin {manifest}",
                    f"missing {path}; run `autodev init . --use claude`",
                )

    if tool == "gemini":
        path = project_root / ".gemini" / "extensions" / "autodev-local" / "gemini-extension.json"
        if path.exists():
            _record(checks, "ok", "gemini extension scaffold", str(path))
        else:
            _record(
                checks,
                "error",
                "gemini extension scaffold",
                f"missing {path}; run `autodev init . --use gemini`",
            )


def _check_user_install_state(checks: list[DoctorCheck], project_root: Path, tool: str) -> None:
    if tool == "codex":
        target_root = Path.home() / ".agents" / "skills"
        source_root = project_root / ".codex" / "skills"
    elif tool == "opencode":
        target_root = Path.home() / ".config" / "opencode" / "skills"
        source_root = project_root / ".opencode" / "skills"
    elif tool == "claude":
        _record(
            checks,
            "warn",
            "claude install state",
            "project plugin scaffold is present, but Claude local-scope registration is not inspected automatically; run `autodev install-skills` if needed",
        )
        return
    elif tool == "gemini":
        _record(
            checks,
            "warn",
            "gemini install state",
            "project extension scaffold is present, but Gemini link state is not inspected automatically; run `autodev install-skills` if needed",
        )
        return
    else:
        return

    linked = 0
    for skill_name in DEFAULT_PROJECT_SKILLS:
        target = target_root / skill_name
        expected = source_root / skill_name
        if target.is_symlink() and _same_target(target, expected):
            linked += 1
            _record(checks, "ok", f"{tool} installed skill {skill_name}", f"{target} -> {expected}")
        elif target.exists():
            _record(
                checks,
                "warn",
                f"{tool} installed skill {skill_name}",
                f"{target} exists but does not point to {expected}",
            )
        else:
            _record(
                checks,
                "warn",
                f"{tool} installed skill {skill_name}",
                f"missing {target}; run `autodev install-skills` to register project skills for {tool}",
            )

    if linked == len(DEFAULT_PROJECT_SKILLS):
        _record(checks, "ok", f"{tool} install summary", f"all {linked} default skills are linked")
    else:
        _record(
            checks,
            "warn",
            f"{tool} install summary",
            f"{linked}/{len(DEFAULT_PROJECT_SKILLS)} default skills are linked into {target_root}",
        )


def cmd_skills_list(args: argparse.Namespace) -> int:
    """Handle ``autodev skills list``."""
    source_label, skills = _available_skills()
    if not skills:
        print(f"No skills found in {source_label}.", file=sys.stderr)
        return 1

    print(f"Skills from {source_label}:")
    for skill in skills:
        category_label = f" [{skill.category}]" if skill.category else ""
        print(f"- {skill.directory_name}{category_label}: {skill.description or '(no description)'}")
    return 0


def cmd_skills_recommend(args: argparse.Namespace) -> int:
    """Handle ``autodev skills recommend``."""
    query = str(args.query or "").strip()
    if not query:
        print("Error: provide a query for skill recommendation.", file=sys.stderr)
        return 1

    source_label, skills = _available_skills()
    matches = recommend_skills(skills, query, limit=args.limit)
    if not matches:
        print(f"No skill recommendations found in {source_label} for: {query}")
        return 0

    print(f"Recommended skills from {source_label} for: {query}")
    for skill in matches:
        print(f"- {skill.directory_name}: {skill.description or '(no description)'}")
    return 0


def cmd_skills_doctor(args: argparse.Namespace) -> int:
    """Diagnose the current project's skill wiring."""
    config_path = find_config(args).resolve()
    config = load_runtime_config(args)
    project_root = config_path.parent
    tool = parse_init_tools_spec(config.backend.default)

    checks: list[DoctorCheck] = []
    _record(checks, "ok", "config", str(config_path))
    _record(checks, "ok", "backend.default", tool)
    _check_required_skill_dirs(checks, project_root / ".skills")
    _check_tool_scaffold(checks, project_root, tool)
    _check_user_install_state(checks, project_root, tool)

    errors = sum(1 for check in checks if check.level == "error")
    warnings = sum(1 for check in checks if check.level == "warn")

    print(f"Skill doctor for {project_root} (backend.default={tool})")
    for check in checks:
        print(f"[{check.level}] {check.label}: {check.detail}")

    print(
        f"Summary: {len(checks) - errors - warnings} ok, {warnings} warning(s), {errors} error(s)"
    )
    return 1 if errors else 0
