from __future__ import annotations

from autodev.task_audit import describe_task_contract


_EXECUTION_CONTEXT_FIELDS = (
    ("execution_mode", "Mode"),
    ("current_iteration", "Current iteration"),
    ("max_iterations", "Max iterations"),
    ("baseline_metric", "Baseline metric"),
    ("best_metric", "Best metric"),
    ("no_improvement_streak", "No improvement streak"),
    ("metric_goal", "Metric goal"),
)


def build_execution_context(task: dict, execution_context: dict | None = None) -> dict[str, object]:
    """Return a stable execution-context mapping for prompts and task briefs."""
    context = dict(execution_context or {})
    if not str(context.get("execution_mode", "")).strip():
        context["execution_mode"] = describe_task_contract(task)["execution_mode"]
    return context


def format_execution_context_prompt_lines(
    task: dict,
    execution_context: dict | None = None,
    *,
    empty_text: str = "- Standard delivery execution",
) -> str:
    """Render execution context using machine-readable keys for prompts."""
    context = build_execution_context(task, execution_context)
    lines: list[str] = []
    for key, _ in _EXECUTION_CONTEXT_FIELDS:
        value = str(context.get(key, "")).strip()
        if value:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines) if lines else empty_text


def format_execution_context_brief_lines(
    task: dict,
    execution_context: dict | None = None,
    *,
    attempt: int | None = None,
    max_attempts: int | None = None,
    empty_text: str = "- Standard delivery execution",
) -> str:
    """Render execution context using human-readable labels for TASK.md."""
    context = build_execution_context(task, execution_context)
    lines: list[str] = []
    if attempt is not None and max_attempts is not None:
        lines.append(f"- Attempt: {attempt}/{max_attempts}")
    for key, label in _EXECUTION_CONTEXT_FIELDS:
        value = str(context.get(key, "")).strip()
        if value:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines) if lines else empty_text
