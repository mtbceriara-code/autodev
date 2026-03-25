"""CLI handlers for project bootstrap and execution commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autodev.cli_common import load_runtime_config


def cmd_run(args: argparse.Namespace) -> int:
    """Handle ``autodev run``."""
    from autodev.log import Logger
    from autodev.runner import run

    config = load_runtime_config(args)

    if args.backend:
        config.backend.default = args.backend
    if args.max_tasks is not None:
        config.run.max_tasks = args.max_tasks
    if args.max_retries is not None:
        config.run.max_retries = args.max_retries
    if args.epochs is not None:
        config.run.max_epochs = args.epochs

    # --detach: launch the run in a background tmux session
    if getattr(args, "detach", False):
        from autodev.tmux_session import check_tmux_available, launch_detached

        err = check_tmux_available()
        if err:
            print(err, file=sys.stderr)
            return 1

        session_name = f"{config.detach.tmux_session_prefix}-{config.project.name}"
        cmd = _rebuild_run_cmd(args)
        log_file = Path(config.files.log_dir) / "autodev.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        actual_name = launch_detached(
            session_name,
            cmd,
            cwd=Path(config.project.code_dir),
            log_file=log_file,
        )
        print(f"Launched in tmux session: {actual_name}")
        print(f"  tmux attach -t {actual_name}   # watch live")
        print(f"  autodev list                    # see all sessions")
        print(f"  autodev stop {actual_name}      # stop")
        return 0

    log_file = Path(config.files.log_dir) / "autodev.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = Logger(log_file=log_file)

    result = run(config, logger, dry_run=args.dry_run, epochs=config.run.max_epochs)
    return result.exit_code


def _rebuild_run_cmd(args: argparse.Namespace) -> list[str]:
    """Rebuild the ``autodev run`` command without ``--detach``."""
    cmd = ["autodev"]
    if getattr(args, "config", None):
        cmd.extend(["-c", args.config])
    cmd.append("run")
    if getattr(args, "backend", None):
        cmd.extend(["--backend", args.backend])
    if getattr(args, "max_tasks", None) is not None:
        cmd.extend(["--max-tasks", str(args.max_tasks)])
    if getattr(args, "max_retries", None) is not None:
        cmd.extend(["--max-retries", str(args.max_retries)])
    if getattr(args, "epochs", None) is not None:
        cmd.extend(["--epochs", str(args.epochs)])
    if getattr(args, "dry_run", False):
        cmd.append("--dry-run")
    return cmd


def cmd_init(args: argparse.Namespace) -> int:
    """Handle ``autodev init``."""
    from autodev.init_project import (
        infer_init_default_backend,
        init_project,
        parse_init_tools_spec,
    )

    directory = Path(args.directory).resolve()
    try:
        tool = parse_init_tools_spec(args.use)
        default_backend = infer_init_default_backend(tool)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    created = init_project(
        directory,
        project_name=args.name or "",
        available_tool=tool,
        default_backend=default_backend,
    )

    if not created:
        print("All files already exist – nothing to do.")
    else:
        print(f"Created {len(created)} file(s) in {directory}:")
        for file_name in created:
            print(f"  {file_name}")
    return 0
