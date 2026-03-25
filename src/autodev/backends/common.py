"""Shared backend command/result helpers."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BackendResult:
    """Result of running an AI backend."""

    exit_code: int
    log_file: Path
    tee_exit: int = 0


@dataclass(frozen=True)
class CommandSpec:
    """Executable backend command and optional environment overrides."""

    cmd: list[str]
    env: dict[str, str] | None = None


def execute_with_tee(
    cmd: list[str],
    env: dict[str, str] | None,
    cwd: Path,
    attempt_log: Path,
    main_log: Path,
) -> BackendResult:
    """Run command, tee output to attempt log + main log + stdout."""
    if shutil.which("stdbuf"):
        cmd = ["stdbuf", "-oL", "-eL"] + cmd

    tee_exit = 0
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(cwd),
            env=env,
        )
    except FileNotFoundError as exc:
        err_msg = f"Error: {exc}\n"
        attempt_log.write_text(err_msg, encoding="utf-8")
        with open(main_log, "a", encoding="utf-8") as mf:
            mf.write(err_msg)
        return BackendResult(exit_code=127, log_file=attempt_log, tee_exit=0)

    try:
        with open(attempt_log, "wb") as af, open(main_log, "ab") as mf:
            assert proc.stdout is not None
            for chunk in iter(lambda: proc.stdout.read(4096), b""):
                try:
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                except OSError:
                    pass
                try:
                    af.write(chunk)
                    mf.write(chunk)
                except OSError:
                    tee_exit = 1
    except OSError:
        tee_exit = 1

    exit_code = proc.wait()
    return BackendResult(exit_code=exit_code, log_file=attempt_log, tee_exit=tee_exit)
