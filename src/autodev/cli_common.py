"""Shared helpers for CLI commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find_config(args: argparse.Namespace) -> Path:
    """Locate the config file from CLI args or search upward."""
    if hasattr(args, "config") and args.config:
        path = Path(args.config)
        if not path.exists():
            print(f"Error: config file not found: {path}", file=sys.stderr)
            sys.exit(1)
        return path

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / "autodev.toml"
        if candidate.exists():
            return candidate

    print(
        "Error: autodev.toml not found in current directory or any parent.\n"
        "Run 'autodev init' to create one.",
        file=sys.stderr,
    )
    sys.exit(1)


def load_runtime_config(args: argparse.Namespace):
    """Load and return an ``AutodevConfig`` for a command invocation."""
    from autodev.config import ConfigError, load_config

    path = find_config(args)
    try:
        return load_config(path)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error loading {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def print_json(data: object, *, ensure_ascii: bool = True) -> None:
    """Print formatted JSON consistently across commands."""
    print(json.dumps(data, indent=2, ensure_ascii=ensure_ascii))


def load_task_data(args: argparse.Namespace):
    """Load runtime config together with the project's task data."""
    from autodev.task_store import load_tasks

    config = load_runtime_config(args)
    task_path = Path(config.files.task_json)
    try:
        data = load_tasks(task_path)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"Task data error: {exc}", file=sys.stderr)
        sys.exit(1)
    return config, task_path, data


def parse_key_value_items(items: list[str] | None) -> dict[str, str]:
    """Parse repeated ``key=value`` CLI arguments into a dictionary."""
    values: dict[str, str] = {}
    if not items:
        return values

    for item in items:
        if "=" in item:
            key, value = item.split("=", 1)
            values[key] = value
    return values
