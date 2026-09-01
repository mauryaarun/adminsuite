"""
Rsync folder sync utility for SFTP module.
"""
import os
import shlex
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QPlainTextEdit, QFileDialog,
    QMessageBox, QCheckBox
)

class RsyncWorker(QThread):
    output_ready = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, cmd, cwd=None):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd
        self.proc = None

    def run(self):
        try:
            self.proc = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, cwd=self.cwd, bufsize=1
            )
            for line in self.proc.stdout:
                self.output_ready.emit(line)
            self.proc.wait()
            self.finished_signal.emit(self.proc.returncode)
        except Exception as e:
            self.output_ready.emit(f"\n[ERROR] {e}\n")
            self.finished_signal.emit(-1)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

class RsyncDialog(QDialog):
    def __init__(self, parent, services, host_info):
        super().__init__(parent)
        self.services = services
        self.host_info = host_info
        self.worker = None
        self.setWindowTitle("Rsync Folder Sync")
        self.resize(650, 550)
        layout = QVBoxLayout(self)
        
        # Direction
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Direction:"))
        self.direction = QComboBox()
        self.direction.addItems(["Upload (Local -> Remote)", "Download (Remote -> Local)"])
        dir_layout.addWidget(self.direction, 1)
        layout.addLayout(dir_layout)
        
        # Local Path
        local_layout = QHBoxLayout()
        local_layout.addWidget(QLabel("Local Path:"))
        self.local_path = QLineEdit()
        self.local_path.setPlaceholderText("/path/to/local/folder/")
        local_layout.addWidget(self.local_path, 1)
        browse_local = QPushButton("Browse...")
        browse_local.clicked.connect(self.browse_local)
        local_layout.addWidget(browse_local)
        layout.addLayout(local_layout)
        
        # Remote Path
        remote_layout = QHBoxLayout()
        remote_layout.addWidget(QLabel("Remote Path:"))
        self.remote_path = QLineEdit()
        self.remote_path.setPlaceholderText("/path/to/remote/folder/")
        remote_layout.addWidget(self.remote_path, 1)
        layout.addLayout(remote_layout)
        
        # Options
        opts_layout = QHBoxLayout()
        self.dry_run = QCheckBox("Dry Run")
        self.delete = QCheckBox("Delete extraneous (--delete)")
        opts_layout.addWidget(self.dry_run)
        opts_layout.addWidget(self.delete)
        opts_layout.addStretch()
        layout.addLayout(opts_layout)

        # Advanced Options
        adv_layout = QHBoxLayout()
        adv_layout.addWidget(QLabel("Exclude:"))
        self.exclude = QLineEdit()
        self.exclude.setPlaceholderText("e.g. *.log, .git/")
        adv_layout.addWidget(self.exclude, 1)
        adv_layout.addWidget(QLabel("BW Limit (KB/s):"))
        self.bw_limit = QLineEdit()
        self.bw_limit.setPlaceholderText("0")
        self.bw_limit.setMaximumWidth(60)
        adv_layout.addWidget(self.bw_limit)
        layout.addLayout(adv_layout)
        
        # Output
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("font-family: Consolas, monospace; background: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.output, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("▶ Start Sync")
        self.run_btn.setStyleSheet("background:#3daee9; color:white; font-weight:bold; padding:6px;")
        self.run_btn.clicked.connect(self.start_sync)
        self.stop_btn = QPushButton("⛔ Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_sync)
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

    def browse_local(self):
        path = QFileDialog.getExistingDirectory(self, "Select Local Folder")
        if path: self.local_path.setText(path)

    def build_command(self):
        h = self.host_info
        host, port, user, creds = h.get("host", ""), h.get("port", 22), h.get("user", ""), h.get("creds")
        local, remote = self.local_path.text().strip(), self.remote_path.text().strip()
        if not local or not remote:
            return None, "Local and Remote paths are required."
            
        if not local.endswith("/"): local += "/"
        if not remote.endswith("/"): remote += "/"
        
        ssh_cmd = ["ssh", "-p", str(port), "-o", "StrictHostKeyChecking=no"]
        if creds and getattr(creds, "key_path", None):
            ssh_cmd.extend(["-i", creds.key_path])
        ssh_cmd_str = " ".join(shlex.quote(c) for c in ssh_cmd)
        
        cmd = ["rsync", "-avz", "--progress", "-e", ssh_cmd_str]
        if self.dry_run.isChecked(): cmd.append("--dry-run")
        if self.delete.isChecked(): cmd.append("--delete")
        
        # Exclude
        excludes = [e.strip() for e in self.exclude.text().split(",") if e.strip()]
        for ex in excludes:
            cmd.extend(["--exclude", ex])
            
        # BW Limit
        bw = self.bw_limit.text().strip()
        if bw.isdigit() and int(bw) > 0:
            cmd.extend(["--bwlimit", bw])

        if creds and getattr(creds, "password", None) and not getattr(creds, "key_path", None):
            try:
                subprocess.run(["sshpass", "-V"], capture_output=True, check=True)
                cmd = ["sshpass", "-p", creds.password] + cmd
            except (FileNotFoundError, subprocess.CalledProcessError):
                return None, "Password auth requires 'sshpass' installed locally."
                
        remote_target = f"{user}@{host}:{remote}"
        if self.direction.currentIndex() == 0:
            cmd.extend([local, remote_target])
        else:
            cmd.extend([remote_target, local])
        return cmd, None

    def start_sync(self):
        cmd, err = self.build_command()
        if err:
            QMessageBox.warning(self, "Validation", err)
            return
        self.output.clear()
        self.output.appendPlainText(f"$ {' '.join(cmd)}\n\n")
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.worker = RsyncWorker(cmd)
        self.worker.output_ready.connect(self.output.appendPlainText)
        self.worker.finished_signal.connect(self.sync_finished)
        self.worker.start()

    def stop_sync(self):
        if self.worker:
            self.worker.stop()
            self.output.appendPlainText("\n[STOPPED BY USER]\n")

    def sync_finished(self, rc):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if rc == 0:
            self.output.appendPlainText("\n✅ Sync completed successfully.\n")
        else:
            self.output.appendPlainText(f"\n❌ Sync finished with exit code {rc}.\n")