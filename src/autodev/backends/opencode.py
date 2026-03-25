"""OpenCode CLI backend.

Builds and executes the ``opencode run`` command, mirroring the argument
construction and environment setup from the original shell script
(``run-opencode-full-auto.sh``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.config import AutodevConfig

from autodev.backends.common import BackendResult, CommandSpec, execute_with_tee


def build_opencode_command(
    prompt: str,
    config: AutodevConfig,
    *,
    for_plan: bool = False,
) -> CommandSpec:
    """Build the OpenCode CLI command for execution or planning."""
    oc = config.backend.opencode

    cmd: list[str] = ["opencode", "run", prompt]

    if oc.format and oc.format != "default":
        cmd.extend(["--format", oc.format])

    if oc.model:
        cmd.extend(["--model", oc.model])

    env = os.environ.copy()
    if oc.permissions:
        env["OPENCODE_PERMISSION"] = oc.permissions
    if oc.log_level:
        env["OPENCODE_LOG_LEVEL"] = oc.log_level

    if not for_plan:
        _ensure_opencode_dirs(env)

    return CommandSpec(cmd=cmd, env=env)


def run_opencode(
    prompt: str,
    config: AutodevConfig,
    code_dir: Path,
    attempt_log: Path,
    main_log: Path,
) -> BackendResult:
    """Build and execute the ``opencode run`` command."""
    spec = build_opencode_command(prompt, config)
    return execute_with_tee(
        spec.cmd,
        env=spec.env,
        cwd=code_dir,
        attempt_log=attempt_log,
        main_log=main_log,
    )


def _ensure_opencode_dirs(env: dict[str, str]) -> None:
    """Pre-create OpenCode's writable directories.

    OpenCode stores logs and internal state under
    ``~/.local/share/opencode/{log,storage}``.  When running as root the
    HOME directory may point to a location without pre-existing structure,
    causing ``EACCES`` or ``ENOENT`` errors.  We defensively create these
    directories ahead of time.
    """
    home = env.get("HOME", str(Path.home()))
    for subdir in ["log", "storage"]:
        dirpath = Path(home) / ".local" / "share" / "opencode" / subdir
        try:
            dirpath.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Best-effort: if we cannot create the directory (e.g. read-only
            # filesystem) we let opencode itself surface the error later.
            pass
