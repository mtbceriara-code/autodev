"""Circuit breaker for the retry loop.

Tracks three failure signals and decides whether to continue retrying,
pause (rate limit), or trip (give up early). Inspired by Ralph's
circuit breaker but simplified to per-task scope with no persistence.

States:
    CLOSED  — normal operation, attempts proceed
    OPEN    — tripped, skip remaining retries immediately
    PAUSED  — rate limit detected, sleep then retry
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.config import CircuitBreakerConfig
    from autodev.log import Logger


class CircuitBreaker:
    """Per-task circuit breaker for the retry loop."""

    def __init__(self, config: CircuitBreakerConfig, logger: Logger) -> None:
        self._config = config
        self._logger = logger
        self._no_progress_count: int = 0
        self._last_exit_code: int | None = None
        self._repeated_error_count: int = 0
        self._tripped: bool = False
        self._trip_reason: str = ""

    @property
    def is_tripped(self) -> bool:
        return self._tripped

    @property
    def trip_reason(self) -> str:
        return self._trip_reason

    def record_attempt(
        self,
        exit_code: int,
        changed_files_count: int,
        attempt_log: Path,
        *,
        allow_rate_limit_pause: bool = True,
    ) -> None:
        """Feed the result of one backend attempt into the circuit breaker.

        Must be called after each attempt, before ``should_continue()``.
        If a rate limit is detected, this method **blocks** for the
        configured cooldown period before returning.
        """
        # --- Rate limit detection (check first, may pause & clear) ----------
        # Only check for rate limits on failed backend attempts when the
        # caller confirms the failure came from backend execution rather than
        # downstream verification. A successful backend run (exit_code == 0)
        # cannot be rate-limited, and verification failures may still leave
        # stream-json metadata words like "capacity" or "usage" in the log.
        if allow_rate_limit_pause and exit_code != 0 and self._check_rate_limit(attempt_log):
            cooldown = self._config.rate_limit_cooldown
            self._logger.warning(
                f"Rate limit detected — pausing {cooldown}s before next attempt"
            )
            time.sleep(cooldown)
            # Don't count this as a real failure
            return

        # --- No progress tracking -------------------------------------------
        if exit_code == 0 and changed_files_count == 0:
            # Backend "succeeded" but changed nothing — suspicious
            self._no_progress_count += 1
        elif changed_files_count == 0 and exit_code != 0:
            self._no_progress_count += 1
        else:
            self._no_progress_count = 0

        if self._no_progress_count >= self._config.no_progress_threshold:
            self._trip(
                f"No file changes in {self._no_progress_count} consecutive attempts"
            )
            return

        # --- Repeated identical errors --------------------------------------
        if exit_code != 0:
            if exit_code == self._last_exit_code:
                self._repeated_error_count += 1
            else:
                self._repeated_error_count = 1
            self._last_exit_code = exit_code
        else:
            self._repeated_error_count = 0
            self._last_exit_code = None

        if self._repeated_error_count >= self._config.repeated_error_threshold:
            self._trip(
                f"Same error (exit={self._last_exit_code}) repeated "
                f"{self._repeated_error_count} times"
            )

    def _trip(self, reason: str) -> None:
        self._tripped = True
        self._trip_reason = reason
        self._logger.warning(f"Circuit breaker tripped: {reason}")

    def _check_rate_limit(self, attempt_log: Path) -> bool:
        """Check if the attempt log contains rate-limit indicators."""
        patterns = self._config.rate_limit_patterns
        if not patterns:
            return False
        try:
            content = attempt_log.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            return False
        return any(p.lower() in content for p in patterns)
