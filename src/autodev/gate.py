from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from autodev.task_audit import normalize_task_contracts
from autodev.task_formatting import task_identity_text

if TYPE_CHECKING:
    from autodev.config import AutodevConfig


@dataclass
class GateCheck:
    name: str
    ok: bool
    details: str = ""


@dataclass
class GateMetricResult:
    name: str
    value: float | None = None
    baseline: float | None = None
    best_before: float | None = None
    outcome: str = ""
    details: str = ""


@dataclass
class GateVerificationResult:
    passed: bool = False


@dataclass
class GateCompletionResult:
    kind: str = "boolean"
    passed: bool = False
    outcome: str = ""
    source: str = "gate"
    details: str = ""
    name: str = ""
    success_when: str = ""
    value: float | None = None
    baseline: float | None = None
    best_before: float | None = None
    target: float | None = None
    direction: str = ""


@dataclass
class GateResult:
    status: str  # "passed" or "failed"
    task_id: str = ""
    checks: list[GateCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metric: GateMetricResult | None = None
    verification_result: GateVerificationResult = field(default_factory=GateVerificationResult)
    completion_result: GateCompletionResult = field(default_factory=GateCompletionResult)


@dataclass
class ValidateCommandResult:
    command: str = ""
    exit_code: int = 0
    stdout: str = ""
    error_detail: str = ""


@dataclass
class TaskGateConfig:
    """Task verification config merged from task.json + global config."""

    path_patterns: list[str] = field(default_factory=list)
    validate_commands: list[str] = field(default_factory=list)
    min_changed_files: int = 1
    validate_timeout_seconds: int = 1800
    validate_working_directory: str = ""
    validate_environment: dict[str, str] = field(default_factory=dict)


def get_task_gate(task: dict, config: AutodevConfig) -> TaskGateConfig:
    """Merge task-level verification config with global defaults."""
    task_verification = task.get("verification", task.get("gate", {}))
    if not isinstance(task_verification, dict):
        task_verification = {}
    return TaskGateConfig(
        path_patterns=task_verification.get("path_patterns", []),
        validate_commands=task_verification.get(
            "validate_commands",
            config.verification.validate_commands,
        ),
        min_changed_files=config.verification.min_changed_files,
        validate_timeout_seconds=int(
            task_verification.get(
                "validate_timeout_seconds",
                config.verification.validate_timeout_seconds,
            )
        ),
        validate_working_directory=str(
            task_verification.get(
                "validate_working_directory",
                config.verification.validate_working_directory,
            )
        ),
        validate_environment={
            str(key): str(value)
            for key, value in (
                task_verification.get(
                    "validate_environment",
                    config.verification.validate_environment,
                )
                or {}
            ).items()
        },
    )


def has_matching_path(changed_files: list[str], patterns: list[str]) -> bool:
    """Check if any changed file matches any of the required patterns.
    Uses fnmatch glob matching (same as existing task_acceptance_gate.py).
    """
    for pattern in patterns:
        for filepath in changed_files:
            if fnmatch.fnmatch(filepath, pattern):
                return True
            if not pattern.startswith("*") and fnmatch.fnmatch(filepath, "*" + pattern):
                return True
    return False


def resolve_validate_cwd(code_dir: Path, working_directory: str) -> Path:
    """Resolve validation working directory against the project code dir."""
    if not working_directory:
        return code_dir
    workdir = Path(working_directory)
    if workdir.is_absolute():
        return workdir
    return (code_dir / workdir).resolve()


_SHELL_CONTROL_TOKENS = {"&&", "||", "|", ";", "<", ">", ">>"}


def _parse_validate_command(cmd: str) -> list[str]:
    """Parse a validation command into argv, rejecting shell-only syntax."""
    stripped = cmd.strip()
    if not stripped:
        raise ValueError("Validation command is empty")
    argv = shlex.split(stripped)
    if not argv:
        raise ValueError("Validation command is empty")
    if any(
        token in _SHELL_CONTROL_TOKENS
        or token.startswith((">", "<"))
        or "$(" in token
        or "`" in token
        for token in argv
    ):
        raise ValueError(
            "Validation command uses shell syntax; split it into separate commands "
            "or invoke a checked-in script directly"
        )
    return argv


def run_validate_command(
    cmd: str,
    cwd: Path,
    timeout_seconds: int,
    environment: dict[str, str] | None = None,
) -> ValidateCommandResult:
    """Run a validation command and return exit code, stdout, and any error."""
    try:
        argv = _parse_validate_command(cmd)
    except ValueError as exc:
        return ValidateCommandResult(command=cmd, exit_code=-1, error_detail=str(exc))

    try:
        env = os.environ.copy()
        if environment:
            env.update(environment)
        result = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
        return ValidateCommandResult(command=cmd, exit_code=result.returncode, stdout=result.stdout or "")
    except subprocess.TimeoutExpired:
        return ValidateCommandResult(command=cmd, exit_code=-1, error_detail="Validation command timed out")
    except OSError as exc:
        return ValidateCommandResult(command=cmd, exit_code=-1, error_detail=str(exc) or "Validation command failed")


_METRIC_SEGMENT_PATTERN = re.compile(r"([^\[\]]+)|\[(\d+)\]")


def _parse_metric_json_path(json_path: str) -> list[str | int]:
    path = str(json_path or "").strip()
    if not path:
        raise ValueError("Experiment metric json_path is empty")
    if path == "$":
        return []
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:].lstrip(".")
    if not path:
        return []

    parts: list[str | int] = []
    for segment in path.split("."):
        if not segment:
            raise ValueError(f"Experiment metric json_path '{json_path}' is invalid")
        position = 0
        for match in _METRIC_SEGMENT_PATTERN.finditer(segment):
            if match.start() != position:
                raise ValueError(f"Experiment metric json_path '{json_path}' is invalid")
            key = match.group(1)
            index = match.group(2)
            if key is not None:
                parts.append(key)
            elif index is not None:
                parts.append(int(index))
            position = match.end()
        if position != len(segment):
            raise ValueError(f"Experiment metric json_path '{json_path}' is invalid")
    return parts


def _extract_metric_from_json_stdout(stdout: str, json_path: str) -> float:
    text = str(stdout or "").strip()
    if not text:
        raise ValueError("Validation command did not produce JSON stdout")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Validation command stdout is not valid JSON: {exc.msg}") from exc

    current: object = payload
    for part in _parse_metric_json_path(json_path):
        if isinstance(part, int):
            if not isinstance(current, list):
                raise ValueError(f"Metric json_path segment [{part}] expected a list")
            if part < 0 or part >= len(current):
                raise ValueError(f"Metric json_path segment [{part}] is out of range")
            current = current[part]
            continue
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Metric json_path segment '{part}' was not found")
        current = current[part]

    if isinstance(current, bool) or not isinstance(current, (int, float)):
        raise ValueError("Metric json_path did not resolve to a numeric value")
    return float(current)


def _format_metric_value(value: float | None) -> str:
    return "n/a" if value is None else f"{value:g}"


def _compare_metric_value(
    value: float,
    *,
    direction: str,
    baseline: float | None,
    best_before: float | None,
    min_improvement: float,
    unchanged_tolerance: float,
) -> tuple[str, str]:
    reference = best_before if best_before is not None else baseline
    if reference is None:
        return "measured", f"measured={value:g} (no baseline/reference provided)"

    delta = value - reference
    improvement = (reference - value) if direction == "lower_is_better" else (value - reference)
    if abs(delta) <= unchanged_tolerance:
        return "unchanged", (
            f"measured={value:g}, reference={reference:g}, delta={delta:g}, "
            f"within tolerance={unchanged_tolerance:g}"
        )
    if improvement > 0 and improvement < min_improvement:
        return "unchanged", (
            f"measured={value:g}, reference={reference:g}, improvement={improvement:g}, "
            f"below min_improvement={min_improvement:g}"
        )
    if improvement >= min_improvement:
        return "improved", (
            f"measured={value:g}, reference={reference:g}, improvement={improvement:g}"
        )
    return "regressed", f"measured={value:g}, reference={reference:g}, delta={delta:g}"


def _metric_target_is_met(value: float, *, target: float, direction: str) -> bool:
    if direction == "lower_is_better":
        return value <= target
    if direction == "higher_is_better":
        return value >= target
    return False


def _evaluate_numeric_completion_metric(
    task: dict,
    validate_results: list[ValidateCommandResult],
    *,
    baseline_metric: float | None,
    best_before: float | None,
) -> GateMetricResult | None:
    completion, _ = normalize_task_contracts(task)
    if completion.get("kind") != "numeric":
        return None

    metric_name = str(completion.get("name") or "metric").strip() or "metric"
    metric_source = str(completion.get("source") or "json_stdout").strip() or "json_stdout"
    json_path = str(completion.get("json_path") or "").strip()
    direction = str(completion.get("direction") or "").strip()
    min_improvement = float(completion.get("min_improvement") or 0.0)
    unchanged_tolerance = float(completion.get("unchanged_tolerance") or 0.0)

    if metric_source != "json_stdout":
        return GateMetricResult(
            name=metric_name,
            baseline=baseline_metric,
            best_before=best_before,
            outcome="invalid",
            details=f"Unsupported metric source: {metric_source}",
        )
    if not json_path:
        return GateMetricResult(
            name=metric_name,
            baseline=baseline_metric,
            best_before=best_before,
            outcome="invalid",
            details="Completion metric json_path is empty",
        )
    if direction not in {"lower_is_better", "higher_is_better"}:
        return GateMetricResult(
            name=metric_name,
            baseline=baseline_metric,
            best_before=best_before,
            outcome="invalid",
            details=f"Unsupported metric direction: {direction}",
        )

    extraction_errors: list[str] = []
    for validate_result in reversed(validate_results):
        if validate_result.exit_code != 0:
            continue
        try:
            metric_value = _extract_metric_from_json_stdout(validate_result.stdout, json_path)
        except ValueError as exc:
            extraction_errors.append(f"{validate_result.command}: {exc}")
            continue
        outcome, details = _compare_metric_value(
            metric_value,
            direction=direction,
            baseline=baseline_metric,
            best_before=best_before,
            min_improvement=min_improvement,
            unchanged_tolerance=unchanged_tolerance,
        )
        return GateMetricResult(
            name=metric_name,
            value=metric_value,
            baseline=baseline_metric,
            best_before=best_before,
            outcome=outcome,
            details=details,
        )

    details = (
        extraction_errors[0]
        if extraction_errors
        else "No successful validation command produced JSON stdout for metric extraction"
    )
    return GateMetricResult(
        name=metric_name,
        baseline=baseline_metric,
        best_before=best_before,
        outcome="invalid",
        details=details,
    )


def _build_boolean_completion_result(
    completion: dict,
    *,
    verification_passed: bool,
    verification_errors: list[str],
) -> GateCompletionResult:
    details = (
        "All verification checks passed"
        if verification_passed
        else "; ".join(verification_errors[:3]) or "Verification checks did not pass"
    )
    return GateCompletionResult(
        kind="boolean",
        passed=verification_passed,
        outcome="met" if verification_passed else "not_met",
        source="gate",
        details=details,
        success_when=str(completion.get("success_when") or "all_checks_pass"),
    )


def _build_numeric_completion_result(completion: dict, metric_result: GateMetricResult | None) -> GateCompletionResult:
    result = GateCompletionResult(
        kind="numeric",
        source=str(completion.get("source") or "json_stdout"),
        name=str(completion.get("name") or (metric_result.name if metric_result is not None else "metric")).strip()
        or "metric",
        value=metric_result.value if metric_result is not None else None,
        baseline=metric_result.baseline if metric_result is not None else None,
        best_before=metric_result.best_before if metric_result is not None else None,
        direction=str(completion.get("direction") or "").strip(),
        target=completion.get("target") if isinstance(completion.get("target"), (int, float)) else None,
    )
    if metric_result is None:
        result.outcome = "invalid"
        result.details = "Numeric completion metric could not be evaluated"
        return result

    result.details = metric_result.details
    result.outcome = metric_result.outcome or "invalid"
    result.passed = result.outcome not in {"invalid", "regressed"}

    if (
        result.target is not None
        and metric_result.value is not None
        and result.outcome not in {"invalid", "regressed"}
    ):
        if _metric_target_is_met(metric_result.value, target=float(result.target), direction=result.direction):
            result.outcome = "target_met"
            target_text = f"target={float(result.target):g} met"
            result.details = f"{result.details}; {target_text}" if result.details else target_text
            result.passed = True
        else:
            target_text = f"target={float(result.target):g} not met"
            result.details = f"{result.details}; {target_text}" if result.details else target_text
            result.passed = False
    elif result.target is not None and metric_result.value is None:
        result.passed = False
        target_text = f"target={float(result.target):g} could not be evaluated"
        result.details = f"{result.details}; {target_text}" if result.details else target_text

    return result


def _completion_failure_message(completion_result: GateCompletionResult) -> str:
    if completion_result.kind == "boolean":
        return completion_result.details or "Boolean completion condition was not met"

    metric_name = completion_result.name or "metric"
    outcome = completion_result.outcome or "invalid"
    value_text = _format_metric_value(completion_result.value)
    detail_text = f". {completion_result.details}" if completion_result.details else ""
    return f"Completion metric {metric_name} did not pass: outcome={outcome}, value={value_text}{detail_text}"


def run_gate(
    task: dict,
    config: AutodevConfig,
    changed_files: list[str],
    code_dir: Path,
    *,
    baseline_metric: float | None = None,
    best_before: float | None = None,
    enforce_change_requirements: bool = True,
) -> GateResult:
    """Run all task completion verification checks.

    Checks:
    1. Changed files >= min_changed_files
    2. Changed files match path_patterns (if any defined)
    3. Validate commands pass (if any defined)
    """
    gate_config = get_task_gate(task, config)
    completion, _ = normalize_task_contracts(task)
    task_id, _ = task_identity_text(task)

    result = GateResult(status="passed", task_id=task_id)

    if enforce_change_requirements:
        count_ok = len(changed_files) >= gate_config.min_changed_files
        result.checks.append(
            GateCheck(
                name="min_changed_files",
                ok=count_ok,
                details=f"{len(changed_files)} files changed (minimum: {gate_config.min_changed_files})",
            )
        )
        if not count_ok:
            result.errors.append(
                f"Too few changed files: {len(changed_files)} < {gate_config.min_changed_files}"
            )

    if enforce_change_requirements and gate_config.path_patterns:
        paths_ok = has_matching_path(changed_files, gate_config.path_patterns)
        result.checks.append(
            GateCheck(
                name="path_patterns",
                ok=paths_ok,
                details=f"Patterns: {gate_config.path_patterns}",
            )
        )
        if not paths_ok:
            result.errors.append(
                f"Changed files do not match required patterns: {gate_config.path_patterns}"
            )

    validate_cwd = resolve_validate_cwd(code_dir, gate_config.validate_working_directory)
    validate_results: list[ValidateCommandResult] = []
    for cmd in gate_config.validate_commands:
        validate_result = run_validate_command(
            cmd,
            validate_cwd,
            timeout_seconds=gate_config.validate_timeout_seconds,
            environment=gate_config.validate_environment,
        )
        validate_results.append(validate_result)
        cmd_ok = validate_result.exit_code == 0
        details = f"exit_code={validate_result.exit_code}"
        if validate_result.error_detail:
            details = f"{details}, error={validate_result.error_detail}"
        result.checks.append(
            GateCheck(
                name=f"validate:{cmd}",
                ok=cmd_ok,
                details=details,
            )
        )
        if not cmd_ok:
            message = (
                "Validation command failed: "
                f"{cmd} (exit={validate_result.exit_code}, timeout={gate_config.validate_timeout_seconds}s)"
            )
            if validate_result.error_detail:
                message += f". {validate_result.error_detail}"
            result.errors.append(message)

    result.verification_result = GateVerificationResult(passed=not result.errors)

    if completion.get("kind") == "numeric":
        metric_result = _evaluate_numeric_completion_metric(
            task,
            validate_results,
            baseline_metric=baseline_metric,
            best_before=best_before,
        )
        result.metric = metric_result
        result.completion_result = _build_numeric_completion_result(completion, metric_result)
        if metric_result is not None:
            result.checks.append(
                GateCheck(
                    name=f"metric:{metric_result.name or 'metric'}",
                    ok=result.completion_result.passed,
                    details=(
                        f"outcome={result.completion_result.outcome}, value={_format_metric_value(metric_result.value)}, "
                        f"baseline={_format_metric_value(metric_result.baseline)}, "
                        f"best_before={_format_metric_value(metric_result.best_before)}"
                        + (f", details={result.completion_result.details}" if result.completion_result.details else "")
                    ),
                )
            )
    else:
        result.completion_result = _build_boolean_completion_result(
            completion,
            verification_passed=result.verification_result.passed,
            verification_errors=result.errors,
        )

    if not result.completion_result.passed:
        completion_error = _completion_failure_message(result.completion_result)
        if completion_error and completion_error not in result.errors:
            result.errors.append(completion_error)

    if not result.verification_result.passed or not result.completion_result.passed:
        result.status = "failed"

    return result
