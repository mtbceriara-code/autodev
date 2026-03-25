from __future__ import annotations


def task_identity_text(task: dict) -> tuple[str, str]:
    """Return normalized task id and title text for UI/prompt rendering."""
    task_id = str(task.get("id", "")).strip()
    task_title = str(task.get("title") or task.get("name") or "").strip()
    return task_id, task_title


def format_bullet_list(items: object, *, empty_text: str) -> str:
    """Render a list-like object as markdown bullets, dropping blank entries."""
    values = [str(item).strip() for item in items] if isinstance(items, list) else []
    values = [value for value in values if value]
    if not values:
        return empty_text
    return "\n".join(f"- {value}" for value in values)
