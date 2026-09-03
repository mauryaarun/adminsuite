from __future__ import annotations

import subprocess
from typing import Any, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from admin_suite.ssh.client import ssh_kwargs
from admin_suite.ssh.credentials import SshCredentials, profile_creds
from admin_suite.ssh.hostkeys import create_ssh_client


class RemoteExecThread(QThread):
    """
    Execute one command remotely or locally.
    """

    finished_cmd = pyqtSignal(str, int)

    def __init__(
        self,
        profile: Optional[str] = None,
        cmd: str = "",
        timeout: Optional[float] = None,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.cmd = cmd
        self.timeout = timeout

    def run(self) -> None:
        try:
            # Example implementation for SSH execution
            creds = profile_creds(self.profile)
            kw = ssh_kwargs(creds)
            client = create_ssh_client()
            client.connect(**kw)

            stdin, stdout, stderr = client.exec_command(
                self.cmd,
                timeout=self.timeout,
            )

            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")

            rc = stdout.channel.recv_exit_status()

            client.close()

            self.finished_cmd.emit(out + err, rc)

        except Exception as e:
            self.finished_cmd.emit(f"[error] {e}", -1)
