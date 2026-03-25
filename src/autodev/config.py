"""Load and validate autodev.toml configuration."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# TOML import – Python 3.11 ships tomllib; older versions need tomli.
# ---------------------------------------------------------------------------
try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[import-not-found, no-redef]
    except ModuleNotFoundError:
        raise ImportError(
            "Python 3.10 requires the 'tomli' package to parse TOML files. "
            "Install it with:  pip install tomli"
        ) from None

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid enum values
# ---------------------------------------------------------------------------
_VALID_BACKENDS = {"claude", "codex", "gemini", "opencode"}
_VALID_PERMISSION_MODES = {
    "bypassPermissions",
    "dontAsk",
    "default",
}
_VALID_OUTPUT_FORMATS = {"text", "json", "stream-json"}
_VALID_GEMINI_OUTPUT_FORMATS = {"text", "json"}

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def resolve_path(base: Path, rel: str) -> Path:
    """Resolve *rel* against *base*, returning an absolute ``Path``.

    If *rel* is already absolute it is returned unchanged.
    """
    p = Path(rel)
    if p.is_absolute():
        return p
    return (base / p).resolve()


# ---------------------------------------------------------------------------
# Dataclasses – full configuration tree
# ---------------------------------------------------------------------------

@dataclass
class ClaudeBackendConfig:
    skip_permissions: bool = True
    permission_mode: str = "bypassPermissions"
    output_format: str = "stream-json"
    model: str = ""
    verbose: bool = True


@dataclass
class OpenCodeBackendConfig:
    model: str = ""
    format: str = "default"
    permissions: str = (
        '{"read":"allow","edit":"allow","bash":"allow",'
        '"glob":"allow","grep":"allow"}'
    )
    log_level: str = ""


@dataclass
class CodexBackendConfig:
    model: str = ""
    yolo: bool = True
    full_auto: bool = False
    dangerously_bypass_approvals_and_sandbox: bool = True
    ephemeral: bool = False


@dataclass
class GeminiBackendConfig:
    model: str = ""
    yolo: bool = True
    approval_mode: str = ""
    output_format: str = "text"
    all_files: bool = False
    include_directories: str = ""
    debug: bool = False


@dataclass
class BackendConfig:
    default: str = "claude"
    claude: ClaudeBackendConfig = field(default_factory=ClaudeBackendConfig)
    codex: CodexBackendConfig = field(default_factory=CodexBackendConfig)
    gemini: GeminiBackendConfig = field(default_factory=GeminiBackendConfig)
    opencode: OpenCodeBackendConfig = field(default_factory=OpenCodeBackendConfig)


@dataclass
class ProjectConfig:
    name: str = "Untitled Project"
    code_dir: str = "."
    config_dir: str = "."


@dataclass
class RootModeConfig:
    disable_skip_permissions: bool = True
    fallback_permission_mode: str = "default"


@dataclass
class RunConfig:
    max_retries: int = 3
    max_tasks: int = 999
    max_epochs: int = 1
    heartbeat_interval: int = 20
    keep_attempt_logs: bool = True
    reset_tasks_on_start: bool = False
    delay_between_tasks: int = 2
    root_mode: RootModeConfig = field(default_factory=RootModeConfig)


@dataclass
class FilesConfig:
    task_json: str = "task.json"
    progress: str = "progress.txt"
    execution_guide: str = "AGENT.md"
    task_brief: str = "TASK.md"
    log_dir: str = "logs"
    attempt_log_subdir: str = "attempts"


@dataclass
class VerificationConfig:
    min_changed_files: int = 1
    changed_files_preview_limit: int = 20
    validate_commands: List[str] = field(default_factory=list)
    validate_timeout_seconds: int = 1800
    validate_working_directory: str = ""
    validate_environment: dict[str, str] = field(default_factory=dict)


@dataclass
class ReflectionConfig:
    enabled: bool = True
    max_refinements_per_task: int = 3
    prompt_timeout_seconds: int = 180
    log_tail_lines: int = 80
    max_attempt_history_entries: int = 12
    max_learning_notes: int = 20
    max_project_learning_entries: int = 50
    prompt_learning_limit: int = 6


@dataclass
class PromptConfig:
    template_file: str = ""
    template: str = ""


@dataclass
class SnapshotConfig:
    watch_dirs: List[str] = field(default_factory=lambda: ["."])
    ignore_dirs: List[str] = field(
        default_factory=lambda: [
            ".git",
            ".idea",
            ".vscode",
            "build",
            "venv",
            "__pycache__",
            "node_modules",
            "logs",
        ]
    )
    ignore_path_globs: List[str] = field(
        default_factory=lambda: [
            "build-*",
            "cmake-build-*",
            "out-*",
            "*.dir/*",
            "*.o",
            "*.obj",
            "*.so",
            "*.a",
            "*.dylib",
            "*.dll",
            "*.pdb",
            "*.exp",
            "*.lib",
            "*.ptx",
            "*.cubin",
            "*.fatbin",
            "task.json",
            "progress.txt",
        ]
    )
    include_path_globs: List[str] = field(default_factory=list)


@dataclass
class CircuitBreakerConfig:
    no_progress_threshold: int = 3
    repeated_error_threshold: int = 3
    rate_limit_cooldown: int = 300  # seconds to wait on rate limit
    rate_limit_patterns: List[str] = field(
        default_factory=lambda: [
            "rate_limit",
            "rate limit",
            "overloaded",
            "too many requests",
            "usage cap",
            "capacity",
            "throttl",
        ]
    )


@dataclass
class GitConfig:
    auto_commit: bool = True
    commit_message_template: str = "autodev: {task_id} - {task_name}"


@dataclass
class EnvErrorsConfig:
    halt_patterns: List[str] = field(
        default_factory=lambda: [
            "cannot be used with root/sudo privileges",
            "permission denied",
            "eacces",
            "unauthorized",
            "invalid api key",
            "authentication",
            "forbidden",
            "requires --verbose",
        ]
    )


@dataclass
class DetachConfig:
    tmux_session_prefix: str = "autodev"


@dataclass
class AutodevConfig:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)
    run: RunConfig = field(default_factory=RunConfig)
    files: FilesConfig = field(default_factory=FilesConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    reflection: ReflectionConfig = field(default_factory=ReflectionConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
    snapshot: SnapshotConfig = field(default_factory=SnapshotConfig)
    env_errors: EnvErrorsConfig = field(default_factory=EnvErrorsConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    git: GitConfig = field(default_factory=GitConfig)
    detach: DetachConfig = field(default_factory=DetachConfig)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _populate_dataclass(cls: type, raw: dict) -> object:
    """Recursively populate a dataclass *cls* from a raw dict.

    Unknown keys are silently ignored so that the config file can evolve
    without breaking older code.  Missing keys fall back to dataclass
    defaults.
    """
    kwargs: dict = {}
    for f in fields(cls):
        if f.name not in raw:
            continue
        value = raw[f.name]
        # Resolve the real type (annotations are strings with __future__)
        # and recurse into nested dataclasses.
        sub_cls = _resolve_type(cls, f)
        if hasattr(sub_cls, "__dataclass_fields__") and isinstance(value, dict):
            value = _populate_dataclass(sub_cls, value)
        kwargs[f.name] = value
    return cls(**kwargs)


def _resolve_type(owner_cls: type, f) -> type:
    """Resolve the real type of field *f* which may be a string annotation."""
    # With `from __future__ import annotations` all annotations are strings.
    annotation = f.type if isinstance(f.type, str) else f.type.__name__
    # Look up in the module globals where all dataclasses are defined.
    import sys
    mod = sys.modules[__name__]
    cls = getattr(mod, annotation, None)
    if cls is not None:
        return cls
    # Fallback: try to evaluate the annotation in the module namespace.
    try:
        return eval(annotation, vars(mod))  # noqa: S307
    except Exception:
        return type(None)


def _coerce_bool(value: str) -> bool:
    """Convert a string env-var value to bool."""
    return value.lower() in {"1", "true", "yes", "on"}


def _coerce_field_value(field_type_name: str, raw: str):
    """Coerce a string *raw* from an env var to the type described by
    *field_type_name* (the annotation string).
    """
    if field_type_name == "bool":
        return _coerce_bool(raw)
    if field_type_name == "int":
        return int(raw)
    if field_type_name == "float":
        return float(raw)
    # str, List[str], or anything else – return as-is.
    return raw


def _apply_env_overrides(cfg: AutodevConfig) -> None:
    """Override config values from ``AUTODEV_<SECTION>_<KEY>`` env vars.

    Only flat (non-dataclass) leaf fields are supported.  Nested sections
    like ``run.root_mode`` can be reached with
    ``AUTODEV_RUN_ROOT_MODE_<KEY>`` (triple-underscore form is *not*
    needed – we walk the tree).
    """
    prefix = "AUTODEV_"

    for section_field in fields(cfg):
        section_obj = getattr(cfg, section_field.name)
        if not hasattr(section_obj, "__dataclass_fields__"):
            continue
        _apply_env_to_section(
            prefix + section_field.name.upper() + "_",
            section_obj,
        )


def _apply_env_to_section(prefix: str, obj: object) -> None:
    """Recursively apply env-var overrides to *obj* (a dataclass instance)."""
    for f in fields(obj):  # type: ignore[arg-type]
        child = getattr(obj, f.name)
        env_key = prefix + f.name.upper()

        if hasattr(child, "__dataclass_fields__"):
            # Nested dataclass – recurse with extended prefix.
            _apply_env_to_section(env_key + "_", child)
            continue

        env_val = os.environ.get(env_key)
        if env_val is None:
            continue

        annotation = f.type if isinstance(f.type, str) else f.type.__name__
        coerced = _coerce_field_value(annotation, env_val)
        object.__setattr__(obj, f.name, coerced)
        log.debug("env override %s = %r", env_key, coerced)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Raised when the configuration is invalid."""


def _validate(cfg: AutodevConfig) -> None:
    """Validate enum fields and other constraints.  Raises ``ConfigError``."""
    errors: list[str] = []

    if cfg.backend.default not in _VALID_BACKENDS:
        errors.append(
            f"backend.default must be one of {sorted(_VALID_BACKENDS)}, "
            f"got {cfg.backend.default!r}"
        )

    if cfg.backend.claude.permission_mode not in _VALID_PERMISSION_MODES:
        errors.append(
            f"backend.claude.permission_mode must be one of "
            f"{sorted(_VALID_PERMISSION_MODES)}, "
            f"got {cfg.backend.claude.permission_mode!r}"
        )

    if cfg.backend.claude.output_format not in _VALID_OUTPUT_FORMATS:
        errors.append(
            f"backend.claude.output_format must be one of "
            f"{sorted(_VALID_OUTPUT_FORMATS)}, "
            f"got {cfg.backend.claude.output_format!r}"
        )

    if cfg.backend.gemini.output_format not in _VALID_GEMINI_OUTPUT_FORMATS:
        errors.append(
            f"backend.gemini.output_format must be one of "
            f"{sorted(_VALID_GEMINI_OUTPUT_FORMATS)}, "
            f"got {cfg.backend.gemini.output_format!r}"
        )

    if cfg.run.root_mode.fallback_permission_mode not in _VALID_PERMISSION_MODES:
        errors.append(
            f"run.root_mode.fallback_permission_mode must be one of "
            f"{sorted(_VALID_PERMISSION_MODES)}, "
            f"got {cfg.run.root_mode.fallback_permission_mode!r}"
        )

    if errors:
        raise ConfigError(
            "Invalid autodev configuration:\n  - " + "\n  - ".join(errors)
        )


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_paths(cfg: AutodevConfig, base: Path) -> None:
    """Resolve relative paths in *cfg* against *base* (the directory that
    contains the ``autodev.toml`` file).
    """
    cfg.project.code_dir = str(resolve_path(base, cfg.project.code_dir))
    cfg.project.config_dir = str(resolve_path(base, cfg.project.config_dir))

    cfg.files.task_json = str(resolve_path(base, cfg.files.task_json))
    cfg.files.progress = str(resolve_path(base, cfg.files.progress))
    cfg.files.execution_guide = str(resolve_path(base, cfg.files.execution_guide))
    cfg.files.task_brief = str(resolve_path(base, cfg.files.task_brief))
    cfg.files.log_dir = str(resolve_path(base, cfg.files.log_dir))
    attempt_log_subdir = Path(cfg.files.attempt_log_subdir)
    if attempt_log_subdir.is_absolute():
        cfg.files.attempt_log_subdir = str(attempt_log_subdir)
    else:
        cfg.files.attempt_log_subdir = str(
            resolve_path(Path(cfg.files.log_dir), cfg.files.attempt_log_subdir)
        )

    if cfg.prompt.template_file:
        cfg.prompt.template_file = str(
            resolve_path(base, cfg.prompt.template_file)
        )

    cfg.snapshot.watch_dirs = [
        str(resolve_path(Path(cfg.project.code_dir), watch_dir))
        for watch_dir in cfg.snapshot.watch_dirs
    ]


# ---------------------------------------------------------------------------
# Auto-adjustments
# ---------------------------------------------------------------------------

def _auto_adjust(cfg: AutodevConfig) -> None:
    """Apply derived / auto-set values."""
    # verbose is automatically enabled when output_format is stream-json.
    if cfg.backend.claude.output_format == "stream-json":
        cfg.backend.claude.verbose = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(path: Path) -> AutodevConfig:
    """Load, merge, validate and return an ``AutodevConfig`` from *path*.

    Parameters
    ----------
    path:
        Path to the ``autodev.toml`` file.

    Returns
    -------
    AutodevConfig
        Fully resolved and validated configuration.

    Raises
    ------
    ConfigError
        If validation fails.
    FileNotFoundError
        If *path* does not exist.
    """
    path = Path(path).resolve()
    base = path.parent

    with open(path, "rb") as fh:
        raw: dict = tomllib.load(fh)

    # Backward compatibility: older configs use [gate]. Prefer the new
    # verification terminology but continue accepting the legacy section.
    if "verification" not in raw and isinstance(raw.get("gate"), dict):
        raw["verification"] = raw["gate"]

    cfg: AutodevConfig = _populate_dataclass(AutodevConfig, raw)  # type: ignore[assignment]

    # Environment variable overrides (applied before validation so that env
    # vars can fix an otherwise-invalid file, and before path resolution so
    # that overridden paths are also resolved).
    _apply_env_overrides(cfg)

    # Auto-adjustments (e.g. verbose for stream-json).
    _auto_adjust(cfg)

    # Validation.
    _validate(cfg)

    # Resolve relative paths.
    _resolve_paths(cfg, base)

    return cfg
