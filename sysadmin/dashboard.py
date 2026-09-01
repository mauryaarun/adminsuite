from __future__ import annotations

import shlex
from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from admin_suite.ssh.remote_exec import RemoteExecThread
from admin_suite.sysadmin.commands import SYSADMIN_CMDS, SYSADMIN_SECTIONS

class SysAdminTab(QWidget):
 
	
    def __init__(
        self,
        services,
        profile_name: str,
        profile: Optional[dict[str, Any]],
        parent=None,
    ):
        super().__init__(parent)

        self.services = services
        self.profile_name = profile_name or "Local"
        self.profile = profile

        self._worker: Optional[RemoteExecThread] = None

        theme = self.services.theme.current

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        left = QVBoxLayout()

        header = QLabel(f"🖥 {self.profile_name}")
        header.setStyleSheet(
            f"color:{theme['accent']};font-weight:bold;font-size:14px;padding:4px;"
        )

        left.addWidget(header)

        self.nav = QListWidget()
        self.nav.setFixedWidth(160)

        for section in SYSADMIN_SECTIONS:
            self.nav.addItem(section)

        self.nav.currentTextChanged.connect(self.load_section)

        left.addWidget(self.nav)

        self.sudo_chk = QCheckBox("Use sudo")

        left.addWidget(self.sudo_chk)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_current)

        left.addWidget(refresh_btn)

        left.addStretch()

        layout.addLayout(left)

        right = QVBoxLayout()

        self.action_bar = QHBoxLayout()

        right.addLayout(self.action_bar)

        self.stack = QStackedWidget()

        self.text_views = {}
        self.table_views = {}

        for section in SYSADMIN_SECTIONS:
            if section in ("Users", "Services", "Processes"):
                table = QTableView()
                table.setAlternatingRowColors(True)

                model = QStandardItemModel()
                table.setModel(model)

                self.table_views[section] = table
                self.stack.addWidget(table)

            else:
                text = QPlainTextEdit()
                text.setReadOnly(True)
                text.setFont(QFont("JetBrains Mono, Consolas", 11))
                text.setLineWrapMode(
                    QPlainTextEdit.LineWrapMode.NoWrap
                )

                self.text_views[section] = text
                self.stack.addWidget(text)

        right.addWidget(self.stack, 1)

        self.status = QLabel("Select a section")
        self.status.setStyleSheet(f"color:{theme['sub']};")

        right.addWidget(self.status)

        layout.addLayout(right, 1)

        self.nav.setCurrentRow(0)

    # ------------------------------------------------------------
    # Section loading
    # ------------------------------------------------------------

    def _refresh_current(self) -> None:
        item = self.nav.currentItem()

        if item:
            self.load_section(item.text())

    def _clear_actions(self) -> None:
        while self.action_bar.count():
            item = self.action_bar.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

    def load_section(self, name: str) -> None:
        if not name:
            return

        index = SYSADMIN_SECTIONS.index(name)

        self.stack.setCurrentIndex(index)

        self._clear_actions()

        if name == "Services":
            for op in ("start", "stop", "restart", "enable", "disable"):
                button = QPushButton(op.capitalize())
                button.clicked.connect(
                    lambda checked, o=op: self.service_op(o)
                )

                self.action_bar.addWidget(button)

            self.action_bar.addStretch()

        cmd = SYSADMIN_CMDS[name]

        self.status.setText(f"Loading {name}...")

        self._worker = RemoteExecThread(
            self.profile,
            cmd,
            timeout=45,
        )

        self._worker.finished_cmd.connect(
            lambda out, rc, n=name: self._render(n, out, rc)
        )

        self._worker.start()

    # ------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------

    def _render(self, name: str, out: str, rc: int) -> None:
        self.status.setText(f"{name} — exit {rc}")

        if name == "Users":
            self._render_users(out)

        elif name == "Services":
            self._render_services(out)

        elif name == "Processes":
            self._render_processes(out)

        else:
            self.text_views[name].setPlainText(out)

    def _render_users(self, out: str) -> None:
        model = self.table_views["Users"].model()

        model.clear()

        model.setHorizontalHeaderLabels(
            ["User", "UID", "GID", "GECOS", "Home", "Shell"]
        )

        for line in out.splitlines():
            parts = line.split(":")

            if len(parts) >= 7:
                model.appendRow(
                    [
                        QStandardItem(x)
                        for x in (
                            parts[0],
                            parts[2],
                            parts[3],
                            parts[4],
                            parts[5],
                            parts[6],
                        )
                    ]
                )

        self.table_views["Users"].resizeColumnsToContents()

    def _render_services(self, out: str) -> None:
        model = self.table_views["Services"].model()

        model.clear()

        model.setHorizontalHeaderLabels(
            ["Unit", "Load", "Active", "Sub", "Description"]
        )

        theme = self.services.theme.current

        for line in out.splitlines():
            parts = line.split(None, 4)

            if len(parts) >= 4 and parts[0].endswith(".service"):
                desc = parts[4] if len(parts) > 4 else ""

                row = [
                    QStandardItem(x)
                    for x in (
                        parts[0],
                        parts[1],
                        parts[2],
                        parts[3],
                        desc,
                    )
                ]

                if parts[2] == "active":
                    row[2].setForeground(QColor(theme["ok"]))

                elif parts[2] == "failed":
                    row[2].setForeground(QColor(theme["danger"]))

                model.appendRow(row)

        self.table_views["Services"].resizeColumnsToContents()

    def _render_processes(self, out: str) -> None:
        model = self.table_views["Processes"].model()

        model.clear()

        lines = out.splitlines()

        if not lines:
            return

        headers = lines[0].split(None, 10)

        model.setHorizontalHeaderLabels(headers)

        for line in lines[1:]:
            parts = line.split(None, 10)

            if len(parts) >= 11:
                model.appendRow(
                    [QStandardItem(x) for x in parts]
                )

        self.table_views["Processes"].resizeColumnsToContents()

    # ------------------------------------------------------------
    # Service operations
    # ------------------------------------------------------------

    def service_op(self, op: str) -> None:
        table = self.table_views["Services"]

        index = table.currentIndex()

        if not index.isValid():
            QMessageBox.information(
                self,
                "Services",
                "Select a service row first.",
            )
            return

        unit = table.model().item(index.row(), 0).text()

        sudo = "sudo " if self.sudo_chk.isChecked() else ""

        cmd = (
            f"{sudo}systemctl {op} {shlex.quote(unit)} "
            f"&& echo '[{op} OK] {shlex.quote(unit)}'"
        )

        if QMessageBox.question(
            self,
            "Confirm",
            f"Run: {cmd}",
        ) != QMessageBox.StandardButton.Yes:
            return

        self.status.setText(f"Running {op} {unit}...")

        self._worker = RemoteExecThread(
            self.profile,
            cmd,
            timeout=60,
        )

        def after(out: str, rc: int) -> None:
            self.services.notifications.push(
                "ok" if rc == 0 else "error",
                f"systemctl {op}",
                out.strip()[:200] or unit,
            )

            self._refresh_current()

        self._worker.finished_cmd.connect(after)

        self._worker.start()
