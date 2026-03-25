from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.log import Logger


class Heartbeat:
    """Background thread that logs periodic status during AI execution."""

    def __init__(
        self,
        logger: Logger,
        task_id: str,
        attempt: int,
        max_attempts: int,
        log_file: Path,
        interval: int = 20,
        on_heartbeat=None,
    ):
        self._logger = logger
        self._task_id = task_id
        self._attempt = attempt
        self._max_attempts = max_attempts
        self._log_file = log_file
        self._interval = interval
        self._on_heartbeat = on_heartbeat
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the heartbeat monitor."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the heartbeat monitor."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        """Main heartbeat loop."""
        last_size = 0
        start = time.monotonic()

        while not self._stop_event.wait(self._interval):
            elapsed = int(time.monotonic() - start)
            current_size = 0
            try:
                if self._log_file.exists():
                    current_size = self._log_file.stat().st_size
            except OSError:
                pass

            if current_size > last_size:
                message = (
                    f"Task {self._task_id} attempt {self._attempt}/{self._max_attempts} "
                    f"still running, {elapsed}s elapsed, log output updating"
                )
                self._logger.state("running", message)
                output_updating = True
            else:
                message = (
                    f"Task {self._task_id} attempt {self._attempt}/{self._max_attempts} "
                    f"still running, {elapsed}s elapsed, waiting for model output"
                )
                self._logger.state("waiting", message)
                output_updating = False
            if self._on_heartbeat is not None:
                try:
                    self._on_heartbeat(elapsed, output_updating)
                except Exception:
                    pass
            last_size = current_size
