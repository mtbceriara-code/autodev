"""Codex CLI backend.

Builds and executes the ``codex exec`` command in non-interactive mode.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.config import AutodevConfig

from autodev.backends.common import BackendResult, CommandSpec, execute_with_tee


def build_codex_command(
    prompt: str,
    config: AutodevConfig,
    *,
    for_plan: bool = False,
) -> CommandSpec:
    """Build the Codex CLI command for execution or planning."""
    del for_plan
    codex = config.backend.codex

    cmd: list[str] = ["codex", "exec"]

    if codex.model:
        cmd.extend(["--model", codex.model])

    # Prefer Codex's official all-in-one YOLO flag. Keep the older split
    # flags as a compatibility fallback when users explicitly disable yolo.
    if codex.yolo:
        cmd.append("--yolo")
    else:
        if codex.full_auto:
            cmd.append("--full-auto")
        if codex.dangerously_bypass_approvals_and_sandbox:
            cmd.append("--dangerously-bypass-approvals-and-sandbox")

    if codex.ephemeral:
        cmd.append("--ephemeral")

    cmd.append(prompt)
    return CommandSpec(cmd=cmd)


def run_codex(
    prompt: str,
    config: AutodevConfig,
    code_dir: Path,
    attempt_log: Path,
    main_log: Path,
) -> BackendResult:
    """Build and execute the ``codex exec`` command."""
    spec = build_codex_command(prompt, config)
    return execute_with_tee(
        spec.cmd,
        env=spec.env,
        cwd=code_dir,
        attempt_log=attempt_log,
        main_log=main_log,
    )
