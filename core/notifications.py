"""
Application notification hub.
"""

from __future__ import annotations

import datetime
import threading
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal


class NotificationHub(QObject):
    """
    Thread-safe notification store.

    UI toast/notification widgets should connect to pushed.
    """

    pushed = pyqtSignal(dict)

    def __init__(self, max_items: int = 200):
        super().__init__()

        self._items: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self.max_items = max_items

    @property
    def items(self) -> list[dict[str, Any]]:
        """
        Return a snapshot of current notifications.
        """
        with self._lock:
            return list(self._items)

    def push(self, level: str, title: str, message: str) -> None:
        """
        Push a notification.

        level should be one of:
        - ok
        - warn
        - error
        - info
        """
        item = {
            "ts": datetime.datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "title": title,
            "msg": message,
        }

        with self._lock:
            self._items.insert(0, item)
            self._items = self._items[: self.max_items]

        self.pushed.emit(item)

    def clear(self) -> None:
        """
        Clear all notifications.
        """
        with self._lock:
            self._items.clear()
