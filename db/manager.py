"""
Database manager widget.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from admin_suite.core.paths import (
    QUERY_FAVORITES_FILE,
    QUERY_HISTORY_FILE,
)

from admin_suite.core.utils import (
    read_json,
    write_json_secure,
)

from admin_suite.db.backends import BACKENDS

from admin_suite.db.cache import SchemaCache
from admin_suite.db.completer import SqlCompleter
from admin_suite.db.export import (
    export_database,
    export_result_csv,
    export_result_json,
    export_table_sql,
)
from admin_suite.db.highlighter import SQLHighlighter, SQL_KEYWORDS
from admin_suite.db.models import SqlResultModel
from admin_suite.db.quoting import qident
from admin_suite.db.session import DbSessionManager
from admin_suite.db.table_detail import TableDetailTab
from admin_suite.db.worker import DbWorker


class DatabaseManagerWidget(QWidget):
    """
    Main database manager UI.
    """

    def __init__(self, services, parent=None):
        super().__init__(parent)

        self.services = services
        self.main_window = parent

        self.session_manager = DbSessionManager()

        self.active_db_profile: Optional[dict[str, Any]] = None

        self.current_schema: Optional[str] = None
        self.current_table: Optional[str] = None

        self.schema_cache = SchemaCache(
            ttl_seconds=int(
                self.services.config.get("db_schema_cache_ttl", 300)
            )
        )

        self.query_history = read_json(QUERY_HISTORY_FILE, [])
        self.query_favs = read_json(QUERY_FAVORITES_FILE, [])

        self._known_words = list(SQL_KEYWORDS)
        self._workers = []

        self._last_headers: list[str] = []
        self._last_rows: list[list[Any]] = []

        theme = self.services.theme.current

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(6, 6, 6, 6)

        self.connect_btn = QPushButton("🔌 Connect Database")
        self.connect_btn.clicked.connect(self.load_schemas)

        self.test_btn = QPushButton("🔌 Test Only")
        self.test_btn.clicked.connect(self.test_connection)

        self.export_csv_btn = QPushButton("📤 CSV")
        self.export_csv_btn.clicked.connect(lambda: self.export_result("csv"))

        self.export_json_btn = QPushButton("📤 JSON")
        self.export_json_btn.clicked.connect(lambda: self.export_result("json"))

        self.hist_btn = QPushButton("🕒 History")
        self.hist_btn.clicked.connect(self.show_history)

        self.fav_btn = QPushButton("⭐ Favorites")
        self.fav_btn.clicked.connect(self.show_favorites)

        self.conn_status = QLabel("● Idle")
        self.conn_status.setStyleSheet(
            f"color:{theme['sub']};font-weight:bold;padding:0 8px;"
        )

        for button in (
            self.connect_btn,
            self.test_btn,
            self.export_csv_btn,
            self.export_json_btn,
            self.hist_btn,
            self.fav_btn,
        ):
            toolbar.addWidget(button)

        toolbar.addStretch()
        toolbar.addWidget(self.conn_status)

        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemExpanded.connect(self.on_tree_expanded)
        self.tree.itemDoubleClicked.connect(self.on_tree_dbl_click)

        self.tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.tree.customContextMenuRequested.connect(self.show_tree_menu)

        splitter.addWidget(self.tree)

        right = QSplitter(Qt.Orientation.Vertical)

        query_widget = QWidget()
        query_layout = QVBoxLayout(query_widget)
        query_layout.setContentsMargins(0, 0, 0, 0)

        query_buttons = QHBoxLayout()

        self.exec_btn = QPushButton("▶ Execute (F5)")
        self.exec_btn.setStyleSheet(
            f"background:{theme['accent']};color:white;font-weight:bold;"
        )
        self.exec_btn.clicked.connect(self.execute_query)

        explain_btn = QPushButton("📊 EXPLAIN")
        explain_btn.clicked.connect(self.explain_query)

        star_btn = QPushButton("⭐ Save Favorite")
        star_btn.clicked.connect(self.save_favorite)

        clear_btn = QPushButton("🧹 Clear")
        clear_btn.clicked.connect(lambda: self.query_edit.clear())

        query_buttons.addStretch()
        query_buttons.addWidget(explain_btn)
        query_buttons.addWidget(star_btn)
        query_buttons.addWidget(clear_btn)
        query_buttons.addWidget(self.exec_btn)

        query_layout.addLayout(query_buttons)

        self.query_edit = QTextEdit()
        self.query_edit.setFont(QFont("JetBrains Mono, Consolas", 11))

        self.query_edit.setPlaceholderText(
            "-- Write SQL here. F5 executes.\n"
            "-- Right-click schema objects for quick queries."
        )

        self._highlighter = SQLHighlighter(self.query_edit.document())
        self._completer = SqlCompleter(self.query_edit)

        self.query_edit.textChanged.connect(self._completer.maybe_complete)

        query_layout.addWidget(self.query_edit)

        right.addWidget(query_widget)

        self.results_table = None
        self.result_model = SqlResultModel()

        from PyQt6.QtWidgets import QTableView

        self.results_table = QTableView()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setModel(self.result_model)

        right.addWidget(self.results_table)

        self.row_count_label = QLabel("")
        self.row_count_label.setStyleSheet(
            f"color:{theme['sub']};padding:4px;"
        )

        right.addWidget(self.row_count_label)

        right.setSizes([220, 420, 24])

        splitter.addWidget(right)
        splitter.setSizes([260, 900])

        layout.addWidget(splitter, 1)

        QShortcut(QKeySequence("F5"), self).activated.connect(
            self.execute_query
        )

    # ------------------------------------------------------------
    # Config/profile helpers
    # ------------------------------------------------------------

    def _backend_name(self) -> str:
        return self._build_cfg().get("backend", "mysql")

    def _qident(self, ident: str) -> str:
        return qident(ident, self._backend_name())

    def set_active_profile(self, profile: Optional[dict[str, Any]]) -> None:
        self.active_db_profile = profile

        if profile:
            self.conn_status.setText(
                f"● Profile: {profile.get('name', 'custom')}"
            )

    def _build_cfg(self) -> dict[str, Any]:
        if self.active_db_profile:
            cfg = dict(self.active_db_profile)

            cfg.setdefault(
                "use_tunnel",
                self.active_db_profile.get("use_tunnel", False),
            )

            return cfg

        return {
            "backend": self.services.config.get("db_backend", "mysql"),
            "ssh_host": self.services.config.get("ssh_host", ""),
            "ssh_user": self.services.config.get("ssh_user", ""),
            "ssh_port": self.services.config.get("ssh_port", "22"),
            "ssh_pass": self.services.secrets.get("ssh_pass", ""),
            "ssh_key_path": "",
            "db_host": self.services.config.get("db_host", "127.0.0.1"),
            "db_port": self.services.config.get("db_port", "3306"),
            "db_user": self.services.config.get("db_user", ""),
            "db_pass": self.services.secrets.get("db_pass", ""),
            "db_name": self.services.config.get("db_name", ""),
            "sqlite_path": self.services.config.get("sqlite_path", ""),
            "use_tunnel": self.services.config.get("db_use_tunnel", True),
        }

    # ------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------

    def _start_worker(self, worker: DbWorker) -> None:
        worker.error_occurred.connect(self.on_db_error)
        worker.start()

        self._workers = [
            w for w in self._workers if w.isRunning()
        ] + [worker]

    # ------------------------------------------------------------
    # Schema tree
    # ------------------------------------------------------------

    def test_connection(self) -> None:
        self.conn_status.setText("● Testing...")

        worker = DbWorker(
            self.session_manager,
            self._build_cfg(),
            mode="fetch_schemas",
        )

        worker.schemas_loaded.connect(
            lambda schemas: (
                self.conn_status.setText("● Reachable ✅"),
                self.services.notifications.push(
                    "ok",
                    "Database",
                    "Connection OK",
                ),
            )
        )

        self._start_worker(worker)

    def load_schemas(self) -> None:
        self.conn_status.setText("● Loading...")

        self.schema_cache.invalidate()

        self.tree.clear()
        self.tree.addTopLevelItem(QTreeWidgetItem(["Loading schemas..."]))

        worker = DbWorker(
            self.session_manager,
            self._build_cfg(),
            mode="fetch_schemas",
        )

        worker.schemas_loaded.connect(self.populate_schemas)

        self._start_worker(worker)

    def populate_schemas(self, schemas: list[str]) -> None:
        self.tree.clear()

        skip = ["information_schema", "performance_schema", "sys"]

        backend = self._backend_name()

        for db in schemas:
            if backend == "mysql" and db in skip:
                continue

            item = QTreeWidgetItem([f"🗄 {db}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ("schema", db))
            item.addChild(QTreeWidgetItem(["Loading..."]))

            self.tree.addTopLevelItem(item)

        self.conn_status.setText(f"● Connected ({backend}) ✅")

        self.services.notifications.push(
            "ok",
            "Database",
            f"{len(schemas)} schema(s) loaded",
        )

    def on_tree_expanded(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if not data:
            return

        if data[0] == "schema":
            db_name = data[1]

            cache_key = ("tables", db_name)
            cached = self.schema_cache.get(cache_key)

            if cached is not None:
                item.takeChildren()
                self.populate_tables(item, cached, db_name)
                return

            item.takeChildren()

            worker = DbWorker(
                self.session_manager,
                self._build_cfg(),
                mode="fetch_tables",
                db_name=db_name,
            )

            def tables_loaded(tables, it=item, db=db_name):
                self.schema_cache.set(("tables", db), tables)
                self.populate_tables(it, tables, db)

            worker.tables_loaded.connect(tables_loaded)

            self._start_worker(worker)

        elif data[0] == "table":
            db_name = data[1]
            table_name = data[2]

            cache_key = ("columns", db_name, table_name)
            cached = self.schema_cache.get(cache_key)

            if cached is not None:
                item.takeChildren()
                self.populate_columns(item, cached)
                return

            item.takeChildren()

            worker = DbWorker(
                self.session_manager,
                self._build_cfg(),
                mode="fetch_columns",
                db_name=db_name,
                table_name=table_name,
            )

            def columns_loaded(cols, it=item, db=db_name, table=table_name):
                self.schema_cache.set(("columns", db, table), cols)
                self.populate_columns(it, cols)

            worker.columns_loaded.connect(columns_loaded)

            self._start_worker(worker)

    def populate_tables(
        self,
        parent_item: QTreeWidgetItem,
        tables: list[str],
        db_name: str,
    ) -> None:
        self._known_words += tables
        self._completer.set_words(self._known_words)

        for table in tables:
            item = QTreeWidgetItem([f"📋 {table}"])
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                ("table", db_name, table),
            )
            item.addChild(QTreeWidgetItem(["Loading..."]))

            parent_item.addChild(item)

    def populate_columns(
        self,
        parent_item: QTreeWidgetItem,
        columns: list[dict],
    ) -> None:
        for col in columns:
            field = col.get("Field", "")

            self._known_words.append(field)

            parent_item.addChild(
                QTreeWidgetItem(
                    [
                        f"🔢 {field} ({col.get('Type', '')})"
                    ]
                )
            )

        self._completer.set_words(self._known_words)

    def on_tree_dbl_click(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if not data:
            return

        if data[0] == "table":
            self.current_schema = data[1]
            self.current_table = data[2]

            self._open_table_detail(data[1], data[2])

        elif data[0] == "schema":
            self.current_schema = data[1]
            self.current_table = None

            quoted = self._qident(data[1])

            self.query_edit.setPlainText(
                f"SELECT * FROM {quoted}.<table> LIMIT 100;"
            )

    def show_tree_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        menu = QMenu(self)

        if not item or not item.data(0, Qt.ItemDataRole.UserRole):
            menu.addAction("🔄 Refresh All").triggered.connect(
                self.load_schemas
            )

            menu.addSeparator()

            menu.addAction("🆕 Create Database").triggered.connect(
                self.create_database_dialog
            )

            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)

        backend = self._backend_name()

        if data[0] == "schema":
            db = data[1]

            self.current_schema = db
            self.current_table = None

            menu.addAction("📋 Copy Name").triggered.connect(
                lambda: QApplication.clipboard().setText(db)
            )

            menu.addSeparator()

            menu.addAction("📤 Export Database (SQL Dump)").triggered.connect(
                lambda: self.export_database(db)
            )

            menu.addSeparator()

            menu.addAction("🆕 Create Table in this DB").triggered.connect(
                lambda: self.create_table_dialog(db)
            )

            if backend == "mysql":
                menu.addAction("🗑 DROP Database").triggered.connect(
                    lambda: self._confirm(
                        f"DROP DATABASE {self._qident(db)};",
                        f"Drop database '{db}'?",
                    )
                )

        elif data[0] == "table":
            db = data[1]
            table = data[2]

            self.current_schema = db
            self.current_table = table

            fqn = f"{self._qident(db)}.{self._qident(table)}"

            menu.addAction("▶ Open Table").triggered.connect(
                lambda: self._open_table_detail(db, table)
            )

            menu.addAction("▶ SELECT * (100 rows)").triggered.connect(
                lambda: (
                    self.query_edit.setPlainText(
                        f"SELECT * FROM {fqn} LIMIT 100;"
                    ),
                    self.execute_query(),
                )
            )

            menu.addAction("🔢 COUNT(*)").triggered.connect(
                lambda: (
                    self.query_edit.setPlainText(
                        f"SELECT COUNT(*) AS total FROM {fqn};"
                    ),
                    self.execute_query(),
                )
            )

            menu.addAction("📊 EXPLAIN SELECT").triggered.connect(
                lambda: (
                    self.query_edit.setPlainText(
                        f"EXPLAIN SELECT * FROM {fqn} LIMIT 10;"
                    ),
                    self.execute_query(),
                )
            )

            menu.addSeparator()

            menu.addAction("📤 Export Table (CSV)").triggered.connect(
                lambda: self.export_table_csv(db, table)
            )

            menu.addAction("📤 Export Table (SQL INSERT)").triggered.connect(
                lambda: self.export_table_sql(db, table)
            )

            menu.addSeparator()

            menu.addAction("⚠ TRUNCATE").triggered.connect(
                lambda: self._confirm(
                    f"TRUNCATE TABLE {fqn};",
                    f"Truncate {table}?",
                )
            )

            menu.addAction("🗑 DROP").triggered.connect(
                lambda: self._confirm(
                    f"DROP TABLE {fqn};",
                    f"Drop {table}?",
                )
            )

            menu.addSeparator()

            menu.addAction("📋 Copy Name").triggered.connect(
                lambda: QApplication.clipboard().setText(fqn)
            )

        menu.addSeparator()

        menu.addAction("🔄 Refresh All").triggered.connect(self.load_schemas)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------

    def explain_query(self) -> None:
        query = self.query_edit.toPlainText().strip()

        if query and not query.upper().startswith("EXPLAIN"):
            self.query_edit.setPlainText("EXPLAIN " + query)

    def execute_query(self) -> None:
        query = self.query_edit.toPlainText().strip()

        if not query:
            return

        self.query_history = [
            x for x in self.query_history if x != query
        ]

        self.query_history.insert(0, query)
        self.query_history = self.query_history[:100]

        write_json_secure(QUERY_HISTORY_FILE, self.query_history)

        self.exec_btn.setEnabled(False)
        self.row_count_label.setText("Executing...")

        started_at = time.perf_counter()

        worker = DbWorker(
            self.session_manager,
            self._build_cfg(),
            mode="run_query",
            query=query,
            db_name=self.current_schema or "",
        )

        worker.data_loaded.connect(
            lambda headers, rows: self.display_data(
                headers,
                rows,
                time.perf_counter() - started_at,
            )
        )

        worker.finished.connect(lambda: self.exec_btn.setEnabled(True))

        self._start_worker(worker)

    def display_data(
        self,
        headers: list[str],
        rows: list[list[Any]],
        elapsed: float = 0.0,
    ) -> None:
        self._last_headers = headers or []
        self._last_rows = rows or []

        if not headers:
            self.result_model.clear()

            self.row_count_label.setText(
                f"Query OK ({elapsed * 1000:.0f} ms) — no result set."
            )

            self.services.notifications.push(
                "ok",
                "Query",
                f"Executed in {elapsed * 1000:.0f} ms",
            )

            return

        self.result_model.set_result(headers, rows)

        self.results_table.resizeColumnsToContents()

        self.row_count_label.setText(
            f"{len(rows)} row(s), {len(headers)} column(s) — "
            f"{elapsed * 1000:.0f} ms"
        )

    # ------------------------------------------------------------
    # Export
    # ------------------------------------------------------------

    def export_result(self, fmt: str) -> None:
        if not self._last_headers or not self._last_rows:
            QMessageBox.information(
                self,
                "Export",
                "No data. Run a SELECT first.",
            )
            return

        if fmt == "csv":
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export CSV",
                "results.csv",
                "CSV Files (*.csv)",
            )

            if not path:
                return

            export_result_csv(path, self._last_headers, self._last_rows)

        else:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export JSON",
                "results.json",
                "JSON Files (*.json)",
            )

            if not path:
                return

            export_result_json(path, self._last_headers, self._last_rows)

        self.services.notifications.push(
            "ok",
            "Export",
            f"{len(self._last_rows)} rows → {path}",
        )

    def export_table_csv(self, db_name: str, table_name: str) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Table CSV",
            f"{table_name}.csv",
            "CSV (*.csv)",
        )

        if not path:
            return

        fqn = f"{self._qident(db_name)}.{self._qident(table_name)}"

        worker = DbWorker(
            self.session_manager,
            self._build_cfg(),
            mode="run_query",
            query=f"SELECT * FROM {fqn} LIMIT 10000;",
            db_name=db_name,
        )

        def save(headers, rows):
            try:
                export_result_csv(path, headers, rows)

                self.services.notifications.push(
                    "ok",
                    "Export",
                    f"{len(rows)} rows → {path}",
                )

            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

        worker.data_loaded.connect(save)
        worker.error_occurred.connect(self.on_db_error)

        worker.start()

        self._workers.append(worker)

    def export_table_sql(self, db_name: str, table_name: str) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Table SQL",
            f"{table_name}_data.sql",
            "SQL Files (*.sql)",
        )

        if not path:
            return

        backend = self._backend_name()

        fqn = f"{self._qident(db_name)}.{self._qident(table_name)}"

        worker = DbWorker(
            self.session_manager,
            self._build_cfg(),
            mode="run_query",
            query=f"SELECT * FROM {fqn} LIMIT 10000;",
            db_name=db_name,
        )

        def save(headers, rows):
            try:
                export_table_sql(
                    path,
                    fqn,
                    headers,
                    rows,
                    backend,
                    self._qident,
                )

                self.services.notifications.push(
                    "ok",
                    "Export",
                    f"{len(rows)} INSERT statements → {path}",
                )

            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

        worker.data_loaded.connect(save)
        worker.error_occurred.connect(self.on_db_error)

        worker.start()

        self._workers.append(worker)

    def export_database(self, db_name: str) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Database",
            f"{db_name}_dump.sql",
            "SQL Files (*.sql)",
        )

        if not path:
            return

        try:
            export_database(
                self._build_cfg(),
                db_name,
                path,
            )

            self.services.notifications.push(
                "ok",
                "Export",
                f"Database '{db_name}' exported to {path}",
            )

        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # ------------------------------------------------------------
    # Create DB/table
    # ------------------------------------------------------------

    def create_database_dialog(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            "Create Database",
            "Database name:",
        )

        if not ok or not name:
            return

        backend = self._backend_name()

        quoted = self._qident(name)

        if backend == "mysql":
            sql = (
                f"CREATE DATABASE {quoted} "
                "CHARACTER SET utf8mb4 "
                "COLLATE utf8mb4_unicode_ci;"
            )
        else:
            sql = f"CREATE DATABASE {quoted};"

        if QMessageBox.question(
            self,
            "Create Database",
            f"Execute:\n{sql}",
        ) == QMessageBox.StandardButton.Yes:
            self.query_edit.setPlainText(sql)
            self.execute_query()

    def create_table_dialog(self, db_name: str) -> None:
        from admin_suite.db.dialogs import CreateTableDialog

        dlg = CreateTableDialog(
            self,
            db_name,
            self._backend_name(),
        )

        if dlg.exec() == QDialog.DialogCode.Accepted:
            sql = dlg.get_sql()

            if sql:
                self.query_edit.setPlainText(sql)
                self.execute_query()

    def _confirm(self, sql: str, message: str) -> None:
        if QMessageBox.question(
            self,
            "Confirm destructive operation",
            message + "\nThis cannot be undone. Execute?",
        ) == QMessageBox.StandardButton.Yes:
            self.query_edit.setPlainText(sql)
            self.execute_query()

    # ------------------------------------------------------------
    # Table detail
    # ------------------------------------------------------------

    def _open_table_detail(self, db_name: str, table_name: str) -> None:
        main_window = self.main_window

        if main_window and hasattr(main_window, "tabs"):
            title = f"📋 {db_name}.{table_name}"

            for i in range(main_window.tabs.count()):
                if main_window.tabs.tabText(i) == title:
                    main_window.tabs.setCurrentIndex(i)
                    return

            detail = TableDetailTab(
                self.services,
                self.session_manager,
                self._build_cfg(),
                db_name,
                table_name,
                main_window,
            )

            idx = main_window.tabs.addTab(detail, title)
            main_window.tabs.setCurrentIndex(idx)

    # ------------------------------------------------------------
    # History/favorites
    # ------------------------------------------------------------

    def show_history(self) -> None:
        from PyQt6.QtWidgets import QListWidget

        dlg = QDialog(self)
        dlg.setWindowTitle("Query History")
        dlg.resize(640, 420)

        layout = QVBoxLayout(dlg)

        lw = QListWidget()
        lw.setFont(QFont("JetBrains Mono, Consolas", 10))

        for query in self.query_history:
            lw.addItem(query)

        layout.addWidget(lw)

        row = QHBoxLayout()

        use = QPushButton("Use Query")

        use.clicked.connect(
            lambda: (
                self.query_edit.setPlainText(
                    lw.currentItem().text()
                )
                if lw.currentItem()
                else None,
                dlg.accept(),
            )
        )

        clear = QPushButton("Clear History")

        clear.clicked.connect(
            lambda: (
                self.query_history.clear(),
                lw.clear(),
            )
        )

        close = QPushButton("Close")
        close.clicked.connect(dlg.reject)

        row.addWidget(use)
        row.addWidget(clear)
        row.addStretch()
        row.addWidget(close)

        layout.addLayout(row)

        lw.itemDoubleClicked.connect(
            lambda item: (
                self.query_edit.setPlainText(item.text()),
                dlg.accept(),
            )
        )

        dlg.exec()

    def save_favorite(self) -> None:
        query = self.query_edit.toPlainText().strip()

        if not query:
            return

        name, ok = QInputDialog.getText(self, "Favorite", "Name:")

        if ok and name:
            self.query_favs.insert(0, {"name": name, "sql": query})

            write_json_secure(
                QUERY_FAVORITES_FILE,
                self.query_favs[:100],
            )

            self.services.notifications.push(
                "ok",
                "Favorite saved",
                name,
            )

    def show_favorites(self) -> None:
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem

        dlg = QDialog(self)
        dlg.setWindowTitle("Query Favorites")
        dlg.resize(640, 420)

        layout = QVBoxLayout(dlg)

        lw = QListWidget()

        for fav in self.query_favs:
            item = QListWidgetItem(f"⭐ {fav['name']}")
            item.setData(Qt.ItemDataRole.UserRole, fav)
            lw.addItem(item)

        layout.addWidget(lw)

        row = QHBoxLayout()

        load_btn = QPushButton("Load")

        load_btn.clicked.connect(
            lambda: (
                self.query_edit.setPlainText(
                    lw.currentItem().data(Qt.ItemDataRole.UserRole)["sql"]
                )
                if lw.currentItem()
                else None,
                dlg.accept(),
            )
        )

        delete_btn = QPushButton("Delete")

        def delete_favorite():
            item = lw.currentItem()

            if item:
                fav = item.data(Qt.ItemDataRole.UserRole)

                if fav in self.query_favs:
                    self.query_favs.remove(fav)

                write_json_secure(
                    QUERY_FAVORITES_FILE,
                    self.query_favs,
                )

                lw.takeItem(lw.row(item))

        delete_btn.clicked.connect(delete_favorite)

        close = QPushButton("Close")
        close.clicked.connect(dlg.reject)

        row.addWidget(load_btn)
        row.addWidget(delete_btn)
        row.addStretch()
        row.addWidget(close)

        layout.addLayout(row)

        lw.itemDoubleClicked.connect(
            lambda item: (
                self.query_edit.setPlainText(
                    item.data(Qt.ItemDataRole.UserRole)["sql"]
                ),
                dlg.accept(),
            )
        )

        dlg.exec()

    # ------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------

    def on_db_error(self, err: str) -> None:
        self.row_count_label.setText(f"Error: {err}")
        self.conn_status.setText("● Error ❌")

        self.services.notifications.push(
            "error",
            "Database",
            str(err)[:200],
        )

        QMessageBox.critical(self, "Database Error", str(err))
