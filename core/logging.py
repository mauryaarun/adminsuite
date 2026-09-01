"""
Debug/log pipeline.
"""

from __future__ import annotations

import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from admin_suite.core.utils import sanitize_for_log


class DebugPipeline(QObject):
    """
    Qt signal-based debug pipeline.

    UI widgets can connect to log_emitted to display log lines.
    """

    log_emitted = pyqtSignal(str)

    def emit(self, source: str, message: str) -> None:
        """
        Emit sanitized log line.
        """
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{source.upper()}] {message}"
        line = sanitize_for_log(line)

        self.log_emitted.emit(line)

    # Compatibility alias.
    def emit_log(self, source: str, message: str) -> None:
        self.emit(source, message)
