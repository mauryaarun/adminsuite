"""
Networking Tools dialog.

Provides UI for:

- local port forwarding
- remote port forwarding
- dynamic SOCKS5 forwarding
- SOCKS5 proxy
- HTTP CONNECT proxy
- ProxyCommand
- jump hosts / host chaining
- SSH agent forwarding option
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from admin_suite.ssh.network_worker import SshNetworkingWorker
from admin_suite.ssh.networking import (
    FORWARD_DYNAMIC,
    FORWARD_LOCAL,
    FORWARD_REMOTE,
    PROXY_COMMAND,
    PROXY_HTTP,
    PROXY_NONE,
    PROXY_SOCKS5,
    ForwardRule,
    JumpHost,
    ProxyConfig,
    SshTarget,
)


class ForwardRuleDialog(QDialog):
    """
    Small dialog for creating a forwarding rule.
    """

    def __init__(self, kind: str = FORWARD_LOCAL, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Port Forwarding Rule")
        self.setMinimumWidth(420)

        layout = QFormLayout(self)

        self.kind_combo = QComboBox()
        self.kind_combo.addItem("Local", FORWARD_LOCAL)
        self.kind_combo.addItem("Remote", FORWARD_REMOTE)
        self.kind_combo.addItem("Dynamic SOCKS5", FORWARD_DYNAMIC)

        index = self.kind_combo.findData(kind)
        if index >= 0:
            self.kind_combo.setCurrentIndex(index)

        self.listen_host_edit = QLineEdit("127.0.0.1")
        self.listen_port_spin = QSpinBox()
        self.listen_port_spin.setRange(0, 65535)
        self.listen_port_spin.setValue(0)
        self.listen_port_spin.setSpecialValueText("Auto")

        self.dest_host_edit = QLineEdit()
        self.dest_port_spin = QSpinBox()
        self.dest_port_spin.setRange(0, 65535)

        layout.addRow("Type", self.kind_combo)
        layout.addRow("Listen Host", self.listen_host_edit)
        layout.addRow("Listen Port", self.listen_port_spin)
        layout.addRow("Destination Host", self.dest_host_edit)
        layout.addRow("Destination Port", self.dest_port_spin)

        self.kind_combo.currentIndexChanged.connect(self._update_fields)
        self._update_fields()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addRow(buttons)

    def _update_fields(self) -> None:
        kind = self.kind_combo.currentData()

        dynamic = kind == FORWARD_DYNAMIC

        self.dest_host_edit.setEnabled(not dynamic)
        self.dest_port_spin.setEnabled(not dynamic)

        if dynamic:
            self.dest_host_edit.setText("")
            self.dest_port_spin.setValue(0)

    def rule(self) -> ForwardRule:
        kind = self.kind_combo.currentData()

        return ForwardRule(
            kind=kind,
            listen_host=self.listen_host_edit.text().strip() or "127.0.0.1",
            listen_port=self.listen_port_spin.value(),
            dest_host=self.dest_host_edit.text().strip(),
            dest_port=self.dest_port_spin.value(),
        )


class JumpHostDialog(QDialog):
    """
    Simple jump host dialog.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Add Jump Host")
        self.setMinimumWidth(420)

        layout = QFormLayout(self)

        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)

        self.user_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.key_path_edit = QLineEdit()

        layout.addRow("Host", self.host_edit)
        layout.addRow("Port", self.port_spin)
        layout.addRow("Username", self.user_edit)
        layout.addRow("Password", self.password_edit)
        layout.addRow("Private Key Path", self.key_path_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addRow(buttons)

    def jump_dict(self) -> dict:
        return {
            "host": self.host_edit.text().strip(),
            "port": self.port_spin.value(),
            "username": self.user_edit.text().strip(),
            "credentials": {
                "password": self.password_edit.text(),
                "key_path": self.key_path_edit.text().strip(),
            },
        }


class NetworkingToolsDialog(QDialog):
    """
    Termius-style SSH networking tools dialog.
    """

    def __init__(
        self,
        services,
        host: str,
        port: int,
        username: str,
        creds: object,
        parent=None,
        profile_data: Optional[dict] = None,
    ):
        super().__init__(parent)

        self.services = services
        self.host = host
        self.port = int(port or 22)
        self.username = username
        self.creds = creds
        self.profile_data = profile_data or {}

        self.worker: Optional[SshNetworkingWorker] = None

        self.setWindowTitle(f"Networking Tools — {username}@{host}:{port}")
        self.setMinimumSize(860, 620)

        layout = QVBoxLayout(self)

        header = QLabel(
            f"SSH Target: {username}@{host}:{port}"
        )
        header.setStyleSheet("font-weight: bold;")
        layout.addWidget(header)

        tabs = QTabWidget()

        tabs.addTab(self._build_forwarding_tab(), "Port Forwarding")
        tabs.addTab(self._build_proxy_tab(), "Proxy")
        tabs.addTab(self._build_jump_tab(), "Jump Hosts")
        tabs.addTab(self._build_options_tab(), "Options")
        tabs.addTab(self._build_log_tab(), "Log")

        layout.addWidget(tabs, 1)

        buttons = QHBoxLayout()

        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_session)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_session)

        self.save_btn = QPushButton("Save to Profile")
        self.save_btn.clicked.connect(self.save_profile)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)

        buttons.addWidget(self.start_btn)
        buttons.addWidget(self.stop_btn)
        buttons.addWidget(self.save_btn)
        buttons.addStretch()
        buttons.addWidget(self.close_btn)

        layout.addLayout(buttons)

        self._load_profile()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_forwarding_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.forward_table = QTableWidget(0, 4)
        self.forward_table.setHorizontalHeaderLabels(
            [
                "Type",
                "Listen",
                "Destination",
                "Label",
            ]
        )
        self.forward_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.forward_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.forward_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        layout.addWidget(self.forward_table, 1)

        buttons = QHBoxLayout()

        add_local = QPushButton("Add Local")
        add_local.clicked.connect(lambda: self._add_forward(FORWARD_LOCAL))

        add_remote = QPushButton("Add Remote")
        add_remote.clicked.connect(lambda: self._add_forward(FORWARD_REMOTE))

        add_dynamic = QPushButton("Add Dynamic SOCKS5")
        add_dynamic.clicked.connect(lambda: self._add_forward(FORWARD_DYNAMIC))

        remove = QPushButton("Remove")
        remove.clicked.connect(self._remove_selected_forward)

        buttons.addWidget(add_local)
        buttons.addWidget(add_remote)
        buttons.addWidget(add_dynamic)
        buttons.addStretch()
        buttons.addWidget(remove)

        layout.addLayout(buttons)

        return widget

    def _build_proxy_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Outbound Proxy")
        form = QFormLayout(group)

        self.proxy_type = QComboBox()
        self.proxy_type.addItem("None", PROXY_NONE)
        self.proxy_type.addItem("HTTP CONNECT", PROXY_HTTP)
        self.proxy_type.addItem("SOCKS5", PROXY_SOCKS5)
        self.proxy_type.addItem("ProxyCommand", PROXY_COMMAND)

        self.proxy_host = QLineEdit()
        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(0, 65535)

        self.proxy_user = QLineEdit()
        self.proxy_password = QLineEdit()
        self.proxy_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.proxy_command = QLineEdit()
        self.proxy_command.setPlaceholderText("ssh -W %h:%p proxy.example.com")

        form.addRow("Proxy Type", self.proxy_type)
        form.addRow("Proxy Host", self.proxy_host)
        form.addRow("Proxy Port", self.proxy_port)
        form.addRow("Proxy Username", self.proxy_user)
        form.addRow("Proxy Password", self.proxy_password)
        form.addRow("Proxy Command", self.proxy_command)

        layout.addWidget(group)
        layout.addStretch()

        self.proxy_type.currentIndexChanged.connect(self._update_proxy_fields)
        self._update_proxy_fields()

        return widget

    def _build_jump_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.jump_table = QTableWidget(0, 3)
        self.jump_table.setHorizontalHeaderLabels(
            [
                "Host",
                "Port",
                "Username",
            ]
        )
        self.jump_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.jump_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.jump_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        layout.addWidget(self.jump_table, 1)

        buttons = QHBoxLayout()

        add_jump = QPushButton("Add Jump Host")
        add_jump.clicked.connect(self._add_jump)

        remove_jump = QPushButton("Remove")
        remove_jump.clicked.connect(self._remove_selected_jump)

        buttons.addWidget(add_jump)
        buttons.addStretch()
        buttons.addWidget(remove_jump)

        layout.addLayout(buttons)

        return widget

    def _build_options_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.agent_forwarding_chk = QCheckBox(
            "Enable SSH agent forwarding for terminal sessions"
        )
        self.agent_forwarding_chk.setChecked(False)

        layout.addWidget(self.agent_forwarding_chk)

        note = QLabel(
            "Agent forwarding allows the remote server to use your local SSH agent.\n"
            "Only enable this on trusted hosts."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #999;")
        layout.addWidget(note)

        layout.addStretch()

        return widget

    def _build_log_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        layout.addWidget(self.log_view)

        return widget

    # ------------------------------------------------------------------
    # UI state
    # ------------------------------------------------------------------

    def _update_proxy_fields(self) -> None:
        proxy_type = self.proxy_type.currentData()

        host_visible = proxy_type in (PROXY_HTTP, PROXY_SOCKS5)
        port_visible = proxy_type in (PROXY_HTTP, PROXY_SOCKS5)
        auth_visible = proxy_type in (PROXY_HTTP, PROXY_SOCKS5)
        command_visible = proxy_type == PROXY_COMMAND

        self.proxy_host.setEnabled(host_visible)
        self.proxy_port.setEnabled(port_visible)
        self.proxy_user.setEnabled(auth_visible)
        self.proxy_password.setEnabled(auth_visible)
        self.proxy_command.setEnabled(command_visible)

    def _log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    # ------------------------------------------------------------------
    # Forward table
    # ------------------------------------------------------------------

    def _add_forward(self, kind: str) -> None:
        dialog = ForwardRuleDialog(kind=kind, parent=self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        rule = dialog.rule()
        self._append_forward_rule(rule)

    def _append_forward_rule(self, rule: ForwardRule) -> None:
        row = self.forward_table.rowCount()
        self.forward_table.insertRow(row)

        type_item = QTableWidgetItem(rule.kind.title())
        type_item.setData(Qt.ItemDataRole.UserRole, rule)

        if rule.kind == FORWARD_DYNAMIC:
            destination = "SOCKS5"
        else:
            destination = f"{rule.dest_host}:{rule.dest_port}"

        self.forward_table.setItem(row, 0, type_item)
        self.forward_table.setItem(
            row,
            1,
            QTableWidgetItem(f"{rule.listen_host}:{rule.listen_port}"),
        )
        self.forward_table.setItem(row, 2, QTableWidgetItem(destination))
        self.forward_table.setItem(row, 3, QTableWidgetItem(rule.label))

    def _remove_selected_forward(self) -> None:
        rows = sorted(
            {index.row() for index in self.forward_table.selectedIndexes()},
            reverse=True,
        )

        for row in rows:
            self.forward_table.removeRow(row)

    def _get_forward_rules(self) -> List[ForwardRule]:
        rules = []

        for row in range(self.forward_table.rowCount()):
            item = self.forward_table.item(row, 0)

            if item is None:
                continue

            rule = item.data(Qt.ItemDataRole.UserRole)

            if isinstance(rule, ForwardRule):
                rules.append(rule)

        return rules

    # ------------------------------------------------------------------
    # Jump table
    # ------------------------------------------------------------------

    def _add_jump(self) -> None:
        dialog = JumpHostDialog(parent=self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.jump_dict()

        if not data.get("host"):
            QMessageBox.warning(self, "Jump Host", "Host is required.")
            return

        row = self.jump_table.rowCount()
        self.jump_table.insertRow(row)

        host_item = QTableWidgetItem(data["host"])
        host_item.setData(Qt.ItemDataRole.UserRole, data)

        self.jump_table.setItem(row, 0, host_item)
        self.jump_table.setItem(row, 1, QTableWidgetItem(str(data["port"])))
        self.jump_table.setItem(row, 2, QTableWidgetItem(data["username"]))

    def _remove_selected_jump(self) -> None:
        rows = sorted(
            {index.row() for index in self.jump_table.selectedIndexes()},
            reverse=True,
        )

        for row in rows:
            self.jump_table.removeRow(row)

    def _get_jump_hosts(self) -> List[JumpHost]:
        jumps = []

        for row in range(self.jump_table.rowCount()):
            item = self.jump_table.item(row, 0)

            if item is None:
                continue

            data = item.data(Qt.ItemDataRole.UserRole)

            if not isinstance(data, dict):
                continue

            jumps.append(JumpHost.from_dict(data))

        return jumps

    # ------------------------------------------------------------------
    # Proxy
    # ------------------------------------------------------------------

    def _get_proxy_config(self) -> ProxyConfig:
        return ProxyConfig(
            type=self.proxy_type.currentData(),
            host=self.proxy_host.text().strip(),
            port=self.proxy_port.value(),
            username=self.proxy_user.text().strip(),
            password=self.proxy_password.text(),
            command=self.proxy_command.text().strip(),
        )

    # ------------------------------------------------------------------
    # Profile persistence
    # ------------------------------------------------------------------

    def _load_profile(self) -> None:
        networking = self.profile_data.get("ssh_networking") or {}

        proxy = networking.get("proxy") or {}
        if proxy:
            proxy_config = ProxyConfig.from_dict(proxy)

            index = self.proxy_type.findData(proxy_config.type)
            if index >= 0:
                self.proxy_type.setCurrentIndex(index)

            self.proxy_host.setText(proxy_config.host)
            self.proxy_port.setValue(proxy_config.port)
            self.proxy_user.setText(proxy_config.username)
            self.proxy_password.setText(proxy_config.password)
            self.proxy_command.setText(proxy_config.command)

        self.agent_forwarding_chk.setChecked(
            bool(networking.get("agent_forwarding", False))
        )

        for rule_data in networking.get("forwards", []):
            rule = ForwardRule.from_dict(rule_data)
            self._append_forward_rule(rule)

        for jump_data in networking.get("jump_hosts", []):
            row = self.jump_table.rowCount()
            self.jump_table.insertRow(row)

            host_item = QTableWidgetItem(jump_data.get("host", ""))
            host_item.setData(Qt.ItemDataRole.UserRole, jump_data)

            self.jump_table.setItem(row, 0, host_item)
            self.jump_table.setItem(
                row,
                1,
                QTableWidgetItem(str(jump_data.get("port", 22))),
            )
            self.jump_table.setItem(
                row,
                2,
                QTableWidgetItem(jump_data.get("username", "")),
            )

    def save_profile(self) -> None:
        proxy = self._get_proxy_config()

        forwards = []
        for rule in self._get_forward_rules():
            forwards.append(rule.to_dict())

        jumps = []
        for row in range(self.jump_table.rowCount()):
            item = self.jump_table.item(row, 0)
            if item is not None:
                data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict):
                    jumps.append(data)

        self.profile_data["ssh_networking"] = {
            "proxy": proxy.to_dict(),
            "agent_forwarding": self.agent_forwarding_chk.isChecked(),
            "forwards": forwards,
            "jump_hosts": jumps,
        }

        try:
            if hasattr(self.services, "profiles"):
                save = getattr(self.services.profiles, "save", None)
                if callable(save):
                    save()
        except Exception:
            pass

        QMessageBox.information(
            self,
            "Networking Tools",
            "Networking settings saved to profile data.",
        )

    # ------------------------------------------------------------------
    # Session control
    # ------------------------------------------------------------------

    def _build_target(self) -> SshTarget:
        return SshTarget(
            host=self.host,
            port=self.port,
            username=self.username,
            creds=self.creds,
            proxy=self._get_proxy_config(),
            jumps=self._get_jump_hosts(),
            use_agent=self.agent_forwarding_chk.isChecked(),
        )

    def start_session(self) -> None:
        if self.worker is not None:
            QMessageBox.information(
                self,
                "Networking Tools",
                "Networking session is already running.",
            )
            return

        target = self._build_target()
        forwards = self._get_forward_rules()

        if not forwards:
            reply = QMessageBox.question(
                self,
                "Networking Tools",
                "No port forwarding rules are configured.\n\n"
                "Start anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        self.worker = SshNetworkingWorker(
            target=target,
            forwards=forwards,
            agent_forwarding=self.agent_forwarding_chk.isChecked(),
        )

        self.worker.status_changed.connect(self._on_status_changed)
        self.worker.log_message.connect(self._log)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.forward_started.connect(self._on_forward_started)
        self.worker.stopped.connect(self._on_worker_stopped)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.worker.start()

    def stop_session(self) -> None:
        if self.worker is None:
            return

        self.worker.stop()
        self.worker.wait(3000)

    def _on_status_changed(self, status: str) -> None:
        self._log(f"Status: {status}")

    def _on_error(self, error: str) -> None:
        self._log(f"Error: {error}")

        QMessageBox.critical(
            self,
            "Networking Tools",
            error,
        )

    def _on_forward_started(self, rule: ForwardRule, bound_port: int) -> None:
        self._log(f"Forward active: {rule.display()} on port {bound_port}")

    def _on_worker_stopped(self) -> None:
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        self.worker = None

    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(3000)

        event.accept()