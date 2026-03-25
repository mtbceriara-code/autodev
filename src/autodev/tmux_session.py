"""Tmux session helpers for detached autodev execution.

Manages launching autodev processes in background tmux sessions,
querying their status, and cleaning them up.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


_SAFE_RE = re.compile(r"[^a-zA-Z0-9_-]")


def _sanitize_session_name(name: str) -> str:
    """Make *name* safe for use as a tmux session name."""
    return _SAFE_RE.sub("-", name)[:60]


def check_tmux_available() -> str | None:
    """Return an error message if tmux is not available, else None."""
    if shutil.which("tmux") is None:
        return "tmux is required for --detach mode but was not found in PATH"
    return None


def launch_detached(
    session_name: str,
    cmd: list[str],
    cwd: Path,
    log_file: Path | None = None,
) -> str:
    """Launch *cmd* in a new detached tmux session.

    Returns the sanitized session name actually used.
    """
    session_name = _sanitize_session_name(session_name)

    # Kill stale session with the same name if present.
    subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True,
    )

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)

    # Build shell command that runs the process and optionally tees to log.
    shell_cmd = _build_shell_command(cmd, log_file)

    result = subprocess.run(
        [
            "tmux", "new-session",
            "-d",                          # detached
            "-s", session_name,
            "-x", "220", "-y", "50",       # reasonable default size
            "bash", "-c", shell_cmd,
        ],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"tmux new-session failed (exit={result.returncode}): {result.stderr.strip()}"
        )

    # Increase scrollback for the session.
    subprocess.run(
        ["tmux", "set-option", "-t", session_name, "history-limit", "50000"],
        capture_output=True,
    )

    return session_name


def is_session_alive(session_name: str) -> bool:
    """Return True if the tmux session exists and is alive."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True,
    )
    return result.returncode == 0


def list_autodev_sessions(prefix: str = "autodev") -> list[dict]:
    """List all tmux sessions whose name starts with *prefix*.

    Returns a list of dicts: ``[{"name": str, "created": str, "windows": int, "pane_path": str}]``.
    """
    result = subprocess.run(
        [
            "tmux", "list-sessions",
            "-F", "#{session_name}\t#{session_created_string}\t#{session_windows}\t#{pane_current_path}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    sessions: list[dict] = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name = parts[0]
        if not name.startswith(prefix):
            continue
        sessions.append({
            "name": name,
            "created": parts[1],
            "windows": int(parts[2]) if parts[2].isdigit() else 1,
            "pane_path": parts[3] if len(parts) > 3 else "",
        })
    return sessions


def kill_session(session_name: str) -> bool:
    """Kill a tmux session by name. Returns True if it was killed."""
    result = subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True,
    )
    return result.returncode == 0


def kill_all_sessions(prefix: str = "autodev") -> int:
    """Kill all tmux sessions matching *prefix*. Returns count killed."""
    sessions = list_autodev_sessions(prefix)
    killed = 0
    for s in sessions:
        if kill_session(s["name"]):
            killed += 1
    return killed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shell_quote(s: str) -> str:
    """Quote a string for safe use in a shell command."""
    if not s:
        return "''"
    safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-=/.,:@+")
    if all(c in safe for c in s):
        return s
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _build_shell_command(
    cmd: list[str],
    log_file: Path | None,
) -> str:
    """Build a shell one-liner that runs *cmd* with optional tee to *log_file*."""
    cmd_str = " ".join(_shell_quote(c) for c in cmd)
    if log_file is not None:
        return f"{cmd_str} 2>&1 | tee {_shell_quote(str(log_file))}"
    return cmd_str
