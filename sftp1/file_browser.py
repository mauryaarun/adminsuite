"""
File browser panel for local and remote SFTP views.
"""
from __future__ import annotations
import datetime
import json
import os
from typing import Any, Optional
from PyQt6.QtCore import QByteArray, QMimeData, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMenu, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget, QCheckBox
)
from admin_suite.sftp.models import SftpAction, SftpTask
from admin_suite.sftp.worker import SftpWorker

class FileBrowserPanel(QWidget):
    file_action = pyqtSignal(str, str, str)

    def __init__(self, services, panel_id: str, mode: str = "local", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.services = services
        self.panel_id = panel_id
        self.mode = mode
        self.show_hidden = False
        self._all_entries = []
        
        if mode == "local":
            default_local = self.services.config.get("sftp_default_local", "")
            self.current_path = default_local if default_local and os.path.isdir(default_local) else os.path.expanduser("~")
        else:
            self.current_path = "/"
            
        self.sftp_worker: Optional[SftpWorker] = None
        self.host_info: dict[str, Any] = {}
        self.setAcceptDrops(True)
        self._drag_start_pos = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Navigation Bar
        pb = QHBoxLayout()
        up = QPushButton("⬆")
        up.setFixedWidth(30)
        up.clicked.connect(self.go_up)
        rf = QPushButton("🔄")
        rf.setFixedWidth(30)
        rf.clicked.connect(self.refresh)
        
        self.hidden_chk = QCheckBox("👁 Hidden")
        self.hidden_chk.toggled.connect(self._toggle_hidden)
        
        self.path_input = QLineEdit(self.current_path)
        self.path_input.returnPressed.connect(lambda: self.navigate_to_path(self.path_input.text()))
        
        pb.addWidget(up)
        pb.addWidget(rf)
        pb.addWidget(self.path_input, 1)
        pb.addWidget(self.hidden_chk)
        layout.addLayout(pb)
        
        # Tree
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Name", "Size", "Modified"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in (1, 2):
            self.tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemDoubleClicked.connect(self.on_dbl_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_ctx_menu)
        self.tree.setDragEnabled(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.tree, 1)
        
        # Filter Bar
        filter_lay = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("🔍 Quick filter...")
        self.filter_input.textChanged.connect(self._apply_filter)
        filter_lay.addWidget(self.filter_input)
        layout.addLayout(filter_lay)

        theme = self.services.theme.current
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color:{theme['sub']};font-size:11px;")
        layout.addWidget(self.status_label)
        
        if mode == "local":
            self.refresh()

    def _toggle_hidden(self, checked: bool):
        self.show_hidden = checked
        self._apply_filter(self.filter_input.text())

    def _apply_filter(self, text: str):
        self._fill_tree(self._all_entries, "filtered")

    def configure_remote(self, host: str, port: int, user: str, creds, *, use_agent: bool = False, strict_host_keys: bool = False) -> None:
        self.host_info = {
            "host": host, "port": port, "user": user, "creds": creds,
            "use_agent": use_agent, "strict_host_keys": strict_host_keys,
        }

    def refresh(self) -> None:
        self.navigate_to_path(self.current_path)

    def go_up(self) -> None:
        if self.mode == "local":
            parent = os.path.dirname(self.current_path.rstrip("/"))
            if not parent: parent = os.path.expanduser("~")
            self.navigate_to_path(parent)
        else:
            self.navigate_to_path(self._remote_parent(self.current_path))

    def navigate_to_path(self, path: str) -> None:
        self.current_path = path
        self.path_input.setText(path)
        if self.mode == "local":
            self._list_local(path)
        else:
            self._list_remote(path)

    def _remote_parent(self, path: str) -> str:
        if path == "/": return "/"
        p = path.rstrip("/")
        if "/" not in p: return "/"
        parent = p.rsplit("/", 1)[0]
        return parent or "/"

    def _remote_full(self, name: str) -> str:
        if self.current_path == "/": return "/" + name
        return self.current_path.rstrip("/") + "/" + name

    def _fill_tree(self, entries: list[dict[str, Any]], tag: str) -> None:
        self._all_entries = entries
        self.tree.clear()
        filter_text = self.filter_input.text().lower()
        count = 0
        
        for e in entries:
            if not self.show_hidden and e["name"].startswith("."):
                continue
            if filter_text and filter_text not in e["name"].lower():
                continue
                
            item = QTreeWidgetItem()
            item.setText(0, ("📁 " if e["is_dir"] else "📄 ") + e["name"])
            item.setText(1, "<DIR>" if e["is_dir"] else self._fmt_size(e["size"]))
            if e.get("mtime"):
                item.setText(2, datetime.datetime.fromtimestamp(e["mtime"]).strftime("%Y-%m-%d %H:%M"))
            else:
                item.setText(2, "")
            item.setData(0, Qt.ItemDataRole.UserRole, e)
            self.tree.addTopLevelItem(item)
            count += 1
            
        self.status_label.setText(f"{count} items ({tag})")

    def _list_local(self, path: str) -> None:
        try:
            entries = []
            for name in os.listdir(path):
                full = os.path.join(path, name)
                try:
                    st = os.stat(full)
                    entries.append({"name": name, "size": st.st_size, "is_dir": os.path.isdir(full), "mtime": st.st_mtime, "mode": st.st_mode})
                except Exception: pass
            entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            self._fill_tree(entries, "local")
        except Exception as ex:
            self.status_label.setText(f"Error: {ex}")

    def _list_remote(self, path: str) -> None:
        if not self.host_info.get("host"):
            self.status_label.setText("Remote host not configured")
            return
        self.status_label.setText("Loading...")
        self.tree.clear()
        if self.sftp_worker and self.sftp_worker.isRunning():
            self.sftp_worker.wait(1500)
        h = self.host_info
        self.sftp_worker = SftpWorker(
            h["host"], h.get("port", 22), h.get("user", ""), h.get("creds"),
            use_agent=h.get("use_agent", False), strict_host_keys=h.get("strict_host_keys", False),
        )
        self.sftp_worker.listing_ready.connect(self._on_remote_listing)
        self.sftp_worker.error_occurred.connect(lambda e: self.status_label.setText(f"Error: {e}"))
        task = SftpTask(action=SftpAction.LIST, path=path)
        self.sftp_worker.set_task(task)
        self.sftp_worker.start()

    def _on_remote_listing(self, entries: list[dict[str, Any]], path: str) -> None:
        self.current_path = path
        self.path_input.setText(path)
        self._fill_tree(entries, "remote")

    @staticmethod
    def _fmt_size(size: float) -> str:
        size = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024: return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def on_dbl_click(self, item: QTreeWidgetItem, column: int) -> None:
        e = item.data(0, Qt.ItemDataRole.UserRole)
        if not e: return
        if e["is_dir"]:
            if self.mode == "local":
                self.navigate_to_path(os.path.join(self.current_path, e["name"]))
            else:
                self.navigate_to_path(self._remote_full(e["name"]))
        else:
            if self.mode == "local":
                self.file_action.emit("upload", os.path.join(self.current_path, e["name"]), self.panel_id)
            else:
                # UX Enhancement: Double clicking a remote file opens it in editor
                self.file_action.emit("edit", self._remote_full(e["name"]), self.panel_id)

    def show_ctx_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        if item:
            e = item.data(0, Qt.ItemDataRole.UserRole)
            full_local = os.path.join(self.current_path, e["name"])
            full_remote = self._remote_full(e["name"])
            if self.mode == "local":
                if e["is_dir"]:
                    menu.addAction("📤 Upload Dir to Remote").triggered.connect(lambda: self.file_action.emit("upload-dir", full_local, self.panel_id))
                else:
                    menu.addAction("📤 Upload to Remote").triggered.connect(lambda: self.file_action.emit("upload", full_local, self.panel_id))
            else:
                if e["is_dir"]:
                    menu.addAction("📥 Download Dir to Local").triggered.connect(lambda: self.file_action.emit("download-dir", full_remote, self.panel_id))
                else:
                    menu.addAction("📥 Download to Local").triggered.connect(lambda: self.file_action.emit("download", full_remote, self.panel_id))
                    menu.addAction("✏️ Open in Editor").triggered.connect(lambda: self.file_action.emit("edit", full_remote, self.panel_id))
                    menu.addAction("🔐 Permissions (chmod)").triggered.connect(lambda: self.file_action.emit("chmod", json.dumps({"path": full_remote, "mode": e.get("mode", 0o644)}), self.panel_id))
                menu.addAction("🗑 Delete").triggered.connect(lambda: self.file_action.emit("delete", full_remote, self.panel_id))
            menu.addSeparator()
            menu.addAction("📋 Copy Path").triggered.connect(lambda: QApplication.clipboard().setText(full_local if self.mode == "local" else full_remote))
        menu.addAction("🔄 Refresh").triggered.connect(self.refresh)
        menu.addAction("📁 New Folder").triggered.connect(lambda: self.file_action.emit("mkdir", self.current_path, self.panel_id))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def get_selected_file(self) -> Optional[dict[str, Any]]:
        item = self.tree.currentItem()
        if not item: return None
        e = item.data(0, Qt.ItemDataRole.UserRole)
        if not e: return None
        if self.mode == "local":
            return {"path": os.path.join(self.current_path, e["name"]), "name": e["name"], "is_dir": e["is_dir"]}
        return {"path": self._remote_full(e["name"]), "name": e["name"], "is_dir": e["is_dir"]}

    def get_selected_files(self) -> list[dict[str, Any]]:
        items = self.tree.selectedItems()
        if not items:
            item = self.tree.currentItem()
            items = [item] if item else []
        selected = []
        for item in items:
            e = item.data(0, Qt.ItemDataRole.UserRole)
            if not e: continue
            if self.mode == "local":
                selected.append({"path": os.path.join(self.current_path, e["name"]), "name": e["name"], "is_dir": e["is_dir"]})
            else:
                selected.append({"path": self._remote_full(e["name"]), "name": e["name"], "is_dir": e["is_dir"]})
        return selected

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_start_pos:
            distance = (e.position().toPoint() - self._drag_start_pos).manhattanLength()
            if distance > 10:
                selected = self.get_selected_files()
                if selected:
                    md = QMimeData()
                    if self.mode == "local":
                        md.setUrls([QUrl.fromLocalFile(x["path"]) for x in selected])
                    else:
                        payload = json.dumps({"panel_id": self.panel_id, "files": [{"path": x["path"], "name": x["name"]} for x in selected]})
                        md.setData("application/x-admin-suite-remote-files", QByteArray(payload.encode()))
                    drag = QDrag(self)
                    drag.setMimeData(md)
                    drag.exec(Qt.DropAction.CopyAction)
                self._drag_start_pos = None
        super().mouseMoveEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasFormat("application/x-admin-suite-remote-files"):
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        if self.mode == "remote" and md.hasUrls():
            for u in md.urls():
                lp = u.toLocalFile()
                if lp and os.path.exists(lp):
                    if os.path.isdir(lp): self.file_action.emit("upload-dir", lp, self.panel_id)
                    else: self.file_action.emit("upload", lp, self.panel_id)
            e.acceptProposedAction()
        elif self.mode == "local" and md.hasFormat("application/x-admin-suite-remote-files"):
            raw = json.loads(bytes(md.data("application/x-admin-suite-remote-files")).decode())
            files = raw.get("files", []) if isinstance(raw, dict) else raw
            for it in files:
                self.file_action.emit("download-to", json.dumps({"remote": it["path"], "local": os.path.join(self.current_path, it["name"])}), self.panel_id)
            e.acceptProposedAction()