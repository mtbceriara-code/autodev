"""CLI handlers for host-tool skill installation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from autodev.cli_common import find_config, load_runtime_config
from autodev.init_project import parse_init_tools_spec


def _project_root_from_args(args: argparse.Namespace) -> Path:
    """Resolve the current autodev project root from CLI args."""
    return find_config(args).resolve().parent


def _selected_tool_from_args(args: argparse.Namespace) -> str:
    """Resolve the configured host tool from ``autodev.toml``."""
    config = load_runtime_config(args)
    return parse_init_tools_spec(config.backend.default)


def _require_path(path: Path, *, label: str, hint: str) -> Path:
    """Return *path* or raise a clear error when it is missing."""
    if path.exists():
        return path
    raise RuntimeError(f"{label} not found: {path}\nRun `{hint}` first.")


def _discover_skill_dirs(skills_root: Path) -> list[Path]:
    """Return direct child skill directories under *skills_root*."""
    _require_path(
        skills_root,
        label="Tool skill directory",
        hint=f"autodev init . --use {skills_root.parent.name.lstrip('.')}",
    )
    skill_dirs = sorted(
        path
        for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    )
    if not skill_dirs:
        raise RuntimeError(f"No skills found in {skills_root}")
    return skill_dirs


def _same_symlink_target(target: Path, source: Path) -> bool:
    """Return ``True`` when *target* already points to *source*."""
    if not target.is_symlink():
        return False
    try:
        return target.resolve() == source.resolve()
    except OSError:
        return False


def _ensure_skill_link(source: Path, target: Path) -> str:
    """Create a symlink from *target* to *source* unless already present."""
    if target.exists() or target.is_symlink():
        if _same_symlink_target(target, source):
            return "existing"
        raise RuntimeError(
            f"Skill target already exists and points elsewhere: {target}\n"
            f"Expected source: {source}"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source, target_is_directory=True)
    return "linked"


def _install_linked_skill_dirs(source_root: Path, target_root: Path) -> list[tuple[str, str, Path]]:
    """Link every skill directory under *source_root* into *target_root*."""
    results: list[tuple[str, str, Path]] = []
    for skill_dir in _discover_skill_dirs(source_root):
        target = target_root / skill_dir.name
        status = _ensure_skill_link(skill_dir, target)
        results.append((skill_dir.name, status, target))
    return results


def _run_command(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a host-tool CLI command with consistent error handling."""
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required command not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if detail:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{detail}") from exc
        raise RuntimeError(f"Command failed: {' '.join(cmd)}") from exc


def _read_manifest_name(path: Path) -> str:
    """Read the ``name`` field from a small JSON manifest."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Failed to read manifest: {path}\n{exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON manifest: {path}\n{exc}") from exc

    name = str(data.get("name", "")).strip()
    if not name:
        raise RuntimeError(f"Manifest missing name: {path}")
    return name


def _install_codex_skills(project_root: Path) -> list[tuple[str, str, Path]]:
    """Install project-local Codex skills into Codex's user discovery path."""
    source_root = project_root / ".codex" / "skills"
    target_root = Path.home() / ".agents" / "skills"
    return _install_linked_skill_dirs(source_root, target_root)


def _install_opencode_skills(project_root: Path) -> list[tuple[str, str, Path]]:
    """Install project-local OpenCode skills into OpenCode's user discovery path."""
    source_root = project_root / ".opencode" / "skills"
    target_root = Path.home() / ".config" / "opencode" / "skills"
    return _install_linked_skill_dirs(source_root, target_root)


def _install_claude_skills(project_root: Path) -> list[str]:
    """Register the local Claude plugin wrapper for the current project."""
    plugin_root = _require_path(
        project_root / ".claude-plugin",
        label="Claude plugin scaffold",
        hint="autodev init . --use claude",
    )
    plugin_manifest = _require_path(
        plugin_root / "plugin.json",
        label="Claude plugin manifest",
        hint="autodev init . --use claude",
    )
    marketplace_manifest = _require_path(
        plugin_root / "marketplace.json",
        label="Claude marketplace manifest",
        hint="autodev init . --use claude",
    )

    plugin_name = _read_manifest_name(plugin_manifest)
    marketplace_name = _read_manifest_name(marketplace_manifest)

    _run_command(["claude", "plugin", "validate", str(plugin_manifest)], cwd=project_root)
    _run_command(["claude", "plugin", "validate", str(marketplace_manifest)], cwd=project_root)
    _run_command(
        ["claude", "plugin", "marketplace", "add", str(plugin_root), "--scope", "local"],
        cwd=project_root,
    )
    _run_command(
        [
            "claude",
            "plugin",
            "install",
            f"{plugin_name}@{marketplace_name}",
            "--scope",
            "local",
        ],
        cwd=project_root,
    )
    return [
        f"validated {plugin_manifest}",
        f"validated {marketplace_manifest}",
        f"registered marketplace {marketplace_name} from {plugin_root}",
        f"installed plugin {plugin_name} in local Claude scope",
    ]


def _install_gemini_skills(project_root: Path) -> list[str]:
    """Register the local Gemini extension scaffold for the current project."""
    extension_root = _require_path(
        project_root / ".gemini" / "extensions" / "autodev-local",
        label="Gemini extension scaffold",
        hint="autodev init . --use gemini",
    )

    _run_command(["gemini", "extensions", "validate", str(extension_root)], cwd=project_root)
    _run_command(
        ["gemini", "extensions", "link", str(extension_root), "--consent"],
        cwd=project_root,
    )
    return [
        f"validated {extension_root}",
        f"linked Gemini extension from {extension_root}",
    ]


def cmd_install_skills(args: argparse.Namespace) -> int:
    """Handle ``autodev install-skills``."""
    try:
        tool = _selected_tool_from_args(args)
        project_root = _project_root_from_args(args)

        if tool == "codex":
            results = _install_codex_skills(project_root)
            print(
                f"Installed Codex skill links from {project_root / '.codex' / 'skills'} "
                f"(backend.default={tool}):"
            )
            for skill_name, status, target in results:
                print(f"  [{status}] {skill_name} -> {target}")
            return 0

        if tool == "opencode":
            results = _install_opencode_skills(project_root)
            print(
                f"Installed OpenCode skill links from {project_root / '.opencode' / 'skills'} "
                f"(backend.default={tool}):"
            )
            for skill_name, status, target in results:
                print(f"  [{status}] {skill_name} -> {target}")
            return 0

        if tool == "claude":
            results = _install_claude_skills(project_root)
            print(f"Installed Claude local plugin wiring (backend.default={tool}):")
            for line in results:
                print(f"  {line}")
            return 0

        if tool == "gemini":
            results = _install_gemini_skills(project_root)
            print(f"Installed Gemini extension wiring (backend.default={tool}):")
            for line in results:
                print(f"  {line}")
            return 0

        raise RuntimeError(f"Unsupported tool: {tool}")
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
