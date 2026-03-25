from __future__ import annotations

from collections.abc import Collection

from autodev.task_formatting import task_identity_text

_TRUE_STRINGS = frozenset({"1", "true", "yes", "y", "on"})
_FALSE_STRINGS = frozenset({"0", "false", "no", "n", "off"})


def normalize_bool(value: object, default: bool = False) -> bool:
    """Convert task-like truthy values into a Python bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_STRINGS:
            return True
        if lowered in _FALSE_STRINGS:
            return False
        return default
    if value is None:
        return default
    return bool(value)


def normalize_int(value: object, default: int = 0) -> int:
    """Convert task-like numeric values into an integer."""
    try:
        return int(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default


def normalize_block_reason(value: object, *, strip: bool = False) -> str:
    """Normalize task block-reason text for storage or display."""
    text = str(value or "")
    return text.strip() if strip else text


def task_matches_id(task: dict | None, task_id: object) -> bool:
    """Return True when a task id matches after string normalization."""
    if not isinstance(task, dict):
        return False
    current_task_id, _ = task_identity_text(task)
    expected_task_id = str(task_id or "").strip()
    return bool(current_task_id) and current_task_id == expected_task_id


def task_is_completed(task: dict | None) -> bool:
    """Return True when a task is marked complete."""
    return isinstance(task, dict) and normalize_bool(task.get("passes"), default=False)


def task_is_blocked(task: dict | None) -> bool:
    """Return True when a task is marked blocked."""
    return isinstance(task, dict) and normalize_bool(task.get("blocked"), default=False)


def task_has_final_status(task: dict | None) -> bool:
    """Return True when a task is either completed or blocked."""
    return task_is_completed(task) or task_is_blocked(task)


def task_lifecycle_status(
    task: dict | None,
    *,
    active_task_id: str = "",
    run_status: str = "",
    active_run_states: Collection[str] | None = None,
) -> str:
    """Return the normalized lifecycle status label for a task."""
    if task_is_completed(task):
        return "completed"
    if task_is_blocked(task):
        return "blocked"
    if (
        active_run_states
        and run_status in active_run_states
        and task_matches_id(task, active_task_id)
    ):
        return "running"
    return "pending"
