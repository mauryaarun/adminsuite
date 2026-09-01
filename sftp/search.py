"""
Remote grep search dialog with history, options, and click-to-open.
"""
from __future__ import annotations
import re
import shlex
from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSpinBox, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout,
)

from admin_suite.sftp.exec_worker import RemoteExecThread


class RemoteSearchDialog(QDialog):
    """Search remote files using grep, with options and history."""

    def __init__(self, parent, host_info: dict[str, Any], services=None):
        super().__init__(parent)
        self.host_info = host_info
        self.services = services
        self._worker = None
        self._history: list[str] = []
        self.setWindowTitle("Remote Search (grep)")
        self.resize(820, 540)

        lay = QVBoxLayout(self)
        lay.setSpacing(6)

        # ---- pattern row ----
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Pattern:"))
        self.pattern = QComboBox()
        self.pattern.setEditable(True)
        self.pattern.setMinimumWidth(260)
        self.pattern.lineEdit().returnPressed.connect(self.run)
        row1.addWidget(self.pattern, 2)
        row1.addWidget(QLabel("Path:"))
        self.path = QLineEdit("/etc")
        row1.addWidget(self.path, 1)
        go = QPushButton("🔍 Search")
        go.setDefault(True)
        go.clicked.connect(self.run)
        row1.addWidget(go)
        lay.addLayout(row1)

        # ---- options row ----
        row2 = QHBoxLayout()
        self.case_i = QCheckBox("Ignore case")
        self.whole = QCheckBox("Whole word")
        self.regex = QCheckBox("Regex (-E)")
        self.regex.setChecked(True)
        row2.addWidget(self.case_i)
        row2.addWidget(self.whole)
        row2.addWidget(self.regex)
        row2.addWidget(QLabel("Context:"))
        self.context = QSpinBox()
        self.context.setRange(0, 10)
        self.context.setValue(0)
        row2.addWidget(self.context)
        row2.addWidget(QLabel("Glob:"))
        self.glob = QLineEdit()
        self.glob.setPlaceholderText("*.conf (optional)")
        row2.addWidget(self.glob, 1)
        export = QPushButton("⬇ Export")
        export.clicked.connect(self.export_results)
        row2.addWidget(export)
        lay.addLayout(row2)

        # ---- results ----
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["File", "Line", "Match"])
        self.tree.header().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemDoubleClicked.connect(self._open_match)
        lay.addWidget(self.tree, 1)

        self.status = QLabel("Ready — double-click a result to open in editor")
        lay.addWidget(self.status)

    # ------------------------------------------------------------------
    def _build_cmd(self) -> str:
        pat = self.pattern.currentText().strip()
        flags = "-rnI --color=never -m 300"
        if self.case_i.isChecked():
            flags += "i"
        if self.whole.isChecked():
            flags += "w"
        if self.regex.isChecked():
            flags += "E"
        ctx = self.context.value()
        if ctx:
            flags += f" -C {ctx}"
        glob = self.glob.text().strip()
        include = f" --include={shlex.quote(glob)}" if glob else ""
        return (
            f"grep {flags}{include} -- "
            f"{shlex.quote(pat)} {shlex.quote(self.path.text())} "
            "2>/dev/null | head -400"
        )

    def run(self) -> None:
        pat = self.pattern.currentText().strip()
        if not pat:
            return
        if pat not in self._history:
            self._history.insert(0, pat)
            self.pattern.insertItem(0, pat)
        self.status.setText("Searching…")
        self.tree.clear()
        self._worker = RemoteExecThread(
            self.host_info, self._build_cmd(), timeout=60)
        self._worker.finished_cmd.connect(self._done)
        self._worker.start()

    def _done(self, out: str, rc: int) -> None:
        count = 0
        for line in out.splitlines():
            m = re.match(r"^(.+?):(\d+)[:-](.*)$", line)
            if m:
                it = QTreeWidgetItem(
                    [m.group(1), m.group(2), m.group(3)[:300]])
                it.setData(0, Qt.ItemDataRole.UserRole, m.group(1))
                it.setData(1, Qt.ItemDataRole.UserRole, m.group(2))
                self.tree.addTopLevelItem(it)
                count += 1
        self.status.setText(
            f"{count} matches — double-click to open in editor")

    def _open_match(self, item: QTreeWidgetItem, _col: int) -> None:
        """Signal the parent tab to open the matched file in the editor."""
        fp = item.data(0, Qt.ItemDataRole.UserRole)
        if not fp:
            return
        # Walk up to the SFTPTab which owns the editor-opening logic.
        p = self.parent()
        while p is not None and not hasattr(p, "open_remote_editor"):
            p = p.parent()
        if p is not None:
            p.open_remote_editor(fp)

    def export_results(self) -> None:
        if not self.tree.topLevelItemCount():
            return
        fn, _ = QFileDialog.getSaveFileName(
            self, "Export results", "search_results.txt",
            "Text files (*.txt)")
        if not fn:
            return
        with open(fn, "w", encoding="utf-8") as fh:
            for i in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(i)
                fh.write(f"{it.text(0)}:{it.text(1)}:{it.text(2)}\n")
        self.status.setText(f"Exported to {fn}")