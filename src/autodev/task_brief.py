"""Helpers for maintaining the project-local active task summary file."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.config import AutodevConfig

from autodev.execution_context import format_execution_context_brief_lines
from autodev.task_formatting import format_bullet_list, task_identity_text


_IDLE_TASK_BRIEF = """\
# Current Task

No active task is being executed right now.

## Runtime Sources of Truth

- `task.json`
- `AGENT.md`
- `progress.txt`
"""


def write_idle_task_brief(path: Path) -> None:
    """Write the default placeholder active-task summary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_IDLE_TASK_BRIEF, encoding="utf-8")


def write_task_brief(
    path: Path,
    task: dict,
    config: "AutodevConfig",
    *,
    attempt: int | None = None,
    max_attempts: int | None = None,
    execution_context: dict | None = None,
) -> None:
    """Write a compact markdown summary of the current task."""
    execution_context = execution_context or {}
    task_id, task_name = task_identity_text(task)
    task_description = str(task.get("description", "")).strip()
    steps = format_bullet_list(task.get("steps"), empty_text="- No steps listed")
    docs = format_bullet_list(task.get("docs"), empty_text="- No docs listed")
    execution_lines = format_execution_context_brief_lines(
        task,
        execution_context,
        attempt=attempt,
        max_attempts=max_attempts,
    )

    content = f"""\
# Current Task

## Task

- ID: {task_id or "(unknown)"}
- Name: {task_name or "(untitled)"}

## Summary

{task_description or "No description provided."}

## Steps

{steps}

## Docs

{docs}

## Execution Context

{execution_lines}

## Runtime Sources of Truth

- `{Path(config.files.task_json).name}`
- `{Path(config.files.execution_guide).name}`
- `{Path(config.files.progress).name}`
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
