from __future__ import annotations

from copy import deepcopy

from autodev.task_formatting import task_identity_text
from autodev.task_state import normalize_bool

_ALLOWED_EXECUTION_MODES = {"delivery", "experiment"}
_ALLOWED_EXECUTION_STRATEGIES = {"single_pass", "iterative"}
_ALLOWED_COMPLETION_KINDS = {"boolean", "numeric"}
_ALLOWED_COMPLETION_SOURCES = {"gate", "json_stdout"}
_ALLOWED_BOOLEAN_SUCCESS_WHEN = {"all_checks_pass"}
_ALLOWED_METRIC_DIRECTIONS = {"lower_is_better", "higher_is_better"}
_ALLOWED_METRIC_SOURCES = {"json_stdout"}
_RUNTIME_ONLY_HINTS = (
    "logs",
    "attempts",
    "autodev.log",
    "dashboard.html",
    "runtime-status.json",
    "task.json",
    "progress.txt",
)
_BUILD_ARTIFACT_HINTS = (
    "build",
    "dist",
    "out",
    "cmake-build",
    ".o",
    ".obj",
    ".so",
    ".a",
    ".dll",
    ".dylib",
    ".pdb",
)


class TaskAuditError(RuntimeError):
    """Raised when generated or refined tasks fail mechanical quality checks."""

    def __init__(self, issues: list[str], *, context: str = "Task audit failed") -> None:
        self.issues = [str(issue).strip() for issue in issues if str(issue).strip()]
        message = context
        if self.issues:
            message += ":\n- " + "\n- ".join(self.issues)
        super().__init__(message)


def _as_int(raw: object, default: int) -> int:
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _as_float(raw: object, default: float) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _as_optional_float(raw: object) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _as_bool(raw: object, default: bool) -> bool:
    return normalize_bool(raw, default=default)


def normalize_execution_mode(value: object) -> str:
    mode = str(value or "delivery").strip().lower() or "delivery"
    return mode if mode in _ALLOWED_EXECUTION_MODES else "delivery"


def normalize_execution_strategy(value: object) -> str:
    strategy = str(value or "single_pass").strip().lower() or "single_pass"
    return strategy if strategy in _ALLOWED_EXECUTION_STRATEGIES else "single_pass"


def normalize_experiment_config(value: object) -> dict:
    experiment = deepcopy(value) if isinstance(value, dict) else {}
    goal_metric = experiment.get("goal_metric")
    if not isinstance(goal_metric, dict):
        goal_metric = {}

    return {
        "max_iterations": _as_int(experiment.get("max_iterations"), 3),
        "rollback_on_regression": _as_bool(experiment.get("rollback_on_regression"), True),
        "keep_on_equal": _as_bool(experiment.get("keep_on_equal"), False),
        "commit_prefix": str(experiment.get("commit_prefix") or "experiment").strip() or "experiment",
        "no_improvement_threshold": _as_int(experiment.get("no_improvement_threshold"), 3),
        "invalid_result_threshold": _as_int(experiment.get("invalid_result_threshold"), 2),
        "goal_metric": {
            "name": str(goal_metric.get("name") or "").strip(),
            "direction": str(goal_metric.get("direction") or "").strip(),
            "source": str(goal_metric.get("source") or "json_stdout").strip() or "json_stdout",
            "json_path": str(goal_metric.get("json_path") or "").strip(),
            "min_improvement": _as_float(goal_metric.get("min_improvement"), 0.0),
            "unchanged_tolerance": _as_float(goal_metric.get("unchanged_tolerance"), 0.0),
        },
    }


def normalize_completion_config(value: object) -> dict:
    completion = deepcopy(value) if isinstance(value, dict) else {}
    kind = str(completion.get("kind") or "boolean").strip().lower() or "boolean"
    if kind not in _ALLOWED_COMPLETION_KINDS:
        kind = "boolean"

    if kind == "boolean":
        success_when = (
            str(completion.get("success_when") or "all_checks_pass").strip().lower() or "all_checks_pass"
        )
        if success_when not in _ALLOWED_BOOLEAN_SUCCESS_WHEN:
            success_when = "all_checks_pass"
        return {
            "kind": "boolean",
            "source": "gate",
            "success_when": success_when,
        }

    source = str(completion.get("source") or "json_stdout").strip() or "json_stdout"
    if source not in _ALLOWED_METRIC_SOURCES:
        source = "json_stdout"
    normalized = {
        "kind": "numeric",
        "source": source,
        "name": str(completion.get("name") or "").strip(),
        "direction": str(completion.get("direction") or "").strip(),
        "json_path": str(completion.get("json_path") or "").strip(),
        "min_improvement": _as_float(completion.get("min_improvement"), 0.0),
        "unchanged_tolerance": _as_float(completion.get("unchanged_tolerance"), 0.0),
    }
    target = _as_optional_float(completion.get("target"))
    if target is not None:
        normalized["target"] = target
    return normalized


def normalize_execution_config(value: object) -> dict:
    execution = deepcopy(value) if isinstance(value, dict) else {}
    strategy = normalize_execution_strategy(execution.get("strategy"))
    if strategy == "single_pass":
        return {"strategy": "single_pass"}
    return {
        "strategy": "iterative",
        "max_iterations": _as_int(execution.get("max_iterations"), 3),
        "rollback_on_failure": _as_bool(execution.get("rollback_on_failure"), True),
        "keep_on_equal": _as_bool(execution.get("keep_on_equal"), False),
        "commit_prefix": str(execution.get("commit_prefix") or "experiment").strip() or "experiment",
        "stop_after_no_improvement": _as_int(execution.get("stop_after_no_improvement"), 3),
        "stop_after_invalid": _as_int(execution.get("stop_after_invalid"), 2),
    }


def normalize_task_contracts(task: dict) -> tuple[dict, dict]:
    raw_completion = task.get("completion")
    raw_execution = task.get("execution")
    if isinstance(raw_completion, dict) and raw_completion:
        completion = normalize_completion_config(raw_completion)
    else:
        completion = _completion_from_legacy_task(task)
    if isinstance(raw_execution, dict) and raw_execution:
        execution = normalize_execution_config(raw_execution)
    else:
        execution = _execution_from_legacy_task(task)
    return completion, execution


def describe_task_contract(task: dict) -> dict[str, str]:
    """Return normalized contract metadata used by runtime views and logs."""
    completion, execution = normalize_task_contracts(task)
    execution_strategy = str(execution.get("strategy") or "single_pass")
    execution_mode = "experiment" if execution_strategy == "iterative" else "delivery"
    completion_kind = str(completion.get("kind") or "boolean")
    completion_name = (
        str(completion.get("name") or "gate").strip() if completion_kind == "numeric" else "gate"
    )
    if completion_kind == "numeric":
        direction = str(completion.get("direction") or "").strip()
        target = completion.get("target")
        target_text = f", target={float(target):g}" if isinstance(target, (int, float)) else ""
        completion_target_summary = (
            f"{completion_name}, "
            f"source={str(completion.get('source') or 'json_stdout').strip() or 'json_stdout'}, "
            f"direction={direction or 'unspecified'}{target_text}"
        )
    else:
        completion_target_summary = (
            str(completion.get("success_when") or "all_checks_pass").strip() or "all_checks_pass"
        )
    return {
        "execution_mode": execution_mode,
        "execution_strategy": execution_strategy,
        "completion_kind": completion_kind,
        "completion_name": completion_name,
        "completion_target_summary": completion_target_summary if completion_target_summary else "-",
    }


def legacy_execution_mode_from_execution(execution: object) -> str:
    normalized_execution = normalize_execution_config(execution)
    return "experiment" if normalized_execution.get("strategy") == "iterative" else "delivery"


def legacy_experiment_from_contracts(completion: object, execution: object) -> dict | None:
    normalized_completion = normalize_completion_config(completion)
    normalized_execution = normalize_execution_config(execution)
    if (
        normalized_completion.get("kind") != "numeric"
        and normalized_execution.get("strategy") != "iterative"
    ):
        return None
    return normalize_experiment_config(
        {
            "max_iterations": normalized_execution.get("max_iterations"),
            "rollback_on_regression": normalized_execution.get("rollback_on_failure"),
            "keep_on_equal": normalized_execution.get("keep_on_equal"),
            "commit_prefix": normalized_execution.get("commit_prefix"),
            "no_improvement_threshold": normalized_execution.get("stop_after_no_improvement"),
            "invalid_result_threshold": normalized_execution.get("stop_after_invalid"),
            "goal_metric": {
                "name": normalized_completion.get("name"),
                "direction": normalized_completion.get("direction"),
                "source": normalized_completion.get("source", "json_stdout"),
                "json_path": normalized_completion.get("json_path"),
                "min_improvement": normalized_completion.get("min_improvement"),
                "unchanged_tolerance": normalized_completion.get("unchanged_tolerance"),
            },
        }
    )


def audit_generated_task_store(data: dict, *, context: str) -> None:
    issues = _collect_task_store_issues(data, require_pending=True)
    if issues:
        raise TaskAuditError(issues, context=context)


def audit_reflection_update(original_task: dict, updated_task: dict) -> None:
    issues: list[str] = []
    task_label = _task_label(updated_task)

    for field_name in ("id", "title", "description"):
        if original_task.get(field_name) != updated_task.get(field_name):
            issues.append(f"{task_label}: reflection may not change {field_name}")

    original_completion, original_execution = normalize_task_contracts(original_task)
    updated_completion, updated_execution = normalize_task_contracts(updated_task)
    if original_completion != updated_completion:
        issues.append(f"{task_label}: reflection may not change completion configuration")
    if original_execution != updated_execution:
        issues.append(f"{task_label}: reflection may not change execution configuration")

    before_verification = original_task.get("verification")
    after_verification = updated_task.get("verification")
    before_commands = _normalize_str_list(
        before_verification.get("validate_commands") if isinstance(before_verification, dict) else None
    )
    after_commands = _normalize_str_list(
        after_verification.get("validate_commands") if isinstance(after_verification, dict) else None
    )
    before_patterns = _normalize_str_list(
        before_verification.get("path_patterns") if isinstance(before_verification, dict) else None
    )
    after_patterns = _normalize_str_list(
        after_verification.get("path_patterns") if isinstance(after_verification, dict) else None
    )

    if before_commands and not after_commands:
        issues.append(f"{task_label}: reflection may not remove existing validate_commands")
    if before_patterns and not after_patterns:
        issues.append(f"{task_label}: reflection may not remove existing path_patterns")

    issues.extend(_collect_single_task_issues(updated_task, require_pending=False))
    if issues:
        raise TaskAuditError(issues, context="Refined task failed audit")


def _collect_task_store_issues(data: dict, *, require_pending: bool) -> list[str]:
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return ["task store is missing a tasks array"]

    issues: list[str] = []
    seen_ids: dict[str, int] = {}
    seen_titles: dict[str, int] = {}
    seen_outputs: dict[str, str] = {}

    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            issues.append(f"task #{index}: task entry must be an object")
            continue

        issues.extend(_collect_single_task_issues(task, require_pending=require_pending))
        task_label = _task_label(task)
        task_id, task_title = task_identity_text(task)

        if task_id:
            if task_id in seen_ids:
                issues.append(f"{task_id}: duplicate task id also used by task #{seen_ids[task_id]}")
            else:
                seen_ids[task_id] = index

        normalized_title = _normalize_title(task_title)
        if normalized_title:
            if normalized_title in seen_titles:
                issues.append(f"{task_label}: duplicate task title overlaps task #{seen_titles[normalized_title]}")
            else:
                seen_titles[normalized_title] = index

        for output_path in _normalize_str_list(task.get("output")):
            normalized_output = output_path.replace("\\", "/")
            previous_owner = seen_outputs.get(normalized_output)
            if previous_owner and previous_owner != task_label:
                # Output overlap is expected in sequential execution: later
                # tasks routinely extend files created by earlier tasks.
                # Record the last writer but do not flag an error.
                pass
            seen_outputs[normalized_output] = task_label

    return issues


def _collect_single_task_issues(task: dict, *, require_pending: bool) -> list[str]:
    issues: list[str] = []
    task_label = _task_label(task)
    task_id, task_title = task_identity_text(task)

    if not task_id:
        issues.append(f"{task_label}: missing id")
    if not task_title:
        issues.append(f"{task_label}: missing title")
    if not str(task.get("description") or "").strip():
        issues.append(f"{task_label}: missing description")
    if not _normalize_str_list(task.get("steps")):
        issues.append(f"{task_label}: missing actionable steps")

    verification = task.get("verification")
    if not isinstance(verification, dict):
        verification = {}
    validate_commands = _normalize_str_list(verification.get("validate_commands"))
    path_patterns = _normalize_str_list(verification.get("path_patterns"))
    if not validate_commands and not path_patterns:
        issues.append(f"{task_label}: verification must include validate_commands or path_patterns")
    elif not validate_commands and _patterns_are_runtime_or_build_only(path_patterns):
        issues.append(
            f"{task_label}: verification may not rely only on runtime/build artifact path patterns"
        )

    raw_mode = task.get("execution_mode")
    if raw_mode is not None:
        raw_mode_text = str(raw_mode).strip().lower()
        if raw_mode_text and raw_mode_text not in _ALLOWED_EXECUTION_MODES:
            issues.append(f"{task_label}: unsupported execution_mode '{task.get('execution_mode')}'")

    raw_completion = task.get("completion")
    if isinstance(raw_completion, dict):
        raw_kind = str(raw_completion.get("kind") or "").strip().lower()
        if raw_kind and raw_kind not in _ALLOWED_COMPLETION_KINDS:
            issues.append(f"{task_label}: completion.kind must be one of {sorted(_ALLOWED_COMPLETION_KINDS)}")
        raw_source = str(raw_completion.get("source") or "").strip()
        if raw_source and raw_source not in _ALLOWED_COMPLETION_SOURCES:
            issues.append(
                f"{task_label}: completion.source must be one of {sorted(_ALLOWED_COMPLETION_SOURCES)}"
            )

    raw_execution = task.get("execution")
    if isinstance(raw_execution, dict):
        raw_strategy = str(raw_execution.get("strategy") or "").strip().lower()
        if raw_strategy and raw_strategy not in _ALLOWED_EXECUTION_STRATEGIES:
            issues.append(
                f"{task_label}: execution.strategy must be one of {sorted(_ALLOWED_EXECUTION_STRATEGIES)}"
            )

    if require_pending and _as_bool(task.get("passes"), False):
        issues.append(f"{task_label}: generated tasks must not start with passes=true")
    if require_pending and _as_bool(task.get("blocked"), False):
        issues.append(f"{task_label}: generated tasks must not start with blocked=true")

    completion, execution = normalize_task_contracts(task)
    issues.extend(_collect_completion_issues(task_label, completion, validate_commands))
    issues.extend(_collect_execution_issues(task_label, execution, completion))

    return issues


def _collect_completion_issues(
    task_label: str,
    completion: dict,
    validate_commands: list[str],
) -> list[str]:
    issues: list[str] = []
    kind = completion.get("kind")
    if kind not in _ALLOWED_COMPLETION_KINDS:
        issues.append(f"{task_label}: completion.kind must be one of {sorted(_ALLOWED_COMPLETION_KINDS)}")
        return issues

    if kind == "boolean":
        if completion.get("source") != "gate":
            issues.append(f"{task_label}: boolean completion.source must be 'gate'")
        if completion.get("success_when") not in _ALLOWED_BOOLEAN_SUCCESS_WHEN:
            issues.append(
                f"{task_label}: boolean completion.success_when must be one of {sorted(_ALLOWED_BOOLEAN_SUCCESS_WHEN)}"
            )
        return issues

    if completion.get("source") not in _ALLOWED_METRIC_SOURCES:
        issues.append(
            f"{task_label}: numeric completion.source must be one of {sorted(_ALLOWED_METRIC_SOURCES)}"
        )
    if not validate_commands:
        issues.append(f"{task_label}: numeric completion requires validate_commands for metric collection")
    if not str(completion.get("name") or "").strip():
        issues.append(f"{task_label}: completion.name is required for numeric completion")
    if completion.get("direction") not in _ALLOWED_METRIC_DIRECTIONS:
        issues.append(
            f"{task_label}: completion.direction must be one of {sorted(_ALLOWED_METRIC_DIRECTIONS)}"
        )
    if not str(completion.get("json_path") or "").strip():
        issues.append(f"{task_label}: completion.json_path is required for numeric completion")
    return issues


def _collect_execution_issues(task_label: str, execution: dict, completion: dict) -> list[str]:
    issues: list[str] = []
    strategy = execution.get("strategy")
    if strategy not in _ALLOWED_EXECUTION_STRATEGIES:
        issues.append(f"{task_label}: execution.strategy must be one of {sorted(_ALLOWED_EXECUTION_STRATEGIES)}")
        return issues

    if strategy == "iterative":
        if completion.get("kind") != "numeric":
            issues.append(f"{task_label}: iterative execution requires numeric completion")
        for field_name in (
            "max_iterations",
            "stop_after_no_improvement",
            "stop_after_invalid",
        ):
            try:
                value = int(execution.get(field_name, 0) or 0)
            except (TypeError, ValueError):
                value = 0
            if value <= 0:
                issues.append(f"{task_label}: execution.{field_name} must be a positive integer")
    return issues


def _completion_from_legacy_task(task: dict) -> dict:
    raw_experiment = task.get("experiment")
    mode = normalize_execution_mode(task.get("execution_mode"))
    if mode == "experiment" or (isinstance(raw_experiment, dict) and raw_experiment):
        experiment = normalize_experiment_config(raw_experiment)
        goal_metric = experiment.get("goal_metric") if isinstance(experiment.get("goal_metric"), dict) else {}
        return normalize_completion_config(
            {
                "kind": "numeric",
                "source": goal_metric.get("source"),
                "name": goal_metric.get("name"),
                "direction": goal_metric.get("direction"),
                "json_path": goal_metric.get("json_path"),
                "min_improvement": goal_metric.get("min_improvement"),
                "unchanged_tolerance": goal_metric.get("unchanged_tolerance"),
            }
        )
    return normalize_completion_config({"kind": "boolean", "source": "gate"})


def _execution_from_legacy_task(task: dict) -> dict:
    raw_experiment = task.get("experiment")
    mode = normalize_execution_mode(task.get("execution_mode"))
    if mode == "experiment" or (isinstance(raw_experiment, dict) and raw_experiment):
        experiment = normalize_experiment_config(raw_experiment)
        return normalize_execution_config(
            {
                "strategy": "iterative",
                "max_iterations": experiment.get("max_iterations"),
                "rollback_on_failure": experiment.get("rollback_on_regression"),
                "keep_on_equal": experiment.get("keep_on_equal"),
                "commit_prefix": experiment.get("commit_prefix"),
                "stop_after_no_improvement": experiment.get("no_improvement_threshold"),
                "stop_after_invalid": experiment.get("invalid_result_threshold"),
            }
        )
    return normalize_execution_config({"strategy": "single_pass"})


def _patterns_are_runtime_or_build_only(patterns: list[str]) -> bool:
    if not patterns:
        return False
    return all(_pattern_looks_runtime_or_build_only(pattern) for pattern in patterns)


def _pattern_looks_runtime_or_build_only(pattern: str) -> bool:
    lowered = str(pattern).strip().lower().replace("\\", "/")
    if not lowered:
        return True
    return any(hint in lowered for hint in _RUNTIME_ONLY_HINTS + _BUILD_ARTIFACT_HINTS)


def _normalize_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value]
    return [item for item in items if item]


def _normalize_title(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _task_label(task: dict) -> str:
    task_id, title = task_identity_text(task)
    if task_id:
        return task_id
    return title or "task"
