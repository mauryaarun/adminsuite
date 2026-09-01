"""
Basic Ansible runner thread.

This is kept for direct Ansible ad-hoc execution.
The main UI primarily uses MultiHostExecThread for profile-based execution.
"""

from __future__ import annotations

import subprocess
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal


class AnsibleRunnerThread(QThread):
    """
    Run ansible or ansible-playbook using argument lists.
    """

    output_ready = pyqtSignal(str)
    run_finished = pyqtSignal(bool)

    def __init__(
        self,
        command: str = "",
        hosts: str = "all",
        playbook_path: Optional[str] = None,
    ):
        super().__init__()

        self.command = command
        self.hosts = hosts or "all"
        self.playbook_path = playbook_path

    def run(self) -> None:
        try:
            if self.playbook_path:
                args = ["ansible-playbook", self.playbook_path]
            else:
                args = [
                    "ansible",
                    self.hosts,
                    "-m",
                    "shell",
                    "-a",
                    self.command,
                ]

            self.output_ready.emit("$ " + " ".join(args) + "\n")

            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
            )

            for line in proc.stdout:
                self.output_ready.emit(line)

            proc.wait()

            self.run_finished.emit(proc.returncode == 0)

        except Exception as e:
            self.output_ready.emit(f"\n[ERROR] {e}\n")
            self.run_finished.emit(False)
