"""Compatibility re-exports for CLI handlers."""

from autodev.cli_ops import cmd_plan, cmd_status, cmd_verify
from autodev.cli_project import cmd_init, cmd_run

__all__ = [
    "cmd_init",
    "cmd_plan",
    "cmd_run",
    "cmd_status",
    "cmd_verify",
]
