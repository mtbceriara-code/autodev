"""Claude Code CLI backend.

Builds and executes the ``claude -p`` command, mirroring the argument
construction logic from the original shell script (lines 689-711 of
``run-full-auto.sh``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.config import AutodevConfig

from autodev.backends.common import BackendResult, CommandSpec, execute_with_tee


def build_claude_command(
    prompt: str,
    config: AutodevConfig,
    *,
    for_plan: bool = False,
) -> CommandSpec:
    """Build the Claude CLI command for execution or one-shot planning."""
    cc = config.backend.claude

    cmd: list[str] = ["claude", "-p", prompt]

    if for_plan:
        cmd.extend(["--output-format", "text"])
        if cc.model:
            cmd.extend(["--model", cc.model])
        return CommandSpec(cmd=cmd)

    # -- skip permissions ----------------------------------------------------
    if cc.skip_permissions:
        cmd.append("--dangerously-skip-permissions")

    # -- permission mode -----------------------------------------------------
    cmd.extend(["--permission-mode", cc.permission_mode])

    # -- output format ------------------------------------------------------
    if cc.output_format != "text":
        cmd.extend(["--output-format", cc.output_format])

    # -- verbose ------------------------------------------------------------
    # The Claude CLI requires --verbose when using stream-json in -p mode.
    # The original shell script unconditionally sets CLAUDE_VERBOSE=1 when
    # CLAUDE_OUTPUT_FORMAT is stream-json (lines 164-167), so by the time the
    # command is assembled --verbose is always present for stream-json.  We
    # replicate that coupling explicitly here so the backend is self-contained
    # and does not rely solely on upstream auto-adjustment.
    if cc.output_format == "stream-json":
        cmd.append("--verbose")
    elif cc.verbose:
        cmd.append("--verbose")

    # -- model override -----------------------------------------------------
    if cc.model:
        cmd.extend(["--model", cc.model])

    return CommandSpec(cmd=cmd)


def run_claude(
    prompt: str,
    config: AutodevConfig,
    code_dir: Path,
    attempt_log: Path,
    main_log: Path,
) -> BackendResult:
    """Build and execute the ``claude -p`` command."""
    spec = build_claude_command(prompt, config)
    return execute_with_tee(
        spec.cmd,
        env=spec.env,
        cwd=code_dir,
        attempt_log=attempt_log,
        main_log=main_log,
    )
