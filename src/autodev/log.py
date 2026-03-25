from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.config import AutodevConfig

# ANSI color codes
DIM = "\033[2m"
BOLD = "\033[1m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
MAGENTA = "\033[0;35m"
GRAY = "\033[0;90m"
NC = "\033[0m"  # No Color

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
_STATUS_COLORS = {
    "pending": BLUE,
    "running": CYAN,
    "validating": MAGENTA,
    "retry": YELLOW,
    "waiting": GRAY,
    "completed": GREEN,
    "blocked": RED,
    "failed": RED,
    "info": BLUE,
}


def supports_color(stream=None) -> bool:
    target = stream or sys.stderr
    try:
        return bool(target.isatty())
    except Exception:
        return False


def colorize(text: str, color: str, *, enabled: bool = True) -> str:
    if not enabled or not color:
        return text
    return f"{color}{text}{NC}"


def status_badge(status: str, *, enabled: bool = True) -> str:
    label = status.upper().replace("_", " ")
    badge = f"[{label}]"
    return colorize(badge, _STATUS_COLORS.get(status, BLUE), enabled=enabled)


class Logger:
    def __init__(
        self,
        log_file: Path | None = None,
        show_timestamps: bool = True,
        use_color: bool | None = None,
    ):
        self._log_file = log_file
        self._show_timestamps = show_timestamps
        self._use_color = supports_color(sys.stderr) if use_color is None else use_color

    def _write(self, message: str, color: str = "") -> None:
        """Write *message* to console (with optional color) and to the log file (plain)."""
        timestamp = ""
        if self._show_timestamps:
            timestamp = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "

        # Console output -- colorize the message portion, not the timestamp
        if color and self._use_color:
            console_line = f"{timestamp}{color}{message}{NC}"
        else:
            console_line = f"{timestamp}{message}"
        print(console_line, file=sys.stderr, flush=True)

        # Log-file output -- strip ANSI escape codes
        if self._log_file is not None:
            plain_line = f"{timestamp}{_ANSI_RE.sub('', message)}"
            try:
                self._log_file.parent.mkdir(parents=True, exist_ok=True)
                with self._log_file.open("a", encoding="utf-8") as fh:
                    fh.write(plain_line + "\n")
            except OSError:
                pass  # best-effort logging

    # ----- convenience levels ------------------------------------------------

    def info(self, msg: str) -> None:
        self._write(msg)

    def success(self, msg: str) -> None:
        self._write(msg, color=GREEN)

    def warning(self, msg: str) -> None:
        self._write(msg, color=YELLOW)

    def error(self, msg: str) -> None:
        self._write(msg, color=RED)

    # ----- structured output --------------------------------------------------

    def state(self, status: str, msg: str) -> None:
        self._write(f"{status_badge(status, enabled=self._use_color)} {msg}")

    def queue_summary(
        self,
        *,
        total: int,
        completed: int,
        blocked: int,
        pending: int,
        running: int = 0,
    ) -> None:
        summary = (
            f"{status_badge('running', enabled=self._use_color)} {running}  "
            f"{status_badge('completed', enabled=self._use_color)} {completed}  "
            f"{status_badge('blocked', enabled=self._use_color)} {blocked}  "
            f"{status_badge('pending', enabled=self._use_color)} {pending}  "
            f"{colorize('[TOTAL]', BOLD, enabled=self._use_color)} {total}"
        )
        self._write(summary)

    def task_header(self, task_number: int, task_id: str, task_name: str) -> None:
        """Print a visually distinct task separator block."""
        bar = "\u2501" * 46  # heavy horizontal box-drawing character
        self._write(bar, color=BLUE)
        title = colorize(f"[Task {task_number}]", BOLD, enabled=self._use_color)
        task_label = colorize(task_id, CYAN, enabled=self._use_color)
        self._write(f"{title} {task_label}: {task_name}", color=YELLOW)
        self._write(bar, color=BLUE)

    def changed_files_summary(self, files: list[str], preview_limit: int) -> None:
        """Log the number of changed files and preview the first *preview_limit*."""
        total = len(files)
        self.info(f"Changed files ({total}):")
        for path in files[:preview_limit]:
            self.info(f"  {path}")
        remaining = total - preview_limit
        if remaining > 0:
            self.info(f"  ... {remaining} more omitted")

    def banner(self, project_name: str) -> None:
        """Print a startup banner box."""
        title = f"  autodev  -  {project_name}  "
        width = len(title) + 4
        border = "+" + "-" * (width - 2) + "+"
        padding = "|" + " " * (width - 2) + "|"
        center = "|  " + title + "  |"
        self._write(border, color=BLUE)
        self._write(padding, color=BLUE)
        self._write(center, color=BLUE)
        self._write(padding, color=BLUE)
        self._write(border, color=BLUE)
