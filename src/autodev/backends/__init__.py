"""Backend registry for AI coding agents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from autodev.backends.claude import build_claude_command, run_claude
from autodev.backends.codex import build_codex_command, run_codex
from autodev.backends.common import BackendResult, CommandSpec, execute_with_tee
from autodev.backends.gemini import build_gemini_command, run_gemini
from autodev.backends.opencode import build_opencode_command, run_opencode

if TYPE_CHECKING:
    from autodev.config import AutodevConfig


CommandBuilder = Callable[[str, "AutodevConfig"], CommandSpec]
BackendRunner = Callable[
    [str, "AutodevConfig", Path, Path, Path],
    BackendResult,
]


@dataclass(frozen=True)
class BackendAdapter:
    """Descriptor for one supported backend."""

    name: str
    cli_name: str
    build_run_command: CommandBuilder
    build_plan_command: CommandBuilder
    runner: BackendRunner


_BACKENDS: dict[str, BackendAdapter] = {
    "claude": BackendAdapter(
        name="claude",
        cli_name="claude",
        build_run_command=build_claude_command,
        build_plan_command=lambda prompt, config: build_claude_command(
            prompt, config, for_plan=True
        ),
        runner=run_claude,
    ),
    "codex": BackendAdapter(
        name="codex",
        cli_name="codex",
        build_run_command=build_codex_command,
        build_plan_command=lambda prompt, config: build_codex_command(
            prompt, config, for_plan=True
        ),
        runner=run_codex,
    ),
    "gemini": BackendAdapter(
        name="gemini",
        cli_name="gemini",
        build_run_command=build_gemini_command,
        build_plan_command=lambda prompt, config: build_gemini_command(
            prompt, config, for_plan=True
        ),
        runner=run_gemini,
    ),
    "opencode": BackendAdapter(
        name="opencode",
        cli_name="opencode",
        build_run_command=build_opencode_command,
        build_plan_command=lambda prompt, config: build_opencode_command(
            prompt, config, for_plan=True
        ),
        runner=run_opencode,
    ),
}


def get_backend(name: str) -> BackendAdapter:
    """Return the adapter for *name* or raise ``ValueError``."""
    try:
        return _BACKENDS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown backend: {name}") from exc


def get_backend_names() -> tuple[str, ...]:
    """Return all supported backend names in stable order."""
    return tuple(_BACKENDS)


def get_backend_cli_name(name: str) -> str:
    """Return the executable name used by the backend CLI."""
    return get_backend(name).cli_name


def build_backend_command(
    backend: str,
    prompt: str,
    config: AutodevConfig,
    *,
    for_plan: bool = False,
) -> CommandSpec:
    """Build the command for the selected backend."""
    adapter = get_backend(backend)
    if for_plan:
        return adapter.build_plan_command(prompt, config)
    return adapter.build_run_command(prompt, config)


def run_backend(
    backend: str,
    prompt: str,
    config: AutodevConfig,
    code_dir: Path,
    attempt_log: Path,
    main_log: Path,
) -> BackendResult:
    """Dispatch to the appropriate backend runner."""
    adapter = get_backend(backend)
    return adapter.runner(prompt, config, code_dir, attempt_log, main_log)
