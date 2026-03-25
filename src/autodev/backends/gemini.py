"""Gemini CLI backend.

Builds and executes the ``gemini -p`` command in headless mode.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.config import AutodevConfig

from autodev.backends.common import BackendResult, CommandSpec, execute_with_tee


def build_gemini_command(
    prompt: str,
    config: AutodevConfig,
    *,
    for_plan: bool = False,
) -> CommandSpec:
    """Build the Gemini CLI command for execution or planning."""
    gemini = config.backend.gemini

    cmd: list[str] = ["gemini", "-p", prompt]

    if gemini.model:
        cmd.extend(["--model", gemini.model])

    if for_plan:
        return CommandSpec(cmd=cmd)

    if gemini.yolo:
        cmd.append("--yolo")
    elif gemini.approval_mode:
        cmd.extend(["--approval-mode", gemini.approval_mode])

    if gemini.output_format != "text":
        cmd.extend(["--output-format", gemini.output_format])

    if gemini.all_files:
        cmd.append("--all-files")

    if gemini.include_directories:
        cmd.extend(["--include-directories", gemini.include_directories])

    if gemini.debug:
        cmd.append("--debug")

    return CommandSpec(cmd=cmd)


def run_gemini(
    prompt: str,
    config: AutodevConfig,
    code_dir: Path,
    attempt_log: Path,
    main_log: Path,
) -> BackendResult:
    """Build and execute the ``gemini -p`` command."""
    spec = build_gemini_command(prompt, config)
    return execute_with_tee(
        spec.cmd,
        env=spec.env,
        cwd=code_dir,
        attempt_log=attempt_log,
        main_log=main_log,
    )
