"""
Main SFTP tab with local/remote panels, transfer queue, and status log.
"""
from __future__ import annotations
import datetime
import json
import os
import subprocess
from typing import Any, Optional
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton,
    QSplitter, QVBoxLayout, QWidget, QInputDialog, QMessageBox
)
from admin_suite.sftp.dialogs import ChmodDialog
from admin_suite.sftp.editor import RemoteEditorTab
from admin_suite.sftp.file_browser import FileBrowserPanel
from admin_suite.sftp.models import SftpAction, SftpTask
from admin_suite.sftp.search import RemoteSearchDialog
from admin_suite.sftp.worker import SftpWorker
from admin_suite.sftp.rsync import RsyncDialog

class SFTPTab(QWidget):
    """
    SFTP browser tab.
    """
    def __init__(
        self, services, main_window=None, *, host: str = "", port: int = 22,
        user: str = "", creds=None, name: str = "", use_agent: bool = False,
        strict_host_keys: Optional[bool] = None,
    ):
        super().__init__(main_window)
        self.services = services
        self.main_window = main_window
        self.host = host
        self.user = user
        try: self.port = int(port) if port else 22
        except Exception: self.port = 22
        self.creds = creds
        self.name = name
        self.use_agent = bool(use_agent)
        if strict_host_keys is None:
            strict_host_keys = bool(self.services.config.get("ssh_strict_host_keys", False))
        self.strict_host_keys = bool(strict_host_keys)
        
        self.host_info = {
            "host": self.host, "port": self.port, "user": self.user, "creds": self.creds,
            "use_agent": self.use_agent, "strict_host_keys": self.strict_host_keys,
        }
        self._queue: list[SftpTask] = []
        self._active_transfer: Optional[SftpWorker] = None
        self._active_task: Optional[SftpTask] = None
        
        theme = self.services.theme.current
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        title = QLabel(f"🔗 SFTP — {user}@{host}:{self.port}")
        title.setStyleSheet(f"color:{theme['accent']};font-weight:bold;padding:4px;")
        layout.addWidget(title)
        
        ab = QHBoxLayout()
        up = QPushButton("⬆ Upload Selected")
        up.clicked.connect(self.upload_selected)
        dn = QPushButton("⬇ Download Selected")
        dn.clicked.connect(self.download_selected)
        srch = QPushButton("🔎 Remote Search...")
        srch.clicked.connect(self.remote_search)
        rsync_btn = QPushButton("🔄 Rsync Folder")
        rsync_btn.clicked.connect(self.open_rsync)
        
        hint = QLabel("Tip: drag files/dirs between panels")
        hint.setStyleSheet(f"color:{theme['sub']};font-size:11px;")
        
        ab.addWidget(up)
        ab.addWidget(dn)
        ab.addWidget(srch)
        ab.addWidget(rsync_btn)
        ab.addStretch()
        ab.addWidget(hint)
        layout.addLayout(ab)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.local_panel = FileBrowserPanel(self.services, "local", mode="local")
        self.local_panel.file_action.connect(self.on_file_action)
        
        self.remote_panel = FileBrowserPanel(self.services, "remote", mode="remote")
        self.remote_panel.configure_remote(
            self.host, self.port, self.user, self.creds,
            use_agent=self.use_agent, strict_host_keys=self.strict_host_keys,
        )
        self.remote_panel.file_action.connect(self.on_file_action)
        
        splitter.addWidget(self.local_panel)
        splitter.addWidget(self.remote_panel)
        splitter.setSizes([600, 600])
        layout.addWidget(splitter, 1)
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color:{theme['sub']};")
        layout.addWidget(self.status_label)
        
        self.sftp_log = QPlainTextEdit()
        self.sftp_log.setReadOnly(True)
        self.sftp_log.setMaximumHeight(130)
        self.sftp_log.setFont(QFont("JetBrains Mono, Consolas", 10))
        self.sftp_log.setPlaceholderText("SFTP operation log...")
        self.sftp_log.setStyleSheet(f"background:{theme['panel']};border:1px solid {theme['border']};")
        layout.addWidget(self.sftp_log)
        
        self.remote_panel.refresh()

    def open_rsync(self):
        dlg = RsyncDialog(self, self.services, self.host_info)
        # Pre-fill paths
        dlg.local_path.setText(self.local_panel.current_path)
        dlg.remote_path.setText(self.remote_panel.current_path)
        dlg.exec()

    def _log(self, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.sftp_log.appendPlainText(f"[{ts}] {msg}")
        doc = self.sftp_log.document()
        if doc.blockCount() > 2000:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(500):
                cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    @staticmethod
    def _remote_join(path: str, name: str) -> str:
        if path == "/": return "/" + name
        return path.rstrip("/") + "/" + name

    def remote_search(self) -> None:
        dlg = RemoteSearchDialog(self, self.host_info)
        dlg.open_file_requested.connect(self._open_remote_file)
        dlg.exec()

    def _open_remote_file(self, path: str, line: int):
        """Opens a remote file in the editor and jumps to the line."""
        self.on_file_action("edit", path, "remote", line)

    def upload_selected(self) -> None:
        sels = self.local_panel.get_selected_files()
        if not sels:
            self.services.notifications.push("info", "Upload", "Select one or more files/folders in the local panel.")
            return
        for sel in sels:
            rp = self._remote_join(self.remote_panel.current_path, sel["name"])
            task = SftpTask(action=SftpAction.UPLOAD, local_path=sel["path"], remote_path=rp, recursive=bool(sel["is_dir"]))
            self._enqueue(task)
        self.status_label.setText(f"Queued {len(sels)} item(s) for upload")

    def download_selected(self) -> None:
        sels = self.remote_panel.get_selected_files()
        if not sels:
            self.services.notifications.push("info", "Download", "Select one or more files/folders in the remote panel.")
            return
        for sel in sels:
            local_path = os.path.join(self.local_panel.current_path, sel["name"])
            task = SftpTask(action=SftpAction.DOWNLOAD, remote_path=sel["path"], local_path=local_path, recursive=bool(sel["is_dir"]))
            self._enqueue(task)
        self.status_label.setText(f"Queued {len(sels)} item(s) for download")

    def _enqueue(self, task: SftpTask) -> None:
        self._queue.append(task)
        source = task.local_path or task.remote_path
        self._log(f"Queued: {task.action.value} {os.path.basename(source)}")
        if self._active_transfer is None:
            self._next_transfer()

    def _next_transfer(self) -> None:
        if not self._queue:
            self._active_transfer = None
            self._active_task = None
            self.progress.setVisible(False)
            return
        task = self._queue.pop(0)
        self._active_task = task
        self.progress.setVisible(True)
        self.progress.setValue(0)
        source = task.local_path or task.remote_path
        self.status_label.setText(f"{task.action.value.capitalize()}ing {os.path.basename(source)}...")
        self._log(f"Starting: {task.action.value} {os.path.basename(source)} → {task.remote_path or task.local_path}")
        
        worker = SftpWorker(
            self.host, self.port, self.user, self.creds,
            use_agent=self.use_agent, strict_host_keys=self.strict_host_keys,
        )
        worker.set_task(task)
        worker.transfer_progress.connect(self._progress)
        worker.transfer_complete.connect(lambda fn, uploaded, t=task: self._done(fn, t))
        worker.error_occurred.connect(self._err)
        worker.status_update.connect(self._log)
        self._active_transfer = worker
        worker.start()

    def _progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress.setMaximum(total)
            self.progress.setValue(done)

    def _done(self, filename: str, task: SftpTask) -> None:
        self.status_label.setText(f"✅ {filename} transferred")
        self._log(f"✅ Complete: {filename} ({task.action.value})")
        self.services.notifications.push("ok", "Transfer complete", f"{filename} ({task.action.value})")
        if task.action == SftpAction.UPLOAD: self.remote_panel.refresh()
        elif task.action == SftpAction.DOWNLOAD: self.local_panel.refresh()
        QTimer.singleShot(150, self._next_transfer)

    def _err(self, err: str) -> None:
        self.status_label.setText(f"❌ {err}")
        self._log(f"❌ ERROR: {err}")
        self.services.notifications.push("error", "Transfer failed", err)
        QTimer.singleShot(150, self._next_transfer)

    def on_file_action(self, action: str, path: str, panel_id: str, extra_arg: Any = None) -> None:
        try:
            if action == "edit":
                jump_line = extra_arg if isinstance(extra_arg, int) else 0
                tab = RemoteEditorTab(self.services, self.host_info, path, parent=self.main_window, jump_to_line=jump_line)
                if self.main_window and hasattr(self.main_window, "tabs"):
                    idx = self.main_window.tabs.addTab(tab, f"✏️ {os.path.basename(path)}")
                    self.main_window.tabs.setCurrentIndex(idx)
                else:
                    tab.show()
            elif action == "chmod":
                try:
                    data = json.loads(path)
                    actual_mode = data.get("mode", 0o644)
                    chmod_path = data["path"]
                except (json.JSONDecodeError, TypeError):
                    actual_mode = 0o644
                    chmod_path = path
                dlg = ChmodDialog(self, actual_mode)
                if dlg.exec():
                    worker = SftpWorker(
                        self.host, self.port, self.user, self.creds,
                        use_agent=self.use_agent, strict_host_keys=self.strict_host_keys,
                    )
                    task = SftpTask(action=SftpAction.CHMOD, path=self.remote_panel.current_path, remote_path=chmod_path, mode=dlg.result_mode)
                    worker.set_task(task)
                    worker.listing_ready.connect(lambda ents, p: self.remote_panel._fill_tree(ents, "remote"))
                    worker.error_occurred.connect(lambda e: (self._log(f"❌ chmod error: {e}"), self.services.notifications.push("error", "chmod", e)))
                    worker.status_update.connect(self._log)
                    worker.start()
            elif action == "delete":
                worker = SftpWorker(
                    self.host, self.port, self.user, self.creds,
                    use_agent=self.use_agent, strict_host_keys=self.strict_host_keys,
                )
                task = SftpTask(action=SftpAction.DELETE, path=self.remote_panel.current_path, remote_path=path)
                worker.set_task(task)
                worker.listing_ready.connect(lambda ents, p: self.remote_panel._fill_tree(ents, "remote"))
                worker.error_occurred.connect(lambda e: (self._log(f"❌ delete error: {e}"), self.services.notifications.push("error", "Delete", e)))
                worker.status_update.connect(self._log)
                worker.start()
            elif action == "mkdir":
                name, ok = QInputDialog.getText(self, "New Folder", "Name:")
                if ok and name:
                    if panel_id == "local":
                        new_path = os.path.join(path, name)
                        try:
                            os.makedirs(new_path, exist_ok=True)
                            self.local_panel.refresh()
                            self._log(f"✅ Created local folder: {new_path}")
                        except Exception as e:
                            self._log(f"❌ local mkdir error: {e}")
                            QMessageBox.critical(self, "mkdir", str(e))
                    else:
                        remote = path.rstrip("/") + "/" + name if path != "/" else "/" + name
                        worker = SftpWorker(
                            self.host, self.port, self.user, self.creds,
                            use_agent=self.use_agent, strict_host_keys=self.strict_host_keys,
                        )
                        task = SftpTask(action=SftpAction.MKDIR, path=path, remote_path=remote)
                        worker.set_task(task)
                        worker.listing_ready.connect(lambda ents, p: self.remote_panel._fill_tree(ents, "remote"))
                        worker.error_occurred.connect(lambda e: (self._log(f"❌ mkdir error: {e}"), QMessageBox.critical(self, "mkdir", e)))
                        worker.status_update.connect(self._log)
                        worker.start()
            elif action in ("upload", "upload-dir"):
                rp = self._remote_join(self.remote_panel.current_path, os.path.basename(path))
                task = SftpTask(action=SftpAction.UPLOAD, local_path=path, remote_path=rp, recursive=(action == "upload-dir"))
                self._enqueue(task)
            elif action in ("download", "download-dir"):
                local_dir = os.path.join(self.local_panel.current_path, os.path.basename(path))
                task = SftpTask(action=SftpAction.DOWNLOAD, remote_path=path, local_path=local_dir, recursive=(action == "download-dir"))
                self._enqueue(task)
            elif action == "download-to":
                spec = json.loads(path)
                task = SftpTask(action=SftpAction.DOWNLOAD, remote_path=spec["remote"], local_path=spec["local"], recursive=False)
                self._enqueue(task)
        except Exception as e:
            self._log(f"❌ Action '{action}' failed: {e}")
            self.services.notifications.push("error", "SFTP Error", f"Operation failed: {e}")

    def closeEvent(self, event):
        try:
            if self._active_transfer is not None and self._active_transfer.isRunning():
                self._active_transfer.wait(1500)
        except Exception: pass
        for panel in (self.local_panel, self.remote_panel):
            worker = getattr(panel, "sftp_worker", None)
            if worker is not None:
                try:
                    if worker.isRunning(): worker.wait(1000)
                except Exception: pass
        event.accept()