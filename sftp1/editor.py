"""
Remote text editor tab.
"""
from __future__ import annotations
from typing import Any, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextDocument
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
    QWidget, QLineEdit, QFrame
)
from admin_suite.sftp.models import SftpAction, SftpTask
from admin_suite.sftp.worker import SftpWorker

class RemoteEditorTab(QWidget):
    """
    Edit a remote text file over SFTP.
    """
    def __init__(
        self,
        services,
        host_info: dict[str, Any],
        remote_path: str,
        parent: Optional[QWidget] = None,
        jump_to_line: int = 0
    ):
        super().__init__(parent)
        self.services = services
        self.host_info = host_info
        self.remote_path = remote_path
        self._loader: Optional[SftpWorker] = None
        self._saver: Optional[SftpWorker] = None
        self._jump_to_line = jump_to_line
        theme = self.services.theme.current
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        
        # Top Bar
        bar = QHBoxLayout()
        title = QLabel(f"✏️ {remote_path}")
        title.setStyleSheet(f"color:{theme['accent']};font-weight:bold;")
        bar.addWidget(title)
        
        self.dirty_label = QLabel("")
        self.dirty_label.setStyleSheet(f"color:{theme['warn']};")
        bar.addWidget(self.dirty_label)
        bar.addStretch()
        
        self.find_btn = QPushButton("🔍 Find")
        self.find_btn.clicked.connect(self.toggle_find_bar)
        bar.addWidget(self.find_btn)
        
        reload_b = QPushButton("🔄 Reload")
        reload_b.clicked.connect(self.load)
        bar.addWidget(reload_b)
        
        save = QPushButton("💾 Save (Ctrl+S)")
        save.setShortcut("Ctrl+S")
        save.clicked.connect(self.save)
        bar.addWidget(save)
        
        lay.addLayout(bar)
        
        # Find Bar (Hidden by default)
        self.find_frame = QFrame()
        self.find_frame.setVisible(False)
        find_lay = QHBoxLayout(self.find_frame)
        find_lay.setContentsMargins(0, 0, 0, 0)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find...")
        self.find_input.returnPressed.connect(self.find_next)
        find_lay.addWidget(self.find_input)
        
        prev_btn = QPushButton("⬆ Prev")
        prev_btn.clicked.connect(self.find_prev)
        find_lay.addWidget(prev_btn)
        
        next_btn = QPushButton("⬇ Next")
        next_btn.clicked.connect(self.find_next)
        find_lay.addWidget(next_btn)
        
        close_find = QPushButton("✖")
        close_find.setMaximumWidth(30)
        close_find.clicked.connect(lambda: self.find_frame.setVisible(False))
        find_lay.addWidget(close_find)
        lay.addWidget(self.find_frame)

        # Editor
        self.edit = QPlainTextEdit()
        self.edit.setFont(QFont("JetBrains Mono, Consolas", 11))
        self.edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.edit.textChanged.connect(lambda: self.dirty_label.setText("● modified"))
        self.edit.cursorPositionChanged.connect(self._update_cursor_pos)
        lay.addWidget(self.edit, 1)
        
        # Status Bar
        self.status_bar = QLabel("Ln 1, Col 1 | UTF-8")
        self.status_bar.setStyleSheet(f"color:{theme['sub']}; font-size:11px;")
        lay.addWidget(self.status_bar)
        
        self.load()

    def toggle_find_bar(self):
        visible = not self.find_frame.isVisible()
        self.find_frame.setVisible(visible)
        if visible:
            self.find_input.setFocus()
            self.find_input.selectAll()

    def find_next(self):
        text = self.find_input.text()
        if text:
            self.edit.find(text)

    def find_prev(self):
        text = self.find_input.text()
        if text:
            self.edit.find(text, QTextDocument.FindFlag.FindBackward)

    def _update_cursor_pos(self):
        cursor = self.edit.textCursor()
        ln = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self.status_bar.setText(f"Ln {ln}, Col {col} | UTF-8")
        
        if self._jump_to_line > 0 and ln == 1:
            # Jump to line after initial load
            block = self.edit.document().findBlockByLineNumber(self._jump_to_line - 1)
            if block.isValid():
                cursor.setPosition(block.position())
                self.edit.setTextCursor(cursor)
                self.edit.centerCursor()
                self._jump_to_line = 0  # Reset

    def _make_worker(self) -> SftpWorker:
        h = self.host_info
        return SftpWorker(
            h.get("host", ""), h.get("port", 22), h.get("user", ""),
            h.get("creds"), use_agent=h.get("use_agent", False),
            strict_host_keys=h.get("strict_host_keys", False),
        )

    def load(self) -> None:
        self._loader = self._make_worker()
        task = SftpTask(action=SftpAction.READ, remote_path=self.remote_path)
        self._loader.set_task(task)
        self._loader.file_content.connect(self._loaded)
        self._loader.error_occurred.connect(
            lambda e: self.services.notifications.push("error", "Remote Editor", e)
        )
        self._loader.start()

    def _loaded(self, path: str, content: str) -> None:
        self.edit.blockSignals(True)
        self.edit.setPlainText(content)
        self.edit.blockSignals(False)
        self.dirty_label.setText("")
        self._update_cursor_pos()  # Trigger jump to line if needed

    def save(self) -> None:
        self._saver = self._make_worker()
        task = SftpTask(
            action=SftpAction.WRITE,
            remote_path=self.remote_path,
            content=self.edit.toPlainText(),
        )
        self._saver.set_task(task)
        self._saver.transfer_complete.connect(
            lambda n, up: (
                self.dirty_label.setText(""),
                self.services.notifications.push("ok", "Saved", f"{self.remote_path} written"),
            )
        )
        self._saver.error_occurred.connect(
            lambda e: self.services.notifications.push("error", "Save Error", e)
        )
        self._saver.start()

    def closeEvent(self, event):
        for attr in ("_loader", "_saver"):
            worker = getattr(self, attr, None)
            if worker is not None:
                try:
                    if worker.isRunning(): worker.wait(1000)
                except Exception: pass
        event.accept()