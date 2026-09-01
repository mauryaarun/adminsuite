"""
Remote grep search dialog.
"""
from __future__ import annotations
import re
import shlex
from typing import Any
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QCheckBox, QGroupBox, QFormLayout
)
from admin_suite.sftp.exec_worker import RemoteExecThread

class RemoteSearchDialog(QDialog):
    """
    Search remote files using grep.
    """
    open_file_requested = pyqtSignal(str, int)  # path, line_number

    def __init__(self, parent, host_info: dict[str, Any]):
        super().__init__(parent)
        self.host_info = host_info
        self._worker = None
        self.setWindowTitle("Remote Search (grep)")
        self.resize(800, 550)
        
        lay = QVBoxLayout(self)
        
        # Search Options Group
        opts_group = QGroupBox("Search Options")
        opts_lay = QHBoxLayout(opts_group)
        
        self.case_sensitive = QCheckBox("Case Sensitive")
        self.case_sensitive.setChecked(True)
        opts_lay.addWidget(self.case_sensitive)
        
        self.use_regex = QCheckBox("Regex")
        opts_lay.addWidget(self.use_regex)
        
        opts_lay.addWidget(QLabel("File Filter:"))
        self.file_filter = QLineEdit("*")
        self.file_filter.setPlaceholderText("e.g. *.py, *.conf")
        self.file_filter.setMaximumWidth(150)
        opts_lay.addWidget(self.file_filter)
        
        opts_lay.addStretch()
        lay.addWidget(opts_group)

        # Main Search Bar
        form = QHBoxLayout()
        form.addWidget(QLabel("Pattern:"))
        self.pattern = QLineEdit()
        self.pattern.setPlaceholderText("Enter search string or regex...")
        form.addWidget(self.pattern, 2)
        
        form.addWidget(QLabel("Path:"))
        self.path = QLineEdit("/etc")
        form.addWidget(self.path, 1)
        
        go = QPushButton("🔍 Search")
        go.clicked.connect(self.run)
        form.addWidget(go)
        lay.addLayout(form)
        
        # Results Tree
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["File", "Line", "Match"])
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        lay.addWidget(self.tree, 1)
        
        self.status = QLabel("Ready. Double-click a result to open in editor.")
        lay.addWidget(self.status)
        
        self.pattern.returnPressed.connect(self.run)

    def run(self) -> None:
        pat = self.pattern.text().strip()
        if not pat:
            return
            
        self.status.setText("Searching...")
        self.tree.clear()
        
        # Build grep flags
        flags = "-rnI --color=never -m 500"
        if not self.case_sensitive.isChecked():
            flags += " -i"
        if not self.use_regex.isChecked():
            flags += " -F"  # Fixed string
            
        include_filter = self.file_filter.text().strip()
        include_cmd = ""
        if include_filter and include_filter != "*":
            include_cmd = f"--include={shlex.quote(include_filter)} "

        cmd = (
            f"grep {flags} {include_cmd}-- "
            f"{shlex.quote(pat)} {shlex.quote(self.path.text())} "
            "2>/dev/null | head -500"
        )
        
        self._worker = RemoteExecThread(self.host_info, cmd, timeout=60)
        self._worker.finished_cmd.connect(self._done)
        self._worker.start()

    def _done(self, out: str, rc: int) -> None:
        count = 0
        for line in out.splitlines():
            m = re.match(r"^(.+?):(\d+):(.*)$", line)
            if m:
                it = QTreeWidgetItem([m.group(1), m.group(2), m.group(3)[:300]])
                it.setData(0, Qt.ItemDataRole.UserRole, (m.group(1), int(m.group(2))))
                self.tree.addTopLevelItem(it)
                count += 1
        self.status.setText(f"✅ {count} matches found. Double-click to edit.")

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            path, line = data
            self.open_file_requested.emit(path, line)
            self.accept()  # Close dialog