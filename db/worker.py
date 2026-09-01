"""
Database worker thread.
"""

from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from admin_suite.db.backends import BACKENDS
from admin_suite.db.session import DbSessionManager
import time


def _is_transient_db_error(message: str) -> bool:
    msg = str(message).lower()

    return any(
        x in msg
        for x in (
            "2013",
            "2006",
            "lost connection",
            "gone away",
            "timed out",
            "connection reset",
            "broken pipe",
            "can't connect",
        )
    )


def _is_read_only_query(sql: str) -> bool:
    s = str(sql or "").strip().upper()

    return s.startswith(
        (
            "SELECT",
            "SHOW",
            "DESC",
            "DESCRIBE",
            "EXPLAIN",
        )
    )

class DbWorker(QThread):
    """
    Executes database metadata/query operations in a background thread.
    """

    schemas_loaded = pyqtSignal(list)
    tables_loaded = pyqtSignal(list)
    columns_loaded = pyqtSignal(list)
    data_loaded = pyqtSignal(list, list)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        session_manager: DbSessionManager,
        cfg: dict[str, Any],
        mode: str = "fetch_schemas",
        db_name: str = "",
        table_name: str = "",
        query: str = "",
        params: Optional[list[Any]] = None,
    ):
        super().__init__()

        self.session_manager = session_manager
        self.cfg = cfg

        self.mode = mode
        self.db_name = db_name
        self.table_name = table_name
        self.query = query
        self.params = params or []
        
    def run(self) -> None:
        backend = BACKENDS.get(self.cfg.get("backend", "mysql"))

        if not backend:
            self.error_occurred.emit(
                f"Backend '{self.cfg.get('backend')}' not available"
            )
            return

        read_only = (
            self.mode != "run_query"
            or _is_read_only_query(self.query)
        )

        max_attempts = 2 if read_only else 1

        last_error = None

        for attempt in range(1, max_attempts + 1):
            conn = None

            try:
                conn = self.session_manager.connect(self.cfg)

                with conn.cursor() as cur:
                    # Apply schema/database context where appropriate.
                    if self.db_name and backend.name == "mysql":
                        try:
                            safe_db = str(self.db_name).replace("`", "``")
                            cur.execute(f"USE `{safe_db}`")
                        except Exception:
                            pass

                    if self.db_name and backend.name == "postgresql":
                        try:
                            safe_schema = str(self.db_name).replace('"', '""')
                            cur.execute(f'SET search_path TO "{safe_schema}"')
                        except Exception:
                            pass

                    if self.mode == "fetch_schemas":
                        self.schemas_loaded.emit(backend.schemas(cur))
                        return

                    elif self.mode == "fetch_tables":
                        self.tables_loaded.emit(
                            backend.tables(cur, self.db_name)
                        )
                        return

                    elif self.mode == "fetch_columns":
                        self.columns_loaded.emit(
                            backend.columns(cur, self.db_name, self.table_name)
                        )
                        return

                    elif self.mode == "run_query":
                        headers, rows, _ = backend.run(
                            cur,
                            self.query,
                            self.params,
                        )

                        self.data_loaded.emit(headers, rows)
                        return

            except Exception as e:
                last_error = e

                if (
                    attempt < max_attempts
                    and read_only
                    and _is_transient_db_error(e)
                ):
                    time.sleep(1.0)
                    continue

                self.error_occurred.emit(str(e))
                return

            finally:
                try:
                    if conn:
                        conn.close()
                except Exception:
                    pass

        if last_error is not None:
            self.error_occurred.emit(str(last_error))