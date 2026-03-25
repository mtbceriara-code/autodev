from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from autodev.backends import get_backend_cli_name

if TYPE_CHECKING:
    from autodev.config import AutodevConfig


def is_root() -> bool:
    """Check if running as root/sudo.

    On Windows this always returns ``False`` because the euid concept does
    not apply.
    """
    if sys.platform == "win32":
        return False
    return os.geteuid() == 0


def check_command_exists(name: str) -> bool:
    """Check if a command is available on PATH."""
    return shutil.which(name) is not None


def check_prerequisites(backend: str) -> list[str]:
    """Check that required commands exist.  Returns a list of error messages."""
    errors: list[str] = []
    if not check_command_exists("python3"):
        errors.append("python3 not found on PATH")
    cli_name = get_backend_cli_name(backend)
    if not check_command_exists(cli_name):
        errors.append(f"{cli_name} CLI not found on PATH")
    return errors


def adjust_config_for_root(config: AutodevConfig) -> None:
    """Mutate *config* for root/sudo mode.

    Matches the shell script root-detection logic: when running as root we
    may need to disable ``--skip-permissions`` and fall back to a safer
    permission mode.
    """
    if not is_root():
        return
    if config.run.root_mode.disable_skip_permissions:
        config.backend.claude.skip_permissions = False
    if config.backend.claude.permission_mode in ("default", "bypassPermissions"):
        config.backend.claude.permission_mode = (
            config.run.root_mode.fallback_permission_mode
        )


def has_env_error(attempt_log: Path, halt_patterns: list[str]) -> bool:
    """Check if an attempt log contains environment/permission errors.

    The comparison is case-insensitive so callers don't need to worry about
    normalisation.
    """
    try:
        content = attempt_log.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False
    return any(pattern.lower() in content for pattern in halt_patterns)
