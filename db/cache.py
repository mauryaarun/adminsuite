"""
Schema metadata cache.
"""

from __future__ import annotations

import time
from typing import Any, Hashable, Optional


class SchemaCache:
    """
    TTL cache for schema/table/column metadata.
    """

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._data: dict[Hashable, Any] = {}
        self._ts: dict[Hashable, float] = {}

    def get(self, key: Hashable) -> Optional[Any]:
        ts = self._ts.get(key)

        if ts is None:
            return None

        if time.time() - ts > self.ttl:
            return None

        return self._data.get(key)

    def set(self, key: Hashable, value: Any) -> None:
        self._data[key] = value
        self._ts[key] = time.time()

    def invalidate(self, key: Optional[Hashable] = None) -> None:
        if key is None:
            self._data.clear()
            self._ts.clear()
        else:
            self._data.pop(key, None)
            self._ts.pop(key, None)
